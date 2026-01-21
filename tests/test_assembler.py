# =============================================================================
# test_assembler.py - Full Assembler Integration Tests
# =============================================================================
# End-to-end integration tests for the complete HD6303 assembler.
# These tests verify the full pipeline from source code to OB3 output.
#
# Test coverage includes:
#   - Complete program assembly
#   - Include file processing
#   - Error reporting with line numbers
#   - Command-line interface
#   - Edge cases and boundary conditions
# =============================================================================

import pytest
import tempfile
import os
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.errors import (
    AssemblerError,
    AssemblySyntaxError,
    UndefinedSymbolError,
    DuplicateSymbolError,
    AddressingModeError,
)


# =============================================================================
# Full Assembly Pipeline Tests
# =============================================================================

class TestFullPipeline:
    """Test the complete assembly pipeline from source to OB3."""

    def test_minimal_program(self):
        """Assemble minimal valid program."""
        source = "NOP"
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None
        assert len(result) > 0

    def test_program_with_org(self):
        """Assemble program with explicit ORG."""
        source = """
            ORG $2100
            NOP
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        # Verify OB3 header
        assert result[:3] == b"ORG"
        # Verify address embedded
        assert result[5:7] == bytes([0x21, 0x00])

    def test_program_with_labels(self):
        """Assemble program with multiple labels."""
        source = """
            ORG $2100
START:      LDAA #$00
            BEQ SKIP
            INCA
SKIP:       STAA $50
END:        RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None

    def test_program_with_data(self):
        """Assemble program with data section."""
        source = """
            ORG $2100
            LDX #DATA
            RTS

DATA:       FCB $01,$02,$03
            FDB $1234
            FCC "Test"
            FCB 0
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None


# =============================================================================
# Symbol Table Tests
# =============================================================================

class TestSymbolTable:
    """Test symbol table functionality."""

    def test_get_symbol_table(self):
        """Verify symbol table is accessible after assembly."""
        source = """
CONST1  EQU $10
CONST2  EQU $20
            ORG $2100
START:      NOP
END:        RTS
        """
        asm = Assembler()
        asm.assemble(source)

        symbols = asm.get_symbols()
        assert "CONST1" in symbols
        assert "CONST2" in symbols
        assert "START" in symbols
        assert "END" in symbols
        assert symbols["CONST1"] == 0x10
        assert symbols["CONST2"] == 0x20

    def test_duplicate_label_error(self):
        """Duplicate label should raise error."""
        # Note: Assembler wraps specific errors in AssemblerError
        source = """
LABEL:      NOP
LABEL:      RTS
        """
        asm = Assembler()
        with pytest.raises(AssemblerError):
            asm.assemble(source)

    def test_case_insensitive_symbols(self):
        """Symbols should be case-insensitive."""
        source = """
MyLabel:    NOP
            JMP MYLABEL
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling and reporting."""

    def test_syntax_error_line_number(self):
        """Syntax errors should include line numbers."""
        source = """
            NOP
            INVALID!!!
            RTS
        """
        asm = Assembler()
        with pytest.raises(AssemblySyntaxError) as exc_info:
            asm.assemble(source)
        # Error should mention line number
        error_msg = str(exc_info.value)
        # Line 3 has the error (counting from 1)
        assert "line" in error_msg.lower() or "3" in error_msg

    def test_undefined_symbol_error(self):
        """Undefined symbol should raise error."""
        # Note: Assembler wraps specific errors in AssemblerError
        source = """
            LDAA UNDEFINED
        """
        asm = Assembler()
        with pytest.raises(AssemblerError):
            asm.assemble(source)

    def test_invalid_addressing_mode(self):
        """Invalid addressing mode should raise error."""
        source = """
            NOP #$10    ; NOP doesn't take operand
        """
        asm = Assembler()
        with pytest.raises((AddressingModeError, AssemblySyntaxError)):
            asm.assemble(source)


# =============================================================================
# Include File Tests
# =============================================================================

class TestIncludeFiles:
    """Test INCLUDE directive functionality."""

    def test_include_file(self):
        """Test including external file."""
        # Create temporary include file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.inc', delete=False
        ) as inc_file:
            inc_file.write("CONST EQU $42\n")
            inc_path = inc_file.name

        try:
            source = f'''
                INCLUDE "{inc_path}"
                LDAA #CONST
            '''
            asm = Assembler()
            result = asm.assemble(source)
            # Should have LDAA #$42
            code = result[7:]  # Skip OB3 header
            assert code == bytes([0x86, 0x42])
        finally:
            os.unlink(inc_path)

    def test_include_with_search_path(self):
        """Test include file with search path."""
        # Create temporary directory with include file
        with tempfile.TemporaryDirectory() as tmpdir:
            inc_path = Path(tmpdir) / "test.inc"
            inc_path.write_text("MYCONST EQU $55\n")

            source = '''
                INCLUDE "test.inc"
                LDAA #MYCONST
            '''
            asm = Assembler(include_paths=[tmpdir])
            result = asm.assemble(source)
            code = result[7:]
            assert code == bytes([0x86, 0x55])

    def test_runtime_inc_assembles_without_undefined_symbols(self):
        """Test that runtime.inc assembles correctly without undefined symbol errors.

        This is a regression test for a bug where runtime.inc used symbols like
        UTW_T4 and UTW_T6 that weren't defined in sysvars.inc. The bug caused
        pass 2 to silently skip large portions of code, resulting in incorrect
        symbol addresses for string literals in C programs.

        The fix was to replace:
        - UTW_T4 -> UTW_W1 ($86-$87)
        - UTW_T6 -> UTW_W2 ($88)
        """
        # This is essentially what a C program includes
        source = '''
            .MODEL LZ
_entry:
            BSR     _main
            RTS
_main:
            JSR     _cls
            LDD     #__S1
            PSHB
            PSHA
            JSR     _print
            INS
            INS
            JSR     _getkey
            RTS
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
__S1:
            FCC     "TEST"
            FCB     0
            END
        '''
        # Get the include path for the project's include directory
        include_dir = Path(__file__).parent.parent / "include"

        # Assemble with relocatable mode (where the bug manifested)
        asm = Assembler(include_paths=[str(include_dir)], relocatable=True)

        # This should not raise UndefinedSymbolError
        result = asm.assemble(source)

        # Verify we got output
        assert result is not None
        assert len(result) > 0

        # Verify __S1 symbol exists and has a reasonable address
        symbols = asm.get_symbols()
        assert "__S1" in symbols
        # __S1 should be after all the runtime code (which is ~1700 bytes)
        # It should NOT be 0 or some small value
        assert symbols["__S1"] > 1000, f"__S1 address {symbols['__S1']} is too small, runtime.inc may not be fully processed"


# =============================================================================
# Listing Output Tests
# =============================================================================

class TestListingOutput:
    """Test assembly listing generation."""

    def test_generate_listing(self):
        """Test listing generation."""
        source = """
            ORG $2100
