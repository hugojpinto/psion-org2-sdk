"""
OPK Pack Builder
================

This module provides the PackBuilder class for creating OPK pack image files.

The PackBuilder allows you to create pack images by adding procedures,
data files, and other records, then serializing everything to the OPK
format that can be loaded into a Psion Organiser II or the JAPE emulator.

Usage
-----
Basic usage to create a pack from OB3 files:

    >>> from psion_sdk.opk import PackBuilder, PackType, PackSize
    >>> builder = PackBuilder(size_kb=16, pack_type=PackType.DATAPAK)
    >>> builder.add_ob3_file("hello.ob3")
    >>> builder.add_ob3_file("utils.ob3")
    >>> opk_data = builder.build()
    >>> Path("output.opk").write_bytes(opk_data)

Adding a procedure directly:

    >>> builder = PackBuilder()
    >>> builder.add_procedure("TEST", bytes([0x86, 0x41, 0x39]))  # LDAA #$41; RTS
    >>> opk_data = builder.build()

Features
--------
- Support for multiple procedures per pack
- Automatic checksum calculation
- Size validation to prevent overflow
- Multiple pack types (Datapak, Rampak, Flashpak)
- Multiple pack sizes (8K, 16K, 32K, 64K, 128K)

Reference
---------
- File format: https://www.jaapsch.net/psion/fileform.htm
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
import logging
import re

from psion_sdk.errors import OPKError, OPKFormatError, PackSizeError
from psion_sdk.opk.records import (
    PackHeader,
    PackRecord,
    ProcedureRecord,
    DataFileRecord,
    DataRecord,
    OB3File,
    RecordType,
    PackType,
    PackSize,
)
from psion_sdk.opk.checksum import (
    calculate_header_checksum,
    create_opk_header,
)
from psion_sdk.opk.parser import validate_ob3, parse_ob3

# Logger for this module
logger = logging.getLogger(__name__)


# =============================================================================
# Validation Helpers
# =============================================================================

# Valid procedure/file name pattern: 1-8 alphanumeric, starts with letter
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,7}$")


def validate_procedure_name(name: str) -> bool:
    """
    Validate a procedure name.

    Psion procedure names must:
    - Be 1-8 characters long
    - Start with a letter (A-Z)
    - Contain only alphanumeric characters (A-Z, 0-9)

    Args:
        name: The name to validate

    Returns:
        True if the name is valid
    """
    return bool(NAME_PATTERN.match(name))


def validate_pack_size(size_kb: int) -> bool:
    """
    Validate a pack size.

    Valid sizes are: 8, 16, 32, 64, 128 (in KB)

    Args:
        size_kb: Size in kilobytes

    Returns:
        True if the size is valid
    """
    try:
        PackSize(size_kb)
        return True
    except ValueError:
        return False


# =============================================================================
# Pack Builder
# =============================================================================

@dataclass
class PackBuilder:
    """
    Builds OPK pack image files.

    This class provides a fluent interface for creating pack images
    by adding procedures and other records, then building the final
    OPK file.

    Attributes:
        size_kb: Pack size in kilobytes (8, 16, 32, 64, or 128)
        pack_type: Type of pack (Datapak, Rampak, Flashpak)
        timestamp: Creation timestamp (defaults to now)

    Example:
        >>> builder = PackBuilder(size_kb=16)
        >>> builder.add_ob3_file("hello.ob3")
        >>> builder.add_procedure("TEST", bytes([0x01, 0x39]))
        >>> opk_data = builder.build()
        >>> Path("output.opk").write_bytes(opk_data)
    """
    # Pack size in kilobytes
    size_kb: int = 16

    # Pack type (default: Datapak for EPROM-like storage)
    pack_type: PackType = PackType.DATAPAK

    # Timestamp for the pack header
    timestamp: datetime = field(default_factory=datetime.now)

    # Internal list of records to include
    _records: list[PackRecord] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate parameters after initialization."""
        if not validate_pack_size(self.size_kb):
            raise PackSizeError(
                f"Invalid pack size: {self.size_kb}KB. "
                f"Valid sizes are: 8, 16, 32, 64, 128"
            )

    # =========================================================================
    # Adding Records
    # =========================================================================

    def add_procedure(
        self,
        name: str,
        object_code: bytes,
        source_code: bytes = b""
    ) -> "PackBuilder":
        """
        Add a procedure to the pack.

        Args:
            name: Procedure name (1-8 alphanumeric, starts with letter)
            object_code: The compiled/assembled machine code
            source_code: Optional source code (usually empty for machine code)

        Returns:
            Self for method chaining

        Raises:
            OPKError: If the name is invalid

        Example:
            >>> builder.add_procedure("HELLO", bytes([0x86, 0x41, 0x39]))
        """
        # Validate name
        name = name.upper()
        if not validate_procedure_name(name):
            raise OPKError(
                f"Invalid procedure name '{name}': must be 1-8 alphanumeric "
                f"characters starting with a letter"
            )

        # Normalize name to 8 chars for comparison
        name_padded = name[:8].ljust(8)

        # Check for duplicate names
        for record in self._records:
            if isinstance(record, ProcedureRecord) and record.name == name_padded:
                raise OPKError(f"Duplicate procedure name: {name}")

        # Create and add record
        record = ProcedureRecord(
            name=name,
            object_code=object_code,
            source_code=source_code
        )
        self._records.append(record)

        logger.debug(f"Added procedure '{name}' ({len(object_code)} bytes)")
        return self

    def add_ob3(self, ob3: OB3File, name: str) -> "PackBuilder":
        """
        Add a procedure from an OB3File object.

        Args:
            ob3: The OB3File instance to add
            name: Name for the procedure

        Returns:
            Self for method chaining

        Example:
            >>> ob3 = OB3File.from_bytes(data)
            >>> builder.add_ob3(ob3, "HELLO")
        """
        return self.add_procedure(name, ob3.object_code, ob3.source_code)

    def add_ob3_data(self, data: bytes, name: Optional[str] = None) -> "PackBuilder":
        """
        Add a procedure from raw OB3 file data.

        Args:
            data: The raw OB3 file bytes
            name: Optional name override (defaults to requiring a name)

        Returns:
            Self for method chaining

        Raises:
            OPKFormatError: If the data is not valid OB3 format
            OPKError: If name is not provided

        Example:
            >>> with open("hello.ob3", "rb") as f:
            ...     builder.add_ob3_data(f.read(), "HELLO")
        """
        if not validate_ob3(data):
            raise OPKFormatError("Invalid OB3 file data")

        if name is None:
            raise OPKError("Name must be provided when adding OB3 data")

        ob3 = parse_ob3(data)
        return self.add_procedure(name, ob3.object_code, ob3.source_code)

    def add_ob3_file(
        self,
        filepath: Union[str, Path],
        name: Optional[str] = None
    ) -> "PackBuilder":
        """
        Add a procedure from an OB3 file.

        The procedure name is derived from the filename if not provided.

        Args:
            filepath: Path to the OB3 file
            name: Optional name override (defaults to filename stem)

        Returns:
            Self for method chaining

        Raises:
            FileNotFoundError: If the file doesn't exist
            OPKFormatError: If the file is not valid OB3 format

        Example:
            >>> builder.add_ob3_file("hello.ob3")  # Name = "HELLO"
            >>> builder.add_ob3_file("mycode.ob3", "MAIN")  # Name = "MAIN"
        """
        filepath = Path(filepath)

        # Read file
        data = filepath.read_bytes()

        # Validate
        if not validate_ob3(data):
            raise OPKFormatError(f"Invalid OB3 file: {filepath}")

        # Derive name from filename if not provided
        if name is None:
            # Use filename stem, uppercase, truncated to 8 chars
            name = filepath.stem.upper()[:8]

        # Parse and add
        ob3 = parse_ob3(data)
        return self.add_procedure(name, ob3.object_code, ob3.source_code)

    def add_record(self, record: PackRecord) -> "PackBuilder":
        """
        Add a generic record to the pack.

        This method allows adding any type of PackRecord, including
        data files, diary entries, etc.

        Args:
            record: The record to add

        Returns:
            Self for method chaining

        Example:
            >>> record = DataFileRecord(name="MYDATA")
            >>> builder.add_record(record)
        """
        self._records.append(record)
        logger.debug(f"Added record type 0x{record.record_type:02X}")
        return self

    def clear(self) -> "PackBuilder":
        """
        Remove all records from the builder.

        Returns:
            Self for method chaining
        """
        self._records.clear()
        return self

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_record_count(self) -> int:
        """Get the number of records added."""
        return len(self._records)

    def get_procedure_count(self) -> int:
        """Get the number of procedure records."""
        return sum(1 for r in self._records if isinstance(r, ProcedureRecord))

    def get_used_bytes(self) -> int:
        """
        Calculate the total bytes that will be used.

        This includes the pack header, all records, and end marker.

        Returns:
            Total bytes used
        """
        # Pack header (10) + records + end marker (2)
        total = 10 + 2
        for record in self._records:
            total += record.get_size()
        return total

    def get_free_bytes(self) -> int:
        """
        Calculate the remaining free space.

        Returns:
            Bytes available for more records
        """
        pack_size = self.size_kb * 1024
        return max(0, pack_size - self.get_used_bytes())

    def can_fit(self, additional_bytes: int) -> bool:
        """
        Check if additional data will fit in the pack.

        Args:
            additional_bytes: Number of bytes to add

        Returns:
            True if there's enough space
        """
        return self.get_free_bytes() >= additional_bytes

    def list_procedures(self) -> list[str]:
        """
        List the names of all procedures added.

        Returns:
            List of procedure names (stripped of padding)
        """
        return [
            record.get_display_name()
            for record in self._records
            if isinstance(record, ProcedureRecord)
        ]

    # =========================================================================
    # Building
    # =========================================================================

    def build(self) -> bytes:
        """
        Build the complete OPK file.

        This method serializes all records, calculates the checksum,
        and produces the final OPK file bytes.

        Returns:
            Complete OPK file as bytes

        Raises:
            PackSizeError: If the data exceeds the pack size

        Example:
            >>> opk_data = builder.build()
            >>> Path("output.opk").write_bytes(opk_data)
        """
        # Build the pack data block first (for checksum calculation)
        pack_data = self._build_pack_data()

        # Build OPK header
        opk_header = create_opk_header(len(pack_data))

        # Combine header and pack data
        return opk_header + pack_data

    def build_to_file(self, filepath: Union[str, Path]) -> int:
        """
        Build and write the OPK file to disk.

        Args:
            filepath: Output file path

        Returns:
            Number of bytes written

        Example:
            >>> bytes_written = builder.build_to_file("output.opk")
            >>> print(f"Wrote {bytes_written} bytes")
        """
        filepath = Path(filepath)
        data = self.build()
        filepath.write_bytes(data)
        return len(data)

    def _build_pack_data(self) -> bytes:
        """
        Build the pack data block (header + records + terminator).

        Returns:
            The complete pack data block

        Raises:
            PackSizeError: If the data exceeds the pack size
        """
        # Serialize all records
        records_data = self._build_records_data()

        # Add end marker
        records_data_with_marker = records_data + b"\xFF\xFF"

        # Calculate checksum from header components
        # The Psion checksum is the sum of 16-bit words at offsets 0, 2, 4, 6
        # of the pack header (flags, size, timestamp, etc.)
        size_indicator = self.size_kb // 8
        year = self.timestamp.year % 100
        month = self.timestamp.month - 1  # 0-indexed
        day = self.timestamp.day - 1      # 0-indexed
        hour = self.timestamp.hour

        checksum = calculate_header_checksum(
            flags=self.pack_type,
            size_indicator=size_indicator,
            year=year,
            month=month,
            day=day,
            hour=hour,
            reserved=0,
            frame_counter=0
        )

        # Build header with calculated checksum
        header = PackHeader(
            flags=self.pack_type,
            size_kb=self.size_kb,
            timestamp=self.timestamp,
            checksum=checksum
        )

        # Combine header and records
        pack_data = header.to_bytes() + records_data_with_marker

        # Validate size
        max_size = self.size_kb * 1024
        if len(pack_data) > max_size:
            raise PackSizeError(
                f"Pack data ({len(pack_data)} bytes) exceeds "
                f"pack size ({max_size} bytes)"
            )

        logger.info(
            f"Built pack: {len(pack_data)} bytes used, "
            f"{max_size - len(pack_data)} bytes free"
        )

        return pack_data

    def _build_records_data(self) -> bytes:
        """
        Serialize all records to bytes.

        Returns:
            Concatenated record data
        """
        result = bytearray()

        # Add standard MAIN header (required for pack recognition)
        # This is what BLDPACK adds when no BOOT.BIN is provided.
        # Format: [length=9] [type=0x81] [name="MAIN    "] [data_type=0x90]
        # The 0x90 is the data record type marker for MAIN's (empty) data
        result.extend(self._build_main_header())

        for record in self._records:
            result.extend(record.to_bytes())
        return bytes(result)

    def _build_main_header(self) -> bytes:
        """
        Build the standard MAIN header stub.

        This minimal header is required for the pack to be recognized
        by the Psion OS. It's automatically added by the SDK's BLDPACK
        when no BOOT.BIN file is provided.

        Format:
            09      - Length (9 bytes follow)
            81      - Type (MAIN/file header)
            MAIN    - 8-byte padded name
            90      - Data record type marker

        Returns:
            The 11-byte MAIN header stub
        """
        header = bytearray()
        header.append(9)                    # Length: type(1) + name(8) = 9
        header.append(0x81)                 # Type: MAIN/data file header
        header.extend(b"MAIN    ")          # Name: "MAIN" padded to 8 bytes
        header.append(0x90)                 # Data record type marker
        return bytes(header)


