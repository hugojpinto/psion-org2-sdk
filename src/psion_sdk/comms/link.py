"""
Psion Link Protocol Implementation
===================================

This module implements the low-level Psion Link Protocol used for serial
communication between a PC and the Psion Organiser II. It handles:

- Packet framing (header, footer, CRC)
- Escape sequence encoding/decoding
- Connection establishment (handshaking)
- Data packet transmission with acknowledgments
- Sequence number management
- Error detection and retransmission

Protocol Overview
-----------------
The Psion Link Protocol uses framed packets with the following structure:

    ┌────────┬────────┬────────┬────────────┬────────┬────────┐
    │ Header │  Chan  │  Type  │    Data    │ Footer │  CRC   │
    │ 16 10  │   01   │   XX   │  0-256 B   │ 10 03  │ 2 bytes│
    │  02    │        │        │            │        │        │
    └────────┴────────┴────────┴────────────┴────────┴────────┘

Key protocol characteristics:
- Byte $10 in data is escaped as $10 $10 (escape bytes not in CRC)
- Sequence numbers cycle 1-7, 0, 1-7, 0, ... (0 only for handshake ACK)
- Receiver ACKs with last valid sequence on error (triggers retransmit)
- Maximum data size is 256 bytes (before escaping)

Connection Handshake
--------------------
1. Psion sends Link Request (type 2, seq 0)
2. PC responds with Link Request (type 2, seq 0)
3. Psion sends ACK (type 0, seq 0)
4. Connection established, sequences reset to 1

References
----------
- https://www.jaapsch.net/psion/protocol.htm (protocol details)
- specs/03-comms.md (full specification in this project)
"""

import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Final, Optional

from psion_sdk.comms.crc import crc_ccitt_fast, crc_from_bytes, crc_to_bytes
from psion_sdk.errors import (
    CommsError,
    ConnectionError,
    ProtocolError,
    TimeoutError,
    TransferError,
)

if TYPE_CHECKING:
    import serial

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Constants
# =============================================================================

# Fixed packet header bytes: SYN DLE STX
PACKET_HEADER: Final[bytes] = bytes([0x16, 0x10, 0x02])

# Fixed packet footer bytes: DLE ETX
PACKET_FOOTER: Final[bytes] = bytes([0x10, 0x03])

# Channel number (always 1 for standard comms)
CHANNEL_NUMBER: Final[int] = 0x01

# Escape byte that needs doubling in payload
ESCAPE_BYTE: Final[int] = 0x10

# Maximum data payload size (before escaping)
# Note: Spec says 256, but Psion can send larger packets (up to ~260 observed)
MAX_DATA_SIZE: Final[int] = 512

# Minimum packet size: header(3) + channel(1) + type(1) + footer(2) + crc(2)
MIN_PACKET_SIZE: Final[int] = 9


# =============================================================================
# Packet Types
# =============================================================================

class PacketType(IntEnum):
    """
    Psion Link Protocol packet types.

    The packet type is encoded in the upper 5 bits of the type byte,
    with the lower 3 bits containing the sequence number.

    Type byte format: TTTTT SSS
        - T bits: Packet type (0-3, shifted left by 3)
        - S bits: Sequence number (0-7)
    """

    # Acknowledgment: confirms receipt of a data packet
    # Sequence number matches the packet being acknowledged
    ACK = 0x00

    # Disconnect: terminates the connection
    # May contain an error code in the data field
    DISCONNECT = 0x08

    # Link Request: used during connection handshake
    # Both sides exchange this to establish connection
    LINK_REQUEST = 0x10

    # Data: carries payload data
    # Sequence numbers cycle 1-7, 0, 1-7, 0, ...
    DATA = 0x18


class RemoteError(IntEnum):
    """
    Error codes that may be received from the Psion device.

    These codes are sent in the data field of a DISCONNECT packet
    to indicate why the remote end terminated the connection.
    """

    BAD_PARAMETER = 190      # Invalid parameter in command
    FILE_NOT_FOUND = 189     # Requested file doesn't exist
    SERVER_ERROR = 188       # General server-side error
    FILE_EXISTS = 187        # File already exists (for create operations)
    DISK_FULL = 186          # No space on device
    RECORD_TOO_LONG = 185    # Record exceeds maximum length

    @classmethod
    def describe(cls, code: int) -> str:
        """Get human-readable description of error code."""
        descriptions = {
            190: "Bad parameter",
            189: "Remote file not found",
            188: "Server error",
            187: "Remote file exists",
            186: "Disk full",
            185: "Record too long",
        }
        return descriptions.get(code, f"Unknown error ({code})")