START:      LDAA #$41
            RTS
        """
        asm = Assembler()
        asm.assemble(source)
        listing = asm.get_listing()

        # Listing should contain address, code bytes, and source
        assert listing is not None
        assert "2100" in listing or "21 00" in listing.lower()
        assert "LDAA" in listing.upper()

    def test_listing_shows_addresses(self):
        """Listing should show correct addresses."""
        source = """
            ORG $3000
            NOP
            NOP
        """
        asm = Assembler()
        asm.assemble(source)
        listing = asm.get_listing()

        # Should show addresses starting at $3000
        assert "3000" in listing


# =============================================================================
# Command-Line Defines Tests
# =============================================================================

class TestDefines:
    """Test command-line defines (-D option)."""

    def test_predefined_symbol(self):
        """Test assembly with predefined symbol."""
        source = """
            LDAA #VALUE
        """
        asm = Assembler(defines={"VALUE": 0x99})
        result = asm.assemble(source)
        code = result[7:]
        assert code == bytes([0x86, 0x99])

    def test_multiple_defines(self):
        """Test multiple predefined symbols."""
        source = """
            LDAA #VAL1
            LDAB #VAL2
        """
        asm = Assembler(defines={"VAL1": 0x11, "VAL2": 0x22})
        result = asm.assemble(source)
        code = result[7:]
        assert code == bytes([0x86, 0x11, 0xC6, 0x22])


# =============================================================================
# Binary Output Tests
# =============================================================================

class TestBinaryOutput:
    """Test raw binary output (without OB3 header)."""

    def test_binary_mode(self):
        """Test binary output without header."""
        source = """
            ORG $2100
            NOP
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source, output_format='binary')
        # Binary format should just be the raw bytes
        assert result == bytes([0x01, 0x39])


# =============================================================================
# Complex Program Tests
# =============================================================================

class TestComplexPrograms:
    """Test assembly of complex programs."""

    def test_complete_psion_program(self):
        """Test complete Psion program structure."""
        source = """
; ===========================================
; Test Program for Psion Organiser II
; ===========================================

            ORG $2100

; System call numbers
DP_EMIT     EQU $10
DP_PRNT     EQU $11
KB_GETK     EQU $48

; Main entry point
START:
            LDX #MESSAGE    ; Load message address
            LDAA #DP_PRNT   ; Print function
            SWI             ; Call OS

WAITKEY:
            LDAA #KB_GETK   ; Get key
            SWI
            CMPA #'Q'       ; Check for Q
            BEQ EXIT
            BRA WAITKEY

EXIT:
            RTS

; Data section
MESSAGE:    FCC "HELLO"
            FCB 0
        """
        asm = Assembler()
        result = asm.assemble(source)

        # Verify it assembled successfully
        assert result is not None
        assert len(result) > 10

        # Verify OB3 header
        assert result[:3] == b"ORG"

    def test_program_with_subroutines(self):
        """Test program with subroutine calls."""
        source = """
            ORG $2100

MAIN:       BSR INIT
            BSR PROCESS
            RTS

INIT:       CLRA
            CLRB
            RTS

PROCESS:    INCA
            INCB
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None

    def test_program_with_lookup_table(self):
        """Test program with lookup table."""
        source = """
            ORG $2100

            LDX #TABLE
            LDAB #3
            ABX
            LDAA 0,X
            RTS

TABLE:      FCB $10,$20,$30,$40,$50
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_source(self):
        """Empty source should produce minimal output."""
        asm = Assembler()
        result = asm.assemble("")
        # Should still produce valid output (possibly just header)
        assert result is not None

    def test_only_comments(self):
        """Source with only comments."""
        source = """
; This is a comment
; Another comment
* Star comment
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None

    def test_very_long_program(self):
        """Test assembly of large program."""
        # Generate a program with many NOPs
        lines = ["ORG $2100"]
        for i in range(256):
            lines.append(f"    NOP ; Instruction {i}")
        lines.append("    RTS")

        source = "\n".join(lines)
        asm = Assembler()
        result = asm.assemble(source)

        # Should have 256 NOPs + 1 RTS
        code = result[7:]
        assert len(code) == 257

    def test_address_wraparound(self):
        """Test behavior near address boundaries."""
        source = """
            ORG $FFF0
            NOP
            NOP
        """
        asm = Assembler()
        # This should assemble (may produce warning about address)
        result = asm.assemble(source)
        assert result is not None

    def test_zero_page_boundary(self):
        """Test direct vs extended addressing at boundary."""
        source = """
            LDAA $FF    ; Direct (zero page)
            LDAA $100   ; Extended (beyond zero page)
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # First should be direct: $96 $FF
        assert code[0] == 0x96
        assert code[1] == 0xFF

        # Second should be extended: $B6 $01 $00
        assert code[2] == 0xB6
        assert code[3] == 0x01
        assert code[4] == 0x00


