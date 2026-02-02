"""
MCP Tools Package
=================

This package provides all MCP tool implementations for the Psion emulator.

Tools are organized into logical modules:
- load: Session creation, pack loading, boot operations
- execution: Running the emulator, stepping, waiting
- display: Screen reading, keyboard input, screenshots
- memory: Memory read/write/search operations
- debugging: Breakpoints, disassembly, tracing, registers

Helper modules:
- core: Result helpers (text_content, error_result, success_result)
- decorators: Tool decorators (@mcp_tool, @requires_session)
- parsing: Parameter parsing (parse_integer, parse_address, parse_byte)
- session: Session helpers, cursor info, OPL system variables

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

# Core utilities
from .core import (
    text_content,
    error_result,
    success_result,
)

# Decorators
from .decorators import (
    mcp_tool,
    requires_session,
)

# Parsing utilities
from .parsing import (
    parse_integer,
    parse_address,
    parse_byte,
)

# Session helpers
from .session import (
    get_session_or_error,
    DPB_CPOS,
    DPB_CUST,
    get_cursor_info,
    format_cursor_info,
    OPL_SYSTEM_VARS,
)

# Load tools
from .load import (
    create_emulator,
    load_pack,
    boot_emulator,
    list_sessions,
    destroy_session,
)

# Execution tools
from .execution import (
    run_program,
    run_until_idle,
    step,
    run_cycles,
    run_until_address,
    wait_for_text,
)

# Display tools
from .display import (
    press_key,
    press_key_and_run,
    read_screen,
    type_text,
    save_screenshot,
    get_display,
)

# Memory tools
from .memory import (
    read_memory,
    write_memory,
    search_memory,
)

# Debugging tools
from .debugging import (
    set_breakpoint,
    remove_breakpoint,
    list_breakpoints,
    get_registers,
    set_registers,
    disassemble,
    disassemble_qcode,
    run_with_trace,
    step_with_disasm,
    get_opl_state,
)

# All public exports
__all__ = [
    # Core utilities
    "text_content",
    "error_result",
    "success_result",
    # Decorators
    "mcp_tool",
    "requires_session",
    # Parsing utilities
    "parse_integer",
    "parse_address",
    "parse_byte",
    # Session helpers
    "get_session_or_error",
    "DPB_CPOS",
    "DPB_CUST",
    "get_cursor_info",
    "format_cursor_info",
    "OPL_SYSTEM_VARS",
    # Load tools
    "create_emulator",
    "load_pack",
    "boot_emulator",
    "list_sessions",
    "destroy_session",
    # Execution tools
    "run_program",
    "run_until_idle",
    "step",
    "run_cycles",
    "run_until_address",
    "wait_for_text",
    # Display tools
    "press_key",
    "press_key_and_run",
    "read_screen",
    "type_text",
    "save_screenshot",
    "get_display",
    # Memory tools
    "read_memory",
    "write_memory",
    "search_memory",
    # Debugging tools
    "set_breakpoint",
    "remove_breakpoint",
    "list_breakpoints",
    "get_registers",
    "set_registers",
    "disassemble",
    "disassemble_qcode",
    "run_with_trace",
    "step_with_disasm",
    "get_opl_state",
]
