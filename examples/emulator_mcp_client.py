#!/usr/bin/env python3
"""
Psion Emulator MCP Client Demo
==============================

This script demonstrates how to interact with the Psion emulator
via the MCP (Model Context Protocol) server.

The MCP server can be integrated with:
- Claude Desktop (recommended)
- Custom MCP clients
- Direct JSON-RPC over stdio

Usage:
    source .venv/bin/activate
    python examples/emulator_mcp_client.py

For Claude Desktop integration, add to:
~/Library/Application Support/Claude/claude_desktop_config.json

{
  "mcpServers": {
    "psion-emulator": {
      "command": "/path/to/psion/.venv/bin/python",
      "args": ["-m", "psion_sdk.emulator.mcp.server"],
      "cwd": "/path/to/psion"
    }
  }
}

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import subprocess
import json
import base64
from pathlib import Path


class MCPClient:
    """Simple MCP client for the Psion emulator server."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["python", "-m", "psion_sdk.emulator.mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self._request_id = 0
        self._initialize()

    def _initialize(self):
        """Initialize the MCP connection."""
        self._send({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "psion-demo", "version": "1.0"}
            }
        })
        self._receive()

    def _send(self, request):
        """Send a JSON-RPC request."""
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()

    def _receive(self):
        """Receive a JSON-RPC response."""
        line = self.proc.stdout.readline()
        return json.loads(line) if line else None

    def call_tool(self, name: str, args: dict) -> dict:
        """Call an MCP tool and return the result."""
        self._request_id += 1
        self._send({
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args}
        })
        return self._receive()

    def get_text_result(self, response: dict) -> str:
        """Extract text from tool response."""
        for content in response.get("result", {}).get("content", []):
            if content.get("type") == "text":
                return content.get("text", "")
        return ""

    def get_image_data(self, response: dict) -> bytes:
        """Extract image data from tool response."""
        for content in response.get("result", {}).get("content", []):
            if content.get("type") == "image":
                return base64.b64decode(content.get("data", ""))
        return b""

    def close(self):
        """Close the MCP connection."""
        self.proc.terminate()


def main():
    output_dir = Path("trash")
    output_dir.mkdir(exist_ok=True)

    print("Starting MCP client...")
    client = MCPClient()

    try:
        # ======================================================================
        # List available tools
        # ======================================================================
        print("\nAvailable MCP tools:")
        print("  - create_emulator: Create a new emulator session")
        print("  - load_program: Load an OPK file")
        print("  - run_program: Run for N cycles")
        print("  - press_key: Press a keyboard key")
        print("  - read_screen: Get display content (text/image/image_lcd)")
        print("  - wait_for_text: Run until text appears")
        print("  - step: Execute single instruction")
        print("  - run_cycles: Execute exact cycles")
        print("  - read_memory: Read memory bytes")
        print("  - write_memory: Write memory bytes")
        print("  - set_breakpoint: Add breakpoint")
        print("  - remove_breakpoint: Remove breakpoint")
        print("  - get_registers: Get CPU state")
        print("  - get_display: Get detailed display info")
        print("  - list_sessions: List active sessions")
        print("  - destroy_session: Clean up session")

        # ======================================================================
        # Create emulator session
        # ======================================================================
        print("\n" + "=" * 60)
        print("Creating LZ64 emulator session...")
        result = client.call_tool("create_emulator", {"model": "LZ64"})
        text = client.get_text_result(result)
        print(f"  {text}")

        # Extract session ID
        session_id = None
        for line in text.split("\n"):
            if "Session ID:" in line:
                session_id = line.split("Session ID:")[1].strip().split()[0]
                break

        if not session_id:
            print("ERROR: Could not get session ID")
            return

        print(f"  Session ID: {session_id}")

        # ======================================================================
        # Boot the emulator
        # ======================================================================
        print("\nBooting emulator (5M cycles)...")
        client.call_tool("run_cycles", {
            "session_id": session_id,
            "cycles": 5_000_000
        })

        # Select English
        print("Selecting English...")
        client.call_tool("press_key", {"session_id": session_id, "key": "EXE"})
        client.call_tool("run_cycles", {"session_id": session_id, "cycles": 2_000_000})

        # ======================================================================
        # Read screen content
        # ======================================================================
        print("\nReading screen (text format):")
        result = client.call_tool("read_screen", {
            "session_id": session_id,
            "format": "text"
        })
        print(client.get_text_result(result))

        # ======================================================================
        # Get LCD-style screenshot
        # ======================================================================
        print("\nGetting LCD-style screenshot...")
        result = client.call_tool("read_screen", {
            "session_id": session_id,
            "format": "image_lcd",
            "scale": 4,
            "pixel_gap": 1,
            "char_gap": 3,
            "bezel": 12
        })

        img_data = client.get_image_data(result)
        if img_data:
            output_path = output_dir / "mcp_demo_menu.png"
            output_path.write_bytes(img_data)
            print(f"  Saved: {output_path} ({len(img_data)} bytes)")

        # ======================================================================
        # Get CPU registers
        # ======================================================================
        print("\nGetting CPU registers:")
        result = client.call_tool("get_registers", {"session_id": session_id})
        print(client.get_text_result(result))

        # ======================================================================
        # Clean up
        # ======================================================================
        print("\nDestroying session...")
        client.call_tool("destroy_session", {"session_id": session_id})
        print("  Done!")

    finally:
        client.close()

    print(f"\nScreenshots saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