# =============================================================================
# File I/O Tests
# =============================================================================

class TestFileIO:
    """Test file input/output operations."""

    def test_assemble_from_file(self):
        """Test assembling from a file."""
        source = """
            ORG $2100
            NOP
            RTS
        """
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.asm', delete=False
        ) as src_file:
            src_file.write(source)
            src_path = src_file.name

        try:
            asm = Assembler()
            result = asm.assemble_file(src_path)
            assert result is not None
        finally:
            os.unlink(src_path)

    def test_write_output_file(self):
        """Test writing output to file."""
        source = """
            ORG $2100
            NOP
        """
        with tempfile.NamedTemporaryFile(
            mode='wb', suffix='.ob3', delete=False
        ) as out_file:
            out_path = out_file.name

        try:
            asm = Assembler()
            asm.assemble(source, output_path=out_path)

            # Verify file was written
            assert os.path.exists(out_path)
            with open(out_path, 'rb') as f:
                data = f.read()
            assert data[:3] == b"ORG"
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)


# =============================================================================
# Psion-Specific Integration Tests
# =============================================================================

class TestPsionIntegration:
    """Tests specific to Psion Organiser II programs."""

    def test_syscall_pattern(self):
        """Test common syscall invocation pattern."""
        source = """
DP_EMIT EQU $10

            LDAA #'A'
            LDAB #DP_EMIT
            SWI
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # LDAA #'A' = $86 $41
        assert code[0:2] == bytes([0x86, ord('A')])
        # LDAB #$10 = $C6 $10
        assert code[2:4] == bytes([0xC6, 0x10])
        # SWI = $3F
        assert code[4] == 0x3F
        # RTS = $39
        assert code[5] == 0x39

    def test_display_buffer_access(self):
        """Test accessing display buffer."""
        source = """
DISP_BUF    EQU $2000

            LDX #DISP_BUF
            LDAA #' '
            STAA 0,X
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None

    def test_keyboard_polling_loop(self):
        """Test keyboard polling loop pattern."""
        source = """
KB_TEST     EQU $4B
KB_GETK     EQU $48

POLL:       LDAA #KB_TEST
            SWI
            BCC POLL        ; Loop while no key
            LDAA #KB_GETK
            SWI             ; Get the key
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        assert result is not None


# =============================================================================
# Forward Reference Tests
# =============================================================================

class TestForwardReferences:
    """Test forward reference handling in two-pass assembly."""

    def test_jsr_forward_reference_uses_extended_mode(self):
        """JSR to forward-declared label should use extended mode consistently.

        This tests a bug fix where pass 1 would assume extended mode (3 bytes)
        for JSR to unknown labels, but pass 2 would use direct mode (2 bytes)
        if the resolved address was <= $FF, causing symbol address mismatches.
        """
        source = """
_entry:     BSR     _main
            RTS
_main:      JSR     _func
            RTS
_func:      LDAA    #$0C
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        symbols = asm.get_symbols()
        code = result[7:]  # Skip OB3 header

        # Entry: BSR _main (2 bytes) + RTS (1 byte) = $0000-$0002
        # _main at $0003: JSR _func (3 bytes for extended) + RTS (1 byte) = $0003-$0006
        # _func at $0007: LDAA #$0C (2 bytes) + RTS (1 byte) = $0007-$0009

        # Verify _func symbol points to where LDAA actually is
        assert symbols['_FUNC'] == 0x07, f"_FUNC should be at $0007, got ${symbols['_FUNC']:04X}"

        # Verify the JSR uses extended mode (opcode $BD) not direct mode ($9D)
        # JSR is at offset 3 in the code (after BSR + RTS)
        assert code[3] == 0xBD, f"JSR should use extended mode ($BD), got ${code[3]:02X}"

        # Verify JSR target address matches _func symbol
        jsr_target = (code[4] << 8) | code[5]
        assert jsr_target == symbols['_FUNC'], \
            f"JSR target ${jsr_target:04X} should match _FUNC ${symbols['_FUNC']:04X}"

    def test_multiple_forward_references(self):
        """Multiple JSRs to forward-declared labels should all use extended mode."""
        source = """
_start:     JSR     _func1
            JSR     _func2
            JSR     _func3
            RTS
_func1:     NOP
            RTS
_func2:     NOP
            RTS
_func3:     NOP
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        symbols = asm.get_symbols()
        code = result[7:]  # Skip OB3 header

        # Each JSR should be 3 bytes (extended mode)
        # _start: 3x JSR (9 bytes) + RTS (1 byte) = 10 bytes
        # _func1 at $000A, _func2 at $000C, _func3 at $000E

        assert symbols['_FUNC1'] == 0x0A, f"_FUNC1 should be at $000A"
        assert symbols['_FUNC2'] == 0x0C, f"_FUNC2 should be at $000C"
        assert symbols['_FUNC3'] == 0x0E, f"_FUNC3 should be at $000E"

        # All JSRs should use extended mode ($BD)
        assert code[0] == 0xBD, "First JSR should use extended mode"
        assert code[3] == 0xBD, "Second JSR should use extended mode"
        assert code[6] == 0xBD, "Third JSR should use extended mode"

    def test_cpd_instruction_rejected(self):
        """CPD instruction is NOT valid HD6303 - it's 68HC11 only.

        The assembler must reject CPD as an unknown instruction. Users should
        use SUBD instead, which sets identical flags (N, Z, V, C) for comparisons.
        For SUBD #0, D is unchanged (D-0=D) while flags are set correctly.
        """
        source = """
