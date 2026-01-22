"""
Psion Testing Framework - Test Context
======================================

The PsionTestContext is the central class of the testing framework.
It wraps an Emulator instance and provides:

- Multi-level action APIs (atomic, primitive, smart, compound)
- Fluent assertions that return self for chaining
- Action logging for diagnostic purposes
- Wait operations with intelligent timeout handling

Granularity Levels:
    Level 1 (Atomic): run_cycles(), step(), read_byte(), write_byte()
    Level 2 (Primitive): tap_key()
    Level 3 (Smart): press(), type_text(), wait_for(), wait_until_idle()
    Level 4 (Compound): enter_text_and_confirm(), navigate_menu()

Usage:
    @psion_test(requires_boot=True)
    def test_example(ctx: PsionTestContext):
        ctx.press("P").press("EXE")
        ctx.wait_for("PROG")
        ctx.assert_display_contains("New")

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Tuple, Optional, Any
import re

from psion_sdk.emulator import Emulator

from .config import TestConfig, get_default_config
from .diagnostics import TestDiagnostics, ActionLogEntry
from .exceptions import (
    TestTimeoutError,
    TestAssertionError,
    PsionTestError,
)

if TYPE_CHECKING:
    pass


class PsionTestContext:
    """
    Test context providing multi-level testing operations.

    This class wraps an Emulator instance with testing-focused operations
    at multiple granularity levels. All action methods return self for
    fluent chaining.

    The context automatically logs all actions for diagnostic purposes.
    When an assertion fails, the action log helps understand what
    happened leading up to the failure.

    Attributes:
        emulator: The wrapped Emulator instance
        config: Test configuration (timing, paths, etc.)

    Example:
        @psion_test(requires_boot=True)
        def test_menu_navigation(ctx: PsionTestContext):
            # Level 3 (Smart) - most tests use this level
            ctx.press("P").press("EXE")
            ctx.wait_for("PROG")
            ctx.assert_display_contains("New")

            # Level 4 (Compound) - convenience methods
            ctx.navigate_menu("CALC")
            ctx.enter_text_and_confirm("123+456")
            ctx.assert_display_contains("579")
    """

    def __init__(
        self,
        emulator: Emulator,
        config: Optional[TestConfig] = None,
    ):
        """
        Initialize test context.

        Args:
            emulator: The Emulator instance to wrap
            config: Test configuration (default: global config)
        """
        self.emulator = emulator
        self.config = config or get_default_config()
        self._diagnostics = TestDiagnostics(self)

    # ═══════════════════════════════════════════════════════════════════════════
    # PROPERTIES - Read-only state access
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def display(self) -> List[str]:
        """
        Current display lines (list of strings).

        Each string represents one line of the display.
        2-line displays return 2 strings, 4-line displays return 4.
        """
        return self.emulator.display_lines

    @property
    def display_text(self) -> str:
        """
        All display lines joined with newlines.

        Useful for substring searching across the entire display.
        """
        return self.emulator.display_text

    @property
    def cursor(self) -> Tuple[int, int]:
        """
        Current cursor position as (row, col).

        Position is 0-indexed. Row 0 is top line, col 0 is leftmost.
        """
        # Read cursor position from system variables
        # DPB_CPOS at $62 contains linear position
        # DPB_CUST at $63 contains cursor state
        try:
            pos = self.emulator.read_byte(0x62)
            rows, cols = self.config.get_display_dimensions(self.model)
            row = pos // cols
            col = pos % cols
            return (row, col)
        except Exception:
            return (0, 0)

    @property
    def cursor_visible(self) -> bool:
        """Whether cursor is currently visible."""
        try:
            state = self.emulator.read_byte(0x63)
            return bool(state & 0x80)  # Bit 7 indicates visibility
        except Exception:
            return True

    @property
    def registers(self) -> Dict[str, int]:
        """
        Current CPU register values.

        Returns dict with keys: a, b, d, x, sp, pc, flag_c, flag_v, etc.
        """
        cpu = self.emulator.cpu
        return {
            "a": cpu.a,
            "b": cpu.b,
            "d": cpu.d,
            "x": cpu.x,
            "sp": cpu.sp,
            "pc": cpu.pc,
            "flag_c": 1 if cpu.flag_c else 0,
            "flag_v": 1 if cpu.flag_v else 0,
            "flag_z": 1 if cpu.flag_z else 0,
            "flag_n": 1 if cpu.flag_n else 0,
            "flag_i": 1 if cpu.flag_i else 0,
            "flag_h": 1 if cpu.flag_h else 0,
        }

    @property
    def model(self) -> str:
        """Emulator model name (CM, XP, LZ, LZ64)."""
        return self.emulator.model.model_type

    @property
    def total_cycles(self) -> int:
        """Total cycles executed since reset."""
        return self.emulator.total_cycles

    @property
    def action_log(self) -> List[ActionLogEntry]:
        """Log of all actions performed (for diagnostics)."""
        return self._diagnostics.action_log

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 1: ATOMIC OPERATIONS - Direct emulator control
    # ═══════════════════════════════════════════════════════════════════════════

    def run_cycles(self, cycles: int) -> "PsionTestContext":
        """
        Execute exact number of CPU cycles.

        Use for timing-critical code or when you need deterministic execution.
        Most tests should prefer smart actions with automatic waiting.

        Args:
            cycles: Exact number of cycles to execute

        Returns:
            self (for chaining)
        """
        self._diagnostics.log_action_start("run_cycles", str(cycles))
        self.emulator.run(cycles)
        self._diagnostics.log_action_end("success")
        return self

    def step(self) -> "PsionTestContext":
        """
        Execute exactly one CPU instruction.

        Useful for debugging or instruction-level verification.
        Note: step() bypasses breakpoints (for deterministic behavior).

        Returns:
            self (for chaining)
        """
        self._diagnostics.log_action_start("step", "")
        self.emulator.step()
        self._diagnostics.log_action_end("success")
        return self

    def read_byte(self, address: int) -> int:
        """
        Read single byte from memory.

        Args:
            address: Memory address (0x0000-0xFFFF)

        Returns:
            Byte value (0-255)
        """
        return self.emulator.read_byte(address)

    def write_byte(self, address: int, value: int) -> "PsionTestContext":
        """
        Write single byte to memory.

        Args:
            address: Memory address (0x0000-0xFFFF)
            value: Byte value (0-255)

        Returns:
            self (for chaining)
        """
        self.emulator.write_byte(address, value)
        return self

    def read_word(self, address: int) -> int:
        """
        Read 16-bit word from memory (big-endian).

        Args:
            address: Memory address of high byte

        Returns:
            Word value (0-65535)
        """
        return self.emulator.read_word(address)

    def write_word(self, address: int, value: int) -> "PsionTestContext":
        """
        Write 16-bit word to memory (big-endian).

        Args:
            address: Memory address for high byte
            value: Word value (0-65535)

        Returns:
            self (for chaining)
        """
        self.emulator.write_word(address, value)
        return self

    def read_bytes(self, address: int, count: int) -> bytes:
        """
        Read multiple bytes from memory.

        Args:
            address: Starting address
            count: Number of bytes to read

        Returns:
            Bytes object with memory contents
        """
        return self.emulator.read_bytes(address, count)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 2: PRIMITIVE ACTIONS - Single UI interactions, no auto-wait
    # ═══════════════════════════════════════════════════════════════════════════

    def tap_key(
        self, key: str, hold_cycles: Optional[int] = None
    ) -> "PsionTestContext":
        """
        Press and release a key without waiting for UI response.

        Use when you need precise control over key timing or when
        testing key matrix behavior. For most tests, use press() instead.

        Args:
            key: Key name (A-Z, 0-9, EXE, MODE, ON, UP, DOWN, LEFT, RIGHT, DEL)
            hold_cycles: How long to hold key (default: from config)

        Returns:
            self (for chaining)
        """
        hold = hold_cycles or self.config.default_hold_cycles
        self._diagnostics.log_action_start("tap_key", f'"{key}"')
        self.emulator.tap_key(key, hold_cycles=hold)
        self._diagnostics.log_action_end("success")
        return self

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 3: SMART ACTIONS - Single UI interactions with intelligent wait
    # ═══════════════════════════════════════════════════════════════════════════

    def press(
        self,
        key: str,
        *,
        hold_cycles: Optional[int] = None,
        wait: str = "idle",
    ) -> "PsionTestContext":
        """
        Press a key and wait for UI response.

        This is the PRIMARY method for key input in tests. It automatically
        waits for the system to process the keypress before returning.

        Args:
            key: Key name (A-Z, 0-9, EXE, MODE, ON, UP, DOWN, LEFT, RIGHT, DEL)
            hold_cycles: How long to hold key (default: from config)
            wait: Wait strategy after keypress:
                  - "idle": Wait until CPU enters idle loop (DEFAULT)
                  - "cycles:N": Wait exactly N cycles (e.g., "cycles:200000")
                  - "none": Don't wait (equivalent to tap_key)
                  - "text:XXX": Wait for text to appear (e.g., "text:DONE")

        Returns:
            self (for chaining)

        Raises:
            TestTimeoutError: If wait strategy times out

        Example:
            ctx.press("P").press("EXE")  # Navigate to PROG menu
            ctx.press("Y", wait="text:CONFIRM")  # Wait for confirmation
        """
        hold = hold_cycles or self.config.default_hold_cycles

        self._diagnostics.log_action_start("press", f'"{key}"')
        try:
            # Press the key
            self.emulator.tap_key(key, hold_cycles=hold)

            # Apply wait strategy
            self._apply_wait_strategy(wait)

            self._diagnostics.log_action_end("success")
        except TestTimeoutError as e:
            self._diagnostics.log_action_end("timeout", str(e))
            raise
        except Exception as e:
            self._diagnostics.log_action_end("failed", str(e))
            raise

        return self

    def type_text(
        self,
        text: str,
        *,
        delay_cycles: Optional[int] = None,
        wait: str = "idle",
    ) -> "PsionTestContext":
        """
        Type a string of characters.

        Each character is typed with a delay between keystrokes.
        After typing completes, the specified wait strategy is applied.

        Args:
            text: Characters to type (letters, numbers, punctuation)
            delay_cycles: Cycles between keypresses (default: from config)
            wait: Wait strategy after typing complete

        Returns:
            self (for chaining)

        Raises:
            TestTimeoutError: If wait strategy times out

        Example:
            ctx.type_text("HELLO").press("EXE")
        """
        delay = delay_cycles or self.config.default_delay_cycles

        self._diagnostics.log_action_start("type_text", f'"{text}"')
        try:
            # Use emulator's type_text method
            self.emulator.type_text(text, delay_cycles=delay)

            # Apply wait strategy
            self._apply_wait_strategy(wait)

            self._diagnostics.log_action_end("success")
        except TestTimeoutError as e:
            self._diagnostics.log_action_end("timeout", str(e))
            raise
        except Exception as e:
            self._diagnostics.log_action_end("failed", str(e))
            raise

        return self

    def wait_for(
        self,
        text: str,
        *,
        timeout_cycles: Optional[int] = None,
        poll_interval: Optional[int] = None,
        case_sensitive: bool = True,
    ) -> "PsionTestContext":
        """
        Wait until text appears on display.

        Polls the display at regular intervals until the specified text
        appears or timeout is reached.

        Args:
            text: Text to wait for
            timeout_cycles: Maximum cycles to wait (default: from config)
            poll_interval: Cycles between display checks (default: from config)
            case_sensitive: Whether to match case (default: True)

        Returns:
            self (for chaining)

        Raises:
            TestTimeoutError: If text doesn't appear within timeout

        Example:
            ctx.wait_for("FIND")  # Wait for main menu
        """
        timeout = timeout_cycles or self.config.default_timeout_cycles
        interval = poll_interval or self.config.default_poll_interval

        self._diagnostics.log_action_start("wait_for", f'"{text}"')
        try:
            start_cycles = self.total_cycles

            while (self.total_cycles - start_cycles) < timeout:
                display_text = self.display_text
                if not case_sensitive:
                    display_text = display_text.upper()
                    text_to_find = text.upper()
                else:
                    text_to_find = text

                if text_to_find in display_text:
                    self._diagnostics.log_action_end("success")
                    return self

                # Run more cycles
                self.emulator.run(interval)

            # Timeout
            raise TestTimeoutError(
                f"Text '{text}' did not appear within {timeout:,} cycles",
                expected=text,
                timeout_cycles=timeout,
                actual_display=self.display,
                total_cycles=self.total_cycles,
            )

        except TestTimeoutError:
            self._diagnostics.log_action_end(
                "timeout", f"'{text}' not found after {timeout:,} cycles"
            )
            raise

    def wait_until_idle(
        self,
        *,
        max_cycles: Optional[int] = None,
        idle_threshold: Optional[int] = None,
    ) -> "PsionTestContext":
        """
        Wait until CPU enters idle loop (waiting for input).

        The emulator detects idle by tracking PC values. When the PC
        stays in the same small region for many consecutive samples,
        the CPU is considered idle (waiting for keyboard input).

        Args:
            max_cycles: Maximum cycles to wait (default: from config)
            idle_threshold: Cycles in same region to consider idle

        Returns:
            self (for chaining)

        Raises:
            TestTimeoutError: If idle state not reached within max_cycles
        """
        timeout = max_cycles or self.config.default_timeout_cycles
        threshold = idle_threshold or self.config.default_idle_threshold

        self._diagnostics.log_action_start("wait_until_idle", "")
        try:
            start_cycles = self.total_cycles
            last_pc = self.emulator.cpu.pc
            idle_count = 0
            pc_region_size = 0x100  # Consider PCs within 256 bytes as "same region"

            while (self.total_cycles - start_cycles) < timeout:
                # Run a batch of cycles
                self.emulator.run(threshold // 10 or 100)

                current_pc = self.emulator.cpu.pc
                if abs(current_pc - last_pc) < pc_region_size:
                    idle_count += 1
                    if idle_count >= 10:  # Stayed in same region for 10 checks
                        self._diagnostics.log_action_end("success")
                        return self
                else:
                    idle_count = 0
                    last_pc = current_pc

            raise TestTimeoutError(
                f"CPU did not enter idle state within {timeout:,} cycles",
                timeout_cycles=timeout,
                actual_display=self.display,
                total_cycles=self.total_cycles,
            )

        except TestTimeoutError:
            self._diagnostics.log_action_end("timeout")
            raise

    def then(self) -> "PsionTestContext":
        """
        Semantic no-op for readability in fluent chains.

        This method does nothing but return self, allowing for more
        readable test code by adding natural language flow.

        Example:
            ctx.press("A").then().press("B")

        Returns:
            self (for chaining)
        """
        return self

    def _apply_wait_strategy(self, wait: str) -> None:
        """
        Apply a wait strategy after an action.

        Args:
            wait: Wait strategy string

        Raises:
            TestTimeoutError: If wait times out
            ValueError: If wait strategy is invalid
        """
        if wait == "idle":
            self.wait_until_idle()
        elif wait == "none":
            pass  # No waiting
        elif wait.startswith("cycles:"):
            try:
                cycles = int(wait[7:])
                self.emulator.run(cycles)
            except ValueError:
                raise ValueError(f"Invalid cycles in wait strategy: {wait}")
        elif wait.startswith("text:"):
            text = wait[5:]
            self.wait_for(text)
        else:
            raise ValueError(f"Unknown wait strategy: {wait}")

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 4: COMPOUND ACTIONS - Multi-step operations
    # ═══════════════════════════════════════════════════════════════════════════

    def enter_text_and_confirm(self, text: str) -> "PsionTestContext":
        """
        Type text and press EXE to confirm.

        Equivalent to: ctx.type_text(text).press("EXE")

        Args:
            text: Text to type before confirming

        Returns:
            self (for chaining)
        """
        return self.type_text(text).press("EXE")

    def navigate_menu(self, menu: str) -> "PsionTestContext":
        """
        Navigate to a menu item by pressing its first letter and EXE.

        This is a quick way to select menu items. The Psion OS allows
        selecting menu items by pressing their first letter.

        Args:
            menu: Menu name (e.g., "PROG", "CALC", "FIND")

        Returns:
            self (for chaining)

        Example:
            ctx.navigate_menu("PROG")  # Equivalent to press("P").press("EXE")
        """
        first_letter = menu[0].upper()
        return self.press(first_letter).press("EXE")

    def select_drive(self, drive: str) -> "PsionTestContext":
        """
        Select a drive by pressing MODE until it appears.

        On drive selection prompts, pressing MODE cycles through
        available drives (A: -> B: -> C: -> A: ...)

        Args:
            drive: Drive name (e.g., "A:", "B:", "C:")

        Returns:
            self (for chaining)

        Raises:
            TestTimeoutError: If drive doesn't appear after max attempts
        """
        # Try up to 4 times (more than number of drives)
        for _ in range(4):
            if drive in self.display_text:
                return self
            self.press("MODE")

        raise TestTimeoutError(
            f"Drive '{drive}' did not appear after pressing MODE",
            expected=drive,
            actual_display=self.display,
        )

    def go_up(self, count: int = 1) -> "PsionTestContext":
        """
        Press UP key count times.

        Args:
            count: Number of times to press UP

        Returns:
            self (for chaining)
        """
        for _ in range(count):
            self.press("UP")
        return self

    def go_down(self, count: int = 1) -> "PsionTestContext":
        """
        Press DOWN key count times.

        Args:
            count: Number of times to press DOWN

        Returns:
            self (for chaining)
        """
        for _ in range(count):
            self.press("DOWN")
        return self

    def go_left(self, count: int = 1) -> "PsionTestContext":
        """
        Press LEFT key count times.

        Args:
            count: Number of times to press LEFT

        Returns:
            self (for chaining)
        """
        for _ in range(count):
            self.press("LEFT")
        return self

    def go_right(self, count: int = 1) -> "PsionTestContext":
        """
        Press RIGHT key count times.

        Args:
            count: Number of times to press RIGHT

        Returns:
            self (for chaining)
        """
        for _ in range(count):
            self.press("RIGHT")
        return self

    # ═══════════════════════════════════════════════════════════════════════════
    # ASSERTIONS - All return self for chaining
    # ═══════════════════════════════════════════════════════════════════════════

    def assert_display_contains(
        self, text: str, *, case_sensitive: bool = True, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert text appears somewhere on display.

        Args:
            text: Text to search for
            case_sensitive: If False, ignore case when matching (default: True)
                           Use False for cross-model tests (LZ shows "Find" not "FIND")
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If text not found
        """
        self._diagnostics.log_action_start("assert_display_contains", f'"{text}"')

        display_text = self.display_text
        text_to_find = text
        if not case_sensitive:
            display_text = display_text.upper()
            text_to_find = text.upper()

        if text_to_find in display_text:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Display does not contain '{text}'"
        error = TestAssertionError(
            error_msg,
            assertion_type="display_contains",
            expected=text,
            actual=self.display_text,
            display_state=self.display,
            cursor_position=self.cursor,
            registers=self.registers,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_display_not_contains(
        self, text: str, *, case_sensitive: bool = True, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert text does NOT appear on display.

        Args:
            text: Text that should be absent
            case_sensitive: If False, ignore case when matching (default: True)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If text is found
        """
        self._diagnostics.log_action_start("assert_display_not_contains", f'"{text}"')

        display_text = self.display_text
        text_to_find = text
        if not case_sensitive:
            display_text = display_text.upper()
            text_to_find = text.upper()

        if text_to_find not in display_text:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Display unexpectedly contains '{text}'"
        error = TestAssertionError(
            error_msg,
            assertion_type="display_not_contains",
            expected=f"NOT '{text}'",
            actual=self.display_text,
            display_state=self.display,
            cursor_position=self.cursor,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_display_line(
        self,
        line: int,
        expected: str,
        *,
        exact: bool = False,
        msg: Optional[str] = None,
    ) -> "PsionTestContext":
        """
        Assert specific display line matches expected.

        Args:
            line: Line number (0-based, 0-1 for 2-line, 0-3 for 4-line)
            expected: Expected text (or pattern if not exact)
            exact: If True, entire line must match exactly
                   If False, line must contain expected text
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If line doesn't match
        """
        self._diagnostics.log_action_start(
            "assert_display_line", f'{line}, "{expected}", exact={exact}'
        )

        lines = self.display
        if line < 0 or line >= len(lines):
            error_msg = f"Line {line} out of range (display has {len(lines)} lines)"
            error = TestAssertionError(
                error_msg,
                assertion_type="display_line",
                expected=expected,
                actual=f"Line {line} does not exist",
                display_state=lines,
                custom_message=msg,
            )
            self._diagnostics.log_action_end("failed", error_msg)
            self._handle_assertion_failure(error)
            raise error

        actual_line = lines[line]

        if exact:
            # Exact match (strip trailing spaces for comparison)
            match = actual_line.rstrip() == expected.rstrip()
        else:
            # Contains check
            match = expected in actual_line

        if match:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        match_type = "equal to" if exact else "contain"
        error_msg = msg or f"Line {line} expected to {match_type} '{expected}', got '{actual_line}'"
        error = TestAssertionError(
            error_msg,
            assertion_type="display_line",
            expected=expected,
            actual=actual_line,
            display_state=lines,
            cursor_position=self.cursor,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_display_matches(
        self, pattern: str, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert display matches regex pattern.

        The pattern is matched against the entire display text
        (all lines joined with newlines).

        Args:
            pattern: Regex pattern to match
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If pattern doesn't match

        Example:
            ctx.assert_display_matches(r"Score:\\s+\\d+")
        """
        self._diagnostics.log_action_start("assert_display_matches", f'"{pattern}"')

        display_text = self.display_text
        if re.search(pattern, display_text):
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Display does not match pattern '{pattern}'"
        error = TestAssertionError(
            error_msg,
            assertion_type="display_matches",
            expected=pattern,
            actual=display_text,
            display_state=self.display,
            cursor_position=self.cursor,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_cursor_at(
        self, row: int, col: int, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert cursor is at specific position.

        Args:
            row: Expected row (0-based)
            col: Expected column (0-based)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If cursor not at expected position
        """
        self._diagnostics.log_action_start("assert_cursor_at", f"{row}, {col}")

        actual = self.cursor
        if actual == (row, col):
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Cursor expected at ({row}, {col}), got {actual}"
        error = TestAssertionError(
            error_msg,
            assertion_type="cursor_at",
            expected=(row, col),
            actual=actual,
            display_state=self.display,
            cursor_position=actual,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_cursor_visible(
        self, visible: bool = True, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert cursor visibility state.

        Args:
            visible: Expected visibility (True = visible)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If cursor visibility doesn't match
        """
        self._diagnostics.log_action_start("assert_cursor_visible", str(visible))

        actual = self.cursor_visible
        if actual == visible:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        expected_str = "visible" if visible else "hidden"
        actual_str = "visible" if actual else "hidden"
        error_msg = msg or f"Cursor expected {expected_str}, got {actual_str}"
        error = TestAssertionError(
            error_msg,
            assertion_type="cursor_visible",
            expected=visible,
            actual=actual,
            display_state=self.display,
            cursor_position=self.cursor,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_memory(
        self, address: int, expected: bytes, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert memory contents at address match expected bytes.

        Args:
            address: Starting memory address (0x0000-0xFFFF)
            expected: Expected byte sequence
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If memory doesn't match

        Example:
            ctx.assert_memory(0x2100, b"\\x42\\x43\\x44")
        """
        self._diagnostics.log_action_start(
            "assert_memory", f"0x{address:04X}, {len(expected)} bytes"
        )

        actual = self.read_bytes(address, len(expected))
        if actual == expected:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Memory at ${address:04X} doesn't match expected"
        error = TestAssertionError(
            error_msg,
            assertion_type="memory",
            expected=expected.hex(),
            actual=actual.hex(),
            display_state=self.display,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_memory_byte(
        self, address: int, expected: int, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert single byte at address equals expected.

        Args:
            address: Memory address
            expected: Expected byte value (0-255)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If byte doesn't match
        """
        self._diagnostics.log_action_start(
            "assert_memory_byte", f"0x{address:04X}, 0x{expected:02X}"
        )

        actual = self.read_byte(address)
        if actual == expected:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Memory byte at ${address:04X}: expected ${expected:02X}, got ${actual:02X}"
        error = TestAssertionError(
            error_msg,
            assertion_type="memory_byte",
            expected=f"${expected:02X}",
            actual=f"${actual:02X}",
            display_state=self.display,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_memory_word(
        self, address: int, expected: int, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert 16-bit word at address equals expected (big-endian).

        Args:
            address: Memory address (high byte)
            expected: Expected word value (0-65535)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If word doesn't match
        """
        self._diagnostics.log_action_start(
            "assert_memory_word", f"0x{address:04X}, 0x{expected:04X}"
        )

        actual = self.read_word(address)
        if actual == expected:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        error_msg = msg or f"Memory word at ${address:04X}: expected ${expected:04X}, got ${actual:04X}"
        error = TestAssertionError(
            error_msg,
            assertion_type="memory_word",
            expected=f"${expected:04X}",
            actual=f"${actual:04X}",
            display_state=self.display,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_register(
        self, register: str, expected: int, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert CPU register equals expected value.

        Args:
            register: Register name (a, b, d, x, sp, pc)
            expected: Expected value
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If register doesn't match

        Example:
            ctx.assert_register("a", 0x42)
        """
        self._diagnostics.log_action_start(
            "assert_register", f'"{register}", 0x{expected:X}'
        )

        regs = self.registers
        reg_key = register.lower()
        if reg_key not in regs:
            error_msg = f"Unknown register: {register}"
            error = TestAssertionError(error_msg, assertion_type="register")
            self._diagnostics.log_action_end("failed", error_msg)
            raise error

        actual = regs[reg_key]
        if actual == expected:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        if reg_key in ("a", "b"):
            error_msg = msg or f"Register {register.upper()}: expected ${expected:02X}, got ${actual:02X}"
        else:
            error_msg = msg or f"Register {register.upper()}: expected ${expected:04X}, got ${actual:04X}"

        error = TestAssertionError(
            error_msg,
            assertion_type="register",
            expected=expected,
            actual=actual,
            registers=regs,
            display_state=self.display,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def assert_flag(
        self, flag: str, expected: bool, *, msg: Optional[str] = None
    ) -> "PsionTestContext":
        """
        Assert CPU flag state.

        Args:
            flag: Flag name (c, v, z, n, i, h)
            expected: Expected state (True = set)
            msg: Optional custom failure message

        Returns:
            self (for chaining)

        Raises:
            TestAssertionError: If flag doesn't match
        """
        self._diagnostics.log_action_start("assert_flag", f'"{flag}", {expected}')

        regs = self.registers
        flag_key = f"flag_{flag.lower()}"
        if flag_key not in regs:
            error_msg = f"Unknown flag: {flag}"
            error = TestAssertionError(error_msg, assertion_type="flag")
            self._diagnostics.log_action_end("failed", error_msg)
            raise error

        actual = bool(regs[flag_key])
        if actual == expected:
            self._diagnostics.log_action_end("success")
            return self

        # Assertion failed
        expected_str = "set" if expected else "clear"
        actual_str = "set" if actual else "clear"
        error_msg = msg or f"Flag {flag.upper()}: expected {expected_str}, got {actual_str}"
        error = TestAssertionError(
            error_msg,
            assertion_type="flag",
            expected=expected,
            actual=actual,
            registers=regs,
            display_state=self.display,
            custom_message=msg,
        )
        self._diagnostics.log_action_end("failed", error_msg)
        self._handle_assertion_failure(error)
        raise error

    def _handle_assertion_failure(self, error: TestAssertionError) -> None:
        """
        Handle an assertion failure by capturing diagnostics.

        This is called automatically when any assertion fails.

        Args:
            error: The assertion error
        """
        # Capture screenshot if configured
        screenshot_path = None
        if self.config.capture_screenshots_on_failure:
            screenshot_path = self._diagnostics.capture_screenshot()

        # Format and print failure report
        report = self._diagnostics.format_failure_report(error, screenshot_path)
        print("\n" + report + "\n")
