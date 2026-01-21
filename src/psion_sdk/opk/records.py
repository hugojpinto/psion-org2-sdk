"""
OPK Record Type Definitions
============================

This module defines the data structures for OPK (Psion Pack) file records.
These records are the fundamental building blocks of a Psion pack image.

Pack Structure Overview
-----------------------
An OPK file contains:
1. OPK Header (6 bytes): Magic "OPK" + 24-bit data length
2. Pack Data Block:
   - Pack Header (10 bytes): Flags, size, timestamp, checksum
   - Records (variable): File records, data records
   - End Marker (2 bytes): FF FF

Record Format
-------------
Psion uses two record formats:

**Short Records** (most common):
    Byte 0:   Length (0x01-0xFE) - bytes that follow, excluding length byte
    Byte 1:   Record type
    Byte 2+:  Data (length-1 bytes)

**Long Records** (for data > 254 bytes):
    Byte 0:   0x02 (error correction marker)
    Byte 1:   0x80 (long record type)
    Byte 2-3: Length word (big-endian)
    Byte 4+:  Data

Record Types
------------
- $80: Long Record marker
- $81: Data File (ODB database header)
- $82: Diary (CM/XP diary entries)
- $83: Procedure (OPL or machine code)
- $84: Comms Setup (communications configuration)
- $85: Spreadsheet (Pocket Spreadsheet file)
- $86: Pager Setup (pager configuration)
- $87: Notepad (LZ notepad file)
- $90-$FE: Data Records (individual records within data files)
- $FF: End marker or error correction byte
- $01-$7F: Deleted records (high bit cleared)

Reference
---------
- File format documentation: https://www.jaapsch.net/psion/fileform.htm
- JAPE emulator pack.js: jape/pack.js
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
import struct


# =============================================================================
# Enumeration Types
# =============================================================================

class PackType(IntEnum):
    """
    Pack hardware type flags.

    The flags byte (offset 0 in pack header) identifies the pack type.

    Bit layout:
        Bit 7: 0 = valid pack, 1 = invalid/unformatted
        Bit 6: 0 = flash pack, 1 = other (datapak/rampak)
        Bit 2: 0 = linear addressing, 1 = paged addressing
        Bit 1: 0 = RAM pack, 1 = EPROM/Flash
        Bit 0: MK1 format flag

    Note: Datapaks (EPROM) must have bit 6 SET to distinguish from flash packs.
    """
    RAMPAK = 0x40           # RAM pack, linear addressing (bit 6 set = not flash)
    DATAPAK = 0x56          # EPROM (Datapak), matches official DOS SDK (bit 6 + bit 4 + bit 2 + bit 1)
    DATAPAK_PAGED = 0x46    # EPROM (Datapak), paged addressing (bit 6 + bit 2 + bit 1)
    DATAPAK_SIMPLE = 0x4a   # EPROM (Datapak), simple format like fnkey40.opk (bit 6 + bit 3 + bit 1)
    FLASHPAK = 0x02         # Flash pack, linear addressing (bit 6 clear = flash)
    FLASHPAK_PAGED = 0x06   # Flash pack, paged addressing
    MK1 = 0xFB              # Organiser I (MK1) pack format

    @classmethod
    def from_flags(cls, flags: int) -> "PackType":
        """Convert a flags byte to a PackType enum value."""
        try:
            return cls(flags)
        except ValueError:
            pass

        if flags == 0xFB:
            return cls.MK1

        is_flash = (flags & 0x40) == 0   # bit 6 clear = flash pack
        is_eprom = (flags & 0x02) != 0   # bit 1 set = EPROM/Flash (vs RAM)
        is_paged = (flags & 0x04) != 0   # bit 2 set = paged addressing

        if is_flash:
            return cls.FLASHPAK_PAGED if is_paged else cls.FLASHPAK
        elif is_eprom:
            return cls.DATAPAK_PAGED if is_paged else cls.DATAPAK
        else:
            return cls.RAMPAK

    def get_description(self) -> str:
        """Get a human-readable description of the pack type."""
        descriptions = {
            PackType.RAMPAK: "RAM Pack (linear addressing)",
            PackType.DATAPAK: "Datapak (EPROM, linear)",
            PackType.DATAPAK_PAGED: "Datapak (EPROM, paged)",
            PackType.FLASHPAK: "Flash Pack (linear)",
            PackType.FLASHPAK_PAGED: "Flash Pack (paged)",
            PackType.MK1: "Organiser I (MK1) Pack",
        }
        return descriptions.get(self, f"Unknown (0x{self:02X})")


class RecordType(IntEnum):
    """
    Pack record type identifiers.

    Each record in the pack has a type byte that identifies what kind of
    data it contains.
    """
    LONG = 0x80             # Long record marker
    DATA_FILE = 0x81        # ODB data file header
    DIARY = 0x82            # CM/XP diary file
    PROCEDURE = 0x83        # OPL or machine code procedure
    COMMS = 0x84            # Communications setup
    SPREADSHEET = 0x85      # Pocket Spreadsheet file
    PAGER = 0x86            # Pager setup
    NOTEPAD = 0x87          # LZ notepad file
    END = 0xFF              # End marker

    # Data records range from 0x90 to 0xFE
    DATA_RECORD_MIN = 0x90
    DATA_RECORD_MAX = 0xFE

    @classmethod
    def is_data_record(cls, type_byte: int) -> bool:
        """Check if a type byte represents a data record."""
        return cls.DATA_RECORD_MIN <= type_byte <= cls.DATA_RECORD_MAX

    @classmethod
    def is_file_record(cls, type_byte: int) -> bool:
        """Check if a type byte represents a file header record."""
        return type_byte in (cls.DATA_FILE, cls.DIARY, cls.PROCEDURE,
                            cls.COMMS, cls.SPREADSHEET, cls.PAGER, cls.NOTEPAD)

    @classmethod
    def is_deleted(cls, type_byte: int) -> bool:
        """Check if a type byte represents a deleted record (high bit clear)."""
        return 0x01 <= type_byte <= 0x7F

    @classmethod
    def get_name(cls, type_byte: int) -> str:
        """Get a human-readable name for a record type."""
        names = {
            0x80: "Long Record",
            0x81: "Data File",
            0x82: "Diary",
            0x83: "Procedure",
            0x84: "Comms Setup",
            0x85: "Spreadsheet",
            0x86: "Pager Setup",
            0x87: "Notepad",
            0xFF: "End Marker",
        }
        if type_byte in names:
            return names[type_byte]
        if cls.is_data_record(type_byte):
            return f"Data Record (0x{type_byte:02X})"
        if cls.is_deleted(type_byte):
            return f"Deleted (0x{type_byte:02X})"
        return f"Unknown (0x{type_byte:02X})"


class PackSize(IntEnum):
    """Standard pack sizes in kilobytes."""
    SIZE_8K = 8
    SIZE_16K = 16
    SIZE_32K = 32
    SIZE_64K = 64
    SIZE_128K = 128

    @classmethod
    def from_indicator(cls, indicator: int) -> "PackSize":
        """Convert a size indicator byte to a PackSize."""
        size_kb = indicator * 8
        try:
            return cls(size_kb)
        except ValueError:
            raise ValueError(f"Invalid pack size indicator: {indicator} ({size_kb}KB)")

    def to_indicator(self) -> int:
        """Convert this PackSize to a size indicator byte."""
        return self.value // 8

    def to_bytes(self) -> int:
        """Get the size in bytes."""
        return self.value * 1024


# =============================================================================
# Pack Header
# =============================================================================

@dataclass
class PackHeader:
    """
    Pack header information (10 bytes in pack data block).

    Structure:
        Offset  Size    Description
        ------  ----    -----------
        0       1       Flags byte (pack type)
        1       1       Size indicator (number of 8KB blocks)
        2       1       Year (0-99)
        3       1       Month (0-11, zero-indexed)
        4       1       Day (0-30, zero-indexed)
        5       1       Hour (0-23)
        6       1       Reserved
        7       1       Frame counter
        8       2       Checksum (big-endian)
    """
    flags: int = PackType.DATAPAK
    size_kb: int = 16
    timestamp: datetime = field(default_factory=datetime.now)
    checksum: int = 0
    reserved: int = 0
    frame_counter: int = 0
    HEADER_SIZE: int = field(default=10, repr=False, init=False)

    def to_bytes(self) -> bytes:
        """Serialize the pack header to 10 bytes."""
        size_indicator = self.size_kb // 8
        year = self.timestamp.year % 100
        month = self.timestamp.month - 1
        day = self.timestamp.day - 1
        hour = self.timestamp.hour

        return struct.pack(
            ">BBBBBBBBH",
            self.flags,
            size_indicator,
            year,
            month,
            day,
            hour,
            self.reserved,
            self.frame_counter,
            self.checksum
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "PackHeader":
        """Deserialize a pack header from bytes."""
        if len(data) < 10:
            raise ValueError(f"Header too short: need 10 bytes, got {len(data)}")

        flags = data[0]
        size_indicator = data[1]
        year = data[2]
        month = data[3]
        day = data[4]
        hour = data[5]
        reserved = data[6]
        frame_counter = data[7]
        checksum = (data[8] << 8) | data[9]

        size_kb = size_indicator * 8
        century = 1900 if year >= 80 else 2000

        try:
            timestamp = datetime(century + year, month + 1, day + 1, hour)
        except ValueError:
            timestamp = datetime.now()

        return cls(
            flags=flags,
            size_kb=size_kb,
            timestamp=timestamp,
            checksum=checksum,
            reserved=reserved,
            frame_counter=frame_counter
        )

    def get_pack_type(self) -> PackType:
        """Get the pack type as a PackType enum."""
        return PackType.from_flags(self.flags)

    def get_pack_size(self) -> PackSize:
        """Get the pack size as a PackSize enum."""
        return PackSize(self.size_kb)


# =============================================================================
# Record Base Class
# =============================================================================

@dataclass
class PackRecord:
    """
    Base class for pack records.

    All Psion pack records use the format:
        [length] [type] [data...]

    Where length is the number of bytes that follow (type + data).
    """
    record_type: int

    def to_bytes(self) -> bytes:
        """Serialize the record to bytes in Psion format."""
        raise NotImplementedError("Subclasses must implement to_bytes()")

    def get_size(self) -> int:
        """Get the total size of this record in bytes."""
        return len(self.to_bytes())

    def get_type_name(self) -> str:
        """Get a human-readable name for this record type."""
        return RecordType.get_name(self.record_type)


# =============================================================================
# File Record (base for all named file types)
# =============================================================================

@dataclass
class FileRecord(PackRecord):
    """
    Base class for file records (types 0x81-0x87).

    All file records have:
    - 8-character space-padded name
    - Record type identifier

    Format: [length] [type] [name 8 bytes] [optional data]
    """
    record_type: int = RecordType.PROCEDURE
    name: str = ""

    def __post_init__(self) -> None:
        """Normalize name to uppercase and pad/truncate to 8 chars."""
        self.name = self.name.upper()[:8].ljust(8)

    def get_display_name(self) -> str:
        """Get the name without trailing spaces."""
        return self.name.rstrip()


# =============================================================================
# Procedure Record
# =============================================================================

@dataclass
class ProcedureRecord(FileRecord):
    """
    Procedure file record (type $83).

    Contains OPL procedures or machine code programs.

    Psion procedure format (based on OPK editor source analysis):
        1. File header record: [length=9] [0x83] [name 8 bytes]
        2. Data block record: [length=2] [0x80] [blocklen_hi] [blocklen_lo]
        3. Raw block data: [blocklen bytes of obj_len + obj_code + src_len + src_code]

    The data block (type 0x80) wraps the code data and gets merged with
    the header during parsing.
    """
    record_type: int = field(default=RecordType.PROCEDURE, init=False)
    name: str = ""
    object_code: bytes = field(default_factory=bytes)
    source_code: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the procedure record to Psion pack format."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        obj_len = len(self.object_code)
        src_len = len(self.source_code)

        result = bytearray()

        # Part 1: Build the code block data first (to know its length)
        # [obj_len 2 bytes] [obj_code] [src_len 2 bytes] [src_code]
        code_block = bytearray()
        code_block.extend(struct.pack(">H", obj_len))
        code_block.extend(self.object_code)
        code_block.extend(struct.pack(">H", src_len))
        if src_len > 0:
            code_block.extend(self.source_code)

        # Part 2: Data block record [length=2] [type=0x80] [blocklen 2 bytes]
        # This will be the "child" of the file header after parsing
        block_len = len(code_block)
        data_block_header = bytearray()
        data_block_header.append(2)  # Length byte (blocklen word = 2 bytes)
        data_block_header.append(RecordType.LONG)  # Type 0x80 (data block)
        data_block_header.extend(struct.pack(">H", block_len))  # Block length

        # Part 3: File header record [length] [type=0x83] [name 8 bytes] [0x00]
        # Length byte = type(1) + name(8) = 9, plus trailing NUL byte
        result.append(9)  # Length byte
        result.append(RecordType.PROCEDURE)  # Type 0x83
        result.extend(name_bytes)  # Name (8 bytes)
        result.append(0x00)  # Trailing NUL (like file_id for DATA_FILE)

        # Part 4: Data block header + raw block data
        result.extend(data_block_header)
        result.extend(code_block)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["ProcedureRecord", int]:
        """
        Parse a procedure record from pack data.

        The format is:
        1. File header: [length=9] [type=0x83] [name 8 bytes]
        2. Data block record: [length=2] [type=0x80] [blocklen 2 bytes]
        3. Raw block data: [obj_len 2] [obj_code] [src_len 2] [src_code]

        Args:
            data: The raw pack data
            offset: Starting offset

        Returns:
            Tuple of (ProcedureRecord, bytes_consumed)
        """
        start = offset

        # Parse file header record
        header_len = data[offset]
        offset += 1

        # Record type should be 0x83
        rec_type = data[offset]
        if rec_type != RecordType.PROCEDURE:
            raise ValueError(f"Not a procedure record: 0x{rec_type:02X}")
        offset += 1

        # Name (8 bytes)
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        # Skip trailing NUL byte after name
        offset += 1

        # Parse data block record header
        block_header_len = data[offset]
        offset += 1
        block_type = data[offset]
        offset += 1

        if block_type != RecordType.LONG:
            raise ValueError(f"Expected data block (0x80), got: 0x{block_type:02X}")

        # Block length (2 bytes, big-endian)
        block_len = (data[offset] << 8) | data[offset + 1]
        offset += 2

        # Parse code block data
        # Object code length and data
        obj_len = (data[offset] << 8) | data[offset + 1]
        offset += 2
        object_code = bytes(data[offset:offset + obj_len])
        offset += obj_len

        # Source code length and data
        src_len = (data[offset] << 8) | data[offset + 1]
        offset += 2
        source_code = bytes(data[offset:offset + src_len]) if src_len > 0 else b""
        offset += src_len

        return cls(name=name, object_code=object_code, source_code=source_code), offset - start

    def validate_name(self) -> bool:
        """Validate the procedure name (1-8 alphanumeric, starts with letter)."""
        name = self.get_display_name()
        if not name or len(name) > 8:
            return False
        if not name[0].isalpha():
            return False
        return name.replace(" ", "").isalnum()


# =============================================================================
# Data File Record
# =============================================================================

@dataclass
class DataFileRecord(FileRecord):
    """
    Data file header record (type $81).

    Marks the start of an ODB (Organiser Database) file.
    Data records ($90-$FE) follow this header.

    Format: [length=10] [0x81] [name 8 bytes] [file_id]
    """
    record_type: int = field(default=RecordType.DATA_FILE, init=False)
    name: str = ""
    file_id: int = 0x90  # Data records for this file use this type byte

    def to_bytes(self) -> bytes:
        """Serialize the data file header."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        data = bytearray()
        data.append(10)  # Length: type(1) + name(8) + file_id(1) = 10
        data.append(RecordType.DATA_FILE)
        data.extend(name_bytes)
        data.append(self.file_id)
        return bytes(data)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["DataFileRecord", int]:
        """Parse a data file header from pack data."""
        start = offset
        length = data[offset]
        offset += 1

        rec_type = data[offset]
        if rec_type != RecordType.DATA_FILE:
            raise ValueError(f"Not a data file record: 0x{rec_type:02X}")
        offset += 1

        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        file_id = data[offset]
        offset += 1

        return cls(name=name, file_id=file_id), offset - start


