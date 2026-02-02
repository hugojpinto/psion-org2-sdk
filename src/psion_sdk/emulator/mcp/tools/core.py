"""
Core MCP Tool Utilities
=======================

Base types and result helper functions for MCP tools.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any, Dict, List

from ..server import ToolResult


def text_content(text: str) -> List[Dict[str, Any]]:
    """Create text content for tool result."""
    return [{"type": "text", "text": text}]


def error_result(message: str) -> ToolResult:
    """Create error tool result."""
    return ToolResult(content=text_content(message), is_error=True)


def success_result(text: str) -> ToolResult:
    """Create success tool result."""
    return ToolResult(content=text_content(text), is_error=False)
