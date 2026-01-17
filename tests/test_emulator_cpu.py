"""
HD6303 CPU Unit Tests
=====================

Comprehensive tests for the HD6303 CPU emulator, covering:
- Register operations
- Flag behavior
- All instruction groups
- Addressing modes
- Interrupt handling
- Stack operations

These tests verify that the Python port matches JAPE's behavior exactly.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.emulator import HD6303, Flags, CPUState


# =============================================================================
# Mock Bus for CPU Testing
# =============================================================================

class MockBus:
    """
    Simple mock bus for CPU testing.

    Provides 64KB of flat memory with no I/O behavior.
    Tracks all reads and writes for verification.
    """

    def __init__(self):
        self._memory = bytearray(0x10000)  # 64KB
        self._reads: list[tuple[int, int]] = []  # (address, value)
        self._writes: list[tuple[int, int]] = []  # (address, value)
        self._nmi_pending = False
        self._oci_pending = False
        self._switched_off = False

    def read(self, address: int) -> int:
        """Read byte from address."""
        address &= 0xFFFF
        value = self._memory[address]
        self._reads.append((address, value))
        return value

    def write(self, address: int, value: int) -> None:
        """Write byte to address."""
        address &= 0xFFFF
        value &= 0xFF
        self._memory[address] = value
        self._writes.append((address, value))

    def is_nmi_due(self) -> bool:
        """Check if NMI is pending."""
        return self._nmi_pending

    def is_oci_due(self) -> bool:
        """Check if OCI is pending."""
        return self._oci_pending

    def inc_frame(self, ticks: int) -> None:
        """Advance timing (no-op for mock)."""
        pass

    def is_switched_off(self) -> bool:
        """Check if switched off."""
        return self._switched_off

    def load_program(self, address: int, data: bytes) -> None:
        """Helper to load program bytes."""
        for i, b in enumerate(data):
            self._memory[(address + i) & 0xFFFF] = b

    def clear_history(self) -> None:
        """Clear read/write history."""
        self._reads.clear()
        self._writes.clear()


# =============================================================================
# CPU Fixture
# =============================================================================

@pytest.fixture
def cpu():
    """Create CPU with mock bus for testing."""
    bus = MockBus()
    cpu = HD6303(bus)
    # Set up reset vector to point to 0x8000
    bus.write(0xFFFE, 0x80)
    bus.write(0xFFFF, 0x00)
    cpu.reset()
    bus.clear_history()
    return cpu


# =============================================================================
# Register Tests
# =============================================================================

class TestRegisters:
    """Test CPU register access and masking."""

    def test_a_register_8bit(self, cpu):
        """A register is 8-bit (masked to 0-255)."""
        cpu.a = 0x42
        assert cpu.a == 0x42

        cpu.a = 0x1FF  # 9-bit value
        assert cpu.a == 0xFF  # Masked to 8 bits

        cpu.a = -1  # Negative
        assert cpu.a == 0xFF  # Two's complement

    def test_b_register_8bit(self, cpu):
        """B register is 8-bit."""
        cpu.b = 0x42
        assert cpu.b == 0x42

        cpu.b = 0x100
        assert cpu.b == 0x00  # Overflow wraps

    def test_d_register_combined(self, cpu):
        """D register is A:B combined (16-bit)."""
        cpu.a = 0x12
        cpu.b = 0x34
        assert cpu.d == 0x1234

        cpu.d = 0xABCD
        assert cpu.a == 0xAB
        assert cpu.b == 0xCD

    def test_x_register_16bit(self, cpu):
        """X index register is 16-bit."""
        cpu.x = 0x1234
        assert cpu.x == 0x1234

        cpu.x = 0x1FFFF
        assert cpu.x == 0xFFFF  # Masked to 16 bits

    def test_sp_register_16bit(self, cpu):
        """Stack pointer is 16-bit."""
        cpu.sp = 0x0100
        assert cpu.sp == 0x0100

    def test_pc_register_16bit(self, cpu):
        """Program counter is 16-bit."""
        cpu.pc = 0x8000
        assert cpu.pc == 0x8000

        cpu.pc = 0x10000
        assert cpu.pc == 0x0000  # Wraps


# =============================================================================
# Flag Tests
# =============================================================================

class TestFlags:
    """Test CPU flag operations."""

    def test_flag_c(self, cpu):
        """Test carry flag."""
        cpu.flag_c = True
        assert cpu.flag_c is True
        assert cpu.state.flags & Flags.C

        cpu.flag_c = False
        assert cpu.flag_c is False
        assert not (cpu.state.flags & Flags.C)

    def test_flag_z(self, cpu):
        """Test zero flag."""
        cpu.flag_z = True
        assert cpu.flag_z is True

        cpu.flag_z = False
        assert cpu.flag_z is False

    def test_flag_n(self, cpu):
        """Test negative flag."""
        cpu.flag_n = True
        assert cpu.flag_n is True

        cpu.flag_n = False
        assert cpu.flag_n is False

    def test_flag_v(self, cpu):
        """Test overflow flag."""
        cpu.flag_v = True
        assert cpu.flag_v is True

        cpu.flag_v = False
        assert cpu.flag_v is False

    def test_flag_i(self, cpu):
        """Test interrupt mask flag."""
        cpu.flag_i = True
        assert cpu.flag_i is True

        cpu.flag_i = False
        assert cpu.flag_i is False

    def test_flag_h(self, cpu):
        """Test half-carry flag."""
        cpu.flag_h = True
        assert cpu.flag_h is True

        cpu.flag_h = False
        assert cpu.flag_h is False

    def test_flags_independent(self, cpu):
        """Test that flags are independent."""
        cpu.state.flags = 0

        cpu.flag_c = True
        cpu.flag_z = True

        assert cpu.flag_c is True
        assert cpu.flag_z is True
        assert cpu.flag_n is False

        cpu.flag_c = False
        assert cpu.flag_z is True  # Still set


# =============================================================================
# Basic Instruction Tests
# =============================================================================

class TestBasicInstructions:
    """Test simple instructions."""

    def test_nop(self, cpu):
        """NOP consumes 1 cycle, changes nothing."""
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x01)  # NOP

        a_before = cpu.a
        b_before = cpu.b

        cycles = cpu.step()

        assert cycles >= 1
        assert cpu.pc == 0x8001
        assert cpu.a == a_before
        assert cpu.b == b_before

    def test_clra(self, cpu):
        """CLRA clears A, sets Z, clears N,V,C."""
        cpu.a = 0x42
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4F)  # CLRA

        cpu.step()

        assert cpu.a == 0x00
        assert cpu.flag_z is True
        assert cpu.flag_n is False
        assert cpu.flag_v is False
        assert cpu.flag_c is False

    def test_clrb(self, cpu):
        """CLRB clears B, sets Z, clears N,V,C."""
        cpu.b = 0x42
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x5F)  # CLRB

        cpu.step()

        assert cpu.b == 0x00
        assert cpu.flag_z is True


# =============================================================================
# Load Instructions
# =============================================================================

class TestLoadInstructions:
    """Test load instructions and flag behavior."""

    def test_ldaa_immediate(self, cpu):
        """LDAA # loads immediate value."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x86, 0x42]))  # LDAA #$42

        cpu.step()

        assert cpu.a == 0x42
        assert cpu.pc == 0x8002
        assert cpu.flag_z is False
        assert cpu.flag_n is False
        assert cpu.flag_v is False

    def test_ldaa_immediate_zero_flag(self, cpu):
        """LDAA #$00 sets Z flag."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x86, 0x00]))  # LDAA #$00

        cpu.step()

        assert cpu.a == 0x00
        assert cpu.flag_z is True
        assert cpu.flag_n is False

    def test_ldaa_immediate_negative_flag(self, cpu):
        """LDAA with bit 7 set sets N flag."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x86, 0x80]))  # LDAA #$80

        cpu.step()

        assert cpu.a == 0x80
        assert cpu.flag_n is True
        assert cpu.flag_z is False

    def test_ldab_immediate(self, cpu):
        """LDAB # loads immediate value."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xC6, 0x55]))  # LDAB #$55

        cpu.step()

        assert cpu.b == 0x55
        assert cpu.pc == 0x8002

    def test_ldd_immediate(self, cpu):
        """LDD # loads 16-bit immediate into D."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xCC, 0x12, 0x34]))  # LDD #$1234

        cpu.step()

        assert cpu.d == 0x1234
        assert cpu.a == 0x12
        assert cpu.b == 0x34

    def test_ldx_immediate(self, cpu):
        """LDX # loads 16-bit immediate into X."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xCE, 0xAB, 0xCD]))  # LDX #$ABCD

        cpu.step()

        assert cpu.x == 0xABCD

    def test_ldaa_direct(self, cpu):
        """LDAA direct page addressing."""
        cpu.pc = 0x8000
        cpu.bus.write(0x0050, 0x77)  # Value at direct page
        cpu.bus.load_program(0x8000, bytes([0x96, 0x50]))  # LDAA $50

        cpu.step()

        assert cpu.a == 0x77

    def test_ldaa_extended(self, cpu):
        """LDAA extended addressing."""
        cpu.pc = 0x8000
        cpu.bus.write(0x1234, 0x99)  # Value at extended address
        cpu.bus.load_program(0x8000, bytes([0xB6, 0x12, 0x34]))  # LDAA $1234

        cpu.step()

        assert cpu.a == 0x99

    def test_ldaa_indexed(self, cpu):
        """LDAA indexed addressing (X+offset)."""
        cpu.pc = 0x8000
        cpu.x = 0x1000
        cpu.bus.write(0x1010, 0xAA)  # Value at X+$10
        cpu.bus.load_program(0x8000, bytes([0xA6, 0x10]))  # LDAA $10,X

        cpu.step()

        assert cpu.a == 0xAA


# =============================================================================
# Store Instructions
# =============================================================================

class TestStoreInstructions:
    """Test store instructions."""

    def test_staa_direct(self, cpu):
        """STAA direct page stores A."""
        cpu.a = 0x42
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x97, 0x50]))  # STAA $50
        cpu.bus.clear_history()

        cpu.step()

        assert cpu.bus.read(0x0050) == 0x42

    def test_stab_direct(self, cpu):
        """STAB direct page stores B."""
        cpu.b = 0x55
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xD7, 0x60]))  # STAB $60

        cpu.step()

        assert cpu.bus.read(0x0060) == 0x55

    def test_std_extended(self, cpu):
        """STD stores D (A:B) to memory."""
        cpu.d = 0x1234
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xFD, 0x10, 0x00]))  # STD $1000

        cpu.step()

        assert cpu.bus.read(0x1000) == 0x12
        assert cpu.bus.read(0x1001) == 0x34


# =============================================================================
# Arithmetic Instructions
# =============================================================================

class TestArithmeticInstructions:
    """Test arithmetic instructions and flag behavior."""

    def test_adda_immediate(self, cpu):
        """ADDA # adds immediate to A."""
        cpu.a = 0x10
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8B, 0x05]))  # ADDA #$05

        cpu.step()

        assert cpu.a == 0x15
        assert cpu.flag_c is False
        assert cpu.flag_z is False

    def test_adda_carry_flag(self, cpu):
        """ADDA sets carry on overflow."""
        cpu.a = 0xFF
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8B, 0x01]))  # ADDA #$01

        cpu.step()

        assert cpu.a == 0x00
        assert cpu.flag_c is True
        assert cpu.flag_z is True

    def test_adda_overflow_flag(self, cpu):
        """ADDA sets V on signed overflow."""
        cpu.a = 0x7F  # +127
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8B, 0x01]))  # ADDA #$01

        cpu.step()

        assert cpu.a == 0x80  # -128 (overflow occurred)
        assert cpu.flag_v is True
        assert cpu.flag_n is True

    def test_adda_half_carry(self, cpu):
        """ADDA sets H on half-carry."""
        cpu.a = 0x0F
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8B, 0x01]))  # ADDA #$01

        cpu.step()

        assert cpu.a == 0x10
        assert cpu.flag_h is True

    def test_suba_immediate(self, cpu):
        """SUBA # subtracts immediate from A."""
        cpu.a = 0x15
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x80, 0x05]))  # SUBA #$05

        cpu.step()

        assert cpu.a == 0x10
        assert cpu.flag_c is False  # No borrow

    def test_suba_borrow_flag(self, cpu):
        """SUBA sets carry (borrow) on underflow."""
        cpu.a = 0x00
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x80, 0x01]))  # SUBA #$01

        cpu.step()

        assert cpu.a == 0xFF  # Wrapped
        assert cpu.flag_c is True  # Borrow occurred

    def test_inca(self, cpu):
        """INCA increments A."""
        cpu.a = 0x41
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4C)  # INCA

        cpu.step()

        assert cpu.a == 0x42

    def test_inca_wrap(self, cpu):
        """INCA wraps from $FF to $00."""
        cpu.a = 0xFF
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4C)  # INCA

        cpu.step()

        assert cpu.a == 0x00
        assert cpu.flag_z is True
        # Note: INCA does not affect C flag

    def test_deca(self, cpu):
        """DECA decrements A."""
        cpu.a = 0x42
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4A)  # DECA

        cpu.step()

        assert cpu.a == 0x41

    def test_deca_wrap(self, cpu):
        """DECA wraps from $00 to $FF."""
        cpu.a = 0x00
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4A)  # DECA

        cpu.step()

        assert cpu.a == 0xFF
        assert cpu.flag_n is True

    def test_addd_immediate(self, cpu):
        """ADDD adds 16-bit immediate to D."""
        cpu.d = 0x1000
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xC3, 0x02, 0x34]))  # ADDD #$0234

        cpu.step()

        assert cpu.d == 0x1234

    def test_subd_immediate(self, cpu):
        """SUBD subtracts 16-bit immediate from D."""
        cpu.d = 0x1234
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x83, 0x02, 0x34]))  # SUBD #$0234

        cpu.step()

        assert cpu.d == 0x1000

    def test_mul(self, cpu):
        """MUL multiplies A*B, result in D."""
        cpu.a = 0x10
        cpu.b = 0x08
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x3D)  # MUL

        cpu.step()

        assert cpu.d == 0x0080  # 16 * 8 = 128


