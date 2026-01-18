"""
Psion Emulator MCP Tools
========================

Tool implementations for the MCP server.

Each tool is an async function that:
- Takes a SessionManager and arguments dictionary
- Returns a ToolResult with content and error status

Tools are organized into:
- High-level tools: Simplified operations for common tasks
- Low-level tools: Direct access to emulator internals
- Session management: Managing emulator instances

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import base64
from pathlib import Path
from typing import Any, Dict, List

from .server import SessionManager, ToolResult


# =============================================================================
# Helper Functions
# =============================================================================

def text_content(text: str) -> List[Dict[str, Any]]:
    """Create text content for tool result."""
    return [{"type": "text", "text": text}]


def error_result(message: str) -> ToolResult:
    """Create error tool result."""
    return ToolResult(content=text_content(message), is_error=True)


def success_result(text: str) -> ToolResult:
    """Create success tool result."""
    return ToolResult(content=text_content(text), is_error=False)


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
# High-Level Tools
# =============================================================================

async def create_emulator(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Create a new Psion emulator session.

    Args:
        manager: Session manager
        args: {"model": "XP"|"CM"|"LZ"|"LZ64"}

    Returns:
        ToolResult with session_id
    """
    model = args.get("model", "XP").upper()

    # Validate model
    valid_models = ["CM", "XP", "LZ", "LZ64"]
    if model not in valid_models:
        return error_result(
            f"Invalid model '{model}'. Valid: {', '.join(valid_models)}"
        )

    try:
        session = manager.create_session(model=model)
        return success_result(
            f"Created emulator session.\n"
            f"Session ID: {session.session_id}\n"
            f"Model: {session.model}\n"
            f"Display: {session.emulator.model.display_lines} lines x "
            f"{session.emulator.model.display_cols} columns\n"
            f"RAM: {session.emulator.model.ram_kb}KB"
        )
    except Exception as e:
        return error_result(f"Failed to create emulator: {e}")


