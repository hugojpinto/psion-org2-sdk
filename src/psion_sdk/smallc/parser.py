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
                CTokenType.EXTERNAL,  # External OPL procedure declarations
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
        # Check for 'external' keyword - OPL procedure declaration
        # =====================================================================
        # External declarations allow C code to call OPL procedures.
        # At runtime, calls to external functions are transformed into
        # QCode injection sequences that invoke the OPL interpreter.
        if self._match(CTokenType.EXTERNAL):
            return self._parse_external_declaration()

        # Parse type specifiers
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise UnexpectedTokenError(
                self._peek().value or self._peek().type.name,
                expected="type specifier",
                location=self._peek().location,
            )

        base_type, is_unsigned = type_info

        # Parse pointer prefix
        pointer_depth = 0
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse identifier
        name_token = self._expect(CTokenType.IDENTIFIER, "identifier")
        name = name_token.value

        # Check if function or variable
        if self._check(CTokenType.LPAREN):
            # Function definition
            return self._parse_function(base_type, is_unsigned, pointer_depth, name, name_token.location)
        else:
            # Global variable declaration
            return self._parse_global_variable(base_type, is_unsigned, pointer_depth, name, name_token.location)

    def _parse_type_specifier(self) -> Optional[tuple[BaseType, bool]]:
        """
        Parse type specifier keywords.

        Returns:
            Tuple of (base_type, is_unsigned) or None if not a type
        """
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

        if not specifiers:
            return None

        try:
            return parse_type_specifiers(specifiers)
        except ValueError as e:
            raise CSyntaxError(str(e), self._peek().location)

    def _parse_external_declaration(self) -> FunctionNode:
        """
        Parse an external OPL procedure declaration.

        Syntax:
            external void procedureName();

        External declarations allow Small-C code to call OPL procedures that
        exist in the Psion's installed OPL programs. At runtime, the compiler
        generates QCode injection sequences to invoke the OPL interpreter.

        Constraints:
        - Return type MUST be void (OPL procedures don't return values to C)
        - Parameters MUST be empty (OPL calling convention is incompatible)
        - Procedure name MUST be <= 8 characters (Psion filesystem limit)
        - No function body (this is a declaration, not a definition)

        The generated code will:
        1. Build a QCode buffer containing the procedure call
        2. Unwind the C stack to the USR entry point
        3. Execute the QCode (which calls the OPL procedure)
        4. Resume C execution after the call

        Reference: dev_docs/PROCEDURE_CALL_RESEARCH.md

        Returns:
            FunctionNode with is_external=True

        Raises:
            CSyntaxError: If the declaration violates external constraints
        """
        location = self._peek().location

        # =====================================================================
        # Parse and validate return type - MUST be void
        # =====================================================================
        # OPL procedures don't return values to C code. The USR() function
        # returns a fixed value (0) which is discarded. Any data exchange
        # between C and OPL must happen through global variables.
        type_info = self._parse_type_specifier()
        if type_info is None:
            raise CSyntaxError(
                "external declaration requires 'void' return type",
                self._peek().location,
                hint="external void procedureName();",
            )

        base_type, is_unsigned = type_info

        # Validate that the return type is void
        if base_type != BaseType.VOID:
            raise CSyntaxError(
                f"external procedures must have void return type, not '{base_type.name.lower()}'",
                location,
                hint="OPL procedures cannot return values to C code; use 'external void'",
            )

        # =====================================================================
        # Parse procedure name
        # =====================================================================
        name_token = self._expect(CTokenType.IDENTIFIER, "procedure name")
        name = name_token.value

        # Validate name length (Psion filesystem limit)
        # OPL procedure names are stored as 8-character filenames
        if len(name) > 8:
            raise CSyntaxError(
                f"external procedure name '{name}' exceeds 8 character limit",
                name_token.location,
                hint="Psion procedure names are limited to 8 characters",
            )

        # =====================================================================
        # Parse parameter list - MUST be empty
        # =====================================================================
        # OPL and C have incompatible calling conventions. OPL procedures
        # receive parameters through global variables, not the stack.
        # We require empty parentheses for syntactic consistency.
        self._expect(CTokenType.LPAREN, "'('")

        # Check for non-empty parameter list
        if not self._check(CTokenType.RPAREN):
            # Allow explicit void: external void foo(void);
            if self._check(CTokenType.VOID) and self._peek(1).type == CTokenType.RPAREN:
                self._advance()  # consume void
            else:
                raise CSyntaxError(
                    "external procedures cannot have parameters",
                    self._peek().location,
                    hint="OPL uses global variables for data exchange, not parameters",
                )

        self._expect(CTokenType.RPAREN, "')'")

        # =====================================================================
        # Expect semicolon - external declarations have no body
        # =====================================================================
        # The actual implementation exists in OPL code on the device.
        # This declaration just tells the C compiler that this name
        # refers to an external OPL procedure.
        self._expect(CTokenType.SEMICOLON, "';'")

        # =====================================================================
        # Create and return the FunctionNode
        # =====================================================================
        # The is_external flag tells the code generator to emit QCode
        # injection sequences instead of normal JSR instructions.
        return FunctionNode(
            location=location,
            name=name,
            return_type=TYPE_VOID,
            parameters=[],
            body=None,
            is_forward_decl=False,  # Not a forward decl - it's an external decl
            is_external=True,
        )

    def _parse_function(
        self,
        base_type: BaseType,
        is_unsigned: bool,
        pointer_depth: int,
        name: str,
        location: SourceLocation,
    ) -> FunctionNode:
        """Parse a function definition."""
        # Create return type
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

        base_type, is_unsigned = type_info

        # Parse pointer prefix
        pointer_depth = 0
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        # Parse name (optional in declarations, but we require it)
        name_token = self._expect(CTokenType.IDENTIFIER, "parameter name")

        # Parse array suffix (treated as pointer)
        if self._match(CTokenType.LBRACKET):
            self._match(CTokenType.NUMBER)  # size is optional and ignored
            self._expect(CTokenType.RBRACKET, "']'")
            pointer_depth += 1

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
    ) -> VariableDeclaration:
        """
        Parse a single declarator: '*'* IDENTIFIER ('[' NUMBER ']')? ('=' expr)?

        This is used for parsing additional variables in multi-variable
        declarations like: int a, *b, c[10];
        """
        location = self._peek().location

        # Parse pointer prefix
        pointer_depth = 0
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
    ) -> list[VariableDeclaration]:
        """
        Parse global variable declaration(s).

        Supports multi-variable declarations like:
            int a, b, c;
            int x = 1, y = 2;
            char *p, buf[10], c;
        """
        declarations = []

        # Parse first declarator (name and pointer already parsed by caller)
        array_size = 0
        if self._match(CTokenType.LBRACKET):
            size_token = self._expect(CTokenType.NUMBER, "array size")
            array_size = size_token.value
            self._expect(CTokenType.RBRACKET, "']'")

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
            decl = self._parse_declarator(base_type, is_unsigned, is_global=True)
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
        """Check if current token starts a type specifier."""
        return self._check(
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
        )

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
        base_type, is_unsigned = type_info

        declarations = []

        # Parse first declarator
        decl = self._parse_declarator(base_type, is_unsigned, is_global=False)
        declarations.append(decl)

        # Parse additional declarators separated by commas
        while self._match(CTokenType.COMMA):
            decl = self._parse_declarator(base_type, is_unsigned, is_global=False)
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
        """Check if token at offset is a type keyword."""
        token = self._peek(offset)
        return token.type in (
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
        )

    def _parse_sizeof(self) -> Expression:
        """Parse sizeof expression."""
        location = self._peek().location
        self._expect(CTokenType.SIZEOF, "'sizeof'")

        if self._match(CTokenType.LPAREN):
            # sizeof(type) or sizeof(expr)
            if self._is_type_keyword():
                type_info = self._parse_type_specifier()
                base_type, is_unsigned = type_info

                pointer_depth = 0
                while self._match(CTokenType.STAR):
                    pointer_depth += 1

                self._expect(CTokenType.RPAREN, "')'")

                target_type = make_type(base_type, is_unsigned, pointer_depth)
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
        base_type, is_unsigned = type_info

        pointer_depth = 0
        while self._match(CTokenType.STAR):
            pointer_depth += 1

        self._expect(CTokenType.RPAREN, "')'")

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
