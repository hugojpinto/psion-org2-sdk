"""
Psion Emulator MCP Server
=========================

Model Context Protocol (MCP) server for the Psion Organiser II emulator.

This server provides tools for:
- Creating and managing emulator instances
- Loading and executing programs
- Interacting with display and keyboard
- Debugging with breakpoints and watchpoints

The server uses JSON-RPC 2.0 over stdio for communication, following
the MCP specification.

Architecture:
    MCPServer
        └── SessionManager
                └── EmulatorSession (one per session_id)
                        └── Emulator instance

Usage:
    # Run as standalone server
    python -m psion_sdk.emulator.mcp.server

    # Or programmatically
    server = MCPServer()
    await server.run()

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import asyncio
import json
import sys
import uuid
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable, Awaitable
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

# Import emulator components
from psion_sdk import __version__
from ..emulator import Emulator, EmulatorConfig
from ..breakpoints import BreakEvent, BreakReason


# =============================================================================
# Session Management
# =============================================================================

@dataclass
class EmulatorSession:
    """
    Represents a single emulator session.

    Each session has its own Emulator instance and tracks metadata
    like creation time and last access time.

    Attributes:
        session_id: Unique identifier for this session
        emulator: The Emulator instance
        created_at: When the session was created
        last_accessed: When the session was last used
        model: The Psion model being emulated
        program_loaded: Whether a program has been loaded
    """
    session_id: str
    emulator: Emulator
    created_at: datetime = field(default_factory=_utcnow)
    last_accessed: datetime = field(default_factory=_utcnow)
    model: str = "XP"
    program_loaded: bool = False
    program_name: Optional[str] = None

    def touch(self) -> None:
        """Update last_accessed timestamp."""
        self.last_accessed = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session info to dictionary."""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "program_loaded": self.program_loaded,
            "program_name": self.program_name,
            "total_cycles": self.emulator.total_cycles,
            "pc": f"${self.emulator.cpu.pc:04X}",
        }


