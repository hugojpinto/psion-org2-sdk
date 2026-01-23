"""
HD6303 Assembly Language Parser
================================

This module implements a parser for HD6303 assembly language. It converts
a stream of tokens from the lexer into an abstract syntax tree (AST) of
statements that the code generator can process.

Statement Types
---------------
The parser produces these types of statements:

1. **LabelDef**: Label definition (global or local)
   ```asm
   start:          ; Global label
   .loop:          ; Local label
   ```

2. **Instruction**: Machine instruction with operand
   ```asm
   LDAA #$41       ; Immediate mode
   STAA buffer     ; Direct/Extended mode
   LDAB 5,X        ; Indexed mode
   BNE start       ; Relative mode
   ```

3. **Directive**: Assembler directive
   ```asm
   ORG $8000       ; Set origin
   buffer EQU $40  ; Define constant
   FCB $41, $42    ; Define bytes
   ```

4. **MacroDef**: Macro definition
   ```asm
   MACRO push_all
       PSHA
       PSHB
       PSHX
   ENDM
   ```

5. **MacroCall**: Macro invocation

6. **ConditionalBlock**: Conditional assembly (#IF, #IFDEF, etc.)

Addressing Mode Detection
-------------------------
The parser determines addressing modes by examining the operand syntax:

| Syntax      | Mode       | Example     |
|-------------|------------|-------------|
| (none)      | Inherent   | NOP, RTS    |
| #value      | Immediate  | #$41        |
| value       | Direct     | $40 (<=FF)  |
| value       | Extended   | $1234 (>FF) |
| value,X     | Indexed    | 5,X         |
| label       | Relative   | BNE label   |

Note: Direct vs Extended is determined during code generation when
the value is known. The parser marks these as DIRECT_OR_EXTENDED.
"""

from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum, auto

from psion_sdk.errors import (
    AssemblySyntaxError,
    SourceLocation,
)
from psion_sdk.assembler.lexer import Token, TokenType, Lexer
from psion_sdk.cpu import (
    AddressingMode,
    MNEMONICS,
    BRANCH_INSTRUCTIONS,
    INHERENT_ONLY_INSTRUCTIONS,
)


# =============================================================================
# Addressing Mode for Parser (includes ambiguous cases)
# =============================================================================

class ParsedAddressingMode(Enum):
    """
    Addressing modes as determined by the parser.

    This includes DIRECT_OR_EXTENDED which is resolved during code
    generation when the actual value is known.
    """
    INHERENT = auto()         # No operand
    IMMEDIATE = auto()        # #value
    DIRECT_OR_EXTENDED = auto()  # address (resolved later)
    INDEXED = auto()          # offset,X
    RELATIVE = auto()         # branch target
    # For HD6303 bit manipulation instructions (AIM, OIM, EIM, TIM)
    IMMEDIATE_DIRECT = auto()    # #mask, addr
    IMMEDIATE_INDEXED = auto()   # #mask, offset,X


# =============================================================================
# Statement Data Classes
# =============================================================================

@dataclass
class Statement:
    """
    Base class for all parsed statements.

    Every statement has a source location for error reporting.
    """
    location: SourceLocation


@dataclass
class LabelDef(Statement):
    """
    Label definition statement.

    Attributes:
        name: Label name (including . or @ prefix for local labels)
        is_local: True if this is a local label
    """
    name: str
    is_local: bool = False


@dataclass
class Operand:
    """
    Instruction operand with addressing mode.

    Attributes:
        mode: The addressing mode
        tokens: Token list representing the operand value/expression
        is_force_extended: True if using > prefix to force extended mode
        is_force_direct: True if using < prefix to force direct mode
    """
    mode: ParsedAddressingMode
    tokens: list[Token] = field(default_factory=list)
    is_force_extended: bool = False
    is_force_direct: bool = False
    # For bit manipulation instructions (AIM, OIM, EIM, TIM)
    mask_tokens: Optional[list[Token]] = None


@dataclass
class Instruction(Statement):
    """
    Machine instruction statement.

    Attributes:
        mnemonic: The instruction mnemonic (uppercase)
        operand: The operand (may be None for inherent mode)
    """
    mnemonic: str
    operand: Optional[Operand] = None