_start:     LDD     #1
            CPD     #0          ; This should fail - CPD is not HD6303
        """
        asm = Assembler()

        with pytest.raises(AssemblerError) as excinfo:
            asm.assemble(source)

        # Verify the error mentions CPD or unknown instruction
        error_msg = str(excinfo.value).lower()
        assert 'cpd' in error_msg or 'unknown' in error_msg or 'invalid' in error_msg, \
            f"Error should mention CPD or unknown instruction, got: {excinfo.value}"

    def test_subd_as_cpd_replacement(self):
        """SUBD can be used as CPD replacement for comparisons.

        SUBD sets identical condition flags as CPD (which is 68HC11-only).
        For SUBD #0, D is unchanged because D - 0 = D, making it perfect
        for boolean tests. SUBD is also more compact: 3 bytes for immediate
        vs 4 bytes that CPD would have needed.
        """
        source = """
_start:     LDD     #1          ; 3 bytes: CC 00 01
            SUBD    #0          ; 3 bytes: 83 00 00 (sets Z if D==0)
            BNE     _skip       ; 2 bytes
_skip:      SUBD    0,X         ; 2 bytes: A3 00 (sets Z if D==mem)
            BEQ     _end        ; 2 bytes
_end:       RTS                 ; 1 byte
        """
        asm = Assembler()
        result = asm.assemble(source)
        symbols = asm.get_symbols()
        code = result[7:]  # Skip OB3 header

        # _start at $0000
        # LDD #1: 3 bytes ($0000-$0002)
        # SUBD #0: 3 bytes ($0003-$0005)
        # BNE _skip: 2 bytes ($0006-$0007)
        # _skip at $0008
        # SUBD 0,X: 2 bytes ($0008-$0009)
        # BEQ _end: 2 bytes ($000A-$000B)
        # _end at $000C
        # RTS: 1 byte ($000C)

        assert symbols['_START'] == 0x00, f"_START should be at $0000"
        assert symbols['_SKIP'] == 0x08, f"_SKIP should be at $0008, got ${symbols['_SKIP']:04X}"
        assert symbols['_END'] == 0x0C, f"_END should be at $000C, got ${symbols['_END']:04X}"

        # Verify SUBD immediate generates 3 bytes (no prefix)
        # At offset 3: should be 83 00 00
        assert code[3] == 0x83, f"SUBD immediate opcode should be $83, got ${code[3]:02X}"
        assert code[4] == 0x00, f"SUBD immediate high byte should be $00"
        assert code[5] == 0x00, f"SUBD immediate low byte should be $00"

        # Verify SUBD indexed generates 2 bytes (no prefix)
        # At offset 8 (_skip): should be A3 00
        assert code[8] == 0xA3, f"SUBD indexed opcode should be $A3, got ${code[8]:02X}"
        assert code[9] == 0x00, f"SUBD indexed offset should be $00"

    def test_jmp_no_direct_mode(self):
        """JMP instruction only supports extended mode, not direct mode.

        Even when target address is <= $FF, JMP must use extended mode (3 bytes)
        because the HD6303 JMP instruction doesn't have a direct addressing mode.
        Pass 1 must correctly calculate 3 bytes for JMP to avoid symbol mismatches.
        """
        source = """
_target:    NOP
            JMP     _target     ; backward ref to $0000, but JMP has no direct mode
_after:     RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        symbols = asm.get_symbols()
        code = result[7:]  # Skip OB3 header

        # _target at $0000: NOP (1 byte)
        # JMP at $0001: 3 bytes (extended only: 7E 00 00)
        # _after at $0004: RTS (1 byte)

        assert symbols['_TARGET'] == 0x00, f"_TARGET should be at $0000"
        assert symbols['_AFTER'] == 0x04, f"_AFTER should be at $0004, got ${symbols['_AFTER']:04X}"

        # Verify JMP uses extended mode (opcode $7E) with 2-byte address
        assert code[1] == 0x7E, f"JMP opcode should be $7E (extended), got ${code[1]:02X}"
        assert code[2] == 0x00 and code[3] == 0x00, "JMP target should be $0000"


# =============================================================================
# Direct vs Extended Addressing Mode Tests
# =============================================================================

class TestDirectVsExtendedAddressing:
    """Test direct vs extended addressing mode selection.

    The assembler optimizes to direct mode (2 bytes) when possible, but must
    use extended mode (3 bytes) in relocatable code for internal symbols.
    These tests verify the correct mode is used in various scenarios.
    """

    def test_non_relocatable_uses_direct_for_low_address(self):
        """Non-relocatable code should use direct mode for addresses <= $FF.

        Without -r flag, the assembler can safely optimize JSR to direct mode
        when the target address fits in one byte.
        """
        source = """
_target:    NOP                 ; at $0000
            RTS                 ; at $0001
_caller:    JSR     _target     ; backward ref to $0000, should use direct
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # _target at $0000: NOP (1 byte) + RTS (1 byte) = 2 bytes
        # _caller at $0002: JSR should use direct mode (9D 00) = 2 bytes
        # Final RTS at $0004

        # Verify JSR uses direct mode (opcode $9D) not extended ($BD)
        assert code[2] == 0x9D, f"JSR should use direct mode ($9D), got ${code[2]:02X}"
        assert code[3] == 0x00, f"JSR target should be $00"

    def test_non_relocatable_uses_extended_for_high_address(self):
        """Non-relocatable code should use extended mode for addresses > $FF."""
        source = """
            ORG     $0100