# =============================================================================
# Compare Instructions
# =============================================================================

class TestCompareInstructions:
    """Test compare instructions (no result, only flags)."""

    def test_cmpa_equal(self, cpu):
        """CMPA sets Z when equal."""
        cpu.a = 0x42
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x81, 0x42]))  # CMPA #$42

        cpu.step()

        assert cpu.a == 0x42  # A unchanged
        assert cpu.flag_z is True
        assert cpu.flag_c is False

    def test_cmpa_less(self, cpu):
        """CMPA sets C when A < value."""
        cpu.a = 0x10
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x81, 0x20]))  # CMPA #$20

        cpu.step()

        assert cpu.a == 0x10  # A unchanged
        assert cpu.flag_c is True  # Borrow
        assert cpu.flag_z is False

    def test_cmpa_greater(self, cpu):
        """CMPA clears Z and C when A > value."""
        cpu.a = 0x30
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x81, 0x20]))  # CMPA #$20

        cpu.step()

        assert cpu.flag_z is False
        assert cpu.flag_c is False

    def test_cpx_equal(self, cpu):
        """CPX sets Z when X equal."""
        cpu.x = 0x1234
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8C, 0x12, 0x34]))  # CPX #$1234

        cpu.step()

        assert cpu.x == 0x1234  # X unchanged
        assert cpu.flag_z is True

    def test_tsta(self, cpu):
        """TSTA tests A, sets flags."""
        cpu.a = 0x00
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x4D)  # TSTA

        cpu.step()

        assert cpu.a == 0x00  # A unchanged
        assert cpu.flag_z is True
        assert cpu.flag_n is False