# =============================================================================
# Diary Record
# =============================================================================

@dataclass
class DiaryRecord(FileRecord):
    """
    Diary file record (type $82).

    CM/XP diary entries.

    Format: [length] [0x82] [name 8 bytes] [diary data]
    """
    record_type: int = field(default=RecordType.DIARY, init=False)
    name: str = ""
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the diary record."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        content = bytearray()
        content.append(RecordType.DIARY)
        content.extend(name_bytes)
        content.extend(self.data)

        if len(content) <= 254:
            result = bytearray()
            result.append(len(content))
            result.extend(content)
            return bytes(result)
        else:
            result = bytearray()
            result.append(0x02)
            result.append(0x80)
            result.extend(struct.pack(">H", len(content)))
            result.extend(content)
            return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["DiaryRecord", int]:
        """Parse a diary record from pack data."""
        start = offset

        if data[offset] == 0x02 and data[offset + 1] == 0x80:
            length = (data[offset + 2] << 8) | data[offset + 3]
            offset += 4
        else:
            length = data[offset]
            offset += 1

        rec_type = data[offset]
        offset += 1
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        remaining = length - 9  # Subtract type(1) + name(8)
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(name=name, data=record_data), offset - start


# =============================================================================
# Comms Setup Record
# =============================================================================

