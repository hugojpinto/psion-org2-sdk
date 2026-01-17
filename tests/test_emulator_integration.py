"""
Emulator Integration Tests
==========================

Tests for the complete emulator system, verifying that all components
work together correctly.

These tests ensure:
- Emulator instantiation with different models
- Program loading and execution
- Display output verification
- Keyboard input handling
- Breakpoint integration
- Snapshot save/restore

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from pathlib import Path
import tempfile

from psion_sdk.emulator import (
    Emulator,
    EmulatorConfig,
    BreakReason,
    RegisterCondition,
    get_model,
    MODEL_XP,
    MODEL_LZ,
)


# =============================================================================
# Fixture for ROM path detection
# =============================================================================

def get_test_rom_path():
    """Get path to test ROMs if available."""
    # Check emulator/roms directory first (primary location)
    emulator_rom_dir = Path(__file__).parent.parent / "src" / "psion_sdk" / "emulator" / "roms"
    if emulator_rom_dir.exists():
        for rom in emulator_rom_dir.glob("*.rom"):
            return rom
    # Fall back to thirdparty location
    thirdparty_rom_dir = Path(__file__).parent.parent / "thirdparty" / "jape" / "roms"
    if thirdparty_rom_dir.exists():
        for rom in thirdparty_rom_dir.glob("*.rom"):
            return rom
    return None


# Skip if no ROM available
requires_rom = pytest.mark.skipif(
    get_test_rom_path() is None,
    reason="No ROM files available for testing"
)


# =============================================================================
# Emulator Initialization Tests
# =============================================================================

class TestEmulatorInit:
    """Test emulator initialization."""

    @requires_rom
    def test_default_config(self):
        """Default config creates XP emulator."""
        emu = Emulator()
        assert emu.model.model_type == "XP"

    @requires_rom
    def test_custom_model(self):
        """Can specify different models."""
        # Test with XP (should always have ROM)
        emu = Emulator(EmulatorConfig(model="XP"))
        assert emu.model.model_type == "XP"

    @requires_rom
    def test_reset(self):
        """Reset initializes to known state."""
        emu = Emulator()
        emu.reset()

        # PC should be set from reset vector
        assert emu.cpu.pc >= 0x8000
        # Display should be on
        assert emu.display.is_on

    def test_invalid_model(self):
        """Invalid model raises error."""
        with pytest.raises((ValueError, KeyError)):
            Emulator(EmulatorConfig(model="INVALID"))


# =============================================================================
# Code Injection Tests
# =============================================================================

class TestCodeInjection:
    """Test program injection without ROMs."""

    @pytest.fixture
    def emu(self):
        """Create emulator with minimal setup."""
        # Create minimal ROM (just reset vector pointing to injected code)
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20  # Reset vector high
        rom_data[0x7FFF] = 0x00  # Reset vector low -> $2000

        # Create emulator with custom ROM
        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_inject_simple_code(self, emu):
        """Inject and execute simple code."""
        # LDAA #$42, NOP, NOP
        code = bytes([0x86, 0x42, 0x01, 0x01])
        emu.inject_program(code, entry_point=0x2000)

        # Step through
        emu.step()

        assert emu.cpu.a == 0x42

    def test_inject_arithmetic(self, emu):
        """Inject arithmetic code."""
        # LDAA #$10, LDAB #$20, ABA (add B to A)
        code = bytes([
            0x86, 0x10,  # LDAA #$10
            0xC6, 0x20,  # LDAB #$20
            0x1B,        # ABA
        ])
        emu.inject_program(code, entry_point=0x2000)

        # Execute
        emu.step()  # LDAA
        emu.step()  # LDAB
        emu.step()  # ABA

        assert emu.cpu.a == 0x30  # $10 + $20 = $30

    def test_inject_loop(self, emu):
        """Inject loop code."""
        # LDAA #$05, DECA, BNE -2 (loop 5 times)
        code = bytes([
            0x86, 0x05,  # LDAA #$05
            0x4A,        # DECA
            0x26, 0xFD,  # BNE -3 (back to DECA)
        ])
        emu.inject_program(code, entry_point=0x2000)

        # Add breakpoint when A == 0
        emu.add_condition('a', '==', 0)

        # Run until breakpoint
        event = emu.run(10000)

        assert event.reason == BreakReason.REGISTER_CONDITION
        assert emu.cpu.a == 0

    def test_memory_operations(self, emu):
        """Test memory read/write."""
        # Write value to RAM
        emu.write_byte(0x0500, 0x42)
        assert emu.read_byte(0x0500) == 0x42

        # Write word
        emu.write_word(0x0510, 0x1234)
        assert emu.read_word(0x0510) == 0x1234
        assert emu.read_byte(0x0510) == 0x12
        assert emu.read_byte(0x0511) == 0x34


# =============================================================================
# Breakpoint Integration Tests
# =============================================================================

class TestBreakpointIntegration:
    """Test breakpoints with running emulator."""

    @pytest.fixture
    def emu(self):
        """Create emulator for breakpoint testing."""
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_pc_breakpoint(self, emu):
        """PC breakpoint stops execution."""
        # Fill with NOPs
        code = bytes([0x01] * 100)  # 100 NOPs
        emu.inject_program(code, entry_point=0x2000)

        # Set breakpoint at NOP #10
        emu.add_breakpoint(0x200A)

        event = emu.run(10000)

        assert event.reason == BreakReason.PC_BREAKPOINT
        assert event.address == 0x200A

    def test_remove_breakpoint(self, emu):
        """Removed breakpoint doesn't trigger."""
        code = bytes([0x01] * 100)
        emu.inject_program(code, entry_point=0x2000)

        emu.add_breakpoint(0x200A)
        emu.remove_breakpoint(0x200A)

        event = emu.run(50)  # Short run

        assert event.reason == BreakReason.MAX_CYCLES

    def test_register_condition(self, emu):
        """Register condition breakpoint."""
        # LDAA #$00, LDAB #$10
        code = bytes([
            0x86, 0x05,  # LDAA #$05
            0x4A,        # DECA
            0x26, 0xFD,  # BNE -3
            0x01,        # NOP (after loop)
        ])
        emu.inject_program(code, entry_point=0x2000)

        cond_id = emu.add_condition('a', '==', 0)
        event = emu.run(10000)

        assert event.reason == BreakReason.REGISTER_CONDITION
        assert emu.cpu.a == 0

    def test_run_until_pc(self, emu):
        """run_until_pc stops at target."""
        code = bytes([0x01] * 50)  # NOPs
        emu.inject_program(code, entry_point=0x2000)

        result = emu.run_until_pc(0x2020)

        assert result is True
        assert emu.cpu.pc == 0x2020

    def test_clear_breakpoints(self, emu):
        """clear_breakpoints removes all."""
        emu.add_breakpoint(0x2000)
        emu.add_breakpoint(0x2010)
        emu.add_condition('a', '==', 0)

        emu.clear_breakpoints()

        # Should run to max cycles without breaking
        code = bytes([0x01] * 100)
        emu.inject_program(code, entry_point=0x2000)
        event = emu.run(50)

        assert event.reason == BreakReason.MAX_CYCLES


