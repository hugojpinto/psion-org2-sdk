"""
OPK and OB3 File Parsers
========================

This module provides parsers for reading Psion pack files (OPK) and
object files (OB3).

PackParser
----------
The PackParser class reads OPK pack image files and extracts their
contents, including the pack header and all records. It can be used
to inspect pack contents or extract procedures for analysis.

OB3 Validation
--------------
The validate_ob3() function validates OB3 object files produced by
the assembler, ensuring they have the correct format before being
packaged into OPK files.

Usage Examples
--------------
Reading an OPK file:
    >>> from psion_sdk.opk import PackParser
    >>> parser = PackParser.from_file("mypack.opk")
    >>> print(f"Pack type: {parser.header.get_pack_type().get_description()}")
    >>> for proc in parser.list_procedures():
    ...     print(f"  Procedure: {proc}")

Extracting a procedure:
    >>> code = parser.extract_procedure("HELLO")
    >>> if code:
    ...     print(f"Object code: {code.hex()}")

Validating an OB3 file:
    >>> from psion_sdk.opk import validate_ob3
    >>> with open("hello.ob3", "rb") as f:
    ...     if validate_ob3(f.read()):
    ...         print("Valid OB3 file")

Reference
---------
- OPK format: https://www.jaapsch.net/psion/fileform.htm
- JAPE pack.js: jape/pack.js
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union, Iterator
import logging

from psion_sdk.errors import OPKError, OPKFormatError
from psion_sdk.opk.records import (
    PackHeader,
    PackRecord,
    ProcedureRecord,
    DataFileRecord,
    DiaryRecord,
    CommsRecord,
    SpreadsheetRecord,
    PagerRecord,
    NotepadRecord,
    DataRecord,
    GenericRecord,
    OB3File,
    RecordType,
    PackType,
    PackSize,
)
from psion_sdk.opk.checksum import (
    analyze_header_checksum,
    parse_opk_header,
    validate_opk_length,
)

# Logger for this module
logger = logging.getLogger(__name__)


# =============================================================================
# OB3 Validation
# =============================================================================

def validate_ob3(data: bytes) -> bool:
    """
    Validate an OB3 (ORG) file format.

    This function performs structural validation of an OB3 file,
    checking that it has the correct magic number, file type, and
    consistent length fields.

    Args:
        data: The raw bytes of the OB3 file

    Returns:
        True if the file is valid, False otherwise

    Example:
        >>> with open("hello.ob3", "rb") as f:
        ...     data = f.read()
        >>> if validate_ob3(data):
        ...     print("File is valid")
        ... else:
        ...     print("File is corrupt or not an OB3 file")
    """
    # Minimum size: magic(3) + len(2) + type(1) + objlen(2) = 8 bytes
    if len(data) < 8:
        logger.debug(f"OB3 validation failed: file too short ({len(data)} bytes)")
        return False

    # Check magic number "ORG"
    if data[0:3] != b"ORG":
        logger.debug(f"OB3 validation failed: invalid magic {data[0:3]!r}")
        return False

    # Check file type ($83 for procedures)
    file_type = data[5]
    if file_type != 0x83:
        logger.debug(f"OB3 validation failed: invalid file type 0x{file_type:02X}")
        return False

    # Get declared data length
    total_len = (data[3] << 8) | data[4]

    # Verify file is long enough for declared length
    if total_len + 5 > len(data):
        logger.debug(f"OB3 validation failed: truncated (declared {total_len + 5}, actual {len(data)})")
        return False

    # Get object code length
    obj_len = (data[6] << 8) | data[7]

    # Verify object code length is reasonable
    # total_len = type(1) + objlen(2) + object(n) + srclen(2) [+ source(m)]
    # So obj_len should be <= total_len - 3 (type + objlen word)
    if obj_len > total_len - 3:
        logger.debug(f"OB3 validation failed: object length {obj_len} > data length - 3")
        return False

    logger.debug(f"OB3 validation passed: {obj_len} bytes of object code")
    return True


def parse_ob3(data: bytes) -> OB3File:
    """
    Parse an OB3 file and return its contents.

    This function validates and parses an OB3 file, extracting the
    object code and optional source code.

    Args:
        data: The raw bytes of the OB3 file

    Returns:
        An OB3File instance with the parsed contents

    Raises:
        OPKFormatError: If the file is not a valid OB3 file

    Example:
        >>> with open("hello.ob3", "rb") as f:
        ...     ob3 = parse_ob3(f.read())
        >>> print(f"Object code: {len(ob3.object_code)} bytes")
    """
    if not validate_ob3(data):
        raise OPKFormatError("Invalid OB3 file format")

    return OB3File.from_bytes(data)


def parse_ob3_file(filepath: Union[str, Path]) -> OB3File:
    """
    Read and parse an OB3 file from disk.

    Args:
        filepath: Path to the OB3 file

    Returns:
        An OB3File instance with the parsed contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        OPKFormatError: If the file is not a valid OB3 file
    """
    filepath = Path(filepath)
    data = filepath.read_bytes()
    return parse_ob3(data)


# =============================================================================
# Pack Parser
# =============================================================================

@dataclass
class PackParser:
    """
    Parser for OPK pack image files.

    This class reads and parses OPK files, extracting the pack header
    and all contained records. It provides methods to list and extract
    procedures, data files, and other pack contents.

    Attributes:
        data: The raw OPK file bytes
        header: The parsed pack header
        records: List of parsed records

    Example:
        >>> parser = PackParser.from_file("mypack.opk")
        >>> print(f"Pack size: {parser.header.size_kb}KB")
        >>> for name in parser.list_procedures():
        ...     print(f"Procedure: {name}")
    """
    # Raw OPK file data (private, not exposed in repr)
    data: bytes = field(repr=False)

    # Parsed pack header
    header: Optional[PackHeader] = None

    # List of parsed records
    records: list[PackRecord] = field(default_factory=list)

    # Flag indicating if pack is valid
    is_valid: bool = False

    # Any error message from parsing
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        """Parse the pack data after initialization."""
        self._parse()

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "PackParser":
        """
        Create a PackParser from a file path.

        Args:
            filepath: Path to the OPK file

        Returns:
            A PackParser instance with parsed contents

        Raises:
            FileNotFoundError: If the file doesn't exist
            OPKFormatError: If the file cannot be parsed
        """
        filepath = Path(filepath)
        data = filepath.read_bytes()
        return cls(data=data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "PackParser":
        """
        Create a PackParser from raw bytes.

        Args:
            data: The raw OPK file bytes

        Returns:
            A PackParser instance with parsed contents
        """
        return cls(data=data)

    def _parse(self) -> None:
        """
        Parse the OPK file data.

        This method is called automatically during initialization.
        It validates the OPK header, parses the pack header, and
        extracts all records.
        """
        try:
            self._parse_opk_header()
            self._parse_pack_header()
            self._parse_records()
            self.is_valid = True
        except OPKError as e:
            self.is_valid = False
            self.error_message = str(e)
            logger.error(f"Failed to parse OPK: {e}")
            raise
        except Exception as e:
            self.is_valid = False
            self.error_message = str(e)
            logger.error(f"Unexpected error parsing OPK: {e}")
            raise OPKFormatError(f"Failed to parse OPK: {e}") from e

    def _parse_opk_header(self) -> None:
        """Parse and validate the 6-byte OPK header."""
        # Check minimum length
        if len(self.data) < 16:  # OPK header (6) + pack header (10)
            raise OPKFormatError(f"OPK file too small: {len(self.data)} bytes")

        # Parse OPK header
        is_valid, data_length = parse_opk_header(self.data)
        if not is_valid:
            raise OPKFormatError(
                f"Invalid OPK magic number: {self.data[0:3]!r}"
            )

        # Validate length
        if not validate_opk_length(len(self.data), data_length):
            # Log warning but continue - some tools create slightly non-standard files
            logger.warning(
                f"OPK length mismatch: declared {data_length}, file size {len(self.data)}"
            )

    def _parse_pack_header(self) -> None:
        """Parse the 10-byte pack header."""
        # Pack data starts at offset 6 (after OPK header)
        pack_data = self.data[6:]

        if len(pack_data) < 10:
            raise OPKFormatError("Pack header too short")

        self.header = PackHeader.from_bytes(pack_data[0:10])

        # Analyze checksum with protection bit detection
        analysis = analyze_header_checksum(pack_data[0:10])

        if analysis.is_valid:
            logger.debug("Pack header checksum valid")
        elif analysis.is_valid_with_protection:
            # Checksum would be valid if protection bits were set after calculation
            logger.info(
                f"Header checksum: {analysis.message} "
                f"(original flags: 0x{analysis.original_flags:02X})"
            )
        else:
            # Genuine mismatch or placeholder
            logger.debug(f"Header checksum: {analysis.message}")

    def _parse_records(self) -> None:
        """
        Parse all records in the pack.

        Psion record format: [length][type][data...]
        - Short records: length byte (0x01-0xFE) followed by type + data
        - Long records: 0x02 0x80 followed by 2-byte length word, then data
        - End marker: 0xFF 0xFF
        - Error correction: single 0xFF bytes (skipped)
        - Deleted records: type byte 0x01-0x7F (high bit clear)
        """
        self.records.clear()

        # Records start at offset 16 (6 OPK + 10 pack header)
        pack_data = self.data[6:]
        offset = 10  # Skip pack header

        while offset < len(pack_data) - 1:
            first_byte = pack_data[offset]

            # Check for end marker (FF FF)
            if first_byte == 0xFF:
                if offset + 1 < len(pack_data) and pack_data[offset + 1] == 0xFF:
                    logger.debug(f"End marker at offset {offset}")
                    break
                # Single FF is error correction byte - skip
                offset += 1
                continue

            # Determine record length and type
            if first_byte == 0x02 and offset + 1 < len(pack_data) and pack_data[offset + 1] == 0x80:
                # Long record format: [0x02][0x80][length word][type][data...]
                if offset + 4 >= len(pack_data):
                    logger.warning(f"Truncated long record at offset {offset}")
                    break
                record_length = (pack_data[offset + 2] << 8) | pack_data[offset + 3]
                record_type = pack_data[offset + 4]
                total_size = 4 + record_length  # 2 + 2 + data
            else:
                # Short record format: [length][type][data...]
                record_length = first_byte
                if record_length == 0:
                    # Zero-length record - skip
                    offset += 1
                    continue
                if offset + 1 >= len(pack_data):
                    logger.warning(f"Truncated record at offset {offset}")
                    break
                record_type = pack_data[offset + 1]
                total_size = 1 + record_length  # length byte + data (which includes type)

            # Parse record based on type
            try:
                record, size = self._parse_record(pack_data, offset, record_type)
                if record:
                    self.records.append(record)
                offset += size
            except Exception as e:
                logger.warning(f"Error parsing record type 0x{record_type:02X} at offset {offset}: {e}")
                # Skip to next record using calculated size
                offset += total_size

    def _parse_record(
        self, data: bytes, offset: int, record_type: int
    ) -> tuple[Optional[PackRecord], int]:
        """
        Parse a single record from the pack data.

        The record format is [length][type][data...] where offset points to
        the length byte. This method dispatches to the appropriate record
        class's from_bytes() method based on the record type.

        Args:
            data: The pack data bytes
            offset: Starting offset of the record (at the length byte)
            record_type: The record type byte (already extracted)

        Returns:
            Tuple of (record or None, bytes consumed)
        """
        # Procedure record (0x83)
        if record_type == RecordType.PROCEDURE:
            record, size = ProcedureRecord.from_bytes(data, offset)
            logger.debug(f"Parsed procedure '{record.get_display_name()}' ({len(record.object_code)} bytes)")
            return record, size

        # Data file header (0x81)
        elif record_type == RecordType.DATA_FILE:
            record, size = DataFileRecord.from_bytes(data, offset)
            logger.debug(f"Parsed data file '{record.get_display_name()}'")
            return record, size

        # Diary record (0x82)
        elif record_type == RecordType.DIARY:
            record, size = DiaryRecord.from_bytes(data, offset)
            logger.debug(f"Parsed diary '{record.get_display_name()}'")
            return record, size

        # Comms setup record (0x84)
        elif record_type == RecordType.COMMS:
            record, size = CommsRecord.from_bytes(data, offset)
            logger.debug(f"Parsed comms setup '{record.get_display_name()}'")
            return record, size

        # Spreadsheet record (0x85)
        elif record_type == RecordType.SPREADSHEET:
            record, size = SpreadsheetRecord.from_bytes(data, offset)
            logger.debug(f"Parsed spreadsheet '{record.get_display_name()}'")
            return record, size

        # Pager setup record (0x86)
        elif record_type == RecordType.PAGER:
            record, size = PagerRecord.from_bytes(data, offset)
            logger.debug(f"Parsed pager setup '{record.get_display_name()}'")
            return record, size

        # Notepad record (0x87)
        elif record_type == RecordType.NOTEPAD:
            record, size = NotepadRecord.from_bytes(data, offset)
            logger.debug(f"Parsed notepad '{record.get_display_name()}'")
            return record, size

        # Data records (0x90-0xFE) - individual records within data files
        elif RecordType.is_data_record(record_type):
            record, size = DataRecord.from_bytes(data, offset)
            logger.debug(f"Parsed data record type 0x{record_type:02X}")
            return record, size

        # Deleted records (0x01-0x7F) - high bit is cleared
        elif RecordType.is_deleted(record_type):
            # Calculate size and skip
            length_byte = data[offset]
            if length_byte == 0x02 and offset + 1 < len(data) and data[offset + 1] == 0x80:
                # Long deleted record
                record_length = (data[offset + 2] << 8) | data[offset + 3]
                size = 4 + record_length
            else:
                size = 1 + length_byte
            logger.debug(f"Skipping deleted record type 0x{record_type:02X}")
            return None, size

        # Unknown record type - parse as generic
        else:
            logger.warning(f"Unknown record type 0x{record_type:02X} at offset {offset}")
            # Calculate size to skip
            length_byte = data[offset]
            if length_byte == 0x02 and offset + 1 < len(data) and data[offset + 1] == 0x80:
                record_length = (data[offset + 2] << 8) | data[offset + 3]
                size = 4 + record_length
                record_data = bytes(data[offset + 5:offset + 4 + record_length])
            else:
                size = 1 + length_byte
                record_data = bytes(data[offset + 2:offset + 1 + length_byte])

            record = GenericRecord(record_type=record_type, data=record_data)
            return record, size

    # =========================================================================
    # Public Query Methods
    # =========================================================================

    def list_procedures(self) -> list[str]:
        """
        List all procedure names in the pack.

        Returns:
            List of procedure names (uppercase, stripped of padding)

        Example:
            >>> parser = PackParser.from_file("mypack.opk")
            >>> for name in parser.list_procedures():
            ...     print(f"  {name}")
        """
        return [
            record.get_display_name()
            for record in self.records
            if isinstance(record, ProcedureRecord)
        ]

    def list_data_files(self) -> list[str]:
        """
        List all data file names in the pack.

        Returns:
            List of data file names (uppercase, stripped of padding)
        """
        return [
            record.get_display_name()
            for record in self.records
            if isinstance(record, DataFileRecord)
        ]

    def get_procedure(self, name: str) -> Optional[ProcedureRecord]:
        """
        Get a procedure record by name.

        Args:
            name: Procedure name (case-insensitive)

        Returns:
            The ProcedureRecord if found, None otherwise
        """
        # Normalize the search name: uppercase, padded to 8 chars
        name = name.upper()[:8].ljust(8)
        for record in self.records:
            if isinstance(record, ProcedureRecord) and record.name == name:
                return record
        return None

    def extract_procedure(self, name: str) -> Optional[bytes]:
        """
        Extract the object code for a procedure by name.

        Args:
            name: Procedure name (case-insensitive)

        Returns:
            The object code bytes if found, None otherwise

        Example:
            >>> code = parser.extract_procedure("HELLO")
            >>> if code:
            ...     print(f"Code: {code.hex()}")
        """
        record = self.get_procedure(name)
        return record.object_code if record else None

    def iter_procedures(self) -> Iterator[ProcedureRecord]:
        """
        Iterate over all procedure records.

        Yields:
            ProcedureRecord instances
        """
        for record in self.records:
            if isinstance(record, ProcedureRecord):
                yield record

    def iter_data_files(self) -> Iterator[DataFileRecord]:
        """
        Iterate over all data file records.

        Yields:
            DataFileRecord instances
        """
        for record in self.records:
            if isinstance(record, DataFileRecord):
                yield record

    def get_used_bytes(self) -> int:
        """
        Calculate the total bytes used by records.

        Returns:
            Number of bytes used (excluding header and padding)
        """
        total = 0
        for record in self.records:
            total += record.get_size()
        return total

    def get_free_bytes(self) -> int:
        """
        Calculate the remaining free space in the pack.

        Returns:
            Number of free bytes available
        """
        if self.header is None:
            return 0

        pack_size = self.header.size_kb * 1024
        # Subtract: pack header (10) + used records + end marker (2)
        used = 10 + self.get_used_bytes() + 2
        return max(0, pack_size - used)

    def get_info(self) -> dict:
        """
        Get summary information about the pack.

        Returns:
            Dictionary with pack information
        """
        if self.header is None:
            return {"error": self.error_message or "Pack not parsed"}

        return {
            "pack_type": self.header.get_pack_type().get_description(),
            "size_kb": self.header.size_kb,
            "timestamp": self.header.timestamp.isoformat(),
            "checksum": f"0x{self.header.checksum:04X}",
            "procedure_count": len(self.list_procedures()),
            "data_file_count": len(self.list_data_files()),
            "total_records": len(self.records),
            "used_bytes": self.get_used_bytes(),
            "free_bytes": self.get_free_bytes(),
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_opk(data: bytes) -> PackParser:
    """
    Parse an OPK file from bytes.

    This is a convenience function that creates a PackParser.

    Args:
        data: The raw OPK file bytes

    Returns:
        A PackParser instance

    Raises:
        OPKFormatError: If the data is not a valid OPK file
    """
    return PackParser.from_bytes(data)


def parse_opk_file(filepath: Union[str, Path]) -> PackParser:
    """
    Parse an OPK file from disk.

    This is a convenience function that creates a PackParser from a file.

    Args:
        filepath: Path to the OPK file

    Returns:
        A PackParser instance

    Raises:
        FileNotFoundError: If the file doesn't exist
        OPKFormatError: If the file is not a valid OPK file
    """
    return PackParser.from_file(filepath)