# =============================================================================
# Packet Class
# =============================================================================

@dataclass
class Packet:
    """
    Represents a single Psion Link Protocol packet.

    This class handles encoding packets for transmission and decoding
    received packets. It manages the escape sequence handling and CRC
    calculation transparently.

    Attributes:
        type: Packet type (ACK, DISCONNECT, LINK_REQUEST, or DATA)
        sequence: Sequence number (0-7)
        data: Payload data (0-256 bytes, before escaping)

    Example:
        # Create a data packet
        packet = Packet(PacketType.DATA, sequence=1, data=b'Hello')
        wire_bytes = packet.to_bytes()

        # Parse a received packet
        received = Packet.from_bytes(wire_bytes)
        print(received.data)  # b'Hello'
    """

    type: PacketType
    sequence: int
    data: bytes

    def __post_init__(self) -> None:
        """Validate packet fields after initialization."""
        # Validate sequence number range
        if not 0 <= self.sequence <= 7:
            raise ValueError(f"Sequence must be 0-7, got {self.sequence}")

        # Validate data size
        if len(self.data) > MAX_DATA_SIZE:
            raise ValueError(
                f"Data too large: {len(self.data)} bytes, max {MAX_DATA_SIZE}"
            )

        # Ensure data is bytes
        if not isinstance(self.data, bytes):
            raise TypeError(f"Data must be bytes, got {type(self.data).__name__}")

    @property
    def type_byte(self) -> int:
        """
        Get the combined type + sequence byte.

        The type byte encodes both the packet type (upper 5 bits)
        and the sequence number (lower 3 bits).
        """
        return (self.type & 0xF8) | (self.sequence & 0x07)

    def to_bytes(self) -> bytes:
        """
        Serialize packet for transmission over serial.

        This method:
        1. Builds the raw payload (channel + type + data)
        2. Calculates CRC over the unescaped payload
        3. Escapes any $10 bytes in the payload
        4. Assembles the final packet with header, footer, and CRC

        Returns:
            Complete packet bytes ready for transmission.

        Note:
            The CRC is calculated over the unescaped payload, but
            escape sequences ARE applied before adding header/footer.
        """
        # Build raw payload: channel byte + type byte + data
        raw_payload = bytearray([CHANNEL_NUMBER, self.type_byte])
        raw_payload.extend(self.data)

        # Calculate CRC over unescaped payload
        crc = crc_ccitt_fast(bytes(raw_payload))

        # Escape $10 bytes in payload (double them)
        escaped_payload = _escape_data(bytes(raw_payload))

        # Build complete packet
        packet = bytearray(PACKET_HEADER)
        packet.extend(escaped_payload)
        packet.extend(PACKET_FOOTER)
        packet.extend(crc_to_bytes(crc))

        logger.debug(
            "Encoded packet: type=%s seq=%d data_len=%d wire_len=%d crc=%04X",
            self.type.name, self.sequence, len(self.data), len(packet), crc
        )

        return bytes(packet)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Packet":
        """
        Parse a packet from received bytes.

        This method:
        1. Validates header and footer markers
        2. Extracts and unescapes the payload
        3. Verifies the CRC checksum
        4. Parses the type and sequence fields

        Args:
            data: Complete packet bytes including header, footer, and CRC.

        Returns:
            Parsed Packet object.

        Raises:
            ProtocolError: If packet structure is invalid.
            TransferError: If CRC verification fails.
        """
        # Minimum size check
        if len(data) < MIN_PACKET_SIZE:
            raise ProtocolError(
                f"Packet too short: {len(data)} bytes, minimum {MIN_PACKET_SIZE}"
            )

        # Validate header
        if data[:3] != PACKET_HEADER:
            raise ProtocolError(
                f"Invalid packet header: got {data[:3].hex()}, expected {PACKET_HEADER.hex()}"
            )

        # Find footer position (scan for $10 $03 that isn't escaped)
        footer_pos = _find_footer(data)
        if footer_pos < 0:
            raise ProtocolError("Packet footer not found")

        # Extract CRC bytes (2 bytes after footer)
        if footer_pos + 4 > len(data):
            raise ProtocolError("Packet missing CRC bytes")

        received_crc = crc_from_bytes(data[footer_pos + 2:footer_pos + 4])

        # Extract and unescape payload
        escaped_payload = data[3:footer_pos]
        raw_payload = _unescape_data(escaped_payload)

        # Verify CRC over unescaped payload
        calculated_crc = crc_ccitt_fast(raw_payload)
        if received_crc != calculated_crc:
            raise TransferError(
                f"CRC mismatch: received {received_crc:04X}, calculated {calculated_crc:04X}"
            )

        # Parse payload fields
        if len(raw_payload) < 2:
            raise ProtocolError(
                f"Payload too short: {len(raw_payload)} bytes, need at least 2"
            )

        channel = raw_payload[0]
        type_byte = raw_payload[1]
        payload_data = bytes(raw_payload[2:]) if len(raw_payload) > 2 else b""

        # Validate channel
        if channel != CHANNEL_NUMBER:
            logger.warning("Unexpected channel number: %d", channel)

        # Extract type and sequence from type byte
        packet_type = PacketType(type_byte & 0xF8)
        sequence = type_byte & 0x07

        logger.debug(
            "Decoded packet: type=%s seq=%d data_len=%d",
            packet_type.name, sequence, len(payload_data)
        )

        return cls(type=packet_type, sequence=sequence, data=payload_data)

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        data_repr = (
            self.data[:20].hex() + "..."
            if len(self.data) > 20
            else self.data.hex()
        )
        return (
            f"Packet(type={self.type.name}, seq={self.sequence}, "
            f"data[{len(self.data)}]={data_repr})"
        )


