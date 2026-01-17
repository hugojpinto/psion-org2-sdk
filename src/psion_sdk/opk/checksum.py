"""
OPK Checksum Calculations
=========================

This module provides checksum calculation functions for Psion pack files.

Pack Header Checksum
--------------------
The pack header checksum (bytes 8-9 of pack header) is calculated as:
- Algorithm: Sum of 16-bit big-endian words at offsets 0, 2, 4, 6
- Purpose: Header integrity verification
- Note: The Organiser never validates this because copy/write protection
  bits are often set AFTER the checksum is calculated

Flashpak Special Case
---------------------
For Flashpaks, the high bit (0x8000) of the checksum word is used for
write-protection status (normally set, cleared for write-protection).
Only the lower 15 bits are compared for checksum validation.

Copy Protection Bits
--------------------
The flags byte (offset 0) contains protection bits that are often modified
after the header checksum is calculated:
- Bit 3 (0x08): Write protection
- Bit 5 (0x20): Copy protection
- Other bits may also be modified

This causes many valid packs to have "incorrect" header checksums. The
`analyze_header_checksum()` function can detect this situation.

Reference
---------
- File format documentation: https://www.jaapsch.net/psion/fileform.htm
"""

from dataclasses import dataclass
from enum import IntFlag


class ProtectionBits(IntFlag):
    """
    Known protection bits in the pack flags byte.

    These bits are often set AFTER the header checksum is calculated,
    causing checksum mismatches in otherwise valid packs.
    """
    WRITE_PROTECT = 0x08   # Bit 3: Write protection
    COPY_PROTECT = 0x20    # Bit 5: Copy protection
    # Combined mask of all known protection bits
    ALL_PROTECTION = WRITE_PROTECT | COPY_PROTECT


# Flashpak detection mask and value
# Flashpaks have bit 6 (0x40) set and bit 1 (0x02) set = 0x42
FLASHPAK_MASK = 0x42
FLASHPAK_VALUE = 0x42

# For Flashpaks, bit 15 of checksum word is used for write-protection
# (normally set, cleared for write-protection) - not part of checksum
FLASHPAK_CHECKSUM_MASK = 0x7FFF  # Lower 15 bits only
FLASHPAK_WRITE_PROTECT_BIT = 0x8000  # High bit of checksum word


@dataclass
class ChecksumAnalysis:
    """
    Result of analyzing a pack header checksum.

    Attributes:
        is_valid: True if checksum matches exactly
        stored_checksum: The checksum value stored in the header
        calculated_checksum: The checksum calculated from header bytes
        is_valid_with_protection: True if checksum would match if protection
            bits were cleared (indicating bits were set after calculation)
        protection_bits_added: Which protection bits appear to have been
            added after checksum calculation (0 if none or unknown)
        original_flags: The likely original flags value before protection
            bits were added (only set if protection_bits_added > 0)
        is_flashpak: True if pack is a Flashpak (uses different checksum scheme)
        flashpak_write_protected: For Flashpaks, True if write-protected
            (bit 15 of checksum word is cleared)
        message: Human-readable explanation of the analysis
    """
    is_valid: bool
    stored_checksum: int
    calculated_checksum: int
    is_valid_with_protection: bool = False
    protection_bits_added: int = 0
    original_flags: int = 0
    is_flashpak: bool = False
    flashpak_write_protected: bool = False
    message: str = ""


def is_flashpak(flags: int) -> bool:
    """
    Check if a pack is a Flashpak based on its flags byte.

    Flashpaks are identified by having both bit 6 (0x40) and bit 1 (0x02) set.
    This gives the base pattern 0x42.

    Args:
        flags: The flags byte (offset 0 of pack header)

    Returns:
        True if the pack is a Flashpak, False otherwise

    Example:
        >>> is_flashpak(0x42)  # FLASHPAK
        True
        >>> is_flashpak(0x46)  # FLASHPAK_PAGED
        True
        >>> is_flashpak(0x02)  # DATAPAK
        False
    """
    return (flags & FLASHPAK_MASK) == FLASHPAK_VALUE


