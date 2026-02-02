"""
MCP Display Tools
=================

Tools for display output, keyboard input, and screenshots.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import base64
from pathlib import Path
from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result, success_result
from .decorators import mcp_tool, requires_session
from .session import get_cursor_info, format_cursor_info


@mcp_tool
@requires_session
async def press_key(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Press a key on the emulator keyboard.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str, "key": str, "action": str, "hold_cycles": int}

    Returns:
        ToolResult indicating success
    """
    key = args.get("key", "").upper()
    action = args.get("action", "tap").lower()
    hold_cycles = args.get("hold_cycles", 50000)

    if not key:
        return error_result("No key specified")

    emu = session.emulator

    if action == "tap":
        emu.tap_key(key, hold_cycles=hold_cycles)
        return success_result(f"Tapped key '{key}'")
    elif action == "down":
        emu.press_key(key)
        return success_result(f"Key '{key}' pressed down")
    elif action == "up":
        emu.release_key(key)
        return success_result(f"Key '{key}' released")
    else:
        return error_result(f"Unknown action: {action}")


@mcp_tool
@requires_session
async def press_key_and_run(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Press a key and run cycles in one call.

    Combines press_key + run_cycles for convenience during navigation.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "key": str,
            "hold_cycles": int (optional, default 50000),
            "run_cycles": int (optional, default 200000)
        }

    Returns:
        ToolResult with key pressed and display content
    """
    key = args.get("key", "").upper()
    hold_cycles = args.get("hold_cycles", 50000)
    run_cycles_count = args.get("run_cycles", 200000)

    if not key:
        return error_result("No key specified")

    emu = session.emulator

    # Press the key
    emu.tap_key(key, hold_cycles=hold_cycles)

    # Run cycles to let emulator process
    emu.run(run_cycles_count)

    # Get display content
    display = emu.display_text.strip()

    return success_result(
        f"Pressed '{key}', ran {run_cycles_count:,} cycles.\n"
        f"Display:\n{display}"
    )


@mcp_tool
@requires_session
async def read_screen(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Read the current display content.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "format": "text"|"lines"|"image"|"image_lcd",
            "scale": int (optional, default 3 for image_lcd, 2 for image),
            "pixel_gap": int (optional, default 1, for image_lcd only),
            "char_gap": int (optional, default 2, for image_lcd only),
            "bezel": int (optional, default 8, for image_lcd only)
        }

    Returns:
        ToolResult with display content
    """
    format_type = args.get("format", "text").lower()

    emu = session.emulator

    # Always read cursor information for text-based formats
    # This enables AI agents to understand spatial context on the screen
    cursor = get_cursor_info(emu)

    if format_type == "text":
        text = emu.display_text
        cursor_info = format_cursor_info(cursor, compact=True)
        return success_result(
            f"Display content:\n{text}\n\n{cursor_info}"
        )

    elif format_type == "lines":
        lines = emu.display_lines
        result = "Display lines:\n"
        for i, line in enumerate(lines):
            # Mark the cursor position with a visual indicator
            row_marker = " <-- cursor" if i == cursor["row"] else ""
            result += f"  [{i}] {repr(line)}{row_marker}\n"
        result += f"\n{format_cursor_info(cursor, compact=True)}"
        return success_result(result)

    elif format_type == "image":
        scale = args.get("scale", 2)
        img_data = emu.display.render_image(scale=scale)
        if img_data is None:
            return error_result(
                "Image rendering requires PIL. "
                "Install with: pip install Pillow"
            )
        img_b64 = base64.b64encode(img_data).decode('ascii')
        return ToolResult(
            content=[{
                "type": "image",
                "data": img_b64,
                "mimeType": "image/png"
            }],
            is_error=False
        )

    elif format_type == "image_lcd":
        # LCD matrix style rendering with visible pixel grid
        scale = args.get("scale", 3)
        pixel_gap = args.get("pixel_gap", 1)
        char_gap = args.get("char_gap", 2)
        bezel = args.get("bezel", 8)

        img_data = emu.display.render_image_lcd(
            scale=scale,
            pixel_gap=pixel_gap,
            char_gap=char_gap,
            bezel=bezel
        )
        if img_data is None:
            return error_result(
                "Image rendering requires PIL. "
                "Install with: pip install Pillow"
            )
        img_b64 = base64.b64encode(img_data).decode('ascii')
        return ToolResult(
            content=[{
                "type": "image",
                "data": img_b64,
                "mimeType": "image/png"
            }],
            is_error=False
        )

    else:
        return error_result(
            f"Unknown format: {format_type}. "
            "Use 'text', 'lines', 'image', or 'image_lcd'"
        )


