# =============================================================================
# test_codegen.py - Code Generator Unit Tests
# =============================================================================
# Tests for the HD6303 assembler code generator.
# Covers Milestone A3: Code Generation from specs/01-assembler.md.
#
# Test coverage includes:
#   - Inherent (no operand) instructions
#   - Immediate addressing mode
#   - Direct addressing mode (zero page)
#   - Extended addressing mode
#   - Indexed addressing mode
#   - Relative addressing mode (branches)
#   - HD6303-specific instructions (AIM, OIM, XGDX, etc.)
#   - All directives (ORG, FCB, FDB, FCC, RMB, EQU)
# =============================================================================

import pytest
from psion_sdk.assembler import Assembler
from psion_sdk.errors import (
    BranchRangeError,
    AddressingModeError,
    UndefinedSymbolError,
)


# =============================================================================
# Helper Functions
# =============================================================================

def assemble(source: str) -> bytes:
    """
    Helper to assemble source code and return the raw code bytes.
    Strips the OB3 header for easier testing.
    """
    asm = Assembler()
    result = asm.assemble(source)
    # Skip OB3 header: "ORG" (3) + length (2) + address (2) = 7 bytes
    if result[:3] == b"ORG":
        code_start = 7
        return result[code_start:]
    return result


def assemble_raw(source: str) -> bytes:
    """Return the complete OB3 output including header."""
    asm = Assembler()
    return asm.assemble(source)


# =============================================================================
# Milestone A3: Code Generation - Basic Tests
# =============================================================================

class TestBasicInstructions:
    """
    Test basic instruction encoding.
    Reference: specs/01-assembler.md Milestone A3
    """

    def test_nop(self):
        """NOP should encode to $01."""
        code = assemble("NOP")
        assert code == bytes([0x01])

    def test_rts(self):
        """RTS should encode to $39."""
        code = assemble("RTS")
        assert code == bytes([0x39])

    def test_rti(self):
        """RTI should encode to $3B."""
        code = assemble("RTI")
        assert code == bytes([0x3B])

    def test_swi(self):
        """SWI should encode to $3F."""
        code = assemble("SWI")
        assert code == bytes([0x3F])

    def test_wai(self):
        """WAI should encode to $3E."""
        code = assemble("WAI")
        assert code == bytes([0x3E])


# =============================================================================
# Inherent Addressing Mode Tests
# =============================================================================

class TestInherentMode:
    """Test instructions with inherent (no operand) addressing."""

    def test_accumulator_ops(self):
        """Test accumulator manipulation instructions."""
        assert assemble("CLRA") == bytes([0x4F])
        assert assemble("CLRB") == bytes([0x5F])
        assert assemble("INCA") == bytes([0x4C])
        assert assemble("INCB") == bytes([0x5C])
        assert assemble("DECA") == bytes([0x4A])
        assert assemble("DECB") == bytes([0x5A])

    def test_shift_rotate(self):
        """Test shift and rotate instructions."""
        assert assemble("ASLA") == bytes([0x48])
        assert assemble("ASLB") == bytes([0x58])
        assert assemble("ASRA") == bytes([0x47])
        assert assemble("ASRB") == bytes([0x57])
        assert assemble("LSRA") == bytes([0x44])
        assert assemble("LSRB") == bytes([0x54])
        assert assemble("ROLA") == bytes([0x49])
        assert assemble("ROLB") == bytes([0x59])
        assert assemble("RORA") == bytes([0x46])
        assert assemble("RORB") == bytes([0x56])

    def test_test_and_complement(self):
        """Test test and complement instructions."""
        assert assemble("TSTA") == bytes([0x4D])
        assert assemble("TSTB") == bytes([0x5D])
        assert assemble("COMA") == bytes([0x43])
        assert assemble("COMB") == bytes([0x53])
        assert assemble("NEGA") == bytes([0x40])
        assert assemble("NEGB") == bytes([0x50])

    def test_stack_ops(self):
        """Test stack operations."""
        assert assemble("PSHA") == bytes([0x36])
        assert assemble("PSHB") == bytes([0x37])
        assert assemble("PSHX") == bytes([0x3C])
        assert assemble("PULA") == bytes([0x32])
        assert assemble("PULB") == bytes([0x33])
        assert assemble("PULX") == bytes([0x38])

    def test_transfer_ops(self):
        """Test register transfer instructions."""
        assert assemble("TAB") == bytes([0x16])
        assert assemble("TBA") == bytes([0x17])
        assert assemble("TAP") == bytes([0x06])
        assert assemble("TPA") == bytes([0x07])
        assert assemble("TSX") == bytes([0x30])
        assert assemble("TXS") == bytes([0x35])

    def test_flag_ops(self):
        """Test flag manipulation instructions."""
        assert assemble("CLC") == bytes([0x0C])
        assert assemble("CLI") == bytes([0x0E])
        assert assemble("CLV") == bytes([0x0A])
        assert assemble("SEC") == bytes([0x0D])
        assert assemble("SEI") == bytes([0x0F])
        assert assemble("SEV") == bytes([0x0B])