def calculate_pack_checksum(pack_header: bytes) -> int:
    """
    Calculate the pack header checksum.

    The Psion pack checksum is simply the sum of the 16-bit big-endian
    words at offsets 0, 2, 4, and 6 of the pack header.

    From the file format documentation:
    "This word is the sum of the words at pack address 0, 2, 4, and 6."

    Note: The Organiser never actually validates this checksum because
    copy/write protection flags may be modified after the checksum is
    calculated.

    **Flashpak special case**: For Flashpaks, the high bit (0x8000) of the
    checksum word is used for write-protection status (normally set, cleared
    for write-protection). When comparing checksums on Flashpaks, only the
    lower 15 bits should be compared.

    Args:
        pack_header: The 10-byte pack header (or at least first 8 bytes)

    Returns:
        16-bit checksum value (0x0000 - 0xFFFF)

    Example:
        >>> header = bytes([0x4A, 0x02, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00])
        >>> checksum = calculate_pack_checksum(header)
        >>> print(f"Checksum: 0x{checksum:04X}")  # 0x6A02
    """
    if len(pack_header) < 8:
        raise ValueError(f"Pack header too short: need at least 8 bytes, got {len(pack_header)}")

    # Sum of 16-bit big-endian words at offsets 0, 2, 4, 6
    word0 = (pack_header[0] << 8) | pack_header[1]
    word2 = (pack_header[2] << 8) | pack_header[3]
    word4 = (pack_header[4] << 8) | pack_header[5]
    word6 = (pack_header[6] << 8) | pack_header[7]

    return (word0 + word2 + word4 + word6) & 0xFFFF


def calculate_header_checksum(
    flags: int,
    size_indicator: int,
    year: int = 0,
    month: int = 0,
    day: int = 0,
    hour: int = 0,
    reserved: int = 0,
    frame_counter: int = 0
) -> int:
    """
    Calculate the checksum for a pack header given its components.

    This builds the header words and calculates the checksum before
    the header is fully assembled.

    Args:
        flags: Pack type flags byte
        size_indicator: Size in 8KB units
        year: Year (0-255)
        month: Month (0-11)
        day: Day (0-30)
        hour: Hour (0-23)
        reserved: Reserved byte
        frame_counter: Frame counter byte

    Returns:
        16-bit checksum value
    """
    # Build header bytes (first 8 bytes)
    header = bytes([
        flags, size_indicator,
        year, month,
        day, hour,
        reserved, frame_counter
    ])
    return calculate_pack_checksum(header)


def verify_pack_checksum(pack_header: bytes) -> bool:
    """
    Verify a pack header's checksum.

    Note: Many valid packs have incorrect checksums because:
    1. The Organiser never validates this checksum
    2. Copy protection bits may be modified after checksum calculation
    3. Some tools use 0xFFFF as a placeholder

    Args:
        pack_header: The 10-byte pack header

    Returns:
        True if the checksum matches, False otherwise

    Example:
        >>> is_valid = verify_pack_checksum(pack_header_bytes)
    """
    if len(pack_header) < 10:
        return False

    stored_checksum = (pack_header[8] << 8) | pack_header[9]
    calculated = calculate_pack_checksum(pack_header)
    return calculated == stored_checksum


def calculate_ob3_checksum(object_code: bytes) -> int:
    """
    Calculate a simple checksum for OB3 object code.

    Note: OB3 files don't have a built-in checksum field, but this
    function can be useful for integrity verification.

    Args:
        object_code: The object code bytes

    Returns:
        16-bit checksum value
    """
    checksum = 0
    for byte in object_code:
        checksum = (checksum + byte) & 0xFFFF
    return checksum


def calculate_opk_data_length(pack_data: bytes, include_terminator: bool = True) -> int:
    """
    Calculate the data length field for an OPK file.

    The OPK format stores a 24-bit data length in bytes 3-5. Different
    tools calculate this differently:

    - BLDPACK style (include_terminator=True): Length includes FF FF
    - UNMAKE style (include_terminator=False): Length excludes FF FF

    Args:
        pack_data: The complete pack data block (header + records + terminator)
        include_terminator: Whether to include the FF FF terminator in length

    Returns:
        Data length value for the OPK header
    """
    length = len(pack_data)
    if not include_terminator:
        # Subtract 2 for FF FF if present
        if length >= 2 and pack_data[-2:] == b"\xFF\xFF":
            length -= 2
    return length


