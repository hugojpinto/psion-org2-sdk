"""
Small-C Recursive Descent Parser
=================================

This module implements a recursive descent parser for the Small-C
language subset. It takes a stream of tokens from the lexer and
builds an Abstract Syntax Tree (AST).

Grammar (Simplified EBNF)
-------------------------
program         ::= (function_def | variable_decl)*
function_def    ::= type_spec IDENTIFIER '(' params? ')' block
variable_decl   ::= type_spec declarator (',' declarator)* ';'
type_spec       ::= 'void' | ('unsigned'? ('char' | 'int'))
declarator      ::= '*'* IDENTIFIER ('[' NUMBER ']')? ('=' expr)?

block           ::= '{' declaration* statement* '}'
statement       ::= if_stmt | while_stmt | for_stmt | do_stmt
                  | switch_stmt | return_stmt | break_stmt
                  | continue_stmt | block | expr_stmt

if_stmt         ::= 'if' '(' expr ')' statement ('else' statement)?
while_stmt      ::= 'while' '(' expr ')' statement
for_stmt        ::= 'for' '(' expr? ';' expr? ';' expr? ')' statement
do_stmt         ::= 'do' statement 'while' '(' expr ')' ';'
switch_stmt     ::= 'switch' '(' expr ')' '{' case_clause* '}'
return_stmt     ::= 'return' expr? ';'
break_stmt      ::= 'break' ';'
continue_stmt   ::= 'continue' ';'
expr_stmt       ::= expr? ';'

Expression Precedence (lowest to highest)
-----------------------------------------
1.  assignment     =, +=, -=, etc.
2.  ternary        ?:
3.  logical_or     ||
4.  logical_and    &&
5.  bitwise_or     |
6.  bitwise_xor    ^
7.  bitwise_and    &
8.  equality       == !=
9.  relational     < > <= >=
10. shift          << >>
11. additive       + -
12. multiplicative * / %
13. unary          - + ! ~ & * ++ --
14. postfix        () [] ++ --
15. primary        IDENTIFIER, NUMBER, STRING, '(' expr ')'

Example Usage
-------------
>>> from psion_sdk.smallc.lexer import CLexer
>>> from psion_sdk.smallc.parser import CParser
>>> source = 'int main() { return 42; }'
>>> tokens = list(CLexer(source, "test.c").tokenize())
>>> parser = CParser(tokens, "test.c")
>>> ast = parser.parse()
>>> print(ast)
ProgramNode with 1 function
"""

from typing import Optional, Callable

from psion_sdk.errors import SourceLocation
from psion_sdk.smallc.lexer import CLexer, CToken, CTokenType
from psion_sdk.smallc.types import (
    CType,
    BaseType,
    TYPE_VOID,
    TYPE_CHAR,
    TYPE_UCHAR,
    TYPE_INT,
    TYPE_UINT,
    parse_type_specifiers,
    make_type,
    make_struct_type,
)
from psion_sdk.smallc.ast import (
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
    AsmStatement,
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
    # Struct-related nodes
    StructField,
    StructDefinition,
    MemberAccessExpression,
)
from psion_sdk.smallc.errors import (
    CSyntaxError,
    UnexpectedTokenError,
    MissingTokenError,
    CErrorCollector,
)