# =============================================================================
# Immediate Addressing Mode Tests
# =============================================================================

class TestImmediateMode:
    """Test immediate addressing mode (#value)."""

    def test_ldaa_immediate(self):
        """LDAA #value - Load A with immediate."""
        code = assemble("LDAA #$41")
        assert code == bytes([0x86, 0x41])

    def test_ldab_immediate(self):
        """LDAB #value - Load B with immediate."""
        code = assemble("LDAB #$42")
        assert code == bytes([0xC6, 0x42])

    def test_ldd_immediate(self):
        """LDD #value - Load D with 16-bit immediate."""
        code = assemble("LDD #$1234")
        assert code == bytes([0xCC, 0x12, 0x34])  # Big-endian

    def test_ldx_immediate(self):
        """LDX #value - Load X with 16-bit immediate."""
        code = assemble("LDX #$2100")
        assert code == bytes([0xCE, 0x21, 0x00])

    def test_lds_immediate(self):
        """LDS #value - Load S with 16-bit immediate."""
        code = assemble("LDS #$03FF")
        assert code == bytes([0x8E, 0x03, 0xFF])

    def test_cmpa_immediate(self):
        """CMPA #value - Compare A with immediate."""
        code = assemble("CMPA #$00")
        assert code == bytes([0x81, 0x00])

    def test_cmpb_immediate(self):
        """CMPB #value - Compare B with immediate."""
        code = assemble("CMPB #$FF")
        assert code == bytes([0xC1, 0xFF])

    def test_cpx_immediate(self):
        """CPX #value - Compare X with 16-bit immediate."""
        code = assemble("CPX #$2000")
        assert code == bytes([0x8C, 0x20, 0x00])

    def test_adda_immediate(self):
        """ADDA #value - Add immediate to A."""
        code = assemble("ADDA #$10")
        assert code == bytes([0x8B, 0x10])

    def test_addb_immediate(self):
        """ADDB #value - Add immediate to B."""
        code = assemble("ADDB #$20")
        assert code == bytes([0xCB, 0x20])

    def test_addd_immediate(self):
        """ADDD #value - Add 16-bit immediate to D."""
        code = assemble("ADDD #$0100")
        assert code == bytes([0xC3, 0x01, 0x00])

    def test_suba_immediate(self):
        """SUBA #value - Subtract immediate from A."""
        code = assemble("SUBA #$01")
        assert code == bytes([0x80, 0x01])

    def test_subb_immediate(self):
        """SUBB #value - Subtract immediate from B."""
        code = assemble("SUBB #$01")
        assert code == bytes([0xC0, 0x01])

    def test_subd_immediate(self):
        """SUBD #value - Subtract 16-bit immediate from D."""
        code = assemble("SUBD #$0001")
        assert code == bytes([0x83, 0x00, 0x01])

    def test_anda_immediate(self):
        """ANDA #value - AND immediate with A."""
        code = assemble("ANDA #$0F")
        assert code == bytes([0x84, 0x0F])

    def test_andb_immediate(self):
        """ANDB #value - AND immediate with B."""
        code = assemble("ANDB #$F0")
        assert code == bytes([0xC4, 0xF0])

    def test_oraa_immediate(self):
        """ORAA #value - OR immediate with A."""
        code = assemble("ORAA #$80")
        assert code == bytes([0x8A, 0x80])

    def test_orab_immediate(self):
        """ORAB #value - OR immediate with B."""
        code = assemble("ORAB #$01")
        assert code == bytes([0xCA, 0x01])

    def test_eora_immediate(self):
        """EORA #value - XOR immediate with A."""
        code = assemble("EORA #$FF")
        assert code == bytes([0x88, 0xFF])

    def test_eorb_immediate(self):
        """EORB #value - XOR immediate with B."""
        code = assemble("EORB #$AA")
        assert code == bytes([0xC8, 0xAA])

    def test_bita_immediate(self):
        """BITA #value - Test bits in A."""
        code = assemble("BITA #$01")
        assert code == bytes([0x85, 0x01])

    def test_bitb_immediate(self):
        """BITB #value - Test bits in B."""
        code = assemble("BITB #$80")
        assert code == bytes([0xC5, 0x80])


