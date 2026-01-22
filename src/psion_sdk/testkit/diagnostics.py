"""
Psion Testing Framework - Diagnostics
=====================================

Diagnostic utilities for test failure analysis including:
- Action logging with timing information
- Screenshot capture
- Comprehensive failure reports
- State capture for debugging

When a test fails, the diagnostics system captures everything needed
to understand what went wrong without re-running the test.

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any, Optional
import io

if TYPE_CHECKING:
    from .context import PsionTestContext


@dataclass
class ActionLogEntry:
    """
    Record of a single action performed during a test.

    Each action (press, type_text, wait_for, assertion) is logged with
    timing information and display state for post-mortem analysis.

    Attributes:
        index: Sequential action number (1-based for readability)
        action_type: Type of action (press, type_text, wait_for, assert_*)
        action_args: Human-readable argument summary (e.g., '"P"' or '"HELLO"')
        timestamp_cycles: Total cycles at start of action
        duration_cycles: Cycles consumed by this action
        result: "success", "failed", or "timeout"
        display_before: Display lines before action
        display_after: Display lines after action
        error_message: Error details if result != "success"
    """

    index: int
    action_type: str
    action_args: str
    timestamp_cycles: int
    duration_cycles: int = 0
    result: str = "success"
    display_before: List[str] = field(default_factory=list)
    display_after: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def format_short(self) -> str:
        """
        Format action as single-line summary.

        Returns:
            Formatted string like '[  3] press("P") → success (45,230 cycles)'
        """
        duration_str = f"{self.duration_cycles:,}" if self.duration_cycles > 0 else "0"
        result_str = self.result
        if self.result == "timeout":
            result_str = f"TIMEOUT after {duration_str} cycles"
        elif self.result == "failed":
            result_str = "FAILED"
        else:
            result_str = f"success ({duration_str} cycles)"

        return f"[{self.index:3}] {self.action_type}({self.action_args}) → {result_str}"

    def format_detailed(self) -> str:
        """
        Format action with full details including display state.

        Returns:
            Multi-line detailed description
        """
        lines = [self.format_short()]

        if self.display_before:
            lines.append("    Display before:")
            for i, line in enumerate(self.display_before):
                lines.append(f"      [{i}] {repr(line)}")

        if self.display_after and self.display_after != self.display_before:
            lines.append("    Display after:")
            for i, line in enumerate(self.display_after):
                lines.append(f"      [{i}] {repr(line)}")

        if self.error_message:
            lines.append(f"    Error: {self.error_message}")

        return "\n".join(lines)


class TestDiagnostics:
    """
    Diagnostic collector for test execution.

    Captures action history, screenshots, and state snapshots for
    generating comprehensive failure reports.

    Usage:
        diagnostics = TestDiagnostics(ctx)

        # Log actions as they happen
        diagnostics.log_action_start("press", '"P"')
        # ... action executes ...
        diagnostics.log_action_end("success")

        # On failure, generate report
        report = diagnostics.format_failure_report(error)
    """

    def __init__(self, ctx: "PsionTestContext"):
        """
        Initialize diagnostics for a test context.

        Args:
            ctx: The test context to monitor
        """
        self._ctx = ctx
        self._action_log: List[ActionLogEntry] = []
        self._current_action: Optional[ActionLogEntry] = None
        self._screenshots: List[bytes] = []
        self._test_name: Optional[str] = None
        self._start_time: datetime = datetime.now()

    @property
    def action_log(self) -> List[ActionLogEntry]:
        """Get the action log."""
        return self._action_log

    def set_test_name(self, name: str) -> None:
        """
        Set the current test name for reports.

        Args:
            name: Test function name
        """
        self._test_name = name

    def log_action_start(
        self,
        action_type: str,
        action_args: str,
    ) -> None:
        """
        Log the start of an action.

        Call this before executing an action to capture the "before" state.

        Args:
            action_type: Type of action (press, type_text, wait_for, etc.)
            action_args: Human-readable arguments
        """
        # Limit log size
        max_size = self._ctx.config.max_action_log_size
        if len(self._action_log) >= max_size:
            # Remove oldest entries, keeping last half
            self._action_log = self._action_log[max_size // 2 :]

        self._current_action = ActionLogEntry(
            index=len(self._action_log) + 1,
            action_type=action_type,
            action_args=action_args,
            timestamp_cycles=self._ctx.total_cycles,
            display_before=list(self._ctx.display),
        )

    def log_action_end(
        self,
        result: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log the end of an action.

        Call this after an action completes to capture duration and result.

        Args:
            result: "success", "failed", or "timeout"
            error_message: Error details if failed
        """
        if self._current_action is None:
            return

        self._current_action.duration_cycles = (
            self._ctx.total_cycles - self._current_action.timestamp_cycles
        )
        self._current_action.result = result
        self._current_action.error_message = error_message
        self._current_action.display_after = list(self._ctx.display)

        self._action_log.append(self._current_action)
        self._current_action = None

    def capture_screenshot(self, path: Optional[Path] = None) -> Optional[Path]:
        """
        Capture current display as screenshot.

        Args:
            path: Path to save screenshot (auto-generated if None)

        Returns:
            Path to saved screenshot, or None if failed
        """
        try:
            # Get image data from display
            format_type = self._ctx.config.screenshot_format
            if format_type == "image_lcd":
                img_data = self._ctx.emulator.display.render_image_lcd(
                    scale=3, pixel_gap=1, char_gap=2, bezel=8
                )
            elif format_type == "image":
                img_data = self._ctx.emulator.display.render_image(scale=4)
            else:
                # Text format - save as text file
                text = "\n".join(self._ctx.display)
                if path is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    test_name = self._test_name or "unknown"
                    filename = f"{test_name}_{timestamp}.txt"
                    path = self._ctx.config.ensure_screenshot_dir() / filename
                path.write_text(text)
                return path

            # Save PNG
            if path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                test_name = self._test_name or "unknown"
                filename = f"{test_name}_{timestamp}.png"
                path = self._ctx.config.ensure_screenshot_dir() / filename

            path.write_bytes(img_data)
            self._screenshots.append(img_data)
            return path

        except Exception as e:
            # Screenshot capture failed - log but don't fail the test
            print(f"Warning: Failed to capture screenshot: {e}")
            return None

    def capture_state(self) -> Dict[str, Any]:
        """
        Capture complete emulator state for debugging.

        Returns:
            Dictionary with registers, flags, display, cursor, memory stats
        """
        emu = self._ctx.emulator
        return {
            "timestamp": datetime.now().isoformat(),
            "total_cycles": emu.total_cycles,
            "model": emu.model.model_type,
            "registers": {
                "a": emu.cpu.a,
                "b": emu.cpu.b,
                "d": emu.cpu.d,
                "x": emu.cpu.x,
                "sp": emu.cpu.sp,
                "pc": emu.cpu.pc,
            },
            "flags": {
                "c": emu.cpu.flag_c,
                "v": emu.cpu.flag_v,
                "z": emu.cpu.flag_z,
                "n": emu.cpu.flag_n,
                "i": emu.cpu.flag_i,
                "h": emu.cpu.flag_h,
            },
            "display": {
                "lines": list(self._ctx.display),
                "cursor": self._ctx.cursor,
                "cursor_visible": self._ctx.cursor_visible,
            },
        }

    def format_failure_report(
        self,
        error: Exception,
        screenshot_path: Optional[Path] = None,
    ) -> str:
        """
        Format comprehensive failure report.

        This is the main diagnostic output when a test fails, providing
        all information needed to understand what went wrong.

        Args:
            error: The exception that caused the failure
            screenshot_path: Path to failure screenshot (if captured)

        Returns:
            Multi-line formatted failure report
        """
        lines = []

        # Header
        lines.append("╔" + "═" * 78 + "╗")
        lines.append("║" + "PSION TEST FAILURE".center(78) + "║")
        lines.append("╠" + "═" * 78 + "╣")

        # Test info
        lines.append("║" + " " * 78 + "║")
        test_name = self._test_name or "unknown"
        lines.append("║" + f"  Test: {test_name}".ljust(78) + "║")
        lines.append(
            "║" + f"  Model: {self._ctx.model}".ljust(78) + "║"
        )
        lines.append("║" + f"  Error: {str(error)[:70]}".ljust(78) + "║")
        lines.append("║" + " " * 78 + "║")

        # Display state
        lines.append("╠" + "═" * 78 + "╣")
        lines.append("║" + "  DISPLAY STATE".ljust(78) + "║")
        display_lines = self._ctx.display
        num_cols = 20 if self._ctx.model in ("LZ", "LZ64") else 16

        # Draw display box
        lines.append("║" + f"  ┌{'─' * num_cols}┐".ljust(78) + "║")
        for i, disp_line in enumerate(display_lines):
            # Pad/truncate to display width
            padded = disp_line[:num_cols].ljust(num_cols)
            lines.append("║" + f"  │{padded}│ line {i}".ljust(78) + "║")
        lines.append("║" + f"  └{'─' * num_cols}┘".ljust(78) + "║")

        # Cursor info
        cursor = self._ctx.cursor
        cursor_vis = "visible" if self._ctx.cursor_visible else "hidden"
        lines.append(
            "║"
            + f"  Cursor: row {cursor[0]}, col {cursor[1]} ({cursor_vis})".ljust(78)
            + "║"
        )
        lines.append("║" + " " * 78 + "║")

        # CPU state
        lines.append("╠" + "═" * 78 + "╣")
        lines.append("║" + "  EXECUTION STATE".ljust(78) + "║")
        lines.append(
            "║"
            + f"  Total cycles: {self._ctx.total_cycles:,}".ljust(78)
            + "║"
        )

        regs = self._ctx.registers
        lines.append(
            "║"
            + f"  PC: ${regs.get('pc', 0):04X}  SP: ${regs.get('sp', 0):04X}  X: ${regs.get('x', 0):04X}".ljust(
                78
            )
            + "║"
        )
        lines.append(
            "║"
            + f"  A: ${regs.get('a', 0):02X}  B: ${regs.get('b', 0):02X}  D: ${regs.get('d', 0):04X}".ljust(
                78
            )
            + "║"
        )

        # Flags
        flags = []
        for flag in ["c", "v", "z", "n", "i", "h"]:
            flag_key = f"flag_{flag}"
            val = regs.get(flag_key, 0)
            flags.append(f"{flag.upper()}={1 if val else 0}")
        lines.append("║" + f"  Flags: {' '.join(flags)}".ljust(78) + "║")
        lines.append("║" + " " * 78 + "║")

        # Recent actions
        lines.append("╠" + "═" * 78 + "╣")
        recent_count = min(5, len(self._action_log))
        total_count = len(self._action_log)
        lines.append(
            "║"
            + f"  RECENT ACTIONS (last {recent_count} of {total_count})".ljust(78)
            + "║"
        )

        for entry in self._action_log[-recent_count:]:
            action_str = entry.format_short()
            lines.append("║" + f"  {action_str[:75]}".ljust(78) + "║")

        lines.append("║" + " " * 78 + "║")

        # Screenshot path
        if screenshot_path:
            lines.append("╠" + "═" * 78 + "╣")
            lines.append(
                "║"
                + f"  SCREENSHOT: {str(screenshot_path)[:65]}".ljust(78)
                + "║"
            )
            lines.append("║" + " " * 78 + "║")

        # Footer
        lines.append("╚" + "═" * 78 + "╝")

        return "\n".join(lines)

    def format_action_log(self, detailed: bool = False) -> str:
        """
        Format complete action log.

        Args:
            detailed: If True, include display state for each action

        Returns:
            Formatted action log
        """
        if not self._action_log:
            return "No actions recorded"

        lines = [f"Action Log ({len(self._action_log)} actions):", ""]

        for entry in self._action_log:
            if detailed:
                lines.append(entry.format_detailed())
            else:
                lines.append(entry.format_short())

        return "\n".join(lines)