def pack_24bit_length(length: int) -> bytes:
    """
    Pack a 24-bit length value into 3 bytes (big-endian).

    Args:
        length: The length value (0 to 16777215)

    Returns:
        3-byte big-endian representation

    Raises:
        ValueError: If length is negative or > 24 bits
    """
    if length < 0:
        raise ValueError(f"Length cannot be negative: {length}")
    if length > 0xFFFFFF:
        raise ValueError(f"Length exceeds 24 bits: {length}")

    return bytes([
        (length >> 16) & 0xFF,
        (length >> 8) & 0xFF,
        length & 0xFF
    ])


def unpack_24bit_length(data: bytes) -> int:
    """
    Unpack a 24-bit length value from 3 bytes (big-endian).

    Args:
        data: 3 bytes in big-endian order

    Returns:
        The unpacked length value

    Raises:
        ValueError: If data is not exactly 3 bytes
    """
    if len(data) != 3:
        raise ValueError(f"Expected 3 bytes, got {len(data)}")

    return (data[0] << 16) | (data[1] << 8) | data[2]


def create_opk_header(data_length: int) -> bytes:
    """
    Create the 6-byte OPK file header.

    The OPK header consists of:
    - 3 bytes: Magic "OPK"
    - 3 bytes: Data length (24-bit big-endian)

    Args:
        data_length: The length of the pack data block

    Returns:
        6-byte OPK header

    Example:
        >>> header = create_opk_header(256)
        >>> print(header.hex())
        4f504b000100
    """
    return b"OPK" + pack_24bit_length(data_length)


def parse_opk_header(data: bytes) -> tuple[bool, int]:
    """
    Parse and validate an OPK file header.

    Args:
        data: At least 6 bytes of OPK file data

    Returns:
        Tuple of (is_valid, data_length)
        - is_valid: True if the header magic is correct
        - data_length: The declared data length (or 0 if invalid)

    Example:
        >>> is_valid, length = parse_opk_header(opk_data)
        >>> if is_valid:
        ...     print(f"Data length: {length}")
    """
    if len(data) < 6:
        return False, 0

    # Check magic "OPK"
    if data[0:3] != b"OPK":
        return False, 0

    # Extract length
    length = unpack_24bit_length(data[3:6])
    return True, length


def validate_opk_length(file_size: int, declared_length: int) -> bool:
    """
    Validate that the declared length matches the actual file size.

    Psion tools use two conventions for the length field:
    - BLDPACK: length = file_size - 6 (includes FF FF)
    - UNMAKE: length = file_size - 8 (excludes FF FF)

    This function accepts either interpretation.

    Args:
        file_size: Actual file size in bytes
        declared_length: Length value from OPK header

    Returns:
        True if the length is consistent, False otherwise
    """
    # BLDPACK style: length = file_size - 6
    if declared_length + 6 == file_size:
        return True

    # UNMAKE style: length = file_size - 8
    if declared_length + 8 == file_size:
        return True

    return False


# =============================================================================
# Header Checksum Analysis (with protection bit detection)
# =============================================================================

