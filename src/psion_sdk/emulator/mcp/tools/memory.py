"""
MCP Memory Tools
================

Tools for reading, writing, and searching emulator memory.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result, success_result
from .decorators import mcp_tool, requires_session
from .parsing import parse_address


@mcp_tool
@requires_session
async def read_memory(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Read bytes from emulator memory.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,  # Accepts hex strings like "0x8100" or "$8100"
            "count": int
        }

    Returns:
        ToolResult with memory contents
    """
    count = args.get("count", 1)

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    # Validate count
    if count < 1 or count > 256:
        return error_result("Count must be 1-256")

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


@mcp_tool
@requires_session
async def write_memory(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Write bytes to emulator memory.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,  # Accepts hex strings like "0x8100" or "$8100"
            "data": List[int]    # Byte values 0-255
        }

    Returns:
        ToolResult indicating success
    """
    data = args.get("data", [])

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    # Validate data
    if not data:
        return error_result("No data specified")
    if len(data) > 256:
        return error_result("Maximum 256 bytes at once")

    # Validate all byte values
    for i, b in enumerate(data):
        if not isinstance(b, int) or not 0 <= b <= 255:
            return error_result(f"Invalid byte at index {i}: {b}")

    emu = session.emulator
    emu.write_bytes(address, bytes(data))

    return success_result(
        f"Wrote {len(data)} bytes starting at ${address:04X}"
    )


@mcp_tool
@requires_session
async def search_memory(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Search for byte pattern in emulator memory.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "pattern": List[int],   # Bytes to search for (0-255 each)
            "start": int|str,       # Start address (default 0)
                                    # Accepts hex strings: "0x8100", "$8100"
            "end": int|str,         # End address (default 0xFFFF)
                                    # Accepts hex strings: "0x8200", "$8200"
            "max_results": int      # Maximum matches to return (default 20)
        }

    Returns:
        ToolResult with matching addresses
    """
    pattern = args.get("pattern", [])
    max_results = args.get("max_results", 20)

    # Parse and validate start/end addresses
    # These support hex strings like "0x8100" or "$8100"
    start = parse_address(args.get("start"), "start", default=0)
    end = parse_address(args.get("end"), "end", default=0xFFFF)

    # Validate pattern
    if not pattern:
        return error_result("No pattern specified")
    if len(pattern) > 64:
        return error_result("Pattern too long (max 64 bytes)")

    # Validate pattern bytes
    for i, b in enumerate(pattern):
        if not isinstance(b, int) or not 0 <= b <= 255:
            return error_result(f"Invalid byte at index {i}: {b}")

    # Validate address range
    if start > end:
        return error_result(
            f"Start address (${start:04X}) must be <= end address (${end:04X})"
        )

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