# =============================================================================
# Convenience Functions
# =============================================================================

def create_opk(
    procedures: list[tuple[str, bytes]],
    size_kb: int = 16,
    pack_type: PackType = PackType.DATAPAK
) -> bytes:
    """
    Create an OPK file from a list of procedures.

    This is a convenience function for simple pack creation.

    Args:
        procedures: List of (name, object_code) tuples
        size_kb: Pack size in kilobytes
        pack_type: Type of pack

    Returns:
        Complete OPK file as bytes

    Example:
        >>> opk = create_opk([
        ...     ("HELLO", bytes([0x86, 0x41, 0x39])),
        ...     ("TEST", bytes([0x01, 0x39])),
        ... ])
    """
    builder = PackBuilder(size_kb=size_kb, pack_type=pack_type)
    for name, code in procedures:
        builder.add_procedure(name, code)
    return builder.build()


def create_opk_from_ob3(
    ob3_files: list[Union[str, Path]],
    output_path: Optional[Union[str, Path]] = None,
    size_kb: int = 16,
    pack_type: PackType = PackType.DATAPAK
) -> bytes:
    """
    Create an OPK file from a list of OB3 files.

    This is a convenience function that handles the common case of
    packaging multiple OB3 files into a single pack.

    Args:
        ob3_files: List of paths to OB3 files
        output_path: Optional output file path (if provided, writes to disk)
        size_kb: Pack size in kilobytes
        pack_type: Type of pack

    Returns:
        Complete OPK file as bytes

    Example:
        >>> opk = create_opk_from_ob3(["hello.ob3", "utils.ob3"], "tools.opk")
    """
    builder = PackBuilder(size_kb=size_kb, pack_type=pack_type)

    for ob3_path in ob3_files:
        builder.add_ob3_file(ob3_path)

    opk_data = builder.build()

    if output_path:
        Path(output_path).write_bytes(opk_data)

    return opk_data