@mcp_tool
@requires_session
async def type_text(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Type a string of text on the emulator keyboard.

    Each character is typed with a short delay between keypresses.
    Supports letters A-Z, numbers 0-9, and common punctuation.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "text": str,
            "hold_cycles": int (optional, default 50000),
            "delay_cycles": int (optional, default 150000)
        }

    Returns:
        ToolResult indicating success
    """
    text = args.get("text", "")
    hold_cycles = args.get("hold_cycles", 50000)
    delay_cycles = args.get("delay_cycles", 150000)

    if not text:
        return error_result("No text specified")

    emu = session.emulator
    typed_count = 0

    for char in text.upper():
        try:
            emu.tap_key(char, hold_cycles=hold_cycles)
            emu.run(delay_cycles)
            typed_count += 1
        except (KeyError, ValueError):
            # Skip characters that can't be typed
            pass

    return success_result(
        f"Typed {typed_count} characters: '{text}'"
    )


@mcp_tool
@requires_session
async def save_screenshot(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Save the current display as an image file.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "file_path": str,
            "format": "image"|"image_lcd" (default: "image_lcd"),
            "scale": int (optional),
            "pixel_gap": int (optional, for image_lcd),
            "char_gap": int (optional, for image_lcd),
            "bezel": int (optional, for image_lcd)
        }

    Returns:
        ToolResult indicating success or failure
    """
    file_path = args.get("file_path", "")
    format_type = args.get("format", "image_lcd").lower()

    if not file_path:
        return error_result("No file_path specified")

    # Validate format
    if format_type not in ("image", "image_lcd"):
        return error_result(
            f"Unknown format: {format_type}. Use 'image' or 'image_lcd'"
        )

    emu = session.emulator
    output_path = Path(file_path)

    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format_type == "image":
        scale = args.get("scale", 2)
        png_data = emu.display.render_image(scale=scale)
    else:  # image_lcd
        scale = args.get("scale", 3)
        pixel_gap = args.get("pixel_gap", 1)
        char_gap = args.get("char_gap", 2)
        bezel = args.get("bezel", 8)
        png_data = emu.display.render_image_lcd(
            scale=scale,
            pixel_gap=pixel_gap,
            char_gap=char_gap,
            bezel=bezel
        )

    if png_data is None:
        return error_result(
            "Image rendering requires PIL. Install with: pip install Pillow"
        )

    # Write PNG bytes directly to file
    output_path.write_bytes(png_data)

    return success_result(f"Screenshot saved to {output_path}")


@mcp_tool
@requires_session
async def get_display(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Get detailed display state.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with display state
    """
    emu = session.emulator
    display = emu.display

    lines = emu.display_lines

    # Get detailed cursor information from system variables
    # This provides accurate cursor position as maintained by the Psion OS
    cursor = get_cursor_info(emu)

    result = (
        f"Display State:\n"
        f"  Type: {emu.model.display_lines} lines x {emu.model.display_cols} columns\n"
        f"  Power: {'ON' if display.is_on else 'OFF'}\n"
        f"\nContent:\n"
    )

    # Format each line with line numbers and cursor indicator
    for i, line in enumerate(lines):
        cursor_marker = ""
        if i == cursor["row"] and cursor["visible"]:
            # Show column position indicator
            cursor_marker = f"  <-- cursor at column {cursor['column']}"
        result += f"  [{i}] \"{line}\"{cursor_marker}\n"

    # Add detailed cursor state information
    # This is essential for AI agents to understand screen position context
    result += f"\n{format_cursor_info(cursor, compact=False)}"

    return success_result(result)
