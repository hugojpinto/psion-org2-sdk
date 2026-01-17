"""
BOOT Protocol for Psion Organiser II Pack Flashing
===================================================

This module implements the BOOT protocol used by the Psion Organiser II
CommsLink for transferring pack images directly to datapaks/rampacks.

Protocol Overview
-----------------
The BOOT protocol is a two-phase process:

1. **Phase 1**: Transfer a bootloader program to Psion RAM at address 0x34DD
2. **Phase 2**: The bootloader receives and writes pack image data to a datapak

This is different from FTRAN (file transfer) which transfers individual files.
BOOT writes raw pack images, essentially "flashing" an entire datapak.

User Workflow
-------------
1. Start PC utility (pslink boot)
2. PC begins polling with Link Request packets
3. On Psion: Navigate to COMMS > BOOT
4. Enter pack name (can be empty) and press EXE
5. Phase 1 executes: Bootloader transfers to Psion
6. Bootloader displays "Making a pack" message
7. PC prompts: "Insert empty datapak/rampack in drive C"
8. Phase 2 executes: Pack image data is written to the pack
9. Transfer completes

References
----------
- dev_docs/BOOT_PROTOCOL.md
- https://www.jaapsch.net/psion/protocol.htm (BOOT overlay section)
"""

import base64
import logging
import time
from pathlib import Path
from typing import Callable, Final, Optional, Tuple

from psion_sdk.comms.link import (
    LinkProtocol,
    Packet,
    PacketType,
    PACKET_HEADER,
    MIN_PACKET_SIZE,
    _find_footer,
)
from psion_sdk.errors import CommsError, ConnectionError, ProtocolError, TransferError

logger = logging.getLogger(__name__)

# =============================================================================
# BOOT Protocol Constants
# =============================================================================

# Overlay name for BOOT protocol
BOOT_OVERLAY: Final[bytes] = b"BOOT"

# Bootloader constants
BOOTLOADER_SIZE: Final[int] = 3367  # Bootloader code size in bytes
BOOTLOADER_LOAD_ADDRESS: Final[int] = 0x34DD  # Default load address (Psion may override)
BOOTLOADER_CHUNK_SIZE: Final[int] = 202  # Max bytes per packet (addr + code)

# Success/error codes in DISCONNECT packets
SUCCESS_CODE: Final[int] = 0x00
EOF_CODE: Final[int] = 0xEE

# OPK file header size to skip
OPK_HEADER_SIZE: Final[int] = 6

# Phase 2 pack data chunk size (matches captured traffic)
PACK_DATA_CHUNK_SIZE: Final[int] = 200

# Relocation table - offsets of 16-bit words (big-endian) to patch when loading
# at an address different from BOOTLOADER_LOAD_ADDRESS (0x34DD).
# These 211 offsets were extracted by comparing the bootloader sent at 0x34DD
# vs 0x2413 in captured CommsLink traffic.
RELOC_OFFSETS: Final[tuple] = (
    6, 273, 308, 316, 321, 326, 334, 339, 358, 401,
    424, 436, 443, 446, 449, 457, 460, 474, 482, 485,
    488, 491, 501, 507, 513, 518, 521, 526, 539, 544,
    547, 551, 558, 561, 564, 567, 570, 573, 578, 581,
    584, 587, 590, 607, 612, 617, 622, 627, 630, 640,
    643, 650, 653, 660, 663, 666, 669, 674, 677, 680,
    685, 692, 702, 707, 710, 728, 731, 741, 753, 756,
    888, 894, 897, 900, 903, 906, 909, 912, 915, 922,
    925, 930, 938, 943, 951, 954, 957, 960, 968, 971,
    986, 989, 992, 1009, 1014, 1050, 1094, 1103, 1106, 1118,
    1125, 1140, 1143, 1146, 1149, 1156, 1159, 1172, 1180, 1185,
    1188, 1193, 1196, 1199, 1202, 1209, 1241, 1250, 1254, 1262,
    1267, 1270, 1273, 1278, 1281, 1290, 1302, 1305, 1315, 1337,
    1354, 1360, 1378, 1409, 1486, 1493, 1519, 1604, 1607, 1655,
    1696, 1700, 1708, 1712, 1738, 1741, 1834, 1846, 1849, 1852,
    1910, 2006, 2080, 2085, 2114, 2117, 2136, 2150, 2166, 2173,
    2182, 2209, 2374, 2391, 2414, 2417, 2471, 2493, 2519, 2524,
    2527, 2533, 2536, 2543, 2546, 2553, 2572, 2575, 2595, 2598,
    2603, 2636, 2662, 2728, 2745, 2751, 2756, 2762, 2768, 2779,
    2786, 2807, 2861, 2873, 2883, 2944, 2965, 3012, 3054, 3057,
    3070, 3079, 3101, 3123, 3183, 3193, 3285, 3321, 3335, 3338,
    3352,
)

