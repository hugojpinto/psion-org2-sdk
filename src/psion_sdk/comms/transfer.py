"""
FTRAN File Transfer Protocol for Psion Organiser II
====================================================

This module implements the FTRAN (File Transfer) overlay protocol used
for transferring files between a PC and Psion Organiser II.

Protocol Architecture
---------------------
**CRITICAL**: The FTRAN protocol operates in a server-client model where
the **Psion is always the client** that initiates requests, and the
**PC acts as a passive server** responding to those requests.

This is counter-intuitive but essential to understand:

- **Psion RECEIVE mode** (PC→Psion): The Psion requests a file from PC.
  The PC serves the file content when asked via GetData commands.

- **Psion SEND mode** (Psion→PC): The Psion pushes a file to PC.
  The PC receives data via PutData commands and acknowledges each.

Protocol Flow: Serving a File (Psion in RECEIVE mode)
----------------------------------------------------
```
PSION (Client)                    PC (Server)
    |                                  |
    | ── DATA: "FTRAN" ────────────→  |  Psion announces overlay
    |                                  |
    | ←───── ACK + empty DATA ──────  |  PC acknowledges
    |                                  |
    | ── DATA: Open mode=00 fname ─→  |  Psion requests file
    |                                  |
    | ←─ ACK + DATA: file info ─────  |  PC sends file metadata
    |                                  |
    | ── DATA: GetData 254 ────────→  |  Psion requests data chunk
    |                                  |
    | ←─ ACK + DATA: raw bytes ─────  |  PC sends file content
    |                                  |
    |     ... repeat until EOF ...     |
    |                                  |
    | ── DATA: GetData 254 ────────→  |  Psion requests more
    |                                  |
    | ←───── ACK (no data) ─────────  |  PC signals EOF
    | ←───── DISCONNECT 0xEE ───────  |  PC terminates
    |                                  |
```

Protocol Flow: Receiving a File (Psion in SEND mode)
---------------------------------------------------
This uses a **two-connection protocol**:

**Connection 1: File existence check**
```
PSION                              PC
    | ── FTRAN overlay ─────────→ |
    | ←── ACK + empty DATA ────── |
    | ── Open mode=04 fname ───→  |  (mode 04 = check exists)
    | ←── ACK + empty DATA ────── |
    | ── Close ─────────────────→ |
    | ←── ACK + empty DATA ────── |
    | ── DISCONNECT ────────────→ |
```

User confirms "File exists. Overwrite?" on Psion...

**Connection 2: Actual data transfer**
```
PSION                              PC
    | ── FTRAN overlay ─────────→ |
    | ←── ACK + empty DATA ────── |
    | ── Open mode=01 fname ───→  |  (mode 01 = create)
    | ←── ACK + empty DATA ────── |
    | ── PutData: chunk 1 ──────→ |
    | ←── ACK + empty DATA ────── |
    | ── PutData: chunk 2 ──────→ |
    | ←── ACK + empty DATA ────── |
    |     ... more chunks ...      |
    | ── Close ─────────────────→ |
    | ←── ACK + empty DATA ────── |
    | ── DISCONNECT ────────────→ |
```

File Types and Open Response Format
-----------------------------------
For OPL files (type=0x01), the Open response must include metadata:
```
01 <blocklen> 81 00 00 <len_hi> <len_lo>
```
- 01: Status OK
- blocklen: Block size (typically 70 = 0x46)
- 81: OPL file marker
- 00 00: OPL start offset
- len_hi len_lo: File length in **big-endian**

For ODB files (type=0x00), simpler format:
```
00 <len_lo> <len_hi>
```
- 00: Status OK
- len_lo len_hi: File length in little-endian

References
----------
- FTRAN_PROTOCOL_NOTES.md: Detailed protocol investigation notes
- https://www.jaapsch.net/psion/protocol.htm
"""

import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Final, Optional, Tuple

from psion_sdk.comms.link import LinkProtocol, Packet, PacketType
from psion_sdk.errors import CommsError, ConnectionError, ProtocolError, TransferError

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# FTRAN Protocol Constants
# =============================================================================

# Overlay name for file transfer
FTRAN_OVERLAY: Final[bytes] = b"FTRAN"
FTRAN_OVERLAY_NULL: Final[bytes] = b"FTRAN\x00"

# Maximum data size per transfer block
# Leave room for command byte in the 256-byte packet limit
MAX_BLOCK_SIZE: Final[int] = 254

# Default OPL block length
# Block length from CommsLink capture (0x21 = 33 decimal)
DEFAULT_OPL_BLOCK_LENGTH: Final[int] = 0x21

# OPL file marker byte
OPL_MARKER: Final[int] = 0x81

# EOF disconnect byte
EOF_DISCONNECT_BYTE: Final[int] = 0xEE

