"""
Pack/Cartridge Emulation for Psion Organiser II Emulator
=========================================================

Ported from JAPE's pack.js to Python.

The Psion Organiser II supports several pack types:
- Datapaks: EPROM-based, write-once (requires 21V for programming)
- Rampaks: RAM-based, read-write (battery backed, hardware ID 0x0101)
- Flash packs: Flash memory, electrically erasable (hardware ID 0xB489)
- ROM packs: Read-only memory

Pack sizes: 8K, 16K, 32K, 64K, 128K

Pack types use different addressing modes:
- Linear (8K, 16K): Simple sequential addressing, SCLK toggles increment
- Paged (32K, 64K): Page register extends address space
- Segmented (128K): Segment register for larger packs

The pack interface uses a control port (from Port 6) and a data bus (Port 2).
Control pins in the control port determine the operation:
- SCLK: Serial clock - address increments when toggled
- SMR: Master reset - resets address counter when high
- SPGM_B: Program bar (active low)
- SOE_B: Output enable bar (active low) - enables data output
- SVPP: VPP select - enables programming voltage
- V21V: 21V present flag
- P2DDR: Port 2 DDR flag (indicates data direction)

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Optional, List


class PackPin(IntEnum):
    """
    Pack control pin constants.

    These map to bits in the control port used by bus.py.
    Values must match JAPE's PackPin object exactly.
    """
    SCLK = 0x01     # Serial clock - address increments on toggle
    SMR = 0x02      # Master reset - resets counter when high
    SPGM_B = 0x04   # Program bar (active low) - used for page advance
    SOE_B = 0x08    # Output enable bar (active low) - enables read
    SVPP = 0x10     # VPP select (programming voltage applied)
    V21V = 0x20     # 21V programming voltage present
    P2DDR = 0x40    # Port 2 DDR flag (data direction)


class PackType(IntEnum):
    """Pack type constants matching JAPE's PackTypes."""
    EPROM = 0       # Write-once EPROM
    RAM = 1         # Battery-backed RAM
    FLASH = 2       # Flash memory
    ROM = 3         # Read-only memory
    TOPSLOT = 4     # Top slot (treated like ROM)
    DUMMY = 5       # Empty slot


class CommandType(IntEnum):
    """
    Command types returned by pack controllers.

    These indicate what operation the control port state is requesting.
    """
    READ = 0        # Read from current address
    WRITE = 1       # Write to current address
    ID_BYTE_1 = 2   # Read hardware ID byte 1 (low byte)
    ID_BYTE_2 = 3   # Read hardware ID byte 2 (high byte)
    OTHER = 4       # No specific command / other state


class AddressingType(IntEnum):
    """Pack addressing modes."""
    LINEAR = 0      # 8K, 16K packs
    PAGED = 1       # 32K, 64K packs
    SEGMENTED = 2   # 128K+ packs


# =============================================================================
# Address Counter Classes
# =============================================================================

class PackCounter(ABC):
    """
    Abstract base class for pack address counters.

    Address counters track the current read/write position in pack memory.
    Different pack sizes use different counter types.
    """

    @property
    @abstractmethod
    def length(self) -> int:
        """Total pack size in bytes."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset counter to address 0."""
        pass

    @property
    @abstractmethod
    def address(self) -> int:
        """Current address."""
        pass

    @abstractmethod
    def control_port(self, pins: int, databus: int) -> None:
        """
        Update counter based on control port state.

        Args:
            pins: Control pins state (PackPin flags)
            databus: Data bus value (for segmented packs)
        """
        pass


class PackCounterLinear(PackCounter):
    """
    Linear address counter for 8K and 16K packs.

    Simple sequential addressing. Address increments when SCLK toggles.
    SMR resets address to 0.

    From JAPE pack.js lines 18-33.
    """

    def __init__(self, size: int):
        """
        Initialize linear counter.

        Args:
            size: Pack size in bytes
        """
        self._length = size
        self._address = 0

    @property
    def length(self) -> int:
        return self._length

    def reset(self) -> None:
        self._address = 0

    @property
    def address(self) -> int:
        return self._address

    def control_port(self, pins: int, databus: int) -> None:
        """
        Update counter based on control pins.

        - SMR high: Reset address to 0
        - SCLK toggle: Increment address (modulo pack length)
        """
        # SMR high resets counters
        if (pins & PackPin.SMR) != 0:
            self._address = 0

        # SCLK toggle increments address
        # Check if SCLK differs from LSB of address (indicates toggle)
        if (pins & PackPin.SCLK) != (self._address & 1):
            self._address = (self._address + 1) % self._length