class CParser:
    """
    Recursive descent parser for Small-C.

    Parses a stream of tokens into an Abstract Syntax Tree (AST).
    Uses standard recursive descent with proper operator precedence
    handling for expressions.

    The parser attempts error recovery to report multiple errors
    when possible, rather than stopping at the first error.

    Attributes:
        tokens: List of tokens to parse
        filename: Source filename for error reporting
    """

    def __init__(
        self,
        tokens: list[CToken],
        filename: str = "<input>",
        source_lines: Optional[list[str]] = None,
    ):
        """
        Initialize the parser.

        Args:
            tokens: List of tokens from the lexer
            filename: Source filename for error messages
            source_lines: Original source lines for error context
        """
        self.tokens = tokens
        self.filename = filename
        self.source_lines = source_lines or []

        # Current position in token stream
        self._pos = 0

        # Error collection for multiple error reporting
        self._errors = CErrorCollector()

        # Typedef table: maps type name -> (base_type, is_unsigned, pointer_depth, array_size)
        # Example: "fp_t" -> (BaseType.CHAR, False, 0, 8) for "typedef char fp_t[8]"
        # For struct typedefs, base_type is VOID and we also store struct_name in _struct_typedefs
        self._typedefs: dict[str, tuple[BaseType, bool, int, int]] = {}

        # ==========================================================================
        # Struct Support
        # ==========================================================================
        # Struct definitions table: maps struct name -> list of (field_name, field_type)
        # This is populated when parsing struct definitions and used when:
        # - Checking if 'struct Name' refers to a valid struct type
        # - Computing struct sizes (sum of field sizes)
        # - Resolving field offsets for member access
        self._structs: dict[str, list[tuple[str, CType]]] = {}

        # Struct typedef aliases: maps typedef name -> struct name
        # When a typedef is created for a struct (typedef struct Point Point;),
        # we need to know which struct it refers to
        self._struct_typedefs: dict[str, str] = {}

    def parse(self) -> ProgramNode:
        """
        Parse the token stream into an AST.

        Returns:
            ProgramNode containing all declarations

        Raises:
            CSyntaxError: If parsing fails
        """
        declarations = []

        while not self._at_end():
            try:
                result = self._parse_top_level_declaration()
                if result:
                    # Global variables return a list (for multi-variable decls)
                    # Functions return a single node
                    if isinstance(result, list):
                        declarations.extend(result)
                    else:
                        declarations.append(result)
            except CSyntaxError as e:
                self._errors.add(e)
                # Try to recover by skipping to next declaration
                self._synchronize()

        if self._errors.has_errors():
            self._errors.raise_if_errors()

        return ProgramNode(
            location=SourceLocation(self.filename, 1, 1),
            declarations=declarations,
        )

    # =========================================================================
    # Token Access Methods
    # =========================================================================

    def _at_end(self) -> bool:
        """Check if we've reached the end of tokens."""
        return self._peek().type == CTokenType.EOF

    def _peek(self, offset: int = 0) -> CToken:
        """Look at token at current position + offset."""
        pos = self._pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF
        return self.tokens[pos]

    def _advance(self) -> CToken:
        """Consume and return the current token."""
        if not self._at_end():
            token = self.tokens[self._pos]
            self._pos += 1
            return token
        return self.tokens[-1]  # Return EOF

    def _check(self, *types: CTokenType) -> bool:
        """Check if current token is one of the given types."""
        return self._peek().type in types

    def _match(self, *types: CTokenType) -> Optional[CToken]:
        """
        Consume current token if it matches one of the types.

        Returns:
            The consumed token, or None if no match
        """
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, token_type: CTokenType, message: str = None) -> CToken:
        """
        Expect and consume a specific token type.

        Args:
            token_type: The expected token type
            message: Error message if not found

        Returns:
            The consumed token

        Raises:
            MissingTokenError: If the expected token is not found
        """
        if self._check(token_type):
            return self._advance()

        current = self._peek()
        if message is None:
            message = token_type.name.lower()

        raise MissingTokenError(
            message,
            current.location,
            self._get_source_line(current.line),
        )

    def _get_source_line(self, line: int) -> Optional[str]:
        """Get source line for error reporting."""
        if 0 < line <= len(self.source_lines):
            return self.source_lines[line - 1]
        return None

    def _synchronize(self) -> None:
        """
        Synchronize parser after error for error recovery.

        Skips tokens until we find a likely statement boundary.
        """
        self._advance()

        while not self._at_end():
            # Stop at likely statement boundaries
            if self._peek().type in (
                CTokenType.SEMICOLON,
                CTokenType.RBRACE,
                CTokenType.IF,
                CTokenType.WHILE,
                CTokenType.FOR,
                CTokenType.RETURN,
                CTokenType.INT,
                CTokenType.CHAR,
                CTokenType.VOID,
                CTokenType.OPL,  # OPL procedure declarations
            ):
                if self._peek().type == CTokenType.SEMICOLON:
                    self._advance()  # consume the semicolon
                return

            self._advance()

    # =========================================================================
    # Top-Level Declaration Parsing
    # =========================================================================

    def _parse_top_level_declaration(self):
        """
        Parse a top-level declaration (function, global variable, or external).

        Returns:
            FunctionNode for functions (including external OPL declarations),
            or list[VariableDeclaration] for global variables.

        External declarations have the form:
            external void procedureName();

        Constraints for external declarations:
        - Must have void return type (OPL procedures don't return values to C)
        - Must have no parameters (OPL calling convention is different)
        - Procedure name must be <= 8 characters (Psion limit)
        - No body (declaration only, implemented in OPL)
        """
        # =====================================================================
        # Check for 'struct' keyword - struct definition or variable
        # =====================================================================
        # Struct can appear in several contexts:
        #   struct Point { int x; int y; };        - definition only
        #   struct Point p;                        - variable declaration
        #   struct Point { int x; int y; } p;     - definition + variable
        if self._check(CTokenType.STRUCT):
            return self._parse_struct_or_struct_variable()

        # =====================================================================
        # Check for 'extern' keyword - C external linkage declaration
        # =====================================================================
        # Extern declarations specify that a function or variable is defined
        # in another translation unit (another .c file). Used for multi-file
        # C linking. The declaration tells the compiler the type signature
        # but no code or storage is generated.
        if self._match(CTokenType.EXTERN):
            return self._parse_extern_declaration()

        # =====================================================================
        # Check for 'opl' keyword - OPL procedure declaration (Psion-specific)
        # =====================================================================
        # OPL declarations allow C code to call OPL procedures installed on
        # the Psion device. At runtime, calls to OPL functions are transformed
        # into QCode injection sequences that invoke the OPL interpreter.
        if self._match(CTokenType.OPL):
            return self._parse_opl_declaration()

        # =====================================================================
        # Check for 'typedef' keyword - type alias
        # =====================================================================
        # Typedef creates type aliases. Supported forms:
        #   typedef char mychar;           - simple alias
        #   typedef char buffer[100];      - array typedef
        #   typedef int *intptr;           - pointer typedef
        #   typedef struct Point Point;    - struct alias
        if self._match(CTokenType.TYPEDEF):
            self._parse_typedef()
            return None  # Typedef doesn't produce AST nodes

        # Parse type specifiers
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="type specifier",
                location=self._peek().location,
            )

        base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, struct_name = type_info

        # If this is a struct type (not a variable), redirect to struct handling
        # This catches cases like: struct Point p; (parsed after initial type check)
        if struct_name is not None:
            # Let struct variable handling take over
            return self._parse_struct_variable_declarators_from_type(
                struct_name, typedef_ptr_depth, typedef_array_size
            )

        # Parse pointer prefix (adds to any typedef pointer depth)
        pointer_depth = typedef_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse identifier
        name_token = self._expect(CTokenType.IDENTIFIER, "identifier")
        name = name_token.value

        # Check if function or variable
        if self._check(CTokenType.LPAREN):
            # Function definition - pass typedef_array_size for parameter handling
            return self._parse_function(base_type, is_unsigned, pointer_depth, name, name_token.location, typedef_array_size)
        else:
            # Global variable declaration - pass typedef info for multi-var declarations
            return self._parse_global_variable(base_type, is_unsigned, pointer_depth, name, name_token.location,
                                               typedef_ptr_depth, typedef_array_size)

    def _parse_type_specifier(self) -> Optional[tuple[BaseType, bool, int, int, Optional[str]]]:
        """
        Parse type specifier keywords, typedef names, or struct types.

        Returns:
            Tuple of (base_type, is_unsigned, typedef_pointer_depth, typedef_array_size, struct_name)
            or None if not a type.

            For built-in types, typedef_pointer_depth, typedef_array_size are 0 and struct_name is None.
            For typedef'd types, these carry the typedef's pointer/array info.
            For struct types, base_type is VOID and struct_name contains the struct name.
        """
        # =================================================================
        # Check for 'struct' keyword
        # =================================================================
        # Struct type: struct Name
        if self._check(CTokenType.STRUCT):
            self._advance()  # consume 'struct'

            # Must be followed by struct name (we don't support anonymous structs here)
            if not self._check(CTokenType.IDENTIFIER):
                raise UnexpectedTokenError(
                    self._peek().value or self._peek().type.name,
                    expected="struct name",
                    location=self._peek().location,
                )

            struct_name_token = self._advance()
            struct_name = struct_name_token.value

            # Check if struct is defined (allow forward reference if it's a pointer)
            # We'll validate this later during parsing when we know if it's a pointer
            # For now, just return the type info
            # Note: VOID is used as placeholder base_type for struct types
            return (BaseType.VOID, False, 0, 0, struct_name)

        # =================================================================
        # Check for built-in type specifiers
        # =================================================================
        specifiers = []

        # Collect type specifier keywords
        while self._check(
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
        ):
            token = self._advance()
            specifiers.append(token.value)

        if specifiers:
            try:
                base_type, is_unsigned = parse_type_specifiers(specifiers)
                return (base_type, is_unsigned, 0, 0, None)  # No typedef info, no struct
            except ValueError as e:
                raise CSyntaxError(str(e), self._peek().location)

        # =================================================================
        # Check for typedef name (including struct typedefs)
        # =================================================================
        if self._check(CTokenType.IDENTIFIER):
            name = self._peek().value

            # Check if it's a struct typedef (e.g., "Point" -> struct Point)
            if name in self._struct_typedefs:
                self._advance()  # consume the typedef name
                struct_name = self._struct_typedefs[name]
                return (BaseType.VOID, False, 0, 0, struct_name)

            # Check if it's a regular typedef
            if name in self._typedefs:
                self._advance()  # consume the typedef name
                base_type, is_unsigned, ptr_depth, array_size = self._typedefs[name]
                return (base_type, is_unsigned, ptr_depth, array_size, None)

        return None

    # =========================================================================
    # PARAMETER LIMIT CONFIGURATION (for OPL procedure calls)
    # =========================================================================
    # Maximum parameters allowed for OPL procedure declarations.
    # OPL supports up to 16 parameters, but the QCode buffer size limits this.
    #
    # TO INCREASE THE LIMIT:
    #   1. Change MAX_OPL_PARAMS below
    #   2. Change _COL_MAX_PARAMS in include/runtime.inc to match
    #   3. The runtime buffer will adjust automatically via EQUs
    #
    # BUFFER SIZE CALCULATION:
    #   Each parameter requires 5 bytes in the QCode buffer:
    #     - $22 HH LL  (3 bytes) - PUSHWORD to push the value
    #     - $20 $00    (2 bytes) - PUSHBYTE type marker (0 = integer)
    #
    #   Fixed overhead: 19 bytes (count + proc_call + restore + SP + USR)
    #
    #   Formula: buffer_size = (max_params * 5) + 19
    #
    #   Examples:
    #     4 params:  4*5 + 19 =  39 bytes (current, cell = 49 bytes)
    #     8 params:  8*5 + 19 =  59 bytes (cell = 69 bytes)
    #    16 params: 16*5 + 19 =  99 bytes (cell = 113 bytes)
    #
    # >>> CHANGE THIS VALUE TO INCREASE PARAMETER LIMIT <<<
    # =========================================================================
    MAX_OPL_PARAMS = 4

    def _parse_extern_declaration(self) -> FunctionNode | list[VariableDeclaration]:
        """
        Parse a C extern declaration (external linkage).

        Syntax:
            extern int helper_func(int x);     // Function in another .c file
            extern int global_counter;         // Variable in another .c file

        Extern declarations are used in multi-file C builds to declare functions
        or variables that are defined in a different translation unit (another
        .c file). The declaration tells the compiler the type signature, but
        no code or storage is generated - the definition comes from another file.

        This is standard C semantics for external linkage, enabling modular
        code organization across multiple source files.

        Returns:
            FunctionNode with is_extern=True for function declarations, or
            list[VariableDeclaration] with is_extern=True for variable declarations.

        Raises:
            CSyntaxError: If the declaration is invalid

        Example:
            // In main.c:
            extern int add(int a, int b);  // Declare function from math.c
            extern int counter;             // Declare variable from state.c

            void main() {
                counter = add(1, 2);
            }

            // In math.c:
            int add(int a, int b) {
                return a + b;
            }

            // In state.c:
            int counter = 0;
        """
        location = self._peek().location

        # Parse type specifier
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise CSyntaxError(
                "extern declaration requires a type",
                self._peek().location,
                hint="extern int funcname(); or extern int varname;",
            )

        base_type, is_unsigned, ptr_depth, typedef_array_size, struct_name = type_info

        # Parse pointer prefix
        while self._match(CTokenType.STAR):
            ptr_depth += 1

        # Parse identifier
        name_token = self._expect(CTokenType.IDENTIFIER, "identifier")
        name = name_token.value

        # Check if this is a function or variable declaration
        if self._check(CTokenType.LPAREN):
            # Function declaration: extern int foo(int x);
            self._advance()  # consume '('
            parameters = self._parse_parameter_list()
            self._expect(CTokenType.RPAREN, "')'")
            self._expect(CTokenType.SEMICOLON, "';'")

            # Build return type
            return_type = CType(
                base_type=base_type,
                is_pointer=ptr_depth > 0,
                pointer_depth=ptr_depth,
                is_unsigned=is_unsigned,
            )

            return FunctionNode(
                location=location,
                name=name,
                return_type=return_type,
                parameters=parameters,
                body=None,
                is_forward_decl=True,  # Extern functions are forward declarations
                is_extern=True,
                is_opl=False,
            )

        else:
            # Variable declaration: extern int counter;
            # Check for array
            array_size = typedef_array_size
            if self._match(CTokenType.LBRACKET):
                if self._check(CTokenType.NUMBER):
                    array_size = self._advance().value
                elif self._check(CTokenType.RBRACKET):
                    # extern int arr[]; - unsized array (size determined by definition)
                    array_size = 0  # 0 means unsized
                else:
                    raise CSyntaxError(
                        "expected array size or ']'",
                        self._peek().location,
                    )
                self._expect(CTokenType.RBRACKET, "']'")

            self._expect(CTokenType.SEMICOLON, "';'")

            # Build variable type
            var_type = CType(
                base_type=base_type,
                is_pointer=ptr_depth > 0,
                pointer_depth=ptr_depth,
                is_unsigned=is_unsigned,
                array_size=array_size,
            )

            return [VariableDeclaration(
                location=location,
                name=name,
                var_type=var_type,
                initializer=None,  # Extern variables cannot have initializers
                is_global=True,
                is_extern=True,
            )]

    def _parse_opl_declaration(self) -> FunctionNode:
        """
        Parse an OPL procedure declaration (Psion-specific).

        Syntax:
            opl void procedureName();              // No parameters
            opl void procedureName(int x);         // One integer parameter
            opl int procedureName(int a, int b);   // Multiple parameters

        OPL declarations allow Small-C code to call OPL procedures that
        exist in the Psion's installed OPL programs. At runtime, the compiler
        generates QCode injection sequences to invoke the OPL interpreter.

        Return Types:
        - void: For OPL procedures that don't return useful values
        - int: For OPL procedures that return integers (name ends with %)
        - char: For OPL procedures that return strings (first char returned)

        OPL procedure naming determines return type:
        - PROC%: returns integer (use 'opl int PROC();')
        - PROC:  returns float (use 'opl void', value not accessible)
        - PROC$: returns string (use 'opl char PROC();')

        Parameter Constraints:
        - Only integer parameters are supported (int, char promoted to int)
        - Maximum MAX_OPL_PARAMS parameters (see class constant above)
        - Parameters are passed via QCode opcodes that push onto language stack
        - To increase the limit, see PARAMETER LIMIT CONFIGURATION above

        How Parameters Work:
        - C code evaluates each parameter expression to a 16-bit value
        - Values are pushed onto the C stack, then encoded into QCode buffer
        - QCode buffer contains $22 HH LL sequences for each parameter
        - OPL interpreter pushes parameters onto language stack before QCO_PROC
        - OPL procedure receives parameters just like any OPL procedure call

        Constraints:
        - Return type: void, int, or char only (float not directly supported)
        - Procedure name MUST be <= 8 characters (Psion filesystem limit)
        - No function body (this is a declaration, not a definition)

        The generated code will:
        1. Evaluate parameter expressions (values in D register)
        2. Build a QCode buffer containing parameter pushes + procedure call
        3. Unwind the C stack to the USR entry point
        4. Execute the QCode (which calls the OPL procedure)
        5. Resume C execution after the call
        6. For int/char returns, D register contains the OPL return value

        Reference: dev_docs/PROCEDURE_CALL_RESEARCH.md

        Returns:
            FunctionNode with is_opl=True

        Raises:
            CSyntaxError: If the declaration violates OPL constraints
        """
        location = self._peek().location

        # =====================================================================
        # Parse and validate return type - void, int, or char only
        # =====================================================================
        # OPL procedures can return values to C code via the language stack.
        # Integer return values (from PROC% procedures) are captured and
        # returned in D register. Float and string returns are not supported.
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise CSyntaxError(
                "opl declaration requires a return type",
                self._peek().location,
                hint="opl void procedureName(); or opl int procedureName();",
            )

        base_type, is_unsigned, ptr_depth, _, struct_name = type_info

        # OPL procedures cannot have struct return types
        if struct_name is not None:
            raise CSyntaxError(
                "opl procedures cannot return struct types",
                self._peek().location,
            )

        # Validate that the return type is void, int, or char (no pointers)
        if base_type == BaseType.VOID:
            return_type = TYPE_VOID
        elif base_type == BaseType.INT and ptr_depth == 0:
            # Allow both int and unsigned int for OPL returns
            return_type = TYPE_UINT if is_unsigned else TYPE_INT
        elif base_type == BaseType.CHAR and ptr_depth == 0:
            # Allow char (treated as 8-bit int) for return value
            return_type = TYPE_UCHAR if is_unsigned else TYPE_CHAR
        else:
            raise CSyntaxError(
                f"opl procedures can only return void, int, or char, not '{base_type.name.lower()}'",
                location,
                hint="OPL only supports integer return values to C code; "
                     "use 'opl void', 'opl int', or 'opl char'",
            )

        # =====================================================================
        # Parse procedure name
        # =====================================================================
        name_token = self._expect(CTokenType.IDENTIFIER, "procedure name")
        name = name_token.value

        # Validate name length (Psion filesystem limit)
        # OPL procedure names are stored as 8-character filenames
        # The C return type determines the OPL name suffix:
        #   opl char GETVAL()  -> calls GETVAL$ in OPL (string)
        #   opl int GETVAL()   -> calls GETVAL% in OPL (integer)
        #   opl void GETVAL()  -> calls GETVAL in OPL (no suffix)
        opl_name = name
        if return_type.base_type == BaseType.CHAR:
            opl_name = name + "$"
        elif return_type.base_type == BaseType.INT:
            opl_name = name + "%"
        # void has no suffix
        if len(opl_name) > 8:
            raise CSyntaxError(
                f"opl procedure name '{name}' (OPL: '{opl_name}') exceeds 8 character limit",
                name_token.location,
                hint="Psion procedure names are limited to 8 characters",
            )

        # =====================================================================
        # Parse parameter list - supports integer parameters
        # =====================================================================
        # OPL procedures can receive parameters via the QCode buffer.
        # We build $22 HH LL (push word) opcodes for each integer parameter.
        # Parameters are pushed in reverse order before QCO_PROC ($7D).
        self._expect(CTokenType.LPAREN, "'('")
        parameters = self._parse_parameter_list()
        self._expect(CTokenType.RPAREN, "')'")

        # =====================================================================
        # Validate parameters for OPL procedures
        # =====================================================================
        # OPL procedure parameters are limited:
        # - Only integer types supported (int, char - no pointers, no arrays)
        # - Maximum 4 parameters (buffer size constraint)
        # - Each parameter is passed as a 16-bit value via QCode $22 opcode
        if len(parameters) > self.MAX_OPL_PARAMS:
            raise CSyntaxError(
                f"opl procedures support at most {self.MAX_OPL_PARAMS} parameters, "
                f"got {len(parameters)}",
                location,
                hint=f"To increase the {self.MAX_OPL_PARAMS}-parameter limit (OPL supports up to 16), "
                     "change MAX_OPL_PARAMS in parser.py and _COL_MAX_PARAMS in runtime.inc",
            )

        for param in parameters:
            # Check that parameter type is a simple integer type (int or char)
            # Pointers and arrays are not supported for OPL parameters
            if param.param_type.pointer_depth > 0:
                raise CSyntaxError(
                    f"opl procedure parameter '{param.name}' cannot be a pointer",
                    param.location,
                    hint="Only integer types (int, char) are supported for opl parameters",
                )
            if param.param_type.base_type not in (BaseType.INT, BaseType.CHAR):
                raise CSyntaxError(
                    f"opl procedure parameter '{param.name}' must be int or char type",
                    param.location,
                    hint="OPL only accepts integer parameters via QCode; "
                         "use int or char (char is promoted to int)",
                )

        # =====================================================================
        # Expect semicolon - OPL declarations have no body
        # =====================================================================
        # The actual implementation exists in OPL code on the device.
        # This declaration just tells the C compiler that this name
        # refers to an OPL procedure.
        self._expect(CTokenType.SEMICOLON, "';'")

        # =====================================================================
        # Create and return the FunctionNode
        # =====================================================================
        # The is_opl flag tells the code generator to emit QCode
        # injection sequences instead of normal JSR instructions.
        # The return_type is set based on what the user declared:
        #   - void: return value ignored
        #   - int:  D register contains OPL return value after call
        # Parameters are stored so codegen can generate the appropriate calls.
        return FunctionNode(
            location=location,
            name=name,
            return_type=return_type,  # Use parsed return type (void or int)
            parameters=parameters,    # Parameters for OPL call
            body=None,
            is_forward_decl=False,    # Not a forward decl - it's an OPL decl
            is_extern=False,
            is_opl=True,
        )

    def _parse_typedef(self) -> None:
        """
        Parse a typedef declaration and register the type alias.

        Supported forms:
            typedef char mychar;           - simple alias
            typedef char buffer[100];      - array typedef
            typedef unsigned int uint;     - unsigned type alias
            typedef char *charptr;         - pointer typedef

        The typedef is stored in self._typedefs for later lookup when
        parsing type specifiers.
        """
        # Parse the base type
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="type specifier in typedef",
                location=self._peek().location,
            )

        # Unpack type info - for typedef of typedef, we flatten to the base
        base_type, is_unsigned, inner_ptr_depth, inner_array_size, struct_name = type_info

        # Parse optional pointer prefix (adds to any inherited pointer depth)
        pointer_depth = inner_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse the typedef name
        name_token = self._expect(CTokenType.IDENTIFIER, "typedef name")
        typedef_name = name_token.value

        # Parse optional array size: typedef char name[SIZE];
        # If explicit size given, it overrides inherited array size
        array_size = inner_array_size
        if self._match(CTokenType.LBRACKET):
            size_token = self._expect(CTokenType.NUMBER, "array size")
            try:
                array_size = int(size_token.value)
                if array_size <= 0:
                    raise CSyntaxError(
                        "array size must be positive",
                        size_token.location,
                    )
            except ValueError:
                raise CSyntaxError(
                    f"invalid array size: {size_token.value}",
                    size_token.location,
                )
            self._expect(CTokenType.RBRACKET, "']'")

        # Expect semicolon
        self._expect(CTokenType.SEMICOLON, "';'")

        # Handle struct typedefs specially
        if struct_name is not None:
            # typedef struct Name AliasName;
            # Store both in struct_typedefs and regular typedefs
            self._struct_typedefs[typedef_name] = struct_name
            # Also store in regular typedefs with VOID as base type
            self._typedefs[typedef_name] = (BaseType.VOID, False, pointer_depth, array_size)
        else:
            # Regular typedef
            self._typedefs[typedef_name] = (base_type, is_unsigned, pointer_depth, array_size)

    # =========================================================================
    # Struct Parsing
    # =========================================================================

    def _parse_struct_or_struct_variable(self):
        """
        Parse a struct definition and/or struct variable declaration.

        This method handles all cases where 'struct' keyword appears at top level:

        1. Struct definition only:
           struct Point { int x; int y; };

        2. Struct definition with variable:
           struct Point { int x; int y; } p;

        3. Struct variable (using existing type):
           struct Point p;

        4. Anonymous struct (NOT supported):
           struct { int x; } p;  -> Error

        Returns:
            StructDefinition for case 1 (definition only),
            list containing StructDefinition + VariableDeclaration(s) for case 2,
            list[VariableDeclaration] for case 3
        """
        struct_loc = self._peek().location
        self._expect(CTokenType.STRUCT, "struct")

        # Must have a struct name (we don't support anonymous structs)
        if not self._check(CTokenType.IDENTIFIER):
            if self._check(CTokenType.LBRACE):
                raise CSyntaxError(
                    "anonymous structs are not supported; give the struct a name",
                    self._peek().location,
                )
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="struct name",
                location=self._peek().location,
            )

        name_token = self._advance()
        struct_name = name_token.value

        # Check for definition (has body)
        if self._check(CTokenType.LBRACE):
            # Parse struct body
            struct_def = self._parse_struct_definition(struct_name, struct_loc)

            # Check if followed by variable declaration
            if self._check(CTokenType.SEMICOLON):
                # Definition only: struct Point { ... };
                self._advance()  # consume ;
                return struct_def
            else:
                # Definition + variable: struct Point { ... } p;
                vars = self._parse_struct_variable_declarators(struct_name)
                return [struct_def] + vars
        else:
            # No body - must be using existing struct type
            if struct_name not in self._structs:
                raise CSyntaxError(
                    f"undefined struct type '{struct_name}'",
                    name_token.location,
                )
            # Parse variable declarator(s)
            return self._parse_struct_variable_declarators(struct_name)

    def _parse_struct_definition(self, struct_name: str, location: SourceLocation) -> StructDefinition:
        """
        Parse the body of a struct definition.

        Args:
            struct_name: The name of the struct being defined
            location: Source location of the 'struct' keyword

        Returns:
            StructDefinition AST node
        """
        # Check for duplicate definition
        if struct_name in self._structs:
            raise CSyntaxError(
                f"struct '{struct_name}' is already defined",
                location,
            )

        self._expect(CTokenType.LBRACE, "'{'")

        fields: list[StructField] = []
        field_names: set[str] = set()  # Track for duplicate detection
        total_size = 0

        while not self._check(CTokenType.RBRACE) and not self._at_end():
            field = self._parse_struct_field(struct_name)

            # Check for duplicate field name
            if field.name in field_names:
                raise CSyntaxError(
                    f"duplicate field '{field.name}' in struct '{struct_name}'",
                    field.location,
                )
            field_names.add(field.name)

            # Track total size
            field_size = self._get_type_size(field.field_type)
            total_size += field_size

            # Check struct size limit (HD6303 indexed addressing: 0-255)
            if total_size > 255:
                raise CSyntaxError(
                    f"struct '{struct_name}' size ({total_size} bytes) exceeds maximum (255 bytes)",
                    field.location,
                )

            fields.append(field)

        self._expect(CTokenType.RBRACE, "'}'")

        # Store struct definition for later lookup
        self._structs[struct_name] = [(f.name, f.field_type) for f in fields]

        return StructDefinition(
            location=location,
            name=struct_name,
            fields=fields,
        )

    def _parse_struct_field(self, struct_name: str) -> StructField:
        """
        Parse a single field declaration within a struct.

        Fields have the form:
            type_spec declarator ;

        Examples:
            int x;
            char *ptr;
            struct Point nested;
            char data[10];
        """
        field_loc = self._peek().location

        # Parse type specifier (handles 'struct Name' as well)
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="field type",
                location=self._peek().location,
            )

        base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, field_struct_name = type_info

        # Parse pointer prefix
        pointer_depth = typedef_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse field name
        name_token = self._expect(CTokenType.IDENTIFIER, "field name")
        field_name = name_token.value

        # Parse optional array size
        array_size = typedef_array_size
        if self._match(CTokenType.LBRACKET):
            size_token = self._expect(CTokenType.NUMBER, "array size")
            try:
                array_size = int(size_token.value)
                if array_size <= 0:
                    raise CSyntaxError(
                        "array size must be positive",
                        size_token.location,
                    )
            except ValueError:
                raise CSyntaxError(
                    f"invalid array size: {size_token.value}",
                    size_token.location,
                )
            self._expect(CTokenType.RBRACKET, "']'")

        # Construct field type
        if field_struct_name is not None:
            # Field is of struct type
            # Check for self-reference: struct can only contain pointer to itself, not itself
            if field_struct_name == struct_name and pointer_depth == 0:
                raise CSyntaxError(
                    f"struct '{struct_name}' cannot contain itself directly; use a pointer",
                    field_loc,
                )
            # Check if nested struct is defined (unless it's a pointer forward reference)
            if pointer_depth == 0 and field_struct_name not in self._structs:
                raise CSyntaxError(
                    f"undefined struct type '{field_struct_name}'",
                    field_loc,
                )
            field_type = make_struct_type(field_struct_name, self._get_type_size, pointer_depth, array_size)
        else:
            # Primitive field type
            field_type = make_type(base_type, is_unsigned, pointer_depth, array_size)

        self._expect(CTokenType.SEMICOLON, "';'")

        return StructField(
            location=field_loc,
            name=field_name,
            field_type=field_type,
        )

    def _parse_struct_variable_declarators(self, struct_name: str) -> list[VariableDeclaration]:
        """
        Parse variable declarators after a struct type.

        Handles: struct Point *p1, p2[3], *p3;

        Args:
            struct_name: The struct type name

        Returns:
            List of VariableDeclaration nodes
        """
        declarations = []

        while True:
            decl_loc = self._peek().location

            # Parse pointer prefix
            pointer_depth = 0
            while self._match(CTokenType.STAR):
                pointer_depth += 1

            # Parse variable name
            name_token = self._expect(CTokenType.IDENTIFIER, "variable name")

            # Parse optional array size
            array_size = 0
            if self._match(CTokenType.LBRACKET):
                size_token = self._expect(CTokenType.NUMBER, "array size")
                try:
                    array_size = int(size_token.value)
                    if array_size <= 0:
                        raise CSyntaxError(
                            "array size must be positive",
                            size_token.location,
                        )
                except ValueError:
                    raise CSyntaxError(
                        f"invalid array size: {size_token.value}",
                        size_token.location,
                    )
                self._expect(CTokenType.RBRACKET, "']'")

            # Create struct type for the variable
            var_type = make_struct_type(struct_name, self._get_type_size, pointer_depth, array_size)

            declarations.append(VariableDeclaration(
                location=decl_loc,
                name=name_token.value,
                var_type=var_type,
                initializer=None,  # Struct initializers not supported
                is_global=True,
            ))

            # Check for more declarators
            if not self._match(CTokenType.COMMA):
                break

        self._expect(CTokenType.SEMICOLON, "';'")
        return declarations

    def _parse_struct_variable_declarators_from_type(
        self,
        struct_name: str,
        typedef_ptr_depth: int = 0,
        typedef_array_size: int = 0,
    ) -> list[VariableDeclaration]:
        """
        Parse variable declarators when the type specifier has already been parsed.

        This is called when we get a struct type from _parse_type_specifier (e.g.,
        from a struct typedef like `Point p;` where Point is typedef'd to struct Point).

        Handles: Point *p1, p2[3], *p3;

        Args:
            struct_name: The struct type name
            typedef_ptr_depth: Pointer depth from typedef (e.g., typedef struct Point *PointPtr)
            typedef_array_size: Array size from typedef

        Returns:
            List of VariableDeclaration nodes
        """
        declarations = []

        while True:
            decl_loc = self._peek().location

            # Parse pointer prefix (adds to any typedef pointer depth)
            pointer_depth = typedef_ptr_depth
            while self._match(CTokenType.STAR):
                pointer_depth += 1

            # Parse variable name
            name_token = self._expect(CTokenType.IDENTIFIER, "variable name")

            # Parse optional array size
            array_size = 0
            if self._match(CTokenType.LBRACKET):
                size_token = self._expect(CTokenType.NUMBER, "array size")
                try:
                    array_size = int(size_token.value)
                    if array_size <= 0:
                        raise CSyntaxError(
                            "array size must be positive",
                            size_token.location,
                        )
                except ValueError:
                    raise CSyntaxError(
                        f"invalid array size: {size_token.value}",
                        size_token.location,
                    )
                self._expect(CTokenType.RBRACKET, "']'")

            # Use typedef array size if no explicit size and not a pointer
            if array_size == 0 and pointer_depth == 0 and typedef_array_size > 0:
                array_size = typedef_array_size

            # Create struct type for the variable
            var_type = make_struct_type(struct_name, self._get_type_size, pointer_depth, array_size)

            declarations.append(VariableDeclaration(
                location=decl_loc,
                name=name_token.value,
                var_type=var_type,
                initializer=None,  # Struct initializers not supported
                is_global=True,
            ))

            # Check for more declarators
            if not self._match(CTokenType.COMMA):
                break

        self._expect(CTokenType.SEMICOLON, "';'")
        return declarations

    def _get_type_size(self, struct_name: str) -> int:
        """
        Get the size of a struct type in bytes.

        This is the callback passed to make_struct_type() for computing
        struct sizes. It takes a struct name and returns the total size.

        Args:
            struct_name: The name of the struct type

        Returns:
            Size in bytes, or 0 if struct is undefined
        """
        if struct_name not in self._structs:
            return 0  # Unknown struct, let codegen handle error

        # Calculate size by summing field sizes
        struct_size = 0
        for _, field_type in self._structs[struct_name]:
            struct_size += self._compute_field_size(field_type)

        return struct_size

    def _compute_field_size(self, field_type: CType) -> int:
        """
        Compute the size of a field type in bytes.

        Args:
            field_type: The CType of the field

        Returns:
            Size in bytes
        """
        if field_type.is_pointer:
            return 2  # All pointers are 16-bit

        if field_type.struct_name is not None:
            # Nested struct - recursively compute size
            base_size = self._get_type_size(field_type.struct_name)
            if field_type.array_size > 0:
                return base_size * field_type.array_size
            return base_size

        # Primitive type
        if field_type.base_type == BaseType.CHAR:
            element_size = 1
        elif field_type.base_type == BaseType.INT:
            element_size = 2
        elif field_type.base_type == BaseType.VOID:
            return 0
        else:
            element_size = 2  # Default to int size

        if field_type.array_size > 0:
            return element_size * field_type.array_size
        return element_size

    def _parse_function(
        self,
        base_type: BaseType,
        is_unsigned: bool,
        pointer_depth: int,
        name: str,
        location: SourceLocation,
        typedef_array_size: int = 0,  # Ignored for return types (can't return arrays)
    ) -> FunctionNode:
        """Parse a function definition."""
        # Create return type (array size ignored - can't return arrays in C)
        return_type = make_type(base_type, is_unsigned, pointer_depth)

        # Parse parameters
        self._expect(CTokenType.LPAREN, "'('")
        parameters = self._parse_parameter_list()
        self._expect(CTokenType.RPAREN, "')'")

        # Check for forward declaration (no body)
        if self._match(CTokenType.SEMICOLON):
            return FunctionNode(
                location=location,
                name=name,
                return_type=return_type,
                parameters=parameters,
                body=None,
                is_forward_decl=True,
            )

        # Parse function body
        body = self._parse_block()

        return FunctionNode(
            location=location,
            name=name,
            return_type=return_type,
            parameters=parameters,
            body=body,
            is_forward_decl=False,
        )

    def _parse_parameter_list(self) -> list[ParameterNode]:
        """Parse function parameter list."""
        parameters = []

        # Check for empty parameter list or void
        if self._check(CTokenType.RPAREN):
            return parameters

        if self._check(CTokenType.VOID) and self._peek(1).type == CTokenType.RPAREN:
            self._advance()  # consume void
            return parameters

        # Parse parameters
        while True:
            param = self._parse_parameter()
            parameters.append(param)

            if not self._match(CTokenType.COMMA):
                break

        return parameters

    def _parse_parameter(self) -> ParameterNode:
        """Parse a single function parameter."""
        location = self._peek().location

        # Parse type
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="parameter type",
                location=self._peek().location,
            )

        base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, param_struct_name = type_info

        # Parse pointer prefix (adds to any typedef pointer depth)
        pointer_depth = typedef_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Struct parameters must be pointers (no by-value struct passing)
        if param_struct_name is not None and pointer_depth == 0:
            raise CSyntaxError(
                f"struct parameters must be passed by pointer; use 'struct {param_struct_name} *'",
                location,
            )

        # Parse name (optional in declarations, but we require it)
        name_token = self._expect(CTokenType.IDENTIFIER, "parameter name")

        # Parse array suffix (treated as pointer)
        if self._match(CTokenType.LBRACKET):
            self._match(CTokenType.NUMBER)  # size is optional and ignored
            self._expect(CTokenType.RBRACKET, "']'")
            pointer_depth += 1

        # Construct parameter type
        if param_struct_name is not None:
            param_type = make_struct_type(param_struct_name, pointer_depth)
        else:
            # For parameters, typedef_array_size is informational only (params are by-pointer)
            param_type = make_type(base_type, is_unsigned, pointer_depth)

        return ParameterNode(
            location=location,
            name=name_token.value,
            param_type=param_type,
        )

    def _parse_declarator(
        self,
        base_type: BaseType,
        is_unsigned: bool,
        is_global: bool,
        typedef_ptr_depth: int = 0,
        typedef_array_size: int = 0,
        struct_name: Optional[str] = None,
    ) -> VariableDeclaration:
        """
        Parse a single declarator: '*'* IDENTIFIER ('[' NUMBER ']')? ('=' expr)?

        This is used for parsing additional variables in multi-variable
        declarations like: int a, *b, c[10];

        For typedef'd array types (e.g., typedef char fp_t[8]):
            fp_t x;     -> allocates 8 bytes (uses typedef_array_size)
            fp_t *p;    -> pointer (2 bytes, typedef_array_size ignored)

        For struct types:
            struct Point p;     -> allocates struct size
            struct Point *pp;   -> pointer (2 bytes)
        """
        location = self._peek().location

        # Parse pointer prefix (adds to any typedef pointer depth)
        pointer_depth = typedef_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse name
        name_token = self._expect(CTokenType.IDENTIFIER, "variable name")

        # Check for array
        array_size = 0
        if self._match(CTokenType.LBRACKET):
            size_token = self._expect(CTokenType.NUMBER, "array size")
            array_size = size_token.value
            self._expect(CTokenType.RBRACKET, "']'")

        # Use typedef array size if no explicit size and not a pointer
        if array_size == 0 and pointer_depth == 0 and typedef_array_size > 0:
            array_size = typedef_array_size

        # Create the appropriate type
        if struct_name:
            var_type = make_struct_type(struct_name, self._get_type_size, pointer_depth, array_size)
        else:
            var_type = make_type(base_type, is_unsigned, pointer_depth, array_size)

        # Check for initializer
        initializer = None
        if self._match(CTokenType.ASSIGN):
            initializer = self._parse_expression()

        return VariableDeclaration(
            location=location,
            name=name_token.value,
            var_type=var_type,
            initializer=initializer,
            is_global=is_global,
        )

    def _parse_global_variable(
        self,
        base_type: BaseType,
        is_unsigned: bool,
        pointer_depth: int,
        name: str,
        location: SourceLocation,
        typedef_ptr_depth: int = 0,
        typedef_array_size: int = 0,
        struct_name: Optional[str] = None,
    ) -> list[VariableDeclaration]:
        """
        Parse global variable declaration(s).

        Supports multi-variable declarations like:
            int a, b, c;
            int x = 1, y = 2;
            char *p, buf[10], c;

        For typedef'd array types (e.g., typedef char fp_t[8]):
            fp_t x;     -> allocates 8 bytes (uses typedef_array_size)
            fp_t *p;    -> pointer (2 bytes, typedef_array_size ignored)
            fp_t x[3];  -> 3 arrays of 8 chars each (explicit size overrides)

        For typedef'd pointer types (e.g., typedef int *intptr):
            intptr a, b;  -> both are int* (uses typedef_ptr_depth)

        For struct types:
            struct Point p;     -> allocates struct size
            struct Point *pp;   -> pointer (2 bytes)
        """
        declarations = []

        # Parse first declarator (name and pointer already parsed by caller)
        array_size = 0
        if self._match(CTokenType.LBRACKET):
            size_token = self._expect(CTokenType.NUMBER, "array size")
            array_size = size_token.value
            self._expect(CTokenType.RBRACKET, "']'")

        # Use typedef array size if no explicit size and not a pointer
        if array_size == 0 and pointer_depth == 0 and typedef_array_size > 0:
            array_size = typedef_array_size

        # Create the appropriate type
        if struct_name:
            var_type = make_struct_type(struct_name, self._get_type_size, pointer_depth, array_size)
        else:
            var_type = make_type(base_type, is_unsigned, pointer_depth, array_size)

        initializer = None
        if self._match(CTokenType.ASSIGN):
            initializer = self._parse_expression()

        declarations.append(VariableDeclaration(
            location=location,
            name=name,
            var_type=var_type,
            initializer=initializer,
            is_global=True,
        ))

        # Parse additional declarators separated by commas
        while self._match(CTokenType.COMMA):
            decl = self._parse_declarator(base_type, is_unsigned, is_global=True,
                                          typedef_ptr_depth=typedef_ptr_depth,
                                          typedef_array_size=typedef_array_size,
                                          struct_name=struct_name)
            declarations.append(decl)

        self._expect(CTokenType.SEMICOLON, "';'")

        return declarations

    # =========================================================================
    # Statement Parsing
    # =========================================================================

    def _parse_block(self) -> BlockStatement:
        """Parse a block statement { ... }."""
        location = self._peek().location
        self._expect(CTokenType.LBRACE, "'{'")

        declarations = []
        statements = []

        # Parse local declarations at start of block
        while self._is_type_keyword() and not self._check(CTokenType.RBRACE):
            decls = self._parse_local_declaration()
            declarations.extend(decls)

        # Parse statements
        while not self._check(CTokenType.RBRACE) and not self._at_end():
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)

        self._expect(CTokenType.RBRACE, "'}'")

        return BlockStatement(
            location=location,
            declarations=declarations,
            statements=statements,
        )

    def _is_type_keyword(self) -> bool:
        """Check if current token starts a type specifier (including typedef names and struct)."""
        if self._check(
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
            CTokenType.STRUCT,
        ):
            return True
        # Also check for typedef names (including struct typedefs)
        if self._check(CTokenType.IDENTIFIER):
            name = self._peek().value
            return name in self._typedefs or name in self._struct_typedefs
        return False

    def _parse_local_declaration(self) -> list[VariableDeclaration]:
        """
        Parse local variable declaration(s).

        Supports multi-variable declarations like:
            int a, b, c;
            int x = 1, y = 2;
            char *p, buf[10], c;
        """
        # Parse type (shared by all declarators)
        type_info = self._parse_type_specifier()
        base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, struct_name = type_info

        declarations = []

        # Parse first declarator
        decl = self._parse_declarator(base_type, is_unsigned, is_global=False,
                                       typedef_ptr_depth=typedef_ptr_depth,
                                       typedef_array_size=typedef_array_size,
                                       struct_name=struct_name)
        declarations.append(decl)

        # Parse additional declarators separated by commas
        while self._match(CTokenType.COMMA):
            decl = self._parse_declarator(base_type, is_unsigned, is_global=False,
                                           typedef_ptr_depth=typedef_ptr_depth,
                                           typedef_array_size=typedef_array_size,
                                           struct_name=struct_name)
            declarations.append(decl)

        self._expect(CTokenType.SEMICOLON, "';'")

        return declarations

    def _parse_statement(self):
        """Parse any statement."""
        token = self._peek()

        if token.type == CTokenType.IF:
            return self._parse_if_statement()
        if token.type == CTokenType.WHILE:
            return self._parse_while_statement()
        if token.type == CTokenType.FOR:
            return self._parse_for_statement()
        if token.type == CTokenType.DO:
            return self._parse_do_while_statement()
        if token.type == CTokenType.SWITCH:
            return self._parse_switch_statement()
        if token.type == CTokenType.RETURN:
            return self._parse_return_statement()
        if token.type == CTokenType.BREAK:
            return self._parse_break_statement()
        if token.type == CTokenType.CONTINUE:
            return self._parse_continue_statement()
        if token.type == CTokenType.GOTO:
            return self._parse_goto_statement()
        if token.type == CTokenType.ASM:
            return self._parse_asm_statement()
        if token.type == CTokenType.LBRACE:
            return self._parse_block()
        if token.type == CTokenType.SEMICOLON:
            # Empty statement
            self._advance()
            return None

        # Check for label
        if (token.type == CTokenType.IDENTIFIER and
            self._peek(1).type == CTokenType.COLON):
            return self._parse_label_statement()

        # Expression statement
        return self._parse_expression_statement()

    def _parse_if_statement(self) -> IfStatement:
        """Parse if statement."""
        location = self._peek().location
        self._expect(CTokenType.IF, "'if'")
        self._expect(CTokenType.LPAREN, "'('")
        condition = self._parse_expression()
        self._expect(CTokenType.RPAREN, "')'")

        then_branch = self._parse_statement()

        else_branch = None
        if self._match(CTokenType.ELSE):
            else_branch = self._parse_statement()

        return IfStatement(
            location=location,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def _parse_while_statement(self) -> WhileStatement:
        """Parse while statement."""
        location = self._peek().location
        self._expect(CTokenType.WHILE, "'while'")
        self._expect(CTokenType.LPAREN, "'('")
        condition = self._parse_expression()
        self._expect(CTokenType.RPAREN, "')'")

        body = self._parse_statement()

        return WhileStatement(
            location=location,
            condition=condition,
            body=body,
        )

    def _parse_for_statement(self) -> ForStatement:
        """Parse for statement."""
        location = self._peek().location
        self._expect(CTokenType.FOR, "'for'")
        self._expect(CTokenType.LPAREN, "'('")

        # Initializer (optional)
        initializer = None
        if not self._check(CTokenType.SEMICOLON):
            initializer = self._parse_expression()
        self._expect(CTokenType.SEMICOLON, "';'")

        # Condition (optional)
        condition = None
        if not self._check(CTokenType.SEMICOLON):
            condition = self._parse_expression()
        self._expect(CTokenType.SEMICOLON, "';'")

        # Update (optional)
        update = None
        if not self._check(CTokenType.RPAREN):
            update = self._parse_expression()
        self._expect(CTokenType.RPAREN, "')'")

        body = self._parse_statement()

        return ForStatement(
            location=location,
            initializer=initializer,
            condition=condition,
            update=update,
            body=body,
        )

    def _parse_do_while_statement(self) -> DoWhileStatement:
        """Parse do-while statement."""
        location = self._peek().location
        self._expect(CTokenType.DO, "'do'")

        body = self._parse_statement()

        self._expect(CTokenType.WHILE, "'while'")
        self._expect(CTokenType.LPAREN, "'('")
        condition = self._parse_expression()
        self._expect(CTokenType.RPAREN, "')'")
        self._expect(CTokenType.SEMICOLON, "';'")

        return DoWhileStatement(
            location=location,
            body=body,
            condition=condition,
        )

    def _parse_switch_statement(self) -> SwitchStatement:
        """Parse switch statement."""
        location = self._peek().location
        self._expect(CTokenType.SWITCH, "'switch'")
        self._expect(CTokenType.LPAREN, "'('")
        expression = self._parse_expression()
        self._expect(CTokenType.RPAREN, "')'")
        self._expect(CTokenType.LBRACE, "'{'")

        cases = []
        while not self._check(CTokenType.RBRACE) and not self._at_end():
            case = self._parse_case_clause()
            cases.append(case)

        self._expect(CTokenType.RBRACE, "'}'")

        return SwitchStatement(
            location=location,
            expression=expression,
            cases=cases,
        )

    def _parse_case_clause(self) -> CaseClause:
        """Parse case or default clause."""
        location = self._peek().location
        is_default = False
        value = None

        if self._match(CTokenType.CASE):
            value = self._parse_expression()
            self._expect(CTokenType.COLON, "':'")
        elif self._match(CTokenType.DEFAULT):
            is_default = True
            self._expect(CTokenType.COLON, "':'")
        else:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="'case' or 'default'",
                location=self._peek().location,
            )

        # Parse statements until next case/default or end of switch
        statements = []
        while not self._check(CTokenType.CASE, CTokenType.DEFAULT, CTokenType.RBRACE):
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)

        return CaseClause(
            location=location,
            value=value,
            statements=statements,
            is_default=is_default,
        )

    def _parse_return_statement(self) -> ReturnStatement:
        """Parse return statement."""
        location = self._peek().location
        self._expect(CTokenType.RETURN, "'return'")

        value = None
        if not self._check(CTokenType.SEMICOLON):
            value = self._parse_expression()

        self._expect(CTokenType.SEMICOLON, "';'")

        return ReturnStatement(location=location, value=value)

    def _parse_break_statement(self) -> BreakStatement:
        """Parse break statement."""
        location = self._peek().location
        self._expect(CTokenType.BREAK, "'break'")
        self._expect(CTokenType.SEMICOLON, "';'")
        return BreakStatement(location=location)

    def _parse_continue_statement(self) -> ContinueStatement:
        """Parse continue statement."""
        location = self._peek().location
        self._expect(CTokenType.CONTINUE, "'continue'")
        self._expect(CTokenType.SEMICOLON, "';'")
        return ContinueStatement(location=location)

    def _parse_goto_statement(self) -> GotoStatement:
        """Parse goto statement."""
        location = self._peek().location
        self._expect(CTokenType.GOTO, "'goto'")
        label_token = self._expect(CTokenType.IDENTIFIER, "label")
        self._expect(CTokenType.SEMICOLON, "';'")
        return GotoStatement(location=location, label=label_token.value)

    def _parse_label_statement(self) -> LabelStatement:
        """Parse labeled statement."""
        location = self._peek().location
        name_token = self._expect(CTokenType.IDENTIFIER, "label")
        self._expect(CTokenType.COLON, "':'")
        statement = self._parse_statement()
        return LabelStatement(
            location=location,
            name=name_token.value,
            statement=statement,
        )

    def _parse_asm_statement(self) -> AsmStatement:
        """
        Parse inline assembly statement.

        Syntax:
            asm("assembly code");

        The assembly code string is passed through to the output with minimal
        processing. Variable references using %varname are resolved at code
        generation time.

        Examples:
            asm("        LDX     #$1234");
            asm("        STD     %result");   /* %result -> stack offset */
        """
        location = self._peek().location
        self._expect(CTokenType.ASM, "'asm'")
        self._expect(CTokenType.LPAREN, "'('")

        # Expect a string literal containing the assembly code
        if self._peek().type != CTokenType.STRING:
            raise CSyntaxError(
                "expected string literal for asm()",
                self._peek().location,
                self._get_source_line(self._peek().location.line),
                hint="asm() requires a string argument, e.g., asm(\"LDX #0\")",
            )

        code_token = self._advance()
        code = code_token.value

        self._expect(CTokenType.RPAREN, "')'")
        self._expect(CTokenType.SEMICOLON, "';'")

        return AsmStatement(location=location, code=code)

    def _parse_expression_statement(self) -> ExpressionStatement:
        """Parse expression statement."""
        location = self._peek().location
        expression = self._parse_expression()
        self._expect(CTokenType.SEMICOLON, "';'")
        return ExpressionStatement(location=location, expression=expression)

    # =========================================================================
    # Expression Parsing (Operator Precedence)
    # =========================================================================

    def _parse_expression(self) -> Expression:
        """Parse expression (top-level, handles assignment)."""
        return self._parse_assignment()

    def _parse_assignment(self) -> Expression:
        """Parse assignment expression (right-associative)."""
        expr = self._parse_ternary()

        # Check for assignment operator
        assign_ops = {
            CTokenType.ASSIGN: AssignmentOperator.ASSIGN,
            CTokenType.PLUS_ASSIGN: AssignmentOperator.ADD_ASSIGN,
            CTokenType.MINUS_ASSIGN: AssignmentOperator.SUB_ASSIGN,
            CTokenType.STAR_ASSIGN: AssignmentOperator.MUL_ASSIGN,
            CTokenType.SLASH_ASSIGN: AssignmentOperator.DIV_ASSIGN,
            CTokenType.PERCENT_ASSIGN: AssignmentOperator.MOD_ASSIGN,
            CTokenType.AND_ASSIGN: AssignmentOperator.AND_ASSIGN,
            CTokenType.OR_ASSIGN: AssignmentOperator.OR_ASSIGN,
            CTokenType.XOR_ASSIGN: AssignmentOperator.XOR_ASSIGN,
            CTokenType.LSHIFT_ASSIGN: AssignmentOperator.LSHIFT_ASSIGN,
            CTokenType.RSHIFT_ASSIGN: AssignmentOperator.RSHIFT_ASSIGN,
        }

        if self._peek().type in assign_ops:
            op_token = self._advance()
            # Right-associative: parse value as assignment
            value = self._parse_assignment()
            return AssignmentExpression(
                location=expr.location,
                operator=assign_ops[op_token.type],
                target=expr,
                value=value,
            )

        return expr

    def _parse_ternary(self) -> Expression:
        """Parse ternary conditional expression (? :)."""
        expr = self._parse_logical_or()

        if self._match(CTokenType.QUESTION):
            then_expr = self._parse_expression()
            self._expect(CTokenType.COLON, "':'")
            else_expr = self._parse_ternary()
            return TernaryExpression(
                location=expr.location,
                condition=expr,
                then_expr=then_expr,
                else_expr=else_expr,
            )

        return expr

    def _parse_logical_or(self) -> Expression:
        """Parse logical OR expression (||)."""
        return self._parse_binary(
            self._parse_logical_and,
            {CTokenType.OR: BinaryOperator.LOGICAL_OR},
        )

    def _parse_logical_and(self) -> Expression:
        """Parse logical AND expression (&&)."""
        return self._parse_binary(
            self._parse_bitwise_or,
            {CTokenType.AND: BinaryOperator.LOGICAL_AND},
        )

    def _parse_bitwise_or(self) -> Expression:
        """Parse bitwise OR expression (|)."""
        return self._parse_binary(
            self._parse_bitwise_xor,
            {CTokenType.PIPE: BinaryOperator.BITWISE_OR},
        )

    def _parse_bitwise_xor(self) -> Expression:
        """Parse bitwise XOR expression (^)."""
        return self._parse_binary(
            self._parse_bitwise_and,
            {CTokenType.CARET: BinaryOperator.BITWISE_XOR},
        )

    def _parse_bitwise_and(self) -> Expression:
        """Parse bitwise AND expression (&)."""
        return self._parse_binary(
            self._parse_equality,
            {CTokenType.AMPERSAND: BinaryOperator.BITWISE_AND},
        )

    def _parse_equality(self) -> Expression:
        """Parse equality expression (== !=)."""
        return self._parse_binary(
            self._parse_relational,
            {
                CTokenType.EQ: BinaryOperator.EQUAL,
                CTokenType.NE: BinaryOperator.NOT_EQUAL,
            },
        )

    def _parse_relational(self) -> Expression:
        """Parse relational expression (< > <= >=)."""
        return self._parse_binary(
            self._parse_shift,
            {
                CTokenType.LT: BinaryOperator.LESS,
                CTokenType.GT: BinaryOperator.GREATER,
                CTokenType.LE: BinaryOperator.LESS_EQ,
                CTokenType.GE: BinaryOperator.GREATER_EQ,
            },
        )

    def _parse_shift(self) -> Expression:
        """Parse shift expression (<< >>)."""
        return self._parse_binary(
            self._parse_additive,
            {
                CTokenType.LSHIFT: BinaryOperator.LEFT_SHIFT,
                CTokenType.RSHIFT: BinaryOperator.RIGHT_SHIFT,
            },
        )

    def _parse_additive(self) -> Expression:
        """Parse additive expression (+ -)."""
        return self._parse_binary(
            self._parse_multiplicative,
            {
                CTokenType.PLUS: BinaryOperator.ADD,
                CTokenType.MINUS: BinaryOperator.SUBTRACT,
            },
        )

    def _parse_multiplicative(self) -> Expression:
        """Parse multiplicative expression (* / %)."""
        return self._parse_binary(
            self._parse_unary,
            {
                CTokenType.STAR: BinaryOperator.MULTIPLY,
                CTokenType.SLASH: BinaryOperator.DIVIDE,
                CTokenType.PERCENT: BinaryOperator.MODULO,
            },
        )

    def _parse_binary(
        self,
        operand_parser: Callable[[], Expression],
        operators: dict[CTokenType, BinaryOperator],
    ) -> Expression:
        """
        Generic binary expression parser.

        Args:
            operand_parser: Function to parse operands
            operators: Map of token types to binary operators
        """
        expr = operand_parser()

        while self._peek().type in operators:
            op_token = self._advance()
            right = operand_parser()
            expr = BinaryExpression(
                location=expr.location,
                operator=operators[op_token.type],
                left=expr,
                right=right,
            )

        return expr

    def _parse_unary(self) -> Expression:
        """Parse unary expression (- + ! ~ & * ++ --)."""
        token = self._peek()

        unary_ops = {
            CTokenType.MINUS: UnaryOperator.NEGATE,
            CTokenType.PLUS: UnaryOperator.POSITIVE,
            CTokenType.NOT: UnaryOperator.LOGICAL_NOT,
            CTokenType.TILDE: UnaryOperator.BITWISE_NOT,
            CTokenType.AMPERSAND: UnaryOperator.ADDRESS_OF,
            CTokenType.STAR: UnaryOperator.DEREFERENCE,
            CTokenType.INCREMENT: UnaryOperator.PRE_INCREMENT,
            CTokenType.DECREMENT: UnaryOperator.PRE_DECREMENT,
        }

        if token.type in unary_ops:
            self._advance()
            operand = self._parse_unary()  # Right-associative
            return UnaryExpression(
                location=token.location,
                operator=unary_ops[token.type],
                operand=operand,
            )

        # Check for sizeof
        if token.type == CTokenType.SIZEOF:
            return self._parse_sizeof()

        # Check for cast (type)expr
        if token.type == CTokenType.LPAREN:
            # Look ahead to see if this is a cast
            if self._is_type_at_offset(1):
                return self._parse_cast()

        return self._parse_postfix()

    def _is_type_at_offset(self, offset: int) -> bool:
        """Check if token at offset is a type keyword (including typedef names and struct)."""
        token = self._peek(offset)
        if token.type in (
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
            CTokenType.STRUCT,
        ):
            return True
        # Also check for typedef names (including struct typedefs)
        if token.type == CTokenType.IDENTIFIER:
            name = token.value
            return name in self._typedefs or name in self._struct_typedefs
        return False

    def _parse_sizeof(self) -> Expression:
        """Parse sizeof expression."""
        location = self._peek().location
        self._expect(CTokenType.SIZEOF, "'sizeof'")

        if self._match(CTokenType.LPAREN):
            # sizeof(type) or sizeof(expr)
            if self._is_type_keyword():
                type_info = self._parse_type_specifier()
                base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, struct_name = type_info

                pointer_depth = typedef_ptr_depth
                while self._match(CTokenType.STAR):
                    pointer_depth += 1

                self._expect(CTokenType.RPAREN, "')'")

                # For sizeof, array size matters for determining total size
                array_size = typedef_array_size if pointer_depth == 0 else 0

                # Handle struct types
                if struct_name:
                    target_type = make_struct_type(struct_name, self._get_type_size, pointer_depth, array_size)
                else:
                    target_type = make_type(base_type, is_unsigned, pointer_depth, array_size)
                return SizeofExpression(
                    location=location,
                    target_type=target_type,
                )
            else:
                expr = self._parse_expression()
                self._expect(CTokenType.RPAREN, "')'")
                return SizeofExpression(location=location, expression=expr)
        else:
            # sizeof expr (without parentheses)
            expr = self._parse_unary()
            return SizeofExpression(location=location, expression=expr)

    def _parse_cast(self) -> Expression:
        """Parse cast expression (type)expr."""
        location = self._peek().location
        self._expect(CTokenType.LPAREN, "'('")

        type_info = self._parse_type_specifier()
        base_type, is_unsigned, typedef_ptr_depth, typedef_array_size, struct_name = type_info

        pointer_depth = typedef_ptr_depth
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        self._expect(CTokenType.RPAREN, "')'")

        # For casts, we don't use typedef array size (you can't cast to array type)
        # For struct types, only pointer casts are allowed
        if struct_name:
            if pointer_depth == 0:
                raise CSyntaxError(
                    f"cannot cast to struct type '{struct_name}' by value; use pointer cast",
                    location,
                )
            target_type = make_struct_type(struct_name, self._get_type_size, pointer_depth)
        else:
            target_type = make_type(base_type, is_unsigned, pointer_depth)
        expr = self._parse_unary()

        return CastExpression(
            location=location,
            target_type=target_type,
            expression=expr,
        )

    def _parse_postfix(self) -> Expression:
        """Parse postfix expression (calls, subscripts, ++, --)."""
        expr = self._parse_primary()

        while True:
            # Function call
            if self._match(CTokenType.LPAREN):
                expr = self._parse_call(expr)

            # Array subscript
            elif self._match(CTokenType.LBRACKET):
                index = self._parse_expression()
                self._expect(CTokenType.RBRACKET, "']'")
                expr = ArraySubscript(
                    location=expr.location,
                    array=expr,
                    index=index,
                )

            # Post-increment
            elif self._match(CTokenType.INCREMENT):
                expr = UnaryExpression(
                    location=expr.location,
                    operator=UnaryOperator.POST_INCREMENT,
                    operand=expr,
                )

            # Post-decrement
            elif self._match(CTokenType.DECREMENT):
                expr = UnaryExpression(
                    location=expr.location,
                    operator=UnaryOperator.POST_DECREMENT,
                    operand=expr,
                )

            # Member access: struct.field
            elif self._match(CTokenType.DOT):
                member_token = self._expect(CTokenType.IDENTIFIER, "member name")
                expr = MemberAccessExpression(
                    location=expr.location,
                    object_expr=expr,
                    member_name=member_token.value,
                    is_arrow=False,
                )

            # Pointer member access: ptr->field
            elif self._match(CTokenType.ARROW):
                member_token = self._expect(CTokenType.IDENTIFIER, "member name")
                expr = MemberAccessExpression(
                    location=expr.location,
                    object_expr=expr,
                    member_name=member_token.value,
                    is_arrow=True,
                )

            else:
                break

        return expr

    def _parse_call(self, callee: Expression) -> CallExpression:
        """Parse function call arguments."""
        # Callee must be an identifier for now
        if not isinstance(callee, IdentifierExpression):
            raise CSyntaxError(
                "cannot call non-function",
                callee.location,
            )

        arguments = []
        if not self._check(CTokenType.RPAREN):
            while True:
                arg = self._parse_assignment()  # Don't allow comma expression in arguments
                arguments.append(arg)
                if not self._match(CTokenType.COMMA):
                    break

        self._expect(CTokenType.RPAREN, "')'")

        return CallExpression(
            location=callee.location,
            function_name=callee.name,
            arguments=arguments,
        )

    def _parse_primary(self) -> Expression:
        """Parse primary expression (literals, identifiers, parenthesized)."""
        token = self._peek()

        # Number literal
        if token.type == CTokenType.NUMBER:
            self._advance()
            return NumberLiteral(location=token.location, value=token.value)

        # Character literal
        if token.type == CTokenType.CHAR_LITERAL:
            self._advance()
            return CharLiteral(location=token.location, value=token.value)

        # String literal
        if token.type == CTokenType.STRING:
            self._advance()
            return StringLiteral(location=token.location, value=token.value)

        # Identifier
        if token.type == CTokenType.IDENTIFIER:
            self._advance()
            return IdentifierExpression(location=token.location, name=token.value)

        # Parenthesized expression
        if token.type == CTokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(CTokenType.RPAREN, "')'")
            return expr

        # Error
        raise UnexpectedTokenError(
            token.value or token.type.name,
            expected="expression",
            location=token.location,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_source(source: str, filename: str = "<input>") -> ProgramNode:
    """
    Parse C source code into an AST.

    This is a convenience function that combines lexing and parsing.

    Args:
        source: The C source code
        filename: Source filename for error messages

    Returns:
        The root ProgramNode of the AST

    Raises:
        CSyntaxError: If parsing fails
    """
    lexer = CLexer(source, filename)
    tokens = list(lexer.tokenize())
    source_lines = source.splitlines()
    parser = CParser(tokens, filename, source_lines)
    return parser.parse()
