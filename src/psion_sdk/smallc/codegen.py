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
from dataclasses import dataclass, field

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
)
from psion_sdk.smallc.types import CType, BaseType, TYPE_INT, TYPE_CHAR
from psion_sdk.smallc.errors import CCodeGenError, UnsupportedFeatureError


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
        self._external_funcs: set[str] = set()

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
        self._external_funcs = set()

        # Emit header (includes)
        self._emit_header()

        # First pass: collect global variables and external function declarations
        for decl in program.declarations:
            if isinstance(decl, VariableDeclaration) and decl.is_global:
                self._add_global(decl)
            elif isinstance(decl, FunctionNode) and decl.is_external:
                # Track external OPL procedure declarations
                # These will be called via QCode injection at runtime
                self._external_funcs.add(decl.name)

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

    def _new_label(self, prefix: str = "L") -> str:
        """Generate a unique label."""
        self._label_counter += 1
        return f"_{prefix}{self._label_counter}"

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
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
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
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
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
            # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
            self._emit_instruction("SUBD", "#0")
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
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
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

    def _generate_number(self, expr: NumberLiteral) -> None:
        """Generate code for number literal."""
        value = expr.value & 0xFFFF
        self._emit_instruction("LDD", f"#{value}")

    def _generate_char(self, expr: CharLiteral) -> None:
        """Generate code for character literal."""
        value = expr.value & 0xFF
        self._emit_instruction("LDAB", f"#{value}")
        self._emit_instruction("CLRA", "")

    def _generate_string(self, expr: StringLiteral) -> None:
        """Generate code for string literal (returns pointer).

        Uses '__S' prefix for string literal labels to avoid collision with
        user-defined variables (which get a single underscore prefix like '_varname').
        """
        label = self._new_label("_S")  # Double underscore prefix: __S1, __S2, etc.
        self._strings.append((label, expr.value))
        self._emit_instruction("LDD", f"#{label}")

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
        elif info.is_global:
            # Global scalar variable: direct addressing (load value)
            if info.sym_type.size == 1:
                self._emit_instruction("LDAB", f"_{expr.name}")
                self._emit_instruction("CLRA", "")
            else:
                self._emit_instruction("LDD", f"_{expr.name}")
        else:
            # Local scalar variable: indexed from X (load value)
            offset = info.offset
            if info.sym_type.size == 1:
                self._emit_instruction("LDAB", f"{offset},X")
                self._emit_instruction("CLRA", "")
            else:
                self._emit_instruction("LDD", f"{offset},X")

    def _generate_binary(self, expr: BinaryExpression) -> None:
        """Generate code for binary expression."""
        op = expr.operator

        # Optimization: for comparisons with constants, use immediate mode
        # This avoids pushing to stack which would destroy frame pointer X
        if op in (BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL,
                  BinaryOperator.LESS, BinaryOperator.GREATER,
                  BinaryOperator.LESS_EQ, BinaryOperator.GREATER_EQ):
            if isinstance(expr.right, (NumberLiteral, CharLiteral)):
                # Generate left operand (result in D)
                self._generate_expression(expr.left)
                # Compare directly with immediate value (CharLiteral.value is already int)
                self._generate_comparison_immediate(op, expr.right.value)
                return

        # Logical operators handle their own operands (short-circuit evaluation)
        # Don't push right operand - they evaluate it only when needed
        if op == BinaryOperator.LOGICAL_AND:
            self._generate_expression(expr.left)
            self._generate_logical_and(expr)
            return
        elif op == BinaryOperator.LOGICAL_OR:
            self._generate_expression(expr.left)
            self._generate_logical_or(expr)
            return

        # General case: push right operand, generate left, operate
        self._generate_expression(expr.right)
        self._emit_instruction("PSHB", "")
        self._emit_instruction("PSHA", "")

        # Generate left operand (result in D)
        self._generate_expression(expr.left)

        # Use _emit_load_sp() to get X = SP, then access pushed word at 0,X
        # NOTE: This destroys X! Only use for operations that don't need X after
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
        elif op in (BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL,
                    BinaryOperator.LESS, BinaryOperator.GREATER,
                    BinaryOperator.LESS_EQ, BinaryOperator.GREATER_EQ):
            self._generate_comparison(op)

        # Pop operand from stack
        self._emit_instruction("INS", "")
        self._emit_instruction("INS", "")

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

        # Left operand already evaluated and pushed
        # Check if false (short-circuit)
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
        self._emit_instruction("BEQ", false_label)

        # Evaluate right operand
        self._generate_expression(expr.right)
        self._emit_instruction("SUBD", "#0")
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
        # Check if true (short-circuit)
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
        self._emit_instruction("BNE", true_label)

        # Evaluate right operand
        self._generate_expression(expr.right)
        self._emit_instruction("SUBD", "#0")
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

        elif op == UnaryOperator.POSITIVE:
            # No-op
            self._generate_expression(expr.operand)

        elif op == UnaryOperator.LOGICAL_NOT:
            self._generate_expression(expr.operand)
            end_label = self._new_label("not")
            # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
            self._emit_instruction("SUBD", "#0")
            self._emit_instruction("BEQ", f"{end_label}_t")
            self._emit_instruction("LDD", "#0")
            self._emit_instruction("BRA", f"{end_label}")
            self._emit_label(f"{end_label}_t")
            self._emit_instruction("LDD", "#1")
            self._emit_label(end_label)

        elif op == UnaryOperator.BITWISE_NOT:
            self._generate_expression(expr.operand)
            self._emit_instruction("COMA", "")
            self._emit_instruction("COMB", "")

        elif op == UnaryOperator.ADDRESS_OF:
            # Get address of variable
            if isinstance(expr.operand, IdentifierExpression):
                info = self._lookup(expr.operand.name)
                if info.is_global:
                    self._emit_instruction("LDD", f"#_{expr.operand.name}")
                else:
                    # Calculate address from frame pointer
                    self._emit_instruction("TXA", "")
                    self._emit_instruction("TAB", "")
                    self._emit_instruction("LDAA", "#0")
                    self._emit_instruction("ADDD", f"#{info.offset}")

        elif op == UnaryOperator.DEREFERENCE:
            self._generate_expression(expr.operand)
            # D contains pointer, load value
            self._emit_instruction("XGDX", "")  # D <-> X
            self._emit_instruction("LDD", "0,X")

        elif op in (UnaryOperator.PRE_INCREMENT, UnaryOperator.PRE_DECREMENT):
            self._generate_increment(expr.operand, op == UnaryOperator.PRE_INCREMENT, True)

        elif op in (UnaryOperator.POST_INCREMENT, UnaryOperator.POST_DECREMENT):
            self._generate_increment(expr.operand, op == UnaryOperator.POST_INCREMENT, False)

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
                if info.sym_type.size == 1:
                    self._emit_instruction("STAB", f"{info.offset},X")
                else:
                    self._emit_instruction("STD", f"{info.offset},X")

        elif isinstance(target, ArraySubscript):
            # Store to array element
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")  # Save value

            # Calculate address
            self._generate_subscript_address(target)

            # Store value: char=1 byte (STAB), int/ptr=2 bytes (STD)
            element_size = self._get_array_element_size(target)
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")
            if element_size == 1:
                self._emit_instruction("STAB", "0,X")  # Store single byte
            else:
                self._emit_instruction("STD", "0,X")   # Store 16-bit value

        elif isinstance(target, UnaryExpression) and target.operator == UnaryOperator.DEREFERENCE:
            # Store through pointer
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")  # Save value
            self._generate_expression(target.operand)
            self._emit_instruction("XGDX", "")  # Pointer to X
            self._emit_instruction("PULA", "")
            self._emit_instruction("PULB", "")
            self._emit_instruction("STD", "0,X")

    def _generate_call(self, expr: CallExpression) -> None:
        """
        Generate code for function call.

        For regular C functions:
        - Push arguments right-to-left
        - JSR to the function
        - Clean up stack after return

        For external OPL procedures:
        - No arguments (enforced by parser)
        - Load procedure name string address into D
        - Call _call_opl which handles QCode injection and resumption
        - D register returns 0 (standard USR return)
        """
        # =====================================================================
        # Check for external OPL procedure call
        # =====================================================================
        # External procedures are called via QCode injection. The _call_opl
        # runtime function builds a synthetic QCode buffer containing:
        #   1. The procedure call (e.g., "azMENU:")
        #   2. USR(restore_address, saved_SP)
        # It then unwinds the stack and exits to the OPL interpreter, which
        # executes the buffer, calls the OPL procedure, then calls USR() to
        # resume C execution.
        if expr.function_name in self._external_funcs:
            # Verify no arguments (should be enforced by parser, but double-check)
            if expr.arguments:
                raise CCodeGenError(
                    f"external procedure '{expr.function_name}' cannot have arguments",
                    expr.location,
                )

            # Create a string literal for the procedure name
            # This will be used by _call_opl to build the QCode buffer
            proc_name_label = self._new_label("_PROC")
            self._strings.append((proc_name_label, expr.function_name))

            self._emit_comment(f"Call external OPL procedure: {expr.function_name}")
            # Load address of procedure name string into D
            self._emit_instruction("LDD", f"#{proc_name_label}")
            # Push name pointer argument to stack (standard calling convention)
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")
            # Call the OPL invocation runtime
            # This will unwind stack, call the OPL procedure, and resume here
            self._emit_instruction("JSR", "_call_opl")
            # Cleanup: REQUIRED! _call_opl calculates resume_addr = return_addr + 2
            # This expects exactly two INS instructions after the JSR, which the
            # restore function jumps past to reach the next statement.
            self._emit_instruction("INS", "")
            self._emit_instruction("INS", "")
            # D register now contains 0 (USR return value, discarded)
            # Execution resumes here after OPL procedure completes
            return

        # =====================================================================
        # Regular C function call
        # =====================================================================
        # Push arguments right-to-left
        for arg in reversed(expr.arguments):
            self._generate_expression(arg)
            self._emit_instruction("PSHB", "")
            self._emit_instruction("PSHA", "")

        # Call function
        self._emit_instruction("JSR", f"_{expr.function_name}")

        # Clean up arguments
        arg_bytes = len(expr.arguments) * 2
        for _ in range(arg_bytes):
            self._emit_instruction("INS", "")

    def _generate_subscript(self, expr: ArraySubscript) -> None:
        """Generate code for array subscript (load value)."""
        self._generate_subscript_address(expr)
        # Load element: char=1 byte (LDAB+CLRA), int/ptr=2 bytes (LDD)
        element_size = self._get_array_element_size(expr)
        if element_size == 1:
            self._emit_instruction("LDAB", "0,X")  # Load single byte
            self._emit_instruction("CLRA", "")     # Zero-extend to 16-bit
        else:
            self._emit_instruction("LDD", "0,X")   # Load 16-bit value

    def _generate_subscript_address(self, expr: ArraySubscript) -> None:
        """Generate address of array element into X register."""
        # Get array base address
        if isinstance(expr.array, IdentifierExpression):
            info = self._lookup(expr.array.name)
            if info.is_global:
                self._emit_instruction("LDX", f"#_{expr.array.name}")
            else:
                # Local array: address is frame + offset
                self._emit_instruction("TXA", "")
                self._emit_instruction("TAB", "")
                self._emit_instruction("LDAA", "#0")
                self._emit_instruction("ADDD", f"#{info.offset}")
                self._emit_instruction("XGDX", "")
        else:
            # Pointer expression
            self._generate_expression(expr.array)
            self._emit_instruction("XGDX", "")

        # Save base address
        self._emit_instruction("PSHX", "")

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
        self._emit_instruction("XGDX", "")

    def _generate_ternary(self, expr: TernaryExpression) -> None:
        """Generate code for ternary expression."""
        else_label = self._new_label("tern_e")
        end_label = self._new_label("tern_x")

        # Evaluate condition
        self._generate_expression(expr.condition)
        # Note: SUBD #0 leaves D unchanged (D-0=D) while setting Z flag
        self._emit_instruction("SUBD", "#0")
        self._emit_instruction("BEQ", else_label)

        # Then expression
        self._generate_expression(expr.then_expr)
        self._emit_instruction("BRA", end_label)

        # Else expression
        self._emit_label(else_label)
        self._generate_expression(expr.else_expr)

        self._emit_label(end_label)

    def _generate_cast(self, expr: CastExpression) -> None:
        """Generate code for type cast."""
        self._generate_expression(expr.expression)

        # Handle char <-> int conversions
        if expr.target_type.base_type == BaseType.CHAR:
            # Truncate to 8 bits (already in B)
            self._emit_instruction("CLRA", "")
        # int to char is automatic (just use low byte)

    def _generate_sizeof(self, expr: SizeofExpression) -> None:
        """Generate code for sizeof expression."""
        if expr.target_type:
            size = expr.target_type.size
        else:
            # Would need type analysis to determine expression type
            size = 2  # Default to int size

        self._emit_instruction("LDD", f"#{size}")
