"""
Psion SDK Error Hierarchy
=========================

This module defines the exception hierarchy for the entire Psion SDK.
All exceptions inherit from PsionError, allowing callers to catch all
SDK-related errors with a single except clause if desired.

Exception Hierarchy
-------------------
PsionError (base)
├── AssemblerError (assembler-related)
│   ├── AssemblySyntaxError - syntax errors in source
│   ├── UndefinedSymbolError - reference to undefined label/symbol
│   ├── DuplicateSymbolError - symbol defined multiple times
│   ├── AddressingModeError - invalid addressing mode for instruction
│   ├── BranchRangeError - branch target too far
│   ├── ExpressionError - error evaluating expression
│   ├── DirectiveError - error in assembler directive
│   ├── MacroError - error in macro definition/expansion
│   └── IncludeError - error including file
├── OPKError (OPK file handling)
│   ├── OPKFormatError - invalid OPK file format
│   └── PackSizeError - pack size invalid
└── CommsError (serial communication)
    ├── ConnectionError - cannot connect to device
    ├── TransferError - error during file transfer
    └── ProtocolError - link protocol error

Design Philosophy
-----------------
Each exception captures source location information (filename, line, column)
when applicable. This allows for detailed error messages that help users
quickly locate and fix issues in their source code.

Error messages follow this format:
    filename:line:column: error: description
    source_line_text
        ^^^^^ (pointer to error location)
    hint: suggestion for fixing (when available)
"""

from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Base Exception Class
# =============================================================================

class PsionError(Exception):
    """
    Base exception for all Psion SDK errors.

    All exceptions in the SDK inherit from this class, allowing callers
    to catch all SDK-related errors with a single except clause:

        try:
            assembler.assemble_file("program.asm")
        except PsionError as e:
            print(f"Error: {e}")
    """
    pass


# =============================================================================
# Source Location Tracking
# =============================================================================

@dataclass(frozen=True)
class SourceLocation:
    """
    Represents a location in source code for error reporting.

    This class is used throughout the assembler to track where tokens,
    statements, and errors occur in the source file. The immutable
    (frozen) design ensures locations cannot be accidentally modified.

    Attributes:
        filename: Name of the source file (or "<input>" for string input)
        line: Line number (1-indexed)
        column: Column number (1-indexed)
    """
    filename: str
    line: int
    column: int

    def __str__(self) -> str:
        """Format as 'filename:line:column' for error messages."""
        return f"{self.filename}:{self.line}:{self.column}"


# =============================================================================
# Assembler Exceptions
# =============================================================================

class AssemblerError(PsionError):
    """
    Base exception for all assembler-related errors.

    This class provides common functionality for error messages including
    source location tracking and optional hint messages.

    Attributes:
        message: The error description
        location: Where in the source the error occurred (optional)
        hint: A suggestion for fixing the error (optional)
        source_line: The actual source text at the error location (optional)
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

        Example output:
            hello.asm:15:9: error: undefined symbol 'prnt_char'
                JSR     prnt_char
                        ^^^^^^^^^
            hint: did you mean 'print_char'?
        """
        parts = []

        # Location prefix
        if self.location:
            parts.append(f"{self.location}: error: {self.message}")
        else:
            parts.append(f"error: {self.message}")

        # Source context with caret pointer
        if self.source_line is not None and self.location is not None:
            parts.append(f"    {self.source_line}")
            # Create caret pointer under the error location
            if self.location.column > 0:
                # Point to the column position
                padding = " " * (4 + self.location.column - 1)
                parts.append(f"{padding}^")

        # Hint for fixing
        if self.hint:
            parts.append(f"hint: {self.hint}")

        return "\n".join(parts)


class AssemblySyntaxError(AssemblerError):
    """
    Syntax error in assembly source code.

    Raised when the lexer or parser encounters invalid syntax that
    cannot be tokenized or parsed according to the assembly grammar.

    Examples:
        - Invalid character in source
        - Unterminated string literal
        - Missing operand
        - Invalid number format
    """
    pass