# Type alias for progress callback
ProgressCallback = Callable[[int, int], None]


# =============================================================================
# Embedded Bootloader
# =============================================================================

# Bootloader binary captured from original CommsLink software
# This is HD6303 machine code that runs on the Psion to receive and write pack data
# Size: 3367 bytes, starts with 0x0D 0x27 (which happens to equal the size in big-endian)
# All code packets use format: addr(2) + code(200) - no separate length field in packets
# Verified: extracted from two separate BOOT transfers in serial_capture.log
_BOOTLOADER_BASE64 = (
    "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"
    "dQQXOQ=="
)


def get_bootloader() -> bytes:
    """
    Get the embedded bootloader binary.

    Returns:
        Bootloader bytes (3367 bytes of HD6303 machine code).
    """
    return base64.b64decode(_BOOTLOADER_BASE64)


def relocate_bootloader(bootloader: bytes, load_address: int) -> bytes:
    """
    Relocate the bootloader for a different load address.

    The embedded bootloader is compiled for base address 0x34DD. When the Psion
    requests a different load address, all absolute address references must be
    patched by the relocation delta.

    Args:
        bootloader: Original bootloader bytes (compiled for 0x34DD).
        load_address: Actual load address requested by the Psion.

    Returns:
        Relocated bootloader bytes ready for transmission.
    """
    if load_address == BOOTLOADER_LOAD_ADDRESS:
        # No relocation needed
        return bootloader

    # Calculate relocation delta (addresses need to be decreased when loading lower)
    delta = BOOTLOADER_LOAD_ADDRESS - load_address
    logger.info(
        "Relocating bootloader: 0x%04X -> 0x%04X (delta=%d)",
        BOOTLOADER_LOAD_ADDRESS, load_address, delta
    )

    # Create mutable copy
    relocated = bytearray(bootloader)

    # Patch each 16-bit address at the relocation offsets
    for offset in RELOC_OFFSETS:
        if offset + 1 < len(relocated):
            # Read big-endian 16-bit word
            old_word = (relocated[offset] << 8) | relocated[offset + 1]
            # Apply relocation
            new_word = (old_word - delta) & 0xFFFF
            # Write back big-endian
            relocated[offset] = (new_word >> 8) & 0xFF
            relocated[offset + 1] = new_word & 0xFF

    logger.debug("Relocated %d addresses", len(RELOC_OFFSETS))
    return bytes(relocated)


# =============================================================================
# BOOT Protocol Implementation
# =============================================================================

