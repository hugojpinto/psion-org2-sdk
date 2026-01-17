"""
Psion Emulator MCP Server Package
=================================

Provides Model Context Protocol (MCP) server implementation for exposing
the Psion Organiser II emulator to AI agents and automation tools.

This package enables:
- Creating and managing emulator instances via MCP tools
- Loading and running programs
- Interacting with display and keyboard
- Debugging with breakpoints and memory inspection

The MCP server can be run standalone or embedded in other applications.

Usage:
    # Run standalone server
    python -m psion_sdk.emulator.mcp.server

    # Or embed in code
    from psion_sdk.emulator.mcp import MCPServer
    server = MCPServer()
    await server.run()

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from .server import MCPServer, EmulatorSession, SessionManager
from .tools import (
    # High-level tools
    create_emulator,
    load_pack,
    run_program,
    press_key,
    read_screen,
    wait_for_text,
    # Low-level tools
    step,
    run_cycles,
    read_memory,
    write_memory,
    set_breakpoint,
    remove_breakpoint,
    get_registers,
    get_display,
    # Session management
    list_sessions,
    destroy_session,
)

__all__ = [
    # Server
    "MCPServer",
    "EmulatorSession",
    "SessionManager",
    # High-level tools
    "create_emulator",
    "load_pack",
    "run_program",
    "press_key",
    "read_screen",
    "wait_for_text",
    # Low-level tools
    "step",
    "run_cycles",
    "read_memory",
    "write_memory",
    "set_breakpoint",
    "remove_breakpoint",
    "get_registers",
    "get_display",
    # Session management
    "list_sessions",
    "destroy_session",
]