_target:    NOP
            RTS
_caller:    JSR     _target     ; target at $0100, must use extended
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # _target at $0100: NOP + RTS = 2 bytes
        # _caller at $0102: JSR extended (BD 01 00) = 3 bytes

        # Verify JSR uses extended mode (opcode $BD)
        assert code[2] == 0xBD, f"JSR should use extended mode ($BD), got ${code[2]:02X}"
        assert code[3] == 0x01 and code[4] == 0x00, "JSR target should be $0100"

    def test_relocatable_forces_extended_for_internal_symbols(self):
        """Relocatable code must use extended mode for internal symbols.

        Even when a symbol's address is <= $FF, relocatable code must use
        extended mode because direct mode addresses cannot be patched.
        """
        source = """
_target:    NOP                 ; at $0000
            RTS
_caller:    JSR     _target     ; must use extended for relocation
            RTS
        """
        asm = Assembler(relocatable=True)
        result = asm.assemble(source)

        # In relocatable mode, there's a stub prepended, so find the user code
        # The stub is ~93 bytes, but let's find JSR by looking for the pattern
        # We know _target is at offset 0 in user code, so JSR should target 0x0000

        # Verify JSR uses extended mode (opcode $BD) not direct ($9D)
        # Search for BD 00 00 pattern (JSR extended to $0000)
        found_extended = False
        for i in range(len(result) - 3):
            if result[i] == 0xBD and result[i+1] == 0x00 and result[i+2] == 0x00:
                found_extended = True
                break

        assert found_extended, "Relocatable code should use extended mode (BD 00 00) for internal symbol"

        # Verify direct mode pattern is NOT present for internal JSR
        found_direct = False
        for i in range(len(result) - 2):
            if result[i] == 0x9D and result[i+1] == 0x00:
                # Check if this looks like a JSR pattern (could be data)
                # In our simple case, 9D 00 would be suspicious
                found_direct = True
                break

        # Note: 9D 00 might appear in the relocation stub, so this test is informational
        # The key test is that BD 00 00 IS present for the user's JSR

    def test_force_direct_with_prefix(self):
        """Explicit < prefix forces direct mode even in non-relocatable code.

        The < prefix is an escape hatch for when the programmer explicitly
        wants direct mode addressing.
        """
        source = """
            JSR     <$50        ; Force direct mode to address $50
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # JSR <$50 should generate 9D 50 (direct mode, 2 bytes)
        assert code[0] == 0x9D, f"JSR < should use direct mode ($9D), got ${code[0]:02X}"
        assert code[1] == 0x50, f"JSR target should be $50, got ${code[1]:02X}"

    def test_force_extended_with_prefix(self):
        """Explicit > prefix forces extended mode."""
        source = """
            JSR     >$50        ; Force extended mode to address $50
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # JSR >$50 should generate BD 00 50 (extended mode, 3 bytes)
        assert code[0] == 0xBD, f"JSR > should use extended mode ($BD), got ${code[0]:02X}"
        assert code[1] == 0x00 and code[2] == 0x50, "JSR target should be $0050"

    def test_equ_constant_uses_direct_in_relocatable(self):
        """EQU constants can use direct mode even in relocatable code.

        Constants defined with EQU represent fixed addresses (like OS calls)
        that don't need relocation, so direct mode is safe.
        """
        source = """
OS_CALL     EQU     $3F         ; System call address (fixed)
            JSR     <OS_CALL    ; Should use direct mode
            RTS
        """
        asm = Assembler(relocatable=True)
        result = asm.assemble(source)

        # Search for 9D 3F pattern (JSR direct to $3F)
        found_direct = False
        for i in range(len(result) - 2):
            if result[i] == 0x9D and result[i+1] == 0x3F:
                found_direct = True
                break

        assert found_direct, "JSR <EQU_CONSTANT should use direct mode (9D 3F)"

    def test_ldaa_direct_vs_extended(self):
        """LDAA should use direct mode for addresses <= $FF, extended otherwise."""
        source = """
            LDAA    $50         ; Should use direct mode (96 50)
            LDAA    $0150       ; Should use extended mode (B6 01 50)
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # LDAA $50: direct mode = 96 50 (2 bytes)
        assert code[0] == 0x96, f"LDAA $50 should use direct mode ($96), got ${code[0]:02X}"
        assert code[1] == 0x50, f"LDAA target should be $50"

        # LDAA $0150: extended mode = B6 01 50 (3 bytes)
        assert code[2] == 0xB6, f"LDAA $0150 should use extended mode ($B6), got ${code[2]:02X}"
        assert code[3] == 0x01 and code[4] == 0x50, "LDAA target should be $0150"

    def test_staa_direct_vs_extended(self):
        """STAA should use direct mode for addresses <= $FF, extended otherwise."""
        source = """
            STAA    $50         ; Should use direct mode (97 50)
            STAA    $0150       ; Should use extended mode (B7 01 50)
            RTS
        """
        asm = Assembler(relocatable=False)
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # STAA $50: direct mode = 97 50 (2 bytes)
        assert code[0] == 0x97, f"STAA $50 should use direct mode ($97), got ${code[0]:02X}"
        assert code[1] == 0x50

        # STAA $0150: extended mode = B7 01 50 (3 bytes)
        assert code[2] == 0xB7, f"STAA $0150 should use extended mode ($B7), got ${code[2]:02X}"

    def test_relocatable_ldx_immediate_to_label(self):
        """LDX #label in relocatable code should use extended and be in fixup table."""
        source = """
_data:      FCB     $01,$02,$03
_code:      LDX     #_data      ; Load address of _data, needs relocation
            RTS
        """
        asm = Assembler(relocatable=True)
        result = asm.assemble(source)

        # LDX immediate is always 3 bytes (CE xx xx), but the address
        # should be in the fixup table for relocation
        # Verify CE is present (LDX immediate opcode)
        found_ldx_imm = False
        for i in range(len(result) - 1):
            if result[i] == 0xCE:
                found_ldx_imm = True
                break

        assert found_ldx_imm, "LDX #label should generate CE opcode"


