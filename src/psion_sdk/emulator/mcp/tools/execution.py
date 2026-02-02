"""
MCP Execution Tools
===================

Tools for running the emulator and controlling execution flow.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result, success_result
from .decorators import mcp_tool, requires_session
from .parsing import parse_address


@mcp_tool
@requires_session
async def run_program(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run the emulator for a specified number of cycles.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str, "max_cycles": int}

    Returns:
        ToolResult with execution status
    """
    max_cycles = args.get("max_cycles", 1_000_000)

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


@mcp_tool
@requires_session
async def run_until_idle(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator until CPU enters idle loop.

    Detects idle by watching for PC staying in a small address range,
    indicating a tight polling loop (typical when waiting for input).

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "max_cycles": int (optional, default 10000000),
            "idle_threshold": int (optional, default 1000 - cycles in same region to consider idle)
        }

    Returns:
        ToolResult with idle detection status and display content
    """
    max_cycles = args.get("max_cycles", 10_000_000)
    idle_threshold = args.get("idle_threshold", 1000)

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


@mcp_tool
@requires_session
async def step(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Execute a single CPU instruction.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with instruction info
    """
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


@mcp_tool
@requires_session
async def run_cycles(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Execute exact number of CPU cycles.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str, "cycles": int}

    Returns:
        ToolResult with execution status
    """
    cycles = args.get("cycles", 1000)

    if cycles < 1:
        return error_result("Cycles must be positive")

    emu = session.emulator
    event = emu.run(cycles)

    return success_result(
        f"Executed {cycles:,} cycles.\n"
        f"Stop reason: {event.reason.name}\n"
        f"PC: ${emu.cpu.pc:04X}"
    )


@mcp_tool
@requires_session
async def run_until_address(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator until PC reaches a specific address.

    This is a convenient alternative to setting a one-shot breakpoint.
    Execution stops when PC equals the target address, or when max_cycles
    is reached.

    Use cases:
    - Run until a specific routine is reached
    - Continue to a known point after injection
    - Debug step-over functionality

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,   # Target PC address
                                  # Accepts hex strings: "0x8100", "$8100"
            "max_cycles": int     # Max cycles before timeout (default: 1000000)
        }

    Returns:
        ToolResult indicating if address was reached
    """
    max_cycles = args.get("max_cycles", 1_000_000)

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    emu = session.emulator
    initial_cycles = emu.total_cycles
    cycles_run = 0

    # Run until address reached
    while cycles_run < max_cycles:
        if emu.cpu.pc == address:
            # Found it!
            cycles_run = emu.total_cycles - initial_cycles
            regs = emu.registers
            display = emu.display_text.strip()

            return success_result(
                f"Reached target address ${address:04X}!\n"
                f"Cycles: {cycles_run:,}\n"
                f"Registers: A=${regs['a']:02X} B=${regs['b']:02X} "
                f"X=${regs['x']:04X} SP=${regs['sp']:04X}\n"
                f"Display:\n{display}"
            )

        # Step one instruction
        emu.step()
        cycles_run += 1

    # Timeout
    regs = emu.registers
    return success_result(
        f"Target ${address:04X} NOT reached within {max_cycles:,} cycles.\n"
        f"Final PC: ${regs['pc']:04X}\n"
        f"A=${regs['a']:02X} B=${regs['b']:02X} "
        f"X=${regs['x']:04X} SP=${regs['sp']:04X}"
    )


@mcp_tool
@requires_session
async def wait_for_text(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator until specific text appears on display.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str, "text": str, "max_cycles": int}

    Returns:
        ToolResult indicating if text was found
    """
    text = args.get("text", "")
    max_cycles = args.get("max_cycles", 10_000_000)

    if not text:
        return error_result("No text specified")

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
