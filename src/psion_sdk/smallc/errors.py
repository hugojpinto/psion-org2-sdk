"""
Small-C Compiler Error Hierarchy
================================

This module defines the exception hierarchy for the Small-C compiler.
All exceptions inherit from SmallCError, which itself inherits from
the base PsionError for consistent error handling across the SDK.

Exception Hierarchy
-------------------
SmallCError (base for all Small-C errors)
├── CSyntaxError - lexer and parser syntax errors
│   ├── UnterminatedStringError - missing closing quote
│   └── InvalidCharacterError - unexpected character
├── CSemanticError - semantic analysis errors
│   ├── UndeclaredIdentifierError - undefined variable/function
│   ├── DuplicateDeclarationError - variable declared twice
│   └── CTypeError - type mismatch errors
├── CPreprocessorError - preprocessor errors
│   └── CIncludeError - include file not found
└── CCodeGenError - code generation errors

Error Message Format
--------------------
All errors include source location information and follow this format:

    filename:line:column: error: description
        source_line_text
            ^^^^^ (pointer to error location)
    hint: suggestion for fixing

Example:
    hello.c:5:12: error: undeclared identifier 'printt'
        printt("Hello");
               ^^^^^^
    hint: did you mean 'print'?
"""

from typing import Optional, List

from psion_sdk.errors import PsionError, SourceLocation


# =============================================================================
# Base Small-C Exception
# =============================================================================

class SmallCError(PsionError):
    """
    Base exception for all Small-C compiler errors.

    This class provides common functionality for error messages including
    source location tracking, source line context, and helpful hints.

    Attributes:
        message: The error description
        location: Where in the source the error occurred
        hint: A suggestion for fixing the error
        source_line: The actual source text at the error location
    """

    def __init__(
        self,
        message: str,
        location: Optional[SourceLocation] = None,
        hint: Optional[str] = None,
        source_line: Optional[str] = None,
    ):
        self.message = message
        self.location = location
        self.hint = hint
        self.source_line = source_line
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """
        Format the error message with location, source context, and hint.

        Creates a user-friendly error message that helps the programmer
        quickly identify and fix the issue. Example:

            hello.c:5:12: error: undeclared identifier 'printt'
                printt("Hello");
                       ^^^^^^
            hint: did you mean 'print'?
        """
        parts = []

        # Location prefix: filename:line:column: error: message
        if self.location:
            parts.append(f"{self.location}: error: {self.message}")
        else:
            parts.append(f"error: {self.message}")

        # Source context with caret pointer
        if self.source_line is not None and self.location is not None:
            # Show the source line with indentation
            parts.append(f"    {self.source_line}")
            # Create caret pointer under the error location
            if self.location.column > 0:
                padding = " " * (4 + self.location.column - 1)
                parts.append(f"{padding}^")

        # Hint for fixing the error
        if self.hint:
            parts.append(f"hint: {self.hint}")

        return "\n".join(parts)


class SmallCCompilationError(SmallCError):
    """
    Aggregate compilation error containing multiple errors.

    Used when the compiler collects multiple errors during compilation
    and reports them together. The message is already a formatted report
    from ErrorReporter and should not have another prefix added.

    Unlike SmallCError which formats a single error with location and hint,
    this class passes through the pre-formatted aggregate report.
    """

    def _format_message(self) -> str:
        """Return message as-is - it's already a formatted aggregate report."""
        return self.message


# =============================================================================
# Syntax Errors (Lexer and Parser)
# =============================================================================

class CSyntaxError(SmallCError):
    """
    Syntax error in C source code.

    Raised when the lexer or parser encounters invalid syntax that
    cannot be tokenized or parsed according to C grammar.

    Examples:
        - Unterminated string literal
        - Missing semicolon
        - Invalid character in source
        - Mismatched parentheses
        - Invalid number format
    """
    pass