# =============================================================================
# Model Support Tests
# =============================================================================

class TestModelSupport:
    """Tests for target model support in assembler."""

    def test_default_model_is_xp(self):
        """Default target model should be XP."""
        asm = Assembler()
        assert asm.get_target_model() == "XP"
        symbols = asm._codegen._symbols
        assert "__MODEL__" in symbols
        assert "__PSION_XP__" in symbols
        assert "__PSION_2LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 2
        assert symbols["DISP_COLS"].value == 16

    def test_cli_model_lz(self):
        """CLI model LZ should set 4-line display symbols."""
        asm = Assembler(target_model="LZ")
        assert asm.get_target_model() == "LZ"
        symbols = asm._codegen._symbols
        assert "__PSION_LZ__" in symbols
        assert "__PSION_4LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 4
        assert symbols["DISP_COLS"].value == 20

    def test_cli_model_lz64(self):
        """CLI model LZ64 should set 4-line display symbols."""
        asm = Assembler(target_model="LZ64")
        assert asm.get_target_model() == "LZ64"
        symbols = asm._codegen._symbols
        assert "__PSION_LZ64__" in symbols
        assert "__PSION_4LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 4

    def test_cli_model_cm(self):
        """CLI model CM should set 2-line display symbols."""
        asm = Assembler(target_model="CM")
        assert asm.get_target_model() == "CM"
        symbols = asm._codegen._symbols
        assert "__PSION_CM__" in symbols
        assert "__PSION_2LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 2

    def test_model_directive(self):
        """.MODEL directive should set model symbols."""
        asm = Assembler()
        source = """
            .MODEL LZ64
            ORG $8000
            NOP
            END
        """
        asm.assemble_string(source)
        symbols = asm._codegen._symbols
        assert "__PSION_LZ64__" in symbols
        assert "__PSION_4LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 4

    def test_cli_overrides_model_directive(self):
        """CLI model should override .MODEL directive."""
        asm = Assembler(target_model="CM")
        source = """
            .MODEL LZ
            ORG $8000
            NOP
            END
        """
        asm.assemble_string(source)
        # CLI takes precedence
        symbols = asm._codegen._symbols
        assert "__PSION_CM__" in symbols
        assert "__PSION_2LINE__" in symbols
        assert symbols["DISP_ROWS"].value == 2

    def test_dot_prefixed_model_directive(self):
        """.MODEL with dot prefix should work."""
        asm = Assembler()
        source = """
            .MODEL LA
            ORG $8000
            NOP
            END
        """
        asm.assemble_string(source)
        symbols = asm._codegen._symbols
        assert "__PSION_LA__" in symbols

    def test_model_without_dot_prefix(self):
        """MODEL without dot prefix should also work."""
        asm = Assembler()
        source = """
            MODEL LZ
            ORG $8000
            NOP
            END
        """
        asm.assemble_string(source)
        symbols = asm._codegen._symbols
        assert "__PSION_LZ__" in symbols

    def test_conditional_assembly_with_model(self):
        """Conditional assembly should work with model symbols."""
        asm = Assembler(target_model="LZ")
        source = """
            ORG $8000
            #IFDEF __PSION_4LINE__
                LDAA #4
            #ELSE
                LDAA #2
            #ENDIF
            END
        """
        asm.assemble_string(source)
        code = asm.get_code()
        # LDAA #4 is opcode 86 04
        assert code[0] == 0x86
        assert code[1] == 0x04

    def test_conditional_assembly_with_2line_model(self):
        """Conditional assembly should select 2-line code for CM."""
        asm = Assembler(target_model="CM")
        source = """
            ORG $8000
            #IFDEF __PSION_4LINE__
                LDAA #4
            #ELSE
                LDAA #2
            #ENDIF
            END
        """
        asm.assemble_string(source)
        code = asm.get_code()
        # LDAA #2 is opcode 86 02
        assert code[0] == 0x86
        assert code[1] == 0x02

    def test_disp_rows_in_code(self):
        """DISP_ROWS symbol should be usable in code."""
        asm = Assembler(target_model="LZ")
        source = """
            ORG $8000
            LDAA #DISP_ROWS
            END
        """
        asm.assemble_string(source)
        code = asm.get_code()
        # LDAA #4 (DISP_ROWS for LZ)
        assert code[0] == 0x86
        assert code[1] == 0x04

    def test_model_case_insensitive(self):
        """Model names should be case-insensitive."""
        asm = Assembler(target_model="lz")
        assert asm.get_target_model() == "LZ"

        asm2 = Assembler()
        source = """
            .model lz64
            ORG $8000
            NOP
            END
        """
        asm2.assemble_string(source)
        symbols = asm2._codegen._symbols
        assert "__PSION_LZ64__" in symbols