class PackCounterPaged(PackCounter):
    """
    Paged address counter for 32K and 64K packs.

    Uses page register to extend address space. Low 8 bits increment with SCLK.
    Page advances when SPGM_B goes low while SMR is low.

    From JAPE pack.js lines 35-57.
    """

    def __init__(self, size: int):
        """
        Initialize paged counter.

        Args:
            size: Pack size in bytes
        """
        self._length = size
        self._address = 0
        self._prev_pins = 0

    @property
    def length(self) -> int:
        return self._length

    def reset(self) -> None:
        self._address = 0

    @property
    def address(self) -> int:
        return self._address

    def control_port(self, pins: int, databus: int) -> None:
        """
        Update counter based on control pins.

        - SMR high: Reset address to 0
        - SCLK toggle: Increment low 8 bits of address
        - SPGM_B falling edge (with SMR low): Advance page (increment upper bits)
        """
        # SMR high resets counters
        if (pins & PackPin.SMR) != 0:
            self._address = 0

        # SCLK toggle increments low 8 bits
        if (pins & PackPin.SCLK) != (self._address & 1):
            low_byte = ((self._address & 0xFF) + 1) & 0xFF
            self._address = (self._address & 0xFFFF00) | low_byte

        # SPGM_B falling edge with SMR low advances page
        # (SVPP omitted in JAPE, just check SPGM_B and SMR)
        if ((pins & (PackPin.SPGM_B | PackPin.SMR)) == 0 and
                (self._prev_pins & PackPin.SPGM_B) != 0):
            self._address = (self._address + 0x100) % self._length

        self._prev_pins = pins


class PackCounterSegmented(PackCounter):
    """
    Segmented address counter for 128K+ packs.

    Uses segment register for high bits, page register for middle bits,
    and linear counter for low bits. Segment can be set via data bus.

    From JAPE pack.js lines 59-86.
    """

    def __init__(self, size: int):
        """
        Initialize segmented counter.

        Args:
            size: Pack size in bytes (must be power of 2)
        """
        self._length = size
        self._address = 0
        self._prev_pins = 0

    @property
    def length(self) -> int:
        return self._length

    def reset(self) -> None:
        # Only reset lower 14 bits (16K segment), preserve segment
        self._address -= (self._address & 0x3FFF)

    @property
    def address(self) -> int:
        return self._address

    def control_port(self, pins: int, databus: int) -> None:
        """
        Update counter based on control pins.

        - SMR high: Reset low 14 bits (within current segment)
        - SCLK toggle: Increment low 8 bits
        - SPGM_B falling edge (with SVPP low, SMR low): Advance page within segment
        - SOE_B high, SMR high (others low): Set segment from data bus
        """
        # SMR high resets lower bits (but preserves segment)
        if (pins & PackPin.SMR) != 0:
            self._address -= (self._address & 0x3FFF)

        # SCLK toggle increments low 8 bits
        if (pins & PackPin.SCLK) != (self._address & 1):
            low_byte = ((self._address & 0xFF) + 1) & 0xFF
            self._address = (self._address & 0xFFFF00) | low_byte

        # SPGM_B falling edge advances page within segment
        if ((pins & (PackPin.SVPP | PackPin.SPGM_B | PackPin.SMR)) == 0 and
                (self._prev_pins & PackPin.SPGM_B) != 0):
            counter_m = self._address & 0x3F00
            counter_hl = self._address - counter_m
            self._address = counter_hl | ((counter_m + 0x100) & 0x3F00)

        # Set segment address from data bus
        # SOE_B high, SMR high, (SPGM_B can be anything)
        if ((pins & (PackPin.SVPP | PackPin.SOE_B | PackPin.SMR)) ==
                (PackPin.SOE_B | PackPin.SMR)):
            self._address = (self._address & 0x3FFF) + (databus << 14)
            # Wrap if exceeds length (assumes length is power of 2)
            if self._address >= self._length:
                self._address &= (self._length - 1)

        self._prev_pins = pins


