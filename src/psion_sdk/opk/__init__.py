"""
OPK File Handling for Psion Organiser II
=========================================

This module provides comprehensive support for working with Psion OPK
(pack image) files. OPK files are the standard format for distributing
and transferring programs and data to the Psion Organiser II.

Overview
--------
The OPK format encapsulates the complete contents of a Psion data pack
(cartridge). These files can be:
- Transferred to real hardware via the Comms Link
- Loaded into the JAPE emulator
- Archived for distribution

This module provides:
- **PackBuilder**: Create new OPK files from object code or OB3 files
- **PackParser**: Read and extract contents from existing OPK files
- **OB3File**: Work with individual object files
- **Record types**: Data structures for procedures, data files, etc.
- **Checksum utilities**: Validate and calculate pack checksums

Quick Start
-----------
Creating a pack from OB3 files:

    >>> from psion_sdk.opk import PackBuilder, PackType
    >>> builder = PackBuilder(size_kb=16, pack_type=PackType.DATAPAK)
    >>> builder.add_ob3_file("hello.ob3")
    >>> builder.add_ob3_file("utils.ob3")
    >>> opk_data = builder.build()

Reading an existing pack:

    >>> from psion_sdk.opk import PackParser
    >>> parser = PackParser.from_file("mypack.opk")
    >>> for name in parser.list_procedures():
    ...     print(f"Procedure: {name}")

Pack Types
----------
The module supports all standard Psion pack types:
- **RAMPAK**: Battery-backed RAM, read-write
- **DATAPAK**: EPROM-based, write-once
- **FLASHPAK**: Flash memory, electrically erasable

Pack Sizes
----------
Standard sizes supported: 8KB, 16KB, 32KB, 64KB, 128KB

File Formats
------------
- **OPK**: Pack image file (contains header + records)
- **OB3**: Object file produced by assembler (ORG format)

Reference
---------
- File format documentation: https://www.jaapsch.net/psion/fileform.htm
- Technical reference: https://www.jaapsch.net/psion/index.htm
"""

# =============================================================================
# Public API Exports
# =============================================================================

# Record type definitions and enums
from psion_sdk.opk.records import (
    # Enums
    PackType,
    RecordType,
    PackSize,
    # Data structures
    PackHeader,
    PackRecord,
    FileRecord,
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
)

# Checksum utilities
from psion_sdk.opk.checksum import (
    # Header checksum (bytes 8-9 of pack header)
    calculate_pack_checksum,
    calculate_header_checksum,
    verify_pack_checksum,
    analyze_header_checksum,
    ChecksumAnalysis,
    ProtectionBits,
    # Flashpak detection and constants
    is_flashpak,
    FLASHPAK_CHECKSUM_MASK,
    FLASHPAK_WRITE_PROTECT_BIT,
    # OPK header utilities
    create_opk_header,
    parse_opk_header,
    validate_opk_length,
)

# Parser classes and functions
from psion_sdk.opk.parser import (
    PackParser,
    validate_ob3,
    parse_ob3,
    parse_ob3_file,
    parse_opk,
    parse_opk_file,
)

# Builder classes and functions
from psion_sdk.opk.builder import (
    PackBuilder,
    validate_procedure_name,
    validate_pack_size,
    create_opk,
    create_opk_from_ob3,
)

# =============================================================================
# Module-level __all__ for explicit exports
# =============================================================================

__all__ = [
    # Enums
    "PackType",
    "RecordType",
    "PackSize",
    # Data structures
    "PackHeader",
    "PackRecord",
    "FileRecord",
    "ProcedureRecord",
    "DataFileRecord",
    "DiaryRecord",
    "CommsRecord",
    "SpreadsheetRecord",
    "PagerRecord",
    "NotepadRecord",
    "DataRecord",
    "GenericRecord",
    "OB3File",
    # Checksum utilities - header checksum
    "calculate_pack_checksum",
    "calculate_header_checksum",
    "verify_pack_checksum",
    "analyze_header_checksum",
    "ChecksumAnalysis",
    "ProtectionBits",
    # Flashpak detection and constants
    "is_flashpak",
    "FLASHPAK_CHECKSUM_MASK",
    "FLASHPAK_WRITE_PROTECT_BIT",
    # OPK header utilities
    "create_opk_header",
    "parse_opk_header",
    "validate_opk_length",
    # Parser
    "PackParser",
    "validate_ob3",
    "parse_ob3",
    "parse_ob3_file",
    "parse_opk",
    "parse_opk_file",
    # Builder
    "PackBuilder",
    "validate_procedure_name",
    "validate_pack_size",
    "create_opk",
    "create_opk_from_ob3",
]