# =============================================================================
# Escape Sequence Handling
# =============================================================================

def _escape_data(data: bytes) -> bytes:
    """
    Escape $10 bytes in data for transmission.

    The Psion protocol uses $10 $03 as the packet footer marker. To prevent
    false footer detection, any $10 byte in the payload is escaped by
    doubling it to $10 $10.

    Args:
        data: Raw data bytes to escape.

    Returns:
        Data with all $10 bytes doubled.

    Note:
        Escape bytes are NOT included in CRC calculation - the CRC is
        computed over the original unescaped data.
    """
    result = bytearray()
    for byte in data:
        result.append(byte)
        if byte == ESCAPE_BYTE:
            result.append(ESCAPE_BYTE)  # Double the $10 byte
    return bytes(result)


def _unescape_data(data: bytes) -> bytes:
    """
    Remove escape sequences from received data.

    This reverses the escaping process: $10 $10 becomes single $10.

    Args:
        data: Escaped data bytes.

    Returns:
        Original unescaped data.

    Raises:
        ProtocolError: If an escape byte is not followed by another $10.
    """
    result = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == ESCAPE_BYTE:
            # Expect another $10 following
            if i + 1 >= len(data):
                raise ProtocolError("Escape byte at end of data")
            next_byte = data[i + 1]
            if next_byte == ESCAPE_BYTE:
                result.append(ESCAPE_BYTE)
                i += 2
            else:
                # This shouldn't happen in properly escaped data
                raise ProtocolError(
                    f"Invalid escape sequence: 10 {next_byte:02X}"
                )
        else:
            result.append(byte)
            i += 1
    return bytes(result)


def _find_footer(data: bytes) -> int:
    """
    Find the footer position in a packet, handling escapes.

    The footer is $10 $03, but we must distinguish it from escaped $10
    in the data. We scan forward looking for $10 that is followed by $03
    rather than by another $10.

    Args:
        data: Complete packet bytes.

    Returns:
        Index of footer ($10 $03) or -1 if not found.
    """
    # Start after header (3 bytes)
    i = 3
    while i < len(data) - 1:
        if data[i] == ESCAPE_BYTE:
            if data[i + 1] == 0x03:
                # Found footer
                return i
            elif data[i + 1] == ESCAPE_BYTE:
                # Escaped $10, skip both
                i += 2
            else:
                # Unexpected byte after $10
                i += 1
        else:
            i += 1
    return -1


# =============================================================================
# Link Protocol State Machine
# =============================================================================

