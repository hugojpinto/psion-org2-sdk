"""
Serial Port Utilities for Psion Communication
==============================================

This module provides utilities for managing serial port connections
to the Psion Organiser II. It handles:

- Port enumeration and detection
- Automatic detection of likely USB-serial adapters
- Port configuration for Psion communication
- Platform-independent operation

Hardware Requirements
---------------------
The Psion Comms Link uses a DB-25 RS-232 connector. For modern computers,
you typically need:

1. DB-25 to DE-9 adapter (if your adapter has 9 pins)
2. DE-9 to USB adapter (USB-serial converter)

Recommended USB-Serial Adapters
-------------------------------
- FTDI FT232R-based adapters (most reliable)
- Silicon Labs CP210x-based adapters (good alternative)

Known Issues
------------
- Prolific PL2303-based adapters may have timing issues
- Some cheap adapters don't properly handle the required timing

Serial Port Settings
--------------------
The Psion Comms Link uses these settings:
- Baud Rate: 9600 (configurable: 1200, 2400, 4800, 9600)
- Data Bits: 8
- Parity: None
- Stop Bits: 1
- Flow Control: None (protocol handles flow)

The baud rate must match the Psion's SETUP > COMMS > BAUD setting.
"""

import logging
from dataclasses import dataclass
from typing import Final, Optional

import serial
import serial.tools.list_ports

from psion_sdk.errors import ConnectionError

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Valid baud rates supported by Psion Comms Link
VALID_BAUD_RATES: Final[tuple[int, ...]] = (1200, 2400, 4800, 9600)

# Default baud rate (matches typical Psion default)
DEFAULT_BAUD_RATE: Final[int] = 9600

# Default read timeout in seconds
DEFAULT_TIMEOUT: Final[float] = 1.0

# USB Vendor IDs for common USB-serial adapters
# These are used for auto-detection of likely Psion connections
USB_VENDOR_IDS: Final[dict[int, str]] = {
    0x0403: "FTDI",       # Future Technology Devices International
    0x10C4: "Silicon Labs",  # Silicon Labs CP210x
    0x067B: "Prolific",   # Prolific Technology (less reliable)
    0x1A86: "QinHeng",    # QinHeng Electronics (CH340)
}


# =============================================================================
# Port Information
# =============================================================================

@dataclass(frozen=True)
class PortInfo:
    """
    Information about an available serial port.

    This dataclass provides a structured view of serial port information,
    useful for displaying port lists to users and for auto-detection.

    Attributes:
        device: System device path (e.g., '/dev/ttyUSB0', 'COM3')
        description: Human-readable description from the driver
        manufacturer: Device manufacturer (if available)
        product: Product name (if available)
        serial_number: Device serial number (if available)
        vid: USB Vendor ID (None for non-USB ports)
        pid: USB Product ID (None for non-USB ports)
        is_usb: True if this is a USB-serial adapter
    """

    device: str
    description: str
    manufacturer: Optional[str]
    product: Optional[str]
    serial_number: Optional[str]
    vid: Optional[int]
    pid: Optional[int]

    @property
    def is_usb(self) -> bool:
        """Return True if this is a USB-serial adapter."""
        return self.vid is not None

    @property
    def vendor_name(self) -> Optional[str]:
        """Return the vendor name for known USB adapters."""
        if self.vid is not None:
            return USB_VENDOR_IDS.get(self.vid)
        return None

    def __str__(self) -> str:
        """Format port info for display."""
        parts = [self.device]
        if self.description:
            parts.append(f"- {self.description}")
        if self.vendor_name:
            parts.append(f"({self.vendor_name})")
        return " ".join(parts)


# =============================================================================
# Port Enumeration
# =============================================================================

def list_serial_ports() -> list[PortInfo]:
    """
    List all available serial ports on the system.

    This function enumerates all serial ports detected by the system,
    including both hardware serial ports and USB-serial adapters.

    Returns:
        List of PortInfo objects describing available ports.

    Example:
        >>> for port in list_serial_ports():
        ...     print(f"{port.device}: {port.description}")
        /dev/ttyUSB0: USB Serial Port (FTDI)
        /dev/ttyS0: ttyS0
    """
    ports = []

    for port in serial.tools.list_ports.comports():
        info = PortInfo(
            device=port.device,
            description=port.description or "",
            manufacturer=port.manufacturer,
            product=port.product,
            serial_number=port.serial_number,
            vid=port.vid,
            pid=port.pid,
        )
        ports.append(info)
        logger.debug(
            "Found port: %s (vid=%s, pid=%s)",
            port.device,
            f"{port.vid:04X}" if port.vid else "N/A",
            f"{port.pid:04X}" if port.pid else "N/A",
        )

    return ports


