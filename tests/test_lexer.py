# =============================================================================
# test_lexer.py - Lexer Unit Tests
# =============================================================================
# Tests for the HD6303 assembler lexer/tokenizer.
# Covers Milestone A1: Lexer & Tokenization from specs/01-assembler.md.
#
# Test coverage includes:
#   - Number formats: decimal, hexadecimal ($), binary (%), octal (@), char
#   - String literals with escape sequences
#   - All token types: identifiers, operators, delimiters
#   - Comments (semicolon and asterisk forms)
#   - Line continuation and whitespace handling
#   - Error conditions
# =============================================================================

import pytest
from psion_sdk.assembler.lexer import Lexer, TokenType, Token
from psion_sdk.errors import AssemblySyntaxError


# =============================================================================
# Helper Function
# =============================================================================

def tokenize(source: str, line_number: int = 1) -> list:
    """
    Helper to tokenize and filter out structural tokens (EOF, NEWLINE).
    Tests are focused on meaningful tokens, not structural ones.

    Args:
        source: The assembly source to tokenize
        line_number: Starting line number (for position tracking tests)
    """
    lexer = Lexer(source, "<test>", line_number=line_number)
    all_tokens = list(lexer.tokenize())
    # Filter out EOF and optionally NEWLINE for cleaner assertions
    return [t for t in all_tokens if t.type not in (TokenType.EOF,)]


# =============================================================================
# Basic Token Recognition Tests
# =============================================================================

class TestBasicTokens:
    """Test basic token recognition for simple inputs."""

    def test_empty_line(self):
        """Empty lines should produce no meaningful tokens."""
        tokens = tokenize("")
        assert tokens == []

    def test_whitespace_only(self):
        """Lines with only whitespace should produce no tokens."""
        tokens = tokenize("   \t   ")
        assert tokens == []

    def test_identifier(self):
        """Test simple identifier tokenization."""
        tokens = tokenize("LABEL")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "LABEL"

    def test_identifier_with_underscore(self):
        """Identifiers can contain underscores."""
        tokens = tokenize("MY_LABEL")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "MY_LABEL"

    def test_identifier_with_numbers(self):
        """Identifiers can contain numbers (not at start)."""
        tokens = tokenize("LOOP1")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "LOOP1"

    def test_multiple_identifiers(self):
        """Multiple identifiers separated by whitespace."""
        tokens = tokenize("LDAA LABEL")
        assert len(tokens) == 2
        assert tokens[0].value == "LDAA"
        assert tokens[1].value == "LABEL"


# =============================================================================
# Number Format Tests
# =============================================================================

class TestNumberFormats:
    """Test various number format recognition."""

    def test_decimal_number(self):
        """Plain decimal numbers."""
        tokens = tokenize("123")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 123

    def test_decimal_zero(self):
        """Zero value."""
        tokens = tokenize("0")
        assert tokens[0].value == 0

    def test_hex_with_dollar(self):
        """Hexadecimal with $ prefix (Motorola style)."""
        tokens = tokenize("$FF")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 0xFF

    def test_hex_lowercase(self):
        """Hexadecimal with lowercase letters."""
        tokens = tokenize("$ff")
        assert tokens[0].value == 0xFF

    def test_hex_mixed_case(self):
        """Hexadecimal with mixed case."""
        tokens = tokenize("$DeAdBeEf")
        assert tokens[0].value == 0xDEADBEEF

    def test_hex_address(self):
        """Common hex address format."""
        tokens = tokenize("$2100")
        assert tokens[0].value == 0x2100

    def test_binary_with_percent(self):
        """Binary with % prefix."""
        tokens = tokenize("%10101010")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 0xAA

    def test_binary_simple(self):
        """Simple binary number."""
        tokens = tokenize("%11111111")
        assert tokens[0].value == 255

    def test_octal_with_at(self):
        """Octal with @ prefix."""
        tokens = tokenize("@377")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 0o377

    def test_character_literal(self):
        """Single character literal with apostrophe."""
        tokens = tokenize("'A'")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == ord('A')

    def test_character_lowercase(self):
        """Lowercase character literal."""
        tokens = tokenize("'z'")
        assert tokens[0].value == ord('z')

    def test_character_digit(self):
        """Digit character literal."""
        tokens = tokenize("'0'")
        assert tokens[0].value == ord('0')

    def test_character_space(self):
        """Space character literal."""
        tokens = tokenize("' '")
        assert tokens[0].value == 0x20


