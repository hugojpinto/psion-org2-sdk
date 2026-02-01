# =============================================================================
# test_asm_inline.py - Inline Assembly (asm()) Tests
# =============================================================================
# Tests for the asm() inline assembly statement that allows embedding raw
# HD6303 assembly code directly in C source files.
#
# Features tested:
#   - Basic asm() statement parsing and code generation
#   - Variable substitution with %varname syntax
#   - Local variable references (stack-relative addressing)
#   - Global variable references (symbol references)
#   - Multiple asm() statements
#   - Integration with C code
#
# Copyright (c) 2025 Hugo José Pinto & Contributors
# =============================================================================

import pytest
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.smallc.compiler import SmallCCompiler, CompilerOptions


# =============================================================================
# Paths and Fixtures
# =============================================================================

INCLUDE_DIR = Path(__file__).parent.parent / "include"


@pytest.fixture
def compiler():
    """Create a Small-C compiler with include paths configured."""
    options = CompilerOptions(
        include_paths=[str(INCLUDE_DIR)],
        target_model="XP",
    )
    return SmallCCompiler(options)


@pytest.fixture
def assembler():
    """Create an assembler with include paths configured."""
    return Assembler(include_paths=[str(INCLUDE_DIR)])


def compile_c(source: str, compiler) -> str:
    """Compile C source to assembly, raising on failure."""
    result = compiler.compile_source(source, "test.c")
    if result.success:
        return result.assembly
    raise Exception(f"Compilation failed: {result.errors}")


# =============================================================================
# Basic asm() Statement Tests
# =============================================================================

class TestAsmBasic:
    """Basic asm() statement parsing and code generation."""

    def test_asm_simple_instruction(self, compiler):
        """Simple asm() with one instruction should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        NOP");
        }
        """
        asm = compile_c(source, compiler)
        assert "NOP" in asm

    def test_asm_multiple_statements(self, compiler):
        """Multiple asm() statements should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        NOP");
            asm("        NOP");
            asm("        NOP");
        }
        """
        asm = compile_c(source, compiler)
        # Count NOP occurrences (should be at least 3 from our code)
        assert asm.count("NOP") >= 3

    def test_asm_with_immediate(self, compiler):
        """asm() with immediate operand should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        LDAA    #$42");
        }
        """
        asm = compile_c(source, compiler)
        assert "LDAA" in asm
        assert "#$42" in asm

    def test_asm_with_address(self, compiler):
        """asm() with address operand should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        LDX     #$1234");
            asm("        LDAA    0,X");
        }
        """
        asm = compile_c(source, compiler)
        assert "LDX" in asm
        assert "#$1234" in asm

    def test_asm_swi_instruction(self, compiler):
        """asm() with SWI and FCB should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        SWI");
            asm("        FCB     $01");
        }
        """
        asm = compile_c(source, compiler)
        assert "SWI" in asm
        assert "FCB" in asm


# =============================================================================
# Variable Substitution Tests
# =============================================================================

class TestAsmVariableSubstitution:
    """Tests for %varname variable substitution in asm()."""

    def test_asm_local_variable_substitution(self, compiler):
        """Local variable %name should be replaced with stack offset."""
        source = """
        #include <psion.h>

        void main() {
            int result;
            asm("        STD     %result");
        }
        """
        asm = compile_c(source, compiler)
        # %result should be replaced with something like "2,X"
        assert "STD" in asm
        # Should NOT contain literal %result
        assert "%result" not in asm
        # Should contain stack-relative addressing
        assert ",X" in asm

    def test_asm_global_variable_substitution(self, compiler):
        """Global variable %name should be replaced with symbol."""
        source = """
        #include <psion.h>

        int global_var;

        void main() {
            asm("        LDD     %global_var");
        }
        """
        asm = compile_c(source, compiler)
        # %global_var should be replaced with _global_var
        assert "LDD" in asm
        assert "_global_var" in asm
        assert "%global_var" not in asm

    def test_asm_multiple_variable_refs(self, compiler):
        """Multiple variable references in same asm() should work."""
        source = """
        #include <psion.h>

        int g1;
        int g2;

        void main() {
            int local;
            asm("        LDD     %g1");
            asm("        ADDD    %g2");
            asm("        STD     %local");
        }
        """
        asm = compile_c(source, compiler)
        assert "_g1" in asm
        assert "_g2" in asm
        assert ",X" in asm  # local variable reference

    def test_asm_parameter_substitution(self, compiler):
        """Function parameter %name should work."""
        source = """
        #include <psion.h>

        void process(int value) {
            asm("        LDD     %value");
            asm("        LSLD");
        }
        """
        asm = compile_c(source, compiler)
        assert "LDD" in asm
        assert "%value" not in asm
        # Parameter should be at a stack offset
        assert ",X" in asm


