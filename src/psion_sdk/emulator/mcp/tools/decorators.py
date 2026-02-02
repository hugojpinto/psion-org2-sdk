"""
MCP Tool Decorators
===================

Decorators for reducing boilerplate in tool implementations.

Usage:
    @mcp_tool
    @requires_session
    async def my_tool(session, manager, args) -> ToolResult:
        # session is already validated
        data = session.emulator.read_bytes(...)
        return success_result(...)

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import functools
from typing import Any, Callable, Dict, TypeVar

from ..server import SessionManager, ToolResult
from .core import error_result

# Type variable for generic tool functions
F = TypeVar('F', bound=Callable[..., Any])


def mcp_tool(func: F) -> F:
    """
    Decorator that wraps MCP tool exceptions into error_result.

    Catches any exception from the tool function and converts it to
    a proper error_result, ensuring the MCP server always gets a
    valid ToolResult response.
    """
    @functools.wraps(func)
    async def wrapper(manager: SessionManager, args: Dict[str, Any]) -> ToolResult:
        try:
            return await func(manager, args)
        except Exception as e:
            return error_result(f"{func.__name__} error: {e}")
    return wrapper  # type: ignore


def requires_session(func: F) -> F:
    """
    Decorator that validates session exists and passes it to the tool.

    Extracts session_id from args, looks up the session, and if found,
    calls the decorated function with (session, manager, args).
    If session not found, returns an error_result.

    The decorated function signature changes from:
        async def tool(manager, args) -> ToolResult
    to:
        async def tool(session, manager, args) -> ToolResult
    """
    @functools.wraps(func)
    async def wrapper(manager: SessionManager, args: Dict[str, Any]) -> ToolResult:
        session_id = args.get("session_id", "")
        session = manager.get_session(session_id)
        if session is None:
            return error_result(f"Session not found: {session_id}")
        return await func(session, manager, args)
    return wrapper  # type: ignore
