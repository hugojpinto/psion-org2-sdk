"""
Unit Tests for the Disassembler Module
======================================

This module contains comprehensive tests for both the HD6303 machine code
disassembler and the OPL QCode bytecode disassembler.

Test coverage includes:
- All HD6303 addressing modes
- HD6303-specific instructions (AIM, OIM, EIM, TIM, XGDX, SLP)
- Branch instructions with target calculation
- Symbol table annotations
- QCode opcodes relevant for debugging
- Edge cases (unknown opcodes, truncated data, empty input)
- _call_opl buffer detection and formatting

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.disassembler import (
    HD6303Disassembler,
    QCodeDisassembler,
    DisassembledInstruction,
    DisassembledQCode,
)
from psion_sdk.disassembler.hd6303 import PSION_SYSTEM_SYMBOLS, create_psion_disassembler
from psion_sdk.disassembler.qcode import (
    detect_lz_prefix,
    is_call_opl_buffer,
    QCODE_TABLE,
)
from psion_sdk.cpu import AddressingMode


# =============================================================================
# HD6303 Disassembler Tests
# =============================================================================

class TestHD6303Disassembler:
    """Tests for the HD6303 machine code disassembler."""

    def setup_method(self):
        """Create disassembler instance for each test."""
        self.disasm = HD6303Disassembler()

    # -------------------------------------------------------------------------
    # Inherent Addressing Mode Tests
    # -------------------------------------------------------------------------

    def test_inherent_nop(self):
        """Test NOP instruction (inherent mode)."""
        data = bytes([0x01])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "NOP"
        assert instr.size == 1
        assert instr.mode == AddressingMode.INHERENT
        assert instr.operand_str == ""

    def test_inherent_rts(self):
        """Test RTS instruction."""
        data = bytes([0x39])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "RTS"
        assert instr.size == 1

    def test_inherent_pshx(self):
        """Test PSHX instruction."""
        data = bytes([0x3C])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "PSHX"
        assert instr.size == 1

    def test_inherent_tsx(self):
        """Test TSX instruction."""
        data = bytes([0x30])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "TSX"
        assert instr.size == 1

    def test_inherent_xgdx(self):
        """Test HD6303-specific XGDX instruction."""
        data = bytes([0x18])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "XGDX"
        assert instr.size == 1

    def test_inherent_slp(self):
        """Test HD6303-specific SLP instruction."""
        data = bytes([0x1A])
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "SLP"
        assert instr.size == 1

    # -------------------------------------------------------------------------
    # Immediate Addressing Mode Tests
    # -------------------------------------------------------------------------

    def test_immediate_8bit(self):
        """Test 8-bit immediate addressing."""
        data = bytes([0x86, 0x42])  # LDAA #$42
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDAA"
        assert instr.size == 2
        assert instr.mode == AddressingMode.IMMEDIATE
        assert instr.operand_str == "#$42"

    def test_immediate_8bit_ascii(self):
        """Test 8-bit immediate with ASCII comment."""
        data = bytes([0x86, 0x41])  # LDAA #'A'
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.operand_str == "#$41"
        assert "'A'" in instr.comment

    def test_immediate_16bit(self):
        """Test 16-bit immediate addressing."""
        data = bytes([0xCE, 0x12, 0x34])  # LDX #$1234
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDX"
        assert instr.size == 3
        assert instr.mode == AddressingMode.IMMEDIATE
        assert instr.operand_str == "#$1234"

    def test_immediate_ldd(self):
        """Test LDD with 16-bit immediate."""
        data = bytes([0xCC, 0xAB, 0xCD])  # LDD #$ABCD
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDD"
        assert instr.operand_str == "#$ABCD"
        assert instr.size == 3

    # -------------------------------------------------------------------------
    # Direct Addressing Mode Tests
    # -------------------------------------------------------------------------

    def test_direct_ldaa(self):
        """Test direct (zero-page) addressing."""
        data = bytes([0x96, 0x40])  # LDAA $40
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDAA"
        assert instr.size == 2
        assert instr.mode == AddressingMode.DIRECT
        assert instr.operand_str == "$40"

    def test_direct_staa(self):
        """Test STAA direct."""
        data = bytes([0x97, 0xA5])  # STAA $A5
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "STAA"
        assert instr.operand_str == "$A5"

    # -------------------------------------------------------------------------
    # Extended Addressing Mode Tests
    # -------------------------------------------------------------------------

    def test_extended_jsr(self):
        """Test JSR with extended addressing."""
        data = bytes([0xBD, 0x12, 0x34])  # JSR $1234
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "JSR"
        assert instr.size == 3
        assert instr.mode == AddressingMode.EXTENDED
        assert instr.operand_str == "$1234"

    def test_extended_jmp(self):
        """Test JMP with extended addressing."""
        data = bytes([0x7E, 0xAB, 0xCD])  # JMP $ABCD
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "JMP"
        assert instr.operand_str == "$ABCD"

    def test_extended_ldaa(self):
        """Test LDAA with extended addressing."""
        data = bytes([0xB6, 0x20, 0x00])  # LDAA $2000
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDAA"
        assert instr.operand_str == "$2000"

    # -------------------------------------------------------------------------
    # Indexed Addressing Mode Tests
    # -------------------------------------------------------------------------

    def test_indexed_ldaa(self):
        """Test indexed addressing."""
        data = bytes([0xA6, 0x05])  # LDAA 5,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "LDAA"
        assert instr.size == 2
        assert instr.mode == AddressingMode.INDEXED
        assert instr.operand_str == "$05,X"

    def test_indexed_staa(self):
        """Test STAA indexed."""
        data = bytes([0xA7, 0x00])  # STAA 0,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "STAA"
        assert instr.operand_str == "$00,X"

    def test_indexed_jmp(self):
        """Test JMP indexed."""
        data = bytes([0x6E, 0x02])  # JMP 2,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "JMP"
        assert instr.operand_str == "$02,X"

    # -------------------------------------------------------------------------
    # Relative Addressing Mode Tests (Branches)
    # -------------------------------------------------------------------------

    def test_branch_forward(self):
        """Test forward branch."""
        data = bytes([0x20, 0x10])  # BRA +16 (from $8002)
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "BRA"
        assert instr.size == 2
        assert instr.mode == AddressingMode.RELATIVE
        # Target = $8000 + 2 + 16 = $8012
        assert instr.operand_str == "$8012"

    def test_branch_backward(self):
        """Test backward branch."""
        data = bytes([0x20, 0xFE])  # BRA -2 (jump to itself)
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "BRA"
        # Target = $8000 + 2 + (-2) = $8000
        assert instr.operand_str == "$8000"

    def test_branch_bne(self):
        """Test BNE conditional branch."""
        data = bytes([0x26, 0x05])  # BNE +5
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "BNE"
        # Target = $8000 + 2 + 5 = $8007
        assert instr.operand_str == "$8007"

    def test_branch_bsr(self):
        """Test BSR (branch to subroutine)."""
        data = bytes([0x8D, 0x20])  # BSR +32
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "BSR"
        # Target = $8000 + 2 + 32 = $8022
        assert instr.operand_str == "$8022"

    # -------------------------------------------------------------------------
    # HD6303-Specific Bit Manipulation Instructions
    # -------------------------------------------------------------------------

    def test_aim_indexed(self):
        """Test AIM (AND immediate with memory) indexed mode."""
        data = bytes([0x61, 0x0F, 0x05])  # AIM #$0F, 5,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "AIM"
        assert instr.size == 3
        assert "#$0F" in instr.operand_str

    def test_oim_indexed(self):
        """Test OIM (OR immediate with memory) indexed mode."""
        data = bytes([0x62, 0x80, 0x00])  # OIM #$80, 0,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "OIM"
        assert instr.size == 3

    def test_eim_indexed(self):
        """Test EIM (XOR immediate with memory) indexed mode."""
        data = bytes([0x65, 0xFF, 0x02])  # EIM #$FF, 2,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "EIM"
        assert instr.size == 3

    def test_tim_indexed(self):
        """Test TIM (test immediate with memory) indexed mode."""
        data = bytes([0x6B, 0x01, 0x00])  # TIM #$01, 0,X
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == "TIM"
        assert instr.size == 3

    # -------------------------------------------------------------------------
    # Symbol Table Tests
    # -------------------------------------------------------------------------

    def test_symbol_table_direct(self):
        """Test symbol annotation for direct addressing."""
        disasm = HD6303Disassembler(symbol_table={0xA5: "RTA_SP"})
        data = bytes([0x97, 0xA5])  # STAA $A5
        instr = disasm.disassemble_one(data, address=0x8000)

        assert "RTA_SP" in instr.comment

    def test_symbol_table_extended(self):
        """Test symbol annotation for extended addressing."""
        disasm = HD6303Disassembler(symbol_table={0x1234: "MY_FUNC"})
        data = bytes([0xBD, 0x12, 0x34])  # JSR $1234
        instr = disasm.disassemble_one(data, address=0x8000)

        assert "MY_FUNC" in instr.comment

    def test_symbol_table_immediate(self):
        """Test symbol annotation for immediate addressing."""
        disasm = HD6303Disassembler(symbol_table={0xABCD: "BUFFER"})
        data = bytes([0xCE, 0xAB, 0xCD])  # LDX #$ABCD
        instr = disasm.disassemble_one(data, address=0x8000)

        assert "BUFFER" in instr.comment

    def test_add_symbol(self):
        """Test adding symbol after construction."""
        self.disasm.add_symbol(0x2000, "MY_VAR")
        data = bytes([0xB6, 0x20, 0x00])  # LDAA $2000
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert "MY_VAR" in instr.comment

    def test_psion_symbols(self):
        """Test pre-configured Psion system symbols."""
        disasm = create_psion_disassembler()
        data = bytes([0xDE, 0xA9])  # LDX $A9
        instr = disasm.disassemble_one(data, address=0x8000)

        assert "RTA_PC" in instr.comment

    # -------------------------------------------------------------------------
    # Multiple Instructions Tests
    # -------------------------------------------------------------------------

    def test_disassemble_multiple(self):
        """Test disassembling multiple instructions."""
        data = bytes([
            0x01,              # NOP
            0x86, 0x42,        # LDAA #$42
            0x97, 0x50,        # STAA $50
            0x39,              # RTS
        ])
        instructions = self.disasm.disassemble(data, start_address=0x8000)

        assert len(instructions) == 4
        assert instructions[0].mnemonic == "NOP"
        assert instructions[0].address == 0x8000
        assert instructions[1].mnemonic == "LDAA"
        assert instructions[1].address == 0x8001
        assert instructions[2].mnemonic == "STAA"
        assert instructions[2].address == 0x8003
        assert instructions[3].mnemonic == "RTS"
        assert instructions[3].address == 0x8005

    def test_disassemble_count_limit(self):
        """Test limiting instruction count."""
        data = bytes([0x01] * 10)  # 10 NOPs
        instructions = self.disasm.disassemble(data, start_address=0x8000, count=3)

        assert len(instructions) == 3

    def test_disassemble_to_text(self):
        """Test text output formatting."""
        data = bytes([0x39])  # RTS
        text = self.disasm.disassemble_to_text(data, start_address=0x8000)

        assert "$8000" in text
        assert "RTS" in text

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_unknown_opcode(self):
        """Test handling of unknown opcode."""
        data = bytes([0x02])  # Not a valid HD6303 opcode
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert instr.mnemonic == ".BYTE"
        assert "$02" in instr.operand_str
        assert "unknown" in instr.comment.lower()

    def test_truncated_instruction(self):
        """Test handling of truncated instruction."""
        data = bytes([0xBD, 0x12])  # JSR needs 3 bytes, only 2 provided
        instr = self.disasm.disassemble_one(data, address=0x8000)

        assert "incomplete" in instr.comment.lower() or instr.operand_str == "???"

    def test_empty_data(self):
        """Test handling of empty data."""
        with pytest.raises(ValueError):
            self.disasm.disassemble_one(bytes(), address=0x8000)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = bytes([0x86, 0x42])  # LDAA #$42
        instr = self.disasm.disassemble_one(data, address=0x8000)
        d = instr.to_dict()

        assert d["address"] == "$8000"
        assert d["address_int"] == 0x8000
        assert d["mnemonic"] == "LDAA"
        assert d["operand"] == "#$42"
        assert d["size"] == 2


# =============================================================================
# QCode Disassembler Tests
# =============================================================================

class TestQCodeDisassembler:
    """Tests for the OPL QCode bytecode disassembler."""

    def setup_method(self):
        """Create disassembler instance for each test."""
        self.disasm = QCodeDisassembler()

    # -------------------------------------------------------------------------
    # Basic Opcode Tests
    # -------------------------------------------------------------------------

    def test_stop_opcode(self):
        """Test STOP opcode ($59)."""
        data = bytes([0x59])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x59
        assert instr.mnemonic == "STOP"
        assert instr.size == 1

    def test_return_opcode(self):
        """Test RETURN opcode ($7B)."""
        data = bytes([0x7B])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x7B
        assert instr.mnemonic == "RETURN"
        assert instr.size == 1

    def test_usr_opcode(self):
        """Test USR opcode ($9F)."""
        data = bytes([0x9F])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x9F
        assert instr.mnemonic == "USR"
        assert instr.size == 1

    def test_peekw_opcode(self):
        """Test PEEKW opcode ($9C)."""
        data = bytes([0x9C])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x9C
        assert instr.mnemonic == "PEEKW"

    # -------------------------------------------------------------------------
    # Push Operations Tests
    # -------------------------------------------------------------------------

    def test_push_word(self):
        """Test PUSH_W (push 16-bit integer) opcode ($22)."""
        data = bytes([0x22, 0x12, 0x34])  # PUSH_W $1234 (big-endian)
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x22
        assert instr.mnemonic == "PUSH_W"
        assert instr.size == 3
        assert "$1234" in instr.operand_str

    def test_push_byte(self):
        """Test PUSH_B (push 8-bit integer) opcode ($23)."""
        data = bytes([0x23, 0x42])  # PUSH_B $42
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x23
        assert instr.mnemonic == "PUSH_B"
        assert instr.size == 2
        assert "$42" in instr.operand_str

    def test_push_0(self):
        """Test PUSH_0 opcode ($20)."""
        data = bytes([0x20])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x20
        assert instr.mnemonic == "PUSH_0"
        assert instr.size == 1

    def test_push_1(self):
        """Test PUSH_1 opcode ($21)."""
        data = bytes([0x21])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x21
        assert instr.mnemonic == "PUSH_1"
        assert instr.size == 1

    # -------------------------------------------------------------------------
    # Procedure Call Tests
    # -------------------------------------------------------------------------

    def test_qco_proc(self):
        """Test QCO_PROC opcode ($7D) - procedure call."""
        data = bytes([0x7D, 0x03, 0x53, 0x55, 0x42])  # QCO_PROC "SUB"
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.opcode == 0x7D
        assert instr.mnemonic == "QCO_PROC"
        assert instr.size == 5  # opcode + length + 3 chars
        assert '"SUB"' in instr.operand_str
        assert "length=3" in instr.comment

    def test_qco_proc_long_name(self):
        """Test QCO_PROC with longer procedure name."""
        data = bytes([0x7D, 0x06, 0x41, 0x5A, 0x4D, 0x45, 0x4E, 0x55])  # "AZMENU"
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.mnemonic == "QCO_PROC"
        assert '"AZMENU"' in instr.operand_str
        assert instr.size == 8

    # -------------------------------------------------------------------------
    # Operator Tests
    # -------------------------------------------------------------------------

    def test_add_operator(self):
        """Test ADD operator ($46)."""
        data = bytes([0x46])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.mnemonic == "ADD"

    def test_sub_operator(self):
        """Test SUB operator ($47)."""
        data = bytes([0x47])
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert instr.mnemonic == "SUB"

    def test_comparison_operators(self):
        """Test comparison operators."""
        operators = {
            0x52: "EQ",
            0x53: "NE",
            0x54: "GT",
            0x55: "LT",
            0x56: "GE",
            0x57: "LE",
        }
        for opcode, expected_mnemonic in operators.items():
            data = bytes([opcode])
            instr = self.disasm.disassemble_one(data, address=0x2700)
            assert instr.mnemonic == expected_mnemonic

    # -------------------------------------------------------------------------
    # _call_opl Buffer Tests
    # -------------------------------------------------------------------------

    def test_call_opl_buffer_format(self):
        """Test special _call_opl buffer formatting."""
        # Typical _call_opl buffer: QCO_PROC "SUB", PUSH restore, PUSH SP, USR
        buffer = bytes([
            0x7D, 0x03, 0x53, 0x55, 0x42,  # QCO_PROC "SUB"
            0x22, 0x12, 0x34,              # PUSH_W $1234 (restore addr)
            0x22, 0x1F, 0xF0,              # PUSH_W $1FF0 (saved SP)
            0x9F,                           # USR
        ])
        result = self.disasm.disassemble_call_opl_buffer(buffer, start_address=0x2705)

        assert "_call_opl" in result
        assert "QCO_PROC" in result
        assert '"SUB"' in result
        assert "PUSH_W" in result
        assert "USR" in result

    def test_detect_lz_prefix(self):
        """Test LZ 4-line mode prefix detection."""
        # LZ prefix is $59 $B2 (STOP + SIN)
        lz_code = bytes([0x59, 0xB2, 0x7B])
        non_lz_code = bytes([0x7B, 0x9F])

        assert detect_lz_prefix(lz_code) is True
        assert detect_lz_prefix(non_lz_code) is False

    def test_is_call_opl_buffer_valid(self):
        """Test _call_opl buffer detection - valid buffer."""
        buffer = bytes([
            0x7D, 0x03, 0x53, 0x55, 0x42,  # QCO_PROC "SUB"
            0x22, 0x12, 0x34,              # PUSH_W
            0x22, 0x1F, 0xF0,              # PUSH_W
            0x9F,                           # USR
        ])
        assert is_call_opl_buffer(buffer) is True

    def test_is_call_opl_buffer_invalid(self):
        """Test _call_opl buffer detection - invalid buffer."""
        # Doesn't start with $7D
        buffer1 = bytes([0x22, 0x12, 0x34, 0x9F])
        assert is_call_opl_buffer(buffer1) is False

        # Doesn't end with $9F
        buffer2 = bytes([0x7D, 0x03, 0x53, 0x55, 0x42, 0x7B])
        assert is_call_opl_buffer(buffer2) is False

        # Too short
        buffer3 = bytes([0x7D, 0x9F])
        assert is_call_opl_buffer(buffer3) is False

    # -------------------------------------------------------------------------
    # Multiple Instructions Tests
    # -------------------------------------------------------------------------

    def test_disassemble_multiple(self):
        """Test disassembling multiple QCode instructions."""
        data = bytes([
            0x20,              # PUSH_0
            0x21,              # PUSH_1
            0x46,              # ADD
            0x7B,              # RETURN
        ])
        instructions = self.disasm.disassemble(data, start_address=0x2700)

        assert len(instructions) == 4
        assert instructions[0].mnemonic == "PUSH_0"
        assert instructions[0].address == 0x2700
        assert instructions[1].mnemonic == "PUSH_1"
        assert instructions[1].address == 0x2701
        assert instructions[2].mnemonic == "ADD"
        assert instructions[2].address == 0x2702
        assert instructions[3].mnemonic == "RETURN"
        assert instructions[3].address == 0x2703

    def test_disassemble_count_limit(self):
        """Test limiting instruction count."""
        data = bytes([0x20] * 10)  # 10 PUSH_0s
        instructions = self.disasm.disassemble(data, start_address=0x2700, count=5)

        assert len(instructions) == 5

    def test_disassemble_to_text(self):
        """Test text output formatting."""
        data = bytes([0x7B])  # RETURN
        text = self.disasm.disassemble_to_text(data, start_address=0x2700)

        assert "$2700" in text
        assert "RETURN" in text

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_unknown_opcode(self):
        """Test handling of unknown QCode opcode."""
        data = bytes([0xFF])  # Not a known opcode
        instr = self.disasm.disassemble_one(data, address=0x2700)

        assert "???" in instr.mnemonic or "FF" in instr.mnemonic

    def test_truncated_push_word(self):
        """Test handling of truncated PUSH_W."""
        data = bytes([0x22, 0x12])  # PUSH_W needs 3 bytes
        instr = self.disasm.disassemble_one(data, address=0x2700)

        # Should handle gracefully
        assert instr.opcode == 0x22

    def test_truncated_proc_call(self):
        """Test handling of truncated QCO_PROC."""
        data = bytes([0x7D, 0x05, 0x41, 0x42])  # Claims 5 chars, only 2 provided
        instr = self.disasm.disassemble_one(data, address=0x2700)

        # Should handle gracefully
        assert instr.opcode == 0x7D

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = bytes([0x22, 0x12, 0x34])  # PUSH_W $1234
        instr = self.disasm.disassemble_one(data, address=0x2700)
        d = instr.to_dict()

        assert d["address"] == "$2700"
        assert d["address_int"] == 0x2700
        assert d["mnemonic"] == "PUSH_W"
        assert d["size"] == 3


# =============================================================================
# CLI Tests
# =============================================================================

class TestDisassemblerCLI:
    """Tests for the psdisasm CLI tool."""

    def test_cli_help(self, tmp_path):
        """Test CLI help output."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Disassemble HD6303" in result.output

    def test_cli_version(self, tmp_path):
        """Test CLI version output."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0

    def test_cli_basic_disassembly(self, tmp_path):
        """Test basic disassembly."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        # Create test binary
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x01, 0x39]))  # NOP, RTS

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file)])

        assert result.exit_code == 0
        assert "NOP" in result.output
        assert "RTS" in result.output

    def test_cli_with_address(self, tmp_path):
        """Test disassembly with base address."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x39]))  # RTS

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--address", "0x8000"])

        assert result.exit_code == 0
        assert "$8000" in result.output

    def test_cli_qcode_mode(self, tmp_path):
        """Test QCode disassembly mode."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x7B]))  # RETURN

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--qcode"])

        assert result.exit_code == 0
        assert "RETURN" in result.output
        assert "QCode" in result.output

    def test_cli_hex_dump(self, tmp_path):
        """Test hex dump output."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x01, 0x39]))  # NOP, RTS

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--hex"])

        assert result.exit_code == 0
        assert "Hex dump" in result.output
        assert "01 39" in result.output

    def test_cli_output_file(self, tmp_path):
        """Test output to file."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x39]))  # RTS
        output_file = tmp_path / "output.asm"

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "-o", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "RTS" in content

    def test_cli_count_limit(self, tmp_path):
        """Test instruction count limit."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x01] * 100))  # 100 NOPs

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--count", "3"])

        assert result.exit_code == 0
        # Should only have 3 NOP lines
        assert result.output.count("NOP") == 3

    def test_cli_no_bytes(self, tmp_path):
        """Test compact output without bytes."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([0x86, 0x42]))  # LDAA #$42

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--no-bytes"])

        assert result.exit_code == 0
        assert "LDAA" in result.output
        # Should not have the raw bytes "86 42"
        assert "86 42" not in result.output

    def test_cli_call_opl_mode(self, tmp_path):
        """Test _call_opl buffer mode."""
        from click.testing import CliRunner
        from psion_sdk.cli.psdisasm import main

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(bytes([
            0x7D, 0x03, 0x53, 0x55, 0x42,  # QCO_PROC "SUB"
            0x22, 0x12, 0x34,              # PUSH_W
            0x22, 0x1F, 0xF0,              # PUSH_W
            0x9F,                           # USR
        ]))

        runner = CliRunner()
        result = runner.invoke(main, [str(test_file), "--call-opl"])

        assert result.exit_code == 0
        assert "_call_opl" in result.output
        assert "QCO_PROC" in result.output