# Command codes
CMD_OPEN: Final[int] = 0x00
CMD_CLOSE: Final[int] = 0x01
CMD_PUT_DATA: Final[int] = 0x02
CMD_GET_DATA: Final[int] = 0x03


# =============================================================================
# Enumerations
# =============================================================================

class OpenMode(IntEnum):
    """
    File open modes for FTRAN protocol.

    These modes control how files are opened and whether they can
    be created or must already exist.
    """

    READ_ONLY = 0x00        # Open existing file for reading only
    CREATE_REPLACE = 0x01   # Create new file or replace existing
    REPLACE = 0x02          # Replace existing (fail if not exists)
    CREATE_NEW = 0x03       # Create new (fail if exists)
    UPDATE = 0x04           # Check if file exists (used in two-connection protocol)


class FileType(IntEnum):
    """
    File types for FTRAN protocol.

    The file type affects how data is transferred and the Open response format.
    """

    ODB = 0x00         # Data file (ODB format)
    OPL = 0x01         # Program file (OPL text format)
    BINARY = 0x00      # Alias for ODB (backward compatibility)
    ASCII = 0x01       # Alias for OPL (backward compatibility)
    DIRECTORY = 0x02   # Directory listing (special type for Open)


class ResponseStatus(IntEnum):
    """
    Response status codes from FTRAN operations.

    These codes are returned in the first byte of response packets.
    """

    OK = 0x00               # Operation successful
    FILE_NOT_FOUND = 0x02   # File does not exist
    FILE_EXISTS = 0x05      # File already exists (for CREATE_NEW)
    DISK_FULL = 0x06        # No space on device
    END_OF_FILE = 0x10      # End of file reached
    IO_ERROR = 0x20         # General I/O error


# =============================================================================
# Progress Callback Type
# =============================================================================

# Type alias for progress callback: (bytes_done, total_bytes) -> None
ProgressCallback = Callable[[int, int], None]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DirectoryEntry:
    """
    Represents a file entry from a directory listing.

    Attributes:
        name: File or procedure name
        type_code: File type indicator from device
        size: File size in bytes (if available)
    """

    name: str
    type_code: Optional[int] = None
    size: Optional[int] = None

    def __str__(self) -> str:
        """Format entry for display."""
        if self.size is not None:
            return f"{self.name:12} {self.size:6d} bytes"
        return self.name


@dataclass
class FTRANCommand:
    """
    Represents a parsed FTRAN command from the Psion.

    Attributes:
        command: Command code (CMD_OPEN, CMD_CLOSE, etc.)
        mode: Open mode (for Open commands)
        file_type: File type (for Open commands)
        filename: Filename (for Open commands)
        data: Raw data (for PutData commands)
        length: Requested length (for GetData commands)
    """

    command: int
    mode: Optional[int] = None
    file_type: Optional[int] = None
    filename: Optional[str] = None
    data: Optional[bytes] = None
    length: Optional[int] = None


# =============================================================================
# File Transfer Class
# =============================================================================