# =============================================================================
# Direct Addressing Mode Tests
# =============================================================================

class TestDirectMode:
    """Test direct (zero page) addressing mode."""

    def test_ldaa_direct(self):
        """LDAA $addr - Load A from zero page."""
        code = assemble("LDAA $50")
        assert code == bytes([0x96, 0x50])

    def test_ldab_direct(self):
        """LDAB $addr - Load B from zero page."""
        code = assemble("LDAB $60")
        assert code == bytes([0xD6, 0x60])

    def test_ldd_direct(self):
        """LDD $addr - Load D from zero page."""
        code = assemble("LDD $80")
        assert code == bytes([0xDC, 0x80])

    def test_ldx_direct(self):
        """LDX $addr - Load X from zero page."""
        code = assemble("LDX $90")
        assert code == bytes([0xDE, 0x90])

    def test_staa_direct(self):
        """STAA $addr - Store A to zero page."""
        code = assemble("STAA $50")
        assert code == bytes([0x97, 0x50])

    def test_stab_direct(self):
        """STAB $addr - Store B to zero page."""
        code = assemble("STAB $60")
        assert code == bytes([0xD7, 0x60])

    def test_std_direct(self):
        """STD $addr - Store D to zero page."""
        code = assemble("STD $80")
        assert code == bytes([0xDD, 0x80])

    def test_stx_direct(self):
        """STX $addr - Store X to zero page."""
        code = assemble("STX $90")
        assert code == bytes([0xDF, 0x90])


# =============================================================================
# Extended Addressing Mode Tests
# =============================================================================

class TestExtendedMode:
    """Test extended (16-bit address) addressing mode."""

    def test_ldaa_extended(self):
        """LDAA $addr - Load A from memory."""
        code = assemble("LDAA $2100")
        assert code == bytes([0xB6, 0x21, 0x00])

    def test_ldab_extended(self):
        """LDAB $addr - Load B from memory."""
        code = assemble("LDAB $2100")
        assert code == bytes([0xF6, 0x21, 0x00])

    def test_ldd_extended(self):
        """LDD $addr - Load D from memory."""
        code = assemble("LDD $2100")
        assert code == bytes([0xFC, 0x21, 0x00])

    def test_ldx_extended(self):
        """LDX $addr - Load X from memory."""
        code = assemble("LDX $2100")
        assert code == bytes([0xFE, 0x21, 0x00])

    def test_staa_extended(self):
        """STAA $addr - Store A to memory."""
        code = assemble("STAA $2100")
        assert code == bytes([0xB7, 0x21, 0x00])

    def test_stab_extended(self):
        """STAB $addr - Store B to memory."""
        code = assemble("STAB $2100")
        assert code == bytes([0xF7, 0x21, 0x00])

    def test_std_extended(self):
        """STD $addr - Store D to memory."""
        code = assemble("STD $2100")
        assert code == bytes([0xFD, 0x21, 0x00])

    def test_stx_extended(self):
        """STX $addr - Store X to memory."""
        code = assemble("STX $2100")
        assert code == bytes([0xFF, 0x21, 0x00])

    def test_jmp_extended(self):
        """JMP $addr - Jump to address."""
        code = assemble("JMP $2100")
        assert code == bytes([0x7E, 0x21, 0x00])

    def test_jsr_extended(self):
        """JSR $addr - Jump to subroutine."""
        code = assemble("JSR $2100")
        assert code == bytes([0xBD, 0x21, 0x00])


# =============================================================================
# Indexed Addressing Mode Tests
# =============================================================================

