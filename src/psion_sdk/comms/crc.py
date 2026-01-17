"""
CRC-CCITT Implementation for Psion Link Protocol
=================================================

This module implements the CRC-CCITT checksum algorithm used by the Psion
Link Protocol for packet integrity verification. The CRC ensures reliable
data transfer between the PC and Psion Organiser II over serial connection.

Technical Details
-----------------
- Polynomial: x^16 + x^12 + x^5 + 1
- Initial value: 0x0000
- The algorithm uses documented base CRC values for power-of-2 bytes
- Multi-byte CRC uses the iterative formula from Jaap's documentation

Known CRC Values (from Psion documentation)
-------------------------------------------
These reference values are used to build the lookup table:

    CRC($01) = $C1C0
    CRC($02) = $81C1
    CRC($04) = $01C3
    CRC($08) = $01C6
    CRC($10) = $01CC
    CRC($20) = $01D8
    CRC($40) = $01F0
    CRC($80) = $01A0

Iterative Formula (from Jaap's documentation)
---------------------------------------------
If xxyy is the CRC for a sequence of bytes, then the CRC of that sequence
followed by byte bb is: CRC(bb XOR xx) XOR (yy << 8)

Where CRC() is the single-byte lookup table value.

Usage
-----
    from psion_sdk.comms.crc import crc_ccitt, crc_ccitt_fast

    # Calculate CRC of some data
    data = bytes([0x01, 0x10])
    checksum = crc_ccitt_fast(data)  # Returns 0x005C

    # Verify a packet
    expected_crc = crc_ccitt_fast(data)
    assert crc_ccitt_fast(data) == expected_crc
"""

from typing import Final

# =============================================================================
# CRC-CCITT Constants
# =============================================================================

# Default initial CRC value (start at 0)
CRC_INITIAL: Final[int] = 0x0000

# Mask for 16-bit values
CRC_MASK: Final[int] = 0xFFFF

# Base CRC values from Psion documentation
# These are the CRC values for single bytes that are powers of 2
# All other single-byte CRC values can be computed via XOR (CRC is linear over GF(2))
_BASE_CRC_VALUES: Final[dict[int, int]] = {
    0x01: 0xC1C0,
    0x02: 0x81C1,
    0x04: 0x01C3,
    0x08: 0x01C6,
    0x10: 0x01CC,
    0x20: 0x01D8,
    0x40: 0x01F0,
    0x80: 0x01A0,
}


# =============================================================================
# Lookup Table Generation
# =============================================================================

def _generate_crc_table() -> tuple[int, ...]:
    """
    Generate the 256-entry CRC lookup table from documented base values.

    The CRC algorithm is linear over GF(2), which means:
        CRC(a XOR b) = CRC(a) XOR CRC(b)

    This allows us to compute any single-byte CRC value by XORing together
    the base values for each bit that is set in the byte.

    Returns:
        Tuple of 256 CRC values for each possible byte value.
    """
    table = []
    for byte_val in range(256):
        # Decompose byte into sum of powers of 2 and XOR the base CRC values
        crc = 0
        for bit in range(8):
            if byte_val & (1 << bit):
                crc ^= _BASE_CRC_VALUES[1 << bit]
        table.append(crc)
    return tuple(table)


# Pre-computed CRC lookup table - generated once at import time
# This provides O(1) lookup for each byte processed
CRC_TABLE: Final[tuple[int, ...]] = _generate_crc_table()


# =============================================================================
# Reference Implementation (Using lookup table)
# =============================================================================

def crc_ccitt(data: bytes, initial: int = CRC_INITIAL) -> int:
    """
    Calculate CRC-CCITT checksum using the Psion iterative formula.

    The iterative formula from Jaap's documentation:
    If xxyy is the CRC for a sequence of bytes, then the CRC of that sequence
    followed by byte bb is: CRC(bb XOR xx) XOR (yy << 8)

    Where:
        xx = high byte of current CRC
        yy = low byte of current CRC
        CRC() = single-byte lookup table value

    Args:
        data: Input bytes to calculate CRC over. This should NOT include
              any escape sequences (they are stripped before CRC calculation
              in the link protocol).
        initial: Initial CRC value. Default is 0x0000 as used by the Psion
                 protocol. Can be used for incremental CRC calculation.

    Returns:
        16-bit CRC value (0x0000 to 0xFFFF).

    Example:
        >>> hex(crc_ccitt(bytes([0x01])))
        '0xc1c0'
        >>> hex(crc_ccitt(bytes([0x02])))
        '0x81c1'
        >>> hex(crc_ccitt(bytes([0x01, 0x10])))
        '0x5c'
    """
    crc = initial

    for byte in data:
        # Extract high and low bytes of current CRC
        xx = (crc >> 8) & 0xFF  # High byte
        yy = crc & 0xFF         # Low byte

        # Apply iterative formula: CRC(bb XOR xx) XOR (yy << 8)
        crc = CRC_TABLE[byte ^ xx] ^ (yy << 8)

    return crc


