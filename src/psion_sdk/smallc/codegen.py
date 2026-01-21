"""
HD6303 Code Generator for Small-C
==================================

This module generates HD6303 assembly code from the Small-C AST.
It implements the code generation phase of the compiler, producing
assembly that can be assembled by psasm.

Code Generation Strategy
------------------------
The code generator uses a simple stack-based evaluation model:

1. Expressions evaluate to a result in the D register (A:B for 16-bit)
2. For binary operations, left operand is pushed, right is in D
3. Local variables are accessed relative to the X register (frame pointer)
4. Global variables are accessed by direct/extended addressing

Register Usage
--------------
| Register | Usage                                    |
|----------|------------------------------------------|
| A        | Expression evaluation (high byte)        |
| B        | Expression evaluation (low byte)         |
| D (A:B)  | 16-bit operations, function returns      |
| X        | Frame pointer, array/pointer operations  |
| SP       | Stack pointer                            |

Stack Frame Layout
------------------
When a function is called, the stack frame looks like:

    +----------------+ <- SP before call
    | Return address |  (pushed by JSR)
    +----------------+
    | Saved X        |  (saved frame pointer)
    +----------------+ <- X (new frame pointer)
    | Local var N    |
    | ...            |
    | Local var 1    |
    +----------------+ <- SP during function
    | Temp values    |  (expression evaluation)
    +----------------+

Arguments are pushed right-to-left, so first argument is at highest address.
Caller cleans up arguments after call.

Comparison Strategy (SUBD vs CPD)
---------------------------------
The HD6303 does NOT have a CPD (Compare D) instruction - that's 68HC11 only.
We use SUBD for all D register comparisons:

1. SUBD and (hypothetical) CPD both compute (D - operand) and set identical
   condition flags: N (negative), Z (zero), V (overflow), C (carry/borrow).

2. The ONLY difference: SUBD modifies D, while CPD would preserve it.

3. For boolean tests (SUBD #0): D is unchanged because D - 0 = D.

4. For switch/comparison operations: D is either immediately overwritten with
   the boolean result (0 or 1), or reloaded from the stack for the next case,
   so the modification doesn't matter.

This approach is actually MORE efficient than CPD would be - SUBD #0 is 3 bytes
vs. 4 bytes for CPD #0, saving code space in boolean tests.

Generated Assembly Format
-------------------------
The generated assembly uses the psasm assembler syntax:
- Labels with colon: label:
- Comments with semicolon: ; comment
- Directives: ORG, FCB, FCC, FDB, RMB, EQU

Example output:
    ; Function: main
    _main:
        PSHX            ; Save frame pointer
        TSX             ; Set up new frame
        ; ... function body ...
        PULX            ; Restore frame pointer
        RTS

Usage
-----
>>> from psion_sdk.smallc.parser import parse_source
>>> from psion_sdk.smallc.codegen import CodeGenerator
>>> ast = parse_source('void main() { int x; x = 42; }')
>>> gen = CodeGenerator()
>>> asm = gen.generate(ast)
>>> print(asm)
"""

from typing import Optional
from dataclasses import dataclass

from psion_sdk.smallc.ast import (
    ASTNode,
    ASTVisitor,
    ProgramNode,
    FunctionNode,
    VariableDeclaration,
    ParameterNode,
    BlockStatement,
    ExpressionStatement,
    IfStatement,
    WhileStatement,
    ForStatement,
    DoWhileStatement,
    SwitchStatement,
    CaseClause,
    ReturnStatement,
    BreakStatement,
    ContinueStatement,
    GotoStatement,
    LabelStatement,
    Expression,
    BinaryExpression,
    UnaryExpression,
    AssignmentExpression,
    TernaryExpression,
    CallExpression,
    ArraySubscript,
    IdentifierExpression,
    NumberLiteral,
    CharLiteral,
    StringLiteral,
    CastExpression,
    SizeofExpression,
    BinaryOperator,
    UnaryOperator,
    AssignmentOperator,
    # Struct support
    StructDefinition,
    StructField,
    MemberAccessExpression,
)
from psion_sdk.smallc.types import CType, BaseType, TYPE_CHAR, TYPE_INT
from psion_sdk.smallc.errors import CCodeGenError, CTypeError


# =============================================================================
# Symbol Table for Code Generation
# =============================================================================

@dataclass
class SymbolInfo:
    """
    Information about a symbol (variable or function).

    Attributes:
        name: Symbol name
        sym_type: The C type
        is_global: True for global variables
        offset: Stack offset for locals (negative from X)
        is_parameter: True for function parameters
    """
    name: str
    sym_type: CType
    is_global: bool = False
    offset: int = 0
    is_parameter: bool = False


@dataclass
class FunctionInfo:
    """
    Information about a function during code generation.

    Attributes:
        name: Function name
        return_type: Return type
        param_count: Number of parameters
        local_size: Total size of local variables
    """
    name: str
    return_type: CType
    param_count: int = 0
    local_size: int = 0


@dataclass
class ExternalFuncInfo:
    """
    Information about an external OPL procedure declaration.

    External procedures are declared with the 'external' keyword and represent
    OPL procedures that exist on the Psion device. Calls to these are transformed
    into QCode injection sequences at runtime.

    Attributes:
        name: Procedure name (as declared in C, without OPL suffix)
        return_type: Return type determines OPL name suffix and restore function:
                    - void: no suffix, _call_opl (return ignored)
                    - int: % suffix, _call_opl (BCD float to int)
                    - char: $ suffix, _call_opl_str (first char of string)
        param_count: Number of parameters (0-4, enforced by parser)
        param_types: List of parameter types (all must be int or char)
    """
    name: str
    return_type: CType
    param_count: int
    param_types: list[CType]


@dataclass
class StructFieldInfo:
    """
    Information about a struct field for code generation.

    Attributes:
        name: Field name
        field_type: The C type of the field
        offset: Byte offset within the struct
    """
    name: str
    field_type: CType
    offset: int


@dataclass
class StructInfo:
    """
    Information about a struct type for code generation.

    Attributes:
        name: Struct type name
        fields: List of field info in declaration order
        size: Total size of the struct in bytes
    """
    name: str
    fields: list[StructFieldInfo]
    size: int


# =============================================================================
# Code Generator Class
# =============================================================================