class FileTransfer:
    """
    High-level file transfer operations using FTRAN protocol.

    This class provides methods for sending and receiving files
    to/from a Psion Organiser II. It correctly implements the
    FTRAN protocol where the Psion acts as client and PC as server.

    Key Protocol Insights
    ---------------------
    - The PC always responds with ACK + DATA to every Psion DATA packet
    - For GetData responses, send RAW file bytes (no 0x02 prefix)
    - For EOF, wait for final GetData, ACK it, then DISCONNECT with 0xEE
    - Receiving files uses a two-connection protocol (mode 04 check, then mode 01 transfer)

    Thread Safety
    -------------
    This class is NOT thread-safe. Only use from a single thread
    or protect all method calls with external synchronization.

    Example:
        link = LinkProtocol(port)
        link.connect()
        transfer = FileTransfer(link)

        # Serve a file to Psion (Psion in RECEIVE mode)
        transfer.serve_file("MYFILE", file_data, FileType.OPL)

        # Receive a file from Psion (Psion in SEND mode)
        filename, data = transfer.receive_file()

        link.disconnect()
    """

    # Timeout for waiting for Psion commands
    COMMAND_TIMEOUT: Final[float] = 30.0

    # Short delay between ACK and DATA response
    RESPONSE_DELAY: Final[float] = 0.02

    def __init__(self, link: LinkProtocol):
        """
        Initialize the file transfer handler.

        Args:
            link: LinkProtocol instance. For receive operations, the
                  connection is established internally. For send operations,
                  the link should already be connected.
        """
        self.link = link
        self._current_sequence = 1

    # -------------------------------------------------------------------------
    # Low-Level Protocol Helpers
    # -------------------------------------------------------------------------

    def _send_ack(self, sequence: int) -> None:
        """
        Send an ACK packet with the specified sequence number.

        Args:
            sequence: Sequence number to acknowledge.
        """
        ack = Packet(PacketType.ACK, sequence=sequence, data=b"")
        self.link._send_packet(ack)
        logger.debug("TX: ACK seq=%d", sequence)

    def _send_data_response(self, sequence: int, data: bytes = b"") -> None:
        """
        Send a DATA response packet with the specified sequence number.

        Args:
            sequence: Sequence number for the response.
            data: Optional data payload.
        """
        pkt = Packet(PacketType.DATA, sequence=sequence, data=data)
        self.link._send_packet(pkt)
        if data:
            logger.debug("TX: DATA seq=%d len=%d", sequence, len(data))
        else:
            logger.debug("TX: DATA seq=%d (empty)", sequence)

    def _send_ack_and_data(self, sequence: int, data: bytes = b"") -> None:
        """
        Send ACK followed by DATA response (standard FTRAN response pattern).

        This is the core response pattern: every Psion DATA packet must be
        answered with ACK + DATA (even if DATA is empty).

        Args:
            sequence: Sequence number for both packets.
            data: Optional data payload for the DATA packet.
        """
        self._send_ack(sequence)
        time.sleep(self.RESPONSE_DELAY)
        self._send_data_response(sequence, data)

    def _send_disconnect(self, data: bytes = b"") -> None:
        """
        Send a DISCONNECT packet.

        Args:
            data: Optional data (e.g., bytes([0xEE]) for EOF).
        """
        pkt = Packet(PacketType.DISCONNECT, sequence=0, data=data)
        self.link._send_packet(pkt)
        logger.debug("TX: DISCONNECT data=%s", data.hex() if data else "(empty)")

    def _receive_data_packet(self, timeout: float = None) -> Packet:
        """
        Receive a DATA packet from the Psion.

        Args:
            timeout: Optional timeout override.

        Returns:
            Received DATA packet.

        Raises:
            ProtocolError: If non-DATA packet received.
            ConnectionError: If DISCONNECT received.
            TimeoutError: If no packet within timeout.
        """
        if timeout is None:
            timeout = self.COMMAND_TIMEOUT

        packet = self.link._receive_packet(timeout=timeout)

        if packet.type == PacketType.DISCONNECT:
            logger.debug("RX: DISCONNECT")
            raise ConnectionError("Psion disconnected")

        if packet.type != PacketType.DATA:
            raise ProtocolError(f"Expected DATA packet, got {packet.type.name}")

        logger.debug("RX: DATA seq=%d len=%d", packet.sequence, len(packet.data))
        return packet

    def _parse_ftran_command(self, data: bytes) -> FTRANCommand:
        """
        Parse a raw FTRAN command from packet data.

        Args:
            data: Raw packet data.

        Returns:
            Parsed FTRANCommand.

        Raises:
            ProtocolError: If command cannot be parsed.
        """
        if not data:
            raise ProtocolError("Empty FTRAN command")

        command = data[0]

        if command == CMD_OPEN:
            if len(data) < 4:
                raise ProtocolError(f"Open command too short: {len(data)} bytes")
            mode = data[1]
            file_type = data[2]
            # Filename is null-terminated string starting at byte 3
            filename_bytes = data[3:]
            null_pos = filename_bytes.find(0x00)
            if null_pos >= 0:
                filename = filename_bytes[:null_pos].decode('ascii', errors='replace')
            else:
                filename = filename_bytes.decode('ascii', errors='replace')
            return FTRANCommand(
                command=command,
                mode=mode,
                file_type=file_type,
                filename=filename
            )

        elif command == CMD_CLOSE:
            return FTRANCommand(command=command)

        elif command == CMD_PUT_DATA:
            return FTRANCommand(command=command, data=data[1:])

        elif command == CMD_GET_DATA:
            length = data[1] if len(data) > 1 else MAX_BLOCK_SIZE
            return FTRANCommand(command=command, length=length)

        else:
            raise ProtocolError(f"Unknown FTRAN command: 0x{command:02X}")

    def _build_open_response(
        self,
        file_type: int,
        file_size: int,
        block_length: int = 0x21  # Match CommsLink: 33 bytes
    ) -> bytes:
        """
        Build the Open response data for a file.

        Format captured from original CommsLink software:
        - OPL: 06 <blocklen> 81 00 00 <len_hi> <len_lo>
        - ODB: 00 <len_lo> <len_hi>

        Args:
            file_type: File type (OPL or ODB).
            file_size: File size in bytes.
            block_length: Block length for OPL files (default 0x21 = 33).

        Returns:
            Open response data bytes.
        """
        if file_type == FileType.OPL:
            # OPL format: 06 <blocklen> 81 00 00 <len_hi> <len_lo>
            # Captured from CommsLink: 06 21 81 00 00 06 1d
            # Length is BIG-ENDIAN for OPL!
            return bytes([
                0x06,                           # Record type (from CommsLink capture)
                block_length,                   # Block length (0x21 = 33)
                OPL_MARKER,                     # OPL marker (0x81)
                0x00, 0x00,                     # OPL start offset
                (file_size >> 8) & 0xFF,        # Length high byte (big-endian)
                file_size & 0xFF,               # Length low byte
            ])
        else:
            # ODB format: 00 <len_lo> <len_hi>
            # Length is LITTLE-ENDIAN for ODB
            return bytes([
                0x00,                           # Status OK
                file_size & 0xFF,               # Length low byte
                (file_size >> 8) & 0xFF,        # Length high byte
            ])

    # -------------------------------------------------------------------------
    # Wait for FTRAN Overlay
    # -------------------------------------------------------------------------

    def _wait_for_ftran_overlay(self, timeout: float = None) -> int:
        """
        Wait for the Psion to send the FTRAN overlay name.

        This is the first step after connection: Psion sends "FTRAN"
        to indicate it wants to use the file transfer protocol.

        Args:
            timeout: Optional timeout override.

        Returns:
            Sequence number of the received packet.

        Raises:
            ProtocolError: If overlay name is not "FTRAN".
            TimeoutError: If no packet received.
        """
        packet = self._receive_data_packet(timeout)

        if packet.data != FTRAN_OVERLAY:
            raise ProtocolError(
                f"Expected FTRAN overlay, got: {packet.data!r}"
            )

        logger.info("Received FTRAN overlay")
        return packet.sequence

    # -------------------------------------------------------------------------
    # Serve File (PC → Psion, Psion in RECEIVE mode)
    # -------------------------------------------------------------------------

    def serve_file(
        self,
        filename: str,
        data: bytes,
        file_type: FileType = FileType.OPL,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Serve a file to the Psion device.

        The Psion must be in RECEIVE mode. When the user enters a filename
        on the Psion, the Psion sends a request to the PC, and this method
        responds with the file content.

        **Important**: The `filename` parameter should match what the user
        types on the Psion. If the user types "TEST.OPL", you should pass
        "TEST" as the filename (Psion strips extensions for the request).

        Args:
            filename: Name of the file to serve (used for logging/verification).
            data: File contents to send.
            file_type: Type of file (OPL or ODB).
            progress: Optional callback for progress updates.
                      Called with (bytes_sent, total_bytes).

        Raises:
            TransferError: If the transfer fails.
            ConnectionError: If Psion disconnects unexpectedly.
            ProtocolError: If protocol violation occurs.

        Example:
            # Read an OPL file and serve it
            with open('program.opl', 'rb') as f:
                data = f.read()

            # Start COMMS > RECEIVE on Psion, enter "PROGRAM.OPL"
            transfer.serve_file("PROGRAM", data, FileType.OPL)
        """
        total_bytes = len(data)
        logger.info("Ready to serve file '%s' (%d bytes, type=%s)",
                    filename, total_bytes, file_type.name)

        # Use continuous loop to handle multiple connection attempts
        # (user may say "No" to "File exists?" and retry)
        bytes_sent = 0
        actual_type = file_type

        while True:
            result = self._serve_file_connection(
                filename, data, file_type, total_bytes, bytes_sent, progress
            )

            if result == 'complete':
                # Transfer finished successfully
                return
            elif result == 'retry':
                # User said "No" to overwrite, wait for next connection
                logger.info("Psion disconnected, waiting for retry...")
                bytes_sent = 0  # Reset for fresh transfer
                continue
            else:
                raise ProtocolError(f"Unexpected result from connection handler: {result}")

    def _serve_file_connection(
        self,
        filename: str,
        data: bytes,
        file_type: FileType,
        total_bytes: int,
        bytes_sent: int,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """
        Handle a single connection attempt for serving a file.

        Returns:
            'complete' if transfer finished
            'retry' if user said No to overwrite (should wait for new connection)
        """
        import time

        # Build Link Request packet for handshake polling
        link_request = Packet(PacketType.LINK_REQUEST, sequence=0, data=b"")

        # State machine
        state = 'HANDSHAKE'
        buffer = bytearray()
        got_ftran = False
        actual_type = file_type

        # Timing
        start_time = time.time()
        last_link_req_time = 0.0
        LINK_REQ_INTERVAL = 0.2
        READ_TIMEOUT = 0.05
        TIMEOUT = 120.0

        old_timeout = self.link.port.timeout
        self.link.port.timeout = READ_TIMEOUT

        try:
            while time.time() - start_time < TIMEOUT:
                now = time.time()

                # Send Link Requests during handshake
                if state == 'HANDSHAKE' and (now - last_link_req_time) >= LINK_REQ_INTERVAL:
                    self.link._send_packet(link_request)
                    last_link_req_time = now

                # Read available data
                chunk = self.link.port.read(512)
                if chunk:
                    buffer.extend(chunk)

                # Parse packets
                while True:
                    packet, remaining = self._parse_packet_from_buffer(bytes(buffer))
                    buffer = bytearray(remaining)
                    if packet is None:
                        break

                    if state == 'HANDSHAKE' and packet.type == PacketType.LINK_REQUEST:
                        logger.info("Connection established")
                        ack = Packet(PacketType.ACK, sequence=0, data=b"")
                        self.link._send_packet(ack)
                        state = 'CONNECTED'
                        self.link._connected = True
                        got_ftran = False

                    elif packet.type == PacketType.DISCONNECT:
                        logger.debug("RX: DISCONNECT")
                        self.link._connected = False
                        # User said No to overwrite - return to allow retry
                        return 'retry'

                    elif packet.type == PacketType.ACK:
                        logger.debug("RX: ACK seq=%d", packet.sequence)

                    elif packet.type == PacketType.DATA:
                        seq = packet.sequence

                        if packet.data == FTRAN_OVERLAY:
                            logger.info("Received FTRAN overlay")
                            self._send_ack_and_data(seq)
                            got_ftran = True

                        elif packet.data and got_ftran:
                            cmd = self._parse_ftran_command(packet.data)

                            if cmd.command == CMD_OPEN:
                                logger.info(
                                    "Psion requested: '%s' (mode=0x%02X, type=0x%02X)",
                                    cmd.filename, cmd.mode, cmd.file_type
                                )

                                # Check filename matches what we're serving
                                if cmd.filename and cmd.filename.upper() != filename.upper():
                                    logger.warning(
                                        "File not found: Psion requested '%s', serving '%s'",
                                        cmd.filename, filename
                                    )
                                    # Send ACK then DISCONNECT with FILE_NOT_FOUND error
                                    self._send_ack(seq)
                                    self._send_disconnect(bytes([189]))  # FILE_NOT_FOUND
                                    return 'retry'  # Allow them to try again with correct name

                                actual_type = cmd.file_type if cmd.file_type else file_type
                                open_response = self._build_open_response(actual_type, total_bytes)
                                self._send_ack_and_data(seq, open_response)
                                logger.debug("Sent Open response: %s", open_response.hex())

                            elif cmd.command == CMD_GET_DATA:
                                requested_len = cmd.length if cmd.length else MAX_BLOCK_SIZE
                                logger.debug("GetData: request %d bytes", requested_len)

                                if bytes_sent >= total_bytes:
                                    # EOF - all data sent
                                    logger.info("EOF reached, sending DISCONNECT")
                                    self._send_ack(seq)
                                    time.sleep(self.RESPONSE_DELAY)
                                    self._send_disconnect(bytes([EOF_DISCONNECT_BYTE]))
                                    logger.info("Transfer complete: %d bytes sent", bytes_sent)
                                    return 'complete'

                                # Send next chunk
                                chunk_end = min(bytes_sent + requested_len, total_bytes)
                                file_chunk = data[bytes_sent:chunk_end]
                                bytes_sent = chunk_end

                                self._send_ack_and_data(seq, file_chunk)
                                logger.debug("Sent %d bytes (total: %d/%d)",
                                            len(file_chunk), bytes_sent, total_bytes)

                                if progress:
                                    progress(bytes_sent, total_bytes)

                            elif cmd.command == CMD_CLOSE:
                                logger.warning("Psion closed early")
                                self._send_ack_and_data(seq)
                                return 'complete'

            raise TimeoutError(f"Serve operation timed out after {TIMEOUT}s")

        finally:
            self.link.port.timeout = old_timeout

    # -------------------------------------------------------------------------
    # Receive File (Psion → PC, Psion in SEND mode)
    # -------------------------------------------------------------------------

    def receive_file(
        self,
        progress: Optional[Callable[[int], None]] = None,
    ) -> Tuple[str, bytes]:
        """
        Receive a file from the Psion device.

        The Psion must be in SEND mode. This method handles the complete
        two-connection protocol in a single continuous loop:

        1. **Connection 1**: File existence check (mode 0x04)
           - Psion checks if file exists on PC
           - PC always responds with empty DATA (simulating "file exists")
           - Psion closes and disconnects
           - User confirms "Overwrite?" on Psion

        2. **Connection 2**: Actual data transfer (mode 0x01)
           - Psion opens file for create/replace
           - Psion sends PutData packets with file content
           - PC acknowledges each with ACK + empty DATA

        Args:
            progress: Optional callback called with bytes received.

        Returns:
            Tuple of (filename, data) where filename is what Psion sent.

        Raises:
            TransferError: If the transfer fails.
            ConnectionError: If connection issues occur.
            ProtocolError: If protocol violation occurs.

        Example:
            # Start COMMS > SEND on Psion, select file
            filename, data = transfer.receive_file()
            print(f"Received: {filename} ({len(data)} bytes)")
        """
        logger.info("Waiting to receive file from Psion...")

        # Use single continuous loop like test_receive_v3.py for speed
        filename, data = self._receive_file_continuous(
            expected_connections=2,
            progress=progress,
        )

        if filename is None:
            raise TransferError("No filename received from Psion")

        logger.info("Transfer complete: received '%s' (%d bytes)",
                   filename, len(data))
        return filename, data

    def _receive_file_continuous(
        self,
        expected_connections: int = 2,
        progress: Optional[Callable[[int], None]] = None,
        timeout: float = 120.0,
    ) -> Tuple[Optional[str], bytes]:
        """
        Handle file receive in a single continuous loop.

        This mirrors test_receive_v3.py's approach: one loop that handles
        handshakes, data transfer, and re-connections without breaking out.

        Args:
            expected_connections: Number of connections to handle (1 or 2).
            progress: Optional callback for progress updates.
            timeout: Overall timeout for entire operation.

        Returns:
            Tuple of (filename, data).
        """
        import time

        # Build Link Request packet for handshake polling
        link_request = Packet(PacketType.LINK_REQUEST, sequence=0, data=b"")

        # State
        state = 'HANDSHAKE'
        connection_count = 0
        filename = None
        data = bytearray()
        buffer = bytearray()

        # Timing
        start_time = time.time()
        last_link_req_time = 0.0
        LINK_REQ_INTERVAL = 0.2  # Send Link Request every 200ms
        READ_TIMEOUT = 0.05  # 50ms read timeout

        # Save original timeout
        old_timeout = self.link.port.timeout
        self.link.port.timeout = READ_TIMEOUT

        try:
            while time.time() - start_time < timeout:
                now = time.time()

                # Send Link Requests during handshake
                if state == 'HANDSHAKE' and (now - last_link_req_time) >= LINK_REQ_INTERVAL:
                    self.link._send_packet(link_request)
                    last_link_req_time = now

                # Read any available data (non-blocking style)
                chunk = self.link.port.read(512)
                if chunk:
                    buffer.extend(chunk)

                # Try to parse packets from buffer
                while True:
                    packet, remaining = self._parse_packet_from_buffer(bytes(buffer))
                    buffer = bytearray(remaining)
                    if packet is None:
                        break

                    # Handle packet based on state
                    if state == 'HANDSHAKE' and packet.type == PacketType.LINK_REQUEST:
                        connection_count += 1
                        logger.info("Connection #%d established", connection_count)
                        # Send ACK seq=0 to complete handshake
                        ack = Packet(PacketType.ACK, sequence=0, data=b"")
                        self.link._send_packet(ack)
                        state = 'CONNECTED'
                        self.link._connected = True

                    elif packet.type == PacketType.DISCONNECT:
                        logger.debug("RX: DISCONNECT")
                        self.link._connected = False
                        if connection_count >= expected_connections:
                            # All done
                            return filename, bytes(data)
                        # Go back to handshake for next connection
                        state = 'HANDSHAKE'
                        logger.info("Waiting for user confirmation on Psion...")

                    elif packet.type == PacketType.ACK:
                        logger.debug("RX: ACK seq=%d", packet.sequence)
                        # Just continue

                    elif packet.type == PacketType.DATA:
                        seq = packet.sequence
                        logger.debug("RX: DATA seq=%d len=%d", seq, len(packet.data))

                        # Always respond with ACK + empty DATA
                        self._send_ack_and_data(seq)

                        # Process content
                        if packet.data == FTRAN_OVERLAY:
                            logger.info("Received FTRAN overlay")
                        elif packet.data:
                            cmd = self._parse_ftran_command(packet.data)

                            if cmd.command == CMD_OPEN:
                                filename = cmd.filename
                                logger.info(
                                    "Open: '%s' (mode=0x%02X, type=0x%02X)",
                                    filename, cmd.mode, cmd.file_type
                                )
                                if cmd.mode == 0x04:
                                    logger.info("Existence check complete for '%s'", filename)

                            elif cmd.command == CMD_PUT_DATA:
                                if cmd.data:
                                    data.extend(cmd.data)
                                    if progress:
                                        progress(len(data))

                            elif cmd.command == CMD_CLOSE:
                                logger.debug("Close command received")

            raise TimeoutError(f"Receive operation timed out after {timeout}s")

        finally:
            self.link.port.timeout = old_timeout

    def _parse_packet_from_buffer(
        self,
        buffer: bytes
    ) -> Tuple[Optional[Packet], bytes]:
        """
        Try to parse a packet from the buffer.

        Args:
            buffer: Raw bytes buffer.

        Returns:
            Tuple of (packet, remaining_buffer). Packet is None if incomplete.
        """
        from psion_sdk.comms.link import PACKET_HEADER, MIN_PACKET_SIZE, _find_footer

        if len(buffer) < MIN_PACKET_SIZE:
            return None, buffer

        # Find header
        try:
            header_pos = buffer.index(PACKET_HEADER)
        except ValueError:
            return None, buffer

        # Discard bytes before header
        if header_pos > 0:
            buffer = buffer[header_pos:]

        # Find footer
        footer_pos = _find_footer(buffer)
        if footer_pos < 0 or footer_pos + 4 > len(buffer):
            return None, buffer

        # Complete packet - extract and parse
        packet_bytes = buffer[:footer_pos + 4]
        remaining = buffer[footer_pos + 4:]

        try:
            packet = Packet.from_bytes(packet_bytes)
            return packet, remaining
        except Exception as e:
            logger.warning("Failed to parse packet: %s", e)
            return None, remaining

    def _handle_receive_connection(
        self,
        expect_data: bool = False
    ) -> Tuple[Optional[str], bytes]:
        """
        Handle a single connection in the receive protocol.

        This uses a simple packet loop that processes all incoming packets
        without blocking on ACK responses. The pattern is:
        - On any DATA packet: send ACK + empty DATA, then continue
        - On ACK: just log and continue
        - On DISCONNECT: end the connection

        Args:
            expect_data: If True, expect PutData packets with file content.

        Returns:
            Tuple of (filename, data). Data is empty for existence check.
        """
        filename = None
        data = bytearray()
        got_ftran = False
        got_close = False

        while not got_close:
            try:
                packet = self.link._receive_packet(timeout=15.0)
            except TimeoutError:
                logger.warning("Timeout waiting for packet")
                break

            if packet.type == PacketType.DISCONNECT:
                logger.debug("RX: DISCONNECT")
                break

            if packet.type == PacketType.ACK:
                logger.debug("RX: ACK seq=%d", packet.sequence)
                continue

            if packet.type != PacketType.DATA:
                logger.warning("Unexpected packet type: %s", packet.type.name)
                continue

            # It's a DATA packet - always respond with ACK + empty DATA
            seq = packet.sequence
            logger.debug("RX: DATA seq=%d len=%d", seq, len(packet.data))

            self._send_ack_and_data(seq)

            # Now process the content
            if packet.data == FTRAN_OVERLAY:
                logger.info("Received FTRAN overlay")
                got_ftran = True
                continue

            if not packet.data:
                continue

            # Parse FTRAN command
            cmd = self._parse_ftran_command(packet.data)

            if cmd.command == CMD_OPEN:
                filename = cmd.filename
                logger.info(
                    "Open: '%s' (mode=0x%02X, type=0x%02X)",
                    filename, cmd.mode, cmd.file_type
                )

            elif cmd.command == CMD_PUT_DATA:
                if cmd.data:
                    data.extend(cmd.data)
                    logger.debug("PutData: received %d bytes (total: %d)",
                                len(cmd.data), len(data))

            elif cmd.command == CMD_CLOSE:
                logger.debug("Close command received")
                got_close = True

            else:
                logger.warning("Unknown command: 0x%02X", cmd.command)

        return filename, bytes(data)

    def receive_file_simple(
        self,
        progress: Optional[Callable[[int], None]] = None,
    ) -> Tuple[str, bytes]:
        """
        Simplified receive that handles a single connection only.

        Use this if you know the Psion will skip the existence check
        (e.g., new file that doesn't exist on PC).

        Args:
            progress: Optional callback called with bytes received.

        Returns:
            Tuple of (filename, data).
        """
        logger.info("Waiting to receive file from Psion (simple mode)...")

        # Use single continuous loop with 1 connection expected
        filename, data = self._receive_file_continuous(
            expected_connections=1,
            progress=progress,
        )

        if filename is None:
            raise TransferError("No filename received from Psion")

        logger.info("Transfer complete: received '%s' (%d bytes)",
                   filename, len(data))
        return filename, data

    # -------------------------------------------------------------------------
    # Directory Operations
    # -------------------------------------------------------------------------

    def list_directory(self, device: str = "B:") -> list[str]:
        """
        List files on a Psion device/pack.

        **Note**: This operation requires the Psion to be in TRANSMIT mode
        and uses a different protocol flow than file transfer.

        Args:
            device: Device to list. Valid values:
                    - 'A:' - Internal memory
                    - 'B:' - Pack slot B
                    - 'C:' - Pack slot C (if equipped)
                    - 'M:' - Main device (RAM)

        Returns:
            List of filenames on the device.

        Raises:
            TransferError: If device cannot be accessed.
            CommsError: If communication fails.
        """
        # Ensure device string ends with colon
        if not device.endswith(':'):
            device += ':'

        logger.info("Listing directory: %s", device)

        # For directory listing, we need to send the request
        # This uses a different flow where PC initiates
        self.link.send_data(FTRAN_OVERLAY_NULL)

        # Open directory
        open_cmd = bytearray([CMD_OPEN, OpenMode.READ_ONLY, FileType.DIRECTORY])
        open_cmd.extend(device.encode('ascii'))
        open_cmd.append(0x00)

        self.link.send_data(bytes(open_cmd))

        # Wait for response
        response = self.link.receive_data()
        status = response[0] if response else 0xFF

        if status != ResponseStatus.OK:
            self._handle_error_status(status, f"Cannot access device: {device}")

        # Read directory entries
        files = []
        while True:
            # Request data
            cmd = bytes([CMD_GET_DATA, MAX_BLOCK_SIZE])
            self.link.send_data(cmd)

            response = self.link.receive_data()

            if not response or len(response) <= 1:
                break  # End of listing

            status = response[0]
            if status == ResponseStatus.END_OF_FILE:
                break

            if status != ResponseStatus.OK:
                break

            # Parse directory entry
            entry = response[1:].decode('ascii', errors='ignore').strip()
            if entry:
                for part in entry.replace('\x00', '\n').split('\n'):
                    name = part.strip()
                    if name and name not in files:
                        files.append(name)

        # Close
        self.link.send_data(bytes([CMD_CLOSE]))
        try:
            self.link.receive_data()
        except TimeoutError:
            pass  # Expected when connection closes
        except Exception as e:
            logger.debug("Unexpected error during directory close: %s", e)

        logger.debug("Found %d files", len(files))
        return files

    # -------------------------------------------------------------------------
    # Legacy API (for backward compatibility)
    # -------------------------------------------------------------------------

    def send_file(
        self,
        data: bytes,
        filename: str,
        file_type: FileType = FileType.BINARY,
        mode: OpenMode = OpenMode.CREATE_REPLACE,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Send a file to the Psion device.

        **DEPRECATED**: This method uses the old (incorrect) protocol flow.
        Use `serve_file()` instead, which correctly waits for Psion to
        request the file.

        For backward compatibility, this method now delegates to serve_file().

        Args:
            data: File contents to send.
            filename: Destination filename on Psion.
            file_type: Type of file (BINARY/ODB or ASCII/OPL).
            mode: Open mode (ignored - Psion controls this).
            progress: Optional callback for progress updates.
        """
        logger.warning(
            "send_file() is deprecated. Use serve_file() for correct protocol."
        )
        # Extract just the filename part (remove device prefix if present)
        if ':' in filename:
            filename = filename.split(':')[1]

        self.serve_file(filename, data, file_type, progress)

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def _handle_error_status(self, status: int, context: str) -> None:
        """
        Convert a status code to an appropriate exception.

        Args:
            status: Response status code.
            context: Description of the operation that failed.

        Raises:
            TransferError: Always raised with appropriate message.
        """
        error_messages = {
            ResponseStatus.FILE_NOT_FOUND: "File not found",
            ResponseStatus.FILE_EXISTS: "File already exists",
            ResponseStatus.DISK_FULL: "Disk full",
            ResponseStatus.IO_ERROR: "I/O error",
        }

        message = error_messages.get(status, f"Unknown error (status={status})")
        raise TransferError(f"{context}: {message}")


# =============================================================================
# Convenience Functions
# =============================================================================

def send_opk(
    link: LinkProtocol,
    opk_data: bytes,
    device: str = "B:",
    filename: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> None:
    """
    Send an OPK pack file to the Psion device.

    **Note**: The Psion must be in RECEIVE mode and the user must enter
    the filename on the Psion. This function waits for the Psion's request.

    Args:
        link: Connected LinkProtocol instance.
        opk_data: OPK file contents.
        device: Target device (logged only, Psion controls destination).
        filename: Filename to serve (default 'PROGRAM').
        progress: Optional progress callback.

    Example:
        with open('program.opk', 'rb') as f:
            opk_data = f.read()

        # User types 'PROGRAM.OPL' on Psion in RECEIVE mode
        send_opk(link, opk_data, filename='PROGRAM')
    """
    transfer = FileTransfer(link)

    if filename is None:
        filename = "PROGRAM"

    # Remove device prefix if present
    if ':' in filename:
        filename = filename.split(':')[1]

    transfer.serve_file(
        filename,
        opk_data,
        file_type=FileType.OPL,
        progress=progress,
    )


def receive_opk(
    link: LinkProtocol,
    filename: str = None,
    device: str = "B:",
    progress: Optional[Callable[[int], None]] = None,
) -> bytes:
    """
    Receive an OPK pack file from the Psion device.

    The Psion must be in SEND mode with the file selected.

    Args:
        link: Connected LinkProtocol instance.
        filename: Expected filename (logged only, Psion sends actual name).
        device: Source device (logged only).
        progress: Optional progress callback.

    Returns:
        File contents.

    Example:
        # User selects file on Psion in SEND mode
        data = receive_opk(link)
        with open('received.opk', 'wb') as f:
            f.write(data)
    """
    transfer = FileTransfer(link)
    received_filename, data = transfer.receive_file(progress=progress)

    logger.info("Received file: '%s' (%d bytes)", received_filename, len(data))
    return data