def find_psion_port() -> Optional[str]:
    """
    Attempt to auto-detect a Psion-compatible serial port.

    This function looks for USB-serial adapters that are known to work
    well with the Psion Comms Link. It prioritizes FTDI and Silicon Labs
    adapters over others.

    Detection Priority:
    1. FTDI adapters (most reliable)
    2. Silicon Labs CP210x adapters
    3. Other USB-serial adapters
    4. None if no suitable port found

    Returns:
        Device path of the detected port, or None if not found.

    Note:
        This auto-detection is a convenience feature. Users can always
        specify the port explicitly using the --port option.

    Example:
        >>> port = find_psion_port()
        >>> if port:
        ...     print(f"Found likely Psion port: {port}")
        ... else:
        ...     print("No suitable port found, please specify manually")
    """
    ports = list_serial_ports()
    usb_ports = [p for p in ports if p.is_usb]

    if not usb_ports:
        logger.debug("No USB serial ports found")
        return None

    # Prioritize by vendor
    for vid in [0x0403, 0x10C4]:  # FTDI, Silicon Labs
        for port in usb_ports:
            if port.vid == vid:
                logger.info(
                    "Auto-detected port: %s (%s)",
                    port.device, port.vendor_name
                )
                return port.device

    # Fall back to any USB-serial port
    first_usb = usb_ports[0]
    logger.info(
        "Using first USB serial port: %s (%s)",
        first_usb.device, first_usb.description
    )
    return first_usb.device


# =============================================================================
# Port Configuration
# =============================================================================

def open_serial_port(
    device: str,
    baud_rate: int = DEFAULT_BAUD_RATE,
    timeout: float = DEFAULT_TIMEOUT,
) -> serial.Serial:
    """
    Open and configure a serial port for Psion communication.

    This function opens the specified serial port and configures it
    with the correct settings for the Psion Comms Link:
    - 8 data bits
    - No parity
    - 1 stop bit
    - No hardware or software flow control

    Args:
        device: Serial port device path (e.g., '/dev/ttyUSB0', 'COM3').
        baud_rate: Baud rate (must be 1200, 2400, 4800, or 9600).
                   Default is 9600.
        timeout: Read timeout in seconds. Default is 1.0.

    Returns:
        Configured and opened serial.Serial object.

    Raises:
        ConnectionError: If the port cannot be opened or configured.
        ValueError: If baud_rate is not a valid value.

    Example:
        >>> port = open_serial_port('/dev/ttyUSB0', baud_rate=9600)
        >>> # Use port for communication...
        >>> port.close()

    Note:
        The caller is responsible for closing the port when done.
        Consider using a context manager or try/finally block.
    """
    # Validate baud rate
    if baud_rate not in VALID_BAUD_RATES:
        valid_str = ", ".join(str(b) for b in VALID_BAUD_RATES)
        raise ValueError(
            f"Invalid baud rate: {baud_rate}. Valid rates: {valid_str}"
        )

    logger.info(
        "Opening serial port: %s at %d baud",
        device, baud_rate
    )

    try:
        port = serial.Serial(
            port=device,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            xonxoff=False,      # No software flow control
            rtscts=False,       # No hardware flow control
            dsrdtr=False,       # No DTR/DSR handshaking
        )

        # Flush any pending data
        port.reset_input_buffer()
        port.reset_output_buffer()

        logger.debug(
            "Port opened: %s (timeout=%.1f)",
            device, timeout
        )

        return port

    except serial.SerialException as e:
        # Provide helpful error messages for common issues
        error_msg = str(e)

        if "Permission denied" in error_msg:
            raise ConnectionError(
                f"Permission denied accessing {device}. "
                "You may need to add your user to the 'dialout' group: "
                "sudo usermod -a -G dialout $USER"
            )
        elif "No such file" in error_msg or "not found" in error_msg.lower():
            raise ConnectionError(
                f"Serial port not found: {device}. "
                "Use 'pslink ports' to list available ports."
            )
        elif "busy" in error_msg.lower() or "in use" in error_msg.lower():
            raise ConnectionError(
                f"Serial port {device} is busy. "
                "Close any other programs using the port."
            )
        else:
            raise ConnectionError(f"Cannot open {device}: {e}")