class TestIndexedMode:
    """Test indexed addressing mode (offset,X)."""

    def test_ldaa_indexed_zero(self):
        """LDAA 0,X - Load A from address in X."""
        code = assemble("LDAA 0,X")
        assert code == bytes([0xA6, 0x00])

    def test_ldaa_indexed_offset(self):
        """LDAA offset,X - Load A with offset."""
        code = assemble("LDAA $10,X")
        assert code == bytes([0xA6, 0x10])

    def test_ldab_indexed(self):
        """LDAB offset,X - Load B indexed."""
        code = assemble("LDAB $20,X")
        assert code == bytes([0xE6, 0x20])

    def test_ldd_indexed(self):
        """LDD offset,X - Load D indexed."""
        code = assemble("LDD $30,X")
        assert code == bytes([0xEC, 0x30])

    def test_staa_indexed(self):
        """STAA offset,X - Store A indexed."""
        code = assemble("STAA $10,X")
        assert code == bytes([0xA7, 0x10])

    def test_stab_indexed(self):
        """STAB offset,X - Store B indexed."""
        code = assemble("STAB $20,X")
        assert code == bytes([0xE7, 0x20])

    def test_std_indexed(self):
        """STD offset,X - Store D indexed."""
        code = assemble("STD $30,X")
        assert code == bytes([0xED, 0x30])

    def test_jmp_indexed(self):
        """JMP offset,X - Jump indexed."""
        code = assemble("JMP $00,X")
        assert code == bytes([0x6E, 0x00])

    def test_jsr_indexed(self):
        """JSR offset,X - Jump to subroutine indexed."""
        code = assemble("JSR $00,X")
        assert code == bytes([0xAD, 0x00])

    def test_inc_indexed(self):
        """INC offset,X - Increment memory indexed."""
        code = assemble("INC $10,X")
        assert code == bytes([0x6C, 0x10])

    def test_dec_indexed(self):
        """DEC offset,X - Decrement memory indexed."""
        code = assemble("DEC $10,X")
        assert code == bytes([0x6A, 0x10])


# =============================================================================
# Relative Addressing Mode Tests (Branches)
# =============================================================================

class TestRelativeMode:
    """Test relative addressing mode for branches."""

    def test_bra_forward(self):
        """BRA forward branch."""
        source = """
            ORG $2100
            BRA SKIP
            NOP
SKIP:       NOP
        """
        code = assemble(source)
        # BRA opcode $20, offset $01 (skip 1 byte NOP)
        assert code[0:2] == bytes([0x20, 0x01])

    def test_bra_backward(self):
        """BRA backward branch."""
        source = """
            ORG $2100
LOOP:       NOP
            BRA LOOP
        """
        code = assemble(source)
        # NOP at $2100, BRA at $2101
        # Offset = LOOP - (PC after BRA) = $2100 - $2103 = -3 = $FD
        assert code[1] == 0x20  # BRA opcode
        assert code[2] == 0xFD  # -3 offset

    def test_beq_branch(self):
        """BEQ conditional branch."""
        source = """
            ORG $2100
            BEQ TARGET
            NOP
TARGET:     RTS
        """
        code = assemble(source)
        assert code[0] == 0x27  # BEQ opcode

    def test_bne_branch(self):
        """BNE conditional branch."""
        source = """
            ORG $2100
            BNE TARGET
            NOP
TARGET:     RTS
        """
        code = assemble(source)
        assert code[0] == 0x26  # BNE opcode

    def test_bcc_branch(self):
        """BCC (branch if carry clear) conditional branch."""
        source = """
            ORG $2100
            BCC TARGET
            NOP
TARGET:     RTS
        """
        code = assemble(source)
        assert code[0] == 0x24  # BCC opcode

    def test_bcs_branch(self):
        """BCS (branch if carry set) conditional branch."""
        source = """
            ORG $2100
            BCS TARGET
            NOP
TARGET:     RTS
        """
        code = assemble(source)
        assert code[0] == 0x25  # BCS opcode

    def test_bsr_subroutine(self):
        """BSR (branch to subroutine)."""
        source = """
            ORG $2100
            BSR SUB
            RTS
SUB:        RTS
        """
        code = assemble(source)
        assert code[0] == 0x8D  # BSR opcode
        assert code[1] == 0x01  # Skip RTS

    def test_branch_range_relaxation(self):
        """Branch out of range should be relaxed to JMP (branch relaxation).

        The assembler implements automatic branch relaxation: when a branch
        target is beyond the ±127 byte range of relative branches, BRA is
        automatically converted to JMP. See TestBranchRelaxation in
        test_assembler.py for comprehensive branch relaxation tests.
        """
        # Create source with branch target more than 127 bytes away
        source = """
            ORG $2100
            BRA FAR
            RMB 200
FAR:        NOP
        """
        # Should NOT raise an error - branch relaxation converts BRA to JMP
        # Note: assemble() helper already strips OB3 header
        code = assemble(source)

        # BRA becomes JMP (3 bytes) + 200 bytes RMB + NOP (1 byte) = 204 bytes
        assert len(code) == 204

        # First instruction should be JMP (opcode $7E) not BRA
        assert code[0] == 0x7E  # JMP extended addressing opcode

        # JMP target should point to FAR label (at $2100 + 3 + 200 = $21CB)
        jmp_target = (code[1] << 8) | code[2]
        assert jmp_target == 0x2100 + 3 + 200  # $21CB