# =============================================================================
# Logic Instructions
# =============================================================================

class TestLogicInstructions:
    """Test logical operations."""

    def test_anda_immediate(self, cpu):
        """ANDA # performs bitwise AND."""
        cpu.a = 0b11110000
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x84, 0b10101010]))  # ANDA #$AA

        cpu.step()

        assert cpu.a == 0b10100000

    def test_oraa_immediate(self, cpu):
        """ORAA # performs bitwise OR."""
        cpu.a = 0b11110000
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x8A, 0b00001111]))  # ORAA #$0F

        cpu.step()

        assert cpu.a == 0b11111111

    def test_eora_immediate(self, cpu):
        """EORA # performs bitwise XOR."""
        cpu.a = 0b11110000
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x88, 0b11111111]))  # EORA #$FF

        cpu.step()

        assert cpu.a == 0b00001111

    def test_coma(self, cpu):
        """COMA complements A (one's complement)."""
        cpu.a = 0b11110000
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x43)  # COMA

        cpu.step()

        assert cpu.a == 0b00001111
        assert cpu.flag_c is True  # Always set by COM

    def test_nega(self, cpu):
        """NEGA negates A (two's complement)."""
        cpu.a = 0x01
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x40)  # NEGA

        cpu.step()

        assert cpu.a == 0xFF  # -1 in two's complement