class UnterminatedStringError(CSyntaxError):
    """
    Unterminated string literal.

    Raised when a string literal is not properly closed before the
    end of the line or file.

    Example:
        char *s = "hello    // Missing closing quote
    """

    def __init__(
        self,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        super().__init__(
            "unterminated string literal",
            location=location,
            hint="add closing '\"' to complete the string",
            source_line=source_line,
        )


class InvalidCharacterError(CSyntaxError):
    """
    Invalid character in source code.

    Raised when the lexer encounters a character that is not
    valid in C source code.
    """

    def __init__(
        self,
        char: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.char = char
        super().__init__(
            f"invalid character '{char}' (0x{ord(char):02X})",
            location=location,
            source_line=source_line,
        )


class UnexpectedTokenError(CSyntaxError):
    """
    Unexpected token during parsing.

    Raised when the parser encounters a token that doesn't match
    the expected grammar rule.
    """

    def __init__(
        self,
        found: str,
        expected: Optional[str] = None,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.found = found
        self.expected = expected

        message = f"unexpected token '{found}'"
        hint = None
        if expected:
            hint = f"expected {expected}"

        super().__init__(
            message,
            location=location,
            hint=hint,
            source_line=source_line,
        )


class MissingTokenError(CSyntaxError):
    """
    Required token is missing.

    Raised when a required token (like ';' or ')') is not found
    where expected.
    """

    def __init__(
        self,
        expected: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.expected = expected
        super().__init__(
            f"expected '{expected}'",
            location=location,
            source_line=source_line,
        )


# =============================================================================
# Semantic Errors (Type Checking and Analysis)
# =============================================================================

class CSemanticError(SmallCError):
    """
    Semantic error in C source code.

    Raised during semantic analysis when the code is syntactically
    correct but violates language semantics.

    Examples:
        - Using an undeclared variable
        - Declaring a variable twice in same scope
        - Type mismatch in assignment
        - Wrong number of function arguments
    """
    pass


class UndeclaredIdentifierError(CSemanticError):
    """
    Reference to an undeclared identifier.

    Raised when a variable, function, or other identifier is used
    without being declared first.

    The compiler attempts to suggest similarly-named identifiers
    when this error occurs, helping to catch typos.
    """

    def __init__(
        self,
        identifier: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
        similar_identifiers: Optional[List[str]] = None,
    ):
        self.identifier = identifier
        self.similar_identifiers = similar_identifiers or []

        # Auto-generate hint if similar identifiers found
        hint = None
        if self.similar_identifiers:
            suggestions = ", ".join(f"'{s}'" for s in self.similar_identifiers[:3])
            hint = f"did you mean {suggestions}?"

        super().__init__(
            f"undeclared identifier '{identifier}'",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class DuplicateDeclarationError(CSemanticError):
    """
    Identifier declared multiple times in same scope.

    Raised when a variable, function, or parameter is declared
    more than once in the same scope.
    """

    def __init__(
        self,
        identifier: str,
        location: Optional[SourceLocation] = None,
        original_location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.identifier = identifier
        self.original_location = original_location

        hint = None
        if original_location:
            hint = f"'{identifier}' was first declared at {original_location}"

        super().__init__(
            f"redeclaration of '{identifier}'",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class CTypeError(CSemanticError):
    """
    Type mismatch or type-related error.

    Raised when:
        - Incompatible types in expression
        - Wrong type in assignment
        - Invalid type conversion
        - Pointer type mismatch
    """

    def __init__(
        self,
        message: str,
        expected_type: Optional[str] = None,
        actual_type: Optional[str] = None,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.expected_type = expected_type
        self.actual_type = actual_type

        hint = None
        if expected_type and actual_type:
            hint = f"expected '{expected_type}', got '{actual_type}'"

        super().__init__(
            message,
            location=location,
            hint=hint,
            source_line=source_line,
        )


class ArgumentCountError(CSemanticError):
    """
    Wrong number of arguments in function call.

    Raised when a function is called with a different number
    of arguments than declared in its definition.
    """

    def __init__(
        self,
        function_name: str,
        expected: int,
        actual: int,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.function_name = function_name
        self.expected = expected
        self.actual = actual

        word = "argument" if expected == 1 else "arguments"
        super().__init__(
            f"'{function_name}' expects {expected} {word}, got {actual}",
            location=location,
            source_line=source_line,
        )


class InvalidLValueError(CSemanticError):
    """
    Invalid left-hand side of assignment.

    Raised when the left side of an assignment is not a valid
    lvalue (something that can be assigned to).

    Examples of invalid lvalues:
        - 42 = x         // literal
        - (a + b) = x    // expression result
        - func() = x     // function return value
    """

    def __init__(
        self,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        super().__init__(
            "expression is not assignable (not an lvalue)",
            location=location,
            hint="left side of assignment must be a variable, array element, or dereferenced pointer",
            source_line=source_line,
        )


class InvalidBreakContinueError(CSemanticError):
    """
    break or continue outside of loop.

    Raised when 'break' or 'continue' is used outside of a
    while, for, or do-while loop (or switch for break).
    """

    def __init__(
        self,
        keyword: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.keyword = keyword
        context = "loop" if keyword == "continue" else "loop or switch"
        super().__init__(
            f"'{keyword}' statement not within a {context}",
            location=location,
            source_line=source_line,
        )


# =============================================================================
# Preprocessor Errors
# =============================================================================

class CPreprocessorError(SmallCError):
    """
    Error during preprocessing.

    Raised when the preprocessor encounters an error processing
    directives like #define, #include, #ifdef, etc.
    """
    pass


class CIncludeError(CPreprocessorError):
    """
    Error including a file.

    Raised when:
        - Include file not found
        - Circular include detected
        - Permission denied
    """

    def __init__(
        self,
        filename: str,
        reason: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
        search_paths: Optional[List[str]] = None,
    ):
        self.included_filename = filename
        self.reason = reason
        self.search_paths = search_paths or []

        hint = None
        if self.search_paths:
            paths_str = ", ".join(self.search_paths)
            hint = f"searched in: {paths_str}"

        super().__init__(
            f"cannot include '{filename}': {reason}",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class MacroExpansionError(CPreprocessorError):
    """
    Error expanding a macro.

    Raised when:
        - Wrong number of arguments to function-like macro
        - Recursive macro expansion detected
        - Unterminated macro argument
    """

    def __init__(
        self,
        macro_name: str,
        message: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.macro_name = macro_name
        super().__init__(
            f"error expanding macro '{macro_name}': {message}",
            location=location,
            source_line=source_line,
        )


# =============================================================================
# Code Generation Errors
# =============================================================================

class CCodeGenError(SmallCError):
    """
    Error during code generation.

    Raised when the code generator encounters a situation it
    cannot handle, such as:
        - Unsupported feature
        - Code too large
        - Internal error
    """
    pass


class UnsupportedFeatureError(CCodeGenError):
    """
    Unsupported language feature.

    Raised when the source code uses a C feature that is not
    supported by this Small-C implementation.

    Examples:
        - struct/union types
        - floating point
        - multi-dimensional arrays
    """

    def __init__(
        self,
        feature: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
        alternative: Optional[str] = None,
    ):
        self.feature = feature
        hint = alternative

        super().__init__(
            f"unsupported feature: {feature}",
            location=location,
            hint=hint,
            source_line=source_line,
        )


# =============================================================================
# Error Collection (for multi-error reporting)
# =============================================================================

class CErrorCollector:
    """
    Collects multiple errors for batch reporting.

    The compiler uses this to continue processing after encountering
    an error, collecting all errors before reporting them together.
    This helps users fix multiple issues without repeated compile runs.

    Example:
        collector = CErrorCollector(max_errors=100)

        for stmt in statements:
            try:
                compile_statement(stmt)
            except SmallCError as e:
                collector.add(e)
                if collector.should_stop():
                    break

        if collector.has_errors():
            print(collector.report())
    """

    def __init__(self, max_errors: int = 100):
        """
        Initialize the error collector.

        Args:
            max_errors: Maximum errors to collect before stopping
        """
        self.errors: List[SmallCError] = []
        self.warnings: List[str] = []
        self.max_errors = max_errors

    def add(self, error: SmallCError) -> None:
        """Add an error to the collection."""
        self.errors.append(error)

    def add_warning(self, message: str, location: Optional[SourceLocation] = None) -> None:
        """Add a warning message."""
        if location:
            self.warnings.append(f"{location}: warning: {message}")
        else:
            self.warnings.append(f"warning: {message}")

    def has_errors(self) -> bool:
        """Return True if any errors have been collected."""
        return len(self.errors) > 0

    def should_stop(self) -> bool:
        """Return True if max_errors has been reached."""
        return len(self.errors) >= self.max_errors

    def error_count(self) -> int:
        """Return the number of collected errors."""
        return len(self.errors)

    def warning_count(self) -> int:
        """Return the number of collected warnings."""
        return len(self.warnings)

    def report(self) -> str:
        """Format all errors and warnings for display."""
        lines = []

        # List all errors
        for error in self.errors:
            lines.append(str(error))
            lines.append("")  # Blank line between errors

        # List all warnings
        if self.warnings:
            for warning in self.warnings:
                lines.append(warning)

        # Summary line
        error_word = "error" if len(self.errors) == 1 else "errors"
        warning_word = "warning" if len(self.warnings) == 1 else "warnings"
        lines.append(
            f"\n{len(self.errors)} {error_word}, {len(self.warnings)} {warning_word}"
        )

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all collected errors and warnings."""
        self.errors.clear()
        self.warnings.clear()

    def raise_if_errors(self) -> None:
        """Raise a SmallCCompilationError if any errors were collected."""
        if self.has_errors():
            raise SmallCCompilationError(self.report())