@dataclass
class CommsRecord(FileRecord):
    """
    Comms link setup file record (type $84).

    Communications configuration settings.

    Format: [length] [0x84] [name 8 bytes] [comms config data]
    """
    record_type: int = field(default=RecordType.COMMS, init=False)
    name: str = ""
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the comms record."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        content = bytearray()
        content.append(RecordType.COMMS)
        content.extend(name_bytes)
        content.extend(self.data)

        result = bytearray()
        result.append(len(content))
        result.extend(content)
        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["CommsRecord", int]:
        """Parse a comms record from pack data."""
        start = offset
        length = data[offset]
        offset += 1

        rec_type = data[offset]
        offset += 1
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        remaining = length - 9
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(name=name, data=record_data), offset - start


# =============================================================================
# Spreadsheet Record
# =============================================================================

@dataclass
class SpreadsheetRecord(FileRecord):
    """
    Pocket Spreadsheet file record (type $85).

    Format: [length] [0x85] [name 8 bytes] [spreadsheet data]
    """
    record_type: int = field(default=RecordType.SPREADSHEET, init=False)
    name: str = ""
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the spreadsheet record."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        content = bytearray()
        content.append(RecordType.SPREADSHEET)
        content.extend(name_bytes)
        content.extend(self.data)

        if len(content) <= 254:
            result = bytearray()
            result.append(len(content))
            result.extend(content)
            return bytes(result)
        else:
            result = bytearray()
            result.append(0x02)
            result.append(0x80)
            result.extend(struct.pack(">H", len(content)))
            result.extend(content)
            return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["SpreadsheetRecord", int]:
        """Parse a spreadsheet record from pack data."""
        start = offset

        if data[offset] == 0x02 and data[offset + 1] == 0x80:
            length = (data[offset + 2] << 8) | data[offset + 3]
            offset += 4
        else:
            length = data[offset]
            offset += 1

        rec_type = data[offset]
        offset += 1
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        remaining = length - 9
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(name=name, data=record_data), offset - start