# =============================================================================
# Shift/Rotate Instructions
# =============================================================================

class TestShiftInstructions:
    """Test shift and rotate instructions."""

    def test_lsra(self, cpu):
        """LSRA logical shift right A."""
        cpu.a = 0b11111110
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x44)  # LSRA

        cpu.step()

        assert cpu.a == 0b01111111
        assert cpu.flag_c is False  # Bit 0 was 0

    def test_lsra_carry(self, cpu):
        """LSRA sets carry from bit 0."""
        cpu.a = 0b11111111
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x44)  # LSRA

        cpu.step()

        assert cpu.a == 0b01111111
        assert cpu.flag_c is True  # Bit 0 was 1

    def test_asla(self, cpu):
        """ASLA arithmetic shift left A."""
        cpu.a = 0b01111111
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x48)  # ASLA

        cpu.step()

        assert cpu.a == 0b11111110
        assert cpu.flag_c is False  # Bit 7 was 0

    def test_asla_carry(self, cpu):
        """ASLA sets carry from bit 7."""
        cpu.a = 0b10000001
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x48)  # ASLA

        cpu.step()

        assert cpu.a == 0b00000010
        assert cpu.flag_c is True  # Bit 7 was 1

    def test_rola(self, cpu):
        """ROLA rotates left through carry."""
        cpu.a = 0b10000000
        cpu.flag_c = True
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x49)  # ROLA

        cpu.step()

        assert cpu.a == 0b00000001  # Carry rotated in
        assert cpu.flag_c is True  # Bit 7 rotated out

    def test_rora(self, cpu):
        """RORA rotates right through carry."""
        cpu.a = 0b00000001
        cpu.flag_c = True
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x46)  # RORA

        cpu.step()

        assert cpu.a == 0b10000000  # Carry rotated into bit 7
        assert cpu.flag_c is True  # Bit 0 rotated out

    def test_lsrd(self, cpu):
        """LSRD shifts D right (16-bit)."""
        cpu.d = 0x8000
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x04)  # LSRD

        cpu.step()

        assert cpu.d == 0x4000

    def test_asld(self, cpu):
        """ASLD shifts D left (16-bit)."""
        cpu.d = 0x4000
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x05)  # ASLD

        cpu.step()

        assert cpu.d == 0x8000