# =============================================================================
# Pack Controller Classes
# =============================================================================

class PackController(ABC):
    """
    Abstract base class for pack controllers.

    Controllers interpret control port state to determine the command type
    (read, write, ID read, etc.) and provide hardware ID for pack detection.
    """

    @abstractmethod
    def get_hardware_id(self) -> int:
        """
        Get hardware identification bytes.

        Returns:
            16-bit hardware ID, or -1 if not supported.
            Low byte is ID_BYTE_1, high byte is ID_BYTE_2.
        """
        pass

    @abstractmethod
    def control_port(self, pins: int, databus: int) -> CommandType:
        """
        Interpret control port state to determine command.

        Args:
            pins: Control pins state
            databus: Data bus value

        Returns:
            CommandType indicating requested operation
        """
        pass


class PackControllerDummy(PackController):
    """
    Controller for empty pack slots.

    Always returns OTHER command type - no operations performed.
    """

    def get_hardware_id(self) -> int:
        return -1

    def control_port(self, pins: int, databus: int) -> CommandType:
        return CommandType.OTHER


class PackControllerRom(PackController):
    """
    Controller for ROM packs (read-only).

    Only supports read operations via SOE_B low.
    """

    def get_hardware_id(self) -> int:
        return -1

    def control_port(self, pins: int, databus: int) -> CommandType:
        # SOE_B low enables read
        if (pins & PackPin.SOE_B) == 0:
            return CommandType.READ
        return CommandType.OTHER


class PackControllerEprom(PackController):
    """
    Controller for EPROM packs (write-once).

    Read: SOE_B low
    Write: SVPP high, SOE_B high, SPGM_B low

    From JAPE pack.js lines 114-127.
    """

    def get_hardware_id(self) -> int:
        return -1  # EPROMs don't have hardware ID

    def control_port(self, pins: int, databus: int) -> CommandType:
        # SOE_B low: read
        if (pins & PackPin.SOE_B) == 0:
            return CommandType.READ

        # SVPP high, SOE_B high, SPGM_B low: write
        # (Don't check if 21V is actually present - assume any VPP is enough)
        if ((pins & (PackPin.SVPP | PackPin.SOE_B | PackPin.SPGM_B)) ==
                (PackPin.SVPP | PackPin.SOE_B)):
            return CommandType.WRITE

        return CommandType.OTHER


class PackControllerRam(PackController):
    """
    Controller for RAM packs (read-write).

    Hardware ID: 0x0101

    Read: SOE_B low
    Write: SOE_B high, SMR low
    ID: Special states with SMR high

    From JAPE pack.js lines 147-163.
    """

    def get_hardware_id(self) -> int:
        return 0x0101

    def control_port(self, pins: int, databus: int) -> CommandType:
        # ID byte 1: SOE_B low, SMR high, SCLK low
        if ((pins & (PackPin.SOE_B | PackPin.SMR | PackPin.SCLK)) == PackPin.SMR):
            return CommandType.ID_BYTE_1

        # ID byte 2: SOE_B low, SMR high, SCLK high
        if ((pins & (PackPin.SOE_B | PackPin.SMR | PackPin.SCLK)) ==
                (PackPin.SMR | PackPin.SCLK)):
            return CommandType.ID_BYTE_2

        # Read: SOE_B low
        if (pins & PackPin.SOE_B) == 0:
            return CommandType.READ

        # Write: SOE_B high, SMR low
        if ((pins & (PackPin.SOE_B | PackPin.SMR)) == PackPin.SOE_B):
            return CommandType.WRITE

        return CommandType.OTHER