def analyze_header_checksum(pack_header: bytes) -> ChecksumAnalysis:
    """
    Analyze a pack header checksum with protection bit detection.

    This function not only verifies the checksum but also detects when
    a mismatch is caused by copy/write protection bits being set AFTER
    the checksum was calculated - a common occurrence in Psion packs.

    **Flashpak special handling**: For Flashpaks, the high bit (0x8000) of
    the checksum word is used for write-protection status (normally set,
    cleared for write-protection). Only the lower 15 bits are compared.

    Args:
        pack_header: The 10-byte pack header

    Returns:
        ChecksumAnalysis with detailed results

    Example:
        >>> analysis = analyze_header_checksum(header_bytes)
        >>> if analysis.is_valid:
        ...     print("Checksum OK")
        >>> elif analysis.is_valid_with_protection:
        ...     print(f"Checksum OK (protection bits 0x{analysis.protection_bits_added:02X} added later)")
        >>> else:
        ...     print(f"Checksum mismatch: {analysis.message}")
    """
    if len(pack_header) < 10:
        return ChecksumAnalysis(
            is_valid=False,
            stored_checksum=0,
            calculated_checksum=0,
            message="Pack header too short (need 10 bytes)"
        )

    stored = (pack_header[8] << 8) | pack_header[9]
    calculated = calculate_pack_checksum(pack_header)
    flags = pack_header[0]
    pack_is_flashpak = is_flashpak(flags)

    # ==========================================================================
    # Flashpak special case: high bit of checksum is write-protection status
    # ==========================================================================
    if pack_is_flashpak:
        # For Flashpaks, only compare lower 15 bits
        stored_15bit = stored & FLASHPAK_CHECKSUM_MASK
        calculated_15bit = calculated & FLASHPAK_CHECKSUM_MASK

        # Bit 15: normally SET, CLEARED for write-protection
        flashpak_wp = (stored & FLASHPAK_WRITE_PROTECT_BIT) == 0

        if calculated_15bit == stored_15bit:
            wp_msg = " (write-protected)" if flashpak_wp else ""
            return ChecksumAnalysis(
                is_valid=True,
                stored_checksum=stored,
                calculated_checksum=calculated,
                is_flashpak=True,
                flashpak_write_protected=flashpak_wp,
                message=f"Flashpak header checksum valid (15-bit){wp_msg}"
            )

        # Check for placeholder checksums
        if stored == 0xFFFF or stored == 0x7FFF or stored == 0x0000:
            return ChecksumAnalysis(
                is_valid=False,
                stored_checksum=stored,
                calculated_checksum=calculated,
                is_flashpak=True,
                flashpak_write_protected=flashpak_wp,
                message=f"Flashpak checksum is 0x{stored:04X} placeholder (not calculated)"
            )

        # Try to detect protection bits modified after checksum calculation
        # Two cases:
        # 1. Bits ADDED after: calculated > stored, bits present in flags
        # 2. Bits REMOVED after: stored > calculated, bits NOT present in flags
        diff_added = (calculated_15bit - stored_15bit) & FLASHPAK_CHECKSUM_MASK
        diff_removed = (stored_15bit - calculated_15bit) & FLASHPAK_CHECKSUM_MASK

        for bits_to_try in [
            # Standard protection bits
            ProtectionBits.WRITE_PROTECT,  # 0x08
            ProtectionBits.COPY_PROTECT,   # 0x20
            ProtectionBits.ALL_PROTECTION, # 0x28
            0x08, 0x20, 0x28,
            # Extended patterns (some tools modify additional bits)
            0x10, 0x18, 0x30, 0x38,
            0x02, 0x04, 0x06,  # Pack type bits
            0x0A, 0x0C, 0x0E,  # Write protect + pack type
            0x22, 0x24, 0x26,  # Copy protect + pack type
            0x2A, 0x2C, 0x2E,  # All protect + pack type
            0x12, 0x14, 0x16, 0x1A, 0x1C, 0x1E,  # Other bit + combinations
            0x32, 0x34, 0x36, 0x3A, 0x3C, 0x3E,  # More combinations
        ]:
            expected_diff = (bits_to_try << 8) & FLASHPAK_CHECKSUM_MASK

            # Case 1: Bits were ADDED after checksum calculation
            if diff_added == expected_diff and (flags & bits_to_try) == bits_to_try:
                original_flags = flags & ~int(bits_to_try)
                action = "set after"
            # Case 2: Bits were REMOVED after checksum calculation
            elif diff_removed == expected_diff and (flags & bits_to_try) == 0:
                original_flags = flags | bits_to_try
                action = "cleared after"
            else:
                continue

            bit_names = []
            if bits_to_try & ProtectionBits.WRITE_PROTECT:
                bit_names.append("write-protect (0x08)")
            if bits_to_try & ProtectionBits.COPY_PROTECT:
                bit_names.append("copy-protect (0x20)")
            if bits_to_try & ~ProtectionBits.ALL_PROTECTION:
                other_bits = bits_to_try & ~ProtectionBits.ALL_PROTECTION
                bit_names.append(f"other (0x{other_bits:02X})")

            bits_desc = ", ".join(bit_names) if bit_names else f"0x{bits_to_try:02X}"
            wp_msg = " (write-protected)" if flashpak_wp else ""

            return ChecksumAnalysis(
                is_valid=False,
                stored_checksum=stored,
                calculated_checksum=calculated,
                is_valid_with_protection=True,
                protection_bits_added=bits_to_try,
                original_flags=original_flags,
                is_flashpak=True,
                flashpak_write_protected=flashpak_wp,
                message=f"Flashpak checksum valid if {bits_desc} bit(s) were {action} calculation{wp_msg}"
            )

        # Genuine mismatch for Flashpak
        return ChecksumAnalysis(
            is_valid=False,
            stored_checksum=stored,
            calculated_checksum=calculated,
            is_flashpak=True,
            flashpak_write_protected=flashpak_wp,
            message=f"Flashpak checksum mismatch: stored 0x{stored_15bit:04X}, calculated 0x{calculated_15bit:04X} (15-bit comparison)"
        )

    # ==========================================================================
    # Standard packs (Datapak, Rampak): full 16-bit checksum
    # ==========================================================================

    # Check for exact match
    if calculated == stored:
        return ChecksumAnalysis(
            is_valid=True,
            stored_checksum=stored,
            calculated_checksum=calculated,
            message="Header checksum valid"
        )

    # Check for 0xFFFF placeholder (some tools use this)
    if stored == 0xFFFF:
        return ChecksumAnalysis(
            is_valid=False,
            stored_checksum=stored,
            calculated_checksum=calculated,
            message="Checksum is 0xFFFF placeholder (not calculated)"
        )

    # Try to detect protection bits modified after checksum calculation
    # Two cases:
    # 1. Bits ADDED after: calculated > stored, bits present in flags
    # 2. Bits REMOVED after: stored > calculated, bits NOT present in flags
    diff_added = (calculated - stored) & 0xFFFF
    diff_removed = (stored - calculated) & 0xFFFF

    # Check if difference corresponds to known protection bits
    # shifted to the high byte position (flags is high byte of word 0)
    for bits_to_try in [
        # Standard protection bits
        ProtectionBits.WRITE_PROTECT,  # 0x08
        ProtectionBits.COPY_PROTECT,   # 0x20
        ProtectionBits.ALL_PROTECTION, # 0x28
        0x08, 0x20, 0x28,
        # Extended patterns (some tools modify additional bits)
        0x10, 0x18, 0x30, 0x38,
        0x02, 0x04, 0x06,  # Pack type bits
        0x0A, 0x0C, 0x0E,  # Write protect + pack type
        0x22, 0x24, 0x26,  # Copy protect + pack type
        0x2A, 0x2C, 0x2E,  # All protect + pack type
        0x12, 0x14, 0x16, 0x1A, 0x1C, 0x1E,  # Other bit + combinations
        0x32, 0x34, 0x36, 0x3A, 0x3C, 0x3E,  # More combinations
    ]:
        # Protection bits affect word 0's high byte, so difference is bits << 8
        expected_diff = (bits_to_try << 8) & 0xFFFF

        # Case 1: Bits were ADDED after checksum calculation
        if diff_added == expected_diff and (flags & bits_to_try) == bits_to_try:
            original_flags = flags & ~int(bits_to_try)
            action = "set after"
        # Case 2: Bits were REMOVED after checksum calculation
        elif diff_removed == expected_diff and (flags & bits_to_try) == 0:
            original_flags = flags | bits_to_try
            action = "cleared after"
        else:
            continue

        # Build description of which bits
        bit_names = []
        if bits_to_try & ProtectionBits.WRITE_PROTECT:
            bit_names.append("write-protect (0x08)")
        if bits_to_try & ProtectionBits.COPY_PROTECT:
            bit_names.append("copy-protect (0x20)")
        if bits_to_try & ~ProtectionBits.ALL_PROTECTION:
            other_bits = bits_to_try & ~ProtectionBits.ALL_PROTECTION
            bit_names.append(f"other (0x{other_bits:02X})")

        bits_desc = ", ".join(bit_names) if bit_names else f"0x{bits_to_try:02X}"

        return ChecksumAnalysis(
            is_valid=False,
            stored_checksum=stored,
            calculated_checksum=calculated,
            is_valid_with_protection=True,
            protection_bits_added=bits_to_try,
            original_flags=original_flags,
            message=f"Checksum valid if {bits_desc} bit(s) were {action} calculation"
        )

    # No protection bit pattern found - genuine mismatch
    return ChecksumAnalysis(
        is_valid=False,
        stored_checksum=stored,
        calculated_checksum=calculated,
        message=f"Checksum mismatch: stored 0x{stored:04X}, calculated 0x{calculated:04X}"
    )