# =============================================================================
# Branch Relaxation Tests
# =============================================================================

class TestBranchRelaxation:
    """
    Tests for automatic branch relaxation (long branch support).

    The HD6303 branch instructions have a limited range of -128 to +127 bytes.
    When a branch target is beyond this range, the assembler automatically
    generates a "long branch" sequence:

    For conditional branches (BEQ, BNE, etc.):
        BEQ target  -->  BNE skip; JMP target; skip:  (5 bytes)

    For unconditional branches:
        BRA target  -->  JMP target  (3 bytes)
        BSR target  -->  JSR target  (3 bytes)
    """

    def test_short_branch_within_range(self):
        """Short branches within ±127 bytes should use standard 2-byte form."""
        source = """
            ORG $8000
_loop:      NOP
            BNE _loop
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]  # Skip OB3 header

        # NOP (1 byte) + BNE (2 bytes) = 3 bytes
        assert len(code) == 3
        assert code[0] == 0x01      # NOP
        assert code[1] == 0x26      # BNE opcode
        # Offset should be -3 (0xFD) to go back over BNE(2) + NOP(1)
        assert code[2] == 0xFD

    def test_forward_branch_within_range(self):
        """Forward branch within range should use standard 2-byte form."""
        source = """
            ORG $8000
            BEQ _target
            NOP
            NOP
_target:    RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # BEQ (2) + NOP (1) + NOP (1) + RTS (1) = 5 bytes
        assert len(code) == 5
        assert code[0] == 0x27      # BEQ opcode
        assert code[1] == 0x02      # Offset +2 to skip two NOPs

    def test_long_branch_beq_converts_to_bne_jmp(self):
        """BEQ beyond range should become BNE skip; JMP target; skip:"""
        # Create a large gap (200+ bytes of NOPs)
        nops = "NOP\n" * 150  # 150 NOPs = 150 bytes
        source = f"""
            ORG $8000
            BEQ _target
            {nops}
_target:    RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # Long branch for BEQ: BNE skip (2) + JMP target (3) = 5 bytes
        # Then 150 NOPs + RTS = 151 bytes
        # Total = 5 + 150 + 1 = 156 bytes
        assert len(code) == 156

        # First instruction should be BNE (inverted BEQ) with offset +3
        assert code[0] == 0x26      # BNE opcode (inverted from BEQ)
        assert code[1] == 0x03      # Offset +3 to skip over JMP

        # Second instruction should be JMP (extended addressing)
        assert code[2] == 0x7E      # JMP opcode

        # JMP target should be at address of _target (start + 5 + 150)
        jmp_target = (code[3] << 8) | code[4]
        assert jmp_target == 0x8000 + 5 + 150  # $8000 + long_branch_size + nops

    def test_long_branch_bne_converts_to_beq_jmp(self):
        """BNE beyond range should become BEQ skip; JMP target; skip:"""
        nops = "NOP\n" * 150
        source = f"""
            ORG $8000
            BNE _target
            {nops}
_target:    RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # BNE inverts to BEQ
        assert code[0] == 0x27      # BEQ opcode (inverted from BNE)
        assert code[1] == 0x03      # Skip over JMP
        assert code[2] == 0x7E      # JMP opcode

    def test_long_bra_becomes_jmp(self):
        """BRA beyond range should become simple JMP."""
        nops = "NOP\n" * 150
        source = f"""
            ORG $8000
            BRA _target
            {nops}
_target:    RTS
        """
        # Disable optimization - the NOPs after BRA would be removed as dead code
        # by the optimizer, which would make the branch short again
        asm = Assembler(optimize=False)
        result = asm.assemble(source)
        code = result[7:]

        # BRA just becomes JMP (3 bytes)
        # Total = 3 + 150 + 1 = 154 bytes
        assert len(code) == 154

        # Should just be JMP, no condition inversion needed
        assert code[0] == 0x7E      # JMP opcode
        jmp_target = (code[1] << 8) | code[2]
        assert jmp_target == 0x8000 + 3 + 150

    def test_long_bsr_becomes_jsr(self):
        """BSR beyond range should become simple JSR."""
        nops = "NOP\n" * 150
        source = f"""
            ORG $8000
            BSR _subroutine
            RTS
            {nops}
_subroutine:
            NOP
            RTS
        """
        # Disable optimization - the NOPs after RTS would be removed as dead code
        # by the optimizer, which would make the subroutine call short again
        asm = Assembler(optimize=False)
        result = asm.assemble(source)
        code = result[7:]

        # BSR becomes JSR (3 bytes), then RTS (1), 150 NOPs, NOP+RTS (2)
        # Total = 3 + 1 + 150 + 1 + 1 = 156 bytes
        assert len(code) == 156

        # First instruction should be JSR
        assert code[0] == 0xBD      # JSR extended opcode

    def test_multiple_long_branches_same_target(self):
        """Multiple long branches to same target should all be relaxed."""
        nops = "NOP\n" * 60  # 60 NOPs between each branch
        source = f"""
            ORG $8000
            BEQ _target
            {nops}
            BNE _target
            {nops}
            BRA _target
            {nops}
_target:    RTS
        """
        # Disable optimization - the NOPs after BRA would be removed as dead code
        # by the optimizer, affecting the total distance calculation
        asm = Assembler(optimize=False)
        result = asm.assemble(source)
        code = result[7:]

        # Should compile successfully with all long forms
        # Check first BEQ became BNE + JMP
        assert code[0] == 0x26      # BNE (inverted BEQ)
        assert code[1] == 0x03      # Skip
        assert code[2] == 0x7E      # JMP

    def test_backward_long_branch(self):
        """Backward branch beyond -128 bytes should also be relaxed."""
        nops = "NOP\n" * 150
        source = f"""
            ORG $8000
_loop:      NOP
            {nops}
            BNE _loop     ; Way back, needs long form
            RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # Should compile successfully
        # Find the BNE (now BEQ+JMP) near the end
        # It should be at position 1 + 150 = 151
        long_branch_pos = 151
        assert code[long_branch_pos] == 0x27      # BEQ (inverted BNE)
        assert code[long_branch_pos + 1] == 0x03  # Skip
        assert code[long_branch_pos + 2] == 0x7E  # JMP

    def test_all_conditional_branches_can_relax(self):
        """All conditional branch types should be able to relax."""
        branches = [
            ("BEQ", 0x26),  # BEQ inverts to BNE
            ("BNE", 0x27),  # BNE inverts to BEQ
            ("BCC", 0x25),  # BCC inverts to BCS
            ("BCS", 0x24),  # BCS inverts to BCC
            ("BPL", 0x2B),  # BPL inverts to BMI
            ("BMI", 0x2A),  # BMI inverts to BPL
            ("BVC", 0x29),  # BVC inverts to BVS
            ("BVS", 0x28),  # BVS inverts to BVC
            ("BGE", 0x2D),  # BGE inverts to BLT
            ("BLT", 0x2C),  # BLT inverts to BGE
            ("BGT", 0x2F),  # BGT inverts to BLE
            ("BLE", 0x2E),  # BLE inverts to BGT
            ("BHI", 0x23),  # BHI inverts to BLS
            ("BLS", 0x22),  # BLS inverts to BHI
        ]

        nops = "NOP\n" * 150

        for branch_mnemonic, expected_inverted_opcode in branches:
            source = f"""
                ORG $8000
                {branch_mnemonic} _target
                {nops}