# =============================================================================
# Fast Implementation (Alias to reference - both use table lookup)
# =============================================================================

def crc_ccitt_fast(data: bytes, initial: int = CRC_INITIAL) -> int:
    """
    Calculate CRC-CCITT checksum using table lookup.

    This is an alias to crc_ccitt() since the reference implementation
    already uses the efficient table-based approach.

    Args:
        data: Input bytes to calculate CRC over. This should NOT include
              any escape sequences (they are stripped before CRC calculation
              in the link protocol).
        initial: Initial CRC value. Default is 0x0000. Can be used for
                 incremental CRC calculation when processing large data
                 in chunks.

    Returns:
        16-bit CRC value (0x0000 to 0xFFFF).

    Example:
        >>> hex(crc_ccitt_fast(bytes([0x01])))
        '0xc1c0'
        >>> hex(crc_ccitt_fast(bytes([0x04])))
        '0x1c3'

    Note:
        This function produces identical results to crc_ccitt() and can be
        used interchangeably.
    """
    return crc_ccitt(data, initial)


# =============================================================================
# Utility Functions
# =============================================================================

def crc_to_bytes(crc: int) -> bytes:
    """
    Convert a CRC value to big-endian bytes for transmission.

    The Psion link protocol transmits CRC as two bytes, high byte first
    (big-endian), immediately after the packet footer.

    Args:
        crc: 16-bit CRC value to convert.

    Returns:
        Two bytes: [high_byte, low_byte]

    Example:
        >>> crc_to_bytes(0xC1C0)
        b'\\xc1\\xc0'
        >>> crc_to_bytes(0x005C)
        b'\\x00\\x5c'
    """
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def crc_from_bytes(data: bytes) -> int:
    """
    Convert big-endian bytes to a CRC value.

    This is the inverse of crc_to_bytes(), used when receiving packets
    to extract the transmitted CRC for verification.

    Args:
        data: Two bytes in big-endian order [high_byte, low_byte].
              If more than 2 bytes are provided, only the first 2 are used.

    Returns:
        16-bit CRC value.

    Raises:
        ValueError: If data is less than 2 bytes.

    Example:
        >>> crc_from_bytes(b'\\xc1\\xc0')
        0xC1C0
    """
    if len(data) < 2:
        raise ValueError(f"CRC requires 2 bytes, got {len(data)}")
    return (data[0] << 8) | data[1]


def verify_crc(data: bytes, expected_crc: int) -> bool:
    """
    Verify that data matches an expected CRC value.

    This is a convenience function for checking packet integrity.

    Args:
        data: Data bytes to verify (without CRC bytes).
        expected_crc: Expected CRC value.

    Returns:
        True if calculated CRC matches expected, False otherwise.

    Example:
        >>> verify_crc(bytes([0x01]), 0xC1C0)
        True
        >>> verify_crc(bytes([0x01, 0x10]), 0x005C)
        True
    """
    return crc_ccitt_fast(data) == expected_crc


def verify_packet_crc(packet_with_crc: bytes) -> bool:
    """
    Verify a packet that has CRC appended.

    Calculates the CRC over the data portion (all but last 2 bytes) and
    compares with the transmitted CRC (last 2 bytes).

    Args:
        packet_with_crc: Packet data including the 2-byte CRC at the end.

    Returns:
        True if packet CRC is valid, False otherwise.

    Example:
        >>> data = bytes([0x01])
        >>> crc = crc_ccitt_fast(data)
        >>> packet = data + crc_to_bytes(crc)
        >>> verify_packet_crc(packet)
        True
    """
    if len(packet_with_crc) < 3:  # Need at least 1 data byte + 2 CRC bytes
        return False
    data = packet_with_crc[:-2]
    transmitted_crc = crc_from_bytes(packet_with_crc[-2:])
    return crc_ccitt_fast(data) == transmitted_crc


# =============================================================================
# Reference Values for Testing
# =============================================================================

# Known CRC values from Psion documentation
# These are used by the test suite to verify the implementation
REFERENCE_CRC_VALUES: Final[dict[int, int]] = {
    0x01: 0xC1C0,
    0x02: 0x81C1,
    0x04: 0x01C3,
    0x08: 0x01C6,
    0x10: 0x01CC,
    0x20: 0x01D8,
    0x40: 0x01F0,
    0x80: 0x01A0,
}