@dataclass
class Directive(Statement):
    """
    Assembler directive statement.

    Attributes:
        name: Directive name (uppercase)
        arguments: List of argument token lists
        label: Optional label associated with directive (for EQU, SET)
    """
    name: str
    arguments: list[list[Token]] = field(default_factory=list)
    label: Optional[str] = None


@dataclass
class MacroDef(Statement):
    """
    Macro definition.

    Attributes:
        name: Macro name
        parameters: List of parameter names
        body: List of statements in macro body
    """
    name: str
    parameters: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)


@dataclass
class MacroCall(Statement):
    """
    Macro invocation.

    Attributes:
        name: Macro name
        arguments: List of argument token lists
    """
    name: str
    arguments: list[list[Token]] = field(default_factory=list)


@dataclass
class ConditionalBlock(Statement):
    """
    Conditional assembly block.

    Attributes:
        condition_type: IF, IFDEF, IFNDEF, etc.
        condition_tokens: Token list for condition expression
        if_body: Statements to assemble if condition is true
        else_body: Statements to assemble if condition is false
    """
    condition_type: str  # "IF", "IFDEF", "IFNDEF"
    condition_tokens: list[Token] = field(default_factory=list)
    if_body: list[Statement] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)


# =============================================================================
# Directive Names
# =============================================================================

# Directives that define data
DATA_DIRECTIVES = frozenset({
    "FCB", "DB", "BYTE",      # Define byte(s)
    "FCC",                     # Define character string
    "FDB", "DW", "WORD",      # Define word(s)
    "RMB", "DS", "RESERVE",   # Reserve bytes
    "FILL",                    # Fill with value
    "ALIGN",                   # Align to boundary
    "INCBIN",                  # Include binary file
})

# Directives that affect assembly state
CONTROL_DIRECTIVES = frozenset({
    "ORG",                     # Set origin
    "EQU", "SET",             # Define symbol
    "END",                     # End of source
    "INCLUDE",                 # Include source file
    "SECTION",                 # Define section
    "MODEL",                   # Set target Psion model (CM, XP, LA, LZ, LZ64)
})

# Listing control directives
LISTING_DIRECTIVES = frozenset({
    "LIST", "NOLIST",
    "PAGE", "TITLE",
})

# All directives
ALL_DIRECTIVES = DATA_DIRECTIVES | CONTROL_DIRECTIVES | LISTING_DIRECTIVES | {"MACRO", "ENDM"}


# =============================================================================
# Parser Implementation
# =============================================================================