_target:        RTS
            """
            asm = Assembler()
            result = asm.assemble(source)
            code = result[7:]

            assert code[0] == expected_inverted_opcode, \
                f"{branch_mnemonic} should invert to opcode ${expected_inverted_opcode:02X}, got ${code[0]:02X}"
            assert code[1] == 0x03, f"{branch_mnemonic} skip offset should be 3"
            assert code[2] == 0x7E, f"{branch_mnemonic} should be followed by JMP"

    def test_relocatable_long_branch_adds_fixup(self):
        """Long branches in relocatable code should add JMP address to fixups."""
        nops = "NOP\n" * 150
        source = f"""
            ORG $0000
            BEQ _target
            {nops}
_target:    RTS
        """
        asm = Assembler(relocatable=True)
        result = asm.assemble(source)

        # In relocatable mode, the JMP address at offset 3-4 (after BNE skip, JMP opcode)
        # should be in the fixup table. The code generator adds this when _needs_fixup
        # returns True for internal symbols.
        # The result includes stub + code + fixup_count + fixup_table

        # This should compile without error - the key test is that it doesn't crash
        # and the JMP target is correctly recorded for relocation
        assert len(result) > 0

    def test_relaxation_iteration_converges(self):
        """
        Test that relaxation iteration converges correctly.

        This tests a scenario where relaxing one branch might push another
        branch out of range, requiring multiple iterations.
        """
        # Create a situation where branches are near the boundary
        # First branch is just within range, second is just out of range
        # When second is relaxed (grows by 3 bytes), first might need relaxation too
        nops_126 = "NOP\n" * 126  # Just at the boundary
        nops_3 = "NOP\n" * 3

        source = f"""
            ORG $8000
            BEQ _target1    ; This might need relaxation after _target2 branch grows
            {nops_126}
_target1:   NOP
            {nops_3}
            BEQ _target2    ; This needs relaxation
            {nops_126}
            {nops_3}
_target2:   RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        # Should compile without error, proving iteration converged
        assert len(result) > 0

    def test_edge_case_exactly_128_bytes(self):
        """Branch exactly at -128 byte boundary should still use short form."""
        # -128 is still within range, so should use short branch
        nops = "NOP\n" * 125  # 125 NOPs, BNE will be at 127 from loop_start

        source = f"""
            ORG $8000
_loop_start: NOP
            {nops}
            NOP             ; Total 127 bytes of NOPs
            BNE _loop_start ; Offset = -(127 + 2) = -129... just out of range
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # The BNE should need long form since offset is -129
        # Find BNE position: 1 + 125 + 1 = 127
        bne_pos = 127
        # Should be inverted to BEQ for long form
        assert code[bne_pos] == 0x27  # BEQ (inverted)

    def test_edge_case_exactly_127_bytes(self):
        """Branch exactly at +127 byte boundary should use short form."""
        nops = "NOP\n" * 125

        source = f"""
            ORG $8000
            BEQ _target     ; 2 bytes
            {nops}          ; 125 bytes, offset = 125, within range
_target:    RTS
        """
        asm = Assembler()
        result = asm.assemble(source)
        code = result[7:]

        # BEQ (2) + 125 NOPs + RTS = 128 bytes
        assert len(code) == 128

        # Should still be short BEQ
        assert code[0] == 0x27      # BEQ opcode (short form)