# =============================================================================
# Pager Setup Record
# =============================================================================

@dataclass
class PagerRecord(FileRecord):
    """
    Pager setup file record (type $86).

    Format: [length] [0x86] [name 8 bytes] [pager config data]
    """
    record_type: int = field(default=RecordType.PAGER, init=False)
    name: str = ""
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the pager record."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        content = bytearray()
        content.append(RecordType.PAGER)
        content.extend(name_bytes)
        content.extend(self.data)

        result = bytearray()
        result.append(len(content))
        result.extend(content)
        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["PagerRecord", int]:
        """Parse a pager record from pack data."""
        start = offset
        length = data[offset]
        offset += 1

        rec_type = data[offset]
        offset += 1
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        remaining = length - 9
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(name=name, data=record_data), offset - start


# =============================================================================
# Notepad Record
# =============================================================================

@dataclass
class NotepadRecord(FileRecord):
    """
    LZ Notepad file record (type $87).

    Format: [length] [0x87] [name 8 bytes] [notepad data]
    """
    record_type: int = field(default=RecordType.NOTEPAD, init=False)
    name: str = ""
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the notepad record."""
        name_bytes = self.name.upper()[:8].ljust(8).encode("ascii")
        content = bytearray()
        content.append(RecordType.NOTEPAD)
        content.extend(name_bytes)
        content.extend(self.data)

        if len(content) <= 254:
            result = bytearray()
            result.append(len(content))
            result.extend(content)
            return bytes(result)
        else:
            result = bytearray()
            result.append(0x02)
            result.append(0x80)
            result.extend(struct.pack(">H", len(content)))
            result.extend(content)
            return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["NotepadRecord", int]:
        """Parse a notepad record from pack data."""
        start = offset

        if data[offset] == 0x02 and data[offset + 1] == 0x80:
            length = (data[offset + 2] << 8) | data[offset + 3]
            offset += 4
        else:
            length = data[offset]
            offset += 1

        rec_type = data[offset]
        offset += 1
        name = data[offset:offset + 8].decode("ascii", errors="replace").rstrip()
        offset += 8

        remaining = length - 9
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(name=name, data=record_data), offset - start


# =============================================================================
# Data Record (individual database record)
# =============================================================================

@dataclass
class DataRecord(PackRecord):
    """
    Individual data record within a data file (types $90-$FE).

    Data records contain the actual data stored in ODB files.
    Fields within a record are typically tab-separated (0x09).

    Format: [length] [type $90-$FE] [field data]
    """
    record_type: int = 0x90
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the data record."""
        content = bytearray()
        content.append(self.record_type)
        content.extend(self.data)

        if len(content) <= 254:
            result = bytearray()
            result.append(len(content))
            result.extend(content)
            return bytes(result)
        else:
            result = bytearray()
            result.append(0x02)
            result.append(0x80)
            result.extend(struct.pack(">H", len(content)))
            result.extend(content)
            return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["DataRecord", int]:
        """Parse a data record from pack data."""
        start = offset

        if data[offset] == 0x02 and data[offset + 1] == 0x80:
            length = (data[offset + 2] << 8) | data[offset + 3]
            offset += 4
        else:
            length = data[offset]
            offset += 1

        rec_type = data[offset]
        offset += 1

        remaining = length - 1
        record_data = bytes(data[offset:offset + remaining]) if remaining > 0 else b""
        offset += remaining

        return cls(record_type=rec_type, data=record_data), offset - start

    def get_fields(self, delimiter: bytes = b"\x09") -> list[bytes]:
        """Split the record data into fields (tab-separated)."""
        return self.data.split(delimiter)