class Parser:
    """
    Parses HD6303 assembly source into statements.

    The parser processes tokens line by line, producing Statement objects
    that represent the semantic content of the source.

    Usage:
        lexer = Lexer(source, filename)
        tokens = list(lexer.tokenize())
        parser = Parser(tokens, filename)
        statements = parser.parse()
    """

    def __init__(
        self,
        tokens: list[Token],
        filename: str = "<input>",
        macros: dict[str, "MacroDef"] | None = None
    ):
        """
        Initialize the parser.

        Args:
            tokens: List of tokens from lexer
            filename: Source filename for error reporting
            macros: Pre-loaded macro definitions (from included files)
        """
        self._tokens = tokens
        self._filename = filename
        self._pos = 0
        self._macros: dict[str, MacroDef] = macros.copy() if macros else {}

    def parse(self) -> list[Statement]:
        """
        Parse all tokens into statements.

        Returns:
            List of Statement objects

        Raises:
            AssemblySyntaxError: If syntax error encountered
        """
        statements: list[Statement] = []

        while not self._at_end():
            # Skip blank lines
            if self._check(TokenType.NEWLINE):
                self._advance()
                continue

            if self._check(TokenType.EOF):
                break

            stmt = self._parse_line()
            if stmt is not None:
                if isinstance(stmt, list):
                    statements.extend(stmt)
                else:
                    statements.append(stmt)

        return statements

    # =========================================================================
    # Token Navigation
    # =========================================================================

    def _at_end(self) -> bool:
        """Check if at end of token stream."""
        return self._pos >= len(self._tokens) or self._current().type == TokenType.EOF

    def _current(self) -> Token:
        """Get current token."""
        if self._pos >= len(self._tokens):
            last = self._tokens[-1] if self._tokens else None
            return Token(
                TokenType.EOF, None,
                last.line if last else 1,
                last.column if last else 1,
                last.filename if last else self._filename
            )
        return self._tokens[self._pos]

    def _peek(self, offset: int = 0) -> Token:
        """Look ahead at token."""
        pos = self._pos + offset
        if pos >= len(self._tokens):
            return self._current()
        return self._tokens[pos]

    def _advance(self) -> Token:
        """Consume and return current token."""
        token = self._current()
        self._pos += 1
        return token

    def _check(self, *types: TokenType) -> bool:
        """Check if current token is one of the given types."""
        return self._current().type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        """Match and consume if current token is one of the types."""
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, token_type: TokenType, message: str) -> Token:
        """Expect specific token type, raise error if not found."""
        if not self._check(token_type):
            raise AssemblySyntaxError(message, self._current().location)
        return self._advance()

    def _skip_to_eol(self) -> None:
        """Skip remaining tokens to end of line."""
        while not self._check(TokenType.NEWLINE, TokenType.EOF):
            self._advance()

    def _location(self) -> SourceLocation:
        """Get current source location."""
        tok = self._current()
        return SourceLocation(tok.filename, tok.line, tok.column)

    # =========================================================================
    # Line Parsing
    # =========================================================================

    def _parse_line(self) -> Optional[Union[Statement, list[Statement]]]:
        """
        Parse a single line of assembly.

        Returns one or more statements, or None for empty/comment lines.
        """
        start_location = self._location()
        statements: list[Statement] = []

        # Check for conditional assembly directives
        if self._check(TokenType.HASH):
            return self._parse_conditional()

        # Check for label at start of line
        label = self._try_parse_label()
        if label:
            statements.append(label)

        # Check for instruction or directive
        if self._check(TokenType.IDENTIFIER):
            name = self._current().value.upper()

            # Handle dot-prefixed directives (e.g., .MODEL, .ORG)
            # Strip leading dot for directive lookup
            directive_name = name[1:] if name.startswith(".") else name

            # Check if it's a mnemonic
            if name in MNEMONICS:
                inst = self._parse_instruction()
                statements.append(inst)
            # Check if it's a directive (with or without dot prefix)
            elif directive_name in ALL_DIRECTIVES:
                directive = self._parse_directive(label.name if label else None)
                statements.append(directive)
            # Check if it's a macro call
            elif name in self._macros:
                macro_call = self._parse_macro_call()
                statements.append(macro_call)
            # Check for symbol = value syntax
            elif self._peek(1).type == TokenType.EQUALS:
                directive = self._parse_equals_directive(label.name if label else None)
                statements.append(directive)
            # Could be a label without colon followed by something
            elif label is None:
                # Treat as label without colon
                label = self._parse_label_without_colon()
                if label:
                    statements.append(label)
                    # Continue parsing rest of line
                    return self._continue_after_label(statements)
                else:
                    # Not a valid label either - unknown identifier
                    raise AssemblySyntaxError(
                        f"unknown instruction or directive '{name}'",
                        self._current().location
                    )
            else:
                raise AssemblySyntaxError(
                    f"unknown instruction or directive '{name}'",
                    self._current().location
                )

        # Expect end of line
        self._match(TokenType.NEWLINE)

        return statements if statements else None

    def _continue_after_label(
        self,
        statements: list[Statement]
    ) -> Optional[Union[Statement, list[Statement]]]:
        """Continue parsing after a label was found."""
        if self._check(TokenType.NEWLINE, TokenType.EOF):
            self._match(TokenType.NEWLINE)
            return statements if statements else None

        if self._check(TokenType.IDENTIFIER):
            name = self._current().value.upper()
            # Handle dot-prefixed directives
            directive_name = name[1:] if name.startswith(".") else name

            if name in MNEMONICS:
                statements.append(self._parse_instruction())
            elif directive_name in ALL_DIRECTIVES:
                label_name = statements[0].name if statements and isinstance(statements[0], LabelDef) else None
                statements.append(self._parse_directive(label_name))

        self._match(TokenType.NEWLINE)
        return statements if statements else None

    # =========================================================================
    # Label Parsing
    # =========================================================================

    def _try_parse_label(self) -> Optional[LabelDef]:
        """
        Try to parse a label definition.

        Returns LabelDef if found, None otherwise.

        Handles labels with \\@ suffix for unique labels in macros:
        - `.label\\@:` -> identifier + macro_param + colon
        """
        if not self._check(TokenType.IDENTIFIER):
            return None

        # Check if followed by colon (definite label)
        if self._peek(1).type == TokenType.COLON:
            name_token = self._advance()
            self._advance()  # consume colon
            is_local = name_token.value.startswith((".","@"))
            return LabelDef(
                location=name_token.location,
                name=name_token.value,
                is_local=is_local
            )

        # Check for label\@: pattern (identifier + macro_param + colon)
        if (self._peek(1).type == TokenType.MACRO_PARAM and
                self._peek(2).type == TokenType.COLON):
            name_token = self._advance()  # identifier
            macro_param = self._advance()  # macro_param (should be "@")
            self._advance()  # consume colon

            # Build the full label name with \@ placeholder
            # The \@ will be replaced during macro expansion
            full_name = name_token.value + "\\" + str(macro_param.value)
            is_local = name_token.value.startswith((".", "@"))
            return LabelDef(
                location=name_token.location,
                name=full_name,
                is_local=is_local
            )

        return None

    def _parse_label_without_colon(self) -> Optional[LabelDef]:
        """
        Parse a label that doesn't have a colon.

        Only valid if followed by instruction/directive on same line or EOL.
        """
        if not self._check(TokenType.IDENTIFIER):
            return None

        name_token = self._current()
        name = name_token.value

        # Check what follows
        next_tok = self._peek(1)

        # If followed by instruction or directive, this is a label
        if next_tok.type == TokenType.IDENTIFIER:
            next_name = next_tok.value.upper()
            if next_name in MNEMONICS or next_name in ALL_DIRECTIVES:
                self._advance()  # consume label name
                is_local = name.startswith((".", "@"))
                return LabelDef(
                    location=name_token.location,
                    name=name,
                    is_local=is_local
                )

        # If followed by EOL, it's a standalone label
        if next_tok.type in (TokenType.NEWLINE, TokenType.EOF):
            self._advance()  # consume label name
            is_local = name.startswith((".", "@"))
            return LabelDef(
                location=name_token.location,
                name=name,
                is_local=is_local
            )

        return None

    # =========================================================================
    # Instruction Parsing
    # =========================================================================

    def _parse_instruction(self) -> Instruction:
        """Parse a machine instruction."""
        mnemonic_token = self._advance()
        mnemonic = mnemonic_token.value.upper()
        location = mnemonic_token.location

        # Check for inherent-only instructions
        if mnemonic in INHERENT_ONLY_INSTRUCTIONS:
            return Instruction(
                location=location,
                mnemonic=mnemonic,
                operand=Operand(mode=ParsedAddressingMode.INHERENT)
            )

        # Check for branch instructions
        if mnemonic in BRANCH_INSTRUCTIONS:
            operand = self._parse_branch_operand()
            return Instruction(location=location, mnemonic=mnemonic, operand=operand)

        # Check for bit manipulation instructions (AIM, OIM, EIM, TIM)
        if mnemonic in ("AIM", "OIM", "EIM", "TIM"):
            operand = self._parse_bit_manipulation_operand()
            return Instruction(location=location, mnemonic=mnemonic, operand=operand)

        # Parse regular operand
        if self._check(TokenType.NEWLINE, TokenType.EOF):
            # No operand - inherent mode
            return Instruction(
                location=location,
                mnemonic=mnemonic,
                operand=Operand(mode=ParsedAddressingMode.INHERENT)
            )

        operand = self._parse_operand()
        return Instruction(location=location, mnemonic=mnemonic, operand=operand)

    def _parse_operand(self) -> Operand:
        """Parse an instruction operand."""
        # Check for immediate mode (#)
        if self._match(TokenType.HASH):
            tokens = self._collect_expression_tokens()
            return Operand(mode=ParsedAddressingMode.IMMEDIATE, tokens=tokens)

        # Check for force direct (<) or force extended (>)
        force_direct = False
        force_extended = False

        if self._match(TokenType.LT):
            force_direct = True
        elif self._match(TokenType.GT):
            force_extended = True

        # Collect expression tokens
        tokens = self._collect_expression_tokens()

        # Check for indexed mode (,X at end)
        if self._check(TokenType.COMMA):
            self._advance()  # consume comma
            if self._check(TokenType.IDENTIFIER):
                reg = self._current().value.upper()
                if reg == "X":
                    self._advance()  # consume X
                    return Operand(
                        mode=ParsedAddressingMode.INDEXED,
                        tokens=tokens,
                        is_force_direct=force_direct,
                        is_force_extended=force_extended
                    )

            raise AssemblySyntaxError(
                "expected 'X' after comma in indexed addressing",
                self._current().location
            )

        # Direct or extended mode (determined by value during code generation)
        return Operand(
            mode=ParsedAddressingMode.DIRECT_OR_EXTENDED,
            tokens=tokens,
            is_force_direct=force_direct,
            is_force_extended=force_extended
        )

    def _parse_branch_operand(self) -> Operand:
        """Parse a branch instruction operand (relative addressing)."""
        tokens = self._collect_expression_tokens()
        return Operand(mode=ParsedAddressingMode.RELATIVE, tokens=tokens)

    def _parse_bit_manipulation_operand(self) -> Operand:
        """
        Parse operand for AIM, OIM, EIM, TIM instructions.

        Syntax: #mask, address  or  #mask, offset,X
        """
        # Expect immediate value first
        self._expect(TokenType.HASH, "expected '#' for bit manipulation mask")
        mask_tokens = self._collect_expression_tokens_until_comma()

        # Expect comma
        self._expect(TokenType.COMMA, "expected ',' after mask value")

        # Parse address/offset
        addr_tokens = self._collect_expression_tokens()

        # Check for indexed mode
        if self._check(TokenType.COMMA):
            self._advance()  # consume comma
            if self._check(TokenType.IDENTIFIER) and self._current().value.upper() == "X":
                self._advance()  # consume X
                return Operand(
                    mode=ParsedAddressingMode.IMMEDIATE_INDEXED,
                    tokens=addr_tokens,
                    mask_tokens=mask_tokens
                )
            raise AssemblySyntaxError(
                "expected 'X' after comma",
                self._current().location
            )

        return Operand(
            mode=ParsedAddressingMode.IMMEDIATE_DIRECT,
            tokens=addr_tokens,
            mask_tokens=mask_tokens
        )

    def _collect_expression_tokens(self) -> list[Token]:
        """Collect tokens that form an expression until EOL or comma."""
        tokens = []
        paren_depth = 0

        while not self._check(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()

            # Handle comma (might be part of indexed addressing)
            if tok.type == TokenType.COMMA and paren_depth == 0:
                break

            # Track parentheses
            if tok.type == TokenType.LPAREN:
                paren_depth += 1
            elif tok.type == TokenType.RPAREN:
                paren_depth -= 1

            tokens.append(self._advance())

        return tokens

    def _collect_expression_tokens_until_comma(self) -> list[Token]:
        """Collect expression tokens until a comma."""
        tokens = []
        paren_depth = 0

        while not self._check(TokenType.NEWLINE, TokenType.EOF, TokenType.COMMA):
            tok = self._current()

            if tok.type == TokenType.COMMA and paren_depth == 0:
                break

            if tok.type == TokenType.LPAREN:
                paren_depth += 1
            elif tok.type == TokenType.RPAREN:
                paren_depth -= 1

            tokens.append(self._advance())

        return tokens

    # =========================================================================
    # Directive Parsing
    # =========================================================================

    def _parse_directive(self, label: Optional[str] = None) -> Directive:
        """Parse an assembler directive."""
        directive_token = self._advance()
        raw_name = directive_token.value.upper()
        # Strip leading dot for directive name (e.g., .MODEL -> MODEL)
        name = raw_name[1:] if raw_name.startswith(".") else raw_name
        location = directive_token.location

        # Parse directive-specific arguments
        if name in ("ORG",):
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name=name, arguments=args, label=label)

        if name in ("EQU", "SET"):
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name=name, arguments=args, label=label)

        if name in ("FCB", "DB", "BYTE"):
            args = self._parse_comma_separated_args()
            return Directive(location=location, name="FCB", arguments=args, label=label)

        if name in ("FDB", "DW", "WORD"):
            args = self._parse_comma_separated_args()
            return Directive(location=location, name="FDB", arguments=args, label=label)

        if name in ("FCC",):
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name="FCC", arguments=args, label=label)

        if name in ("RMB", "DS", "RESERVE"):
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name="RMB", arguments=args, label=label)

        if name == "FILL":
            args = self._parse_comma_separated_args()
            if len(args) != 2:
                raise AssemblySyntaxError(
                    "FILL requires two arguments: value, count",
                    location
                )
            return Directive(location=location, name=name, arguments=args, label=label)

        if name == "ALIGN":
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name=name, arguments=args, label=label)

        if name == "INCLUDE":
            # Expect string argument
            if self._check(TokenType.STRING):
                filename_tok = self._advance()
                return Directive(
                    location=location,
                    name=name,
                    arguments=[[filename_tok]],
                    label=label
                )
            raise AssemblySyntaxError(
                "INCLUDE requires a filename string",
                location
            )

        if name == "INCBIN":
            if self._check(TokenType.STRING):
                filename_tok = self._advance()
                return Directive(
                    location=location,
                    name=name,
                    arguments=[[filename_tok]],
                    label=label
                )
            raise AssemblySyntaxError(
                "INCBIN requires a filename string",
                location
            )

        if name == "END":
            # Optional start address
            if not self._check(TokenType.NEWLINE, TokenType.EOF):
                args = [self._collect_expression_tokens()]
            else:
                args = []
            return Directive(location=location, name=name, arguments=args, label=label)

        if name in ("LIST", "NOLIST", "PAGE"):
            return Directive(location=location, name=name, arguments=[], label=label)

        if name == "TITLE":
            if self._check(TokenType.STRING):
                title_tok = self._advance()
                return Directive(
                    location=location,
                    name=name,
                    arguments=[[title_tok]],
                    label=label
                )
            raise AssemblySyntaxError("TITLE requires a string", location)

        if name == "MACRO":
            return self._parse_macro_definition(location)

        if name == "ENDM":
            raise AssemblySyntaxError("ENDM without matching MACRO", location)

        if name == "SECTION":
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name=name, arguments=args, label=label)

        if name == "MODEL":
            # .MODEL directive - expects a model name identifier (CM, XP, LA, LZ, LZ64)
            args = [self._collect_expression_tokens()]
            return Directive(location=location, name=name, arguments=args, label=label)

        # Generic directive handling
        args = self._parse_comma_separated_args() if not self._check(TokenType.NEWLINE, TokenType.EOF) else []
        return Directive(location=location, name=name, arguments=args, label=label)

    def _parse_equals_directive(self, label: Optional[str]) -> Directive:
        """Parse symbol = value syntax."""
        # Get symbol name
        if label is None:
            name_token = self._advance()
            label = name_token.value
        location = self._current().location

        self._expect(TokenType.EQUALS, "expected '='")

        args = [self._collect_expression_tokens()]
        return Directive(location=location, name="EQU", arguments=args, label=label)

    def _parse_comma_separated_args(self) -> list[list[Token]]:
        """Parse comma-separated arguments."""
        args: list[list[Token]] = []
        current_arg: list[Token] = []
        paren_depth = 0

        while not self._check(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()

            if tok.type == TokenType.COMMA and paren_depth == 0:
                if current_arg:
                    args.append(current_arg)
                    current_arg = []
                self._advance()  # consume comma
                continue

            if tok.type == TokenType.LPAREN:
                paren_depth += 1
            elif tok.type == TokenType.RPAREN:
                paren_depth -= 1

            current_arg.append(self._advance())

        if current_arg:
            args.append(current_arg)

        return args

    # =========================================================================
    # Macro Parsing
    # =========================================================================

    def _parse_macro_definition(self, location: SourceLocation) -> MacroDef:
        """Parse a macro definition."""
        # Get macro name
        if not self._check(TokenType.IDENTIFIER):
            raise AssemblySyntaxError("expected macro name", self._current().location)

        name_token = self._advance()
        name = name_token.value.upper()

        # Parse optional parameters
        parameters: list[str] = []
        while self._check(TokenType.IDENTIFIER, TokenType.COMMA):
            if self._match(TokenType.COMMA):
                continue
            param_token = self._advance()
            parameters.append(param_token.value)

        self._match(TokenType.NEWLINE)

        # Parse macro body until ENDM
        body: list[Statement] = []
        while not self._at_end():
            if self._check(TokenType.NEWLINE):
                self._advance()
                continue

            if self._check(TokenType.IDENTIFIER):
                if self._current().value.upper() == "ENDM":
                    self._advance()
                    break

            stmt = self._parse_line()
            if stmt:
                if isinstance(stmt, list):
                    body.extend(stmt)
                else:
                    body.append(stmt)

        macro_def = MacroDef(
            location=location,
            name=name,
            parameters=parameters,
            body=body
        )
        self._macros[name] = macro_def
        return macro_def

    def _parse_macro_call(self) -> MacroCall:
        """Parse a macro invocation."""
        name_token = self._advance()
        name = name_token.value.upper()
        location = name_token.location

        # Parse arguments
        arguments = self._parse_comma_separated_args()

        return MacroCall(location=location, name=name, arguments=arguments)

    # =========================================================================
    # Conditional Assembly
    # =========================================================================

    def _parse_conditional(self) -> ConditionalBlock:
        """Parse conditional assembly (#IF, #IFDEF, #IFNDEF)."""
        self._advance()  # consume #
        location = self._current().location

        if not self._check(TokenType.IDENTIFIER):
            raise AssemblySyntaxError(
                "expected conditional directive after '#'",
                location
            )

        directive = self._advance().value.upper()

        if directive not in ("IF", "IFDEF", "IFNDEF", "ELSE", "ELIF", "ENDIF"):
            raise AssemblySyntaxError(
                f"unknown conditional directive '#{directive}'",
                location
            )

        if directive == "ENDIF":
            raise AssemblySyntaxError("ENDIF without matching IF", location)

        if directive == "ELSE":
            raise AssemblySyntaxError("ELSE without matching IF", location)

        if directive == "ELIF":
            raise AssemblySyntaxError("ELIF without matching IF", location)

        # Parse condition
        condition_tokens = self._collect_expression_tokens()
        self._match(TokenType.NEWLINE)

        # Parse if-body
        if_body: list[Statement] = []
        else_body: list[Statement] = []
        in_else = False

        while not self._at_end():
            if self._check(TokenType.NEWLINE):
                self._advance()
                continue

            # Check for nested conditional directives
            if self._check(TokenType.HASH):
                # Look ahead
                if self._peek(1).type == TokenType.IDENTIFIER:
                    next_dir = self._peek(1).value.upper()

                    if next_dir == "ENDIF":
                        self._advance()  # #
                        self._advance()  # ENDIF
                        self._match(TokenType.NEWLINE)
                        break

                    if next_dir == "ELSE":
                        self._advance()  # #
                        self._advance()  # ELSE
                        self._match(TokenType.NEWLINE)
                        in_else = True
                        continue

                    if next_dir == "ELIF":
                        # Handle ELIF as nested IF in else branch
                        self._advance()  # #
                        self._advance()  # ELIF
                        nested = ConditionalBlock(
                            location=self._location(),
                            condition_type="IF",
                            condition_tokens=self._collect_expression_tokens()
                        )
                        self._match(TokenType.NEWLINE)
                        # Continue parsing as nested conditional
                        # For simplicity, treat rest as else body
                        in_else = True
                        else_body.append(nested)
                        continue

                    # Nested conditional
                    nested = self._parse_conditional()
                    if in_else:
                        else_body.append(nested)
                    else:
                        if_body.append(nested)
                    continue

            # Parse regular statement
            stmt = self._parse_line()
            if stmt:
                target = else_body if in_else else if_body
                if isinstance(stmt, list):
                    target.extend(stmt)
                else:
                    target.append(stmt)

        return ConditionalBlock(
            location=location,
            condition_type=directive,
            condition_tokens=condition_tokens,
            if_body=if_body,
            else_body=else_body
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_source(
    source: str,
    filename: str = "<input>",
    include_paths: list[str] | None = None
) -> list[Statement]:
    """
    Convenience function to parse assembly source.

    This function pre-processes include files to collect macro definitions
    before parsing the main file. This ensures macros defined in included
    files are available when parsing the main source.

    Args:
        source: Assembly source text
        filename: Source filename for error messages
        include_paths: List of directories to search for include files

    Returns:
        List of parsed statements
    """
    from pathlib import Path

    # Collect macros from include files first
    macros = _collect_macros_from_includes(
        source, filename, include_paths or [], set()
    )

    # Now parse the main source with all macros available
    lexer = Lexer(source, filename)
    tokens = list(lexer.tokenize())
    parser = Parser(tokens, filename, macros=macros)
    return parser.parse()


def _collect_macros_from_includes(
    source: str,
    filename: str,
    include_paths: list[str],
    processed: set[str]
) -> dict[str, MacroDef]:
    """
    Recursively collect macro definitions from include files.

    This pre-processes the source to find INCLUDE directives and
    extracts macro definitions from included files. This is necessary
    because macros must be known during parsing of the main file.

    Args:
        source: Source code to scan
        filename: Source filename for path resolution
        include_paths: Directories to search for includes
        processed: Set of already processed files (for circular detection)

    Returns:
        Dictionary of macro name -> MacroDef
    """
    from pathlib import Path

    macros: dict[str, MacroDef] = {}

    # Quick scan for INCLUDE directives
    # We do a simple token-based scan, not a full parse
    lexer = Lexer(source, filename)
    tokens = list(lexer.tokenize())

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Look for INCLUDE directive
        if tok.type == TokenType.IDENTIFIER and tok.value.upper() == "INCLUDE":
            # Next token should be the filename
            if i + 1 < len(tokens) and tokens[i + 1].type == TokenType.STRING:
                include_name = tokens[i + 1].value

                # Resolve include path
                include_path = _resolve_include(
                    include_name, filename, include_paths
                )

                if include_path and str(include_path) not in processed:
                    processed.add(str(include_path))

                    # Recursively collect macros from included file
                    try:
                        include_source = include_path.read_text(encoding='utf-8')
                        child_macros = _collect_macros_from_includes(
                            include_source,
                            str(include_path),
                            include_paths,
                            processed
                        )
                        macros.update(child_macros)

                        # Also parse this file for its own macro definitions
                        child_lexer = Lexer(include_source, str(include_path))
                        child_tokens = list(child_lexer.tokenize())
                        child_parser = Parser(
                            child_tokens, str(include_path), macros=macros
                        )
                        child_statements = child_parser.parse()

                        # Extract macro definitions
                        for stmt in child_statements:
                            if isinstance(stmt, MacroDef):
                                macros[stmt.name] = stmt

                    except Exception:
                        pass  # Ignore errors during pre-processing

        # Also look for MACRO definitions in the current file
        if tok.type == TokenType.IDENTIFIER and tok.value.upper() == "MACRO":
            # Parse this macro definition
            # We need to find MACRO name, params, body, ENDM
            if i + 1 < len(tokens) and tokens[i + 1].type == TokenType.IDENTIFIER:
                macro_name = tokens[i + 1].value.upper()

                # Find the end of this macro (ENDM)
                j = i + 2
                body_start = j
                while j < len(tokens):
                    if (tokens[j].type == TokenType.IDENTIFIER and
                            tokens[j].value.upper() == "ENDM"):
                        break
                    j += 1

                # Skip past this macro in our scan
                i = j

        i += 1

    return macros


def _resolve_include(
    filename: str,
    current_file: str,
    include_paths: list[str]
) -> "Path | None":
    """Resolve an include filename to a full path."""
    from pathlib import Path

    # Try relative to current file
    if current_file != "<input>":
        current_dir = Path(current_file).parent
        candidate = current_dir / filename
        if candidate.exists():
            return candidate

    # Try include paths
    for path_str in include_paths:
        candidate = Path(path_str) / filename
        if candidate.exists():
            return candidate

    return None