# =============================================================================
# HD6303-Specific Instruction Tests
# =============================================================================

class TestHD6303Specific:
    """Test HD6303-specific instructions not in standard 6800."""

    def test_xgdx(self):
        """XGDX - Exchange D and X registers."""
        code = assemble("XGDX")
        assert code == bytes([0x18])

    def test_slp(self):
        """SLP - Sleep mode (low power)."""
        code = assemble("SLP")
        assert code == bytes([0x1A])

    def test_abx(self):
        """ABX - Add B to X."""
        code = assemble("ABX")
        assert code == bytes([0x3A])

    def test_aim_direct(self):
        """AIM - AND immediate with memory (direct)."""
        code = assemble("AIM #$F0,$50")
        assert code == bytes([0x71, 0xF0, 0x50])

    def test_aim_indexed(self):
        """AIM - AND immediate with memory (indexed)."""
        code = assemble("AIM #$0F,$10,X")
        assert code == bytes([0x61, 0x0F, 0x10])

    def test_oim_direct(self):
        """OIM - OR immediate with memory (direct)."""
        code = assemble("OIM #$80,$50")
        assert code == bytes([0x72, 0x80, 0x50])

    def test_oim_indexed(self):
        """OIM - OR immediate with memory (indexed)."""
        code = assemble("OIM #$01,$10,X")
        assert code == bytes([0x62, 0x01, 0x10])

    def test_eim_direct(self):
        """EIM - XOR immediate with memory (direct)."""
        code = assemble("EIM #$FF,$50")
        assert code == bytes([0x75, 0xFF, 0x50])

    def test_eim_indexed(self):
        """EIM - XOR immediate with memory (indexed)."""
        code = assemble("EIM #$AA,$10,X")
        assert code == bytes([0x65, 0xAA, 0x10])

    def test_tim_direct(self):
        """TIM - Test bits immediate with memory (direct)."""
        code = assemble("TIM #$01,$50")
        assert code == bytes([0x7B, 0x01, 0x50])

    def test_tim_indexed(self):
        """TIM - Test bits immediate with memory (indexed)."""
        code = assemble("TIM #$80,$10,X")
        assert code == bytes([0x6B, 0x80, 0x10])


# =============================================================================
# Directive Tests
# =============================================================================

class TestDirectives:
    """Test assembler directives."""

    def test_org_directive(self):
        """ORG sets the program counter."""
        source = """
            ORG $2100
            NOP
        """
        raw = assemble_raw(source)
        # Check OB3 header has correct address
        assert raw[:3] == b"ORG"
        # Address is at bytes 5-6 (big-endian)
        assert raw[5:7] == bytes([0x21, 0x00])

    def test_fcb_single(self):
        """FCB (Form Constant Byte) single value."""
        code = assemble("FCB $41")
        assert code == bytes([0x41])

    def test_fcb_multiple(self):
        """FCB multiple values."""
        code = assemble("FCB $01,$02,$03")
        assert code == bytes([0x01, 0x02, 0x03])

    def test_fdb_single(self):
        """FDB (Form Double Byte) single value."""
        code = assemble("FDB $1234")
        assert code == bytes([0x12, 0x34])  # Big-endian

    def test_fdb_multiple(self):
        """FDB multiple values."""
        code = assemble("FDB $1234,$5678")
        assert code == bytes([0x12, 0x34, 0x56, 0x78])

    def test_fcc_string(self):
        """FCC (Form Constant Characters) string."""
        code = assemble('FCC "Hello"')
        assert code == b"Hello"

    def test_fcc_with_null(self):
        """FCC followed by null terminator."""
        source = '''
            FCC "Hello"
            FCB 0
        '''
        code = assemble(source)
        assert code == b"Hello\x00"

    def test_rmb_reserve(self):
        """RMB (Reserve Memory Bytes)."""
        source = """
            ORG $2100
            FCB $AA
            RMB 5
            FCB $BB
        """
        code = assemble(source)
        # $AA, then 5 zeros, then $BB
        assert len(code) == 7
        assert code[0] == 0xAA
        assert code[1:6] == bytes([0x00] * 5)
        assert code[6] == 0xBB

    def test_equ_constant(self):
        """EQU defines a constant."""
        source = """
VALUE   EQU $10
        LDAA #VALUE
        """
        code = assemble(source)
        assert code == bytes([0x86, 0x10])

    def test_equ_expression(self):
        """EQU with expression."""
        source = """
BASE    EQU $2000
OFFSET  EQU $100
ADDR    EQU BASE+OFFSET
        LDX #ADDR
        """
        code = assemble(source)
        assert code == bytes([0xCE, 0x21, 0x00])