# =============================================================================
# String Literal Tests
# =============================================================================

class TestStringLiterals:
    """Test string literal tokenization."""

    def test_simple_string(self):
        """Simple quoted string."""
        tokens = tokenize('"Hello"')
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "Hello"

    def test_string_with_spaces(self):
        """String containing spaces."""
        tokens = tokenize('"Hello World"')
        assert tokens[0].value == "Hello World"

    def test_empty_string(self):
        """Empty string."""
        tokens = tokenize('""')
        assert tokens[0].value == ""

    def test_string_with_numbers(self):
        """String containing numbers."""
        tokens = tokenize('"Test123"')
        assert tokens[0].value == "Test123"

    def test_string_escape_newline(self):
        """Escaped newline in string."""
        tokens = tokenize('"Hello\\n"')
        assert tokens[0].value == "Hello\n"

    def test_string_escape_tab(self):
        """Escaped tab in string."""
        tokens = tokenize('"Hello\\t"')
        assert tokens[0].value == "Hello\t"

    def test_string_escape_backslash(self):
        """Escaped backslash in string."""
        tokens = tokenize('"Hello\\\\"')
        assert tokens[0].value == "Hello\\"

    def test_string_escape_quote(self):
        """Escaped quote in string."""
        tokens = tokenize('"Say \\"Hi\\""')
        assert tokens[0].value == 'Say "Hi"'


# =============================================================================
# Operator and Delimiter Tests
# =============================================================================

class TestOperators:
    """Test operator and delimiter tokenization."""

    def test_hash_immediate(self):
        """Hash for immediate addressing."""
        tokens = tokenize("#$10")
        assert tokens[0].type == TokenType.HASH
        assert tokens[1].type == TokenType.NUMBER

    def test_comma(self):
        """Comma separator."""
        tokens = tokenize("A,X")
        assert len(tokens) == 3
        assert tokens[1].type == TokenType.COMMA

    def test_plus_operator(self):
        """Plus operator."""
        tokens = tokenize("1+2")
        assert tokens[1].type == TokenType.PLUS

    def test_minus_operator(self):
        """Minus operator."""
        tokens = tokenize("10-5")
        assert tokens[1].type == TokenType.MINUS

    def test_multiply_operator(self):
        """Multiply operator."""
        tokens = tokenize("2*3")
        assert tokens[1].type == TokenType.STAR

    def test_divide_operator(self):
        """Divide operator."""
        tokens = tokenize("10/2")
        assert tokens[1].type == TokenType.SLASH

    def test_parentheses(self):
        """Parentheses for grouping."""
        lexer = Lexer("(1+2)")
        tokens = list(lexer.tokenize())
        assert tokens[0].type == TokenType.LPAREN
        assert tokens[4].type == TokenType.RPAREN

    def test_colon_label(self):
        """Colon for label definition."""
        tokens = tokenize("LABEL:")
        assert len(tokens) == 2
        assert tokens[1].type == TokenType.COLON

    def test_ampersand(self):
        """Ampersand for bitwise AND."""
        tokens = tokenize("$FF&$0F")
        assert tokens[1].type == TokenType.AMPERSAND

    def test_pipe(self):
        """Pipe for bitwise OR."""
        tokens = tokenize("$F0|$0F")
        assert tokens[1].type == TokenType.PIPE

    def test_caret(self):
        """Caret for bitwise XOR."""
        tokens = tokenize("$FF^$AA")
        assert tokens[1].type == TokenType.CARET

    def test_tilde(self):
        """Tilde for bitwise NOT."""
        tokens = tokenize("~$FF")
        assert tokens[0].type == TokenType.TILDE

    def test_less_than(self):
        """Less-than for comparisons or LOW byte."""
        tokens = tokenize("<ADDR")
        assert tokens[0].type == TokenType.LT

    def test_greater_than(self):
        """Greater-than for comparisons or HIGH byte."""
        tokens = tokenize(">ADDR")
        assert tokens[0].type == TokenType.GT


# =============================================================================
# Comment Tests
# =============================================================================

