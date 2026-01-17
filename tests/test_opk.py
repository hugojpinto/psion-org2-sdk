"""
OPK Module Unit Tests
=====================

This module contains comprehensive tests for the OPK file handling functionality.

Test Categories
---------------
1. Records: Testing record type definitions and serialization
2. Checksum: Testing checksum calculation functions
3. OB3: Testing OB3 file parsing and validation
4. Parser: Testing OPK file parsing
5. Builder: Testing OPK file creation
6. Round-trip: Testing create/parse/verify cycles
"""

import pytest
from pathlib import Path
from datetime import datetime
import struct

# Import the modules we're testing
from psion_sdk.opk import (
    # Records
    PackType,
    RecordType,
    PackSize,
    PackHeader,
    ProcedureRecord,
    DataFileRecord,
    DataRecord,
    OB3File,
    # Checksum
    calculate_pack_checksum,
    calculate_header_checksum,
    verify_pack_checksum,
    create_opk_header,
    parse_opk_header,
    # Parser
    PackParser,
    validate_ob3,
    parse_ob3,
    # Builder
    PackBuilder,
    validate_procedure_name,
    validate_pack_size,
    create_opk,
)
from psion_sdk.errors import OPKError, OPKFormatError, PackSizeError


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_object_code() -> bytes:
    """
    Sample HD6303 object code for testing.

    This is a simple program that loads 'A' into register A and returns:
        LDAA #$41   ; Load 'A' (0x41) into accumulator A
        RTS         ; Return from subroutine

    Machine code: 86 41 39
    """
    return bytes([0x86, 0x41, 0x39])


@pytest.fixture
def sample_ob3_data(sample_object_code: bytes) -> bytes:
    """
    Create valid OB3 file data for testing.

    OB3 Format:
    - 3 bytes: "ORG" magic
    - 2 bytes: data length (big-endian)
    - 1 byte: file type ($83)
    - 2 bytes: code length (big-endian)
    - n bytes: object code
    - 2 bytes: source length (0)
    """
    code_len = len(sample_object_code)
    # data_len = type(1) + code_len_word(2) + code(n) + src_len_word(2)
    data_len = 1 + 2 + code_len + 2

    result = bytearray()
    result.extend(b"ORG")                           # Magic
    result.extend(struct.pack(">H", data_len))      # Data length
    result.append(0x83)                             # File type
    result.extend(struct.pack(">H", code_len))      # Code length
    result.extend(sample_object_code)               # Object code
    result.extend(struct.pack(">H", 0))             # Source length (0)

    return bytes(result)


@pytest.fixture
def sample_procedure_record(sample_object_code: bytes) -> ProcedureRecord:
    """Create a sample procedure record for testing."""
    return ProcedureRecord(
        name="HELLO",
        object_code=sample_object_code,
        source_code=b""
    )


@pytest.fixture
def sample_opk_data(sample_object_code: bytes) -> bytes:
    """
    Create valid OPK file data for testing.

    This creates a minimal valid OPK with one procedure.
    """
    builder = PackBuilder(size_kb=8)
    builder.add_procedure("TEST", sample_object_code)
    return builder.build()


# =============================================================================
# Pack Type Tests
# =============================================================================

class TestPackType:
    """Tests for PackType enum and methods."""

    def test_standard_types(self):
        """Test that standard pack types have correct values."""
        # Bit 6 = 0 means flash pack, bit 6 = 1 means other (datapak/rampak)
        # Bit 1 = EPROM/Flash (vs RAM)
        assert PackType.RAMPAK == 0x40           # bit 6 set (not flash)
        assert PackType.DATAPAK == 0x56          # matches official DOS SDK
        assert PackType.DATAPAK_PAGED == 0x46    # bit 6 + bit 2 + bit 1
        assert PackType.FLASHPAK == 0x02         # bit 6 clear (flash) + bit 1
        assert PackType.FLASHPAK_PAGED == 0x06   # bit 6 clear + bit 2 + bit 1
        assert PackType.MK1 == 0xFB

    def test_from_flags_direct_match(self):
        """Test from_flags with exact matches."""
        assert PackType.from_flags(0x40) == PackType.RAMPAK
        assert PackType.from_flags(0x56) == PackType.DATAPAK
        assert PackType.from_flags(0x02) == PackType.FLASHPAK
        assert PackType.from_flags(0xFB) == PackType.MK1

    def test_get_description(self):
        """Test that descriptions are human-readable."""
        desc = PackType.DATAPAK.get_description()
        assert "Datapak" in desc
        assert "EPROM" in desc


