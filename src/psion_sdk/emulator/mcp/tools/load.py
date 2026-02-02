"""
MCP Load Tools
==============

Tools for session creation, pack loading, and boot operations.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from pathlib import Path
from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result, success_result
from .decorators import mcp_tool, requires_session


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


@mcp_tool
@requires_session
async def load_pack(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Load an OPK pack file into the emulator.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str, "opk_path": str, "slot": int}

    Returns:
        ToolResult indicating success or failure
    """
    opk_path = args.get("opk_path", "")
    slot = args.get("slot", 0)

    # Validate path
    path = Path(opk_path)
    if not path.exists():
        return error_result(f"OPK file not found: {opk_path}")

    # Validate slot
    if not 0 <= slot <= 2:
        return error_result(
            f"Invalid slot {slot}. Use 0 (B:), 1 (C:), or 2 (top slot)."
        )

    session.emulator.load_opk(path, slot=slot)
    session.program_loaded = True
    session.program_name = path.name

    # Map slot number to user-friendly name
    slot_names = {0: "B:", 1: "C:", 2: "top slot"}
    slot_name = slot_names.get(slot, f"slot {slot}")

    return success_result(
        f"Loaded pack '{path.name}' into {slot_name}."
    )


@mcp_tool
@requires_session
async def boot_emulator(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Boot the emulator through the complete startup sequence.

    This combines: reset + run 5M cycles + select English + run 2M cycles.
    After this, the emulator will be at the main menu ready for use.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with boot status and display content
    """
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