def close_serial_port(port: serial.Serial) -> None:
    """
    Safely close a serial port.

    This function ensures the port is closed properly, flushing
    any pending data and ignoring errors during close.

    Args:
        port: Serial port object to close.
    """
    if port is None:
        return

    try:
        if port.is_open:
            port.reset_input_buffer()
            port.reset_output_buffer()
            port.close()
            logger.debug("Serial port closed")
    except Exception as e:
        logger.warning("Error closing serial port: %s", e)


# =============================================================================
# Port Validation
# =============================================================================

def validate_port_settings(
    port: serial.Serial,
    expected_baud: int = DEFAULT_BAUD_RATE,
) -> bool:
    """
    Validate that a port has the correct settings for Psion communication.

    This is useful for verifying that a port passed from external code
    has been configured correctly.

    Args:
        port: Serial port object to validate.
        expected_baud: Expected baud rate (default 9600).

    Returns:
        True if settings are correct, False otherwise.

    Note:
        This function only checks settings, it doesn't verify that
        communication is actually working.
    """
    if not port.is_open:
        logger.warning("Port is not open")
        return False

    issues = []

    if port.baudrate != expected_baud:
        issues.append(f"baud rate is {port.baudrate}, expected {expected_baud}")

    if port.bytesize != serial.EIGHTBITS:
        issues.append(f"data bits is {port.bytesize}, expected 8")

    if port.parity != serial.PARITY_NONE:
        issues.append(f"parity is {port.parity}, expected none")

    if port.stopbits != serial.STOPBITS_ONE:
        issues.append(f"stop bits is {port.stopbits}, expected 1")

    if port.xonxoff:
        issues.append("XON/XOFF flow control should be disabled")

    if port.rtscts:
        issues.append("RTS/CTS flow control should be disabled")

    if issues:
        for issue in issues:
            logger.warning("Port setting issue: %s", issue)
        return False

    return True


# =============================================================================
# Platform Detection
# =============================================================================

def get_default_port_prefix() -> str:
    """
    Get the default serial port prefix for the current platform.

    Returns:
        Platform-specific port prefix:
        - Linux: '/dev/ttyUSB' (USB-serial) or '/dev/ttyS' (hardware)
        - macOS: '/dev/tty.usbserial' or '/dev/cu.usbserial'
        - Windows: 'COM'

    Example:
        >>> prefix = get_default_port_prefix()
        >>> print(f"Look for ports like: {prefix}0, {prefix}1, ...")
    """
    import platform

    system = platform.system().lower()

    if system == "linux":
        return "/dev/ttyUSB"
    elif system == "darwin":
        return "/dev/tty.usbserial"
    elif system == "windows":
        return "COM"
    else:
        return "/dev/ttyUSB"  # Default to Linux-style


def format_port_list(ports: list[PortInfo], verbose: bool = False) -> str:
    """
    Format a list of ports for display to the user.

    Args:
        ports: List of PortInfo objects to format.
        verbose: If True, include additional details.

    Returns:
        Formatted string with one port per line.
    """
    if not ports:
        return "No serial ports found."

    lines = []
    for port in ports:
        if verbose:
            line = f"  {port.device}"
            if port.description:
                line += f"\n    Description: {port.description}"
            if port.manufacturer:
                line += f"\n    Manufacturer: {port.manufacturer}"
            if port.product:
                line += f"\n    Product: {port.product}"
            if port.vid is not None:
                line += f"\n    USB VID:PID: {port.vid:04X}:{port.pid:04X}"
                if port.vendor_name:
                    line += f" ({port.vendor_name})"
            if port.serial_number:
                line += f"\n    Serial: {port.serial_number}"
            lines.append(line)
        else:
            lines.append(f"  {port}")

    return "\n".join(lines)