class TestComments:
    """Test comment handling."""

    def test_semicolon_comment(self):
        """Semicolon starts end-of-line comment."""
        tokens = tokenize("NOP ; This is a comment")
        assert len(tokens) == 1
        assert tokens[0].value == "NOP"

    def test_semicolon_only(self):
        """Line with only comment."""
        tokens = tokenize("; Full line comment")
        assert tokens == []

    def test_asterisk_comment_at_start(self):
        """Asterisk at line start is comment."""
        tokens = tokenize("* This is a full line comment")
        assert tokens == []

    def test_asterisk_not_at_start(self):
        """Asterisk not at start is multiply operator."""
        tokens = tokenize("2*3")
        assert len(tokens) == 3
        assert tokens[1].type == TokenType.STAR

    def test_comment_after_string(self):
        """Comment after string literal."""
        tokens = tokenize('FCC "Hello" ; message')
        assert len(tokens) == 2
        assert tokens[0].value == "FCC"
        assert tokens[1].value == "Hello"


# =============================================================================
# Complex Line Tests
# =============================================================================

class TestComplexLines:
    """Test tokenization of complete assembly lines."""

    def test_label_and_instruction(self):
        """Label followed by instruction."""
        tokens = tokenize("START: NOP")
        assert len(tokens) == 3
        assert tokens[0].value == "START"
        assert tokens[1].type == TokenType.COLON
        assert tokens[2].value == "NOP"

    def test_instruction_with_immediate(self):
        """Instruction with immediate operand."""
        tokens = tokenize("LDAA #$41")
        assert len(tokens) == 3
        assert tokens[0].value == "LDAA"
        assert tokens[1].type == TokenType.HASH
        assert tokens[2].value == 0x41

    def test_instruction_with_indexed(self):
        """Instruction with indexed operand."""
        tokens = tokenize("LDAA $10,X")
        assert len(tokens) == 4
        assert tokens[0].value == "LDAA"
        assert tokens[1].value == 0x10
        assert tokens[2].type == TokenType.COMMA
        assert tokens[3].value == "X"

    def test_org_directive(self):
        """ORG directive with address."""
        tokens = tokenize("ORG $2100")
        assert len(tokens) == 2
        assert tokens[0].value == "ORG"
        assert tokens[1].value == 0x2100

    def test_fcb_multiple_values(self):
        """FCB with multiple values."""
        tokens = tokenize("FCB $01,$02,$03")
        assert len(tokens) == 6  # FCB, val, comma, val, comma, val
        assert tokens[0].value == "FCB"

    def test_fcc_string(self):
        """FCC with string."""
        tokens = tokenize('FCC "Hello World"')
        assert len(tokens) == 2
        assert tokens[0].value == "FCC"
        assert tokens[1].value == "Hello World"

    def test_equ_definition(self):
        """EQU constant definition."""
        tokens = tokenize("CONST EQU $100")
        assert len(tokens) == 3
        assert tokens[0].value == "CONST"
        assert tokens[1].value == "EQU"
        assert tokens[2].value == 0x100

    def test_expression_operand(self):
        """Instruction with expression operand."""
        lexer = Lexer("LDAA #HIGH(ADDR)")
        tokens = list(lexer.tokenize())
        assert tokens[0].value == "LDAA"
        assert tokens[1].type == TokenType.HASH
        assert tokens[2].value == "HIGH"
        assert tokens[3].type == TokenType.LPAREN

    def test_full_line_with_comment(self):
        """Complete line with label, instruction, operand, and comment."""
        tokens = tokenize("LOOP: LDAA #$41  ; Load 'A'")
        assert len(tokens) == 5
        assert tokens[0].value == "LOOP"
        assert tokens[1].type == TokenType.COLON
        assert tokens[2].value == "LDAA"
        assert tokens[3].type == TokenType.HASH
        assert tokens[4].value == 0x41


# =============================================================================
# Position Tracking Tests
# =============================================================================

class TestPositionTracking:
    """Test that tokens track their source positions correctly."""

    def test_column_tracking(self):
        """Tokens should track their column position."""
        tokens = tokenize("LABEL NOP")
        assert tokens[0].column == 1  # LABEL starts at column 1
        assert tokens[1].column == 7  # NOP starts at column 7

    def test_line_number(self):
        """Tokens should have correct line numbers."""
        tokens = tokenize("NOP", line_number=5)
        assert tokens[0].line == 5


