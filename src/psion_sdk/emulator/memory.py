"""
Memory Subsystem for Psion Organiser II Emulator
=================================================

Ported from JAPE's memory.js with Python idioms.

Memory Map:
    $0000-$003F  Processor internal registers (handled by bus.py)
    $0040-$00FF  Processor RAM (zero page, fast access)
    $0100-$03FF  Semi-custom chip I/O (handled by bus.py)
    $0400-$1FFF  System RAM (varies by model)
    $2000-$7FFF  Extended RAM (banked on LZ models)
    $8000-$FFFF  ROM (banked on some models)

RAM configurations:
    - 8K:  0x2000-0x4000 (CM)
    - 16K: 0x2000-0x6000 (XP)
    - 32K+: 0x0000-0x8000 (LZ, with bank switching)

ROM configuration:
    - Always at 0x8000-0xFFFF (32KB)
    - Multiple ROM banks supported via bank switching

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from dataclasses import dataclass, field
from typing import Optional


class Ram:
    """
    RAM memory with bank switching support.

    The Psion uses different RAM configurations:
    - 8KB: Maps to $2000-$4000
    - 16KB: Maps to $2000-$6000
    - 32KB+: Maps to $0000-$8000 with bank switching above $4000

    Bank switching allows accessing additional RAM banks above the
    first 16KB. Each bank switch replaces the $4000-$8000 region.

    Attributes:
        size_kb: RAM size in kilobytes
    """

    # Processor RAM is at $40-$FF (196 bytes)
    PROCESSOR_RAM_LOW = 0x40
    PROCESSOR_RAM_HIGH = 0x100

    # Banks start at $4000
    BANK_ADDRESS = 0x4000

    def __init__(self, size_kb: int):
        """
        Initialize RAM.

        Args:
            size_kb: RAM size in KB (8, 16, 32, 64, or 96)
        """
        self.size_kb = size_kb

        # Determine address range based on size
        if size_kb == 8:
            self._low_address = 0x2000
            self._high_address = 0x4000
            # Actual data size includes processor RAM
            self._size = 16  # 16KB buffer
        elif size_kb == 16:
            self._low_address = 0x2000
            self._high_address = 0x6000
            self._size = 24  # 24KB buffer
        else:  # 32, 64, 96
            self._low_address = 0x0000
            self._high_address = 0x8000
            self._size = size_kb

        # Allocate RAM buffer
        self._data = bytearray(self._size * 1024)

        # Bank index points into _data for bank-switched region
        self._current_bank_index = self.BANK_ADDRESS

    def read(self, address: int) -> int:
        """
        Read byte from RAM.

        Args:
            address: 16-bit address

        Returns:
            Byte value at address, or 0xFF if outside RAM
        """
        # Processor RAM ($40-$FF)
        if self.PROCESSOR_RAM_LOW <= address < self.PROCESSOR_RAM_HIGH:
            return self._data[address]

        # Outside RAM range
        if address >= self._high_address or address < self._low_address:
            return 0xFF

        # Below bank-switched region
        if address < self.BANK_ADDRESS:
            return self._data[address]

        # Bank-switched region
        return self._data[address - self.BANK_ADDRESS + self._current_bank_index]

    def write(self, address: int, value: int) -> None:
        """
        Write byte to RAM.

        Args:
            address: 16-bit address
            value: Byte value to write
        """
        value = value & 0xFF

        # Processor RAM ($40-$FF)
        if self.PROCESSOR_RAM_LOW <= address < self.PROCESSOR_RAM_HIGH:
            self._data[address] = value
            return

        # Outside RAM range - ignore writes
        if address >= self._high_address or address < self._low_address:
            return

        # Below bank-switched region
        if address < self.BANK_ADDRESS:
            self._data[address] = value
            return

        # Bank-switched region
        self._data[address - self.BANK_ADDRESS + self._current_bank_index] = value

    def next_bank(self) -> None:
        """Switch to next RAM bank (wraps around)."""
        self._current_bank_index += self.BANK_ADDRESS
        if self._current_bank_index >= len(self._data):
            self._current_bank_index = self.BANK_ADDRESS

    def reset_bank(self) -> None:
        """Reset to first RAM bank."""
        self._current_bank_index = self.BANK_ADDRESS

    def get_snapshot_data(self) -> list[int]:
        """Get RAM state for snapshot."""
        result = [
            len(self._data) // 1024,  # Size in KB
            (self._current_bank_index >> 8) & 0xFF,
            self._current_bank_index & 0xFF,
            (self._low_address >> 8) & 0xFF,
            self._low_address & 0xFF,
            (self._high_address >> 8) & 0xFF,
            self._high_address & 0xFF,
        ]
        # Processor RAM
        result.extend(self._data[self.PROCESSOR_RAM_LOW:self.PROCESSOR_RAM_HIGH])
        # Main RAM
        result.extend(self._data[self._low_address:len(self._data)])
        return result

    def apply_snapshot_data(self, data: list[int], offset: int = 0) -> int:
        """Restore RAM state from snapshot."""
        size = data[offset]
        self._data = bytearray(size * 1024)
        self._current_bank_index = (data[offset + 1] << 8) | data[offset + 2]
        self._low_address = (data[offset + 3] << 8) | data[offset + 4]
        self._high_address = (data[offset + 5] << 8) | data[offset + 6]

        pos = offset + 7
        # Processor RAM
        for i in range(self.PROCESSOR_RAM_LOW, self.PROCESSOR_RAM_HIGH):
            self._data[i] = data[pos]
            pos += 1
        # Main RAM
        for i in range(self._low_address, len(self._data)):
            self._data[i] = data[pos]
            pos += 1

        return pos - offset


class Rom:
    """
    ROM memory with bank switching support.

    ROM is mapped to $8000-$FFFF (32KB visible at a time).
    Bank switching allows accessing additional ROM banks beyond
    the first 32KB.

    Bank layout:
    - Bank 0: First 32KB, always visible at $C000-$FFFF
    - Banks 1+: Mapped to $8000-$BFFF via bank switching

    Attributes:
        data: Raw ROM data bytes
    """

    LOW_ADDRESS = 0x8000
    HIGH_ADDRESS = 0x10000  # One past highest address
    BANK_SIZE = 0x4000  # 16KB per bank

    def __init__(self, data: bytes):
        """
        Initialize ROM with data.

        Args:
            data: Raw ROM bytes (typically 32KB or more)
        """
        self._data = data
        self._size = len(data)
        self._current_bank_index = 0

    def read(self, address: int) -> int:
        """
        Read byte from ROM.

        Args:
            address: 16-bit address

        Returns:
            Byte value at address, or -1 if outside ROM
        """
        if not (self.LOW_ADDRESS <= address < self.HIGH_ADDRESS):
            return -1

        index = address - self.LOW_ADDRESS

        # Upper 16KB ($C000-$FFFF) always comes from start of ROM
        # Lower 16KB ($8000-$BFFF) comes from bank-switched region
        if index >= self.BANK_SIZE or self._current_bank_index == 0:
            return self._data[index] if index < self._size else 0xFF
        else:
            bank_index = index + self._current_bank_index
            return self._data[bank_index] if bank_index < self._size else 0xFF

    def next_bank(self) -> None:
        """Switch to next ROM bank."""
        if self._current_bank_index == 0:
            self._current_bank_index = 0x8000  # Skip first 32KB
        else:
            self._current_bank_index += self.BANK_SIZE

        if self._current_bank_index >= self._size:
            self._current_bank_index = 0

    def reset_bank(self) -> None:
        """Reset to first ROM bank."""
        self._current_bank_index = 0

    def get_snapshot_data(self) -> list[int]:
        """Get ROM bank state for snapshot (doesn't save ROM data)."""
        return [
            (self._current_bank_index >> 8) & 0xFF,
            self._current_bank_index & 0xFF,
        ]

    def apply_snapshot_data(self, data: list[int], offset: int = 0) -> int:
        """Restore ROM bank state from snapshot."""
        self._current_bank_index = (data[offset] << 8) | data[offset + 1]
        return 2


class Memory:
    """
    Unified memory interface combining RAM and ROM.

    Provides a simple read/write interface that routes to the
    appropriate memory component based on address.

    Address routing:
        $0000-$7FFF: RAM (with bank switching for 32KB+ configs)
        $8000-$FFFF: ROM (with bank switching)

    Note: Processor registers ($00-$3F) and semi-custom chip ($100-$3FF)
    are handled by the Bus class, not Memory.

    Attributes:
        ram: Ram instance
        rom: Rom instance
    """

    def __init__(self, ram_size_kb: int, rom_data: Optional[bytes] = None):
        """
        Initialize memory subsystem.

        Args:
            ram_size_kb: RAM size in KB (8, 16, 32, 64, 96)
            rom_data: ROM image bytes (or None for empty ROM)
        """
        self.ram = Ram(ram_size_kb)
        self.rom = Rom(rom_data or bytes(0x8000))

    def read(self, address: int) -> int:
        """
        Read byte from memory.

        Args:
            address: 16-bit address

        Returns:
            Byte value at address
        """
        if address >= 0x8000:
            return self.rom.read(address)
        return self.ram.read(address)

    def write(self, address: int, value: int) -> None:
        """
        Write byte to memory.

        Only writes to RAM are allowed. ROM writes are ignored.

        Args:
            address: 16-bit address
            value: Byte value to write
        """
        self.ram.write(address, value)

    def next_ram(self) -> None:
        """Switch to next RAM bank."""
        self.ram.next_bank()

    def next_rom(self) -> None:
        """Switch to next ROM bank."""
        self.rom.next_bank()

    def reset_bank(self) -> None:
        """Reset all memory banks to initial state."""
        self.ram.reset_bank()
        self.rom.reset_bank()

    def get_snapshot_data(self) -> list[int]:
        """Get complete memory state for snapshot."""
        result = []
        result.extend(self.rom.get_snapshot_data())
        result.extend(self.ram.get_snapshot_data())
        return result

    def apply_snapshot_data(self, data: list[int], offset: int = 0) -> int:
        """Restore memory state from snapshot."""
        consumed = self.rom.apply_snapshot_data(data, offset)
        consumed += self.ram.apply_snapshot_data(data, offset + consumed)
        return consumed

    def is_ready(self) -> bool:
        """Check if memory is ready (always true for Python implementation)."""
        return True