# =============================================================================
# Register Access Tests
# =============================================================================

class TestRegisterAccess:
    """Test register access through emulator."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_registers_property(self, emu):
        """registers property returns dict."""
        # Set some values
        code = bytes([0x86, 0x42, 0xC6, 0x55])  # LDAA #$42, LDAB #$55
        emu.inject_program(code, entry_point=0x2000)
        emu.step()
        emu.step()

        regs = emu.registers

        assert regs['a'] == 0x42
        assert regs['b'] == 0x55
        assert 'pc' in regs
        assert 'sp' in regs
        assert 'x' in regs

    def test_total_cycles(self, emu):
        """total_cycles tracks execution."""
        # Set up valid stack pointer in RAM before running
        emu.cpu.sp = 0x7FF0

        emu.inject_program(bytes([0x01] * 10), entry_point=0x2000)

        assert emu.total_cycles == 0

        emu.run(100)

        assert emu.total_cycles > 0


# =============================================================================
# Snapshot Tests
# =============================================================================

class TestSnapshot:
    """Test snapshot save/restore."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_snapshot_roundtrip(self, emu):
        """Save and load snapshot preserves state."""
        # Set up state
        code = bytes([0x86, 0x42, 0xC6, 0x55])
        emu.inject_program(code, entry_point=0x2000)
        emu.step()
        emu.step()

        # Save snapshot
        with tempfile.NamedTemporaryFile(suffix='.snap', delete=False) as f:
            snap_path = Path(f.name)

        try:
            emu.save_snapshot(snap_path)

            # Change state
            emu.cpu.a = 0x00
            emu.cpu.b = 0x00

            # Load snapshot
            emu.load_snapshot(snap_path)

            assert emu.cpu.a == 0x42
            assert emu.cpu.b == 0x55
        finally:
            snap_path.unlink()

    def test_invalid_snapshot(self, emu):
        """Loading invalid snapshot raises error."""
        with tempfile.NamedTemporaryFile(suffix='.snap', delete=False) as f:
            f.write(b"invalid data")
            snap_path = Path(f.name)

        try:
            with pytest.raises(ValueError):
                emu.load_snapshot(snap_path)
        finally:
            snap_path.unlink()

    def test_nonexistent_snapshot(self, emu):
        """Loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            emu.load_snapshot(Path("/nonexistent/path.snap"))


# =============================================================================
# Display Integration Tests
# =============================================================================

class TestDisplayIntegration:
    """Test display through emulator API."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_display_text_empty(self, emu):
        """Display text is accessible."""
        text = emu.display_text
        assert isinstance(text, str)

    def test_display_lines(self, emu):
        """Display lines returns list."""
        lines = emu.display_lines
        assert isinstance(lines, list)
        assert len(lines) == 2  # Default is 2-line display

    def test_display_pixels(self, emu):
        """Display pixels returns bytes."""
        pixels = emu.display_pixels
        assert isinstance(pixels, bytes)