class TestPackSize:
    """Tests for PackSize enum and methods."""

    def test_standard_sizes(self):
        """Test that standard sizes are correct."""
        assert PackSize.SIZE_8K == 8
        assert PackSize.SIZE_16K == 16
        assert PackSize.SIZE_32K == 32
        assert PackSize.SIZE_64K == 64
        assert PackSize.SIZE_128K == 128

    def test_from_indicator(self):
        """Test converting size indicator byte to PackSize."""
        assert PackSize.from_indicator(1) == PackSize.SIZE_8K
        assert PackSize.from_indicator(2) == PackSize.SIZE_16K
        assert PackSize.from_indicator(4) == PackSize.SIZE_32K
        assert PackSize.from_indicator(8) == PackSize.SIZE_64K
        assert PackSize.from_indicator(16) == PackSize.SIZE_128K

    def test_from_indicator_invalid(self):
        """Test that invalid indicators raise ValueError."""
        with pytest.raises(ValueError):
            PackSize.from_indicator(3)  # 24KB is not valid

    def test_to_indicator(self):
        """Test converting PackSize to indicator byte."""
        assert PackSize.SIZE_8K.to_indicator() == 1
        assert PackSize.SIZE_16K.to_indicator() == 2
        assert PackSize.SIZE_128K.to_indicator() == 16

    def test_to_bytes(self):
        """Test converting PackSize to byte count."""
        assert PackSize.SIZE_8K.to_bytes() == 8192
        assert PackSize.SIZE_16K.to_bytes() == 16384
        assert PackSize.SIZE_128K.to_bytes() == 131072


# =============================================================================
# Pack Header Tests
# =============================================================================

class TestPackHeader:
    """Tests for PackHeader serialization and deserialization."""

    def test_to_bytes_length(self):
        """Test that header serializes to exactly 10 bytes."""
        header = PackHeader()
        data = header.to_bytes()
        assert len(data) == 10

    def test_to_bytes_flags(self):
        """Test that flags are serialized correctly."""
        header = PackHeader(flags=PackType.DATAPAK)
        data = header.to_bytes()
        assert data[0] == 0x56  # DATAPAK = 0x56 (matches official DOS SDK)

    def test_to_bytes_size(self):
        """Test that size indicator is serialized correctly."""
        header = PackHeader(size_kb=32)
        data = header.to_bytes()
        assert data[1] == 4  # 32 / 8 = 4

    def test_from_bytes_roundtrip(self):
        """Test that serialization round-trips correctly."""
        original = PackHeader(
            flags=PackType.DATAPAK,
            size_kb=16,
            timestamp=datetime(2024, 6, 15, 14, 30),
            checksum=0x1234
        )
        data = original.to_bytes()
        restored = PackHeader.from_bytes(data)

        assert restored.flags == original.flags
        assert restored.size_kb == original.size_kb
        assert restored.checksum == original.checksum

    def test_from_bytes_too_short(self):
        """Test that short data raises ValueError."""
        with pytest.raises(ValueError):
            PackHeader.from_bytes(bytes(5))


# =============================================================================
# Procedure Record Tests
# =============================================================================

