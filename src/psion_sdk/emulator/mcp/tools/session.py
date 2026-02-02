"""
MCP Tool Session Helpers
========================

Session management utilities and cursor position helpers.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result


def get_session_or_error(
    manager: SessionManager,
    session_id: str
) -> tuple[Any, ToolResult | None]:
    """
    Get session by ID or return error.

    Returns:
        Tuple of (session, None) on success, or (None, error_result) on failure
    """
    session = manager.get_session(session_id)
    if session is None:
        return None, error_result(f"Session not found: {session_id}")
    return session, None


# =============================================================================
# Cursor Position Helper
# =============================================================================
# The Psion OS maintains cursor position and state in system variables.
# These addresses are STABLE across all Psion II models (CM, XP, LZ, LZ64).
# Reference: https://www.jaapsch.net/psion/sysvars.htm

# Display cursor system variable addresses
DPB_CPOS = 0x62  # Current cursor position (1 byte)
                  # Range: 0-31 for 2-line displays (CM/XP)
                  #        0-79 for 4-line displays (LZ/LZ64)
DPB_CUST = 0x63  # Cursor state flags (1 byte)
                  # Bit 7: cursor visibility (1=on, 0=off)
                  # Bit 0: cursor style (1=line/underline, 0=block)


def get_cursor_info(emulator) -> Dict[str, Any]:
    """
    Read cursor position and state from Psion system variables.

    This reads the DPB_CPOS and DPB_CUST system variables from emulator
    memory to determine the current cursor position and state.

    The cursor position is a linear value that can be converted to
    row/column coordinates based on the display dimensions:
    - 2-line displays (CM/XP): 16 columns × 2 rows, position 0-31
    - 4-line displays (LZ/LZ64): 20 columns × 4 rows, position 0-79

    Args:
        emulator: The Emulator instance

    Returns:
        Dictionary containing:
        - position: Linear cursor position (0-31 or 0-79)
        - row: Calculated row number (0-based)
        - column: Calculated column number (0-based)
        - visible: True if cursor is visible
        - style: "block" or "line" (underline)
        - display_lines: Number of display lines (2 or 4)
        - display_cols: Number of display columns (16 or 20)
    """
    # Read cursor position and state from system variables
    cpos = emulator.read_bytes(DPB_CPOS, 1)[0]
    cust = emulator.read_bytes(DPB_CUST, 1)[0]

    # Get display dimensions from emulator model
    display_lines = emulator.model.display_lines
    display_cols = emulator.model.display_cols

    # Calculate row and column from linear position
    # Position formula: pos = (row * columns) + column
    row = cpos // display_cols
    column = cpos % display_cols

    # Clamp row to valid range (in case position exceeds display size)
    if row >= display_lines:
        row = display_lines - 1

    # Parse cursor state flags
    # Bit 7: cursor visibility (1=on, 0=off)
    # Bit 0: cursor style (1=line/underline, 0=block)
    visible = (cust & 0x80) != 0
    style = "line" if (cust & 0x01) != 0 else "block"

    return {
        "position": cpos,
        "row": row,
        "column": column,
        "visible": visible,
        "style": style,
        "display_lines": display_lines,
        "display_cols": display_cols,
    }


def format_cursor_info(cursor: Dict[str, Any], compact: bool = False) -> str:
    """
    Format cursor information as human-readable string.

    Args:
        cursor: Dictionary from get_cursor_info()
        compact: If True, return single-line format for embedding in other output

    Returns:
        Formatted string describing cursor state
    """
    if compact:
        # Single-line format for embedding in other output
        visibility = "visible" if cursor["visible"] else "hidden"
        return (
            f"Cursor: row {cursor['row']}, col {cursor['column']} "
            f"(pos {cursor['position']}) [{cursor['style']}, {visibility}]"
        )
    else:
        # Multi-line detailed format
        visibility = "ON (visible)" if cursor["visible"] else "OFF (hidden)"
        return (
            f"Cursor Position:\n"
            f"  Row: {cursor['row']} (0-{cursor['display_lines']-1})\n"
            f"  Column: {cursor['column']} (0-{cursor['display_cols']-1})\n"
            f"  Linear Position: {cursor['position']}\n"
            f"  Visibility: {visibility}\n"
            f"  Style: {cursor['style']}"
        )


# =============================================================================
# OPL Interpreter System Variables
# =============================================================================
# These addresses are STABLE across all Psion II models (CM, XP, LA, LZ, LZ64, P350)
# Reference: https://www.jaapsch.net/psion/sysvars.htm

OPL_SYSTEM_VARS = {
    "RTA_SP": (0xA5, 2, "Language stack pointer"),
    "RTA_FP": (0xA7, 2, "Frame pointer"),
    "RTA_PC": (0xA9, 2, "QCode program counter"),
    "DEFAULT_DEV": (0xB5, 1, "Default device letter ('A'=0x41, 'B'=0x42)"),
}