# =============================================================================
# Integration Tests
# =============================================================================

class TestAsmIntegration:
    """Integration tests for asm() with C code and assembler."""

    def test_asm_with_c_code(self, compiler):
        """asm() mixed with C code should compile."""
        source = """
        #include <psion.h>

        void main() {
            int x;
            x = 10;
            asm("        LDAA    #$FF");
            x = x + 1;
            asm("        NOP");
            print_int(x);
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None
        assert "LDAA" in asm
        assert "NOP" in asm

    def test_asm_syscall_pattern(self, compiler, assembler):
        """Common SWI syscall pattern should compile and assemble."""
        source = """
        #include <psion.h>

        void main() {
            asm("        LDAA    #$41");
            asm("        SWI");
            asm("        FCB     $1B");
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None
        assert len(result) > 0

    def test_asm_full_pipeline(self, compiler, assembler):
        """Complete program with asm() should compile and assemble."""
        source = """
        #include <psion.h>

        int result;

        void main() {
            asm("        LDX     #$1234");
            asm("        STX     %result");
            print_int(result);
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None
        assert len(result) > 0

    def test_asm_register_manipulation(self, compiler, assembler):
        """Direct register manipulation should work."""
        source = """
        #include <psion.h>

        void main() {
            int val;
            val = 100;

            asm("        LDD     %val");
            asm("        ADDD    #50");
            asm("        STD     %val");

            print_int(val);
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None

    def test_asm_in_function(self, compiler, assembler):
        """asm() in non-main function should work."""
        source = """
        #include <psion.h>

        int double_it(int x) {
            asm("        LDD     %x");
            asm("        LSLD");
            asm("        STD     %x");
            return x;
        }

        void main() {
            int r;
            r = double_it(21);
            print_int(r);
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestAsmEdgeCases:
    """Edge cases and special scenarios for asm()."""

    def test_asm_empty_string(self, compiler):
        """asm() with empty string should compile (no-op)."""
        source = """
        #include <psion.h>

        void main() {
            asm("");
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_asm_whitespace_only(self, compiler):
        """asm() with whitespace only should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        ");
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_asm_comment_in_string(self, compiler):
        """asm() with assembly comment should compile."""
        source = """
        #include <psion.h>

        void main() {
            asm("        NOP     ; This is a comment");
        }
        """
        asm = compile_c(source, compiler)
        assert "NOP" in asm

    def test_asm_label_definition(self, compiler, assembler):
        """asm() with label should compile and assemble."""
        source = """
        #include <psion.h>

        void main() {
            asm("_myloop:");
            asm("        NOP");
            asm("        BRA     _myloop");
        }
        """
        # Note: This may cause infinite loop at runtime, but should compile
        asm = compile_c(source, compiler)
        assert "_myloop" in asm

    def test_asm_preserves_indentation(self, compiler):
        """asm() should preserve leading whitespace."""
        source = """
        #include <psion.h>

        void main() {
            asm("        NOP");
        }
        """
        asm = compile_c(source, compiler)
        # The assembly should have proper indentation
        lines = [l for l in asm.split('\n') if 'NOP' in l]
        assert len(lines) > 0
        # Check that NOP line has leading spaces
        assert lines[0].startswith(' ')

    def test_asm_unknown_variable(self, compiler, assembler):
        """Unknown variable reference should become symbol (assembler catches it)."""
        source = """
        #include <psion.h>

        void main() {
            asm("        LDD     %unknown_var");
        }
        """
        asm = compile_c(source, compiler)
        # Should compile (variable becomes _unknown_var symbol)
        assert "_unknown_var" in asm
        # Assembler may fail on undefined symbol, which is correct behavior


# =============================================================================
# Documentation Example Tests
# =============================================================================

class TestAsmDocExamples:
    """Test examples from documentation."""

    def test_doc_example_syscall(self, compiler, assembler):
        """Documentation syscall example should work."""
        source = """
        #include <psion.h>

        void main() {
            int result;

            asm("        LDX     #$1234");
            asm("        LDAB    #$83");
            asm("        SWI");
            asm("        FCB     $24");
            asm("        STD     %result");

            print_int(result);
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None

    def test_doc_example_direct_hardware(self, compiler, assembler):
        """Direct hardware access example should work."""
        source = """
        #include <psion.h>

        void main() {
            asm("        LDAA    #$FF");
            asm("        STAA    $20");
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        result = assembler.assemble(asm)
        assert result is not None