# =============================================================================
# Label Tests
# =============================================================================

class TestLabels:
    """Test label definition and reference."""

    def test_label_definition(self):
        """Label on its own line."""
        source = """
            ORG $2100
START:
            NOP
            JMP START
        """
        code = assemble(source)
        # NOP ($01), JMP ($7E, $21, $00)
        assert code[0] == 0x01
        assert code[1:4] == bytes([0x7E, 0x21, 0x00])

    def test_label_same_line(self):
        """Label on same line as instruction."""
        source = """
            ORG $2100
START:  NOP
            JMP START
        """
        code = assemble(source)
        assert code[0] == 0x01
        assert code[1:4] == bytes([0x7E, 0x21, 0x00])

    def test_forward_reference(self):
        """Forward reference to label."""
        source = """
            ORG $2100
            JMP END
            NOP
END:        RTS
        """
        code = assemble(source)
        # JMP to END at $2104
        assert code[0:3] == bytes([0x7E, 0x21, 0x04])

    def test_undefined_label(self):
        """Reference to undefined label should raise error."""
        # Note: The assembler wraps specific errors in AssemblerError
        from psion_sdk.errors import AssemblerError
        source = """
            JMP NOWHERE
        """
        with pytest.raises(AssemblerError):
            assemble(source)


# =============================================================================
# OB3 File Format Tests
# =============================================================================

class TestOB3Format:
    """Test OB3 output file format."""

    def test_ob3_header(self):
        """OB3 file should have correct header."""
        source = """
            ORG $2100
            NOP
        """
        raw = assemble_raw(source)
        # Check magic number
        assert raw[:3] == b"ORG"

    def test_ob3_length(self):
        """OB3 header should contain correct length."""
        source = """
            ORG $2100
            NOP
            NOP
            NOP
        """
        raw = assemble_raw(source)
        # Length at bytes 3-4 (big-endian), includes address bytes
        length = (raw[3] << 8) | raw[4]
        # 2 bytes address + 3 bytes code
        assert length == 5

    def test_ob3_address(self):
        """OB3 header should contain load address."""
        source = """
            ORG $3000
            NOP
        """
        raw = assemble_raw(source)
        # Address at bytes 5-6 (big-endian)
        addr = (raw[5] << 8) | raw[6]
        assert addr == 0x3000


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete programs."""

    def test_hello_world_pattern(self):
        """Test typical Psion 'Hello World' pattern."""
        source = """
            ORG $2100

; System call numbers
DP_PRNT EQU $11

START:
            LDX #MSG        ; Point to message
            LDAA #DP_PRNT   ; Print service
            SWI             ; Call OS
            RTS             ; Return

MSG:        FCC "Hello"
            FCB 0
        """
        code = assemble(source)
        # Verify key instruction bytes
        assert code[0] == 0xCE  # LDX immediate
        # Message address (relative to code start + offset)
        assert code[3] == 0x86  # LDAA immediate
        assert code[4] == 0x11  # DP_PRNT
        assert code[5] == 0x3F  # SWI
        assert code[6] == 0x39  # RTS

    def test_keypress_wait(self):
        """Test keypress wait pattern."""
        source = """
KB_GETK EQU $48

            LDAA #KB_GETK
            SWI
            RTS
        """
        code = assemble(source)
        assert code == bytes([0x86, 0x48, 0x3F, 0x39])

    def test_loop_with_counter(self):
        """Test loop with counter."""
        source = """
            ORG $2100

            LDAB #10        ; Counter
LOOP:       DECB            ; Decrement
            BNE LOOP        ; Loop if not zero
            RTS
        """
        code = assemble(source)
        assert code[0:2] == bytes([0xC6, 0x0A])  # LDAB #10
        assert code[2] == 0x5A  # DECB
        assert code[3] == 0x26  # BNE
        assert code[4] == 0xFD  # Offset -3 (back to LOOP)
        assert code[5] == 0x39  # RTS