async def load_pack(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Load an OPK pack file into the emulator.

    Args:
        manager: Session manager
        args: {"session_id": str, "opk_path": str, "slot": int}

    Returns:
        ToolResult indicating success or failure
    """
    session_id = args.get("session_id", "")
    opk_path = args.get("opk_path", "")
    slot = args.get("slot", 0)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    # Validate path
    path = Path(opk_path)
    if not path.exists():
        return error_result(f"OPK file not found: {opk_path}")

    # Validate slot
    if not 0 <= slot <= 2:
        return error_result(
            f"Invalid slot {slot}. Use 0 (B:), 1 (C:), or 2 (top slot)."
        )

    try:
        session.emulator.load_opk(path, slot=slot)
        session.program_loaded = True
        session.program_name = path.name

        # Map slot number to user-friendly name
        slot_names = {0: "B:", 1: "C:", 2: "top slot"}
        slot_name = slot_names.get(slot, f"slot {slot}")

        return success_result(
            f"Loaded pack '{path.name}' into {slot_name}."
        )
    except Exception as e:
        return error_result(f"Failed to load OPK: {e}")


async def run_program(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run the emulator for a specified number of cycles.

    Args:
        manager: Session manager
        args: {"session_id": str, "max_cycles": int}

    Returns:
        ToolResult with execution status
    """
    session_id = args.get("session_id", "")
    max_cycles = args.get("max_cycles", 1_000_000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        initial_cycles = emu.total_cycles

        event = emu.run(max_cycles)

        cycles_run = emu.total_cycles - initial_cycles
        reason = event.reason.name

        # Get display state
        display_text = emu.display_text.strip() or "(empty)"

        return success_result(
            f"Execution stopped: {reason}\n"
            f"Cycles executed: {cycles_run:,}\n"
            f"PC: ${emu.cpu.pc:04X}\n"
            f"Display:\n{display_text}"
        )
    except Exception as e:
        return error_result(f"Execution error: {e}")


async def press_key(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Press a key on the emulator keyboard.

    Args:
        manager: Session manager
        args: {"session_id": str, "key": str, "action": str, "hold_cycles": int}

    Returns:
        ToolResult indicating success
    """
    session_id = args.get("session_id", "")
    key = args.get("key", "").upper()
    action = args.get("action", "tap").lower()
    hold_cycles = args.get("hold_cycles", 50000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if not key:
        return error_result("No key specified")

    try:
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

    except (KeyError, ValueError) as e:
        return error_result(f"Invalid key '{key}': {e}")
    except Exception as e:
        return error_result(f"Key error: {e}")


async def press_key_and_run(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Press a key and run cycles in one call.

    Combines press_key + run_cycles for convenience during navigation.

    Args:
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
    session_id = args.get("session_id", "")
    key = args.get("key", "").upper()
    hold_cycles = args.get("hold_cycles", 50000)
    run_cycles_count = args.get("run_cycles", 200000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if not key:
        return error_result("No key specified")

    try:
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

    except (KeyError, ValueError) as e:
        return error_result(f"Invalid key '{key}': {e}")
    except Exception as e:
        return error_result(f"Key error: {e}")


async def run_until_idle(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator until CPU enters idle loop.

    Detects idle by watching for PC staying in a small address range,
    indicating a tight polling loop (typical when waiting for input).

    Args:
        manager: Session manager
        args: {
            "session_id": str,
            "max_cycles": int (optional, default 10000000),
            "idle_threshold": int (optional, default 1000 - cycles in same region to consider idle)
        }

    Returns:
        ToolResult with idle detection status and display content
    """
    session_id = args.get("session_id", "")
    max_cycles = args.get("max_cycles", 10_000_000)
    idle_threshold = args.get("idle_threshold", 1000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        initial_cycles = emu.total_cycles

        # Track PC history to detect idle loop
        pc_history = []
        cycles_run = 0
        chunk_size = 10000  # Run in chunks to check for idle

        while cycles_run < max_cycles:
            emu.run(chunk_size)
            cycles_run += chunk_size

            current_pc = emu.cpu.pc
            pc_history.append(current_pc)

            # Keep only recent history
            if len(pc_history) > 100:
                pc_history = pc_history[-100:]

            # Check if PC is staying in small range (idle loop)
            if len(pc_history) >= 10:
                pc_min = min(pc_history[-10:])
                pc_max = max(pc_history[-10:])
                # If PC range is small (< 32 bytes), likely in idle loop
                if pc_max - pc_min < 32:
                    display = emu.display_text.strip()
                    return success_result(
                        f"Idle detected at ${current_pc:04X}\n"
                        f"Cycles: {cycles_run:,}\n"
                        f"Display:\n{display}"
                    )

        # Max cycles reached without detecting idle
        display = emu.display_text.strip()
        return success_result(
            f"Max cycles reached without idle detection.\n"
            f"Cycles: {cycles_run:,}\n"
            f"PC: ${emu.cpu.pc:04X}\n"
            f"Display:\n{display}"
        )

    except Exception as e:
        return error_result(f"Run until idle error: {e}")


async def read_screen(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Read the current display content.

    Args:
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
    session_id = args.get("session_id", "")
    format_type = args.get("format", "text").lower()

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator

        if format_type == "text":
            text = emu.display_text
            return success_result(f"Display content:\n{text}")

        elif format_type == "lines":
            lines = emu.display_lines
            result = "Display lines:\n"
            for i, line in enumerate(lines, 1):
                result += f"  Line {i}: {repr(line)}\n"
            return success_result(result)

        elif format_type == "image":
            try:
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
            except ImportError:
                return error_result(
                    "Image rendering requires PIL. "
                    "Install with: pip install Pillow"
                )

        elif format_type == "image_lcd":
            try:
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
            except ImportError:
                return error_result(
                    "Image rendering requires PIL. "
                    "Install with: pip install Pillow"
                )

        else:
            return error_result(
                f"Unknown format: {format_type}. "
                "Use 'text', 'lines', 'image', or 'image_lcd'"
            )

    except Exception as e:
        return error_result(f"Read screen error: {e}")


async def boot_emulator(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Boot the emulator through the complete startup sequence.

    This combines: reset + run 5M cycles + select English + run 2M cycles.
    After this, the emulator will be at the main menu ready for use.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with boot status and display content
    """
    session_id = args.get("session_id", "")

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator

        # Reset and run initial boot
        emu.reset()
        emu.run(5_000_000)

        # Select English (first option)
        emu.tap_key("EXE", hold_cycles=50000)
        emu.run(2_000_000)

        # Get display content
        display = emu.display_text.strip()

        return success_result(
            f"Emulator booted successfully.\n"
            f"Total cycles: {emu.total_cycles:,}\n"
            f"Display:\n{display}"
        )

    except Exception as e:
        return error_result(f"Boot error: {e}")


async def type_text(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Type a string of text on the emulator keyboard.

    Each character is typed with a short delay between keypresses.
    Supports letters A-Z, numbers 0-9, and common punctuation.

    Args:
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
    session_id = args.get("session_id", "")
    text = args.get("text", "")
    hold_cycles = args.get("hold_cycles", 50000)
    delay_cycles = args.get("delay_cycles", 150000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if not text:
        return error_result("No text specified")

    try:
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

    except Exception as e:
        return error_result(f"Type text error: {e}")


async def save_screenshot(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Save the current display as an image file.

    Args:
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
    session_id = args.get("session_id", "")
    file_path = args.get("file_path", "")
    format_type = args.get("format", "image_lcd").lower()

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if not file_path:
        return error_result("No file_path specified")

    # Validate format
    if format_type not in ("image", "image_lcd"):
        return error_result(
            f"Unknown format: {format_type}. Use 'image' or 'image_lcd'"
        )

    try:
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

    except Exception as e:
        return error_result(f"Save screenshot error: {e}")


async def wait_for_text(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator until specific text appears on display.

    Args:
        manager: Session manager
        args: {"session_id": str, "text": str, "max_cycles": int}

    Returns:
        ToolResult indicating if text was found
    """
    session_id = args.get("session_id", "")
    text = args.get("text", "")
    max_cycles = args.get("max_cycles", 10_000_000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if not text:
        return error_result("No text specified")

    try:
        emu = session.emulator
        initial_cycles = emu.total_cycles

        found = emu.run_until_text(text, max_cycles=max_cycles)

        cycles_run = emu.total_cycles - initial_cycles
        display = emu.display_text.strip()

        if found:
            return success_result(
                f"Text '{text}' found!\n"
                f"Cycles: {cycles_run:,}\n"
                f"Display:\n{display}"
            )
        else:
            return success_result(
                f"Text '{text}' not found within {max_cycles:,} cycles.\n"
                f"Display:\n{display}"
            )

    except Exception as e:
        return error_result(f"Wait error: {e}")


# =============================================================================
# Low-Level Tools
# =============================================================================

async def step(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Execute a single CPU instruction.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with instruction info
    """
    session_id = args.get("session_id", "")

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        pc_before = emu.cpu.pc

        event = emu.step()

        regs = emu.registers
        return success_result(
            f"Stepped from ${pc_before:04X} to ${regs['pc']:04X}\n"
            f"A=${regs['a']:02X} B=${regs['b']:02X} "
            f"X=${regs['x']:04X} SP=${regs['sp']:04X}\n"
            f"Flags: Z={regs['z']} N={regs['n']} C={regs['c']} V={regs['v']}"
        )

    except Exception as e:
        return error_result(f"Step error: {e}")


async def run_cycles(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Execute exact number of CPU cycles.

    Args:
        manager: Session manager
        args: {"session_id": str, "cycles": int}

    Returns:
        ToolResult with execution status
    """
    session_id = args.get("session_id", "")
    cycles = args.get("cycles", 1000)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if cycles < 1:
        return error_result("Cycles must be positive")

    try:
        emu = session.emulator
        event = emu.run(cycles)

        return success_result(
            f"Executed {cycles:,} cycles.\n"
            f"Stop reason: {event.reason.name}\n"
            f"PC: ${emu.cpu.pc:04X}"
        )

    except Exception as e:
        return error_result(f"Run error: {e}")


async def read_memory(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Read bytes from emulator memory.

    Args:
        manager: Session manager
        args: {"session_id": str, "address": int, "count": int}

    Returns:
        ToolResult with memory contents
    """
    session_id = args.get("session_id", "")
    address = args.get("address", 0)
    count = args.get("count", 1)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    # Validate
    if not 0 <= address <= 0xFFFF:
        return error_result(f"Address ${address:04X} out of range")
    if count < 1 or count > 256:
        return error_result("Count must be 1-256")

    try:
        emu = session.emulator
        data = emu.read_bytes(address, count)

        # Format as hex dump
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            addr = address + i
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(
                chr(b) if 32 <= b < 127 else '.'
                for b in chunk
            )
            lines.append(f"${addr:04X}: {hex_part:<48} |{ascii_part}|")

        return success_result('\n'.join(lines))

    except Exception as e:
        return error_result(f"Read memory error: {e}")


async def write_memory(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Write bytes to emulator memory.

    Args:
        manager: Session manager
        args: {"session_id": str, "address": int, "data": List[int]}

    Returns:
        ToolResult indicating success
    """
    session_id = args.get("session_id", "")
    address = args.get("address", 0)
    data = args.get("data", [])

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    # Validate
    if not 0 <= address <= 0xFFFF:
        return error_result(f"Address ${address:04X} out of range")
    if not data:
        return error_result("No data specified")
    if len(data) > 256:
        return error_result("Maximum 256 bytes at once")

    # Validate all values
    for i, b in enumerate(data):
        if not isinstance(b, int) or not 0 <= b <= 255:
            return error_result(f"Invalid byte at index {i}: {b}")

    try:
        emu = session.emulator
        emu.write_bytes(address, bytes(data))

        return success_result(
            f"Wrote {len(data)} bytes starting at ${address:04X}"
        )

    except Exception as e:
        return error_result(f"Write memory error: {e}")


async def search_memory(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Search for byte pattern in emulator memory.

    Args:
        manager: Session manager
        args: {
            "session_id": str,
            "pattern": List[int],  # Bytes to search for (0-255 each)
            "start": int,          # Start address (default 0)
            "end": int,            # End address (default 0xFFFF)
            "max_results": int     # Maximum matches to return (default 20)
        }

    Returns:
        ToolResult with matching addresses
    """
    session_id = args.get("session_id", "")
    pattern = args.get("pattern", [])
    start = args.get("start", 0)
    end = args.get("end", 0xFFFF)
    max_results = args.get("max_results", 20)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    # Validate
    if not pattern:
        return error_result("No pattern specified")
    if len(pattern) > 64:
        return error_result("Pattern too long (max 64 bytes)")

    # Validate pattern bytes
    for i, b in enumerate(pattern):
        if not isinstance(b, int) or not 0 <= b <= 255:
            return error_result(f"Invalid byte at index {i}: {b}")

    if not 0 <= start <= 0xFFFF:
        return error_result(f"Start address ${start:04X} out of range")
    if not 0 <= end <= 0xFFFF:
        return error_result(f"End address ${end:04X} out of range")
    if start > end:
        return error_result("Start must be <= end")

    try:
        emu = session.emulator
        pattern_bytes = bytes(pattern)
        pattern_len = len(pattern_bytes)
        matches = []

        # Search through memory
        addr = start
        while addr <= end - pattern_len + 1 and len(matches) < max_results:
            # Read bytes at current position
            data = emu.read_bytes(addr, pattern_len)
            if data == pattern_bytes:
                matches.append(addr)
            addr += 1

        # Format results
        if not matches:
            pattern_hex = ' '.join(f'{b:02X}' for b in pattern)
            return success_result(
                f"Pattern [{pattern_hex}] not found in range "
                f"${start:04X}-${end:04X}"
            )

        # Build result with context
        result_lines = [
            f"Found {len(matches)} match(es) for pattern "
            f"[{' '.join(f'{b:02X}' for b in pattern)}]:"
        ]

        for addr in matches:
            # Show some context around the match
            ctx_start = max(0, addr - 4)
            ctx_end = min(0xFFFF, addr + pattern_len + 4)
            context = emu.read_bytes(ctx_start, ctx_end - ctx_start)

            # Format with match highlighted
            hex_parts = []
            for i, b in enumerate(context):
                real_addr = ctx_start + i
                if addr <= real_addr < addr + pattern_len:
                    hex_parts.append(f"[{b:02X}]")  # Highlight match
                else:
                    hex_parts.append(f"{b:02X}")

            result_lines.append(f"  ${addr:04X}: {' '.join(hex_parts)}")

        if len(matches) >= max_results:
            result_lines.append(f"  (limited to {max_results} results)")

        return success_result('\n'.join(result_lines))

    except Exception as e:
        return error_result(f"Search memory error: {e}")


async def set_breakpoint(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Set a breakpoint or watchpoint with optional condition.

    Args:
        manager: Session manager
        args: {
            "session_id": str,
            "type": str,       # "pc" (default), "read", or "write"
            "address": int,    # Memory address (required)

            # Optional condition - break only fires when condition is also true:
            "when_register": str,  # a, b, d, x, sp, pc, flag_c, flag_v, flag_z, flag_n
            "when_op": str,        # ==, !=, <, <=, >, >=, &
            "when_value": int
        }

    Examples:
        - Simple: {type: "pc", address: 0x8000}
        - Conditional: {type: "pc", address: 0x8000, when_register: "a", when_op: "==", when_value: 0x42}
          → Break at $8000 only when A == 0x42

    Returns:
        ToolResult indicating success
    """
    session_id = args.get("session_id", "")
    bp_type = args.get("type", "pc").lower()
    address = args.get("address", -1)

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    # Validate address
    if address < 0 or address > 0xFFFF:
        return error_result(f"Address required (0-65535)")

    # Build optional condition
    condition = None
    when_register = args.get("when_register")
    when_op = args.get("when_op")
    when_value = args.get("when_value")

    if when_register and when_op and when_value is not None:
        condition = (when_register, when_op, when_value)

    try:
        emu = session.emulator

        if bp_type == "pc":
            emu.breakpoints.add_breakpoint(address, condition=condition)
            msg = f"Breakpoint set at ${address:04X}"
        elif bp_type == "read":
            emu.breakpoints.add_read_watchpoint(address, condition=condition)
            msg = f"Read watchpoint set at ${address:04X}"
        elif bp_type == "write":
            emu.breakpoints.add_write_watchpoint(address, condition=condition)
            msg = f"Write watchpoint set at ${address:04X}"
        else:
            return error_result(f"Unknown type: {bp_type}. Use pc, read, or write.")

        if condition:
            msg += f" (when {when_register} {when_op} {when_value})"

        return success_result(msg)

    except ValueError as e:
        return error_result(f"Invalid condition: {e}")
    except Exception as e:
        return error_result(f"Set breakpoint error: {e}")


async def remove_breakpoint(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Remove a breakpoint or watchpoint at an address.

    Args:
        manager: Session manager
        args: {
            "session_id": str,
            "address": int,    # Memory address (required)
            "type": str        # "all" (default), "pc", "read", or "write"
        }

    Returns:
        ToolResult indicating what was removed
    """
    session_id = args.get("session_id", "")
    address = args.get("address", -1)
    bp_type = args.get("type", "all").lower()

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    if address < 0 or address > 0xFFFF:
        return error_result("Address required (0-65535)")

    try:
        emu = session.emulator
        removed = []

        if bp_type in ("pc", "all"):
            if emu.breakpoints.has_breakpoint(address):
                emu.breakpoints.remove_breakpoint(address)
                removed.append("PC breakpoint")

        if bp_type in ("read", "all"):
            if address in emu.breakpoints._read_watchpoints:
                emu.breakpoints.remove_read_watchpoint(address)
                removed.append("read watchpoint")

        if bp_type in ("write", "all"):
            if address in emu.breakpoints._write_watchpoints:
                emu.breakpoints.remove_write_watchpoint(address)
                removed.append("write watchpoint")

        if removed:
            return success_result(
                f"Removed at ${address:04X}: {', '.join(removed)}"
            )
        else:
            return success_result(
                f"No breakpoints/watchpoints at ${address:04X}"
            )

    except Exception as e:
        return error_result(f"Remove breakpoint error: {e}")


async def list_breakpoints(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    List all active breakpoints and watchpoints.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with all active debugging points and their conditions
    """
    session_id = args.get("session_id", "")

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        bp_mgr = emu.breakpoints
        result_lines = []

        def format_entry(addr: int, cond) -> str:
            """Format a breakpoint/watchpoint entry with optional condition."""
            if cond:
                return f"  ${addr:04X}  when {cond}"
            return f"  ${addr:04X}"

        # PC Breakpoints
        pc_breakpoints = bp_mgr.list_breakpoints()
        if pc_breakpoints:
            result_lines.append(f"PC Breakpoints ({len(pc_breakpoints)}):")
            for addr, cond in pc_breakpoints:
                result_lines.append(format_entry(addr, cond))
        else:
            result_lines.append("PC Breakpoints: (none)")

        # Read Watchpoints
        read_watchpoints = bp_mgr.list_read_watchpoints()
        if read_watchpoints:
            result_lines.append(f"\nRead Watchpoints ({len(read_watchpoints)}):")
            for addr, cond in read_watchpoints:
                result_lines.append(format_entry(addr, cond))
        else:
            result_lines.append("\nRead Watchpoints: (none)")

        # Write Watchpoints
        write_watchpoints = bp_mgr.list_write_watchpoints()
        if write_watchpoints:
            result_lines.append(f"\nWrite Watchpoints ({len(write_watchpoints)}):")
            for addr, cond in write_watchpoints:
                result_lines.append(format_entry(addr, cond))
        else:
            result_lines.append("\nWrite Watchpoints: (none)")

        # Summary
        total = len(pc_breakpoints) + len(read_watchpoints) + len(write_watchpoints)
        result_lines.append(f"\nTotal: {total} active")

        return success_result('\n'.join(result_lines))

    except Exception as e:
        return error_result(f"List breakpoints error: {e}")


async def get_registers(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Get current CPU register values.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with register values
    """
    session_id = args.get("session_id", "")

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        regs = emu.registers

        return success_result(
            f"CPU Registers:\n"
            f"  A:  ${regs['a']:02X} ({regs['a']:3d})\n"
            f"  B:  ${regs['b']:02X} ({regs['b']:3d})\n"
            f"  D:  ${regs['d']:04X} ({regs['d']:5d})\n"
            f"  X:  ${regs['x']:04X}\n"
            f"  SP: ${regs['sp']:04X}\n"
            f"  PC: ${regs['pc']:04X}\n"
            f"Flags:\n"
            f"  C (Carry):     {regs['c']}\n"
            f"  V (Overflow):  {regs['v']}\n"
            f"  Z (Zero):      {regs['z']}\n"
            f"  N (Negative):  {regs['n']}\n"
            f"  I (Interrupt): {regs['i']}\n"
            f"  H (Half-Carry):{regs['h']}"
        )

    except Exception as e:
        return error_result(f"Get registers error: {e}")


async def get_display(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Get detailed display state.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with display state
    """
    session_id = args.get("session_id", "")

    session, error = get_session_or_error(manager, session_id)
    if error:
        return error

    try:
        emu = session.emulator
        display = emu.display

        lines = emu.display_lines
        text = emu.display_text

        result = (
            f"Display State:\n"
            f"  Type: {emu.model.display_lines} lines x {emu.model.display_cols} columns\n"
            f"  Power: {'ON' if display.is_on else 'OFF'}\n"
            f"\nContent:\n"
        )

        # Format each line with line numbers
        for i, line in enumerate(lines, 1):
            result += f"  [{i}] \"{line}\"\n"

        # Show cursor position if available
        if hasattr(display, '_cursor_address'):
            result += f"\nCursor: position {display._cursor_address}"

        return success_result(result)

    except Exception as e:
        return error_result(f"Get display error: {e}")


# =============================================================================
# Session Management Tools
# =============================================================================

async def list_sessions(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    List all active emulator sessions.

    Args:
        manager: Session manager
        args: {} (no arguments)

    Returns:
        ToolResult with session list
    """
    try:
        sessions = manager.list_sessions()

        if not sessions:
            return success_result("No active sessions.")

        result = f"Active sessions ({len(sessions)}):\n"
        for s in sessions:
            result += (
                f"\n  Session: {s['session_id']}\n"
                f"    Model: {s['model']}\n"
                f"    Program: {s.get('program_name', 'None')}\n"
                f"    Cycles: {s['total_cycles']:,}\n"
                f"    PC: {s['pc']}\n"
            )

        return success_result(result)

    except Exception as e:
        return error_result(f"List sessions error: {e}")


async def destroy_session(
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Destroy an emulator session.

    Args:
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult indicating success
    """
    session_id = args.get("session_id", "")

    if not session_id:
        return error_result("No session_id specified")

    try:
        if manager.destroy_session(session_id):
            return success_result(f"Session {session_id} destroyed.")
        else:
            return error_result(f"Session not found: {session_id}")

    except Exception as e:
        return error_result(f"Destroy session error: {e}")
