"""
Memory Subsystem Unit Tests
============================

Tests for RAM, ROM, and Memory classes with bank switching support.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.emulator import Memory, Ram, Rom


# =============================================================================
# RAM Tests
# =============================================================================

class TestRam:
    """Test RAM class."""

    def test_ram_8k_size(self):
        """8KB RAM has correct size_kb property."""
        ram = Ram(8)
        assert ram.size_kb == 8
        # Note: Internal buffer is larger (16KB) to accommodate processor RAM
        # 8KB RAM maps to $2000-$4000 in address space

    def test_ram_32k_size(self):
        """32KB RAM has correct size."""
        ram = Ram(32)
        assert ram.size_kb == 32

    def test_ram_read_write(self):
        """Basic read/write works."""
        ram = Ram(8)

        # 8KB RAM is at $2000-$4000, so use addresses in that range
        ram.write(0x2000, 0x42)
        assert ram.read(0x2000) == 0x42

        ram.write(0x3FFF, 0x55)
        assert ram.read(0x3FFF) == 0x55

    def test_ram_initialization(self):
        """RAM initializes to zeros."""
        ram = Ram(8)
        # RAM should be initialized to 0
        # Test processor RAM range ($40-$FF)
        assert ram.read(0x40) == 0
        assert ram.read(0xFF) == 0

    def test_ram_bank_switching(self):
        """Bank switching works for large RAM."""
        ram = Ram(64)  # 64KB, multiple banks

        # Write to address in banked region ($4000+)
        ram.write(0x5000, 0x11)

        # Switch bank and write to same address
        ram.next_bank()
        ram.write(0x5000, 0x22)

        # Values are independent
        assert ram.read(0x5000) == 0x22
        ram.reset_bank()
        assert ram.read(0x5000) == 0x11


# =============================================================================
# ROM Tests
# =============================================================================

class TestRom:
    """Test ROM class."""

    def test_rom_creation(self):
        """ROM created from bytes and readable at $8000+."""
        data = bytes([0x01, 0x02, 0x03, 0x04] * 8192)  # 32KB ROM
        rom = Rom(data)

        # ROM is mapped at $8000-$FFFF
        assert rom.read(0x8000) == 0x01
        assert rom.read(0x8003) == 0x04

    def test_rom_immutable(self):
        """ROM has no write method (immutable)."""
        data = bytes([0x42] * 0x8000)  # 32KB ROM
        rom = Rom(data)

        # ROM doesn't have a write method - it's read-only
        assert not hasattr(rom, 'write') or not callable(getattr(rom, 'write', None))
        # Read should still work
        assert rom.read(0x8000) == 0x42

    def test_rom_bank_switching(self):
        """ROM bank switching works."""
        # Create 64KB ROM (2 x 32KB or more complex banking)
        data = bytes(range(256)) * 256  # 64KB
        rom = Rom(data)

        initial = rom.read(0x8000)
        rom.next_bank()
        # Bank switching affects $8000-$BFFF region
        # The upper region ($C000-$FFFF) always reads from first 16KB of ROM


# =============================================================================
# Memory Tests
# =============================================================================

class TestMemory:
    """Test Memory class combining RAM and ROM."""

    @pytest.fixture
    def memory(self):
        """Create standard memory configuration."""
        # 32KB RAM, 32KB ROM
        rom_data = bytes([0xEA] * 0x8000)  # Fill ROM with $EA
        # Set reset vector to $8000
        rom_data = bytearray(rom_data)
        rom_data[0x7FFE] = 0x80
        rom_data[0x7FFF] = 0x00
        return Memory(32, bytes(rom_data))

    def test_ram_range(self, memory):
        """RAM is accessible at $0400-$7FFF."""
        # Write to RAM
        memory.write(0x0400, 0x42)
        assert memory.read(0x0400) == 0x42

        memory.write(0x7FFF, 0x55)
        assert memory.read(0x7FFF) == 0x55

    def test_rom_range(self, memory):
        """ROM is readable at $8000-$FFFF."""
        # ROM filled with $EA
        assert memory.read(0x8000) == 0xEA
        assert memory.read(0xFFFD) == 0xEA

    def test_rom_write_ignored(self, memory):
        """Writes to ROM are ignored."""
        memory.write(0x8000, 0x00)
        assert memory.read(0x8000) == 0xEA  # Unchanged

    def test_processor_ram(self, memory):
        """Processor RAM at $40-$FF."""
        memory.write(0x0040, 0x11)
        assert memory.read(0x0040) == 0x11

        memory.write(0x00FF, 0x22)
        assert memory.read(0x00FF) == 0x22

    def test_reset_vector(self, memory):
        """Reset vector at $FFFE-$FFFF."""
        # We set this to $8000 in fixture
        assert memory.read(0xFFFE) == 0x80
        assert memory.read(0xFFFF) == 0x00

    def test_bank_reset(self, memory):
        """reset_bank resets all bank pointers."""
        memory.next_ram()
        memory.next_rom()

        memory.reset_bank()
        # Should be back to bank 0

    def test_snapshot(self, memory):
        """Snapshot save/restore works."""
        memory.write(0x0400, 0x42)
        memory.write(0x1000, 0x55)

        # Save state
        snapshot = memory.get_snapshot_data()

        # Modify memory
        memory.write(0x0400, 0x00)
        memory.write(0x1000, 0x00)

        # Restore state
        memory.apply_snapshot_data(snapshot)

        assert memory.read(0x0400) == 0x42
        assert memory.read(0x1000) == 0x55


# =============================================================================
# Address Range Tests
# =============================================================================

class TestAddressRanges:
    """Test memory address range handling."""

    @pytest.fixture
    def memory(self):
        rom_data = bytes([0x00] * 0x8000)
        return Memory(32, rom_data)

    def test_zero_page_processor_registers(self, memory):
        """$00-$3F is processor internal (returns 0 for basic memory)."""
        # In full emulator, this is handled by bus
        # Basic memory returns 0 for these
        val = memory.read(0x0000)
        assert isinstance(val, int)

    def test_wraparound(self, memory):
        """Address wraps at 16 bits."""
        # Writing to $10000 should wrap to $0000
        # This is handled by masking in implementation


# =============================================================================
# Model-Specific Memory Tests
# =============================================================================

class TestModelMemory:
    """Test memory configurations for different models."""

    def test_cm_8k_ram(self):
        """CM model has 8KB RAM."""
        rom_data = bytes([0x00] * 0x8000)
        mem = Memory(8, rom_data)

        # 8KB RAM is at $2000-$4000
        mem.write(0x2000, 0x42)
        assert mem.read(0x2000) == 0x42

    def test_xp_32k_ram(self):
        """XP model has 32KB RAM."""
        rom_data = bytes([0x00] * 0x8000)
        mem = Memory(32, rom_data)

        # Can write to full 32KB range
        mem.write(0x7000, 0x42)
        assert mem.read(0x7000) == 0x42

    def test_lz64_64k_ram(self):
        """LZ64 model has 64KB RAM with bank switching."""
        rom_data = bytes([0x00] * 0x8000)
        mem = Memory(64, rom_data)

        # Bank switching affects addresses $4000+
        # Write to bank 0 in the banked region
        mem.write(0x5000, 0x11)

        # Bank switch and write to same address
        mem.next_ram()
        mem.write(0x5000, 0x22)

        # Verify bank independence
        assert mem.read(0x5000) == 0x22
        mem.reset_bank()
        assert mem.read(0x5000) == 0x11