class TestProcedureRecord:
    """Tests for ProcedureRecord serialization and deserialization."""

    def test_to_bytes_format(self, sample_object_code: bytes):
        """Test procedure record serialization format.

        Psion procedure format:
        1. File header: [length=9] [0x83] [name 8 bytes]
        2. Data block record: [length=2] [0x80] [blocklen 2 bytes]
        3. Raw block data: [obj_len 2] [obj_code] [src_len 2] [src_code]
        """
        record = ProcedureRecord(name="TEST", object_code=sample_object_code)
        data = record.to_bytes()

        # File header: [length=9] [type=0x83] [name 8 bytes] [trailing 0x00]
        # Length byte = type(1) + name(8) = 9
        assert data[0] == 9

        # Second byte is record type
        assert data[1] == RecordType.PROCEDURE

        # Name follows (8 bytes, space padded)
        assert data[2:10] == b"TEST    "

        # Trailing byte (like file_id for DATA_FILE)
        assert data[10] == 0x00

        # Data block record header at offset 11
        assert data[11] == 2  # Data block length byte
        assert data[12] == RecordType.LONG  # Type 0x80

        # Block length at offset 13-14
        block_len = (data[13] << 8) | data[14]

        # Code block starts at offset 15
        # Object code length (big-endian)
        obj_len = (data[15] << 8) | data[16]
        assert obj_len == len(sample_object_code)

    def test_name_uppercase(self):
        """Test that names are normalized to uppercase and padded to 8 chars."""
        record = ProcedureRecord(name="hello")
        # Names are stored uppercase and padded to 8 characters
        assert record.name == "HELLO   "
        # get_display_name() strips trailing spaces
        assert record.get_display_name() == "HELLO"

    def test_from_bytes_roundtrip(self, sample_object_code: bytes):
        """Test serialization round-trip."""
        original = ProcedureRecord(
            name="MYPROC",
            object_code=sample_object_code,
            source_code=b"some source"
        )
        data = original.to_bytes()
        restored, _ = ProcedureRecord.from_bytes(data)

        assert restored.name == original.name
        assert restored.object_code == original.object_code
        assert restored.source_code == original.source_code

    def test_validate_name_valid(self):
        """Test valid procedure names."""
        valid_names = ["A", "TEST", "HELLO123", "M1", "ABCDEFGH"]
        for name in valid_names:
            record = ProcedureRecord(name=name)
            assert record.validate_name(), f"'{name}' should be valid"

    def test_validate_name_invalid(self):
        """Test invalid procedure names.

        Note: Names are truncated to 8 chars in __post_init__, so "TOOLONGNAME"
        becomes "TOOLONGN" which is technically valid. Empty names and names
        starting with non-letters are invalid.
        """
        invalid_names = ["", "123", "TEST-", "_HELLO"]
        for name in invalid_names:
            record = ProcedureRecord(name=name)
            assert not record.validate_name(), f"'{name}' should be invalid"

    def test_name_truncation(self):
        """Test that long names are truncated to 8 characters."""
        record = ProcedureRecord(name="TOOLONGNAME")
        # Name is truncated to 8 chars and padded
        assert record.name == "TOOLONGN"
        assert record.get_display_name() == "TOOLONGN"


# =============================================================================
# OB3 File Tests
# =============================================================================

class TestOB3File:
    """Tests for OB3File class."""

    def test_to_bytes_format(self, sample_object_code: bytes):
        """Test OB3 file serialization format."""
        ob3 = OB3File(object_code=sample_object_code)
        data = ob3.to_bytes()

        # Check magic
        assert data[0:3] == b"ORG"

        # Check file type
        assert data[5] == 0x83

        # Check code length
        code_len = (data[6] << 8) | data[7]
        assert code_len == len(sample_object_code)

    def test_from_bytes_roundtrip(self, sample_object_code: bytes):
        """Test serialization round-trip."""
        original = OB3File(
            object_code=sample_object_code,
            source_code=b"test source"
        )
        data = original.to_bytes()
        restored = OB3File.from_bytes(data)

        assert restored.object_code == original.object_code
        assert restored.source_code == original.source_code

    def test_is_valid(self, sample_object_code: bytes):
        """Test validity check."""
        valid_ob3 = OB3File(object_code=sample_object_code)
        assert valid_ob3.is_valid()

        empty_ob3 = OB3File(object_code=b"")
        assert not empty_ob3.is_valid()


class TestValidateOB3:
    """Tests for OB3 validation function."""

    def test_valid_ob3(self, sample_ob3_data: bytes):
        """Test validation of valid OB3 data."""
        assert validate_ob3(sample_ob3_data)

    def test_too_short(self):
        """Test rejection of truncated data."""
        assert not validate_ob3(b"ORG\x00")

    def test_wrong_magic(self):
        """Test rejection of wrong magic number."""
        assert not validate_ob3(b"OPK\x00\x05\x83\x00\x03ABC")

    def test_wrong_type(self, sample_object_code: bytes):
        """Test rejection of wrong file type."""
        bad_data = bytearray(b"ORG\x00\x05")
        bad_data.append(0x81)  # Wrong type (should be 0x83)
        bad_data.extend(struct.pack(">H", len(sample_object_code)))
        bad_data.extend(sample_object_code)
        bad_data.extend(b"\x00\x00")
        assert not validate_ob3(bytes(bad_data))


# =============================================================================
# Checksum Tests
# =============================================================================