# =============================================================================
# Branch Instructions
# =============================================================================

class TestBranchInstructions:
    """Test branch instructions."""

    def test_bra_forward(self, cpu):
        """BRA branches forward."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x20, 0x10]))  # BRA +16

        cpu.step()

        assert cpu.pc == 0x8012  # 0x8002 + 0x10

    def test_bra_backward(self, cpu):
        """BRA branches backward (negative offset)."""
        cpu.pc = 0x8010
        cpu.bus.load_program(0x8010, bytes([0x20, 0xFE]))  # BRA -2

        cpu.step()

        # 0x8012 + (-2) = 0x8010 (infinite loop)
        assert cpu.pc == 0x8010

    def test_brn(self, cpu):
        """BRN never branches."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x21, 0x10]))  # BRN +16

        cpu.step()

        assert cpu.pc == 0x8002  # Just consumed the offset

    def test_beq_taken(self, cpu):
        """BEQ branches when Z=1."""
        cpu.flag_z = True
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x27, 0x10]))  # BEQ +16

        cpu.step()

        assert cpu.pc == 0x8012

    def test_beq_not_taken(self, cpu):
        """BEQ does not branch when Z=0."""
        cpu.flag_z = False
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x27, 0x10]))  # BEQ +16

        cpu.step()

        assert cpu.pc == 0x8002

    def test_bne_taken(self, cpu):
        """BNE branches when Z=0."""
        cpu.flag_z = False
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x26, 0x10]))  # BNE +16

        cpu.step()

        assert cpu.pc == 0x8012

    def test_bcc_taken(self, cpu):
        """BCC branches when C=0."""
        cpu.flag_c = False
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x24, 0x10]))  # BCC +16

        cpu.step()

        assert cpu.pc == 0x8012

    def test_bcs_taken(self, cpu):
        """BCS branches when C=1."""
        cpu.flag_c = True
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x25, 0x10]))  # BCS +16

        cpu.step()

        assert cpu.pc == 0x8012

    def test_bpl_taken(self, cpu):
        """BPL branches when N=0."""
        cpu.flag_n = False
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x2A, 0x10]))  # BPL +16

        cpu.step()

        assert cpu.pc == 0x8012

    def test_bmi_taken(self, cpu):
        """BMI branches when N=1."""
        cpu.flag_n = True
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x2B, 0x10]))  # BMI +16

        cpu.step()

        assert cpu.pc == 0x8012