class UndefinedSymbolError(AssemblerError):
    """
    Reference to an undefined symbol (label or constant).

    Raised during the second pass of assembly when a symbol reference
    cannot be resolved because no definition was found.

    The assembler attempts to suggest similarly-named symbols when
    this error occurs, helping to catch typos.
    """

    def __init__(
        self,
        symbol: str,
        location: Optional[SourceLocation] = None,
        hint: Optional[str] = None,
        source_line: Optional[str] = None,
        similar_symbols: Optional[list[str]] = None,
    ):
        self.symbol = symbol
        self.similar_symbols = similar_symbols or []

        # Auto-generate hint if similar symbols found
        if not hint and self.similar_symbols:
            suggestions = ", ".join(f"'{s}'" for s in self.similar_symbols[:3])
            hint = f"did you mean {suggestions}?"

        super().__init__(
            f"undefined symbol '{symbol}'",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class DuplicateSymbolError(AssemblerError):
    """
    Symbol defined multiple times.

    Raised when a label or constant is defined more than once in the
    source code. Includes information about the original definition
    location when available.
    """

    def __init__(
        self,
        symbol: str,
        location: Optional[SourceLocation] = None,
        original_location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.symbol = symbol
        self.original_location = original_location

        hint = None
        if original_location:
            hint = f"'{symbol}' was first defined at {original_location}"

        super().__init__(
            f"duplicate symbol '{symbol}'",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class AddressingModeError(AssemblerError):
    """
    Invalid addressing mode for instruction.

    Raised when an instruction is used with an addressing mode it
    doesn't support. For example, STAA with immediate mode (#) is
    invalid because you cannot store to a literal value.

    Example:
        STAA #$41  ; Error: STAA doesn't support immediate mode
    """

    def __init__(
        self,
        mnemonic: str,
        mode: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
        valid_modes: Optional[list[str]] = None,
    ):
        self.mnemonic = mnemonic
        self.mode = mode
        self.valid_modes = valid_modes or []

        hint = None
        if self.valid_modes:
            modes_str = ", ".join(self.valid_modes)
            hint = f"{mnemonic} supports: {modes_str}"

        super().__init__(
            f"'{mnemonic}' does not support {mode} addressing mode",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class BranchRangeError(AssemblerError):
    """
    Branch target is out of range.

    HD6303 branch instructions use PC-relative addressing with a
    signed 8-bit offset, limiting the range to -128 to +127 bytes
    from the instruction following the branch.

    When this error occurs, the user should consider:
    1. Moving code closer together
    2. Using JMP instead of branch (but loses conditional)
    3. Using a trampoline pattern:
           BEQ near_target
           ...
       near_target:
           JMP far_target
    """

    def __init__(
        self,
        target: str,
        offset: int,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
    ):
        self.target = target
        self.offset = offset

        direction = "forward" if offset > 0 else "backward"
        hint = (
            f"branch offset is {offset}, but range is -128 to +127; "
            f"consider using JMP for {direction} references"
        )

        super().__init__(
            f"branch target '{target}' is out of range (offset: {offset})",
            location=location,
            hint=hint,
            source_line=source_line,
        )


class ExpressionError(AssemblerError):
    """
    Error evaluating an expression.

    Raised when an arithmetic or logical expression cannot be
    evaluated, typically due to:
    - Division by zero
    - Unresolved forward reference in expression
    - Invalid operand type
    - Overflow in calculation
    """
    pass


class DirectiveError(AssemblerError):
    """
    Error in assembler directive.

    Raised when a directive (ORG, EQU, FCB, etc.) is used incorrectly
    or has invalid arguments.

    Examples:
        - ORG with non-constant expression
        - FCB with value > 255
        - FILL with negative count
    """
    pass


class MacroError(AssemblerError):
    """
    Error in macro definition or expansion.

    Raised when:
    - Macro is defined without ENDM
    - Macro is used before definition
    - Wrong number of arguments passed to macro
    - Recursive macro expansion detected
    """
    pass


class IncludeError(AssemblerError):
    """
    Error including a file.

    Raised when:
    - Include file not found
    - Circular include detected
    - Permission denied reading file
    """

    def __init__(
        self,
        filename: str,
        reason: str,
        location: Optional[SourceLocation] = None,
        source_line: Optional[str] = None,
        search_paths: Optional[list[str]] = None,
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


# =============================================================================
# OPK File Exceptions
# =============================================================================

class OPKError(PsionError):
    """Base exception for OPK file handling errors."""
    pass


class OPKFormatError(OPKError):
    """
    Invalid OPK file format.

    Raised when reading an OPK file that:
    - Missing or invalid magic bytes ("OPK")
    - Inconsistent length fields
    - Invalid record types
    - Corrupted data
    """
    pass


class PackSizeError(OPKError):
    """
    Invalid pack size.

    Pack sizes must be valid powers of 2 in the range 8KB to 128KB.
    Valid sizes: 8, 16, 32, 64, 128 (in KB).
    """
    pass


# =============================================================================
# Communication Exceptions
# =============================================================================

class CommsError(PsionError):
    """Base exception for serial communication errors."""
    pass


class ConnectionError(CommsError):
    """
    Cannot connect to Psion device.

    Raised when:
    - Serial port not found
    - Permission denied
    - Device not responding
    """
    pass


class TransferError(CommsError):
    """
    Error during file transfer.

    Raised when:
    - CRC mismatch
    - Timeout waiting for response
    - Transfer cancelled by device
    """
    pass


class ProtocolError(CommsError):
    """
    Link protocol error.

    Raised when the device sends an unexpected response or the
    protocol state machine enters an invalid state.
    """
    pass


class TimeoutError(CommsError):
    """
    Communication timeout error.

    Raised when an operation times out waiting for a response
    from the Psion device. This could indicate:
    - Device not in COMMS mode
    - Cable disconnected
    - Incorrect baud rate setting
    - Hardware or driver issue

    Note:
        This is a Psion-specific TimeoutError, distinct from the
        Python builtin TimeoutError. It inherits from CommsError
        for consistent error handling in the comms module.
    """
    pass


class CRCError(TransferError):
    """
    CRC verification failed.

    Raised when the CRC checksum in a received packet doesn't
    match the calculated checksum. This indicates data corruption
    during transmission.

    The link protocol should automatically retry on CRC errors,
    so this exception typically means repeated failures.
    """

    def __init__(self, expected: int, actual: int, message: str = ""):
        self.expected = expected
        self.actual = actual
        if not message:
            message = f"CRC mismatch: expected {expected:04X}, got {actual:04X}"
        super().__init__(message)


class RemoteError(TransferError):
    """
    Error reported by the Psion device.

    Raised when the Psion sends a DISCONNECT packet with an error code.
    The error code indicates what went wrong on the device side.

    Common error codes:
    - 185: Record too long
    - 186: Disk full
    - 187: File exists
    - 188: Server error
    - 189: File not found
    - 190: Bad parameter
    """

    def __init__(self, code: int, message: str = ""):
        self.code = code
        if not message:
            message = self._default_message(code)
        super().__init__(message)

    @staticmethod
    def _default_message(code: int) -> str:
        """Get default message for known error codes."""
        messages = {
            190: "Bad parameter",
            189: "Remote file not found",
            188: "Server error",
            187: "Remote file exists",
            186: "Disk full",
            185: "Record too long",
        }
        return messages.get(code, f"Remote error ({code})")


# =============================================================================
# Error Collection for Multiple Error Reporting
# =============================================================================

class ErrorCollector:
    """
    Collects multiple errors for batch reporting.

    The assembler uses this to continue processing after encountering
    an error, collecting all errors before reporting them together.
    This helps users fix multiple issues without repeated assembly runs.

    Example:
        collector = ErrorCollector(max_errors=100)

        try:
            # ... assembly process ...
            if error_found:
                collector.add(UndefinedSymbolError(...))
        except TooManyErrors:
            pass  # Already logged max_errors

        if collector.has_errors():
            print(collector.report())
            sys.exit(1)
    """

    def __init__(self, max_errors: int = 100):
        """
        Initialize the error collector.

        Args:
            max_errors: Maximum errors to collect before raising TooManyErrors
        """
        self.errors: list[AssemblerError] = []
        self.warnings: list[str] = []
        self.max_errors = max_errors

    def add(self, error: AssemblerError) -> None:
        """
        Add an error to the collection.

        Args:
            error: The error to add

        Raises:
            TooManyErrors: If max_errors has been reached
        """
        self.errors.append(error)
        if len(self.errors) >= self.max_errors:
            raise TooManyErrors(f"Too many errors ({self.max_errors}), stopping")

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Return True if any errors have been collected."""
        return len(self.errors) > 0

    def error_count(self) -> int:
        """Return the number of collected errors."""
        return len(self.errors)

    def warning_count(self) -> int:
        """Return the number of collected warnings."""
        return len(self.warnings)

    def report(self) -> str:
        """
        Format all errors and warnings for display.

        Returns:
            Formatted string with all errors and warnings
        """
        lines = []

        for error in self.errors:
            lines.append(str(error))
            lines.append("")  # Blank line between errors

        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  {warning}")

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


class TooManyErrors(AssemblerError):
    """
    Raised when too many errors have been encountered.

    This prevents the assembler from running indefinitely when
    there are fundamental problems with the source code.
    """

    def __init__(self, message: str = "Too many errors"):
        super().__init__(message)