class TestChecksum:
    """Tests for checksum calculation functions.

    The Psion pack checksum is the sum of 16-bit big-endian words at
    offsets 0, 2, 4, 6 of the pack header.
    """

    def test_pack_checksum_basic(self):
        """Test basic pack header checksum calculation."""
        # Pack header: flags=0x4A, size=0x02, year=0, month=0, day=0x20, hour=0, reserved=0, frame=0
        header = bytes([0x4A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00])
        # Word 0: 0x4A02, Word 2: 0x0000, Word 4: 0x2000, Word 6: 0x0000
        # Sum = 0x4A02 + 0x0000 + 0x2000 + 0x0000 = 0x6A02
        assert calculate_pack_checksum(header) == 0x6A02

    def test_pack_checksum_all_zeros(self):
        """Test checksum of all-zero header."""
        header = bytes([0x00] * 8)
        assert calculate_pack_checksum(header) == 0x0000

    def test_pack_checksum_wraps_at_16_bits(self):
        """Test that checksum wraps at 16 bits."""
        # Create header that will overflow
        header = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        # 4 words of 0xFFFF = 4 * 65535 = 262140 = 0x3FFFC -> wraps to 0xFFFC
        checksum = calculate_pack_checksum(header)
        assert checksum == 0xFFFC

    def test_header_checksum_helper(self):
        """Test the helper function for calculating checksum from components."""
        checksum = calculate_header_checksum(
            flags=0x4A,
            size_indicator=0x02,
            year=0,
            month=0,
            day=0x20,
            hour=0,
            reserved=0,
            frame_counter=0
        )
        assert checksum == 0x6A02

    def test_verify_pack_checksum_valid(self):
        """Test verification of valid checksum."""
        # Header with correct checksum at bytes 8-9
        header = bytes([0x4A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x6A, 0x02])
        assert verify_pack_checksum(header)

    def test_verify_pack_checksum_invalid(self):
        """Test verification of invalid checksum."""
        # Header with wrong checksum
        header = bytes([0x4A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0xFF, 0xFF])
        assert not verify_pack_checksum(header)


class TestChecksumAnalysis:
    """Tests for analyze_header_checksum with protection bit detection."""

    def test_analyze_valid_checksum(self):
        """Test analysis of valid checksum."""
        from psion_sdk.opk import analyze_header_checksum
        header = bytes([0x4A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x6A, 0x02])
        analysis = analyze_header_checksum(header)

        assert analysis.is_valid
        assert analysis.stored_checksum == 0x6A02
        assert analysis.calculated_checksum == 0x6A02
        assert not analysis.is_valid_with_protection
        assert "valid" in analysis.message.lower()

    def test_analyze_write_protect_added(self):
        """Test detection of write-protect bit (0x08) added after checksum.

        Uses Datapak (0x02) flags to avoid Flashpak special handling.
        """
        from psion_sdk.opk import analyze_header_checksum
        # Original flags: 0x02 (Datapak), checksum calculated, then 0x08 added -> 0x0A
        # Word 0 changes from 0x0202 to 0x0A02, diff = 0x0800
        original_checksum = (0x0202 + 0x0000 + 0x2000 + 0x0000) & 0xFFFF  # 0x2202
        header = bytes([0x0A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00,
                       (original_checksum >> 8) & 0xFF, original_checksum & 0xFF])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert analysis.is_valid_with_protection
        assert analysis.protection_bits_added == 0x08
        assert analysis.original_flags == 0x02
        assert "write-protect" in analysis.message.lower()

    def test_analyze_copy_protect_added(self):
        """Test detection of copy-protect bit (0x20) added after checksum.

        Uses Datapak (0x02) flags to avoid Flashpak special handling.
        """
        from psion_sdk.opk import analyze_header_checksum
        # Original flags: 0x02 (Datapak), checksum calculated, then 0x20 added -> 0x22
        original_checksum = (0x0202 + 0x0000 + 0x2000 + 0x0000) & 0xFFFF  # 0x2202
        header = bytes([0x22, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00,
                       (original_checksum >> 8) & 0xFF, original_checksum & 0xFF])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert analysis.is_valid_with_protection
        assert analysis.protection_bits_added == 0x20
        assert analysis.original_flags == 0x02
        assert "copy-protect" in analysis.message.lower()

    def test_analyze_ffff_placeholder(self):
        """Test detection of 0xFFFF placeholder checksum.

        Uses Datapak (0x02) flags to avoid Flashpak special handling.
        """
        from psion_sdk.opk import analyze_header_checksum
        header = bytes([0x02, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0xFF, 0xFF])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert not analysis.is_valid_with_protection
        assert analysis.stored_checksum == 0xFFFF
        assert "placeholder" in analysis.message.lower()

    def test_analyze_genuine_mismatch(self):
        """Test detection of genuine checksum mismatch.

        Uses Datapak (0x02) flags to avoid Flashpak special handling.
        """
        from psion_sdk.opk import analyze_header_checksum
        header = bytes([0x02, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x12, 0x34])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert not analysis.is_valid_with_protection
        assert analysis.stored_checksum == 0x1234
        assert "mismatch" in analysis.message.lower()