# =============================================================================
# Jump Instructions
# =============================================================================

class TestJumpInstructions:
    """Test jump and call instructions."""

    def test_jmp_extended(self, cpu):
        """JMP jumps to extended address."""
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x7E, 0x90, 0x00]))  # JMP $9000

        cpu.step()

        assert cpu.pc == 0x9000

    def test_jsr_extended(self, cpu):
        """JSR pushes return address and jumps."""
        cpu.sp = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0xBD, 0x90, 0x00]))  # JSR $9000

        cpu.step()

        assert cpu.pc == 0x9000
        assert cpu.sp == 0x07FE  # Two bytes pushed
        # Return address (after JSR = 0x8003)
        assert cpu.bus.read(0x07FE) == 0x80
        assert cpu.bus.read(0x07FF) == 0x03

    def test_rts(self, cpu):
        """RTS pops and returns."""
        cpu.sp = 0x07FE  # Valid RAM address
        cpu.bus.write(0x07FE, 0x81)  # Return high
        cpu.bus.write(0x07FF, 0x23)  # Return low
        cpu.pc = 0x9000
        cpu.bus.write(0x9000, 0x39)  # RTS

        cpu.step()

        assert cpu.pc == 0x8123
        assert cpu.sp == 0x0800


# =============================================================================
# Stack Instructions
# =============================================================================

class TestStackInstructions:
    """Test stack operations."""

    def test_psha(self, cpu):
        """PSHA pushes A onto stack."""
        cpu.a = 0x42
        cpu.sp = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x36)  # PSHA

        cpu.step()

        assert cpu.sp == 0x07FF
        assert cpu.bus.read(0x07FF) == 0x42

    def test_pshb(self, cpu):
        """PSHB pushes B onto stack."""
        cpu.b = 0x55
        cpu.sp = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x37)  # PSHB

        cpu.step()

        assert cpu.sp == 0x07FF
        assert cpu.bus.read(0x07FF) == 0x55

    def test_pshx(self, cpu):
        """PSHX pushes X onto stack."""
        cpu.x = 0x1234
        cpu.sp = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x3C)  # PSHX

        cpu.step()

        assert cpu.sp == 0x07FE
        assert cpu.bus.read(0x07FE) == 0x12
        assert cpu.bus.read(0x07FF) == 0x34

    def test_pula(self, cpu):
        """PULA pops A from stack."""
        cpu.sp = 0x07FF  # Valid RAM address
        cpu.bus.write(0x07FF, 0x42)
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x32)  # PULA

        cpu.step()

        assert cpu.a == 0x42
        assert cpu.sp == 0x0800

    def test_pulb(self, cpu):
        """PULB pops B from stack."""
        cpu.sp = 0x07FF  # Valid RAM address
        cpu.bus.write(0x07FF, 0x55)
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x33)  # PULB

        cpu.step()

        assert cpu.b == 0x55
        assert cpu.sp == 0x0800

    def test_pulx(self, cpu):
        """PULX pops X from stack."""
        cpu.sp = 0x07FE  # Valid RAM address
        cpu.bus.write(0x07FE, 0x12)
        cpu.bus.write(0x07FF, 0x34)
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x38)  # PULX

        cpu.step()

        assert cpu.x == 0x1234
        assert cpu.sp == 0x0800

    def test_tsx(self, cpu):
        """TSX copies SP to X (HD6303: X=SP, not X=SP+1)."""
        cpu.sp = 0x07FE  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x30)  # TSX

        cpu.step()

        assert cpu.x == 0x07FE  # HD6303 gives X=SP directly

    def test_txs(self, cpu):
        """TXS copies X to SP."""
        cpu.x = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x35)  # TXS

        cpu.step()

        assert cpu.sp == 0x0800

    def test_ins(self, cpu):
        """INS increments SP."""
        cpu.sp = 0x07FF  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x31)  # INS

        cpu.step()

        assert cpu.sp == 0x0800

    def test_des(self, cpu):
        """DES decrements SP."""
        cpu.sp = 0x0800  # Valid RAM address
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x34)  # DES

        cpu.step()

        assert cpu.sp == 0x07FF