class LinkProtocol:
    """
    Psion Link Protocol state machine.

    This class manages the full communication session including:
    - Connection establishment (handshake)
    - Packet transmission with ACK/retransmit
    - Packet reception with sequence validation
    - Clean disconnection

    The protocol maintains separate sequence counters for transmit and
    receive directions, as data can flow in both directions independently.

    Sequence Number Behavior
    ------------------------
    After the initial handshake (which uses seq 0), data packets use
    sequence numbers 1-7, then 0, then 1-7, etc. The sequence 0 is
    special during handshake but is reused during data transfer.

    Error Handling
    --------------
    - CRC errors: Receiver ACKs the previous sequence, triggering retransmit
    - Timeout: Sender retries up to MAX_RETRIES times
    - Remote error: Disconnect packet contains error code

    Usage:
        port = open_serial_port('/dev/ttyUSB0')
        link = LinkProtocol(port)

        # Connect (start COMMS on Psion first)
        link.connect(timeout=30.0)

        # Send data
        link.send_data(b'FTRAN\\x00')  # Overlay name

        # Receive response
        response = link.receive_data()

        # Clean disconnect
        link.disconnect()
    """

    # Default timeout for packet receive (seconds)
    DEFAULT_TIMEOUT: Final[float] = 5.0

    # Maximum retransmit attempts before giving up
    MAX_RETRIES: Final[int] = 3

    # Delay between retransmit attempts (seconds)
    RETRY_DELAY: Final[float] = 0.1

    def __init__(self, port: "serial.Serial"):
        """
        Initialize the link protocol handler.

        Args:
            port: Configured serial port object. The port should already
                  be opened with correct settings (9600 8N1 typically).
        """
        self.port = port
        self._tx_sequence = 0  # Transmit sequence number
        self._rx_sequence = 0  # Expected receive sequence number
        self._connected = False
        self._overlay: Optional[str] = None  # Active overlay name

    @property
    def connected(self) -> bool:
        """Return True if connection is established."""
        return self._connected

    @property
    def tx_sequence(self) -> int:
        """Current transmit sequence number."""
        return self._tx_sequence

    @property
    def rx_sequence(self) -> int:
        """Expected receive sequence number."""
        return self._rx_sequence

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    def connect(self, timeout: float = 30.0) -> bool:
        """
        Establish connection with Psion device.

        This implements the link handshake:
        1. PC sends Link Request packets (actively polling)
        2. Psion responds with Link Request
        3. PC sends ACK seq=0

        The user must start COMMS mode on the Psion before calling this.

        Args:
            timeout: Maximum time to wait for connection (seconds).
                     Includes time waiting for initial Link Request.

        Returns:
            True if connection established successfully.

        Raises:
            ConnectionError: If connection cannot be established.
            TimeoutError: If timeout expires.
        """
        if self._connected:
            logger.warning("Already connected, disconnecting first")
            self.disconnect()

        logger.info("Waiting for connection from Psion...")
        start_time = time.time()

        # Build Link Request packet for polling
        link_request = Packet(PacketType.LINK_REQUEST, sequence=0, data=b"")

        # Phase 1: Send Link Requests and wait for Psion's Link Request response
        # The PC must actively poll - Psion waits for PC to initiate
        while time.time() - start_time < timeout:
            # Send Link Request
            self._send_packet(link_request)
            logger.debug("Sent Link Request")

            # Wait briefly for response
            try:
                packet = self._receive_packet(timeout=0.3)
                if packet.type == PacketType.LINK_REQUEST:
                    logger.debug("Received Link Request from Psion")
                    break
            except TimeoutError:
                # Keep polling
                continue
        else:
            raise ConnectionError(
                f"No Link Request received from Psion within {timeout}s. "
                "Ensure COMMS mode is started on the device."
            )

        # Phase 2: Send ACK seq=0 to complete handshake
        logger.debug("Sending ACK seq=0")
        ack = Packet(PacketType.ACK, sequence=0, data=b"")
        self._send_packet(ack)

        # Connection established - reset sequence numbers
        self._tx_sequence = 1
        self._rx_sequence = 1
        self._connected = True

        logger.info("Connection established")
        return True

    def disconnect(self, error_code: Optional[int] = None) -> None:
        """
        Cleanly close the connection.

        Sends a DISCONNECT packet to notify the Psion. If an error code
        is provided, it is included in the packet.

        Args:
            error_code: Optional error code to send (from RemoteError enum).
        """
        if not self._connected:
            logger.debug("Not connected, nothing to disconnect")
            return

        # Build disconnect packet
        data = bytes([error_code]) if error_code is not None else b""
        packet = Packet(PacketType.DISCONNECT, sequence=0, data=data)

        try:
            self._send_packet(packet)
        except Exception as e:
            logger.warning("Error sending disconnect: %s", e)

        self._connected = False
        self._overlay = None
        logger.info("Disconnected")

    # -------------------------------------------------------------------------
    # Data Transmission
    # -------------------------------------------------------------------------

    def send_data(self, data: bytes) -> None:
        """
        Send a data packet with automatic retransmission.

        The packet is sent with the current transmit sequence number.
        This method waits for an ACK with matching sequence. If the
        ACK has a different sequence (or times out), the packet is
        retransmitted up to MAX_RETRIES times.

        Args:
            data: Data payload to send (max 256 bytes).

        Raises:
            ValueError: If data exceeds maximum size.
            TransferError: If transmission fails after retries.
            ConnectionError: If remote sends disconnect.
        """
        if not self._connected:
            raise CommsError("Not connected")

        if len(data) > MAX_DATA_SIZE:
            raise ValueError(
                f"Data too large: {len(data)} bytes, maximum {MAX_DATA_SIZE}"
            )

        packet = Packet(PacketType.DATA, sequence=self._tx_sequence, data=data)

        for attempt in range(self.MAX_RETRIES):
            logger.debug(
                "Sending data packet: seq=%d len=%d attempt=%d",
                self._tx_sequence, len(data), attempt + 1
            )
            self._send_packet(packet)

            try:
                ack = self._receive_packet(timeout=self.DEFAULT_TIMEOUT)

                if ack.type == PacketType.ACK:
                    if ack.sequence == self._tx_sequence:
                        # Success - advance sequence
                        self._advance_tx_sequence()
                        logger.debug("Data acknowledged, seq now %d", self._tx_sequence)
                        return
                    else:
                        # Wrong sequence - retransmit
                        logger.debug(
                            "ACK sequence mismatch: got %d, expected %d",
                            ack.sequence, self._tx_sequence
                        )
                        continue

                elif ack.type == PacketType.DISCONNECT:
                    self._handle_disconnect(ack)

                else:
                    logger.warning("Unexpected packet type: %s", ack.type.name)

            except TimeoutError:
                logger.debug("Timeout waiting for ACK, retrying")
                time.sleep(self.RETRY_DELAY)
                continue

        # All retries exhausted
        raise TransferError(
            f"Failed to send data after {self.MAX_RETRIES} attempts"
        )

    def receive_data(self, timeout: Optional[float] = None) -> bytes:
        """
        Receive and acknowledge a data packet.

        Waits for a DATA packet with the expected sequence number. If the
        sequence matches, sends an ACK and returns the data. If the sequence
        is wrong (duplicate), ACKs with the previous sequence to trigger
        retransmit from the remote.

        Args:
            timeout: Receive timeout in seconds (default: DEFAULT_TIMEOUT).

        Returns:
            Received data payload.

        Raises:
            TransferError: If received packet has CRC error.
            ConnectionError: If remote sends disconnect.
            TimeoutError: If no packet received within timeout.
        """
        if not self._connected:
            raise CommsError("Not connected")

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        packet = self._receive_packet(timeout=timeout)

        if packet.type == PacketType.DATA:
            if packet.sequence == self._rx_sequence:
                # Valid packet - send ACK and advance sequence
                ack = Packet(PacketType.ACK, sequence=packet.sequence, data=b"")
                self._send_packet(ack)
                self._advance_rx_sequence()
                logger.debug(
                    "Received data: seq=%d len=%d",
                    packet.sequence, len(packet.data)
                )
                return packet.data
            else:
                # Wrong sequence - ACK previous to trigger retransmit
                prev_seq = self._previous_sequence(self._rx_sequence)
                logger.debug(
                    "Sequence mismatch: got %d, expected %d, ACKing %d",
                    packet.sequence, self._rx_sequence, prev_seq
                )
                ack = Packet(PacketType.ACK, sequence=prev_seq, data=b"")
                self._send_packet(ack)
                # Recursively wait for correct packet
                return self.receive_data(timeout=timeout)

        elif packet.type == PacketType.DISCONNECT:
            self._handle_disconnect(packet)
            # _handle_disconnect raises, but satisfy type checker
            raise ConnectionError("Disconnected")

        else:
            raise ProtocolError(f"Unexpected packet type: {packet.type.name}")

    # -------------------------------------------------------------------------
    # Low-Level Packet I/O
    # -------------------------------------------------------------------------

    def _send_packet(self, packet: Packet) -> None:
        """
        Send a packet over the serial port.

        Args:
            packet: Packet to send.
        """
        wire_bytes = packet.to_bytes()
        self.port.write(wire_bytes)
        self.port.flush()
        logger.debug("Sent %d bytes: %s", len(wire_bytes), wire_bytes.hex())

    def _receive_packet(self, timeout: float) -> Packet:
        """
        Receive a packet from the serial port.

        This method reads bytes until it finds a complete valid packet
        or the timeout expires. It handles synchronization by searching
        for the packet header.

        Uses short read timeouts (50ms) with polling to avoid blocking,
        similar to how the working test scripts operate.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            Parsed Packet object.

        Raises:
            TimeoutError: If no complete packet received within timeout.
            ProtocolError: If packet structure is invalid.
            TransferError: If CRC verification fails.
        """
        # Use short read timeout for non-blocking style reads
        # This matches the approach in test_receive_v3.py
        READ_TIMEOUT = 0.05

        old_timeout = self.port.timeout
        self.port.timeout = READ_TIMEOUT
        start_time = time.time()

        try:
            buffer = bytearray()

            while time.time() - start_time < timeout:
                # Read available bytes (short timeout, returns quickly)
                chunk = self.port.read(512)
                if chunk:
                    buffer.extend(chunk)
                    logger.debug("Buffer now %d bytes", len(buffer))

                # Try to find and parse a complete packet
                if len(buffer) >= MIN_PACKET_SIZE:
                    # Look for header
                    header_pos = buffer.find(PACKET_HEADER)
                    if header_pos > 0:
                        # Discard bytes before header
                        logger.debug(
                            "Discarding %d bytes before header", header_pos
                        )
                        buffer = buffer[header_pos:]

                    if buffer[:3] == PACKET_HEADER:
                        # Find footer
                        footer_pos = _find_footer(bytes(buffer))
                        if footer_pos >= 0 and footer_pos + 4 <= len(buffer):
                            # Complete packet - extract and parse
                            packet_bytes = bytes(buffer[:footer_pos + 4])
                            buffer = buffer[footer_pos + 4:]
                            logger.debug(
                                "Received %d bytes: %s",
                                len(packet_bytes), packet_bytes.hex()
                            )
                            return Packet.from_bytes(packet_bytes)

            raise TimeoutError(f"No packet received within {timeout}s")

        finally:
            self.port.timeout = old_timeout

    # -------------------------------------------------------------------------
    # Sequence Number Management
    # -------------------------------------------------------------------------

    def _advance_tx_sequence(self) -> None:
        """Advance transmit sequence to next value (1-7, 0, 1-7, 0, ...)."""
        self._tx_sequence = (self._tx_sequence % 7) + 1
        if self._tx_sequence == 8:
            self._tx_sequence = 0  # Wrap from 7 to 0

    def _advance_rx_sequence(self) -> None:
        """Advance receive sequence to next expected value."""
        self._rx_sequence = (self._rx_sequence % 7) + 1
        if self._rx_sequence == 8:
            self._rx_sequence = 0

    @staticmethod
    def _previous_sequence(seq: int) -> int:
        """Get the previous sequence number for NAK responses."""
        if seq == 0:
            return 7
        elif seq == 1:
            return 0
        else:
            return seq - 1

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def _handle_disconnect(self, packet: Packet) -> None:
        """
        Handle a DISCONNECT packet from the remote.

        Args:
            packet: DISCONNECT packet received.

        Raises:
            ConnectionError: Always raised with error details.
        """
        self._connected = False

        if packet.data:
            error_code = packet.data[0]
            error_msg = RemoteError.describe(error_code)
            raise ConnectionError(f"Remote disconnect: {error_msg} ({error_code})")
        else:
            raise ConnectionError("Remote disconnect (no error code)")
