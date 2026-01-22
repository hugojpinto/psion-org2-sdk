"""
HD6303 Assembly Language Lexer
==============================

This module implements a lexer (tokenizer) for HD6303 assembly language.
It converts source text into a stream of tokens that the parser can process.

Token Types
-----------
- IDENTIFIER: Labels, mnemonics, directives, symbol names
- NUMBER: Decimal, hex ($FF/0xFF), binary (%1010/0b1010), octal (@177/0o177)
- STRING: Double-quoted strings ("hello")
- CHAR: Single-quoted character ('A')
- Operators: +, -, *, /, %, &, |, ^, ~, <<, >>, etc.
- Delimiters: ,, :, #, (, )
- NEWLINE: End of line
- EOF: End of file

Number Formats
--------------
The lexer supports multiple number formats common in assembly:

| Format      | Prefix   | Example  | Value |
|-------------|----------|----------|-------|
| Decimal     | (none)   | 123      | 123   |
| Hexadecimal | $ or 0x  | $7F, 0x7F| 127   |
| Binary      | % or 0b  | %1010    | 10    |
| Octal       | @ or 0o  | @177     | 127   |
| Character   | '        | 'A'      | 65    |

Comments
--------
Two comment styles are supported:
- Semicolon: "; comment" (anywhere on line)
- Asterisk: "* comment" (only at start of line)

Example
-------
>>> from psion_sdk.assembler.lexer import Lexer
>>> source = "start: LDAA #$41  ; load 'A'"
>>> lexer = Lexer(source, "example.asm")
>>> for token in lexer.tokenize():
...     print(token)
Token(IDENTIFIER, 'start', 1, 1)
Token(COLON, ':', 1, 6)
Token(IDENTIFIER, 'LDAA', 1, 8)
Token(HASH, '#', 1, 13)
Token(NUMBER, 65, 1, 14)
Token(NEWLINE, None, 1, 25)
Token(EOF, None, 1, 25)
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Optional
import string

from psion_sdk.errors import AssemblySyntaxError, SourceLocation


# =============================================================================
# Token Type Enumeration
# =============================================================================

class TokenType(Enum):
    """
    Token types for the HD6303 assembly language.

    Each token type represents a category of lexical element that can
    appear in assembly source code.
    """

    # Structural tokens
    NEWLINE = auto()    # End of line (significant for statement boundaries)
    EOF = auto()        # End of file

    # Values
    IDENTIFIER = auto()  # Labels, mnemonics, symbols
    NUMBER = auto()      # Numeric literals (all formats)
    STRING = auto()      # Double-quoted string "..."
    CHAR = auto()        # Single-quoted character 'X'

    # Arithmetic operators
    PLUS = auto()        # +
    MINUS = auto()       # -
    STAR = auto()        # * (multiply or current PC)
    SLASH = auto()       # /
    PERCENT = auto()     # %

    # Bitwise operators
    AMPERSAND = auto()   # &
    PIPE = auto()        # |
    CARET = auto()       # ^
    TILDE = auto()       # ~
    LSHIFT = auto()      # <<
    RSHIFT = auto()      # >>

    # Comparison operators (for conditional assembly expressions)
    LT = auto()          # <
    GT = auto()          # >
    LE = auto()          # <=
    GE = auto()          # >=
    EQ = auto()          # == or =
    NE = auto()          # != or <>

    # Delimiters
    COMMA = auto()       # ,
    COLON = auto()       # :
    HASH = auto()        # # (immediate mode indicator)
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    DOLLAR = auto()      # $ (alone, means current PC)
    EQUALS = auto()      # = (for EQU shorthand)

    # Macro-related
    MACRO_PARAM = auto()  # \name (macro parameter reference)

    # Directives (detected as IDENTIFIER, then categorized)
    # Note: Directives are initially tokenized as IDENTIFIER and
    # the parser determines if they are directives based on context


# =============================================================================
# Token Data Class
# =============================================================================

@dataclass(frozen=True)
class Token:
    """
    Represents a single token from the source code.

    This is an immutable data class that stores the token type, value,
    and location information for error reporting.

    Attributes:
        type: The TokenType classification
        value: The token value (string for identifiers, int for numbers, etc.)
        line: Line number in source (1-indexed)
        column: Column number in source (1-indexed)
        filename: Name of the source file
    """
    type: TokenType
    value: str | int | None
    line: int
    column: int
    filename: str

    def __repr__(self) -> str:
        if self.value is not None:
            if isinstance(self.value, int):
                return f"Token({self.type.name}, ${self.value:X}, {self.line}:{self.column})"
            return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
        return f"Token({self.type.name}, {self.line}:{self.column})"

    @property
    def location(self) -> SourceLocation:
        """Return a SourceLocation for error reporting."""
        return SourceLocation(self.filename, self.line, self.column)


# =============================================================================
# Lexer Implementation
# =============================================================================

class Lexer:
    """
    Tokenizes HD6303 assembly source code.

    The lexer handles all the syntactic elements of assembly language:
    - Multi-format numbers ($hex, %binary, @octal, decimal)
    - Character literals ('A')
    - String literals ("text")
    - Comments (; and * at line start)
    - All operators and delimiters
    - Escape sequences in strings

    The lexer is designed to be fault-tolerant and provide helpful
    error messages with exact source locations.

    Usage:
        lexer = Lexer(source_text, filename)
        tokens = list(lexer.tokenize())

    Attributes:
        source: The source code being tokenized
        filename: Name of the source file (for error reporting)
    """

    # Characters that can start an identifier
    IDENT_START = string.ascii_letters + "_"

    # Characters that can continue an identifier
    IDENT_CHARS = string.ascii_letters + string.digits + "_"

    # Single-character operators
    SINGLE_CHAR_TOKENS = {
        "+": TokenType.PLUS,
        "-": TokenType.MINUS,
        "*": TokenType.STAR,
        "/": TokenType.SLASH,
        "%": TokenType.PERCENT,
        "&": TokenType.AMPERSAND,
        "|": TokenType.PIPE,
        "^": TokenType.CARET,
        "~": TokenType.TILDE,
        ",": TokenType.COMMA,
        ":": TokenType.COLON,
        "#": TokenType.HASH,
        "(": TokenType.LPAREN,
        ")": TokenType.RPAREN,
        "=": TokenType.EQUALS,
    }

    # Escape sequences in strings
    ESCAPE_SEQUENCES = {
        "n": "\n",      # Newline
        "r": "\r",      # Carriage return
        "t": "\t",      # Tab
        "\\": "\\",     # Backslash
        '"': '"',       # Double quote
        "'": "'",       # Single quote
        "0": "\0",      # Null
    }

    def __init__(self, source: str, filename: str = "<input>", line_number: int = 1):
        """
        Initialize the lexer with source code.

        Args:
            source: The assembly source code to tokenize
            filename: Name of the source file (for error messages)
            line_number: Starting line number (default 1, useful for include files)
        """
        self.source = source
        self.filename = filename

        # Current position in source
        self._pos = 0
        self._line = line_number  # Support starting from arbitrary line number
        self._column = 1

        # Track if we're at the start of a line (for * comments)
        self._at_line_start = True

        # Current line text for error reporting
        self._line_start_pos = 0

    def tokenize(self) -> Iterator[Token]:
        """
        Generate tokens from the source code.

        Yields:
            Token objects representing each lexical element

        Raises:
            AssemblySyntaxError: If invalid syntax is encountered
        """
        while not self._at_end():
            # Skip whitespace (but not newlines)
            if self._skip_whitespace():
                continue

            # Check for comments
            if self._skip_comment():
                continue

            # Get the next token
            token = self._scan_token()
            if token is not None:
                yield token

        # Always end with EOF token
        yield self._make_token(TokenType.EOF, None)

    # =========================================================================
    # Character Access Methods
    # =========================================================================

    def _at_end(self) -> bool:
        """Check if we've reached the end of source."""
        return self._pos >= len(self.source)

    def _peek(self, offset: int = 0) -> str:
        """
        Look at character at current position + offset without advancing.

        Returns empty string if past end of source.
        """
        pos = self._pos + offset
        if pos >= len(self.source):
            return ""
        return self.source[pos]

    def _advance(self) -> str:
        """
        Consume and return the current character, advancing position.

        Updates line and column tracking.
        """
        if self._at_end():
            return ""

        char = self.source[self._pos]
        self._pos += 1

        if char == "\n":
            self._line += 1
            self._column = 1
            self._at_line_start = True
            self._line_start_pos = self._pos
        else:
            self._column += 1
            if char not in " \t":
                self._at_line_start = False

        return char

    def _match(self, expected: str) -> bool:
        """
        Consume next character if it matches expected.

        Args:
            expected: The character to match

        Returns:
            True if matched and consumed, False otherwise
        """
        if self._peek() == expected:
            self._advance()
            return True
        return False

    # =========================================================================
    # Token Creation
    # =========================================================================

    def _make_token(
        self,
        token_type: TokenType,
        value: str | int | None,
        start_line: Optional[int] = None,
        start_column: Optional[int] = None,
    ) -> Token:
        """
        Create a token with current or specified position.

        Args:
            token_type: The type of token
            value: The token value
            start_line: Override line number (for multi-char tokens)
            start_column: Override column number
        """
        return Token(
            type=token_type,
            value=value,
            line=start_line or self._line,
            column=start_column or self._column,
            filename=self.filename,
        )

    def _error(self, message: str) -> AssemblySyntaxError:
        """
        Create a syntax error with current location.

        Args:
            message: Error description

        Returns:
            AssemblySyntaxError with location information
        """
        location = SourceLocation(self.filename, self._line, self._column)

        # Get the current line text for context
        line_end = self.source.find("\n", self._line_start_pos)
        if line_end == -1:
            line_end = len(self.source)
        source_line = self.source[self._line_start_pos:line_end]

        return AssemblySyntaxError(message, location, source_line=source_line)

    # =========================================================================
    # Whitespace and Comment Handling
    # =========================================================================

    def _skip_whitespace(self) -> bool:
        """
        Skip whitespace characters (space, tab) but not newlines.

        Returns:
            True if any whitespace was skipped
        """
        skipped = False
        # Note: Must check for non-empty string first because '' in ' \t' is True in Python
        while self._peek() and self._peek() in " \t":
            self._advance()
            skipped = True
        return skipped

    def _skip_comment(self) -> bool:
        """
        Skip comment to end of line.

        Handles two comment styles:
        - Semicolon (;) anywhere on line
        - Asterisk (*) only at start of line

        Returns:
            True if a comment was skipped
        """
        char = self._peek()

        # Semicolon comment - can appear anywhere
        if char == ";":
            while not self._at_end() and self._peek() != "\n":
                self._advance()
            return True

        # Asterisk comment - only at start of line
        if char == "*" and self._at_line_start:
            while not self._at_end() and self._peek() != "\n":
                self._advance()
            return True

        return False

    # =========================================================================
    # Token Scanning
    # =========================================================================

    def _scan_token(self) -> Optional[Token]:
        """
        Scan the next token from source.

        Returns:
            The next Token, or None if nothing to scan
        """
        start_line = self._line
        start_column = self._column

        char = self._peek()

        # Newline - significant for statement boundaries
        if char == "\n":
            self._advance()
            return self._make_token(TokenType.NEWLINE, None, start_line, start_column)

        # Identifiers (labels, mnemonics, directives)
        if char in self.IDENT_START:
            return self._scan_identifier(start_line, start_column)

        # Numbers
        if char.isdigit():
            return self._scan_decimal_number(start_line, start_column)

        # Hexadecimal with $ prefix
        if char == "$":
            # Could be hex number or current PC symbol
            # Note: Must check _peek(1) is non-empty because '' in string.hexdigits is True
            next_char = self._peek(1)
            if next_char and next_char in string.hexdigits:
                return self._scan_hex_number(start_line, start_column)
            else:
                # $ alone means current program counter
                self._advance()
                return self._make_token(TokenType.DOLLAR, "$", start_line, start_column)

        # Binary with % prefix (only if followed by 0 or 1)
        # Note: Must check _peek(1) is non-empty because '' in "01" is True
        next_char = self._peek(1) if char == "%" else ""
        if char == "%" and next_char and next_char in "01":
            return self._scan_binary_number(start_line, start_column)

        # Octal with @ prefix (only if followed by digit)
        # Note: Must check BEFORE local labels since @ is also used for local labels
        if char == "@" and self._peek(1).isdigit():
            return self._scan_octal_number(start_line, start_column)

        # Local labels starting with . or @ (after checking for octal)
        if char in ".@":
            return self._scan_local_label(start_line, start_column)

        # String literal
        if char == '"':
            return self._scan_string(start_line, start_column)

        # Character literal
        if char == "'":
            return self._scan_char(start_line, start_column)

        # Macro parameter reference (\name)
        if char == "\\":
            return self._scan_macro_param(start_line, start_column)

        # Two-character operators
        if char == "<":
            self._advance()
            if self._match("<"):
                return self._make_token(TokenType.LSHIFT, "<<", start_line, start_column)
            if self._match("="):
                return self._make_token(TokenType.LE, "<=", start_line, start_column)
            if self._match(">"):
                return self._make_token(TokenType.NE, "<>", start_line, start_column)
            return self._make_token(TokenType.LT, "<", start_line, start_column)

        if char == ">":
            self._advance()
            if self._match(">"):
                return self._make_token(TokenType.RSHIFT, ">>", start_line, start_column)
            if self._match("="):
                return self._make_token(TokenType.GE, ">=", start_line, start_column)
            return self._make_token(TokenType.GT, ">", start_line, start_column)

        if char == "!":
            self._advance()
            if self._match("="):
                return self._make_token(TokenType.NE, "!=", start_line, start_column)
            # Lone ! is not valid
            raise self._error("unexpected character '!'")

        # Single-character tokens
        if char in self.SINGLE_CHAR_TOKENS:
            self._advance()
            return self._make_token(
                self.SINGLE_CHAR_TOKENS[char],
                char,
                start_line,
                start_column
            )

        # Handle == (equality)
        if char == "=":
            self._advance()
            if self._match("="):
                return self._make_token(TokenType.EQ, "==", start_line, start_column)
            return self._make_token(TokenType.EQUALS, "=", start_line, start_column)

        # Unknown character
        self._advance()
        raise self._error(f"unexpected character '{char}'")

    def _scan_identifier(self, start_line: int, start_column: int) -> Token:
        """
        Scan an identifier (label, mnemonic, directive, or symbol).

        Identifiers start with a letter or underscore and can contain
        letters, digits, and underscores.
        """
        chars = []
        # Note: Must check for non-empty string first because '' in 'string' is True in Python
        while self._peek() and self._peek() in self.IDENT_CHARS:
            chars.append(self._advance())

        name = "".join(chars)
        return self._make_token(TokenType.IDENTIFIER, name, start_line, start_column)

    def _scan_local_label(self, start_line: int, start_column: int) -> Token:
        """
        Scan a local label starting with . or @.

        Local labels are scoped to the enclosing global label and
        can be reused in different scopes.
        """
        chars = [self._advance()]  # Consume . or @
        # Note: Must check for non-empty string first because '' in 'string' is True in Python
        while self._peek() and self._peek() in self.IDENT_CHARS:
            chars.append(self._advance())

        if len(chars) == 1:
            raise self._error(f"expected identifier after '{chars[0]}'")

        name = "".join(chars)
        return self._make_token(TokenType.IDENTIFIER, name, start_line, start_column)

    def _scan_macro_param(self, start_line: int, start_column: int) -> Token:
        """
        Scan a macro parameter reference (\\name) or unique label suffix (\\@).

        Macro parameters are prefixed with backslash and reference
        the formal parameters defined in a MACRO directive.

        The special form \\@ is used for generating unique labels within
        macros. During macro expansion, \\@ is replaced with a unique
        numeric suffix to prevent label conflicts when a macro is used
        multiple times.
        """
        self._advance()  # consume backslash

        # Check for \@ (unique label suffix)
        if self._peek() == "@":
            self._advance()  # consume @
            return self._make_token(TokenType.MACRO_PARAM, "@", start_line, start_column)

        # Collect parameter name
        chars = []
        while self._peek() and self._peek() in self.IDENT_CHARS:
            chars.append(self._advance())

        if not chars:
            raise self._error("expected parameter name after '\\'")

        name = "".join(chars)
        return self._make_token(TokenType.MACRO_PARAM, name, start_line, start_column)

    def _scan_decimal_number(self, start_line: int, start_column: int) -> Token:
        """
        Scan a decimal number.

        Also handles 0x (hex) and 0b (binary) and 0o (octal) prefixes.
        """
        # Check for 0x, 0b, 0o prefixes
        if self._peek() == "0":
            next_char = self._peek(1).lower()
            if next_char == "x":
                self._advance()  # consume 0
                self._advance()  # consume x
                return self._scan_hex_digits(start_line, start_column)
            if next_char == "b":
                self._advance()  # consume 0
                self._advance()  # consume b
                return self._scan_binary_digits(start_line, start_column)
            if next_char == "o":
                self._advance()  # consume 0
                self._advance()  # consume o
                return self._scan_octal_digits(start_line, start_column)

        # Regular decimal number
        chars = []
        while self._peek().isdigit():
            chars.append(self._advance())

        value = int("".join(chars))
        return self._make_token(TokenType.NUMBER, value, start_line, start_column)

    def _scan_hex_number(self, start_line: int, start_column: int) -> Token:
        """Scan hexadecimal number with $ prefix."""
        self._advance()  # consume $
        return self._scan_hex_digits(start_line, start_column)

    def _scan_hex_digits(self, start_line: int, start_column: int) -> Token:
        """Scan hexadecimal digits after prefix."""
        chars = []
        # Note: Must check for non-empty string first because '' in string.hexdigits is True
        while self._peek() and self._peek() in string.hexdigits:
            chars.append(self._advance())

        if not chars:
            raise self._error("expected hexadecimal digits")

        value = int("".join(chars), 16)
        return self._make_token(TokenType.NUMBER, value, start_line, start_column)

    def _scan_binary_number(self, start_line: int, start_column: int) -> Token:
        """Scan binary number with % prefix."""
        self._advance()  # consume %
        return self._scan_binary_digits(start_line, start_column)

    def _scan_binary_digits(self, start_line: int, start_column: int) -> Token:
        """Scan binary digits after prefix."""
        chars = []
        # Note: Must check for non-empty string first because '' in "01" is True
        while self._peek() and self._peek() in "01":
            chars.append(self._advance())

        if not chars:
            raise self._error("expected binary digits")

        value = int("".join(chars), 2)
        return self._make_token(TokenType.NUMBER, value, start_line, start_column)

    def _scan_octal_number(self, start_line: int, start_column: int) -> Token:
        """Scan octal number with @ prefix."""
        self._advance()  # consume @
        return self._scan_octal_digits(start_line, start_column)

    def _scan_octal_digits(self, start_line: int, start_column: int) -> Token:
        """Scan octal digits after prefix."""
        chars = []
        # Note: Must check for non-empty string first because '' in "01234567" is True
        while self._peek() and self._peek() in "01234567":
            chars.append(self._advance())

        if not chars:
            raise self._error("expected octal digits")

        value = int("".join(chars), 8)
        return self._make_token(TokenType.NUMBER, value, start_line, start_column)

    def _scan_string(self, start_line: int, start_column: int) -> Token:
        """
        Scan a double-quoted string literal.

        Supports escape sequences: \\n, \\r, \\t, \\\\, \", \\xNN
        """
        self._advance()  # consume opening "

        chars = []
        while not self._at_end():
            char = self._peek()

            if char == '"':
                self._advance()  # consume closing "
                return self._make_token(
                    TokenType.STRING,
                    "".join(chars),
                    start_line,
                    start_column
                )

            if char == "\n":
                raise self._error("unterminated string literal")

            if char == "\\":
                self._advance()  # consume backslash
                escaped = self._scan_escape_sequence()
                chars.append(escaped)
            else:
                chars.append(self._advance())

        raise self._error("unterminated string literal")

    def _scan_char(self, start_line: int, start_column: int) -> Token:
        """
        Scan a single-quoted character literal.

        Returns the ASCII value of the character as a NUMBER token.
        """
        self._advance()  # consume opening '

        if self._at_end() or self._peek() == "\n":
            raise self._error("unterminated character literal")

        if self._peek() == "\\":
            self._advance()  # consume backslash
            char = self._scan_escape_sequence()
        else:
            char = self._advance()

        if self._peek() != "'":
            raise self._error("expected closing quote for character literal")
        self._advance()  # consume closing '

        value = ord(char)
        return self._make_token(TokenType.NUMBER, value, start_line, start_column)

    def _scan_escape_sequence(self) -> str:
        """
        Scan an escape sequence after backslash.

        Returns:
            The character represented by the escape sequence
        """
        if self._at_end():
            raise self._error("unexpected end of input in escape sequence")

        char = self._advance()

        # Simple escape sequences
        if char in self.ESCAPE_SEQUENCES:
            return self.ESCAPE_SEQUENCES[char]

        # Hex escape: \xNN
        if char == "x":
            hex_chars = []
            for _ in range(2):
                if self._peek() in string.hexdigits:
                    hex_chars.append(self._advance())
                else:
                    break

            if not hex_chars:
                raise self._error("expected hexadecimal digits after \\x")

            value = int("".join(hex_chars), 16)
            return chr(value)

        # Unknown escape - treat as literal
        return char

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_current_line(self) -> str:
        """
        Get the current line of source text.

        Useful for error reporting.
        """
        line_end = self.source.find("\n", self._line_start_pos)
        if line_end == -1:
            line_end = len(self.source)
        return self.source[self._line_start_pos:line_end]