# =============================================================================
# Index Register Instructions
# =============================================================================

class TestIndexInstructions:
    """Test index register operations."""

    def test_inx(self, cpu):
        """INX increments X."""
        cpu.x = 0x00FF
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x08)  # INX

        cpu.step()

        assert cpu.x == 0x0100
        assert cpu.flag_z is False

    def test_inx_zero(self, cpu):
        """INX sets Z when X becomes 0."""
        cpu.x = 0xFFFF
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x08)  # INX

        cpu.step()

        assert cpu.x == 0x0000
        assert cpu.flag_z is True

    def test_dex(self, cpu):
        """DEX decrements X."""
        cpu.x = 0x0100
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x09)  # DEX

        cpu.step()

        assert cpu.x == 0x00FF
        assert cpu.flag_z is False

    def test_dex_zero(self, cpu):
        """DEX sets Z when X becomes 0."""
        cpu.x = 0x0001
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x09)  # DEX

        cpu.step()

        assert cpu.x == 0x0000
        assert cpu.flag_z is True

    def test_abx(self, cpu):
        """ABX adds B to X."""
        cpu.x = 0x1000
        cpu.b = 0x42
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x3A)  # ABX

        cpu.step()

        assert cpu.x == 0x1042


# =============================================================================
# Transfer Instructions
# =============================================================================

class TestTransferInstructions:
    """Test register transfer instructions."""

    def test_tab(self, cpu):
        """TAB transfers A to B."""
        cpu.a = 0x42
        cpu.b = 0x00
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x16)  # TAB

        cpu.step()

        assert cpu.b == 0x42
        assert cpu.a == 0x42  # A unchanged

    def test_tba(self, cpu):
        """TBA transfers B to A."""
        cpu.a = 0x00
        cpu.b = 0x55
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x17)  # TBA

        cpu.step()

        assert cpu.a == 0x55
        assert cpu.b == 0x55  # B unchanged

    def test_xgdx(self, cpu):
        """XGDX exchanges D and X."""
        cpu.d = 0x1234
        cpu.x = 0xABCD
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x18)  # XGDX

        cpu.step()

        assert cpu.d == 0xABCD
        assert cpu.x == 0x1234

    def test_tap(self, cpu):
        """TAP transfers A to CC flags."""
        cpu.a = 0b00010101  # I=1, Z=1, C=1
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x06)  # TAP

        cpu.step()

        assert cpu.flag_c is True
        assert cpu.flag_z is True
        assert cpu.flag_i is True

    def test_tpa(self, cpu):
        """TPA transfers CC to A (bits 7,6 always 1)."""
        cpu.state.flags = 0b00010101
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x07)  # TPA

        cpu.step()

        assert cpu.a == 0b11010101  # High bits set


# =============================================================================
# Flag Instructions
# =============================================================================

class TestFlagInstructions:
    """Test flag manipulation instructions."""

    def test_clc(self, cpu):
        """CLC clears carry flag."""
        cpu.flag_c = True
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0C)  # CLC

        cpu.step()

        assert cpu.flag_c is False

    def test_sec(self, cpu):
        """SEC sets carry flag."""
        cpu.flag_c = False
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0D)  # SEC

        cpu.step()

        assert cpu.flag_c is True

    def test_clv(self, cpu):
        """CLV clears overflow flag."""
        cpu.flag_v = True
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0A)  # CLV

        cpu.step()

        assert cpu.flag_v is False

    def test_sev(self, cpu):
        """SEV sets overflow flag."""
        cpu.flag_v = False
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0B)  # SEV

        cpu.step()

        assert cpu.flag_v is True

    def test_cli(self, cpu):
        """CLI clears interrupt mask."""
        cpu.flag_i = True
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0E)  # CLI

        cpu.step()

        assert cpu.flag_i is False

    def test_sei(self, cpu):
        """SEI sets interrupt mask."""
        cpu.flag_i = False
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x0F)  # SEI

        cpu.step()

        assert cpu.flag_i is True