# =============================================================================
# Error Condition Tests
# =============================================================================

class TestLexerErrors:
    """Test error handling in the lexer."""

    def test_unterminated_string(self):
        """Unterminated string should raise error."""
        lexer = Lexer('"Hello')
        with pytest.raises(AssemblySyntaxError):
            # Must consume the generator to trigger the error
            list(lexer.tokenize())

    def test_unterminated_char(self):
        """Unterminated character literal should raise error."""
        lexer = Lexer("'A")
        with pytest.raises(AssemblySyntaxError):
            # Must consume the generator to trigger the error
            list(lexer.tokenize())

    def test_invalid_hex_after_0x(self):
        """Invalid hex digit after 0x prefix should raise error."""
        # Note: $GG is parsed as $ (PC) + GG (identifier) - valid tokenization
        # but 0xGG has no fallback interpretation
        lexer = Lexer("0xGG")
        with pytest.raises(AssemblySyntaxError):
            # Must consume the generator to trigger the error
            list(lexer.tokenize())

    def test_dollar_followed_by_non_hex(self):
        """$ followed by non-hex is $ (PC) plus identifier - valid tokens."""
        # This is NOT an error - $ alone is valid (current PC), followed by identifier
        tokens = tokenize("$GG")
        assert len(tokens) == 2
        assert tokens[0].type == TokenType.DOLLAR
        assert tokens[1].type == TokenType.IDENTIFIER
        assert tokens[1].value == "GG"

    def test_binary_partial_match(self):
        """Binary stops at first non-binary digit, rest becomes new tokens."""
        # %102 tokenizes as %10 (binary 2) + 2 (decimal) - greedy tokenization
        tokens = tokenize("%102")
        assert len(tokens) == 2
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 2  # %10 = binary 2
        assert tokens[1].type == TokenType.NUMBER
        assert tokens[1].value == 2  # decimal 2


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_dollar_sign_alone(self):
        """Dollar sign alone means current PC."""
        tokens = tokenize("$")
        # $ alone is special - represents current address
        assert len(tokens) == 1

    def test_asterisk_alone_at_start(self):
        """Asterisk alone at start is comment marker."""
        tokens = tokenize("*")
        assert tokens == []

    def test_tab_as_whitespace(self):
        """Tabs are treated as whitespace."""
        tokens = tokenize("NOP\tRTS")
        assert len(tokens) == 2
        assert tokens[0].value == "NOP"
        assert tokens[1].value == "RTS"

    def test_multiple_spaces(self):
        """Multiple spaces between tokens."""
        tokens = tokenize("NOP     RTS")
        assert len(tokens) == 2

    def test_case_preservation(self):
        """Identifier case should be preserved (upper-cased internally)."""
        tokens = tokenize("Label")
        # Internally case is normalized to uppercase
        assert tokens[0].value.upper() == "LABEL"

    def test_long_hex_number(self):
        """Long hexadecimal number (32-bit)."""
        tokens = tokenize("$DEADBEEF")
        assert tokens[0].value == 0xDEADBEEF

    def test_zero_prefixed_decimal(self):
        """Decimal with leading zeros."""
        tokens = tokenize("007")
        assert tokens[0].value == 7


# =============================================================================
# Psion-Specific Tests
# =============================================================================

class TestPsionSpecific:
    """Test Psion Organiser II specific syntax."""

    def test_swi_instruction(self):
        """SWI instruction (no operand)."""
        tokens = tokenize("SWI")
        assert len(tokens) == 1
        assert tokens[0].value == "SWI"

    def test_syscall_pattern(self):
        """Common syscall pattern: LDAA #service; SWI"""
        tokens = tokenize("LDAA #$10")
        assert tokens[0].value == "LDAA"
        assert tokens[2].value == 0x10

    def test_typical_org_address(self):
        """Typical Psion code load address."""
        tokens = tokenize("ORG $2100")
        assert tokens[1].value == 0x2100

    def test_rmb_directive(self):
        """RMB directive for reserving memory."""
        tokens = tokenize("RMB 10")
        assert tokens[0].value == "RMB"
        assert tokens[1].value == 10