# =============================================================================
# Generic/Unknown Record
# =============================================================================

@dataclass
class GenericRecord(PackRecord):
    """
    Generic record for unknown or unhandled types.

    Used when parsing records that don't match known types.
    """
    record_type: int = 0
    data: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the generic record."""
        content = bytearray()
        content.append(self.record_type)
        content.extend(self.data)

        if len(content) <= 254:
            result = bytearray()
            result.append(len(content))
            result.extend(content)
            return bytes(result)
        else:
            result = bytearray()
            result.append(0x02)
            result.append(0x80)
            result.extend(struct.pack(">H", len(content)))
            result.extend(content)
            return bytes(result)


# =============================================================================
# OB3 File Structure
# =============================================================================

@dataclass
class OB3File:
    """
    Represents an OB3 (ORG) file from the assembler.

    OB3 is the output format of the assembler, NOT the same as pack records.

    Structure:
        Offset  Size    Description
        0       3       Magic number: "ORG"
        3       2       Total data length (big-endian)
        5       1       File type: $83 for procedures
        6       2       Object code length (big-endian)
        8       n       Object code bytes
        8+n     2       Source length (may be 0)
        10+n    m       Source code (if length > 0)
    """
    MAGIC: bytes = field(default=b"ORG", repr=False, init=False)
    FILE_TYPE: int = field(default=0x83, repr=False, init=False)

    object_code: bytes = field(default_factory=bytes)
    source_code: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize the OB3 file to bytes."""
        obj_len = len(self.object_code)
        src_len = len(self.source_code)
        # data_len excludes the type byte (matches official SDK behavior)
        data_len = 2 + obj_len + 2 + src_len

        result = bytearray()
        result.extend(b"ORG")
        result.extend(struct.pack(">H", data_len))
        result.append(0x83)
        result.extend(struct.pack(">H", obj_len))
        result.extend(self.object_code)
        result.extend(struct.pack(">H", src_len))
        if src_len > 0:
            result.extend(self.source_code)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes) -> "OB3File":
        """Parse an OB3 file from bytes."""
        if len(data) < 8:
            raise ValueError(f"OB3 file too short: {len(data)} bytes")

        if data[0:3] != b"ORG":
            raise ValueError(f"Invalid OB3 magic: {data[0:3]!r}")

        file_type = data[5]
        if file_type != 0x83:
            raise ValueError(f"Invalid OB3 file type: 0x{file_type:02X}")

        obj_len = (data[6] << 8) | data[7]
        if len(data) < 8 + obj_len:
            raise ValueError(f"OB3 file truncated")

        object_code = bytes(data[8:8 + obj_len])

        src_offset = 8 + obj_len
        source_code = b""
        if len(data) >= src_offset + 2:
            src_len = (data[src_offset] << 8) | data[src_offset + 1]
            if src_len > 0 and len(data) >= src_offset + 2 + src_len:
                source_code = bytes(data[src_offset + 2:src_offset + 2 + src_len])

        return cls(object_code=object_code, source_code=source_code)

    def is_valid(self) -> bool:
        """Check if this OB3 file is structurally valid."""
        return len(self.object_code) > 0

    # =========================================================================
    # Target Model Constants
    # =========================================================================
    # These define which Psion models are 2-line vs 4-line displays.
    # See dev_docs/TARGET_MODELS.md for full documentation.
    # =========================================================================
    TARGETS_2LINE = ("CM", "XP", "LA")      # 16x2 character displays
    TARGETS_4LINE = ("LZ", "LZ64")          # 20x4 character displays
    TARGETS_ALL = TARGETS_2LINE + TARGETS_4LINE + ("PORTABLE",)
    DEFAULT_TARGET = "XP"

    # QCode opcodes for 4-line procedure identification
    # When LZ/LZ64 sees STOP+SIN at procedure start, it stays in 4-line mode.
    # When CM/XP/LA sees this, STOP executes and gracefully terminates.
    QCODE_STOP = 0x59  # STOP opcode - halts OPL execution
    QCODE_SIN = 0xB2   # SIN opcode - sine function (forms "stop sign" pun)

    @classmethod
    def from_machine_code(cls, machine_code: bytes, target: str = "XP") -> "OB3File":
        """
        Create an OB3 file from raw machine code.

        This wraps the machine code in an OPL procedure structure that can
        be executed on the Psion. The format is based on MAKEPROC output.

        The generated procedure:
        1. Computes the address of the embedded machine code at runtime
        2. Calls it via USR with parameter 0
        3. Returns the result

        Structure of the generated object code:
        - VVVV (2 bytes): Variable space = 2
        - QQQQ (2 bytes): QCode size (varies by target)
        - XX (1 byte): Parameter count = 0
        - Tables (8 bytes): Empty table markers
        - [STOP+SIN] (2 bytes): Only for LZ/LZ64 targets - 4-line identifier
        - QCode (14 bytes): Address calculation + USR call + return
        - Machine code: The actual code to execute

        Target Models:
        - CM, XP, LA: 2-line displays, no STOP+SIN prefix
        - LZ, LZ64: 4-line displays, adds STOP+SIN prefix (0x52 0xB2)
        - PORTABLE: No prefix, runs on all models, programmer controls mode

        The STOP+SIN prefix serves two purposes:
        1. On LZ/LZ64: Identifies procedure as 4-line, OS stays in 4-line mode
        2. On CM/XP/LA: STOP executes first, gracefully terminating the program

        Args:
            machine_code: Raw HD6303 machine code bytes
            target: Target model (CM, XP, LA, LZ, LZ64, PORTABLE). Default: XP

        Returns:
            OB3File with properly wrapped machine code

        Raises:
            ValueError: If target is not a recognized model
        """
        # Validate and normalize target
        target_upper = target.upper()
        if target_upper not in cls.TARGETS_ALL:
            valid = ", ".join(cls.TARGETS_ALL)
            raise ValueError(
                f"Unknown target model '{target}'. Valid targets: {valid}"
            )

        # Determine if we need the STOP+SIN prefix for 4-line mode
        is_4line_target = target_upper in cls.TARGETS_4LINE

        mc_len = len(machine_code)

        # QCode size calculation:
        # - STOP+SIN (if 4-line): 2 bytes
        # - Base QCode bootstrap: 14 bytes
        # - Embedded machine code: mc_len bytes
        prefix_len = 2 if is_4line_target else 0
        qcode_len = prefix_len + 14 + mc_len

        # Build the object code
        obj_code = bytearray()

        # OPL procedure header
        obj_code.extend(struct.pack(">H", 2))          # VVVV: 2 bytes variable space
        obj_code.extend(struct.pack(">H", qcode_len))  # QQQQ: QCode size
        obj_code.append(0)                              # XX: 0 parameters

        # Empty tables (8 bytes of zeros)
        obj_code.extend(b'\x00' * 8)

        # QCode bootstrap that computes machine code address and calls USR
        # This is the exact sequence from MAKEPROC:
        # - Push 0xa9 (RTA system variable address)
        # - PEEKW (read procedure base address)
        # - Push offset, subtract (compute MC address)
        # - Push 0 (USR parameter)
        # - Call USR
        # - Return handling
        #
        # Build QCode - for 4-line targets, STOP+SIN are the first instructions
        qcode = bytearray()
        if is_4line_target:
            qcode.append(cls.QCODE_STOP)  # 0x59 - STOP
            qcode.append(cls.QCODE_SIN)   # 0xB2 - SIN
        qcode.extend([
            0x22, 0x00, 0xa9,        # Push integer 0x00a9 (RTA address)
            0x9c,                    # PEEKW (read procedure base)
            0x22, 0x00, 0x0b,        # Push offset 11 to machine code
            0x2d,                    # Subtract (compute MC address)
            0x22, 0x00, 0x00,        # Push integer 0 (USR parameter)
            0x9f,                    # USR call
            0x86, 0x79,              # Return handling
        ])
        obj_code.extend(qcode)

        # Append the actual machine code
        obj_code.extend(machine_code)

        return cls(object_code=bytes(obj_code))