# =============================================================================
# HD6303-Specific Instructions
# =============================================================================

class TestHD6303Instructions:
    """Test HD6303-specific instructions not in 6801."""

    def test_aim_direct(self, cpu):
        """AIM ANDs immediate with memory."""
        cpu.bus.write(0x0050, 0xFF)
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x71, 0x0F, 0x50]))  # AIM #$0F,$50

        cpu.step()

        assert cpu.bus.read(0x0050) == 0x0F

    def test_oim_direct(self, cpu):
        """OIM ORs immediate with memory."""
        cpu.bus.write(0x0050, 0xF0)
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x72, 0x0F, 0x50]))  # OIM #$0F,$50

        cpu.step()

        assert cpu.bus.read(0x0050) == 0xFF

    def test_eim_direct(self, cpu):
        """EIM XORs immediate with memory."""
        cpu.bus.write(0x0050, 0xFF)
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x75, 0x0F, 0x50]))  # EIM #$0F,$50

        cpu.step()

        assert cpu.bus.read(0x0050) == 0xF0

    def test_tim_direct(self, cpu):
        """TIM tests immediate with memory (no result)."""
        cpu.bus.write(0x0050, 0xF0)
        cpu.pc = 0x8000
        cpu.bus.load_program(0x8000, bytes([0x7B, 0x10, 0x50]))  # TIM #$10,$50

        cpu.step()

        # Memory unchanged
        assert cpu.bus.read(0x0050) == 0xF0
        # Z set because $F0 & $10 = $10, which is non-zero
        assert cpu.flag_z is False


# =============================================================================
# Execution Control Tests
# =============================================================================

class TestExecutionControl:
    """Test execution control methods."""

    def test_step_returns_cycles(self, cpu):
        """step() returns cycles consumed."""
        cpu.pc = 0x8000
        cpu.bus.write(0x8000, 0x01)  # NOP (1 cycle)

        cycles = cpu.step()

        assert cycles >= 1

    def test_execute_runs_cycles(self, cpu):
        """execute() runs for specified cycles."""
        # Fill with NOPs
        for i in range(100):
            cpu.bus.write(0x8000 + i, 0x01)
        cpu.pc = 0x8000

        cycles = cpu.execute(50)

        assert cycles >= 50
        assert cpu.pc > 0x8000

    def test_instruction_hook_can_stop(self, cpu):
        """Instruction hook returning False stops execution."""
        # Fill with NOPs
        for i in range(100):
            cpu.bus.write(0x8000 + i, 0x01)
        cpu.pc = 0x8000

        calls = []
        def hook(pc, opcode):
            calls.append((pc, opcode))
            return len(calls) < 5  # Stop after 5 instructions

        cpu.on_instruction = hook
        cpu.execute(1000)

        assert len(calls) == 5


# =============================================================================
# Snapshot Tests
# =============================================================================

class TestSnapshot:
    """Test CPU snapshot save/restore."""

    def test_get_snapshot_data(self, cpu):
        """get_snapshot_data returns all state."""
        cpu.a = 0x12
        cpu.b = 0x34
        cpu.x = 0x5678
        cpu.sp = 0x0100
        cpu.pc = 0x8000
        cpu.state.flags = 0x15

        data = cpu.get_snapshot_data()

        assert len(data) == 10  # A, B, flags, Xhi, Xlo, PChi, PClo, SPhi, SPlo, sleep
        assert data[0] == 0x12  # A
        assert data[1] == 0x34  # B

    def test_apply_snapshot_data(self, cpu):
        """apply_snapshot_data restores state."""
        data = [0x12, 0x34, 0x15, 0x56, 0x78, 0x80, 0x00, 0x01, 0x00, 0]

        consumed = cpu.apply_snapshot_data(data)

        assert consumed == 10
        assert cpu.a == 0x12
        assert cpu.b == 0x34
        assert cpu.x == 0x5678
        assert cpu.pc == 0x8000
        assert cpu.sp == 0x0100
