"""
Psion Testing Framework - Exception Classes
============================================

Custom exceptions for the automated testing framework. These provide
clear, actionable error messages when tests fail or encounter issues.

Exception Hierarchy:
    PsionTestError (base)
    ├── TestTimeoutError       - Waited too long for something
    ├── TestAssertionError     - Assertion failed
    ├── TestSetupError         - Error during test setup
    ├── ProgramBuildError      - Failed to compile test program
    └── ROMNotAvailableError   - ROM files not found

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from typing import Optional, List, Dict, Any


class PsionTestError(Exception):
    """
    Base exception for all Psion testing framework errors.

    All testing-specific exceptions inherit from this class,
    making it easy to catch any testing error.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize test error with message and optional context.

        Args:
            message: Human-readable error description
            context: Additional diagnostic information (display state, cycles, etc.)
        """
        super().__init__(message)
        self.context = context or {}


class TestTimeoutError(PsionTestError):
    """
    Raised when an operation times out.

    This includes waiting for text to appear, waiting for idle state,
    or any other operation that has a maximum cycle limit.
    """

    def __init__(
        self,
        message: str,
        *,
        expected: str = None,
        timeout_cycles: int = None,
        actual_display: List[str] = None,
        total_cycles: int = None,
    ):
        """
        Initialize timeout error with diagnostic details.

        Args:
            message: Description of what timed out
            expected: What we were waiting for (text, state, etc.)
            timeout_cycles: Maximum cycles we waited
            actual_display: Display contents when timeout occurred
            total_cycles: Total cycles executed in the test
        """
        context = {
            "expected": expected,
            "timeout_cycles": timeout_cycles,
            "actual_display": actual_display,
            "total_cycles": total_cycles,
        }
        super().__init__(message, context)
        self.expected = expected
        self.timeout_cycles = timeout_cycles
        self.actual_display = actual_display
        self.total_cycles = total_cycles


class TestAssertionError(PsionTestError, AssertionError):
    """
    Raised when a test assertion fails.

    Inherits from both PsionTestError (for context) and AssertionError
    (for pytest compatibility).
    """

    def __init__(
        self,
        message: str,
        *,
        assertion_type: str = None,
        expected: Any = None,
        actual: Any = None,
        display_state: List[str] = None,
        cursor_position: tuple = None,
        registers: Dict[str, int] = None,
        custom_message: str = None,
    ):
        """
        Initialize assertion error with full diagnostic context.

        Args:
            message: Description of the failed assertion
            assertion_type: Type of assertion (display_contains, memory_byte, etc.)
            expected: Expected value
            actual: Actual value found
            display_state: Current display contents
            cursor_position: Current cursor (row, col)
            registers: Current CPU register values
            custom_message: User-provided custom message
        """
        context = {
            "assertion_type": assertion_type,
            "expected": expected,
            "actual": actual,
            "display_state": display_state,
            "cursor_position": cursor_position,
            "registers": registers,
            "custom_message": custom_message,
        }
        super().__init__(message, context)
        self.assertion_type = assertion_type
        self.expected = expected
        self.actual = actual
        self.display_state = display_state
        self.cursor_position = cursor_position
        self.registers = registers
        self.custom_message = custom_message


class TestSetupError(PsionTestError):
    """
    Raised when test setup fails.

    This includes creating emulators, loading programs, booting, etc.
    """

    def __init__(
        self,
        message: str,
        *,
        phase: str = None,
        model: str = None,
        cause: Exception = None,
    ):
        """
        Initialize setup error.

        Args:
            message: Description of setup failure
            phase: Setup phase that failed (create_emulator, boot, load_program)
            model: Emulator model being created
            cause: Underlying exception if any
        """
        context = {
            "phase": phase,
            "model": model,
            "cause": str(cause) if cause else None,
        }
        super().__init__(message, context)
        self.phase = phase
        self.model = model
        self.cause = cause


class ProgramBuildError(PsionTestError):
    """
    Raised when compiling a test program fails.

    This includes both compilation errors (pscc) and assembly errors (psasm).
    """

    def __init__(
        self,
        message: str,
        *,
        source_path: str = None,
        build_command: str = None,
        stdout: str = None,
        stderr: str = None,
        return_code: int = None,
    ):
        """
        Initialize build error.

        Args:
            message: Description of build failure
            source_path: Path to source file
            build_command: Command that was executed
            stdout: Standard output from build
            stderr: Standard error from build
            return_code: Process return code
        """
        context = {
            "source_path": source_path,
            "build_command": build_command,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }
        super().__init__(message, context)
        self.source_path = source_path
        self.build_command = build_command
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code


class ROMNotAvailableError(PsionTestError):
    """
    Raised when ROM files are required but not found.

    This is typically caught by the @requires_rom decorator to skip tests.
    """

    def __init__(
        self,
        message: str = "ROM files not available",
        *,
        search_paths: List[str] = None,
        model: str = None,
    ):
        """
        Initialize ROM not available error.

        Args:
            message: Description
            search_paths: Paths that were searched
            model: Model requiring the ROM
        """
        context = {
            "search_paths": search_paths,
            "model": model,
        }
        super().__init__(message, context)
        self.search_paths = search_paths
        self.model = model
