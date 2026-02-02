"""
MCP Tool Parameter Parsing
==========================

Utilities for parsing parameter values from various input formats.

MCP clients may send numeric values in various formats:
    - Integer: 0x8100, 33024
    - String hex: "0x8100", "0X8100", "$8100"
    - String decimal: "33024"

These utilities normalize values to Python integers with proper validation.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any


def parse_integer(
    value: Any,
    param_name: str,
    min_val: int = 0,
    max_val: int = 0xFFFF,
    default: int = None
) -> int:
    """
    Parse an integer value from various input formats.

    Accepts:
        - int: Used directly (e.g., 0x8100, 33024)
        - str with "0x"/"0X" prefix: Hex string (e.g., "0x8100")
        - str with "$" prefix: Assembly-style hex (e.g., "$8100")
        - str decimal: Decimal string (e.g., "33024")
        - None: Returns default if provided, raises otherwise

    Args:
        value: The input value to parse
        param_name: Name of the parameter (for error messages)
        min_val: Minimum allowed value (inclusive, default 0)
        max_val: Maximum allowed value (inclusive, default 0xFFFF)
        default: Default value if input is None (optional)

    Returns:
        The parsed integer value

    Raises:
        ValueError: If parsing fails or value is out of range

    Examples:
        >>> parse_integer(0x8100, "address")
        33024
        >>> parse_integer("0x8100", "address")
        33024
        >>> parse_integer("$8100", "address")
        33024
        >>> parse_integer("33024", "address")
        33024
        >>> parse_integer(None, "start", default=0)
        0
    """
    # Handle None/missing values
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{param_name}: value required")

    # Already an integer - use directly
    if isinstance(value, int) and not isinstance(value, bool):
        parsed = value
    elif isinstance(value, str):
        value = value.strip()
        if not value:
            if default is not None:
                return default
            raise ValueError(f"{param_name}: empty string")

        try:
            # Handle different string formats
            if value.startswith(("0x", "0X")):
                # Standard hex notation: "0x8100"
                parsed = int(value, 16)
            elif value.startswith("$"):
                # Assembly-style hex notation: "$8100"
                parsed = int(value[1:], 16)
            else:
                # Try decimal first, then hex as fallback
                # This handles both "33024" and "8100" (if all hex digits)
                try:
                    parsed = int(value, 10)
                except ValueError:
                    # Try as hex without prefix (e.g., "8100", "FF")
                    parsed = int(value, 16)
        except ValueError as e:
            raise ValueError(
                f"{param_name}: cannot parse '{value}' as integer. "
                f"Use decimal (33024) or hex (0x8100, $8100)"
            ) from e
    else:
        raise ValueError(
            f"{param_name}: expected integer or string, got {type(value).__name__}"
        )

    # Range validation
    if not (min_val <= parsed <= max_val):
        if max_val == 0xFF:
            range_hint = "0-255 (0x00-0xFF)"
        elif max_val == 0xFFFF:
            range_hint = "0-65535 (0x0000-0xFFFF)"
        else:
            range_hint = f"{min_val}-{max_val}"
        raise ValueError(
            f"{param_name}: value ${parsed:04X} ({parsed}) out of range. "
            f"Must be {range_hint}"
        )

    return parsed


def parse_address(value: Any, param_name: str = "address", default: int = None) -> int:
    """
    Parse a 16-bit memory address from various input formats.

    Convenience wrapper around parse_integer for address parameters.
    Addresses are 16-bit values (0x0000 to 0xFFFF).

    Args:
        value: The input value to parse
        param_name: Name of the parameter (for error messages)
        default: Default value if input is None (optional)

    Returns:
        The parsed address as an integer (0-65535)

    Raises:
        ValueError: If parsing fails or value is out of range

    Examples:
        >>> parse_address(0x8100)
        33024
        >>> parse_address("0x8100")
        33024
        >>> parse_address("$8100")
        33024
    """
    return parse_integer(value, param_name, min_val=0, max_val=0xFFFF, default=default)


def parse_byte(value: Any, param_name: str = "value", default: int = None) -> int:
    """
    Parse an 8-bit byte value from various input formats.

    Convenience wrapper around parse_integer for byte parameters.
    Bytes are 8-bit values (0x00 to 0xFF).

    Args:
        value: The input value to parse
        param_name: Name of the parameter (for error messages)
        default: Default value if input is None (optional)

    Returns:
        The parsed byte as an integer (0-255)

    Raises:
        ValueError: If parsing fails or value is out of range

    Examples:
        >>> parse_byte(0x42)
        66
        >>> parse_byte("0x42")
        66
        >>> parse_byte("66")
        66
    """
    return parse_integer(value, param_name, min_val=0, max_val=0xFF, default=default)