# =============================================================================
# Keyboard Integration Tests
# =============================================================================

class TestKeyboardIntegration:
    """Test keyboard through emulator API."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_press_release_key(self, emu):
        """Can press and release keys."""
        emu.press_key('A')
        assert emu.keyboard.is_key_down('A')

        emu.release_key('A')
        assert not emu.keyboard.is_key_down('A')

    def test_tap_key(self, emu):
        """tap_key presses and releases."""
        # Fill with simple loop
        code = bytes([0x01] * 1000)  # NOPs
        emu.inject_program(code, entry_point=0x2000)
        # Set up valid stack pointer in RAM
        emu.cpu.sp = 0x7FF0

        initial_cycles = emu.total_cycles

        # tap_key runs for some cycles
        emu.tap_key('A', hold_cycles=100)

        # Key should be released after tap
        assert not emu.keyboard.is_key_down('A')
        # Cycles should have increased from running
        assert emu.total_cycles > initial_cycles


# =============================================================================
# Model Configuration Tests
# =============================================================================

class TestModelConfiguration:
    """Test different Psion models."""

    def test_model_properties(self):
        """Model has expected properties."""
        model = get_model("XP")

        assert model.ram_kb in [16, 32]
        assert model.display_lines == 2
        assert model.display_cols == 16

    def test_lz_model_properties(self):
        """LZ model has 4-line display."""
        model = get_model("LZ")

        assert model.display_lines == 4
        assert model.display_cols == 20


# =============================================================================
# Disassembly Tests
# =============================================================================

class TestDisassembly:
    """Test disassembly functionality."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_disassemble_at(self, emu):
        """disassemble_at returns disassembly."""
        code = bytes([
            0x86, 0x42,  # LDAA #$42
            0x01,        # NOP
            0x39,        # RTS
        ])
        emu.inject_program(code, entry_point=0x2000)

        disasm = emu.disassemble_at(0x2000, count=3)

        assert len(disasm) >= 2
        assert '$2000' in disasm[0].upper()


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def emu(self):
        rom_data = bytearray([0x00] * 0x8000)
        rom_data[0x7FFE] = 0x20
        rom_data[0x7FFF] = 0x00

        with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
            f.write(bytes(rom_data))
            rom_path = Path(f.name)

        try:
            emu = Emulator(EmulatorConfig(rom_path=rom_path))
            emu.reset()
            yield emu
        finally:
            rom_path.unlink()

    def test_run_zero_cycles(self, emu):
        """Running 0 cycles is safe."""
        event = emu.run(0)
        assert event.reason == BreakReason.MAX_CYCLES

    def test_step_multiple_times(self, emu):
        """Multiple steps work."""
        code = bytes([0x01] * 10)
        emu.inject_program(code, entry_point=0x2000)

        for _ in range(5):
            event = emu.step()
            assert event.reason == BreakReason.STEP

    def test_emulator_repr(self, emu):
        """Emulator has string representation."""
        s = repr(emu)
        assert "Emulator" in s