class TestFlashpakChecksum:
    """Tests for Flashpak-specific checksum handling.

    Flashpaks use the high bit (0x8000) of the checksum word for write-protection
    status (normally set, cleared for write-protection), not as part of the checksum.
    """

    def test_is_flashpak(self):
        """Test Flashpak detection."""
        from psion_sdk.opk import is_flashpak
        assert is_flashpak(0x42)  # FLASHPAK
        assert is_flashpak(0x46)  # FLASHPAK_PAGED
        assert is_flashpak(0x4A)  # FLASHPAK with protection bits
        assert not is_flashpak(0x00)  # RAMPAK
        assert not is_flashpak(0x02)  # DATAPAK
        assert not is_flashpak(0x06)  # DATAPAK_PAGED

    def test_flashpak_checksum_valid_no_wp(self):
        """Test Flashpak with valid checksum, not write-protected (bit 15 set)."""
        from psion_sdk.opk import analyze_header_checksum
        # Flashpak flags=0x42, size=0x02
        # Checksum of words: 0x4202 + 0x0000 + 0x2000 + 0x0000 = 0x6202
        # With bit 15 set (not write-protected): 0x6202 | 0x8000 = 0xE202
        header = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0xE2, 0x02])
        analysis = analyze_header_checksum(header)

        assert analysis.is_valid
        assert analysis.is_flashpak
        assert not analysis.flashpak_write_protected
        assert "flashpak" in analysis.message.lower()

    def test_flashpak_checksum_valid_wp(self):
        """Test Flashpak with valid checksum, write-protected (bit 15 cleared)."""
        from psion_sdk.opk import analyze_header_checksum
        # Same as above but with bit 15 cleared (write-protected): 0x6202
        header = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x62, 0x02])
        analysis = analyze_header_checksum(header)

        assert analysis.is_valid
        assert analysis.is_flashpak
        assert analysis.flashpak_write_protected
        assert "write-protected" in analysis.message.lower()

    def test_flashpak_checksum_ignores_high_bit(self):
        """Test that Flashpak comparison ignores bit 15."""
        from psion_sdk.opk import analyze_header_checksum
        # Both should be valid - only differ in bit 15
        header_no_wp = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0xE2, 0x02])
        header_wp = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x62, 0x02])

        analysis_no_wp = analyze_header_checksum(header_no_wp)
        analysis_wp = analyze_header_checksum(header_wp)

        assert analysis_no_wp.is_valid
        assert analysis_wp.is_valid
        assert not analysis_no_wp.flashpak_write_protected
        assert analysis_wp.flashpak_write_protected

    def test_flashpak_checksum_mismatch(self):
        """Test Flashpak with genuine checksum mismatch."""
        from psion_sdk.opk import analyze_header_checksum
        # Wrong checksum (0x1234 in lower 15 bits doesn't match 0x6202)
        header = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x12, 0x34])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert analysis.is_flashpak
        assert "mismatch" in analysis.message.lower()
        assert "15-bit" in analysis.message.lower()

    def test_flashpak_placeholder(self):
        """Test Flashpak with 0xFFFF placeholder."""
        from psion_sdk.opk import analyze_header_checksum
        header = bytes([0x42, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0xFF, 0xFF])
        analysis = analyze_header_checksum(header)

        assert not analysis.is_valid
        assert analysis.is_flashpak
        assert "placeholder" in analysis.message.lower()


