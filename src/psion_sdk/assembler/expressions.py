"""
Assembly Expression Evaluator
==============================

This module implements an expression evaluator for HD6303 assembly language.
It handles arithmetic and logical expressions that appear in operands and
directive arguments.

Supported Operations
--------------------
**Arithmetic:**
- Addition (+)
- Subtraction (-)
- Multiplication (*)
- Division (/)
- Modulo (%)

**Bitwise:**
- AND (&)
- OR (|)
- XOR (^)
- NOT (~)
- Left shift (<<)
- Right shift (>>)

**Comparison** (for conditional assembly):
- Less than (<)
- Greater than (>)
- Less or equal (<=)
- Greater or equal (>=)
- Equal (==)
- Not equal (!=, <>)

**Functions:**
- HIGH(expr) - Extract high byte of 16-bit value
- LOW(expr) - Extract low byte of 16-bit value

**Special Symbols:**
- * or $ - Current program counter

Expression Grammar
------------------
The evaluator uses a recursive descent parser with proper operator
precedence (from lowest to highest):

1. Comparison: < <= > >= == !=
2. Bitwise OR: |
3. Bitwise XOR: ^
4. Bitwise AND: &
5. Shift: << >>
6. Addition/Subtraction: + -
7. Multiplication/Division: * / %
8. Unary: + - ~ (NOT)
9. Primary: number, symbol, function call, (grouped expression)

Example Usage
-------------
>>> from psion_sdk.assembler.expressions import ExpressionEvaluator
>>> evaluator = ExpressionEvaluator()
>>> evaluator.set_symbol("buffer", 0x1000)
>>> evaluator.set_pc(0x8000)
>>> result = evaluator.evaluate("buffer + 10")
>>> print(f"${result:04X}")  # $1010
>>> result = evaluator.evaluate("HIGH(buffer)")
>>> print(f"${result:02X}")  # $10

Forward References
------------------
Expressions may contain forward references to symbols not yet defined.
The evaluator tracks these and raises UndefinedSymbolError. The assembler
handles forward references by doing two passes:

1. Pass 1: Collect symbols and addresses
2. Pass 2: Evaluate expressions with full symbol table
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum, auto

from psion_sdk.errors import (
    ExpressionError,
    UndefinedSymbolError,
    SourceLocation,
)
from psion_sdk.assembler.lexer import Token, TokenType


# =============================================================================
# Expression AST Nodes
# =============================================================================

class ExprNodeType(Enum):
    """Types of expression AST nodes."""
    NUMBER = auto()      # Literal number
    SYMBOL = auto()      # Symbol reference
    PC = auto()          # Current program counter (* or $)
    BINARY_OP = auto()   # Binary operation (a + b)
    UNARY_OP = auto()    # Unary operation (-a, ~a)
    FUNCTION = auto()    # Function call (HIGH, LOW)


@dataclass
class ExprNode:
    """
    AST node for expression evaluation.

    This class represents a node in the expression tree. Each node
    has a type and carries data appropriate to that type.
    """
    node_type: ExprNodeType
    value: int | str | None = None  # For NUMBER/SYMBOL
    operator: str | None = None     # For BINARY_OP/UNARY_OP
    left: Optional["ExprNode"] = None
    right: Optional["ExprNode"] = None
    func_name: str | None = None    # For FUNCTION
    func_arg: Optional["ExprNode"] = None


# =============================================================================
# Expression Evaluator
# =============================================================================

class ExpressionEvaluator:
    """
    Evaluates assembly expressions.

    The evaluator maintains a symbol table and current program counter
    for resolving references. It uses a two-stage approach:

    1. Parse expression into AST
    2. Evaluate AST with current symbol table

    This separation allows for detecting forward references during
    pass 1 and evaluating them during pass 2.

    Attributes:
        symbols: Dictionary of symbol names to values
        pc: Current program counter value
    """

    # Built-in functions
    FUNCTIONS = {"HIGH", "LOW"}

    def __init__(self):
        """Initialize the evaluator with empty symbol table."""
        self._symbols: dict[str, int] = {}
        self._pc: int = 0
        self._undefined_symbols: set[str] = set()

    # =========================================================================
    # Symbol Table Management
    # =========================================================================

    def set_symbol(self, name: str, value: int) -> None:
        """
        Define a symbol with a value.

        Args:
            name: Symbol name
            value: Symbol value (16-bit integer)
        """
        self._symbols[name] = value & 0xFFFF

    def get_symbol(self, name: str) -> Optional[int]:
        """
        Look up a symbol's value.

        Args:
            name: Symbol name to look up

        Returns:
            Symbol value if defined, None otherwise
        """
        return self._symbols.get(name)

    def has_symbol(self, name: str) -> bool:
        """Check if a symbol is defined."""
        return name in self._symbols

    def set_pc(self, value: int) -> None:
        """
        Set the current program counter.

        Args:
            value: New PC value
        """
        self._pc = value & 0xFFFF

    def get_pc(self) -> int:
        """Get the current program counter."""
        return self._pc

    def clear_undefined(self) -> None:
        """Clear the set of undefined symbols encountered."""
        self._undefined_symbols.clear()

    def get_undefined_symbols(self) -> set[str]:
        """Get the set of undefined symbols encountered during evaluation."""
        return self._undefined_symbols.copy()

    # =========================================================================
    # Main Evaluation Interface
    # =========================================================================

    def evaluate(
        self,
        tokens: list[Token],
        location: Optional[SourceLocation] = None,
        allow_undefined: bool = False,
    ) -> int:
        """
        Evaluate an expression from a list of tokens.

        Args:
            tokens: Token list representing the expression
            location: Source location for error reporting
            allow_undefined: If True, undefined symbols return 0 and are tracked
                           If False, raises UndefinedSymbolError

        Returns:
            The integer result of the expression

        Raises:
            ExpressionError: If expression is malformed
            UndefinedSymbolError: If symbol not found and allow_undefined=False
        """
        if not tokens:
            raise ExpressionError("empty expression", location)

        self._tokens = tokens
        self._pos = 0
        self._location = location
        self._allow_undefined = allow_undefined
        self._undefined_symbols.clear()

        try:
            result = self._parse_comparison()

            # Check for unconsumed tokens
            if self._pos < len(self._tokens):
                tok = self._current()
                if tok.type not in (TokenType.NEWLINE, TokenType.EOF):
                    raise ExpressionError(
                        f"unexpected token '{tok.value}' in expression",
                        location or tok.location
                    )

            return result & 0xFFFF  # Ensure 16-bit result

        except IndexError:
            raise ExpressionError("unexpected end of expression", location)

    def evaluate_to_byte(
        self,
        tokens: list[Token],
        location: Optional[SourceLocation] = None,
        allow_undefined: bool = False,
    ) -> int:
        """
        Evaluate an expression and ensure it fits in a byte.

        Args:
            tokens: Token list representing the expression
            location: Source location for error reporting
            allow_undefined: Allow undefined symbols

        Returns:
            The 8-bit result

        Raises:
            ExpressionError: If result doesn't fit in a byte
        """
        result = self.evaluate(tokens, location, allow_undefined)

        # Check if value fits in a byte (allow both signed and unsigned)
        if result > 255 and result < 0xFF00:  # Allow $FF00-$FFFF as negative byte
            if not allow_undefined:
                raise ExpressionError(
                    f"value ${result:04X} does not fit in a byte",
                    location
                )
        return result & 0xFF

    # =========================================================================
    # Token Navigation
    # =========================================================================

    def _current(self) -> Token:
        """Get current token."""
        if self._pos >= len(self._tokens):
            # Return a synthetic EOF token
            last = self._tokens[-1] if self._tokens else None
            return Token(
                TokenType.EOF, None,
                last.line if last else 1,
                last.column if last else 1,
                last.filename if last else "<input>"
            )
        return self._tokens[self._pos]

    def _peek(self, offset: int = 0) -> Token:
        """Look ahead at token."""
        pos = self._pos + offset
        if pos >= len(self._tokens):
            return self._current()  # Will return EOF
        return self._tokens[pos]

    def _advance(self) -> Token:
        """Consume and return current token."""
        token = self._current()
        self._pos += 1
        return token

    def _match(self, *types: TokenType) -> Optional[Token]:
        """Match and consume token if it's one of the given types."""
        if self._current().type in types:
            return self._advance()
        return None

    def _expect(self, token_type: TokenType, message: str) -> Token:
        """Expect a specific token type, raising error if not found."""
        if self._current().type != token_type:
            raise ExpressionError(message, self._location or self._current().location)
        return self._advance()

    # =========================================================================
    # Recursive Descent Parser with Evaluation
    # =========================================================================
    # The parser evaluates expressions during parsing for efficiency.
    # Each parse method returns the integer result directly.
    # =========================================================================

    def _parse_comparison(self) -> int:
        """Parse comparison operators (lowest precedence)."""
        left = self._parse_or()

        while True:
            if self._match(TokenType.LT):
                right = self._parse_or()
                left = 1 if left < right else 0
            elif self._match(TokenType.GT):
                right = self._parse_or()
                left = 1 if left > right else 0
            elif self._match(TokenType.LE):
                right = self._parse_or()
                left = 1 if left <= right else 0
            elif self._match(TokenType.GE):
                right = self._parse_or()
                left = 1 if left >= right else 0
            elif self._match(TokenType.EQ):
                right = self._parse_or()
                left = 1 if left == right else 0
            elif self._match(TokenType.NE):
                right = self._parse_or()
                left = 1 if left != right else 0
            else:
                break

        return left

    def _parse_or(self) -> int:
        """Parse bitwise OR."""
        left = self._parse_xor()

        while self._match(TokenType.PIPE):
            right = self._parse_xor()
            left = left | right

        return left

    def _parse_xor(self) -> int:
        """Parse bitwise XOR."""
        left = self._parse_and()

        while self._match(TokenType.CARET):
            right = self._parse_and()
            left = left ^ right

        return left

    def _parse_and(self) -> int:
        """Parse bitwise AND."""
        left = self._parse_shift()

        while self._match(TokenType.AMPERSAND):
            right = self._parse_shift()
            left = left & right

        return left

    def _parse_shift(self) -> int:
        """Parse shift operators."""
        left = self._parse_additive()

        while True:
            if self._match(TokenType.LSHIFT):
                right = self._parse_additive()
                left = (left << right) & 0xFFFF
            elif self._match(TokenType.RSHIFT):
                right = self._parse_additive()
                left = left >> right
            else:
                break

        return left

    def _parse_additive(self) -> int:
        """Parse addition and subtraction."""
        left = self._parse_multiplicative()

        while True:
            if self._match(TokenType.PLUS):
                right = self._parse_multiplicative()
                left = (left + right) & 0xFFFF
            elif self._match(TokenType.MINUS):
                right = self._parse_multiplicative()
                left = (left - right) & 0xFFFF
            else:
                break

        return left

    def _parse_multiplicative(self) -> int:
        """Parse multiplication, division, and modulo."""
        left = self._parse_unary()

        while True:
            if self._match(TokenType.STAR):
                right = self._parse_unary()
                left = (left * right) & 0xFFFF
            elif self._match(TokenType.SLASH):
                right = self._parse_unary()
                if right == 0:
                    raise ExpressionError("division by zero", self._location)
                left = left // right
            elif self._match(TokenType.PERCENT):
                right = self._parse_unary()
                if right == 0:
                    raise ExpressionError("modulo by zero", self._location)
                left = left % right
            else:
                break

        return left

    def _parse_unary(self) -> int:
        """Parse unary operators (+, -, ~)."""
        if self._match(TokenType.PLUS):
            return self._parse_unary()
        if self._match(TokenType.MINUS):
            return (-self._parse_unary()) & 0xFFFF
        if self._match(TokenType.TILDE):
            return (~self._parse_unary()) & 0xFFFF
        if self._match(TokenType.LT):
            # < as LOW operator (low byte)
            value = self._parse_unary()
            return value & 0xFF
        if self._match(TokenType.GT):
            # > as HIGH operator (high byte)
            value = self._parse_unary()
            return (value >> 8) & 0xFF

        return self._parse_primary()

    def _parse_primary(self) -> int:
        """Parse primary expressions (numbers, symbols, functions, groups)."""
        tok = self._current()

        # Number literal
        if tok.type == TokenType.NUMBER:
            self._advance()
            return tok.value & 0xFFFF

        # String (first character as number)
        if tok.type == TokenType.STRING:
            self._advance()
            if tok.value:
                return ord(tok.value[0])
            return 0

        # Current PC (* or $)
        if tok.type == TokenType.STAR:
            self._advance()
            return self._pc

        if tok.type == TokenType.DOLLAR:
            self._advance()
            return self._pc

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            result = self._parse_comparison()
            self._expect(TokenType.RPAREN, "expected ')' to close expression")
            return result

        # Identifier (symbol or function)
        if tok.type == TokenType.IDENTIFIER:
            name = tok.value.upper()

            # Check for function call
            if name in self.FUNCTIONS and self._peek(1).type == TokenType.LPAREN:
                return self._parse_function_call(name)

            # Symbol reference
            self._advance()
            return self._resolve_symbol(tok.value, tok.location)

        raise ExpressionError(
            f"expected value, got '{tok.value or tok.type.name}'",
            self._location or tok.location
        )

    def _parse_function_call(self, func_name: str) -> int:
        """Parse a function call like HIGH(expr) or LOW(expr)."""
        self._advance()  # consume function name
        self._expect(TokenType.LPAREN, f"expected '(' after {func_name}")
        arg = self._parse_comparison()
        self._expect(TokenType.RPAREN, f"expected ')' after {func_name} argument")

        if func_name == "HIGH":
            return (arg >> 8) & 0xFF
        elif func_name == "LOW":
            return arg & 0xFF
        else:
            raise ExpressionError(f"unknown function '{func_name}'", self._location)

    def _resolve_symbol(self, name: str, location: SourceLocation) -> int:
        """
        Resolve a symbol reference.

        Args:
            name: Symbol name (case-sensitive)
            location: Source location for error reporting

        Returns:
            Symbol value

        Raises:
            UndefinedSymbolError: If symbol not defined and not allowing undefined
        """
        # Check symbol table (case-sensitive)
        if name in self._symbols:
            return self._symbols[name]

        # Check case-insensitive match for common symbols
        name_upper = name.upper()
        if name_upper in self._symbols:
            return self._symbols[name_upper]

        # Symbol not found
        self._undefined_symbols.add(name)

        if self._allow_undefined:
            # Return 0 as placeholder for forward reference
            return 0

        # Find similar symbols for hint
        similar = self._find_similar_symbols(name)
        raise UndefinedSymbolError(
            name,
            location=location,
            similar_symbols=similar
        )

    def _find_similar_symbols(self, name: str) -> list[str]:
        """
        Find symbols with similar names for error hints.

        Uses simple edit distance heuristic.
        """
        name_lower = name.lower()
        similar = []

        for sym in self._symbols:
            sym_lower = sym.lower()
            # Check for simple typos: off by one char, case difference
            if (
                sym_lower == name_lower or
                abs(len(sym) - len(name)) <= 1 and
                self._edit_distance(name_lower, sym_lower) <= 2
            ):
                similar.append(sym)

        return similar[:3]  # Return at most 3 suggestions

    def _edit_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        distances = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            new_distances = [i + 1]
            for j, c2 in enumerate(s2):
                if c1 == c2:
                    new_distances.append(distances[j])
                else:
                    new_distances.append(1 + min((
                        distances[j],
                        distances[j + 1],
                        new_distances[-1]
                    )))
            distances = new_distances

        return distances[-1]


# =============================================================================
# Convenience Functions
# =============================================================================

def evaluate_expression(
    tokens: list[Token],
    symbols: dict[str, int],
    pc: int = 0,
    location: Optional[SourceLocation] = None,
) -> int:
    """
    Convenience function to evaluate an expression.

    Args:
        tokens: Token list representing the expression
        symbols: Symbol table
        pc: Current program counter
        location: Source location for errors

    Returns:
        Expression result as 16-bit integer
    """
    evaluator = ExpressionEvaluator()
    evaluator._symbols = symbols
    evaluator._pc = pc
    return evaluator.evaluate(tokens, location)
