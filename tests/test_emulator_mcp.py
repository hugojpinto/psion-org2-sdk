"""
MCP Server Unit Tests
=====================

Tests for the MCP server and tool implementations.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

from psion_sdk.emulator.mcp.server import (
    MCPServer,
    SessionManager,
    EmulatorSession,
)
from psion_sdk.emulator.mcp import tools


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def session_manager():
    """Create a session manager for testing."""
    return SessionManager(max_sessions=5, session_timeout=3600)


@pytest.fixture
def temp_rom():
    """Create a temporary ROM file for testing."""
    rom_data = bytearray([0x00] * 0x8000)
    rom_data[0x7FFE] = 0x20  # Reset vector high
    rom_data[0x7FFF] = 0x00  # Reset vector low -> $2000

    with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
        f.write(bytes(rom_data))
        path = Path(f.name)

    yield path
    path.unlink()


# =============================================================================
# Session Manager Tests
# =============================================================================

class TestSessionManager:
    """Test SessionManager functionality."""

    def test_create_session(self, session_manager, temp_rom):
        """Can create a session."""
        session = session_manager.create_session(model="XP", rom_path=temp_rom)

        assert session is not None
        assert session.session_id is not None
        assert session.model == "XP"
        assert session.emulator is not None

    def test_get_session(self, session_manager, temp_rom):
        """Can retrieve a session by ID."""
        session1 = session_manager.create_session(rom_path=temp_rom)
        session2 = session_manager.get_session(session1.session_id)

        assert session2 is not None
        assert session2.session_id == session1.session_id

    def test_get_nonexistent_session(self, session_manager):
        """Get nonexistent session returns None."""
        session = session_manager.get_session("nonexistent")
        assert session is None

    def test_destroy_session(self, session_manager, temp_rom):
        """Can destroy a session."""
        session = session_manager.create_session(rom_path=temp_rom)
        sid = session.session_id

        assert session_manager.destroy_session(sid) is True
        assert session_manager.get_session(sid) is None

    def test_destroy_nonexistent(self, session_manager):
        """Destroying nonexistent session returns False."""
        assert session_manager.destroy_session("nonexistent") is False

    def test_list_sessions(self, session_manager, temp_rom):
        """Can list all sessions."""
        session_manager.create_session(model="XP", rom_path=temp_rom)
        session_manager.create_session(model="XP", rom_path=temp_rom)

        sessions = session_manager.list_sessions()
        assert len(sessions) == 2

    def test_max_sessions_limit(self, session_manager, temp_rom):
        """Max sessions limit is enforced."""
        # Create up to max
        for _ in range(5):
            session_manager.create_session(rom_path=temp_rom)

        # Next should fail
        with pytest.raises(RuntimeError, match="Maximum sessions"):
            session_manager.create_session(rom_path=temp_rom)


# =============================================================================
# EmulatorSession Tests
# =============================================================================

class TestEmulatorSession:
    """Test EmulatorSession dataclass."""

    def test_to_dict(self, session_manager, temp_rom):
        """Session converts to dictionary."""
        session = session_manager.create_session(rom_path=temp_rom)
        d = session.to_dict()

        assert "session_id" in d
        assert "model" in d
        assert "created_at" in d
        assert "last_accessed" in d
        assert "total_cycles" in d

    def test_touch_updates_timestamp(self, session_manager, temp_rom):
        """touch() updates last_accessed."""
        session = session_manager.create_session(rom_path=temp_rom)
        initial_time = session.last_accessed

        # Small delay
        import time
        time.sleep(0.01)

        session.touch()
        assert session.last_accessed > initial_time


# =============================================================================
# Tool Tests - High Level
# =============================================================================

class TestHighLevelTools:
    """Test high-level MCP tools."""

    @pytest.mark.asyncio
    async def test_create_emulator(self, session_manager):
        """create_emulator creates a session."""
        # Note: This may fail if no default ROM is available
        try:
            result = await tools.create_emulator(
                session_manager,
                {"model": "XP"}
            )
            # If it worked, check success
            assert result.is_error is False or "ROM" in result.content[0]["text"]
        except FileNotFoundError:
            # Expected if no ROM available
            pass

    @pytest.mark.asyncio
    async def test_create_emulator_invalid_model(self, session_manager):
        """Invalid model returns error."""
        result = await tools.create_emulator(
            session_manager,
            {"model": "INVALID"}
        )
        assert result.is_error is True
        assert "Invalid model" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_press_key_no_session(self, session_manager):
        """press_key with invalid session returns error."""
        result = await tools.press_key(
            session_manager,
            {"session_id": "invalid", "key": "A"}
        )
        assert result.is_error is True
        assert "Session not found" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_screen_no_session(self, session_manager):
        """read_screen with invalid session returns error."""
        result = await tools.read_screen(
            session_manager,
            {"session_id": "invalid"}
        )
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_load_pack_file_not_found(self, session_manager, temp_rom):
        """load_pack with missing file returns error."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.load_pack(
            session_manager,
            {"session_id": session.session_id, "opk_path": "/nonexistent/file.opk"}
        )
        assert result.is_error is True
        assert "not found" in result.content[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_wait_for_text_empty(self, session_manager, temp_rom):
        """wait_for_text with empty text returns error."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.wait_for_text(
            session_manager,
            {"session_id": session.session_id, "text": ""}
        )
        assert result.is_error is True


# =============================================================================
# Tool Tests - Low Level
# =============================================================================

class TestLowLevelTools:
    """Test low-level MCP tools."""

    @pytest.mark.asyncio
    async def test_step(self, session_manager, temp_rom):
        """step executes one instruction."""
        session = session_manager.create_session(rom_path=temp_rom)

        # Inject some code
        code = bytes([0x86, 0x42, 0x01])  # LDAA #$42, NOP
        session.emulator.inject_program(code, entry_point=0x2000)

        result = await tools.step(
            session_manager,
            {"session_id": session.session_id}
        )

        assert result.is_error is False
        assert "$2000" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_run_cycles(self, session_manager, temp_rom):
        """run_cycles executes specified cycles."""
        session = session_manager.create_session(rom_path=temp_rom)

        # Inject NOPs
        code = bytes([0x01] * 100)
        session.emulator.inject_program(code, entry_point=0x2000)

        result = await tools.run_cycles(
            session_manager,
            {"session_id": session.session_id, "cycles": 50}
        )

        assert result.is_error is False
        assert "50" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_run_cycles_invalid(self, session_manager, temp_rom):
        """run_cycles with invalid cycles returns error."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.run_cycles(
            session_manager,
            {"session_id": session.session_id, "cycles": 0}
        )

        assert result.is_error is True
        assert "positive" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_memory(self, session_manager, temp_rom):
        """read_memory returns hex dump."""
        session = session_manager.create_session(rom_path=temp_rom)

        # Write some data
        session.emulator.write_byte(0x0500, 0x42)

        result = await tools.read_memory(
            session_manager,
            {"session_id": session.session_id, "address": 0x0500, "count": 16}
        )

        assert result.is_error is False
        assert "$0500" in result.content[0]["text"]
        assert "42" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_memory_invalid_address(self, session_manager, temp_rom):
        """read_memory with invalid address returns error."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.read_memory(
            session_manager,
            {"session_id": session.session_id, "address": 0x10000}
        )

        assert result.is_error is True
        assert "out of range" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_write_memory(self, session_manager, temp_rom):
        """write_memory writes bytes."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.write_memory(
            session_manager,
            {
                "session_id": session.session_id,
                "address": 0x0600,
                "data": [0x11, 0x22, 0x33]
            }
        )

        assert result.is_error is False
        assert session.emulator.read_byte(0x0600) == 0x11
        assert session.emulator.read_byte(0x0601) == 0x22

    @pytest.mark.asyncio
    async def test_write_memory_invalid_data(self, session_manager, temp_rom):
        """write_memory with invalid data returns error."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.write_memory(
            session_manager,
            {
                "session_id": session.session_id,
                "address": 0x0600,
                "data": [256]  # Invalid byte value
            }
        )

        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_set_breakpoint(self, session_manager, temp_rom):
        """set_breakpoint adds a breakpoint."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.set_breakpoint(
            session_manager,
            {
                "session_id": session.session_id,
                "address": 0x8100,
                "type": "pc"
            }
        )

        assert result.is_error is False
        assert "breakpoint set" in result.content[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_remove_breakpoint(self, session_manager, temp_rom):
        """remove_breakpoint removes a breakpoint."""
        session = session_manager.create_session(rom_path=temp_rom)
        session.emulator.add_breakpoint(0x8100)

        result = await tools.remove_breakpoint(
            session_manager,
            {"session_id": session.session_id, "address": 0x8100}
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_registers(self, session_manager, temp_rom):
        """get_registers returns register values."""
        session = session_manager.create_session(rom_path=temp_rom)

        # Set some register values via code
        code = bytes([0x86, 0x42, 0xC6, 0x55])  # LDAA #$42, LDAB #$55
        session.emulator.inject_program(code, entry_point=0x2000)
        session.emulator.step()
        session.emulator.step()

        result = await tools.get_registers(
            session_manager,
            {"session_id": session.session_id}
        )

        assert result.is_error is False
        text = result.content[0]["text"]
        assert "A:" in text
        assert "B:" in text
        assert "42" in text.upper()
        assert "55" in text.upper()

    @pytest.mark.asyncio
    async def test_get_display(self, session_manager, temp_rom):
        """get_display returns display state."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.get_display(
            session_manager,
            {"session_id": session.session_id}
        )

        assert result.is_error is False
        text = result.content[0]["text"]
        assert "Display State" in text


# =============================================================================
# Session Management Tools
# =============================================================================

class TestSessionManagementTools:
    """Test session management tools."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, session_manager):
        """list_sessions with no sessions."""
        result = await tools.list_sessions(session_manager, {})

        assert result.is_error is False
        assert "No active sessions" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_sessions_with_sessions(self, session_manager, temp_rom):
        """list_sessions with active sessions."""
        session_manager.create_session(rom_path=temp_rom)
        session_manager.create_session(rom_path=temp_rom)

        result = await tools.list_sessions(session_manager, {})

        assert result.is_error is False
        assert "(2)" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_destroy_session_tool(self, session_manager, temp_rom):
        """destroy_session tool removes session."""
        session = session_manager.create_session(rom_path=temp_rom)

        result = await tools.destroy_session(
            session_manager,
            {"session_id": session.session_id}
        )

        assert result.is_error is False
        assert "destroyed" in result.content[0]["text"].lower()
        assert session_manager.get_session(session.session_id) is None

    @pytest.mark.asyncio
    async def test_destroy_session_not_found(self, session_manager):
        """destroy_session with invalid ID returns error."""
        result = await tools.destroy_session(
            session_manager,
            {"session_id": "invalid"}
        )

        assert result.is_error is True


# =============================================================================
# MCP Server Tests
# =============================================================================

class TestMCPServer:
    """Test MCP server functionality."""

    def test_server_initialization(self):
        """Server initializes correctly."""
        server = MCPServer()

        assert server.session_manager is not None
        assert server.SERVER_NAME == "psion-emulator"

    def test_tool_registration(self):
        """All expected core tools are registered."""
        server = MCPServer()

        # Core tools that must always be present
        # Note: This list covers the essential tools; additional debugging tools
        # may be added without breaking this test
        expected_tools = [
            # Session management
            "create_emulator",
            "list_sessions",
            "destroy_session",
            # Program loading and execution
            "load_pack",  # Renamed from load_program
            "run_program",
            "boot_emulator",
            # Input
            "press_key",
            "press_key_and_run",
            "type_text",
            # Output
            "read_screen",
            "get_display",
            "save_screenshot",
            "wait_for_text",
            # Execution control
            "step",
            "run_cycles",
            "run_until_idle",
            # Memory
            "read_memory",
            "write_memory",
            "search_memory",
            # Debugging
            "set_breakpoint",
            "remove_breakpoint",
            "list_breakpoints",
            "get_registers",
        ]

        for tool_name in expected_tools:
            assert tool_name in server._tools, f"Missing tool: {tool_name}"
            assert tool_name in server._tool_definitions

    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        """Initialize returns server info."""
        server = MCPServer()

        result = await server.handle_initialize({})

        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "psion-emulator"

    @pytest.mark.asyncio
    async def test_handle_list_tools(self):
        """List tools returns tool definitions."""
        server = MCPServer()

        result = await server.handle_list_tools()

        assert "tools" in result
        assert len(result["tools"]) > 0

        # Check first tool has required fields
        tool = result["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_handle_call_unknown_tool(self):
        """Calling unknown tool returns error."""
        server = MCPServer()

        result = await server.handle_call_tool("unknown_tool", {})

        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_process_request_initialize(self):
        """Process initialize request."""
        server = MCPServer()

        response = await server.process_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "serverInfo" in response["result"]

    @pytest.mark.asyncio
    async def test_process_request_tools_list(self):
        """Process tools/list request."""
        server = MCPServer()

        response = await server.process_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })

        assert response["id"] == 2
        assert "tools" in response["result"]

    @pytest.mark.asyncio
    async def test_process_request_unknown_method(self):
        """Process unknown method returns error."""
        server = MCPServer()

        response = await server.process_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "unknown/method",
            "params": {}
        })

        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_process_notification(self):
        """Notification (no id) returns None."""
        server = MCPServer()

        response = await server.process_request({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })

        assert response is None