class PackControllerFlash(PackController):
    """
    Controller for Flash packs (electrically erasable).

    Hardware ID: 0xB489

    Uses a mode state machine for write operations:
    - Mode transitions based on data bus commands
    - 0x40: Switch to write mode
    - 0x00: Read command (high voltage)
    - 0xC0: Read/verify command
    - 0xFF: Reset to read mode

    From JAPE pack.js lines 166-221.
    """

    # Flash mode constants
    MODE_READ = 0
    MODE_VERIFY = 1
    MODE_WRITE = 2
    MODE_ERASE = 3

    def __init__(self):
        self._mode = self.MODE_READ

    def get_hardware_id(self) -> int:
        return 0xB489

    def control_port(self, pins: int, databus: int) -> CommandType:
        # With SVPP high (programming voltage applied)
        if (pins & PackPin.SVPP) != 0:
            if self._mode == self.MODE_WRITE:
                self._mode = self.MODE_READ
                return CommandType.WRITE
            elif (databus & 0xFF) == 0x40:
                self._mode = self.MODE_WRITE
            elif (databus & 0xFF) == 0x00:
                self._mode = self.MODE_READ
                return CommandType.READ
            elif (databus & 0xFF) == 0xC0:
                self._mode = self.MODE_READ  # Actually verify mode
                return CommandType.READ
            elif (databus & 0xFF) == 0xFF:
                self._mode = self.MODE_READ  # Reset mode
        else:
            # Without SVPP
            self._mode = self.MODE_READ

            # ID byte 2: SOE_B low, SMR high
            if ((pins & (PackPin.SOE_B | PackPin.SMR)) == PackPin.SMR):
                return CommandType.ID_BYTE_2

            # ID byte 1: SOE_B high, SMR high
            if ((pins & (PackPin.SOE_B | PackPin.SMR)) ==
                    (PackPin.SOE_B | PackPin.SMR)):
                return CommandType.ID_BYTE_1

            # Read: SOE_B low
            if (pins & PackPin.SOE_B) == 0:
                return CommandType.READ

        return CommandType.OTHER


# =============================================================================
# Main Pack Class
# =============================================================================