class SessionManager:
    """
    Manages multiple emulator sessions.

    Provides session lifecycle operations (create, get, destroy) and
    automatic cleanup of idle sessions.

    Attributes:
        max_sessions: Maximum number of concurrent sessions
        session_timeout: Seconds before idle sessions are cleaned up
    """

    def __init__(
        self,
        max_sessions: int = 10,
        session_timeout: int = 3600  # 1 hour default
    ):
        """
        Initialize session manager.

        Args:
            max_sessions: Maximum concurrent sessions (default 10)
            session_timeout: Idle timeout in seconds (default 3600)
        """
        self._sessions: Dict[str, EmulatorSession] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout

    def create_session(
        self,
        model: str = "XP",
        rom_path: Optional[Path] = None
    ) -> EmulatorSession:
        """
        Create a new emulator session.

        Args:
            model: Psion model to emulate ("CM", "XP", "LZ", "LZ64")
            rom_path: Optional custom ROM file path

        Returns:
            The created EmulatorSession

        Raises:
            RuntimeError: If maximum sessions reached
        """
        # Check session limit
        self._cleanup_expired()
        if len(self._sessions) >= self.max_sessions:
            raise RuntimeError(
                f"Maximum sessions ({self.max_sessions}) reached. "
                "Destroy unused sessions first."
            )

        # Create unique session ID
        session_id = str(uuid.uuid4())[:8]

        # Create emulator
        config = EmulatorConfig(model=model, rom_path=rom_path)
        emulator = Emulator(config)
        emulator.reset()

        # Create session
        session = EmulatorSession(
            session_id=session_id,
            emulator=emulator,
            model=model,
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[EmulatorSession]:
        """
        Get session by ID.

        Args:
            session_id: The session identifier

        Returns:
            EmulatorSession if found, None otherwise
        """
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def destroy_session(self, session_id: str) -> bool:
        """
        Destroy a session.

        Args:
            session_id: The session to destroy

        Returns:
            True if session was destroyed, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.

        Returns:
            List of session info dictionaries
        """
        self._cleanup_expired()
        return [s.to_dict() for s in self._sessions.values()]

    def _cleanup_expired(self) -> None:
        """Remove sessions that have been idle too long."""
        now = _utcnow()
        expired = []
        for sid, session in self._sessions.items():
            idle_seconds = (now - session.last_accessed).total_seconds()
            if idle_seconds > self.session_timeout:
                expired.append(sid)

        for sid in expired:
            del self._sessions[sid]


# =============================================================================
# MCP Protocol Types
# =============================================================================

@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ToolResult:
    """Result from an MCP tool execution."""
    content: List[Dict[str, Any]]
    is_error: bool = False


# =============================================================================
# MCP Server
# =============================================================================

class MCPServer:
    """
    MCP Server for Psion Emulator.

    Implements the Model Context Protocol to expose emulator functionality
    to AI agents and other MCP clients.

    The server communicates via JSON-RPC 2.0 over stdio.

    Attributes:
        session_manager: Manages emulator sessions
        tools: Dictionary of registered tools

    Example:
        server = MCPServer()
        await server.run()  # Run until shutdown
    """

    # Server information
    SERVER_NAME = "psion-emulator"
    SERVER_VERSION = __version__
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self):
        """Initialize MCP server."""
        self.session_manager = SessionManager()
        self._tools: Dict[str, Callable[..., Awaitable[ToolResult]]] = {}
        self._tool_definitions: Dict[str, ToolDefinition] = {}
        self._running = False

        # Register all tools
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all available tools."""
        # Import tool implementations
        from . import tools

        # High-level tools
        self._register_tool(
            "create_emulator",
            tools.create_emulator,
            "Create a new Psion emulator session",
            {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Psion model to emulate: CM, XP, LZ, or LZ64",
                        "enum": ["CM", "XP", "LZ", "LZ64"],
                        "default": "XP"
                    }
                },
                "required": []
            }
        )

        self._register_tool(
            "load_pack",
            tools.load_pack,
            "Load an OPK pack file into the emulator",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from create_emulator"
                    },
                    "opk_path": {
                        "type": "string",
                        "description": "Path to the .opk file to load"
                    },
                    "slot": {
                        "type": "integer",
                        "description": "Pack slot: 0=B:, 1=C:, 2=top slot",
                        "default": 0
                    }
                },
                "required": ["session_id", "opk_path"]
            }
        )

        self._register_tool(
            "run_program",
            tools.run_program,
            "Run the emulator for a specified number of cycles",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from create_emulator"
                    },
                    "max_cycles": {
                        "type": "integer",
                        "description": "Maximum cycles to execute",
                        "default": 1000000
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "press_key",
            tools.press_key,
            "Press a key on the emulator keyboard",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "key": {
                        "type": "string",
                        "description": "Key to press (e.g., 'A', 'EXE', 'MODE')"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["tap", "down", "up"],
                        "description": "Key action: tap (press+release), down, or up",
                        "default": "tap"
                    },
                    "hold_cycles": {
                        "type": "integer",
                        "description": "Cycles to hold key (for tap action)",
                        "default": 50000
                    }
                },
                "required": ["session_id", "key"]
            }
        )

        self._register_tool(
            "press_key_and_run",
            tools.press_key_and_run,
            "Press a key and run cycles in one call (convenience for navigation)",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "key": {
                        "type": "string",
                        "description": "Key to press (e.g., 'A', 'EXE', 'MODE')"
                    },
                    "hold_cycles": {
                        "type": "integer",
                        "description": "Cycles to hold key (default: 50000)",
                        "default": 50000
                    },
                    "run_cycles": {
                        "type": "integer",
                        "description": "Cycles to run after keypress (default: 200000)",
                        "default": 200000
                    }
                },
                "required": ["session_id", "key"]
            }
        )

        self._register_tool(
            "run_until_idle",
            tools.run_until_idle,
            "Run emulator until CPU enters idle loop (waiting for input)",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "max_cycles": {
                        "type": "integer",
                        "description": "Maximum cycles to run (default: 10000000)",
                        "default": 10000000
                    },
                    "idle_threshold": {
                        "type": "integer",
                        "description": "Cycles in same PC region to consider idle (default: 1000)",
                        "default": 1000
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "read_screen",
            tools.read_screen,
            "Read the current display content. Use 'image_lcd' format for "
            "realistic LCD rendering with visible pixel matrix grid.",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "lines", "image", "image_lcd"],
                        "description": "Output format: text (plain text), lines (array), "
                                       "image (compact PNG), image_lcd (LCD matrix style PNG)",
                        "default": "text"
                    },
                    "scale": {
                        "type": "integer",
                        "description": "Pixel scale factor (default: 2 for image, 3 for image_lcd)",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "pixel_gap": {
                        "type": "integer",
                        "description": "Gap between pixels within characters (image_lcd only, default: 1)",
                        "minimum": 0,
                        "maximum": 5
                    },
                    "char_gap": {
                        "type": "integer",
                        "description": "Gap between character cells (image_lcd only, default: 2)",
                        "minimum": 0,
                        "maximum": 10
                    },
                    "bezel": {
                        "type": "integer",
                        "description": "Border size around display (image_lcd only, default: 8)",
                        "minimum": 0,
                        "maximum": 50
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "boot_emulator",
            tools.boot_emulator,
            "Boot the emulator through complete startup sequence (reset, language select, to main menu)",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from create_emulator"
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "type_text",
            tools.type_text,
            "Type a string of text on the emulator keyboard",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type (letters, numbers, punctuation)"
                    },
                    "hold_cycles": {
                        "type": "integer",
                        "description": "Cycles to hold each key (default: 50000)",
                        "default": 50000
                    },
                    "delay_cycles": {
                        "type": "integer",
                        "description": "Cycles between keypresses (default: 150000)",
                        "default": 150000
                    }
                },
                "required": ["session_id", "text"]
            }
        )

        self._register_tool(
            "save_screenshot",
            tools.save_screenshot,
            "Save the current display as an image file",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to save the PNG file"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["image", "image_lcd"],
                        "description": "Output format: image (compact) or image_lcd (LCD matrix style)",
                        "default": "image_lcd"
                    },
                    "scale": {
                        "type": "integer",
                        "description": "Pixel scale factor",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "pixel_gap": {
                        "type": "integer",
                        "description": "Gap between pixels (image_lcd only)",
                        "minimum": 0,
                        "maximum": 5
                    },
                    "char_gap": {
                        "type": "integer",
                        "description": "Gap between characters (image_lcd only)",
                        "minimum": 0,
                        "maximum": 10
                    },
                    "bezel": {
                        "type": "integer",
                        "description": "Border size (image_lcd only)",
                        "minimum": 0,
                        "maximum": 50
                    }
                },
                "required": ["session_id", "file_path"]
            }
        )

        self._register_tool(
            "wait_for_text",
            tools.wait_for_text,
            "Run emulator until specific text appears on display",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to wait for"
                    },
                    "max_cycles": {
                        "type": "integer",
                        "description": "Maximum cycles to wait",
                        "default": 10000000
                    }
                },
                "required": ["session_id", "text"]
            }
        )

        # Low-level tools
        self._register_tool(
            "step",
            tools.step,
            "Execute a single CPU instruction",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "run_cycles",
            tools.run_cycles,
            "Execute exact number of CPU cycles",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "cycles": {
                        "type": "integer",
                        "description": "Number of cycles to execute"
                    }
                },
                "required": ["session_id", "cycles"]
            }
        )

        self._register_tool(
            "read_memory",
            tools.read_memory,
            "Read bytes from emulator memory",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "address": {
                        "type": "integer",
                        "description": "Starting address (0-65535)"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of bytes to read",
                        "default": 1
                    }
                },
                "required": ["session_id", "address"]
            }
        )

        self._register_tool(
            "write_memory",
            tools.write_memory,
            "Write bytes to emulator memory",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "address": {
                        "type": "integer",
                        "description": "Starting address (0-65535)"
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Bytes to write (0-255 each)"
                    }
                },
                "required": ["session_id", "address", "data"]
            }
        )

        self._register_tool(
            "search_memory",
            tools.search_memory,
            "Search for byte pattern in emulator memory",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "pattern": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Bytes to search for (0-255 each)"
                    },
                    "start": {
                        "type": "integer",
                        "description": "Start address (default: 0)",
                        "default": 0
                    },
                    "end": {
                        "type": "integer",
                        "description": "End address (default: 65535)",
                        "default": 65535
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum matches to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["session_id", "pattern"]
            }
        )

        self._register_tool(
            "set_breakpoint",
            tools.set_breakpoint,
            "Set a breakpoint or watchpoint with optional condition",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "address": {
                        "type": "integer",
                        "description": "Memory address (0-65535)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["pc", "read", "write"],
                        "description": "Type: pc (default), read, or write",
                        "default": "pc"
                    },
                    "when_register": {
                        "type": "string",
                        "description": "Optional condition register: a, b, d, x, sp, pc, flag_c, flag_v, flag_z, flag_n"
                    },
                    "when_op": {
                        "type": "string",
                        "enum": ["==", "!=", "<", "<=", ">", ">=", "&"],
                        "description": "Optional condition operator (& is bitwise AND test)"
                    },
                    "when_value": {
                        "type": "integer",
                        "description": "Optional condition value"
                    }
                },
                "required": ["session_id", "address"]
            }
        )

        self._register_tool(
            "remove_breakpoint",
            tools.remove_breakpoint,
            "Remove a breakpoint or watchpoint at an address",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "address": {
                        "type": "integer",
                        "description": "Memory address (0-65535)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["all", "pc", "read", "write"],
                        "description": "What to remove: all (default), pc, read, or write",
                        "default": "all"
                    }
                },
                "required": ["session_id", "address"]
            }
        )

        self._register_tool(
            "list_breakpoints",
            tools.list_breakpoints,
            "List all active breakpoints, watchpoints, and register conditions",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "get_registers",
            tools.get_registers,
            "Get current CPU register values",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    }
                },
                "required": ["session_id"]
            }
        )

        self._register_tool(
            "get_display",
            tools.get_display,
            "Get detailed display state",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    }
                },
                "required": ["session_id"]
            }
        )

        # Session management tools
        self._register_tool(
            "list_sessions",
            tools.list_sessions,
            "List all active emulator sessions",
            {
                "type": "object",
                "properties": {},
                "required": []
            }
        )

        self._register_tool(
            "destroy_session",
            tools.destroy_session,
            "Destroy an emulator session",
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to destroy"
                    }
                },
                "required": ["session_id"]
            }
        )

    def _register_tool(
        self,
        name: str,
        handler: Callable[..., Awaitable[ToolResult]],
        description: str,
        input_schema: Dict[str, Any]
    ) -> None:
        """
        Register a tool with the server.

        Args:
            name: Tool name
            handler: Async function to handle tool calls
            description: Human-readable description
            input_schema: JSON Schema for tool input
        """
        self._tools[name] = handler
        self._tool_definitions[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema
        )

    # =========================================================================
    # MCP Protocol Methods
    # =========================================================================

    async def handle_initialize(
        self,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle initialize request.

        Returns server capabilities and info.
        """
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {}  # We support tools
            },
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION
            }
        }

    async def handle_list_tools(self) -> Dict[str, Any]:
        """
        Handle tools/list request.

        Returns list of available tools.
        """
        tools = []
        for name, defn in self._tool_definitions.items():
            tools.append({
                "name": defn.name,
                "description": defn.description,
                "inputSchema": defn.input_schema
            })
        return {"tools": tools}

    async def handle_call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle tools/call request.

        Executes the requested tool and returns results.
        """
        if name not in self._tools:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }],
                "isError": True
            }

        try:
            handler = self._tools[name]
            result = await handler(self.session_manager, arguments)
            return {
                "content": result.content,
                "isError": result.is_error
            }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Tool error: {str(e)}"
                }],
                "isError": True
            }

    # =========================================================================
    # JSON-RPC Processing
    # =========================================================================

    async def process_request(
        self,
        request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a JSON-RPC request.

        Args:
            request: The JSON-RPC request object

        Returns:
            Response object, or None for notifications
        """
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        # Route to appropriate handler
        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "notifications/initialized":
                # Client acknowledged initialization
                return None
            elif method == "tools/list":
                result = await self.handle_list_tools()
            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = await self.handle_call_tool(name, arguments)
            else:
                result = None
                error = {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
                if request_id is not None:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": error
                    }
                return None

            # Build response
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
            return None

        except Exception as e:
            error = {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": error
                }
            return None

    # =========================================================================
    # Server Main Loop
    # =========================================================================

    async def run(self) -> None:
        """
        Run the MCP server.

        Reads JSON-RPC requests from stdin, processes them, and writes
        responses to stdout. Runs until stdin is closed.
        """
        self._running = True
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol, sys.stdin
        )

        while self._running:
            try:
                # Read a line
                line = await reader.readline()
                if not line:
                    break  # EOF

                line = line.decode('utf-8').strip()
                if not line:
                    continue

                # Parse JSON-RPC request
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    # Invalid JSON
                    continue

                # Process request
                response = await self.process_request(request)

                # Send response if any
                if response is not None:
                    response_line = json.dumps(response) + "\n"
                    sys.stdout.write(response_line)
                    sys.stdout.flush()

            except Exception as e:
                # Log error but continue running
                sys.stderr.write(f"Server error: {e}\n")
                sys.stderr.flush()

    def shutdown(self) -> None:
        """Signal the server to shut down."""
        self._running = False


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """Run the MCP server from command line."""
    server = MCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
