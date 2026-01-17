"""
Psion Communication Module
===========================

This module provides communication facilities for transferring files
between a PC and the Psion Organiser II via serial connection. It
implements the Psion Link Protocol and FTRAN file transfer overlay.

Protocol Architecture
---------------------
**Important**: The FTRAN protocol operates in a server-client model:

- **Psion** acts as the **client** that initiates all requests
- **PC** acts as the **server** that responds to requests

This means:

- **Psion RECEIVE mode**: Psion requests files from PC. Use `serve_file()`.
- **Psion SEND mode**: Psion pushes files to PC. Use `receive_file()`.

Module Structure
----------------
The comms module is organized into several submodules:

- **crc**: CRC-CCITT checksum implementation
- **link**: Low-level link protocol (packet framing, handshaking)
- **serial**: Serial port utilities (detection, configuration)
- **transfer**: High-level file transfer (FTRAN protocol)

Quick Start
-----------
**Sending a file to Psion** (Psion in RECEIVE mode):

    from psion_sdk.comms import (
        LinkProtocol,
        FileTransfer,
        FileType,
        open_serial_port,
    )

    # Open port and connect
    port = open_serial_port('/dev/ttyUSB0', baud_rate=9600)
    link = LinkProtocol(port)
    link.connect(timeout=30)

    # Serve file (Psion will request it)
    transfer = FileTransfer(link)
    transfer.serve_file("MYFILE", file_data, FileType.OPL)

    # Clean up
    link.disconnect()
    port.close()

**Receiving a file from Psion** (Psion in SEND mode):

    # Open port and connect
    port = open_serial_port('/dev/ttyUSB0', baud_rate=9600)
    link = LinkProtocol(port)
    link.connect(timeout=30)

    # Receive file (Psion will push it)
    transfer = FileTransfer(link)
    filename, data = transfer.receive_file()
    print(f"Received: {filename} ({len(data)} bytes)")

    # Clean up
    link.disconnect()
    port.close()

Hardware Requirements
---------------------
The Psion Comms Link uses a DB-25 RS-232 connector. For modern computers,
you need:

1. DB-25 to DE-9 adapter (if your USB adapter has 9-pin connector)
2. USB-Serial adapter (FTDI or Silicon Labs recommended)

The serial settings must match the Psion's COMMS setup:
- Baud rate: 9600 (default, can be 1200/2400/4800/9600)
- 8 data bits, no parity, 1 stop bit
- No flow control

Error Handling
--------------
All communication errors inherit from `CommsError`:

- `ConnectionError`: Cannot establish or maintain connection
- `TransferError`: File transfer failed (CRC error, timeout, etc.)
- `ProtocolError`: Link protocol violation

These exceptions are defined in `psion_sdk.errors`.

Thread Safety
-------------
The communication classes are NOT thread-safe. Use only from a single
thread, or protect all calls with external synchronization.

References
----------
- https://www.jaapsch.net/psion/protocol.htm (protocol documentation)
- specs/03-comms.md (full specification in this project)
- dev_docs/FTRAN_PROTOCOL_NOTES.md (protocol investigation notes)
"""

# =============================================================================
# Public API Exports
# =============================================================================

# CRC utilities
from psion_sdk.comms.crc import (
    CRC_INITIAL,
    CRC_TABLE,
    REFERENCE_CRC_VALUES,
    crc_ccitt,
    crc_ccitt_fast,
    crc_from_bytes,
    crc_to_bytes,
    verify_crc,
    verify_packet_crc,
)

# Link protocol
from psion_sdk.comms.link import (
    CHANNEL_NUMBER,
    MAX_DATA_SIZE,
    MIN_PACKET_SIZE,
    PACKET_FOOTER,
    PACKET_HEADER,
    LinkProtocol,
    Packet,
    PacketType,
    RemoteError,
)

# Serial port utilities
from psion_sdk.comms.serial import (
    DEFAULT_BAUD_RATE,
    VALID_BAUD_RATES,
    PortInfo,
    close_serial_port,
    find_psion_port,
    format_port_list,
    get_default_port_prefix,
    list_serial_ports,
    open_serial_port,
    validate_port_settings,
)

# File transfer
from psion_sdk.comms.transfer import (
    # Constants
    MAX_BLOCK_SIZE,
    FTRAN_OVERLAY,
    DEFAULT_OPL_BLOCK_LENGTH,
    OPL_MARKER,
    EOF_DISCONNECT_BYTE,
    CMD_OPEN,
    CMD_CLOSE,
    CMD_PUT_DATA,
    CMD_GET_DATA,
    # Enums
    OpenMode,
    FileType,
    ResponseStatus,
    # Classes
    DirectoryEntry,
    FTRANCommand,
    FileTransfer,
    # Type aliases
    ProgressCallback,
    # Convenience functions
    send_opk,
    receive_opk,
)

# BOOT protocol (pack flashing)
from psion_sdk.comms.boot import (
    # Constants
    BOOT_OVERLAY,
    BOOTLOADER_SIZE,
    BOOTLOADER_LOAD_ADDRESS,
    BOOTLOADER_CHUNK_SIZE,
    OPK_HEADER_SIZE,
    PACK_DATA_CHUNK_SIZE,
    RELOC_OFFSETS,
    # Classes
    BootTransfer,
    # Functions
    get_bootloader,
    relocate_bootloader,
    flash_opk,
)

# Version info
__version__ = "1.1.0"

# Public API - what gets exported with "from psion_sdk.comms import *"
__all__ = [
    # Version
    "__version__",
    # CRC
    "CRC_TABLE",
    "CRC_INITIAL",
    "REFERENCE_CRC_VALUES",
    "crc_ccitt",
    "crc_ccitt_fast",
    "crc_to_bytes",
    "crc_from_bytes",
    "verify_crc",
    "verify_packet_crc",
    # Link Protocol
    "PACKET_HEADER",
    "PACKET_FOOTER",
    "CHANNEL_NUMBER",
    "MAX_DATA_SIZE",
    "MIN_PACKET_SIZE",
    "PacketType",
    "RemoteError",
    "Packet",
    "LinkProtocol",
    # Serial
    "VALID_BAUD_RATES",
    "DEFAULT_BAUD_RATE",
    "PortInfo",
    "list_serial_ports",
    "find_psion_port",
    "open_serial_port",
    "close_serial_port",
    "validate_port_settings",
    "get_default_port_prefix",
    "format_port_list",
    # Transfer Constants
    "MAX_BLOCK_SIZE",
    "FTRAN_OVERLAY",
    "DEFAULT_OPL_BLOCK_LENGTH",
    "OPL_MARKER",
    "EOF_DISCONNECT_BYTE",
    "CMD_OPEN",
    "CMD_CLOSE",
    "CMD_PUT_DATA",
    "CMD_GET_DATA",
    # Transfer Enums
    "OpenMode",
    "FileType",
    "ResponseStatus",
    # Transfer Classes
    "DirectoryEntry",
    "FTRANCommand",
    "FileTransfer",
    "ProgressCallback",
    # Transfer Functions
    "send_opk",
    "receive_opk",
    # BOOT Protocol Constants
    "BOOT_OVERLAY",
    "BOOTLOADER_SIZE",
    "BOOTLOADER_LOAD_ADDRESS",
    "BOOTLOADER_CHUNK_SIZE",
    "OPK_HEADER_SIZE",
    "PACK_DATA_CHUNK_SIZE",
    "RELOC_OFFSETS",
    # BOOT Protocol Classes
    "BootTransfer",
    # BOOT Protocol Functions
    "get_bootloader",
    "relocate_bootloader",
    "flash_opk",
]