class CodeGenerator(ASTVisitor):
    """
    Generates HD6303 assembly from Small-C AST.

    The generator traverses the AST and emits assembly instructions
    for each node. It maintains symbol tables for variables and
    generates unique labels for control flow.

    Attributes:
        output: List of generated assembly lines
        target_model: Target Psion model (CM, XP, LA, LZ, LZ64)
    """

    # Model display characteristics: model -> (rows, columns)
    MODEL_DISPLAY = {
        "CM": (2, 16),
        "XP": (2, 16),
        "LA": (4, 20),
        "LZ": (4, 20),
        "LZ64": (4, 20),
    }

    def __init__(self, target_model: str = "XP", has_float_support: bool = False):
        """
        Initialize the code generator.

        Args:
            target_model: Target Psion model (CM, XP, LA, LZ, LZ64).
                         Defaults to XP for broad compatibility with 2-line models.
            has_float_support: Whether to include floating point runtime support.
                              True if float.h was included, False otherwise.
        """
        # Target model for generated code
        self._target_model = target_model.upper() if target_model else "XP"

        # Whether to include floating point support (fpruntime.inc)
        self._has_float_support = has_float_support

        # Assembly output lines
        self._output: list[str] = []

        # Symbol tables
        self._globals: dict[str, SymbolInfo] = {}
        self._locals: dict[str, SymbolInfo] = {}

        # Current function context
        self._current_function: Optional[FunctionInfo] = None
        self._local_offset: int = 0
        self._current_local_size: int = 0

        # Label generation
        self._label_counter: int = 0

        # String literal pool
        self._strings: list[tuple[str, str]] = []  # (label, value)

        # Loop context for break/continue
        self._loop_stack: list[tuple[str, str]] = []  # (continue_label, break_label)

        # Switch context
        self._switch_stack: list[str] = []  # break label for switch

        # External OPL procedure declarations
        # These are procedures declared with 'external' keyword that exist in
        # OPL code on the device. Calls to these are transformed into QCode
        # injection sequences at runtime.
        # Maps function name -> ExternalFuncInfo for complete procedure info:
        #   - Return type (determines OPL suffix and restore function)
        #   - Parameter count and types (for QCode buffer generation)
        self._external_funcs: dict[str, ExternalFuncInfo] = {}

        # Expression size tracking for optimization
        # Tracks the size (in bytes) of the last expression result:
        # - 1 = char (value in B, A cleared to 0) - can use TSTB for boolean test
        # - 2 = int (value in D) - must use SUBD #0 for boolean test
        # This enables 8-bit boolean tests: TSTB (1 byte) vs SUBD #0 (3 bytes)
        self._last_expr_size: int = 2

        # Struct type definitions
        # Maps struct name -> StructInfo for field layout and size computation
        self._structs: dict[str, StructInfo] = {}

        # Stack depth tracking for function call arguments
        # When generating function arguments, we push them one by one. Each push
        # changes SP, so TSX gives a different value. This tracks how many bytes
        # have been pushed so we can compensate when computing local addresses.
        self._arg_push_depth: int = 0

    def generate(self, program: ProgramNode) -> str:
        """
        Generate assembly code from AST.

        Args:
            program: The root AST node

        Returns:
            Complete HD6303 assembly source code
        """
        self._output = []
        self._globals = {}
        self._strings = []
        self._label_counter = 0
        self._external_funcs = {}
        self._structs = {}
        self._last_expr_size = 2  # Reset expression size tracking

        # Emit header (includes)
        self._emit_header()

        # First pass: collect struct definitions, global variables, and external declarations
        for decl in program.declarations:
            if isinstance(decl, StructDefinition):
                self._add_struct(decl)
                continue
            if isinstance(decl, VariableDeclaration) and decl.is_global:
                self._add_global(decl)
            elif isinstance(decl, FunctionNode) and decl.is_external:
                # Track external OPL procedure declarations with their complete info
                # These will be called via QCode injection at runtime
                # Stored info includes:
                #   - Return type (determines OPL suffix and restore function)
                #   - Parameter count and types (for QCode buffer generation)
                self._external_funcs[decl.name] = ExternalFuncInfo(
                    name=decl.name,
                    return_type=decl.return_type,
                    param_count=len(decl.parameters),
                    param_types=[p.param_type for p in decl.parameters],
                )

        # Emit startup code - must be first executable code
        # Uses BSR (relative branch) so _main must follow immediately
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("; Entry Point - called by USR()")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("_entry:")
        self._emit("        BSR     _main           ; Call main (relative branch)")
        self._emit("        RTS                     ; Return to OPL")
        self._emit("")

        # Find and emit main() first (so BSR can reach it)
        main_func = None
        other_funcs = []
        for decl in program.declarations:
            if isinstance(decl, FunctionNode) and not decl.is_forward_decl:
                if decl.name == "main":
                    main_func = decl
                else:
                    other_funcs.append(decl)

        # Generate main first
        if main_func:
            self._generate_function(main_func)

        # Then other functions
        for func in other_funcs:
            self._generate_function(func)

        # Emit includes AFTER user code (so entry point is first)
        self._emit("")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("; Runtime Library and System Definitions")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("        INCLUDE \"psion.inc\"")
        self._emit("        INCLUDE \"runtime.inc\"")
        if self._has_float_support:
            self._emit("        INCLUDE \"float.inc\"       ; FP constants and macros")
            self._emit("        INCLUDE \"fpruntime.inc\"  ; Floating point support")

        # Emit global variables
        self._emit_globals()

        # Emit string literals
        self._emit_strings()

        # Emit footer
        self._emit_footer()

        return "\n".join(self._output)

    # =========================================================================
    # Assembly Output Methods
    # =========================================================================

    def _emit(self, line: str = "") -> None:
        """Emit a line of assembly."""
        self._output.append(line)

    def _emit_comment(self, comment: str) -> None:
        """Emit a comment."""
        self._emit(f"; {comment}")

    def _emit_label(self, label: str) -> None:
        """Emit a label definition."""
        self._emit(f"{label}:")

    def _emit_instruction(self, mnemonic: str, operand: str = "") -> None:
        """Emit an instruction with optional operand."""
        if operand:
            self._emit(f"        {mnemonic:<8}{operand}")
        else:
            self._emit(f"        {mnemonic}")

    def _emit_load_sp(self) -> None:
        """Load stack pointer into X. On HD6303, TSX gives X=SP directly."""
        self._emit_instruction("TSX", "")

    def _emit_boolean_test(self) -> None:
        """Emit code to test if expression result is zero, setting Z flag.

        This method optimizes boolean tests based on the size of the last
        expression result:
        - For char (1 byte): Uses TSTB (1 byte) since A is known to be 0
        - For int (2 bytes): Uses SUBD #0 (3 bytes)

        The optimization saves 2 bytes per boolean test for char expressions.
        After this call, Z flag is set if expression was zero.
        """
        if self._last_expr_size == 1:
            # Char expression: A is already 0, so D==0 iff B==0
            # TSTB is 1 byte vs SUBD #0 which is 3 bytes
            self._emit_instruction("TSTB", "")
        else:
            # Int expression: must test full D register
            # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
            self._emit_instruction("SUBD", "#0")

    def _new_label(self, prefix: str = "L") -> str:
        """Generate a unique label."""
        self._label_counter += 1
        return f"_{prefix}{self._label_counter}"

    # =========================================================================
    # Constant Folding
    # =========================================================================

    def _try_eval_constant(self, expr: Expression) -> Optional[int]:
        """
        Try to evaluate an expression as a compile-time constant.

        Returns the constant value (as 16-bit signed int) if the expression
        can be fully evaluated at compile time, or None if it cannot.

        Supports:
        - Number literals and char literals
        - Binary operations: +, -, *, /, %, &, |, ^, <<, >>
        - Comparison operations: ==, !=, <, >, <=, >=
        - Unary operations: -, ~, !
        - Nested constant expressions

        This optimization is called "constant folding" and reduces code size
        by computing values at compile time instead of runtime.
        """
        if isinstance(expr, NumberLiteral):
            return expr.value & 0xFFFF

        if isinstance(expr, CharLiteral):
            return expr.value & 0xFF

        if isinstance(expr, UnaryExpression):
            operand = self._try_eval_constant(expr.operand)
            if operand is None:
                return None

            op = expr.operator
            if op == UnaryOperator.NEGATE:
                return (-operand) & 0xFFFF
            elif op == UnaryOperator.POSITIVE:
                return operand
            elif op == UnaryOperator.BITWISE_NOT:
                return (~operand) & 0xFFFF
            elif op == UnaryOperator.LOGICAL_NOT:
                return 0 if operand else 1
            # Other unary ops (address-of, deref, inc/dec) are not constant
            return None

        if isinstance(expr, BinaryExpression):
            left = self._try_eval_constant(expr.left)
            right = self._try_eval_constant(expr.right)
            if left is None or right is None:
                return None

            op = expr.operator
            try:
                if op == BinaryOperator.ADD:
                    result = left + right
                elif op == BinaryOperator.SUBTRACT:
                    result = left - right
                elif op == BinaryOperator.MULTIPLY:
                    result = left * right
                elif op == BinaryOperator.DIVIDE:
                    if right == 0:
                        return None  # Division by zero - let it fail at runtime
                    result = left // right
                elif op == BinaryOperator.MODULO:
                    if right == 0:
                        return None
                    result = left % right
                elif op == BinaryOperator.BITWISE_AND:
                    result = left & right
                elif op == BinaryOperator.BITWISE_OR:
                    result = left | right
                elif op == BinaryOperator.BITWISE_XOR:
                    result = left ^ right
                elif op == BinaryOperator.LEFT_SHIFT:
                    result = left << (right & 0xF)  # Limit shift to 0-15
                elif op == BinaryOperator.RIGHT_SHIFT:
                    result = left >> (right & 0xF)
                elif op == BinaryOperator.EQUAL:
                    result = 1 if left == right else 0
                elif op == BinaryOperator.NOT_EQUAL:
                    result = 1 if left != right else 0
                elif op == BinaryOperator.LESS:
                    result = 1 if left < right else 0
                elif op == BinaryOperator.GREATER:
                    result = 1 if left > right else 0
                elif op == BinaryOperator.LESS_EQ:
                    result = 1 if left <= right else 0
                elif op == BinaryOperator.GREATER_EQ:
                    result = 1 if left >= right else 0
                elif op == BinaryOperator.LOGICAL_AND:
                    result = 1 if (left and right) else 0
                elif op == BinaryOperator.LOGICAL_OR:
                    result = 1 if (left or right) else 0
                else:
                    return None  # Unknown operator
                return result & 0xFFFF
            except (ValueError, OverflowError):
                return None

        if isinstance(expr, CastExpression):
            value = self._try_eval_constant(expr.expression)
            if value is None:
                return None
            # Apply cast (char truncates to 8 bits)
            if expr.target_type.base_type == BaseType.CHAR:
                return value & 0xFF
            return value & 0xFFFF

        # Not a constant expression
        return None

    @staticmethod
    def _is_power_of_2(n: int) -> bool:
        """Check if n is a positive power of 2."""
        return n > 0 and (n & (n - 1)) == 0

    @staticmethod
    def _log2(n: int) -> int:
        """Return log base 2 of n (assumes n is a power of 2)."""
        result = 0
        while n > 1:
            n >>= 1
            result += 1
        return result

    # =========================================================================
    # Expression Type Inference
    # =========================================================================
    #
    # This section provides methods to determine the type of expressions at
    # compile time. This is essential for:
    #
    # 1. **8-bit char arithmetic**: When both operands of a binary operation
    #    are `char` type, we can use efficient 8-bit HD6303 instructions
    #    (ADDB, SUBB, ANDB, ORAB, EORB) instead of 16-bit operations.
    #
    # 2. **Type safety**: Mixed char/int operations are disallowed to enforce
    #    type discipline and avoid implicit promotions that could surprise users.
    #
    # 3. **Boolean test optimization**: Knowing expression size allows using
    #    TSTB (1 byte) vs SUBD #0 (3 bytes) for zero tests.
    #
    # Type Rules:
    # -----------
    # - CharLiteral ('A')          -> char
    # - NumberLiteral (42)         -> int
    # - IdentifierExpression (x)   -> symbol's declared type
    # - BinaryExpression:
    #   - char OP char -> char (for +, -, &, |, ^) or int (for *, /, %, <<, >>)
    #   - int OP int   -> int
    #   - char OP int  -> ERROR (mixed types not allowed)
    #   - int OP char  -> ERROR (mixed types not allowed)
    #
    # Operations that support 8-bit:  +, -, &, |, ^
    # Operations that require 16-bit: *, /, %, <<, >> (promote char to int)
    # =========================================================================

    # Operations that can be performed with 8-bit instructions when both
    # operands are char. These have direct HD6303 equivalents:
    # ADDB, SUBB, ANDB, ORAB, EORB
    _CHAR_SUPPORTED_OPS = frozenset([
        BinaryOperator.ADD,
        BinaryOperator.SUBTRACT,
        BinaryOperator.BITWISE_AND,
        BinaryOperator.BITWISE_OR,
        BinaryOperator.BITWISE_XOR,
    ])

    # Operations that always require 16-bit even for char operands.
    # These have no 8-bit HD6303 equivalent, so we promote to 16-bit.
    _CHAR_PROMOTED_OPS = frozenset([
        BinaryOperator.MULTIPLY,
        BinaryOperator.DIVIDE,
        BinaryOperator.MODULO,
        BinaryOperator.LEFT_SHIFT,
        BinaryOperator.RIGHT_SHIFT,
    ])

    # Comparison operations - these compare in the native width but always
    # produce a 16-bit boolean result (0 or 1).
    _COMPARISON_OPS = frozenset([
        BinaryOperator.EQUAL,
        BinaryOperator.NOT_EQUAL,
        BinaryOperator.LESS,
        BinaryOperator.GREATER,
        BinaryOperator.LESS_EQ,
        BinaryOperator.GREATER_EQ,
    ])

    # Logical operations - these always produce 16-bit boolean results
    # and handle their own short-circuit evaluation.
    _LOGICAL_OPS = frozenset([
        BinaryOperator.LOGICAL_AND,
        BinaryOperator.LOGICAL_OR,
    ])

    def _get_expression_type(self, expr: Expression) -> CType:
        """
        Determine the result type of an expression.

        This method infers the type of any expression in the AST, which is
        essential for generating correct code (8-bit vs 16-bit) and detecting
        type errors (mixed char/int operations).

        Type inference rules:
        - CharLiteral ('A'): Returns TYPE_CHAR
        - NumberLiteral (42): Returns TYPE_INT
        - IdentifierExpression: Returns the symbol's declared type
        - BinaryExpression: Validates operand types and returns result type
        - UnaryExpression: Returns operand type (with some exceptions)
        - CastExpression: Returns the target type
        - ArraySubscript: Returns the element type
        - CallExpression: Returns int (function return type not tracked here)

        Args:
            expr: The expression to type-check

        Returns:
            CType representing the expression's result type

        Raises:
            CTypeError: If operand types are incompatible (e.g., char + int)
            CCodeGenError: If expression type cannot be determined
        """
        if isinstance(expr, CharLiteral):
            # Character literals are always char type
            return TYPE_CHAR

        if isinstance(expr, NumberLiteral):
            # Numeric literals are always int type
            # Note: In Small-C, all integer constants are int (16-bit)
            return TYPE_INT

        if isinstance(expr, StringLiteral):
            # String literals decay to char* (pointer to char)
            return CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)

        if isinstance(expr, IdentifierExpression):
            # Look up the symbol to get its declared type
            info = self._lookup(expr.name)
            if info is None:
                # Unknown identifier - this should have been caught by parser
                raise CCodeGenError(f"undeclared identifier '{expr.name}'")
            return info.sym_type

        if isinstance(expr, BinaryExpression):
            return self._get_binary_expression_type(expr)

        if isinstance(expr, UnaryExpression):
            return self._get_unary_expression_type(expr)

        if isinstance(expr, CastExpression):
            # Cast expressions have an explicit target type
            return expr.target_type

        if isinstance(expr, ArraySubscript):
            # Array subscript returns the element type
            return self._get_array_subscript_type(expr)

        if isinstance(expr, CallExpression):
            # For now, assume all functions return int
            # TODO: Track function return types for better type checking
            return TYPE_INT

        if isinstance(expr, TernaryExpression):
            # Ternary has complex type rules - for now, assume int
            # Both branches should have compatible types in proper C
            return TYPE_INT

        if isinstance(expr, AssignmentExpression):
            # Assignment returns the type of the target
            return self._get_expression_type(expr.target)

        if isinstance(expr, SizeofExpression):
            # sizeof always returns int (size in bytes)
            return TYPE_INT

        if isinstance(expr, MemberAccessExpression):
            # Member access returns the type of the field
            object_type = self._get_expression_type(expr.object_expr)

            # Determine struct name based on operator
            if expr.is_arrow:
                # ptr->field: object must be pointer to struct
                if not object_type.is_pointer or not object_type.struct_name:
                    raise CCodeGenError(
                        "'->' requires pointer to struct", expr.location
                    )
                struct_name = object_type.struct_name
            else:
                # obj.field: object must be struct value
                if object_type.is_pointer:
                    raise CCodeGenError(
                        "'.' requires struct value, use '->' for pointers", expr.location
                    )
                if not object_type.struct_name:
                    raise CCodeGenError(
                        "'.' requires struct type", expr.location
                    )
                struct_name = object_type.struct_name

            # Look up field type
            field_info = self._get_struct_field_info(struct_name, expr.member_name)
            return field_info.field_type

        # Unknown expression type
        raise CCodeGenError(f"cannot determine type of expression: {type(expr).__name__}")

    def _get_binary_expression_type(self, expr: BinaryExpression) -> CType:
        """
        Determine the result type of a binary expression.

        This method enforces type safety for binary operations:
        - Both operands must have the same base type (both char or both int)
        - Mixed char/int operations raise a CTypeError
        - For char operands, the result type depends on the operation

        Args:
            expr: The binary expression to type-check

        Returns:
            CType for the expression result

        Raises:
            CTypeError: If operand types are incompatible
        """
        op = expr.operator
        left_type = self._get_expression_type(expr.left)
        right_type = self._get_expression_type(expr.right)

        # Logical operations always produce 16-bit boolean result
        if op in self._LOGICAL_OPS:
            return TYPE_INT

        # For pointers, use existing 16-bit path (no 8-bit pointer arithmetic)
        if left_type.is_pointer or right_type.is_pointer:
            return TYPE_INT

        # For arrays (which decay to pointers), use 16-bit path
        if left_type.array_size > 0 or right_type.array_size > 0:
            return TYPE_INT

        # Determine operand types
        left_is_char = (left_type.base_type == BaseType.CHAR and
                        not left_type.is_pointer and
                        left_type.array_size == 0)
        right_is_char = (right_type.base_type == BaseType.CHAR and
                         not right_type.is_pointer and
                         right_type.array_size == 0)
        left_is_int = (left_type.base_type == BaseType.INT and
                       not left_type.is_pointer and
                       left_type.array_size == 0)
        right_is_int = (right_type.base_type == BaseType.INT and
                        not right_type.is_pointer and
                        right_type.array_size == 0)

        # Mixed char/int handling
        # For + and -, we allow mixing char and int. The result is char (8-bit)
        # with natural overflow behavior. This enables common patterns like:
        #   char c = 'A'; c = c + 1;  // c becomes 'B'
        #   char c = 'z'; c = c - 32; // c becomes 'Z' (lowercase to uppercase)
        #
        # For other operations (&, |, ^, *, /, %, etc.), mixed types are an error.
        is_mixed = ((left_is_char and right_is_int) or
                    (left_is_int and right_is_char))

        if is_mixed:
            # Allow + and - with mixed char/int, result is char (8-bit)
            if op in (BinaryOperator.ADD, BinaryOperator.SUBTRACT):
                return TYPE_CHAR

            # Comparisons with mixed types are allowed, result is int (boolean)
            if op in self._COMPARISON_OPS:
                return TYPE_INT

            # For all other operations, mixed types are an error
            left_type_name = "char" if left_is_char else "int"
            right_type_name = "char" if right_is_char else "int"

            raise CTypeError(
                f"cannot mix 'char' and 'int' operands in '{op.name.lower()}' expression",
                expected_type=left_type_name,
                actual_type=right_type_name,
                # Note: location would be set by caller if available
            )

        # Both operands are char
        if left_is_char and right_is_char:
            # Comparison operations always return int (16-bit boolean)
            if op in self._COMPARISON_OPS:
                return TYPE_INT

            # Operations that support 8-bit return char
            if op in self._CHAR_SUPPORTED_OPS:
                return TYPE_CHAR

            # Operations that require 16-bit promote to int
            if op in self._CHAR_PROMOTED_OPS:
                return TYPE_INT

        # Both operands are int, or fallback
        return TYPE_INT

    def _get_unary_expression_type(self, expr: UnaryExpression) -> CType:
        """
        Determine the result type of a unary expression.

        Most unary operations preserve the operand type, with exceptions:
        - Address-of (&x) returns a pointer type
        - Dereference (*p) returns the pointed-to type
        - Logical NOT (!) always returns int (boolean)

        Args:
            expr: The unary expression to type-check

        Returns:
            CType for the expression result
        """
        op = expr.operator
        operand_type = self._get_expression_type(expr.operand)

        if op == UnaryOperator.ADDRESS_OF:
            # &x returns pointer to x's type
            return CType(
                operand_type.base_type,
                operand_type.is_unsigned,
                is_pointer=True,
                pointer_depth=operand_type.pointer_depth + 1,
            )

        if op == UnaryOperator.DEREFERENCE:
            # *p returns the pointed-to type
            if operand_type.is_pointer and operand_type.pointer_depth > 0:
                return operand_type.dereference()
            # Dereferencing non-pointer is an error but let codegen handle it
            return TYPE_INT

        if op == UnaryOperator.LOGICAL_NOT:
            # !x always returns int (0 or 1)
            return TYPE_INT

        # All other unary ops preserve the operand type:
        # NEGATE (-), POSITIVE (+), BITWISE_NOT (~), PRE/POST INC/DEC
        return operand_type

    def _get_array_subscript_type(self, expr: ArraySubscript) -> CType:
        """
        Determine the result type of an array subscript expression.

        Array subscript returns the element type of the array.

        Args:
            expr: The array subscript expression

        Returns:
            CType for the element type
        """
        array_type = self._get_expression_type(expr.array)

        if array_type.is_pointer or array_type.array_size > 0:
            return array_type.dereference()

        # Not an array or pointer - return int as fallback
        return TYPE_INT

    def _describe_expression(self, expr: Expression) -> str:
        """
        Create a human-readable description of an expression for error messages.

        This helps users understand which part of their code caused the error.

        Args:
            expr: The expression to describe

        Returns:
            String description like "variable 'x'" or "literal '42'"
        """
        if isinstance(expr, CharLiteral):
            # Format as character literal
            char_val = expr.value
            if 32 <= char_val <= 126:
                return f"character literal '{chr(char_val)}'"
            else:
                return f"character literal (value {char_val})"

        if isinstance(expr, NumberLiteral):
            return f"integer literal '{expr.value}'"

        if isinstance(expr, IdentifierExpression):
            return f"variable '{expr.name}'"

        if isinstance(expr, BinaryExpression):
            return "binary expression"

        if isinstance(expr, UnaryExpression):
            return "unary expression"

        if isinstance(expr, CallExpression):
            return f"function call '{expr.function_name}()'"

        if isinstance(expr, ArraySubscript):
            if isinstance(expr.array, IdentifierExpression):
                return f"array element '{expr.array.name}[...]'"
            return "array subscript"

        return "expression"

    def _is_char_type(self, ctype: CType) -> bool:
        """
        Check if a type is a simple char (not pointer, not array).

        This helper is used to determine if 8-bit operations can be used.

        Args:
            ctype: The type to check

        Returns:
            True if type is simple char, False otherwise
        """
        return (ctype.base_type == BaseType.CHAR and
                not ctype.is_pointer and
                ctype.array_size == 0)

    def _is_int_type(self, ctype: CType) -> bool:
        """
        Check if a type is a simple int (not pointer, not array).

        Args:
            ctype: The type to check

        Returns:
            True if type is simple int, False otherwise
        """
        return (ctype.base_type == BaseType.INT and
                not ctype.is_pointer and
                ctype.array_size == 0)

    # =========================================================================
    # Header and Footer Generation
    # =========================================================================

    def _emit_header(self) -> None:
        """Emit assembly header with includes and configuration."""
        # Get display info for the target model
        rows, cols = self.MODEL_DISPLAY.get(self._target_model, (4, 20))
        display_type = "2-line" if rows == 2 else "4-line"

        self._emit("; =============================================================================")
        self._emit("; Small-C Generated Assembly for HD6303")
        self._emit("; Generated by pscc - Psion Small-C Compiler")
        self._emit("; =============================================================================")
        self._emit("")
        self._emit(f"; Target Model: {self._target_model} ({display_type} display, {cols}x{rows})")
        self._emit("")
        self._emit("; Model-specific assembler directive (can be overridden by psasm -m flag)")
        self._emit(f"        .MODEL  {self._target_model}")
        self._emit("")
        self._emit("; NOTE: Entry point must be FIRST, before any includes that contain code!")
        self._emit("; The Psion loads machine code at runtime addresses, so we need to use")
        self._emit("; relative branching (BSR) to reach main.")
        self._emit("")

    def _emit_footer(self) -> None:
        """Emit assembly footer."""
        self._emit("")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("; End of generated code")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("        END")

    def _emit_globals(self) -> None:
        """Emit global variable declarations."""
        if not self._globals:
            return

        self._emit("")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("; Global Variables")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("")

        for name, info in self._globals.items():
            size = info.sym_type.total_size
            self._emit_label(f"_{name}")
            if size == 1:
                self._emit_instruction("RMB", "1")
            elif size == 2:
                self._emit_instruction("RMB", "2")
            else:
                self._emit_instruction("RMB", str(size))

    def _emit_strings(self) -> None:
        """Emit string literal pool."""
        if not self._strings:
            return

        self._emit("")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("; String Literals")
        self._emit("; -----------------------------------------------------------------------------")
        self._emit("")

        for label, value in self._strings:
            self._emit_label(label)
            # Emit as C-style null-terminated string for C runtime compatibility
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            self._emit_instruction("FCC", f'"{escaped}"')
            self._emit_instruction("FCB", "0")  # Null terminator

    # =========================================================================
    # Symbol Table Management
    # =========================================================================

    def _add_global(self, decl: VariableDeclaration) -> None:
        """Add a global variable to the symbol table."""
        self._globals[decl.name] = SymbolInfo(
            name=decl.name,
            sym_type=decl.var_type,
            is_global=True,
        )

    def _add_struct(self, defn: StructDefinition) -> None:
        """
        Add a struct definition to the struct table.

        Computes field offsets and total struct size by traversing fields
        in declaration order, packing them without any padding (HD6303
        doesn't benefit from alignment).
        """
        fields: list[StructFieldInfo] = []
        offset = 0

        for field in defn.fields:
            # Compute field size
            field_size = self._compute_type_size(field.field_type)
            fields.append(StructFieldInfo(
                name=field.name,
                field_type=field.field_type,
                offset=offset,
            ))
            offset += field_size

        self._structs[defn.name] = StructInfo(
            name=defn.name,
            fields=fields,
            size=offset,
        )

    def _compute_type_size(self, ctype: CType) -> int:
        """
        Compute the size of a type in bytes.

        Handles primitive types, pointers, arrays, and struct types.
        """
        # Pointers are always 2 bytes (16-bit addresses)
        if ctype.is_pointer:
            if ctype.is_array:
                return 2 * ctype.array_size  # Array of pointers
            return 2

        # Struct types
        if ctype.struct_name is not None:
            if ctype.struct_name not in self._structs:
                raise CCodeGenError(f"undefined struct '{ctype.struct_name}'", None)
            struct_size = self._structs[ctype.struct_name].size
            if ctype.is_array:
                return struct_size * ctype.array_size
            return struct_size

        # Primitive types
        if ctype.base_type == BaseType.CHAR:
            element_size = 1
        elif ctype.base_type == BaseType.INT:
            element_size = 2
        elif ctype.base_type == BaseType.VOID:
            return 0
        else:
            element_size = 2  # Default to int size

        if ctype.is_array:
            return element_size * ctype.array_size
        return element_size

    def _get_struct_field_info(self, struct_name: str, field_name: str) -> StructFieldInfo:
        """
        Get field information for a struct member access.

        Args:
            struct_name: Name of the struct type
            field_name: Name of the field

        Returns:
            StructFieldInfo with offset and type

        Raises:
            CCodeGenError: If struct or field is not found
        """
        if struct_name not in self._structs:
            raise CCodeGenError(f"undefined struct '{struct_name}'", None)

        struct = self._structs[struct_name]
        for field in struct.fields:
            if field.name == field_name:
                return field

        raise CCodeGenError(
            f"struct '{struct_name}' has no member '{field_name}'", None
        )

    def _add_local(self, name: str, var_type: CType, is_param: bool = False) -> int:
        """
        Add a local variable to the symbol table.

        Returns the stack offset for the variable.

        Stack layout (locals allocated BEFORE PSHX for positive offsets):
          X, SP -> saved_X_high     (offset 0)
          X+1   -> saved_X_low      (offset 1)
          X+2   -> local[0]         (offset 2)
          X+3   -> local[1]         (offset 3)
          ...
          X+2+N -> ret_high
          X+3+N -> ret_low
          X+4+N -> param[0]
        """
        size = var_type.size if var_type.size > 0 else 2

        if is_param:
            # Parameters are handled separately in _generate_function
            # This shouldn't be called for params anymore
            offset = 4 + self._local_offset
        else:
            # Locals are at positive offsets from frame pointer
            # First local at offset 2 (after saved_X)
            offset = 2 + self._local_offset
            self._local_offset += size

        self._locals[name] = SymbolInfo(
            name=name,
            sym_type=var_type,
            is_global=False,
            offset=offset,
            is_parameter=is_param,
        )

        return offset

    def _lookup(self, name: str) -> Optional[SymbolInfo]:
        """Look up a symbol in local then global scope."""
        if name in self._locals:
            return self._locals[name]
        if name in self._globals:
            return self._globals[name]
        return None

    def _get_array_element_size(self, expr: ArraySubscript) -> int:
        """
        Get the element size for an array subscript expression.

        For char arrays, returns 1.
        For int arrays or pointer arrays, returns 2.

        Args:
            expr: The ArraySubscript expression

        Returns:
            Element size in bytes (1 for char, 2 for int/pointer)
        """
        # Get the array type from the expression
        if isinstance(expr.array, IdentifierExpression):
            info = self._lookup(expr.array.name)
            if info and info.sym_type:
                # Dereference to get element type
                if info.sym_type.is_array or info.sym_type.is_pointer:
                    element_type = info.sym_type.dereference()
                    return element_type.size
        # Default to 2 (int size) for pointers and unknown types
        return 2

    # =========================================================================
    # Function Code Generation
    # =========================================================================

    def _generate_function(self, func: FunctionNode) -> None:
        """Generate code for a function definition."""
        self._emit("")
        self._emit_comment(f"Function: {func.name}")
        self._emit_comment(f"Returns: {func.return_type}")

        # Reset local state
        self._locals = {}
        self._local_offset = 0
        self._current_function = FunctionInfo(
            name=func.name,
            return_type=func.return_type,
            param_count=len(func.parameters),
        )

        # Calculate local size FIRST (needed for param offsets)
        local_size = 0
        if func.body:
            local_size = self._calculate_locals_size(func.body)
        self._current_local_size = local_size

        # Emit function label
        self._emit_label(f"_{func.name}")

        # =====================================================================
        # External OPL Support: Inject setup code at start of main()
        # =====================================================================
        # If any external OPL procedures are declared, we need to call
        # _call_opl_setup at the VERY START of main(), BEFORE any stack
        # modifications (local allocation, PSHX, etc.).
        #
        # This captures the "USR entry SP" which is used later to unwind
        # the stack when calling external OPL procedures. The setup function
        # calculates SP + 4 to point to the return address that leads back
        # to the OPL interpreter.
        #
        # CRITICAL: This MUST be the first instruction in main(), before
        # any local variables are allocated or frame pointer is saved.
        # Otherwise the captured SP will be wrong and stack unwinding will
        # fail catastrophically.
        #
        # Reference: dev_docs/PROCEDURE_CALL_RESEARCH.md
        if func.name == "main" and self._external_funcs:
            self._emit_comment("Initialize external OPL call support")
            self._emit_comment("MUST be first - captures USR entry SP before any stack changes")
            self._emit_instruction("JSR", "_call_opl_setup")

        # Function prologue - NEW LAYOUT for HD6303
        # Allocate locals FIRST, THEN save X, so locals are at positive offsets
        # HD6303 indexed addressing only supports unsigned 0-255 offsets
        if local_size > 0:
            self._emit_comment(f"Allocate {local_size} bytes for locals")
            for _ in range(local_size):
                self._emit_instruction("DES", "")

        # PSHX saves caller's frame pointer
        # HD6303: TSX gives X = SP directly (NOT SP+1 like old 6800)
        self._emit_instruction("PSHX", "")
        self._emit_instruction("TSX", "")

        # Stack layout after prologue:
        #   X, SP -> saved_X_high     (offset 0)
        #   X+1   -> saved_X_low      (offset 1)
        #   X+2   -> local[0]         (offset 2)
        #   X+3   -> local[1]         (offset 3)
        #   ...
        #   X+2+N-1 -> local[N-1]
        #   X+2+N -> ret_high
        #   X+3+N -> ret_low
        #   X+4+N -> param[0]

        # Add parameters to symbol table
        # Params are after: saved_X (2) + locals (N) + return addr (2)
        param_offset = 4 + local_size  # Start after saved X, locals, and return address
        for param in func.parameters:
            self._locals[param.name] = SymbolInfo(
                name=param.name,
                sym_type=param.param_type,
                is_global=False,
                offset=param_offset,
                is_parameter=True,
            )
            param_offset += param.param_type.size

        # Add local variables to symbol table
        if func.body:
            self._collect_locals(func.body)
            # Generate body
            self._generate_block(func.body)

        # Function epilogue
        # NOTE: Don't rely on X here - it may have been destroyed by TSX in binary ops
        # Stack at exit: [saved X], [locals], [return addr]
        self._emit_label(f"_{func.name}_exit")
        self._emit_instruction("PULX", "")  # Restore saved X, SP now at locals
        # Deallocate locals
        if local_size > 0:
            for _ in range(local_size):
                self._emit_instruction("INS", "")
        self._emit_instruction("RTS", "")   # Return

        self._current_function = None
        self._current_local_size = 0

    def _calculate_locals_size(self, block: BlockStatement) -> int:
        """Calculate total size needed for local variables."""
        total = 0
        for decl in block.declarations:
            total += decl.var_type.size if decl.var_type.size > 0 else 2
        return total

    def _collect_locals(self, block: BlockStatement) -> None:
        """Add local variable declarations to symbol table."""
        for decl in block.declarations:
            self._add_local(decl.name, decl.var_type)

    # =========================================================================
    # Statement Code Generation
    # =========================================================================

    def _generate_block(self, block: BlockStatement) -> None:
        """Generate code for a block statement."""
        for stmt in block.statements:
            self._generate_statement(stmt)

    def _generate_statement(self, stmt) -> None:
        """Generate code for any statement."""
        if stmt is None:
            return

        if isinstance(stmt, BlockStatement):
            self._generate_block(stmt)
        elif isinstance(stmt, ExpressionStatement):
            self._generate_expression(stmt.expression)
        elif isinstance(stmt, IfStatement):
            self._generate_if(stmt)
        elif isinstance(stmt, WhileStatement):
            self._generate_while(stmt)
        elif isinstance(stmt, ForStatement):
            self._generate_for(stmt)
        elif isinstance(stmt, DoWhileStatement):
            self._generate_do_while(stmt)
        elif isinstance(stmt, SwitchStatement):
            self._generate_switch(stmt)
        elif isinstance(stmt, ReturnStatement):
            self._generate_return(stmt)
        elif isinstance(stmt, BreakStatement):
            self._generate_break()
        elif isinstance(stmt, ContinueStatement):
            self._generate_continue()
        elif isinstance(stmt, GotoStatement):
            self._generate_goto(stmt)
        elif isinstance(stmt, LabelStatement):
            self._generate_label(stmt)

    def _generate_if(self, stmt: IfStatement) -> None:
        """Generate code for if statement."""
        else_label = self._new_label("else")
        end_label = self._new_label("endif")

        # Generate condition
        self._emit_comment("if condition")
        self._generate_expression(stmt.condition)

        # Test condition (D == 0 means false)
        # Use helper for 8-bit optimization when condition is char
        self._emit_boolean_test()
        self._emit_instruction("BEQ", else_label)

        # Then branch
        self._generate_statement(stmt.then_branch)

        if stmt.else_branch:
            self._emit_instruction("BRA", end_label)
            self._emit_label(else_label)
            self._generate_statement(stmt.else_branch)
            self._emit_label(end_label)
        else:
            self._emit_label(else_label)

    def _generate_while(self, stmt: WhileStatement) -> None:
        """Generate code for while statement.

        Uses JMP for loop control to handle large loop bodies that
        exceed the 127-byte limit of relative branches.
        """
        start_label = self._new_label("while")
        body_label = self._new_label("wbody")
        end_label = self._new_label("wend")

        self._loop_stack.append((start_label, end_label))

        self._emit_label(start_label)

        # Generate condition
        self._emit_comment("while condition")
        self._generate_expression(stmt.condition)

        # Test condition - use short forward branch + JMP for long distance
        # Use helper for 8-bit optimization when condition is char
        self._emit_boolean_test()
        self._emit_instruction("BNE", body_label)  # Short forward jump
        self._emit_instruction("JMP", end_label)   # Long jump if condition false

        self._emit_label(body_label)

        # Body
        self._generate_statement(stmt.body)

        # Loop back using JMP (handles any distance)
        self._emit_instruction("JMP", start_label)
        self._emit_label(end_label)

        self._loop_stack.pop()

    def _generate_for(self, stmt: ForStatement) -> None:
        """Generate code for for statement."""
        start_label = self._new_label("for")
        continue_label = self._new_label("forc")
        end_label = self._new_label("fend")

        self._loop_stack.append((continue_label, end_label))

        # Initializer
        if stmt.initializer:
            self._emit_comment("for init")
            if isinstance(stmt.initializer, Expression):
                self._generate_expression(stmt.initializer)

        self._emit_label(start_label)

        # Condition
        if stmt.condition:
            self._emit_comment("for condition")
            self._generate_expression(stmt.condition)
            # Use helper for 8-bit optimization when condition is char
            self._emit_boolean_test()
            self._emit_instruction("BEQ", end_label)

        # Body
        self._generate_statement(stmt.body)

        # Continue point
        self._emit_label(continue_label)

        # Update
        if stmt.update:
            self._emit_comment("for update")
            self._generate_expression(stmt.update)

        # Loop back
        self._emit_instruction("BRA", start_label)
        self._emit_label(end_label)

        self._loop_stack.pop()

    def _generate_do_while(self, stmt: DoWhileStatement) -> None:
        """Generate code for do-while statement."""
        start_label = self._new_label("do")
        end_label = self._new_label("dend")

        self._loop_stack.append((start_label, end_label))

        self._emit_label(start_label)

        # Body first
        self._generate_statement(stmt.body)

        # Then condition
        self._emit_comment("do-while condition")
        self._generate_expression(stmt.condition)

        # Loop if true
        # Use helper for 8-bit optimization when condition is char
        self._emit_boolean_test()
        self._emit_instruction("BNE", start_label)

        self._emit_label(end_label)

        self._loop_stack.pop()

    def _generate_switch(self, stmt: SwitchStatement) -> None:
        """Generate code for switch statement."""
        end_label = self._new_label("swend")
        self._switch_stack.append(end_label)

        # Evaluate switch expression
        self._emit_comment("switch expression")
        self._generate_expression(stmt.expression)
        self._emit_instruction("PSHB", "")
        self._emit_instruction("PSHA", "")  # Save switch value

        # Generate case comparisons
        case_labels = []
        default_label = None

        for i, case in enumerate(stmt.cases):
            label = self._new_label(f"case{i}")
            case_labels.append(label)
            if case.is_default:
                default_label = label
            else:
                # Compare with case value
                # Note: D is reloaded from stack for each case, so SUBD's
                # modification doesn't matter - flags are set identically
                self._emit_load_sp()
                self._emit_instruction("LDD", "0,X")  # Get switch value
                if isinstance(case.value, NumberLiteral):
                    self._emit_instruction("SUBD", f"#{case.value.value}")
                else:
                    # Generate case value expression (result in D)
                    self._generate_expression(case.value)
                    # Compare D (case value) with stack (switch value)
                    self._emit_load_sp()
                    self._emit_instruction("SUBD", "0,X")
                self._emit_instruction("BEQ", label)

        # Jump to default or end
        if default_label:
            self._emit_instruction("BRA", default_label)
        else:
            self._emit_instruction("BRA", end_label)

        # Generate case bodies
        for i, case in enumerate(stmt.cases):
            self._emit_label(case_labels[i])
            for case_stmt in case.statements:
                self._generate_statement(case_stmt)

        self._emit_label(end_label)

        # Clean up switch value from stack
        self._emit_instruction("INS", "")
        self._emit_instruction("INS", "")

        self._switch_stack.pop()

    def _generate_return(self, stmt: ReturnStatement) -> None:
        """Generate code for return statement."""
        if stmt.value:
            self._emit_comment("return value")
            self._generate_expression(stmt.value)

        # Jump to function epilogue
        self._emit_instruction("BRA", f"_{self._current_function.name}_exit")

    def _generate_break(self) -> None:
        """Generate code for break statement."""
        if self._switch_stack:
            # Break out of switch
            self._emit_instruction("BRA", self._switch_stack[-1])
        elif self._loop_stack:
            # Break out of loop
            _, break_label = self._loop_stack[-1]
            self._emit_instruction("BRA", break_label)

    def _generate_continue(self) -> None:
        """Generate code for continue statement."""
        if self._loop_stack:
            continue_label, _ = self._loop_stack[-1]
            self._emit_instruction("BRA", continue_label)

    def _generate_goto(self, stmt: GotoStatement) -> None:
        """Generate code for goto statement."""
        self._emit_instruction("BRA", f"_lbl_{stmt.label}")

    def _generate_label(self, stmt: LabelStatement) -> None:
        """Generate code for labeled statement."""
        self._emit_label(f"_lbl_{stmt.name}")
        self._generate_statement(stmt.statement)

    # =========================================================================
    # Expression Code Generation
    # =========================================================================

    def _generate_expression(self, expr: Expression) -> None:
        """
        Generate code for an expression.

        The result is left in the D register (or A for 8-bit).
        """
        if expr is None:
            return

        # Constant folding optimization: try to evaluate at compile time
        # Only attempt for compound expressions (binary, unary with const operand)
        # to avoid redundant work on simple literals
        if isinstance(expr, (BinaryExpression, UnaryExpression, CastExpression)):
            const_value = self._try_eval_constant(expr)
            if const_value is not None:
                # Emit the pre-computed constant
                self._emit_instruction("LDD", f"#{const_value}")
                self._last_expr_size = 2
                return

        if isinstance(expr, NumberLiteral):
            self._generate_number(expr)
        elif isinstance(expr, CharLiteral):
            self._generate_char(expr)
        elif isinstance(expr, StringLiteral):
            self._generate_string(expr)
        elif isinstance(expr, IdentifierExpression):
            self._generate_identifier(expr)
        elif isinstance(expr, BinaryExpression):
            self._generate_binary(expr)
        elif isinstance(expr, UnaryExpression):
            self._generate_unary(expr)
        elif isinstance(expr, AssignmentExpression):
            self._generate_assignment(expr)
        elif isinstance(expr, CallExpression):
            self._generate_call(expr)
        elif isinstance(expr, ArraySubscript):
            self._generate_subscript(expr)
        elif isinstance(expr, TernaryExpression):
            self._generate_ternary(expr)
        elif isinstance(expr, CastExpression):
            self._generate_cast(expr)
        elif isinstance(expr, SizeofExpression):
            self._generate_sizeof(expr)
        elif isinstance(expr, MemberAccessExpression):
            self._generate_member_access(expr)

    def _generate_number(self, expr: NumberLiteral) -> None:
        """Generate code for number literal."""
        value = expr.value & 0xFFFF
        self._emit_instruction("LDD", f"#{value}")
        self._last_expr_size = 2  # Number literals are int (16-bit)

    def _generate_char(self, expr: CharLiteral) -> None:
        """Generate code for character literal."""
        value = expr.value & 0xFF
        self._emit_instruction("LDAB", f"#{value}")
        self._emit_instruction("CLRA", "")
        self._last_expr_size = 1  # Char: A=0, value in B

    def _generate_string(self, expr: StringLiteral) -> None:
        """Generate code for string literal (returns pointer).

        Uses '__S' prefix for string literal labels to avoid collision with
        user-defined variables (which get a single underscore prefix like '_varname').
        """
        label = self._new_label("_S")  # Double underscore prefix: __S1, __S2, etc.
        self._strings.append((label, expr.value))
        self._emit_instruction("LDD", f"#{label}")
        self._last_expr_size = 2  # String pointers are 16-bit

    def _generate_identifier(self, expr: IdentifierExpression) -> None:
        """Generate code for variable reference.

        For arrays, this loads the ADDRESS of the array (arrays decay to pointers).
        For scalars, this loads the VALUE of the variable.
        """
        info = self._lookup(expr.name)
        if info is None:
            raise CCodeGenError(f"undefined variable '{expr.name}'", expr.location)

        # Arrays decay to pointers - load their address, not contents
        if info.sym_type.is_array:
            if info.is_global:
                # Global array: load address using immediate mode
                self._emit_instruction("LDD", f"#_{expr.name}")
            else:
                # Local array: compute address from frame pointer
                # Address = X + offset
                offset = info.offset
                self._emit_instruction("XGDX", "")  # D = X (frame pointer)
                self._emit_instruction("ADDD", f"#{offset}")  # D = X + offset
            self._last_expr_size = 2  # Addresses are always 16-bit
        elif info.is_global:
            # Global scalar variable: direct addressing (load value)
            if info.sym_type.size == 1:
                self._emit_instruction("LDAB", f"_{expr.name}")
                self._emit_instruction("CLRA", "")
                self._last_expr_size = 1  # Char: A=0, value in B
            else:
                self._emit_instruction("LDD", f"_{expr.name}")
                self._last_expr_size = 2  # Int: full D register
        else:
            # Local scalar variable: indexed from X (load value)
            offset = info.offset
            if info.sym_type.size == 1:
                self._emit_instruction("LDAB", f"{offset},X")
                self._emit_instruction("CLRA", "")
                self._last_expr_size = 1  # Char: A=0, value in B
            else:
                self._emit_instruction("LDD", f"{offset},X")
                self._last_expr_size = 2  # Int: full D register

    def _generate_binary(self, expr: BinaryExpression) -> None:
        """
        Generate code for binary expression.

        This method handles type checking and routes to either 8-bit (char)
        or 16-bit (int) code generation paths based on operand types.

        Type Rules:
        -----------
        - char OP char: Uses 8-bit instructions for +, -, &, |, ^
        - int OP int: Uses 16-bit instructions
        - char +/- int: Uses 8-bit instructions, result is char (with overflow)
        - char OP int (other ops): Raises CTypeError

        For operations without 8-bit equivalents (*, /, %, <<, >>), char operands
        are promoted to 16-bit, and mixing with int is still an error.
        """
        op = expr.operator

        # =====================================================================
        # Phase 1: Type Checking
        # =====================================================================
        # Determine operand types and check for mixed type errors.
        # This is done BEFORE generating any code to fail fast on errors.

        # Get the result type - this will raise CTypeError for mixed types
        # Note: _get_binary_expression_type validates and returns the result type
        result_type = self._get_binary_expression_type(expr)

        # Determine if both operands are char (for 8-bit path)
        left_type = self._get_expression_type(expr.left)
        right_type = self._get_expression_type(expr.right)
        both_char = (self._is_char_type(left_type) and
                     self._is_char_type(right_type))

        # =====================================================================
        # Phase 2: Special Cases (handled before general code gen)
        # =====================================================================

        # Comparisons with immediate constant - optimization to avoid stack push
        if op in self._COMPARISON_OPS:
            if isinstance(expr.right, (NumberLiteral, CharLiteral)):
                # Generate left operand (result in D or B depending on type)
                self._generate_expression(expr.left)
                # If left is char, we need to ensure proper comparison
                # CharLiteral.value is already int, works for both
                if both_char:
                    # 8-bit comparison with immediate
                    self._generate_comparison_immediate_char(op, expr.right.value)
                else:
                    # 16-bit comparison with immediate
                    self._generate_comparison_immediate(op, expr.right.value)
                self._last_expr_size = 2  # Comparisons always produce 16-bit boolean
                return

        # Logical operators - short-circuit evaluation, always 16-bit result
        if op == BinaryOperator.LOGICAL_AND:
            self._generate_expression(expr.left)
            self._generate_logical_and(expr)
            self._last_expr_size = 2
            return
        elif op == BinaryOperator.LOGICAL_OR:
            self._generate_expression(expr.left)
            self._generate_logical_or(expr)
            self._last_expr_size = 2
            return

        # Power-of-2 multiply/divide optimization (16-bit shifts)
        if op in (BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE):
            const_val = self._try_eval_constant(expr.right)
            if const_val is not None and const_val > 0 and self._is_power_of_2(const_val):
                shift_count = self._log2(const_val)
                if shift_count <= 8:
                    # Generate left operand
                    self._generate_expression(expr.left)
                    # If char, promote to 16-bit first (CLRA already done by char load)
                    # Emit shifts
                    if op == BinaryOperator.MULTIPLY:
                        for _ in range(shift_count):
                            self._emit_instruction("ASLD", "")
                    else:  # DIVIDE
                        for _ in range(shift_count):
                            self._emit_instruction("LSRD", "")
                    self._last_expr_size = 2
                    return

        # =====================================================================
        # Phase 3: Route to 8-bit or 16-bit code generation
        # =====================================================================

        # Determine if we have mixed char/int for + or -
        left_is_char = self._is_char_type(left_type)
        right_is_char = self._is_char_type(right_type)
        left_is_int = self._is_int_type(left_type)
        right_is_int = self._is_int_type(right_type)
        is_mixed_add_sub = (op in (BinaryOperator.ADD, BinaryOperator.SUBTRACT) and
                           ((left_is_char and right_is_int) or
                            (left_is_int and right_is_char)))

        if both_char and op in self._CHAR_SUPPORTED_OPS:
            # 8-bit path: both operands are char and operation supports 8-bit
            self._generate_binary_char(expr, op)
        elif is_mixed_add_sub:
            # Mixed char/int for + or -: use 8-bit with overflow
            self._generate_binary_char_int(expr, op, left_is_char)
        else:
            # 16-bit path: either int operands or operation requires 16-bit
            self._generate_binary_int(expr, op)

    def _generate_binary_char(self, expr: BinaryExpression, op: BinaryOperator) -> None:
        """
        Generate 8-bit code for binary expression with char operands.

        This method generates efficient 8-bit HD6303 instructions when both
        operands are char type. The result stays in the B register.

        Supported operations:
        - ADD: ADDB (add B register)
        - SUBTRACT: SUBB (subtract from B register)
        - BITWISE_AND: ANDB (AND with B register)
        - BITWISE_OR: ORAB (OR with B register)
        - BITWISE_XOR: EORB (exclusive OR with B register)

        Stack usage: Pushes 1 byte (vs 2 bytes for 16-bit path)

        Register state after:
        - B: Contains the 8-bit result
        - A: Cleared to 0 (CLRA)
        - _last_expr_size: Set to 1

        Args:
            expr: The binary expression (both operands must be char)
            op: The operator (must be in _CHAR_SUPPORTED_OPS)
        """
        # Generate right operand first (result in B, A=0)
        self._generate_expression(expr.right)
        # Push only B (1 byte) - more efficient than 16-bit push
        self._emit_instruction("PSHB", "")
        self._arg_push_depth += 1  # Track this push for left operand generation

        # Generate left operand (result in B, A=0)
        self._generate_expression(expr.left)

        # Get stack pointer to access pushed byte
        self._emit_load_sp()

        # Perform 8-bit operation
        # Stack layout after PSHB: [right_byte] <- SP
        # After TSX: X = SP, so 0,X points to right operand
        if op == BinaryOperator.ADD:
            self._emit_instruction("ADDB", "0,X")
        elif op == BinaryOperator.SUBTRACT:
            self._emit_instruction("SUBB", "0,X")
        elif op == BinaryOperator.BITWISE_AND:
            self._emit_instruction("ANDB", "0,X")
        elif op == BinaryOperator.BITWISE_OR:
            self._emit_instruction("ORAB", "0,X")
        elif op == BinaryOperator.BITWISE_XOR:
            self._emit_instruction("EORB", "0,X")

        # Pop 1 byte from stack
        self._emit_instruction("INS", "")
        self._arg_push_depth -= 1  # Restore push depth

        # Ensure A is clear for consistent D register state
        # (char expressions should have A=0 so D can be used if needed)
        self._emit_instruction("CLRA", "")

        # Mark result as 8-bit for boolean test optimization
        self._last_expr_size = 1

    def _generate_binary_char_int(
        self,
        expr: BinaryExpression,
        op: BinaryOperator,
        left_is_char: bool
    ) -> None:
        """
        Generate 8-bit code for mixed char/int addition or subtraction.

        This method handles expressions like:
        - char + int  (e.g., c = c + 1)
        - int + char  (e.g., c = 1 + c)
        - char - int  (e.g., c = c - 32)
        - int - char  (less common but supported)

        The result is always 8-bit (char) with natural overflow behavior.
        Only the low byte of the int operand is used.

        Strategy:
        - Generate the int operand first (result in D, low byte in B)
        - Push only B (the low byte) to stack
        - Generate the char operand (result in B)
        - Perform 8-bit operation
        - Result in B, A cleared

        Note: For int - char, we need to handle the operand order correctly:
        - If left_is_char: char - int -> B(char) - stack(int_low)
        - If not left_is_char: int - char -> B(int_low) - stack(char)
          But we want the result to be char, so we need to swap operand order

        Args:
            expr: The binary expression (one char, one int operand)
            op: The operator (ADD or SUBTRACT)
            left_is_char: True if left operand is char, False if right is char
        """
        if left_is_char:
            # Pattern: char OP int
            # Generate int operand first (result in D, we use only B)
            self._generate_expression(expr.right)
            # Push low byte of int
            self._emit_instruction("PSHB", "")
            self._arg_push_depth += 1  # Track this push

            # Generate char operand (result in B)
            self._generate_expression(expr.left)

            # Perform 8-bit operation: B = B OP stack
            self._emit_load_sp()
            if op == BinaryOperator.ADD:
                self._emit_instruction("ADDB", "0,X")
            elif op == BinaryOperator.SUBTRACT:
                self._emit_instruction("SUBB", "0,X")
        else:
            # Pattern: int OP char
            # Generate char operand first (result in B)
            self._generate_expression(expr.right)
            # Push char byte
            self._emit_instruction("PSHB", "")
            self._arg_push_depth += 1  # Track this push

            # Generate int operand (result in D, we use only B)
            self._generate_expression(expr.left)
            # B now has low byte of int

            # Perform 8-bit operation: B = B OP stack
            self._emit_load_sp()
            if op == BinaryOperator.ADD:
                self._emit_instruction("ADDB", "0,X")
            elif op == BinaryOperator.SUBTRACT:
                self._emit_instruction("SUBB", "0,X")

        # Pop 1 byte from stack
        self._emit_instruction("INS", "")
        self._arg_push_depth -= 1  # Restore push depth

        # Clear A for consistent D register state
        self._emit_instruction("CLRA", "")

        # Result is 8-bit char
        self._last_expr_size = 1

    def _generate_binary_int(self, expr: BinaryExpression, op: BinaryOperator) -> None:
        """
        Generate 16-bit code for binary expression.

        This is the standard path for int operands or operations that require
        16-bit (*, /, %, <<, >>). Also used when char operands need promotion.

        Stack usage: Pushes 2 bytes (A and B)

        Register state after:
        - D (A:B): Contains the 16-bit result
        - _last_expr_size: Set to 2

        Args:
            expr: The binary expression
            op: The operator
        """
        # Generate right operand (result in D)
        self._generate_expression(expr.right)
        # Push 2 bytes to stack
        self._emit_instruction("PSHB", "")
        self._emit_instruction("PSHA", "")
        self._arg_push_depth += 2  # Track this push for left operand generation

        # Generate left operand (result in D)
        self._generate_expression(expr.left)

        # Perform 16-bit operation
        # Stack layout after PSHA/PSHB: [A][B] <- SP (high byte first)
        # After TSX: X = SP, so 0,X = A (high), 1,X = B (low)
        if op == BinaryOperator.ADD:
            self._emit_load_sp()
            self._emit_instruction("ADDD", "0,X")
        elif op == BinaryOperator.SUBTRACT:
            self._emit_load_sp()
            self._emit_instruction("SUBD", "0,X")
        elif op == BinaryOperator.MULTIPLY:
            self._emit_load_sp()
            self._emit_instruction("LDX", "0,X")
            self._emit_instruction("JSR", "__mul16")
        elif op == BinaryOperator.DIVIDE:
            self._emit_load_sp()
            self._emit_instruction("LDX", "0,X")
            self._emit_instruction("JSR", "__div16")
        elif op == BinaryOperator.MODULO:
            self._emit_load_sp()
            self._emit_instruction("LDX", "0,X")
            self._emit_instruction("JSR", "__mod16")
        elif op == BinaryOperator.BITWISE_AND:
            self._emit_load_sp()
            self._emit_instruction("ANDA", "0,X")   # High byte
            self._emit_instruction("ANDB", "1,X")   # Low byte
        elif op == BinaryOperator.BITWISE_OR:
            self._emit_load_sp()
            self._emit_instruction("ORAA", "0,X")
            self._emit_instruction("ORAB", "1,X")
        elif op == BinaryOperator.BITWISE_XOR:
            self._emit_load_sp()
            self._emit_instruction("EORA", "0,X")
            self._emit_instruction("EORB", "1,X")
        elif op == BinaryOperator.LEFT_SHIFT:
            self._emit_load_sp()
            self._emit_instruction("LDAB", "1,X")   # Shift count in low byte
            self._emit_instruction("JSR", "__shl16")
        elif op == BinaryOperator.RIGHT_SHIFT:
            self._emit_load_sp()
            self._emit_instruction("LDAB", "1,X")
            self._emit_instruction("JSR", "__shr16")
        elif op in self._COMPARISON_OPS:
            self._generate_comparison(op)

        # Pop 2 bytes from stack
        self._emit_instruction("INS", "")
        self._emit_instruction("INS", "")
        self._arg_push_depth -= 2  # Restore push depth

        # Mark result as 16-bit
        self._last_expr_size = 2

    def _generate_comparison_immediate_char(self, op: BinaryOperator, value: int) -> None:
        """
        Generate 8-bit comparison with immediate value.

        This optimized path is used when comparing a char expression against
        a char literal. Uses CMPB instead of SUBD for efficiency.

        Args:
            op: The comparison operator
            value: The immediate value to compare against
        """
        true_label = self._new_label("true")
        end_label = self._new_label("cmpend")

        # B already has left operand (char), compare with immediate
        # CMPB sets flags like SUBB but doesn't modify B
        self._emit_instruction("CMPB", f"#{value & 0xFF}")

        # Branch on condition
        branch_map = {
            BinaryOperator.EQUAL: "BEQ",
            BinaryOperator.NOT_EQUAL: "BNE",
            BinaryOperator.LESS: "BLT",
            BinaryOperator.GREATER: "BGT",
            BinaryOperator.LESS_EQ: "BLE",
            BinaryOperator.GREATER_EQ: "BGE",
        }

        self._emit_instruction(branch_map[op], true_label)
        self._emit_instruction("LDD", "#0")   # False (16-bit result)
        self._emit_instruction("BRA", end_label)
        self._emit_label(true_label)
        self._emit_instruction("LDD", "#1")   # True (16-bit result)
        self._emit_label(end_label)

    def _generate_comparison(self, op: BinaryOperator) -> None:
        """Generate code for comparison operators."""
        true_label = self._new_label("true")
        end_label = self._new_label("cmpend")

        # Compare D with stack top
        # Note: SUBD sets identical flags as CPD, and D is immediately
        # overwritten with boolean result (0 or 1), so modification is fine
        self._emit_load_sp()
        self._emit_instruction("SUBD", "0,X")

        # Branch on condition
        branch_map = {
            BinaryOperator.EQUAL: "BEQ",
            BinaryOperator.NOT_EQUAL: "BNE",
            BinaryOperator.LESS: "BLT",
            BinaryOperator.GREATER: "BGT",
            BinaryOperator.LESS_EQ: "BLE",
            BinaryOperator.GREATER_EQ: "BGE",
        }

        self._emit_instruction(branch_map[op], true_label)
        self._emit_instruction("LDD", "#0")  # False
        self._emit_instruction("BRA", end_label)
        self._emit_label(true_label)
        self._emit_instruction("LDD", "#1")  # True
        self._emit_label(end_label)

    def _generate_comparison_immediate(self, op: BinaryOperator, value: int) -> None:
        """Generate comparison with immediate value - doesn't touch X."""
        true_label = self._new_label("true")
        end_label = self._new_label("cmpend")

        # D already has left operand, compare with immediate
        self._emit_instruction("SUBD", f"#{value & 0xFFFF}")

        branch_map = {
            BinaryOperator.EQUAL: "BEQ",
            BinaryOperator.NOT_EQUAL: "BNE",
            BinaryOperator.LESS: "BLT",
            BinaryOperator.GREATER: "BGT",
            BinaryOperator.LESS_EQ: "BLE",
            BinaryOperator.GREATER_EQ: "BGE",
        }

        self._emit_instruction(branch_map[op], true_label)
        self._emit_instruction("LDD", "#0")  # False
        self._emit_instruction("BRA", end_label)
        self._emit_label(true_label)
        self._emit_instruction("LDD", "#1")  # True
        self._emit_label(end_label)

    def _generate_logical_and(self, expr: BinaryExpression) -> None:
        """Generate code for && with short-circuit evaluation."""
        false_label = self._new_label("land_f")
        end_label = self._new_label("land_e")

        # Left operand already evaluated
        # Check if false (short-circuit) - use helper for 8-bit optimization
        self._emit_boolean_test()
        self._emit_instruction("BEQ", false_label)

        # Evaluate right operand
        self._generate_expression(expr.right)
        # Use helper for 8-bit optimization when right operand is char
        self._emit_boolean_test()
        self._emit_instruction("BEQ", false_label)

        # Both true
        self._emit_instruction("LDD", "#1")
        self._emit_instruction("BRA", end_label)

        self._emit_label(false_label)
        self._emit_instruction("LDD", "#0")

        self._emit_label(end_label)

    def _generate_logical_or(self, expr: BinaryExpression) -> None:
        """Generate code for || with short-circuit evaluation."""
        true_label = self._new_label("lor_t")
        end_label = self._new_label("lor_e")

        # Left operand already evaluated
        # Check if true (short-circuit) - use helper for 8-bit optimization
        self._emit_boolean_test()
        self._emit_instruction("BNE", true_label)

        # Evaluate right operand
        self._generate_expression(expr.right)
        # Use helper for 8-bit optimization when right operand is char
        self._emit_boolean_test()
        self._emit_instruction("BNE", true_label)

        # Both false
        self._emit_instruction("LDD", "#0")
        self._emit_instruction("BRA", end_label)

        self._emit_label(true_label)
        self._emit_instruction("LDD", "#1")

        self._emit_label(end_label)

    def _generate_unary(self, expr: UnaryExpression) -> None:
        """Generate code for unary expression."""
        op = expr.operator

        if op == UnaryOperator.NEGATE:
            self._generate_expression(expr.operand)
            self._emit_instruction("COMA", "")
            self._emit_instruction("COMB", "")
            self._emit_instruction("ADDD", "#1")  # Two's complement
            self._last_expr_size = 2  # Negate produces 16-bit result

        elif op == UnaryOperator.POSITIVE:
            # No-op - just evaluates operand, preserving its size
            self._generate_expression(expr.operand)
            # Size is already set by the operand

        elif op == UnaryOperator.LOGICAL_NOT:
            self._generate_expression(expr.operand)
            end_label = self._new_label("not")
            # Use helper for 8-bit optimization when operand is char
            self._emit_boolean_test()
            self._emit_instruction("BEQ", f"{end_label}_t")
            self._emit_instruction("LDD", "#0")
            self._emit_instruction("BRA", f"{end_label}")
            self._emit_label(f"{end_label}_t")
            self._emit_instruction("LDD", "#1")
            self._emit_label(end_label)
            self._last_expr_size = 2  # Logical NOT produces 16-bit boolean

        elif op == UnaryOperator.BITWISE_NOT:
            self._generate_expression(expr.operand)
            self._emit_instruction("COMA", "")
            self._emit_instruction("COMB", "")
            self._last_expr_size = 2  # Bitwise NOT produces 16-bit result

        elif op == UnaryOperator.ADDRESS_OF:
            # Get address of variable
            if isinstance(expr.operand, IdentifierExpression):
                info = self._lookup(expr.operand.name)
                if info.is_global:
                    self._emit_instruction("LDD", f"#_{expr.operand.name}")
                else:
                    # Calculate address from frame pointer
                    # TSX gives current SP, which may differ from original frame if
                    # we're in the middle of pushing function arguments.
                    # Compensate by adding _arg_push_depth to the offset.
                    adjusted_offset = info.offset + self._arg_push_depth
                    self._emit_instruction("TSX", "")
                    self._emit_instruction("XGDX", "")
                    self._emit_instruction("ADDD", f"#{adjusted_offset}")
            self._last_expr_size = 2  # Addresses are always 16-bit

        elif op == UnaryOperator.DEREFERENCE:
            self._generate_expression(expr.operand)
            # D contains pointer, load value
            self._emit_instruction("XGDX", "")  # D <-> X
            self._emit_instruction("LDD", "0,X")
            self._last_expr_size = 2  # Dereference loads 16-bit value

        elif op in (UnaryOperator.PRE_INCREMENT, UnaryOperator.PRE_DECREMENT):
            self._generate_increment(expr.operand, op == UnaryOperator.PRE_INCREMENT, True)
            self._last_expr_size = 2  # Increment/decrement produces 16-bit

        elif op in (UnaryOperator.POST_INCREMENT, UnaryOperator.POST_DECREMENT):
            self._generate_increment(expr.operand, op == UnaryOperator.POST_INCREMENT, False)
            self._last_expr_size = 2  # Increment/decrement produces 16-bit

    def _generate_increment(self, operand: Expression, is_increment: bool, is_pre: bool) -> None:
        """Generate code for ++/-- operators."""
        if not isinstance(operand, IdentifierExpression):
            raise CCodeGenError("increment/decrement requires lvalue", operand.location)

        info = self._lookup(operand.name)
        if info is None:
            raise CCodeGenError(f"undefined variable '{operand.name}'", operand.location)

        # Load current value
        if info.is_global:
            self._emit_instruction("LDD", f"_{operand.name}")
        else:
            self._emit_instruction("LDD", f"{info.offset},X")

        if not is_pre:
            # Post: save original value
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")

        # Increment or decrement
        if is_increment:
            self._emit_instruction("ADDD", "#1")
        else:
            self._emit_instruction("SUBD", "#1")

        # Store new value
        if info.is_global:
            self._emit_instruction("STD", f"_{operand.name}")
        else:
            self._emit_instruction("STD", f"{info.offset},X")

        if not is_pre:
            # Post: restore original value as result
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")

    def _generate_assignment(self, expr: AssignmentExpression) -> None:
        """Generate code for assignment expression."""
        # Generate the value
        self._generate_expression(expr.value)

        # For compound assignments, need to combine with current value
        if expr.operator != AssignmentOperator.ASSIGN:
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")
            self._generate_expression(expr.target)

            # Apply operator
            op_map = {
                AssignmentOperator.ADD_ASSIGN: BinaryOperator.ADD,
                AssignmentOperator.SUB_ASSIGN: BinaryOperator.SUBTRACT,
                AssignmentOperator.MUL_ASSIGN: BinaryOperator.MULTIPLY,
                AssignmentOperator.DIV_ASSIGN: BinaryOperator.DIVIDE,
                AssignmentOperator.MOD_ASSIGN: BinaryOperator.MODULO,
                AssignmentOperator.AND_ASSIGN: BinaryOperator.BITWISE_AND,
                AssignmentOperator.OR_ASSIGN: BinaryOperator.BITWISE_OR,
                AssignmentOperator.XOR_ASSIGN: BinaryOperator.BITWISE_XOR,
                AssignmentOperator.LSHIFT_ASSIGN: BinaryOperator.LEFT_SHIFT,
                AssignmentOperator.RSHIFT_ASSIGN: BinaryOperator.RIGHT_SHIFT,
            }

            # Create temporary binary expression for the operation
            self._emit_load_sp()
            bin_op = op_map[expr.operator]

            if bin_op == BinaryOperator.ADD:
                self._emit_instruction("ADDD", "0,X")
            elif bin_op == BinaryOperator.SUBTRACT:
                self._emit_instruction("SUBD", "0,X")
            # ... other operators handled similarly

            self._emit_instruction("INS", "")
            self._emit_instruction("INS", "")

        # Store the result
        self._generate_store(expr.target)

        # Assignment leaves the assigned value in D
        # Size depends on target type
        if isinstance(expr.target, IdentifierExpression):
            info = self._lookup(expr.target.name)
            if info and info.sym_type.size == 1:
                self._last_expr_size = 1  # Char assignment
            else:
                self._last_expr_size = 2  # Int/ptr assignment
        else:
            self._last_expr_size = 2  # Array/pointer deref - assume 16-bit

    def _generate_store(self, target: Expression) -> None:
        """Generate code to store D register to target."""
        if isinstance(target, IdentifierExpression):
            info = self._lookup(target.name)
            if info is None:
                raise CCodeGenError(f"undefined variable '{target.name}'", target.location)

            if info.is_global:
                if info.sym_type.size == 1:
                    self._emit_instruction("STAB", f"_{target.name}")
                else:
                    self._emit_instruction("STD", f"_{target.name}")
            else:
                # Refresh frame pointer - X may have been corrupted by expression evaluation
                self._emit_instruction("TSX", "")
                if info.sym_type.size == 1:
                    self._emit_instruction("STAB", f"{info.offset},X")
                else:
                    self._emit_instruction("STD", f"{info.offset},X")

        elif isinstance(target, ArraySubscript):
            # Store to array element
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")  # Save value
            self._arg_push_depth += 2  # Track this temporary push

            # Calculate address
            self._generate_subscript_address(target)

            # Store value: char=1 byte (STAB), int/ptr=2 bytes (STD)
            element_size = self._get_array_element_size(target)
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")
            self._arg_push_depth -= 2  # Restore push depth
            if element_size == 1:
                self._emit_instruction("STAB", "0,X")  # Store single byte
            else:
                self._emit_instruction("STD", "0,X")   # Store 16-bit value

        elif isinstance(target, UnaryExpression) and target.operator == UnaryOperator.DEREFERENCE:
            # Store through pointer
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")  # Save value
            self._arg_push_depth += 2  # Track this temporary push
            self._generate_expression(target.operand)
            self._emit_instruction("XGDX", "")  # Pointer to X
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")
            self._arg_push_depth -= 2  # Restore push depth
            self._emit_instruction("STD", "0,X")

        elif isinstance(target, MemberAccessExpression):
            # Store to struct member: p.x = value or p->x = value
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")  # Save value to stack
            self._arg_push_depth += 2  # Track this temporary push

            # Compute address of member
            self._generate_member_access_address(target)
            self._emit_instruction("XGDX", "")  # Address to X

            # Get field type to determine store size
            object_type = self._get_expression_type(target.object_expr)
            struct_name = object_type.struct_name
            field_info = self._get_struct_field_info(struct_name, target.member_name)

            # Restore value and store
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")
            self._arg_push_depth -= 2  # Restore push depth

            if field_info.field_type.size == 1:
                self._emit_instruction("STAB", "0,X")  # Store char (1 byte)
            else:
                self._emit_instruction("STD", "0,X")   # Store int/ptr (2 bytes)

    def _generate_call(self, expr: CallExpression) -> None:
        """
        Generate code for function call.

        For regular C functions:
        - Push arguments right-to-left
        - JSR to the function
        - Clean up stack after return

        For external OPL procedures:
        - Push arguments right-to-left (for procedures with parameters)
        - Push name pointer
        - Push parameter count
        - Call _call_opl_param which handles QCode injection with parameters
        - D register contains return value (if any)
        """
        # =====================================================================
        # Check for external OPL procedure call
        # =====================================================================
        # External procedures are called via QCode injection. The runtime
        # function builds a synthetic QCode buffer containing:
        #   1. Parameter pushes (if any): $22 HH LL for each int param
        #   2. Parameter count: $20 NN
        #   3. Procedure call: $7D len name
        #   4. Return sequence: $22 restore_addr $22 saved_SP $9F
        # It then unwinds the stack and exits to the OPL interpreter, which
        # executes the buffer, calls the OPL procedure, then calls USR() to
        # resume C execution.
        if expr.function_name in self._external_funcs:
            ext_func = self._external_funcs[expr.function_name]

            # Validate argument count matches declared parameter count
            if len(expr.arguments) != ext_func.param_count:
                raise CCodeGenError(
                    f"external procedure '{expr.function_name}' expects "
                    f"{ext_func.param_count} argument(s), got {len(expr.arguments)}",
                    expr.location,
                )

            # Create a string literal for the procedure name
            # The C return type determines the OPL name suffix:
            #   external char GETVAL()  -> calls GETVAL$ in OPL (string)
            #   external int GETVAL()   -> calls GETVAL% in OPL (integer)
            #   external void GETVAL()  -> calls GETVAL in OPL (no suffix)
            proc_name_label = self._new_label("_PROC")
            return_type = ext_func.return_type
            opl_name = expr.function_name
            if return_type and return_type.base_type == BaseType.CHAR:
                opl_name = expr.function_name + "$"
            elif return_type and return_type.base_type == BaseType.INT:
                opl_name = expr.function_name + "%"
            # void has no suffix
            self._strings.append((proc_name_label, opl_name))

            # ─────────────────────────────────────────────────────────────────
            # Handle external procedure with parameters
            # ─────────────────────────────────────────────────────────────────
            # Stack layout for _call_opl_param (rightmost argument at lowest address):
            #   SP -> [param_count][name_ptr][param N]...[param 1][return addr]
            #
            # The runtime function reads:
            #   - param_count from SP+0
            #   - name_ptr from SP+2
            #   - parameters from SP+4 onwards (first param at highest addr)
            if ext_func.param_count > 0:
                self._emit_comment(f"Call external OPL procedure: {opl_name} "
                                   f"({ext_func.param_count} params)")

                # Push arguments right-to-left (last argument first)
                # This places first argument at highest address, matching C convention
                for arg in reversed(expr.arguments):
                    self._generate_expression(arg)
                    self._emit_instruction("PSHB", "")
                    self._emit_instruction("PSHA", "")

                # Push name pointer
                self._emit_instruction("LDD", f"#{proc_name_label}")
                self._emit_instruction("PSHB", "")
                self._emit_instruction("PSHA", "")

                # Push parameter count
                self._emit_instruction("LDD", f"#{ext_func.param_count}")
                self._emit_instruction("PSHB", "")
                self._emit_instruction("PSHA", "")

                # Select runtime function based on return type:
                #   - char: _call_opl_str_param (returns first char of string)
                #   - int/void: _call_opl_param (converts BCD float to int)
                if return_type and return_type.base_type == BaseType.CHAR:
                    self._emit_instruction("JSR", "_call_opl_str_param")
                else:
                    self._emit_instruction("JSR", "_call_opl_param")

                # Cleanup: REQUIRED! Resume calculation expects exactly 2 INS after JSR
                # The restore function jumps past these to reach the next statement.
                # Total stack cleanup: param_count(2) + name_ptr(2) + params(2*N)
                self._emit_instruction("INS", "")
                self._emit_instruction("INS", "")

            # ─────────────────────────────────────────────────────────────────
            # Handle external procedure without parameters (original path)
            # ─────────────────────────────────────────────────────────────────
            # This uses the simpler _call_opl which doesn't need to read params
            else:
                self._emit_comment(f"Call external OPL procedure: {opl_name}")

                # Push name pointer
                self._emit_instruction("LDD", f"#{proc_name_label}")
                self._emit_instruction("PSHB", "")
                self._emit_instruction("PSHA", "")

                # Select runtime function based on return type:
                #   - char: _call_opl_str (returns first char of string)
                #   - int/void: _call_opl (converts BCD float to int)
                if return_type and return_type.base_type == BaseType.CHAR:
                    self._emit_instruction("JSR", "_call_opl_str")
                else:
                    self._emit_instruction("JSR", "_call_opl")

                # Cleanup: REQUIRED! Resume calculation expects exactly 2 INS after JSR
                self._emit_instruction("INS", "")
                self._emit_instruction("INS", "")

            # D register now contains the OPL procedure's return value:
            #   - For char: first character of the returned string
            #   - For int: the integer return value (converted from BCD float)
            #   - For void: garbage (caller should ignore)
            # Execution resumes here after OPL procedure completes
            self._last_expr_size = 2  # External calls return 16-bit values
            return

        # =====================================================================
        # Regular C function call
        # =====================================================================
        # Push arguments right-to-left
        # Track push depth so local address calculations can compensate
        saved_push_depth = self._arg_push_depth
        for arg in reversed(expr.arguments):
            self._generate_expression(arg)
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")
            self._arg_push_depth += 2  # Track stack growth

        # Call function
        self._emit_instruction("JSR", f"_{expr.function_name}")

        # Clean up arguments and reset push depth
        arg_bytes = len(expr.arguments) * 2
        for _ in range(arg_bytes):
            self._emit_instruction("INS", "")
        self._arg_push_depth = saved_push_depth  # Restore to pre-call depth

        # Function calls return 16-bit values in D
        self._last_expr_size = 2

    def _generate_subscript(self, expr: ArraySubscript) -> None:
        """Generate code for array subscript (load value)."""
        self._generate_subscript_address(expr)
        # Load element: char=1 byte (LDAB+CLRA), int/ptr=2 bytes (LDD)
        element_size = self._get_array_element_size(expr)
        if element_size == 1:
            self._emit_instruction("LDAB", "0,X")  # Load single byte
            self._emit_instruction("CLRA", "")     # Zero-extend to 16-bit
            self._last_expr_size = 1  # Char: A=0, value in B
        else:
            self._emit_instruction("LDD", "0,X")   # Load 16-bit value
            self._last_expr_size = 2  # Int/ptr: full D register

    def _generate_subscript_address(self, expr: ArraySubscript) -> None:
        """Generate address of array element into X register."""
        # Get array base address
        if isinstance(expr.array, IdentifierExpression):
            info = self._lookup(expr.array.name)
            if info.is_global:
                self._emit_instruction("LDX", f"#_{expr.array.name}")
            else:
                # Local array: address is frame + offset
                # Compensate for any bytes pushed during argument generation
                adjusted_offset = info.offset + self._arg_push_depth
                self._emit_instruction("TSX", "")
                self._emit_instruction("XGDX", "")
                self._emit_instruction("ADDD", f"#{adjusted_offset}")
                self._emit_instruction("XGDX", "")
        else:
            # Pointer expression
            self._generate_expression(expr.array)
            self._emit_instruction("XGDX", "")

        # Save base address
        self._emit_instruction("PSHX", "")
        self._arg_push_depth += 2  # Track this temporary push

        # Generate index
        self._generate_expression(expr.index)

        # Multiply by element size: char=1 (no multiply), int/ptr=2 (ASLD)
        element_size = self._get_array_element_size(expr)
        if element_size == 2:
            self._emit_instruction("ASLD", "")  # * 2 for int/pointer arrays

        # Add to base
        self._emit_load_sp()
        self._emit_instruction("ADDD", "0,X")
        self._emit_instruction("INS", "")
        self._emit_instruction("INS", "")
        self._arg_push_depth -= 2  # Restore push depth
        self._emit_instruction("XGDX", "")

    def _generate_ternary(self, expr: TernaryExpression) -> None:
        """Generate code for ternary expression."""
        else_label = self._new_label("tern_e")
        end_label = self._new_label("tern_x")

        # Evaluate condition
        self._generate_expression(expr.condition)
        # Use helper for 8-bit optimization when condition is char
        self._emit_boolean_test()
        self._emit_instruction("BEQ", else_label)

        # Then expression
        self._generate_expression(expr.then_expr)
        self._emit_instruction("BRA", end_label)

        # Else expression
        self._emit_label(else_label)
        self._generate_expression(expr.else_expr)

        self._emit_label(end_label)
        # Note: _last_expr_size is set by whichever branch was taken
        # Conservatively assume 16-bit (both branches should produce same type)
        self._last_expr_size = 2

    def _generate_cast(self, expr: CastExpression) -> None:
        """Generate code for type cast."""
        self._generate_expression(expr.expression)

        # Handle char <-> int conversions
        if expr.target_type.base_type == BaseType.CHAR:
            # Truncate to 8 bits (already in B)
            self._emit_instruction("CLRA", "")
            self._last_expr_size = 1  # Cast to char: A=0, value in B
        else:
            self._last_expr_size = 2  # Cast to int/ptr: full D register

    def _generate_sizeof(self, expr: SizeofExpression) -> None:
        """Generate code for sizeof expression."""
        if expr.target_type:
            # Use the type's size property, which handles structs via size_resolver
            if expr.target_type.struct_name and expr.target_type.struct_name in self._structs:
                # Struct type - get size from our struct table
                struct_info = self._structs[expr.target_type.struct_name]
                if expr.target_type.is_array:
                    size = struct_info.size * expr.target_type.array_size
                elif expr.target_type.is_pointer:
                    size = 2  # Pointer to struct
                else:
                    size = struct_info.size
            else:
                size = expr.target_type.size
        else:
            # sizeof(expr) - would need type analysis to determine expression type
            size = 2  # Default to int size

        self._emit_instruction("LDD", f"#{size}")
        self._last_expr_size = 2  # sizeof returns 16-bit int

    def _generate_member_access(self, expr: MemberAccessExpression) -> None:
        """
        Generate code for struct member access (. and ->).

        For p.x (dot operator):
            - Get address of struct variable
            - Add field offset
            - Load value from that address

        For p->x (arrow operator):
            - Get pointer value (already an address)
            - Add field offset
            - Load value from that address

        Result is in D register.
        """
        # Get the struct type from the object expression
        object_type = self._get_expression_type(expr.object_expr)

        # Determine the struct name
        if expr.is_arrow:
            # ptr->field: object_expr is a pointer to struct
            if not object_type.is_pointer or not object_type.struct_name:
                raise CCodeGenError(
                    "'->' requires pointer to struct", expr.location
                )
            struct_name = object_type.struct_name
        else:
            # obj.field: object_expr is a struct value
            if object_type.is_pointer or not object_type.struct_name:
                raise CCodeGenError(
                    "'.' requires struct value, not pointer", expr.location
                )
            struct_name = object_type.struct_name

        # Get field information (offset and type)
        field_info = self._get_struct_field_info(struct_name, expr.member_name)

        if expr.is_arrow:
            # Arrow operator: object_expr evaluates to a pointer
            # Generate: D = ptr, X = D, then access X+offset
            self._generate_expression(expr.object_expr)
            # Transfer D to X for indexed addressing
            self._emit_instruction("XGDX", "")  # Exchange D and X
        else:
            # Dot operator: need address of the struct variable
            self._generate_member_address(expr.object_expr)
            # Address is now in D, transfer to X
            self._emit_instruction("XGDX", "")  # Exchange D and X

        # Now X holds the struct base address
        # Load the field value from X+offset
        offset = field_info.offset
        field_type = field_info.field_type

        if field_type.is_struct and not field_type.is_pointer:
            # Nested struct by value - return address (like array decay)
            if offset == 0:
                self._emit_instruction("XGDX", "")  # D = X (struct address)
            else:
                self._emit_instruction("XGDX", "")  # D = X
                self._emit_instruction("ADDD", f"#{offset}")  # D = base + offset
            self._last_expr_size = 2  # Address is 16-bit
        elif field_type.is_pointer or field_type.base_type == BaseType.INT or field_type.is_array:
            # 16-bit value or pointer
            if offset <= 255:
                self._emit_instruction("LDD", f"{offset},X")
            else:
                # Large offset - need to compute address
                self._emit_instruction("XGDX", "")  # D = base address
                self._emit_instruction("ADDD", f"#{offset}")
                self._emit_instruction("XGDX", "")  # X = computed address
                self._emit_instruction("LDD", "0,X")
            self._last_expr_size = 2
        elif field_type.base_type == BaseType.CHAR and not field_type.is_array:
            # 8-bit char value
            if offset <= 255:
                self._emit_instruction("LDAB", f"{offset},X")
            else:
                # Large offset
                self._emit_instruction("XGDX", "")
                self._emit_instruction("ADDD", f"#{offset}")
                self._emit_instruction("XGDX", "")
                self._emit_instruction("LDAB", "0,X")
            self._emit_instruction("CLRA", "")
            self._last_expr_size = 1
        else:
            # Default: 16-bit
            if offset <= 255:
                self._emit_instruction("LDD", f"{offset},X")
            else:
                self._emit_instruction("XGDX", "")
                self._emit_instruction("ADDD", f"#{offset}")
                self._emit_instruction("XGDX", "")
                self._emit_instruction("LDD", "0,X")
            self._last_expr_size = 2

    def _generate_member_address(self, expr: Expression) -> None:
        """
        Generate code to compute the address of an expression.

        For identifiers (variables), emits code to load the address.
        For other expressions, this would need lvalue analysis.

        Result is in D register.
        """
        if isinstance(expr, IdentifierExpression):
            # Variable: get its address
            info = self._lookup(expr.name)
            if info is None:
                raise CCodeGenError(f"undefined variable '{expr.name}'", expr.location)

            if info.is_global:
                # Global: load address constant
                self._emit_instruction("LDD", f"#_{expr.name}")
            else:
                # Local: compute address from frame pointer
                # Compensate for any bytes pushed during argument generation
                adjusted_offset = info.offset + self._arg_push_depth
                self._emit_instruction("TSX", "")  # X = SP
                if adjusted_offset == 0:
                    self._emit_instruction("XGDX", "")  # D = X
                else:
                    self._emit_instruction("XGDX", "")  # D = X
                    self._emit_instruction("ADDD", f"#{adjusted_offset}")  # D = X + offset
        elif isinstance(expr, MemberAccessExpression):
            # Nested member access: compute address of the nested member
            self._generate_member_access_address(expr)
        elif isinstance(expr, ArraySubscript):
            # Array element: compute address
            self._generate_subscript_address(expr)
        else:
            raise CCodeGenError(
                "cannot take address of expression", expr.location
            )

    def _generate_member_access_address(self, expr: MemberAccessExpression) -> None:
        """
        Generate code to compute the address of a member access.

        This is for lvalues like p.x or p->x when used as assignment targets
        or for nested struct access.

        Result is in D register.
        """
        # Get the struct type
        object_type = self._get_expression_type(expr.object_expr)

        if expr.is_arrow:
            struct_name = object_type.struct_name
        else:
            struct_name = object_type.struct_name

        field_info = self._get_struct_field_info(struct_name, expr.member_name)

        if expr.is_arrow:
            # ptr->field: ptr + offset
            self._generate_expression(expr.object_expr)  # D = ptr
            if field_info.offset > 0:
                self._emit_instruction("ADDD", f"#{field_info.offset}")
        else:
            # obj.field: &obj + offset
            self._generate_member_address(expr.object_expr)  # D = &obj
            if field_info.offset > 0:
                self._emit_instruction("ADDD", f"#{field_info.offset}")