class TestOPKHeader:
    """Tests for OPK header functions."""

    def test_create_opk_header(self):
        """Test OPK header creation."""
        header = create_opk_header(256)
        assert header[0:3] == b"OPK"
        assert len(header) == 6

        # Verify length encoding
        length = (header[3] << 16) | (header[4] << 8) | header[5]
        assert length == 256

    def test_parse_opk_header_valid(self):
        """Test parsing valid OPK header."""
        header = b"OPK\x00\x01\x00" + b"\x00" * 10
        valid, length = parse_opk_header(header)
        assert valid
        assert length == 256

    def test_parse_opk_header_invalid(self):
        """Test parsing invalid OPK header."""
        valid, _ = parse_opk_header(b"OPL\x00\x00\x00")
        assert not valid


# =============================================================================
# Pack Parser Tests
# =============================================================================

class TestPackParser:
    """Tests for PackParser class."""

    def test_parse_valid_opk(self, sample_opk_data: bytes):
        """Test parsing a valid OPK file."""
        parser = PackParser.from_bytes(sample_opk_data)

        assert parser.is_valid
        assert parser.header is not None
        assert len(parser.records) > 0

    def test_list_procedures(self, sample_opk_data: bytes):
        """Test listing procedures in a pack."""
        parser = PackParser.from_bytes(sample_opk_data)
        procedures = parser.list_procedures()

        assert "TEST" in procedures

    def test_extract_procedure(self, sample_opk_data: bytes, sample_object_code: bytes):
        """Test extracting a procedure by name."""
        parser = PackParser.from_bytes(sample_opk_data)
        code = parser.extract_procedure("TEST")

        assert code == sample_object_code

    def test_extract_nonexistent(self, sample_opk_data: bytes):
        """Test extracting a nonexistent procedure."""
        parser = PackParser.from_bytes(sample_opk_data)
        code = parser.extract_procedure("NOTHERE")

        assert code is None

    def test_get_info(self, sample_opk_data: bytes):
        """Test getting pack information."""
        parser = PackParser.from_bytes(sample_opk_data)
        info = parser.get_info()

        assert "pack_type" in info
        assert "size_kb" in info
        assert "procedure_count" in info
        assert info["procedure_count"] >= 1

    def test_invalid_magic(self):
        """Test rejection of invalid magic number."""
        bad_data = b"OPL" + b"\x00" * 20
        with pytest.raises(OPKFormatError):
            PackParser.from_bytes(bad_data)

    def test_too_short(self):
        """Test rejection of truncated file."""
        with pytest.raises(OPKFormatError):
            PackParser.from_bytes(b"OPK")


# =============================================================================
# Pack Builder Tests
# =============================================================================

class TestPackBuilder:
    """Tests for PackBuilder class."""

    def test_create_empty(self):
        """Test creating an empty builder."""
        builder = PackBuilder(size_kb=8)
        assert builder.get_record_count() == 0
        assert builder.get_procedure_count() == 0

    def test_add_procedure(self, sample_object_code: bytes):
        """Test adding a procedure."""
        builder = PackBuilder()
        builder.add_procedure("TEST", sample_object_code)

        assert builder.get_procedure_count() == 1
        assert "TEST" in builder.list_procedures()

    def test_add_procedure_chaining(self, sample_object_code: bytes):
        """Test method chaining."""
        builder = PackBuilder()
        result = builder.add_procedure("A", sample_object_code)

        assert result is builder  # Returns self for chaining

    def test_add_duplicate_name(self, sample_object_code: bytes):
        """Test rejection of duplicate procedure names."""
        builder = PackBuilder()
        builder.add_procedure("TEST", sample_object_code)

        with pytest.raises(OPKError):
            builder.add_procedure("TEST", sample_object_code)

    def test_invalid_name(self, sample_object_code: bytes):
        """Test rejection of invalid procedure names."""
        builder = PackBuilder()

        with pytest.raises(OPKError):
            builder.add_procedure("123BAD", sample_object_code)

    def test_build_creates_valid_opk(self, sample_object_code: bytes):
        """Test that build() creates valid OPK data."""
        builder = PackBuilder(size_kb=8)
        builder.add_procedure("TEST", sample_object_code)
        opk_data = builder.build()

        # Should start with OPK magic
        assert opk_data[0:3] == b"OPK"

        # Should be parseable
        parser = PackParser.from_bytes(opk_data)
        assert parser.is_valid
        assert "TEST" in parser.list_procedures()

    def test_space_tracking(self, sample_object_code: bytes):
        """Test used/free space tracking."""
        builder = PackBuilder(size_kb=8)
        initial_free = builder.get_free_bytes()

        builder.add_procedure("TEST", sample_object_code)

        assert builder.get_used_bytes() > 0
        assert builder.get_free_bytes() < initial_free

    def test_invalid_pack_size(self):
        """Test rejection of invalid pack sizes."""
        with pytest.raises(PackSizeError):
            PackBuilder(size_kb=24)  # Not a valid size

    def test_pack_overflow(self):
        """Test rejection of data that exceeds pack size."""
        builder = PackBuilder(size_kb=8)

        # Try to add data that's way too large
        huge_code = bytes([0x00] * 10000)
        builder.add_procedure("HUGE", huge_code)

        with pytest.raises(PackSizeError):
            builder.build()


