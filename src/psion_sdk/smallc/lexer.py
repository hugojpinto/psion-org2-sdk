"""
Small-C Lexer (Tokenizer)
=========================

This module implements a lexer for the Small-C subset of C.
It converts source text into a stream of tokens for the parser.

Token Categories
----------------
- Keywords: int, char, void, if, while, for, return, etc.
- Identifiers: variable and function names
- Numbers: decimal, hexadecimal (0x), octal (0), binary (0b)
- Strings: "double quoted"
- Characters: 'single quoted'
- Operators: +, -, *, /, ==, !=, &&, ||, <<, >>, etc.
- Delimiters: (, ), {, }, [, ], ;, ,

Number Formats
--------------
| Format      | Prefix  | Example   | Value |
|-------------|---------|-----------|-------|
| Decimal     | (none)  | 123       | 123   |
| Hexadecimal | 0x/0X   | 0x7F      | 127   |
| Octal       | 0       | 0177      | 127   |
| Binary      | 0b/0B   | 0b1010    | 10    |

Comments
--------
- Single-line: // comment
- Multi-line: /* comment */

Escape Sequences
----------------
\\n (newline), \\r (return), \\t (tab), \\\\ (backslash),
\\' (quote), \\" (double quote), \\0 (null), \\xNN (hex)

Example Usage
-------------
>>> from psion_sdk.smallc.lexer import CLexer
>>> source = 'int main() { return 42; }'
>>> lexer = CLexer(source, "test.c")
>>> for token in lexer.tokenize():
...     print(token)
Token(INT, 'int', 1:1)
Token(IDENTIFIER, 'main', 1:5)
Token(LPAREN, '(', 1:9)
Token(RPAREN, ')', 1:10)
Token(LBRACE, '{', 1:12)
Token(RETURN, 'return', 1:14)
Token(NUMBER, 42, 1:21)
Token(SEMICOLON, ';', 1:23)
Token(RBRACE, '}', 1:25)
Token(EOF, None, 1:26)
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Optional
import string

from psion_sdk.errors import SourceLocation
from psion_sdk.smallc.errors import (
    CSyntaxError,
    UnterminatedStringError,
    InvalidCharacterError,
)


# =============================================================================
# Token Type Enumeration
# =============================================================================

class CTokenType(Enum):
    """
    Token types for the Small-C language.

    Each token type represents a category of lexical element that can
    appear in C source code. Keywords are distinguished from identifiers
    to simplify parsing.
    """

    # === Structural Tokens ===
    EOF = auto()            # End of file
    NEWLINE = auto()        # Used internally for line tracking

    # === Identifiers and Literals ===
    IDENTIFIER = auto()     # Variable/function names
    NUMBER = auto()         # Integer literals (all formats)
    STRING = auto()         # String literals "..."
    CHAR_LITERAL = auto()   # Character literals '...'

    # === Keywords - Type Specifiers ===
    VOID = auto()           # void
    CHAR = auto()           # char
    INT = auto()            # int
    UNSIGNED = auto()       # unsigned
    SIGNED = auto()         # signed

    # === Keywords - Control Flow ===
    IF = auto()             # if
    ELSE = auto()           # else
    WHILE = auto()          # while
    FOR = auto()            # for
    DO = auto()             # do
    SWITCH = auto()         # switch
    CASE = auto()           # case
    DEFAULT = auto()        # default
    BREAK = auto()          # break
    CONTINUE = auto()       # continue
    RETURN = auto()         # return
    GOTO = auto()           # goto

    # === Keywords - Other ===
    SIZEOF = auto()         # sizeof (limited support)

    # === Arithmetic Operators ===
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # * (multiply or dereference)
    SLASH = auto()          # /
    PERCENT = auto()        # %

    # === Increment/Decrement ===
    INCREMENT = auto()      # ++
    DECREMENT = auto()      # --

    # === Comparison Operators ===
    EQ = auto()             # ==
    NE = auto()             # !=
    LT = auto()             # <
    GT = auto()             # >
    LE = auto()             # <=
    GE = auto()             # >=

    # === Logical Operators ===
    AND = auto()            # &&
    OR = auto()             # ||
    NOT = auto()            # !

    # === Bitwise Operators ===
    AMPERSAND = auto()      # & (bitwise AND or address-of)
    PIPE = auto()           # |
    CARET = auto()          # ^
    TILDE = auto()          # ~
    LSHIFT = auto()         # <<
    RSHIFT = auto()         # >>

    # === Assignment Operators ===
    ASSIGN = auto()         # =
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=
    STAR_ASSIGN = auto()    # *=
    SLASH_ASSIGN = auto()   # /=
    PERCENT_ASSIGN = auto() # %=
    AND_ASSIGN = auto()     # &=
    OR_ASSIGN = auto()      # |=
    XOR_ASSIGN = auto()     # ^=
    LSHIFT_ASSIGN = auto()  # <<=
    RSHIFT_ASSIGN = auto()  # >>=

    # === Delimiters ===
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    SEMICOLON = auto()      # ;
    COMMA = auto()          # ,
    COLON = auto()          # :
    QUESTION = auto()       # ? (ternary operator)

    # === Preprocessor (handled specially) ===
    HASH = auto()           # # (preprocessor directive start)


# =============================================================================
# Keyword Mapping
# =============================================================================

# Map keyword strings to their token types
KEYWORDS: dict[str, CTokenType] = {
    # Type specifiers
    "void": CTokenType.VOID,
    "char": CTokenType.CHAR,
    "int": CTokenType.INT,
    "unsigned": CTokenType.UNSIGNED,
    "signed": CTokenType.SIGNED,

    # Control flow
    "if": CTokenType.IF,
    "else": CTokenType.ELSE,
    "while": CTokenType.WHILE,
    "for": CTokenType.FOR,
    "do": CTokenType.DO,
    "switch": CTokenType.SWITCH,
    "case": CTokenType.CASE,
    "default": CTokenType.DEFAULT,
    "break": CTokenType.BREAK,
    "continue": CTokenType.CONTINUE,
    "return": CTokenType.RETURN,
    "goto": CTokenType.GOTO,

    # Other
    "sizeof": CTokenType.SIZEOF,
}


# =============================================================================
# Token Data Class
# =============================================================================

@dataclass(frozen=True)
class CToken:
    """
    Represents a single token from C source code.

    This immutable class stores the token type, value, and location
    for error reporting. The location tracks the exact position in
    the source file where this token appears.

    Attributes:
        type: The CTokenType classification
        value: The token value (string for identifiers, int for numbers, etc.)
        line: Line number in source (1-indexed)
        column: Column number in source (1-indexed)
        filename: Name of the source file
    """
    type: CTokenType
    value: str | int | None
    line: int
    column: int
    filename: str

    def __repr__(self) -> str:
        """Format token for debugging output."""
        if self.value is not None:
            if isinstance(self.value, int):
                return f"Token({self.type.name}, {self.value}, {self.line}:{self.column})"
            return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
        return f"Token({self.type.name}, {self.line}:{self.column})"

    @property
    def location(self) -> SourceLocation:
        """Return a SourceLocation for error reporting."""
        return SourceLocation(self.filename, self.line, self.column)

    def is_type_keyword(self) -> bool:
        """Return True if this token is a type keyword."""
        return self.type in (
            CTokenType.VOID,
            CTokenType.CHAR,
            CTokenType.INT,
            CTokenType.UNSIGNED,
            CTokenType.SIGNED,
        )

    def is_assignment_operator(self) -> bool:
        """Return True if this token is an assignment operator."""
        return self.type in (
            CTokenType.ASSIGN,
            CTokenType.PLUS_ASSIGN,
            CTokenType.MINUS_ASSIGN,
            CTokenType.STAR_ASSIGN,
            CTokenType.SLASH_ASSIGN,
            CTokenType.PERCENT_ASSIGN,
            CTokenType.AND_ASSIGN,
            CTokenType.OR_ASSIGN,
            CTokenType.XOR_ASSIGN,
            CTokenType.LSHIFT_ASSIGN,
            CTokenType.RSHIFT_ASSIGN,
        )


# =============================================================================
# Lexer Implementation
# =============================================================================

class CLexer:
    """
    Tokenizes Small-C source code.

    The lexer handles all syntactic elements of the C language subset:
    - Keywords and identifiers
    - Integer literals in multiple formats (decimal, hex, octal, binary)
    - String and character literals with escape sequences
    - All C operators including compound assignment
    - Comments (// and /* */)

    The lexer is designed to be fault-tolerant and provide helpful
    error messages with exact source locations.

    Usage:
        lexer = CLexer(source_text, filename)
        tokens = list(lexer.tokenize())

    Attributes:
        source: The source code being tokenized
        filename: Name of the source file (for error reporting)
    """

    # Characters that can start an identifier
    IDENT_START = string.ascii_letters + "_"

    # Characters that can continue an identifier
    IDENT_CHARS = string.ascii_letters + string.digits + "_"

    # Escape sequences in strings and characters
    ESCAPE_SEQUENCES = {
        "n": "\n",      # Newline
        "r": "\r",      # Carriage return
        "t": "\t",      # Tab
        "b": "\b",      # Backspace
        "f": "\f",      # Form feed
        "v": "\v",      # Vertical tab
        "\\": "\\",     # Backslash
        "'": "'",       # Single quote
        '"': '"',       # Double quote
        "0": "\0",      # Null
        "a": "\a",      # Bell/alert
    }

    def __init__(
        self,
        source: str,
        filename: str = "<input>",
        line_number: int = 1,
    ):
        """
        Initialize the lexer with source code.

        Args:
            source: The C source code to tokenize
            filename: Name of the source file (for error messages)
            line_number: Starting line number (useful for include files)
        """
        self.source = source
        self.filename = filename

        # Current position in source
        self._pos = 0
        self._line = line_number
        self._column = 1

        # Track line start position for error reporting
        self._line_start_pos = 0

    def tokenize(self) -> Iterator[CToken]:
        """
        Generate tokens from the source code.

        Yields:
            CToken objects representing each lexical element

        Raises:
            CSyntaxError: If invalid syntax is encountered
        """
        while not self._at_end():
            # Skip whitespace and comments
            self._skip_whitespace_and_comments()

            if self._at_end():
                break

            # Get the next token
            token = self._scan_token()
            if token is not None:
                yield token

        # Always end with EOF token
        yield self._make_token(CTokenType.EOF, None)

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

        Updates line and column tracking for error reporting.
        """
        if self._at_end():
            return ""

        char = self.source[self._pos]
        self._pos += 1

        if char == "\n":
            self._line += 1
            self._column = 1
            self._line_start_pos = self._pos
        else:
            self._column += 1

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
        token_type: CTokenType,
        value: str | int | None,
        start_line: Optional[int] = None,
        start_column: Optional[int] = None,
    ) -> CToken:
        """
        Create a token with current or specified position.

        Args:
            token_type: The type of token
            value: The token value
            start_line: Override line number (for multi-char tokens)
            start_column: Override column number
        """
        return CToken(
            type=token_type,
            value=value,
            line=start_line or self._line,
            column=start_column or self._column,
            filename=self.filename,
        )

    def _error(
        self,
        message: str,
        hint: Optional[str] = None,
    ) -> CSyntaxError:
        """
        Create a syntax error with current location.

        Args:
            message: Error description
            hint: Optional hint for fixing

        Returns:
            CSyntaxError with location information
        """
        location = SourceLocation(self.filename, self._line, self._column)

        # Get the current line text for context
        line_end = self.source.find("\n", self._line_start_pos)
        if line_end == -1:
            line_end = len(self.source)
        source_line = self.source[self._line_start_pos:line_end]

        return CSyntaxError(message, location, hint=hint, source_line=source_line)

    # =========================================================================
    # Whitespace and Comment Handling
    # =========================================================================

    def _skip_whitespace_and_comments(self) -> None:
        """Skip all whitespace and comments."""
        while not self._at_end():
            char = self._peek()

            # Skip whitespace
            if char in " \t\n\r":
                self._advance()
                continue

            # Single-line comment: //
            if char == "/" and self._peek(1) == "/":
                self._skip_single_line_comment()
                continue

            # Multi-line comment: /* */
            if char == "/" and self._peek(1) == "*":
                self._skip_multi_line_comment()
                continue

            # Not whitespace or comment
            break

    def _skip_single_line_comment(self) -> None:
        """Skip a single-line comment (// ...)."""
        # Consume the //
        self._advance()
        self._advance()

        # Skip until end of line
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    def _skip_multi_line_comment(self) -> None:
        """
        Skip a multi-line comment (/* ... */).

        Raises:
            CSyntaxError: If comment is not terminated
        """
        start_line = self._line
        start_col = self._column

        # Consume the /*
        self._advance()
        self._advance()

        # Look for closing */
        while not self._at_end():
            if self._peek() == "*" and self._peek(1) == "/":
                self._advance()  # consume *
                self._advance()  # consume /
                return
            self._advance()

        # Reached end without finding */
        raise CSyntaxError(
            "unterminated multi-line comment",
            SourceLocation(self.filename, start_line, start_col),
            hint="add closing */ to terminate the comment",
        )

    # =========================================================================
    # Token Scanning
    # =========================================================================

    def _scan_token(self) -> Optional[CToken]:
        """
        Scan the next token from source.

        Returns:
            The next CToken, or None if nothing to scan
        """
        start_line = self._line
        start_column = self._column

        char = self._peek()

        # Identifiers and keywords
        if char in self.IDENT_START:
            return self._scan_identifier(start_line, start_column)

        # Numbers
        if char.isdigit():
            return self._scan_number(start_line, start_column)

        # String literal
        if char == '"':
            return self._scan_string(start_line, start_column)

        # Character literal
        if char == "'":
            return self._scan_char(start_line, start_column)

        # Operators and delimiters
        return self._scan_operator(start_line, start_column)

    def _scan_identifier(self, start_line: int, start_column: int) -> CToken:
        """
        Scan an identifier or keyword.

        Identifiers start with a letter or underscore and can contain
        letters, digits, and underscores. Keywords are distinguished
        by checking against the keyword table.
        """
        chars = []
        while self._peek() and self._peek() in self.IDENT_CHARS:
            chars.append(self._advance())

        name = "".join(chars)

        # Check if it's a keyword
        if name in KEYWORDS:
            return self._make_token(KEYWORDS[name], name, start_line, start_column)

        return self._make_token(CTokenType.IDENTIFIER, name, start_line, start_column)

    def _scan_number(self, start_line: int, start_column: int) -> CToken:
        """
        Scan a numeric literal.

        Handles:
        - Decimal: 123
        - Hexadecimal: 0x7F or 0X7F
        - Octal: 0177
        - Binary: 0b1010 or 0B1010 (GCC extension)
        """
        # Check for special prefixes
        if self._peek() == "0":
            next_char = self._peek(1).lower()

            # Hexadecimal: 0x...
            if next_char == "x":
                self._advance()  # consume 0
                self._advance()  # consume x
                return self._scan_hex_digits(start_line, start_column)

            # Binary: 0b... (GCC extension)
            if next_char == "b":
                self._advance()  # consume 0
                self._advance()  # consume b
                return self._scan_binary_digits(start_line, start_column)

            # Octal: 0... (but not just 0)
            if next_char and next_char in "01234567":
                return self._scan_octal_number(start_line, start_column)

        # Decimal number
        return self._scan_decimal_number(start_line, start_column)

    def _scan_decimal_number(self, start_line: int, start_column: int) -> CToken:
        """Scan a decimal number."""
        chars = []
        while self._peek().isdigit():
            chars.append(self._advance())

        value = int("".join(chars))
        return self._make_token(CTokenType.NUMBER, value, start_line, start_column)

    def _scan_hex_digits(self, start_line: int, start_column: int) -> CToken:
        """Scan hexadecimal digits after 0x prefix."""
        chars = []
        while self._peek() and self._peek() in string.hexdigits:
            chars.append(self._advance())

        if not chars:
            raise self._error("expected hexadecimal digits after '0x'")

        value = int("".join(chars), 16)
        return self._make_token(CTokenType.NUMBER, value, start_line, start_column)

    def _scan_binary_digits(self, start_line: int, start_column: int) -> CToken:
        """Scan binary digits after 0b prefix."""
        chars = []
        while self._peek() and self._peek() in "01":
            chars.append(self._advance())

        if not chars:
            raise self._error("expected binary digits after '0b'")

        value = int("".join(chars), 2)
        return self._make_token(CTokenType.NUMBER, value, start_line, start_column)

    def _scan_octal_number(self, start_line: int, start_column: int) -> CToken:
        """Scan an octal number starting with 0."""
        chars = []
        while self._peek() and self._peek() in "01234567":
            chars.append(self._advance())

        # If no valid octal digits after 0, it's just decimal 0
        if not chars:
            return self._make_token(CTokenType.NUMBER, 0, start_line, start_column)

        value = int("".join(chars), 8)
        return self._make_token(CTokenType.NUMBER, value, start_line, start_column)

    def _scan_string(self, start_line: int, start_column: int) -> CToken:
        """
        Scan a double-quoted string literal.

        Supports escape sequences: \\n, \\r, \\t, \\\\, \\", \\xNN
        """
        self._advance()  # consume opening "

        chars = []
        while not self._at_end():
            char = self._peek()

            if char == '"':
                self._advance()  # consume closing "
                return self._make_token(
                    CTokenType.STRING,
                    "".join(chars),
                    start_line,
                    start_column,
                )

            if char == "\n":
                raise UnterminatedStringError(
                    SourceLocation(self.filename, start_line, start_column),
                    self._get_current_line(),
                )

            if char == "\\":
                self._advance()  # consume backslash
                escaped = self._scan_escape_sequence()
                chars.append(escaped)
            else:
                chars.append(self._advance())

        raise UnterminatedStringError(
            SourceLocation(self.filename, start_line, start_column),
        )

    def _scan_char(self, start_line: int, start_column: int) -> CToken:
        """
        Scan a single-quoted character literal.

        Returns the ASCII value of the character as a NUMBER token
        with CHAR_LITERAL type for semantic analysis.
        """
        self._advance()  # consume opening '

        if self._at_end() or self._peek() == "\n":
            raise CSyntaxError(
                "unterminated character literal",
                SourceLocation(self.filename, start_line, start_column),
                hint="add closing ' to complete the character literal",
            )

        # Handle escape sequence or regular character
        if self._peek() == "\\":
            self._advance()  # consume backslash
            char = self._scan_escape_sequence()
        else:
            char = self._advance()

        # Check for closing quote
        if self._peek() != "'":
            raise CSyntaxError(
                "character literal too long or missing closing quote",
                SourceLocation(self.filename, self._line, self._column),
                hint="character literals can only contain a single character",
            )
        self._advance()  # consume closing '

        value = ord(char)
        return self._make_token(CTokenType.CHAR_LITERAL, value, start_line, start_column)

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
                if self._peek() and self._peek() in string.hexdigits:
                    hex_chars.append(self._advance())
                else:
                    break

            if not hex_chars:
                raise self._error("expected hexadecimal digits after '\\x'")

            value = int("".join(hex_chars), 16)
            return chr(value)

        # Octal escape: \NNN (up to 3 digits)
        if char in "01234567":
            octal_chars = [char]
            for _ in range(2):  # Already have one, can have 2 more
                if self._peek() and self._peek() in "01234567":
                    octal_chars.append(self._advance())
                else:
                    break

            value = int("".join(octal_chars), 8) & 0xFF
            return chr(value)

        # Unknown escape - return the character as-is (with warning in strict mode)
        return char

    def _scan_operator(self, start_line: int, start_column: int) -> CToken:
        """
        Scan an operator or delimiter.

        Handles single, double, and triple character operators.
        """
        char = self._advance()

        # Two and three character operators
        if char == "+":
            if self._match("+"):
                return self._make_token(CTokenType.INCREMENT, "++", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.PLUS_ASSIGN, "+=", start_line, start_column)
            return self._make_token(CTokenType.PLUS, "+", start_line, start_column)

        if char == "-":
            if self._match("-"):
                return self._make_token(CTokenType.DECREMENT, "--", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.MINUS_ASSIGN, "-=", start_line, start_column)
            return self._make_token(CTokenType.MINUS, "-", start_line, start_column)

        if char == "*":
            if self._match("="):
                return self._make_token(CTokenType.STAR_ASSIGN, "*=", start_line, start_column)
            return self._make_token(CTokenType.STAR, "*", start_line, start_column)

        if char == "/":
            if self._match("="):
                return self._make_token(CTokenType.SLASH_ASSIGN, "/=", start_line, start_column)
            return self._make_token(CTokenType.SLASH, "/", start_line, start_column)

        if char == "%":
            if self._match("="):
                return self._make_token(CTokenType.PERCENT_ASSIGN, "%=", start_line, start_column)
            return self._make_token(CTokenType.PERCENT, "%", start_line, start_column)

        if char == "&":
            if self._match("&"):
                return self._make_token(CTokenType.AND, "&&", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.AND_ASSIGN, "&=", start_line, start_column)
            return self._make_token(CTokenType.AMPERSAND, "&", start_line, start_column)

        if char == "|":
            if self._match("|"):
                return self._make_token(CTokenType.OR, "||", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.OR_ASSIGN, "|=", start_line, start_column)
            return self._make_token(CTokenType.PIPE, "|", start_line, start_column)

        if char == "^":
            if self._match("="):
                return self._make_token(CTokenType.XOR_ASSIGN, "^=", start_line, start_column)
            return self._make_token(CTokenType.CARET, "^", start_line, start_column)

        if char == "=":
            if self._match("="):
                return self._make_token(CTokenType.EQ, "==", start_line, start_column)
            return self._make_token(CTokenType.ASSIGN, "=", start_line, start_column)

        if char == "!":
            if self._match("="):
                return self._make_token(CTokenType.NE, "!=", start_line, start_column)
            return self._make_token(CTokenType.NOT, "!", start_line, start_column)

        if char == "<":
            if self._match("<"):
                if self._match("="):
                    return self._make_token(CTokenType.LSHIFT_ASSIGN, "<<=", start_line, start_column)
                return self._make_token(CTokenType.LSHIFT, "<<", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.LE, "<=", start_line, start_column)
            return self._make_token(CTokenType.LT, "<", start_line, start_column)

        if char == ">":
            if self._match(">"):
                if self._match("="):
                    return self._make_token(CTokenType.RSHIFT_ASSIGN, ">>=", start_line, start_column)
                return self._make_token(CTokenType.RSHIFT, ">>", start_line, start_column)
            if self._match("="):
                return self._make_token(CTokenType.GE, ">=", start_line, start_column)
            return self._make_token(CTokenType.GT, ">", start_line, start_column)

        # Single character tokens
        single_tokens = {
            "(": CTokenType.LPAREN,
            ")": CTokenType.RPAREN,
            "{": CTokenType.LBRACE,
            "}": CTokenType.RBRACE,
            "[": CTokenType.LBRACKET,
            "]": CTokenType.RBRACKET,
            ";": CTokenType.SEMICOLON,
            ",": CTokenType.COMMA,
            ":": CTokenType.COLON,
            "?": CTokenType.QUESTION,
            "~": CTokenType.TILDE,
            "#": CTokenType.HASH,
        }

        if char in single_tokens:
            return self._make_token(single_tokens[char], char, start_line, start_column)

        # Unknown character
        raise InvalidCharacterError(
            char,
            SourceLocation(self.filename, start_line, start_column),
            self._get_current_line(),
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _get_current_line(self) -> str:
        """Get the current line of source text for error reporting."""
        line_end = self.source.find("\n", self._line_start_pos)
        if line_end == -1:
            line_end = len(self.source)
        return self.source[self._line_start_pos:line_end]

    def peek_token(self) -> Optional[CToken]:
        """
        Peek at the next token without consuming it.

        This creates a temporary copy of the lexer state, scans
        the next token, then restores the original state.

        Returns:
            The next token, or None if at end
        """
        # Save state
        saved_pos = self._pos
        saved_line = self._line
        saved_column = self._column
        saved_line_start = self._line_start_pos

        try:
            # Skip whitespace and comments
            self._skip_whitespace_and_comments()

            if self._at_end():
                return self._make_token(CTokenType.EOF, None)

            # Scan token
            return self._scan_token()
        finally:
            # Restore state
            self._pos = saved_pos
            self._line = saved_line
            self._column = saved_column
            self._line_start_pos = saved_line_start