class Pack:
    """
    Complete pack/cartridge emulation.

    Combines address counter and controller to provide full pack functionality.
    Supports loading from OPK files and raw data.

    Example:
        >>> pack = Pack.from_opk(Path("hello.opk"))
        >>> pack.reset()
        >>> data = pack.read_byte(0)  # Read first byte
    """

    def __init__(
        self,
        data: Optional[bytes] = None,
        name: str = "Empty",
        pack_type: PackType = PackType.DUMMY,
        size_kb: int = 0
    ):
        """
        Initialize pack.

        Args:
            data: Optional pack data (raw bytes, not OPK format)
            name: Pack name for display/debugging
            pack_type: Type of pack (EPROM, RAM, Flash, etc.)
            size_kb: Size in kilobytes (0 for empty)
        """
        self._name = name
        self._data: Optional[bytearray] = None
        self._output_data_bus = 0
        self._is_ready = True
        self._changed = False

        # Counter and controller (set by _prepare_hardware)
        self._counter: PackCounter = PackCounterLinear(0)
        self._controller: PackController = PackControllerDummy()

        if data is not None and size_kb > 0:
            self._setup_pack(data, pack_type, size_kb)
        elif data is not None:
            # Assume it's OPK format if no size specified
            self._load_opk_data(data, name)

    def _setup_pack(
        self,
        data: bytes,
        pack_type: PackType,
        size_kb: int
    ) -> None:
        """
        Set up pack with given data and configuration.

        Args:
            data: Raw pack data
            pack_type: Type of pack
            size_kb: Size in kilobytes
        """
        size_bytes = size_kb * 1024

        # Create data buffer
        self._data = bytearray(size_bytes)
        self._data[:len(data)] = data[:size_bytes]
        # Fill remaining with 0xFF (erased state)
        for i in range(len(data), size_bytes):
            self._data[i] = 0xFF

        # Determine addressing type
        paged = size_kb >= 32
        segmented = size_kb >= 128

        # Set up hardware
        self._prepare_hardware(pack_type, segmented, paged, size_bytes)
        self._is_ready = True

    def _prepare_hardware(
        self,
        pack_type: PackType,
        segmented: bool,
        paged: bool,
        size_bytes: int
    ) -> None:
        """
        Configure counter and controller based on pack type and addressing mode.

        Args:
            pack_type: Type of pack
            segmented: True if segmented addressing (128K+)
            paged: True if paged addressing (32K+)
            size_bytes: Pack size in bytes
        """
        # Select address counter
        if segmented:
            self._counter = PackCounterSegmented(size_bytes)
        elif paged:
            self._counter = PackCounterPaged(size_bytes)
        else:
            self._counter = PackCounterLinear(size_bytes)

        # Select controller
        if pack_type == PackType.RAM:
            self._controller = PackControllerRam()
        elif pack_type == PackType.EPROM:
            self._controller = PackControllerEprom()
        elif pack_type == PackType.FLASH:
            self._controller = PackControllerFlash()
        elif pack_type in (PackType.ROM, PackType.TOPSLOT):
            self._controller = PackControllerRom()
        else:
            self._controller = PackControllerDummy()

    def _load_opk_data(self, data: bytes, name: str) -> None:
        """
        Load pack from OPK format data.

        OPK format:
        - Bytes 0-2: "OPK" signature (79, 80, 75)
        - Bytes 3-5: Length (24-bit big-endian, length of data starting at byte 6)
        - Byte 7: Pack size in units of 8KB
        - Byte 6+: Pack data

        Pack type is determined from the pack header (first bytes of pack data):
        - Byte 0: Pack info byte
          - Bit 2: Paged addressing
          - Bit 1: Not RAM (0=RAM, 1=EPROM)
          - Bit 6: Not Flash (0=Flash, 1=EPROM/RAM)
        - Byte 1: Pages count (>=16 indicates segmented)

        From JAPE pack.js lines 359-388.
        """
        self._name = name

        # Validate length
        if len(data) < 16:
            raise ValueError("Pack image too small")

        # Check signature
        if data[0:3] != b'OPK':
            raise ValueError("File is not a pack image (missing OPK signature)")

        # Parse length (24-bit big-endian)
        data_length = (data[3] << 16) | (data[4] << 8) | data[5]

        # Validate length
        if data_length + 6 != len(data) and data_length + 8 != len(data):
            raise ValueError("Inconsistent length bytes in pack image file")

        # Get pack size from byte 7 (in units of 8KB)
        size_8kb = data[7] if len(data) > 7 else 1
        size_kb = size_8kb * 8
        size_bytes = size_kb * 1024

        if size_bytes < data_length:
            raise ValueError("Inconsistent pack size byte in pack image file")

        # Create data buffer and copy content
        self._data = bytearray(size_bytes)
        for i in range(6, len(data)):
            self._data[i - 6] = data[i]
        # Fill rest with 0xFF
        for i in range(len(data) - 6, size_bytes):
            self._data[i] = 0xFF

        # Determine pack type from header
        pack_type = PackType.EPROM
        paged = size_kb >= 32
        segmented = size_kb >= 128

        # Check pack header (if not ORG1 format where first byte is 251/0xFB)
        if self._data[0] != 0xFB:
            r = self._data[0]
            paged = (r & 0x04) != 0
            if (r & 0x02) == 0:
                pack_type = PackType.RAM
            if (r & 0x40) == 0:
                pack_type = PackType.FLASH
            segmented = self._data[1] >= 16  # 128K or larger

        self._prepare_hardware(pack_type, segmented, paged, size_bytes)
        self._changed = False
        self._is_ready = True

    @classmethod
    def from_opk(cls, path_or_data) -> "Pack":
        """
        Create pack from OPK file.

        Args:
            path_or_data: Path to .opk file, or bytes data

        Returns:
            Configured Pack instance
        """
        if isinstance(path_or_data, str):
            from pathlib import Path
            data = Path(path_or_data).read_bytes()
            name = Path(path_or_data).stem
        elif hasattr(path_or_data, 'read_bytes'):
            # Path-like object
            data = path_or_data.read_bytes()
            name = path_or_data.stem
        else:
            # Assume bytes
            data = path_or_data
            name = "Pack"

        return cls(data=data, name=name)

    @classmethod
    def create_blank(
        cls,
        name: str,
        pack_type: PackType,
        size_kb: int
    ) -> "Pack":
        """
        Create a blank pack of specified type and size.

        Args:
            name: Pack name
            pack_type: Type of pack (EPROM, RAM, Flash)
            size_kb: Size in kilobytes (8, 16, 32, 64, 128)

        Returns:
            Blank Pack instance
        """
        return cls(data=bytes(), name=name, pack_type=pack_type, size_kb=size_kb)

    # =========================================================================
    # Properties
    # =========================================================================

    def is_ready(self) -> bool:
        """Check if pack is ready for use."""
        return self._is_ready

    def name(self) -> str:
        """Get pack name."""
        return self._name

    @property
    def size(self) -> int:
        """Get pack size in bytes."""
        return len(self._data) if self._data else 0

    @property
    def has_changed(self) -> bool:
        """Check if pack contents have been modified."""
        return self._changed

    # =========================================================================
    # I/O Interface
    # =========================================================================

    def reset(self) -> None:
        """Reset pack state (address counter)."""
        self._counter.reset()

    def write_control_port(self, control: int, databus: int) -> bool:
        """
        Handle control port write from bus.

        This is the main interface for pack access. The bus calls this
        when port 2 or port 6 changes to perform pack operations.

        Args:
            control: Control pins state (from port 6 + flags)
            databus: Data bus value (from port 2)

        Returns:
            True if a write operation was performed (consumes 21V charge)
        """
        if self._data is None:
            return False

        # Save previous address for debugging
        prev_addr = self._counter.address

        # Update address counter based on control pins
        self._counter.control_port(control, databus)

        # Get command type from controller
        cmd = self._controller.control_port(control, databus)

        # Handle hardware ID reads
        if cmd == CommandType.ID_BYTE_1 or cmd == CommandType.ID_BYTE_2:
            hw_id = self._controller.get_hardware_id()
            if hw_id >= 0:
                if cmd == CommandType.ID_BYTE_1:
                    self._output_data_bus = hw_id & 0xFF
                else:
                    self._output_data_bus = (hw_id >> 8) & 0xFF
                return False
            else:
                # Fall through to read if no hardware ID
                cmd = CommandType.READ

        # Handle read
        if cmd == CommandType.READ:
            self._output_data_bus = self.read_byte(self._counter.address)
            return False

        # Handle write
        if cmd == CommandType.WRITE:
            self.write_byte(self._counter.address, databus)
            return True

        return False

    def read_data_bus(self) -> int:
        """
        Read current data bus value.

        Returns the last value output by the pack (from read or ID command).

        Returns:
            Data bus value (0-255)
        """
        return self._output_data_bus

    def read_byte(self, address: int) -> int:
        """
        Read byte from pack memory at address.

        Args:
            address: Memory address

        Returns:
            Byte value, or 0xFF if out of range
        """
        if self._data is None or address >= len(self._data):
            return 0xFF
        return self._data[address]

    def write_byte(self, address: int, value: int) -> None:
        """
        Write byte to pack memory at address.

        Args:
            address: Memory address
            value: Byte value to write
        """
        if self._data is not None and address < len(self._data):
            if self._data[address] != (value & 0xFF):
                self._changed = True
            self._data[address] = value & 0xFF

    # =========================================================================
    # Data Access
    # =========================================================================

    def get_data(self) -> Optional[bytes]:
        """Get raw pack data."""
        return bytes(self._data) if self._data else None

    def to_opk(self) -> bytes:
        """
        Export pack as OPK format data.

        Returns:
            OPK-formatted bytes
        """
        if self._data is None:
            raise ValueError("Pack has no data")

        # Find actual data length (trim trailing 0xFF)
        ln = len(self._data)
        while ln > 2 and self._data[ln - 3] == 0xFF:
            ln -= 1

        # Build OPK header
        result = bytearray(ln + 6)
        result[0] = 79  # 'O'
        result[1] = 80  # 'P'
        result[2] = 75  # 'K'
        result[3] = (ln - 2) >> 16
        result[4] = ((ln - 2) >> 8) & 0xFF
        result[5] = (ln - 2) & 0xFF

        # Copy data
        for i in range(ln):
            result[i + 6] = self._data[i]

        return bytes(result)

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def get_snapshot_data(self) -> List[int]:
        """
        Get pack state for snapshot.

        Includes counter state and output data bus.
        """
        # Note: Full snapshot would include all pack data, but that could
        # be very large. For now, just save minimal state.
        return [
            self._output_data_bus,
            self._counter.address & 0xFF,
            (self._counter.address >> 8) & 0xFF,
            (self._counter.address >> 16) & 0xFF,
        ]

    def apply_snapshot_data(self, data: List[int], offset: int = 0) -> int:
        """
        Restore pack state from snapshot.

        Returns:
            Number of bytes consumed
        """
        self._output_data_bus = data[offset]
        # Note: Counter address restoration would need counter-specific handling
        # For now, just reset the counter
        self._counter.reset()
        return 4