class BootTransfer:
    """
    BOOT protocol handler for flashing packs on Psion Organiser II.

    This class implements the two-phase BOOT protocol:
    1. Phase 1: Upload bootloader to Psion RAM
    2. Phase 2: Send pack image data to bootloader

    Example:
        port = open_serial_port('/dev/ttyUSB0')
        link = LinkProtocol(port)
        boot = BootTransfer(link)

        # Flash an OPK file
        with open('program.opk', 'rb') as f:
            opk_data = f.read()
        boot.flash_pack(opk_data, progress=progress_callback)
    """

    # Timeout for operations
    HANDSHAKE_TIMEOUT: Final[float] = 120.0
    DATA_TIMEOUT: Final[float] = 30.0

    # Delay between packets
    PACKET_DELAY: Final[float] = 0.02

    # Link Request polling interval
    LINK_REQ_INTERVAL: Final[float] = 0.2

    def __init__(self, link: LinkProtocol):
        """
        Initialize the BOOT transfer handler.

        Args:
            link: LinkProtocol instance (should not be connected yet).
        """
        self.link = link
        self._bootloader = get_bootloader()

    def flash_pack(
        self,
        opk_data: bytes,
        progress: Optional[ProgressCallback] = None,
        user_prompt: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Flash an OPK pack image to the Psion.

        This method performs the complete two-phase BOOT transfer:
        1. Wait for Psion to enter BOOT mode
        2. Upload bootloader (Phase 1)
        3. Prompt user to insert pack
        4. Send pack image data (Phase 2)

        Args:
            opk_data: Complete OPK file contents.
            progress: Optional callback for progress updates (bytes_done, total).
            user_prompt: Optional callback to prompt user for pack insertion.
                         Should return True to continue, False to abort.
                         If None, continues without prompting.

        Raises:
            ValueError: If OPK data is invalid.
            ConnectionError: If connection fails.
            TransferError: If transfer fails.
        """
        # Validate OPK data
        if len(opk_data) < OPK_HEADER_SIZE:
            raise ValueError(f"OPK data too short: {len(opk_data)} bytes")

        if opk_data[:4] != b'OPK\x00':
            raise ValueError("Invalid OPK file: missing OPK signature")

        # Extract pack image (skip OPK header)
        pack_image = opk_data[OPK_HEADER_SIZE:]
        logger.info("Pack image size: %d bytes", len(pack_image))

        # Phase 1: Upload bootloader
        logger.info("Phase 1: Uploading bootloader...")
        self._phase1_upload_bootloader(progress)

        # Prompt user to insert pack
        if user_prompt:
            logger.info("Waiting for user to insert pack...")
            if not user_prompt():
                raise TransferError("User aborted transfer")

        # Phase 2: Send pack data
        logger.info("Phase 2: Sending pack data...")
        self._phase2_send_pack_data(pack_image, progress)

        logger.info("BOOT transfer complete!")

    def _phase1_upload_bootloader(
        self,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Phase 1: Upload bootloader to Psion RAM.

        Protocol flow:
        1. PC polls with LINK_REQUEST
        2. Psion responds with LINK_REQUEST (user entered BOOT mode)
        3. PC sends ACK
        4. Psion sends DATA "BOOT"
        5. PC sends ACK + DATA 0x00 (ready)
        6. Exchange boot info (length, address)
        7. Send bootloader in chunks
        8. DISCONNECT with success code
        """
        # Build packets for handshake
        link_request = Packet(PacketType.LINK_REQUEST, sequence=0, data=b"")

        # State machine
        state = 'HANDSHAKE'
        buffer = bytearray()
        got_boot = False
        sent_boot_info = False
        boot_length_sent = False
        address_received = False
        load_address = 0  # Will be set by Psion
        bytes_sent = 0
        chunk_index = 0
        total_bytes = len(self._bootloader)

        # Timing
        start_time = time.time()
        last_link_req_time = 0.0
        READ_TIMEOUT = 0.05

        old_timeout = self.link.port.timeout
        self.link.port.timeout = READ_TIMEOUT

        try:
            while time.time() - start_time < self.HANDSHAKE_TIMEOUT:
                now = time.time()

                # Send Link Requests during handshake
                if state == 'HANDSHAKE' and (now - last_link_req_time) >= self.LINK_REQ_INTERVAL:
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
                        logger.info("Psion entered BOOT mode")
                        ack = Packet(PacketType.ACK, sequence=0, data=b"")
                        self.link._send_packet(ack)
                        state = 'CONNECTED'
                        self.link._connected = True

                    elif packet.type == PacketType.DISCONNECT:
                        logger.debug("RX: DISCONNECT")
                        self.link._connected = False
                        raise ConnectionError("Psion disconnected during Phase 1")

                    elif packet.type == PacketType.ACK:
                        logger.debug("RX: ACK seq=%d", packet.sequence)

                    elif packet.type == PacketType.DATA:
                        seq = packet.sequence
                        logger.debug("RX: DATA seq=%d len=%d data=%s",
                                    seq, len(packet.data), packet.data[:20].hex())

                        if packet.data == BOOT_OVERLAY:
                            logger.info("Received BOOT overlay")
                            got_boot = True
                            # Send ACK + ready signal (0x00)
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            self._send_data(seq, bytes([0x00]))

                        elif got_boot and not boot_length_sent:
                            # Psion requests boot info - send bootloader length
                            logger.info("Sending bootloader length: %d bytes", BOOTLOADER_SIZE)
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            # Length in big-endian
                            length_data = bytes([
                                (BOOTLOADER_SIZE >> 8) & 0xFF,
                                BOOTLOADER_SIZE & 0xFF
                            ])
                            self._send_data(seq, length_data)
                            boot_length_sent = True

                        elif boot_length_sent and not address_received:
                            # Psion sends load address
                            if len(packet.data) >= 2:
                                load_address = (packet.data[0] << 8) | packet.data[1]
                                logger.info("Load address: 0x%04X", load_address)
                                address_received = True

                                # Relocate bootloader for the actual load address
                                self._bootloader = relocate_bootloader(
                                    self._bootloader, load_address
                                )

                                # Send first code chunk with header
                                self._send_ack(seq)
                                time.sleep(self.PACKET_DELAY)

                                # All chunks use same format: addr(2) + code(200)
                                first_chunk = bytearray()
                                first_chunk.extend([
                                    (load_address >> 8) & 0xFF,
                                    load_address & 0xFF,
                                ])
                                code_bytes = min(BOOTLOADER_CHUNK_SIZE - 2, total_bytes)
                                first_chunk.extend(self._bootloader[:code_bytes])

                                self._send_data(seq, bytes(first_chunk))
                                bytes_sent = code_bytes
                                chunk_index = 1

                                if progress:
                                    progress(bytes_sent, total_bytes)

                        elif address_received and bytes_sent < total_bytes:
                            # Psion requests next chunk (sends 0x00)
                            if packet.data == bytes([0x00]):
                                self._send_ack(seq)
                                time.sleep(self.PACKET_DELAY)

                                # Calculate next chunk address and data
                                chunk_addr = load_address + bytes_sent
                                remaining_bytes = total_bytes - bytes_sent
                                chunk_size = min(BOOTLOADER_CHUNK_SIZE - 2, remaining_bytes)

                                # Subsequent chunks: addr(2) + code
                                chunk_data = bytearray()
                                chunk_data.extend([
                                    (chunk_addr >> 8) & 0xFF,
                                    chunk_addr & 0xFF,
                                ])
                                chunk_data.extend(
                                    self._bootloader[bytes_sent:bytes_sent + chunk_size]
                                )

                                self._send_data(seq, bytes(chunk_data))
                                bytes_sent += chunk_size
                                chunk_index += 1

                                logger.debug("Sent chunk %d: %d bytes at 0x%04X",
                                            chunk_index, chunk_size, chunk_addr)

                                if progress:
                                    progress(bytes_sent, total_bytes)

                        elif bytes_sent >= total_bytes:
                            # All bootloader sent - wait for final ACK then disconnect
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            self._send_disconnect(bytes([SUCCESS_CODE]))
                            logger.info("Phase 1 complete: %d bytes sent", bytes_sent)
                            return

            raise TimeoutError(f"Phase 1 timed out after {self.HANDSHAKE_TIMEOUT}s")

        finally:
            self.link.port.timeout = old_timeout

    def _phase2_send_pack_data(
        self,
        pack_image: bytes,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Phase 2: Send pack image data to the bootloader.

        Protocol flow (from captured traffic):
        1. New connection handshake (LINK_REQUEST exchange)
        2. Multiple sync exchanges (both sides send 0x0000, ~10 rounds)
        3. PC sends 0x014F, waits for ACK, then sends 0xC701
        4. Psion sends 0x0004 (~1.7s delay), PC responds with 0x0001
        5. Psion sends 0x0101 (ready for data)
        6. Pack data transfer (200-byte chunks, raw data, no address prefix)
        7. Completion handshake: 0x0004 echo exchange, then PC sends empty DATA + DISCONNECT
        """
        # Build packets for handshake
        link_request = Packet(PacketType.LINK_REQUEST, sequence=0, data=b"")

        # State machine
        state = 'HANDSHAKE'
        buffer = bytearray()
        sync_count = 0
        negotiation_step = 0  # Track negotiation phase
        bytes_sent = 0
        total_bytes = len(pack_image)
        data_transfer_started = False
        waiting_for_final_ack = False
        completion_echo_count = 0  # Track status echo rounds for termination
        first_empty_sent = False  # Track if we've sent the FIRST empty DATA
        last_data_seq = 0  # Track last data sequence for completion

        # Timing
        start_time = time.time()
        last_link_req_time = 0.0
        READ_TIMEOUT = 0.05

        old_timeout = self.link.port.timeout
        self.link.port.timeout = READ_TIMEOUT

        try:
            while time.time() - start_time < self.HANDSHAKE_TIMEOUT:
                now = time.time()

                # Send Link Requests during handshake
                if state == 'HANDSHAKE' and (now - last_link_req_time) >= self.LINK_REQ_INTERVAL:
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
                        logger.info("Phase 2: Bootloader ready")
                        ack = Packet(PacketType.ACK, sequence=0, data=b"")
                        self.link._send_packet(ack)
                        state = 'CONNECTED'

                    elif packet.type == PacketType.DISCONNECT:
                        logger.debug("RX: DISCONNECT")
                        if bytes_sent >= total_bytes:
                            logger.info("Phase 2 complete: %d bytes sent", bytes_sent)
                            return
                        raise ConnectionError("Bootloader disconnected during Phase 2")

                    elif packet.type == PacketType.ACK:
                        seq = packet.sequence
                        logger.debug("RX: ACK seq=%d (negotiation_step=%d, waiting_final=%s)",
                                    seq, negotiation_step, waiting_for_final_ack)

                        # Handle final ACK after sending SECOND empty DATA - send DISCONNECT
                        if waiting_for_final_ack:
                            logger.info("Completion: received final ACK seq=%d, sending DISCONNECT", seq)
                            time.sleep(self.PACKET_DELAY)
                            self.link.disconnect(0x00)
                            logger.info("Phase 2 complete: sent DISCONNECT 0x00, %d bytes transferred",
                                       bytes_sent)
                            time.sleep(0.5)
                            return

                        # Handle ACK during Phase 2 negotiation
                        if negotiation_step == 1:
                            # Psion acknowledged 0x014F, now send 0xC701 with incremented seq
                            next_seq = (seq + 1) & 0x07
                            self._send_data(next_seq, bytes([0xC7, 0x01]))
                            negotiation_step = 2
                            logger.info("Negotiation: Psion ACK'd 0x014F, sent 0xC701 seq=%d", next_seq)
                        continue

                    elif packet.type == PacketType.LINK_REQUEST and state == 'CONNECTED':
                        # LINK_REQUEST only used for initial Phase 2 handshake
                        seq = packet.sequence
                        logger.debug("RX: LINK_REQ seq=%d", seq)

                    elif packet.type == PacketType.DATA:
                        seq = packet.sequence
                        logger.debug("RX: DATA seq=%d len=%d data=%s",
                                    seq, len(packet.data), packet.data.hex() if packet.data else "")

                        # Phase 2 protocol (from captured traffic - Jan 2025):
                        # IMPORTANT: PC sends ACK packets as acknowledgment (NOT LINK_REQ!)
                        # 1. Sync exchanges (0x0000) - about 10 rounds
                        # 2. After syncs, PC sends 0x014F (same seq), waits for ACK
                        # 3. PC sends 0xC701 (incremented seq), waits for ACK
                        # 4. Psion sends 0x0004 (~1.7s delay), PC responds with 0x0001
                        # 5. Psion sends 0x0101 (ready for data)
                        # 6. Pack data transfer begins

                        if packet.data == b'\x00\x00' and not data_transfer_started:
                            # Sync exchange - respond with ACK, then either 0x0000 or 0x014F
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            sync_count += 1
                            logger.debug("Sync %d: received 0x0000 seq=%d", sync_count, seq)

                            if sync_count >= 10 and negotiation_step == 0:
                                # After 10 syncs, send 0x014F instead of 0x0000
                                self._send_data(seq, bytes([0x01, 0x4F]))
                                negotiation_step = 1
                                logger.info("Negotiation: sent 0x014F seq=%d (after %d syncs)",
                                           seq, sync_count)
                            else:
                                # Continue sync exchange
                                self._send_data(seq, bytes([0x00, 0x00]))
                                logger.debug("Sync response: sent 0x0000 seq=%d", seq)
                            continue

                        elif packet.data == b'\x00\x04' and negotiation_step >= 2 and not data_transfer_started:
                            # Psion acknowledges negotiation (after 0x014F and 0xC701)
                            # Send ACK with same seq, then DATA 0x0001 with INCREMENTED seq
                            logger.info("Negotiation: received 0x0004 seq=%d, sending 0x0001", seq)
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            next_seq = (seq + 1) & 0x07
                            self._send_data(next_seq, bytes([0x00, 0x01]))
                            logger.info("Negotiation: sent 0x0001 seq=%d", next_seq)
                            negotiation_step = 3
                            continue

                        elif (len(packet.data) == 2 and packet.data[0] == 0x00
                              and data_transfer_started):
                            # Status byte 0x00XX means "send more data" or "completion"
                            # The bootloader sends various status values (0x0004, 0x00FF, 0x0014, etc.)
                            status_byte = packet.data[1]

                            if bytes_sent < total_bytes:
                                # More data to send - status is "send next chunk" signal
                                self._send_ack(seq)
                                time.sleep(self.PACKET_DELAY)

                                # Send next chunk with INCREMENTED sequence
                                next_seq = (seq + 1) & 0x07
                                chunk_size = min(PACK_DATA_CHUNK_SIZE, total_bytes - bytes_sent)
                                chunk_data = pack_image[bytes_sent:bytes_sent + chunk_size]

                                self._send_data(next_seq, chunk_data)
                                bytes_sent += chunk_size
                                last_data_seq = next_seq

                                logger.debug("Sent pack data: %d/%d bytes (status=0x%02X)",
                                            bytes_sent, total_bytes, status_byte)

                                if progress:
                                    progress(bytes_sent, total_bytes)
                            else:
                                # All data sent - status is completion signal
                                completion_echo_count += 1
                                logger.info("Completion: received 0x00%02X (echo_count=%d, first_empty=%s)",
                                           status_byte, completion_echo_count, first_empty_sent)

                                self._send_ack(seq)
                                time.sleep(self.PACKET_DELAY)
                                next_seq = (seq + 1) & 0x07

                                if not first_empty_sent:
                                    # First status received - send FIRST empty DATA
                                    self._send_data(next_seq, b'')
                                    logger.info("Completion: sent FIRST empty DATA seq=%d", next_seq)
                                    first_empty_sent = True
                                else:
                                    # Second status received - send SECOND empty DATA immediately
                                    self._send_data(next_seq, b'')
                                    logger.info("Completion: sent SECOND empty DATA seq=%d", next_seq)
                                    waiting_for_final_ack = True
                            continue

                        elif packet.data == b'\x01\x01' and negotiation_step >= 3:
                            # Psion ready for data - start transfer
                            logger.info("Negotiation: received 0x0101 (ready) seq=%d", seq)
                            logger.info("Data transfer: starting, total=%d bytes", total_bytes)
                            data_transfer_started = True
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)

                            # Send first chunk with INCREMENTED sequence
                            next_seq = (seq + 1) & 0x07
                            chunk_size = min(PACK_DATA_CHUNK_SIZE, total_bytes)
                            chunk_data = pack_image[:chunk_size]
                            logger.info("Data transfer: sending first chunk seq=%d, %d bytes (first 8: %s)",
                                       next_seq, chunk_size, chunk_data[:8].hex())
                            self._send_data(next_seq, chunk_data)
                            bytes_sent = chunk_size
                            last_data_seq = next_seq

                            if progress:
                                progress(bytes_sent, total_bytes)
                            continue

                        elif data_transfer_started and bytes_sent < total_bytes:
                            # Psion acknowledges data chunk - send next chunk
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)

                            # Send next chunk with INCREMENTED sequence
                            next_seq = (seq + 1) & 0x07
                            chunk_size = min(PACK_DATA_CHUNK_SIZE, total_bytes - bytes_sent)
                            chunk_data = pack_image[bytes_sent:bytes_sent + chunk_size]

                            self._send_data(next_seq, chunk_data)
                            bytes_sent += chunk_size
                            last_data_seq = next_seq

                            logger.debug("Sent pack data: %d/%d bytes",
                                        bytes_sent, total_bytes)

                            if progress:
                                progress(bytes_sent, total_bytes)

                        else:
                            # Unknown state - respond with ACK and sync
                            logger.debug("Unknown DATA in Phase 2: %s", packet.data.hex())
                            self._send_ack(seq)
                            time.sleep(self.PACKET_DELAY)
                            self._send_data(seq, bytes([0x00, 0x00]))

            raise TimeoutError(f"Phase 2 timed out after {self.HANDSHAKE_TIMEOUT}s")

        finally:
            self.link.port.timeout = old_timeout

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _send_ack(self, sequence: int) -> None:
        """Send an ACK packet."""
        ack = Packet(PacketType.ACK, sequence=sequence, data=b"")
        self.link._send_packet(ack)
        logger.debug("TX: ACK seq=%d", sequence)

    def _send_link_request(self, sequence: int) -> None:
        """Send a LINK_REQUEST packet (used as ACK in Phase 2)."""
        pkt = Packet(PacketType.LINK_REQUEST, sequence=sequence, data=b"")
        self.link._send_packet(pkt)
        logger.debug("TX: LINK_REQ seq=%d", sequence)

    def _send_data(self, sequence: int, data: bytes) -> None:
        """Send a DATA packet."""
        pkt = Packet(PacketType.DATA, sequence=sequence, data=data)
        self.link._send_packet(pkt)
        logger.debug("TX: DATA seq=%d len=%d", sequence, len(data))

    def _send_disconnect(self, data: bytes = b"") -> None:
        """Send a DISCONNECT packet."""
        pkt = Packet(PacketType.DISCONNECT, sequence=0, data=data)
        self.link._send_packet(pkt)
        logger.debug("TX: DISCONNECT data=%s", data.hex() if data else "(empty)")

    def _parse_packet_from_buffer(
        self,
        buffer: bytes
    ) -> Tuple[Optional[Packet], bytes]:
        """
        Try to parse a packet from the buffer.

        Returns:
            Tuple of (packet, remaining_buffer). Packet is None if incomplete.
        """
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


# =============================================================================
# Convenience Functions
# =============================================================================

def flash_opk(
    link: LinkProtocol,
    opk_path: str,
    progress: Optional[ProgressCallback] = None,
    user_prompt: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Flash an OPK file to the Psion via BOOT protocol.

    Args:
        link: LinkProtocol instance (should not be connected).
        opk_path: Path to OPK file.
        progress: Optional progress callback.
        user_prompt: Optional callback to prompt user for pack insertion.

    Raises:
        FileNotFoundError: If OPK file not found.
        ValueError: If OPK file is invalid.
        TransferError: If transfer fails.
    """
    path = Path(opk_path)
    if not path.exists():
        raise FileNotFoundError(f"OPK file not found: {opk_path}")

    opk_data = path.read_bytes()
    logger.info("Loaded OPK file: %s (%d bytes)", path.name, len(opk_data))

    boot = BootTransfer(link)
    boot.flash_pack(opk_data, progress=progress, user_prompt=user_prompt)