class TestValidateProcedureName:
    """Tests for procedure name validation."""

    def test_valid_names(self):
        """Test that valid names pass validation."""
        valid = ["A", "TEST", "PROC1", "ABCDEFGH", "M123"]
        for name in valid:
            assert validate_procedure_name(name), f"'{name}' should be valid"

    def test_invalid_names(self):
        """Test that invalid names fail validation."""
        invalid = ["", "1", "123", "TOOLONGNAME", "A-B", "_A", "A.B"]
        for name in invalid:
            assert not validate_procedure_name(name), f"'{name}' should be invalid"


class TestValidatePackSize:
    """Tests for pack size validation."""

    def test_valid_sizes(self):
        """Test that standard sizes are valid."""
        for size in [8, 16, 32, 64, 128]:
            assert validate_pack_size(size), f"{size}KB should be valid"

    def test_invalid_sizes(self):
        """Test that non-standard sizes are invalid."""
        for size in [0, 4, 12, 24, 48, 100, 256]:
            assert not validate_pack_size(size), f"{size}KB should be invalid"


# =============================================================================
# Round-Trip Tests
# =============================================================================

class TestRoundTrip:
    """Tests for complete create/parse/verify cycles."""

    def test_single_procedure_roundtrip(self, sample_object_code: bytes):
        """Test round-trip with single procedure."""
        # Create
        builder = PackBuilder(size_kb=8)
        builder.add_procedure("HELLO", sample_object_code)
        opk_data = builder.build()

        # Parse
        parser = PackParser.from_bytes(opk_data)

        # Verify
        assert parser.is_valid
        extracted = parser.extract_procedure("HELLO")
        assert extracted == sample_object_code

    def test_multiple_procedures_roundtrip(self, sample_object_code: bytes):
        """Test round-trip with multiple procedures."""
        # Create with multiple procedures
        builder = PackBuilder(size_kb=16)
        builder.add_procedure("PROC1", sample_object_code)
        builder.add_procedure("PROC2", bytes([0x01, 0x39]))  # NOP; RTS
        builder.add_procedure("PROC3", bytes([0x4F, 0x39]))  # CLRA; RTS
        opk_data = builder.build()

        # Parse
        parser = PackParser.from_bytes(opk_data)

        # Verify all procedures
        assert parser.is_valid
        assert len(parser.list_procedures()) == 3
        assert parser.extract_procedure("PROC1") == sample_object_code
        assert parser.extract_procedure("PROC2") == bytes([0x01, 0x39])
        assert parser.extract_procedure("PROC3") == bytes([0x4F, 0x39])

    def test_checksum_verification(self, sample_object_code: bytes):
        """Test that checksums are calculated and verified correctly.

        The Psion checksum is the sum of 16-bit big-endian words at
        offsets 0, 2, 4, 6 of the pack header.
        """
        builder = PackBuilder(size_kb=8)
        builder.add_procedure("TEST", sample_object_code)
        opk_data = builder.build()

        parser = PackParser.from_bytes(opk_data)

        # Calculate checksum manually from pack header
        pack_header = opk_data[6:16]  # Pack header is at offset 6-15
        calculated = calculate_pack_checksum(pack_header)

        assert parser.header.checksum == calculated
        assert verify_pack_checksum(pack_header)


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_opk(self, sample_object_code: bytes):
        """Test create_opk convenience function."""
        opk_data = create_opk([
            ("TEST", sample_object_code),
            ("OTHER", bytes([0x39]))
        ])

        parser = PackParser.from_bytes(opk_data)
        assert parser.is_valid
        assert "TEST" in parser.list_procedures()
        assert "OTHER" in parser.list_procedures()
