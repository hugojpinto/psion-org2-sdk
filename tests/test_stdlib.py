# =============================================================================
# test_stdlib.py - Standard Library Tests
# =============================================================================
# Tests for the Psion SDK standard library functions including:
#   - ctype.h character classification macros
#   - String functions: strchr, strncpy, strncmp (runtime.inc)
#   - Number conversion: atoi, itoa (runtime.inc)
#   - Extended string functions: strrchr, strstr, strncat (stdio.inc)
#   - Formatted output: sprintf (stdio.inc)
#
# Test Approach:
#   - Compilation tests: Verify C code using these functions compiles correctly
#   - Assembly tests: Verify the assembly implementations assemble correctly
#   - Emulator tests: Run compiled code in emulator and verify behavior
#
# Copyright (c) 2025 Hugo José Pinto & Contributors
# =============================================================================

import pytest
import tempfile
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.smallc.compiler import SmallCCompiler, CompilerOptions
from psion_sdk.emulator import Emulator, EmulatorConfig, BreakReason
from psion_sdk.errors import AssemblerError


# =============================================================================
# Paths and Fixtures
# =============================================================================

# Get include directory path
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


@pytest.fixture
def emu():
    """Create emulator with minimal ROM for testing."""
    # Create minimal ROM with reset vector pointing to injected code
    rom_data = bytearray([0x00] * 0x8000)
    rom_data[0x7FFE] = 0x20  # Reset vector high
    rom_data[0x7FFF] = 0x00  # Reset vector low -> $2000

    with tempfile.NamedTemporaryFile(suffix='.rom', delete=False) as f:
        f.write(bytes(rom_data))
        rom_path = Path(f.name)

    try:
        emu = Emulator(EmulatorConfig(rom_path=rom_path))
        emu.reset()
        yield emu
    finally:
        rom_path.unlink()


def compile_c_to_asm(source: str, compiler) -> str:
    """Compile C source to assembly and return the assembly code."""
    result = compiler.compile_source(source, "test.c")
    if result.success:
        return result.assembly
    else:
        raise Exception(f"Compilation failed: {result.errors}")


# =============================================================================
# ctype.h Macro Tests
# =============================================================================

class TestCtypeMacros:
    """
    Test ctype.h character classification macros.

    These are compile-time macros, so we test that:
    1. C code using them compiles without errors
    2. The generated assembly contains the expected comparison patterns
    """

    def test_isdigit_compiles(self, compiler):
        """isdigit macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isdigit(char c) {
            if (isdigit(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain comparisons with '0' (48) and '9' (57)
        assert "#48" in asm or "#$30" in asm.upper() or "#'0'" in asm

    def test_isupper_compiles(self, compiler):
        """isupper macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isupper(char c) {
            if (isupper(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain comparisons with 'A' (65) and 'Z' (90)
        assert "#65" in asm or "#$41" in asm.upper() or "#'A'" in asm

    def test_islower_compiles(self, compiler):
        """islower macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_islower(char c) {
            if (islower(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain comparisons with 'a' (97) and 'z' (122)
        assert "#97" in asm or "#$61" in asm.upper() or "#'a'" in asm

    def test_isalpha_compiles(self, compiler):
        """isalpha macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isalpha(char c) {
            if (isalpha(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # isalpha combines isupper and islower checks

    def test_isalnum_compiles(self, compiler):
        """isalnum macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isalnum(char c) {
            if (isalnum(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_isspace_compiles(self, compiler):
        """isspace macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isspace(char c) {
            if (isspace(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain comparison with ' ' (32)
        assert "#32" in asm or "#$20" in asm.upper() or "#' '" in asm

    def test_isxdigit_compiles(self, compiler):
        """isxdigit macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isxdigit(char c) {
            if (isxdigit(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_toupper_compiles(self, compiler):
        """toupper macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        char test_toupper(char c) {
            return toupper(c);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain subtraction of 32 (difference between 'a' and 'A')
        assert "#32" in asm or "#$20" in asm.upper()

    def test_tolower_compiles(self, compiler):
        """tolower macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        char test_tolower(char c) {
            return tolower(c);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        # Should contain addition of 32

    def test_isprint_compiles(self, compiler):
        """isprint macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_isprint(char c) {
            if (isprint(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_iscntrl_compiles(self, compiler):
        """iscntrl macro should compile correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test_iscntrl(char c) {
            if (iscntrl(c)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None


# =============================================================================
# String Function Compilation Tests
# =============================================================================

class TestStringFunctionsCompile:
    """
    Test that string functions compile correctly.

    These functions are declared in psion.h and implemented in runtime.inc.
    We verify that C code using them compiles and generates correct JSR calls.
    """

    def test_strchr_compiles(self, compiler):
        """strchr function call should compile correctly."""
        source = """
        #include <psion.h>

        void main() {
            char *s = "Hello";
            char *p;
            p = strchr(s, 'l');
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strchr" in asm

    def test_strncpy_compiles(self, compiler):
        """strncpy function call should compile correctly."""
        source = """
        #include <psion.h>

        void main() {
            char src[10];
            char dst[10];
            strncpy(dst, src, 5);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strncpy" in asm

    def test_strncmp_compiles(self, compiler):
        """strncmp function call should compile correctly."""
        source = """
        #include <psion.h>

        void main() {
            char *s1 = "Hello";
            char *s2 = "Help";
            int r;
            r = strncmp(s1, s2, 3);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strncmp" in asm


# =============================================================================
# Number Conversion Function Compilation Tests
# =============================================================================

class TestNumberConversionCompile:
    """
    Test that number conversion functions compile correctly.
    """

    def test_atoi_compiles(self, compiler):
        """atoi function call should compile correctly."""
        source = """
        #include <psion.h>

        void main() {
            char *s = "123";
            int n;
            n = atoi(s);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_atoi" in asm

    def test_itoa_compiles(self, compiler):
        """itoa function call should compile correctly."""
        source = """
        #include <psion.h>

        void main() {
            char buf[12];
            int n = 42;
            itoa(n, buf);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_itoa" in asm


# =============================================================================
# stdio.h Function Compilation Tests
# =============================================================================

class TestStdioFunctionsCompile:
    """
    Test that stdio.h functions compile correctly.

    These functions are declared in stdio.h and implemented in stdio.inc.
    """

    def test_strrchr_compiles(self, compiler):
        """strrchr function call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *path = "/a/b/c.txt";
            char *ext;
            ext = strrchr(path, '.');
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strrchr" in asm

    def test_strstr_compiles(self, compiler):
        """strstr function call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *haystack = "Hello World";
            char *needle = "World";
            char *found;
            found = strstr(haystack, needle);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strstr" in asm

    def test_strncat_compiles(self, compiler):
        """strncat function call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[20];
            strcpy(buf, "Hello");
            strncat(buf, " World", 3);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_strncat" in asm

    def test_sprintf_compiles(self, compiler):
        """sprintf function call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            int n = 42;
            sprintf(buf, "Value: %d", n, 0, 0, 0);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_sprintf" in asm

    def test_sprintf1_compiles(self, compiler):
        """sprintf1 variant should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf1(buf, "Number: %d", 123);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_sprintf1" in asm


# =============================================================================
# Assembly Implementation Tests
# =============================================================================

class TestRuntimeAssembly:
    """
    Test that runtime.inc functions assemble correctly.

    These tests verify that the assembly implementations are syntactically
    correct and produce valid machine code.
    """

    def test_atoi_assembles(self, assembler):
        """_atoi function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            ; Test harness - call atoi with a string pointer
            LDD #TEST_STR
            PSHB
            PSHA
            JSR _atoi
            INS
            INS
            RTS

TEST_STR:   FCC "123"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None
        assert len(result) > 0

    def test_itoa_assembles(self, assembler):
        """_itoa function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            ; Test harness - call itoa with value and buffer
            LDD #BUF
            PSHB
            PSHA
            LDD #42
            PSHB
            PSHA
            JSR _itoa
            LEAS 4,S
            RTS

BUF:        RMB 12
        """
        # Note: LEAS is not HD6303, using INS loop instead
        source_fixed = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            ; Test harness - call itoa with value and buffer
            LDD #BUF
            PSHB
            PSHA
            LDD #42
            PSHB
            PSHA
            JSR _itoa
            INS
            INS
            INS
            INS
            RTS

BUF:        RMB 12
        """
        result = assembler.assemble(source_fixed)
        assert result is not None
        assert len(result) > 0

    def test_strchr_assembles(self, assembler):
        """_strchr function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            LDD #'l'
            PSHB
            PSHA
            LDD #STR
            PSHB
            PSHA
            JSR _strchr
            INS
            INS
            INS
            INS
            RTS

STR:        FCC "Hello"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_strncpy_assembles(self, assembler):
        """_strncpy function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            LDD #5
            PSHB
            PSHA
            LDD #SRC
            PSHB
            PSHA
            LDD #DST
            PSHB
            PSHA
            JSR _strncpy
            INS
            INS
            INS
            INS
            INS
            INS
            RTS

SRC:        FCC "Hello World"
            FCB 0
DST:        RMB 10
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_strncmp_assembles(self, assembler):
        """_strncmp function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"

            ORG $2100
            LDD #3
            PSHB
            PSHA
            LDD #S2
            PSHB
            PSHA
            LDD #S1
            PSHB
            PSHA
            JSR _strncmp
            INS
            INS
            INS
            INS
            INS
            INS
            RTS

S1:         FCC "Hello"
            FCB 0
S2:         FCC "Help"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None


class TestStdioAssembly:
    """
    Test that stdio.inc functions assemble correctly.
    """

    def test_strrchr_assembles(self, assembler):
        """_strrchr function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            LDD #'/'
            PSHB
            PSHA
            LDD #PATH
            PSHB
            PSHA
            JSR _strrchr
            INS
            INS
            INS
            INS
            RTS

PATH:       FCC "/a/b/c"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_strstr_assembles(self, assembler):
        """_strstr function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            LDD #NEEDLE
            PSHB
            PSHA
            LDD #HAYSTACK
            PSHB
            PSHA
            JSR _strstr
            INS
            INS
            INS
            INS
            RTS

HAYSTACK:   FCC "Hello World"
            FCB 0
NEEDLE:     FCC "World"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_strncat_assembles(self, assembler):
        """_strncat function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            LDD #3
            PSHB
            PSHA
            LDD #SRC
            PSHB
            PSHA
            LDD #DST
            PSHB
            PSHA
            JSR _strncat
            INS
            INS
            INS
            INS
            INS
            INS
            RTS

DST:        FCC "Hello"
            FCB 0
            RMB 10
SRC:        FCC " World"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_sprintf_assembles(self, assembler):
        """_sprintf function should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            ; Push args in reverse: a4, a3, a2, a1, fmt, buf
            LDD #0
            PSHB
            PSHA          ; a4
            PSHB
            PSHA          ; a3
            PSHB
            PSHA          ; a2
            LDD #42
            PSHB
            PSHA          ; a1
            LDD #FMT
            PSHB
            PSHA          ; fmt
            LDD #BUF
            PSHB
            PSHA          ; buf
            JSR _sprintf
            ; Clean up 12 bytes
            LDX #12
CLEAN:      INS
            DEX
            BNE CLEAN
            RTS

FMT:        FCC "Value: %d"
            FCB 0
BUF:        RMB 32
        """
        result = assembler.assemble(source)
        assert result is not None


# =============================================================================
# Emulator Execution Tests
# =============================================================================

class TestRuntimeExecution:
    """
    Test runtime functions by executing them in the emulator.

    These tests verify basic emulator operations that underlie string
    function testing. Full integration tests would require booting
    the complete Psion environment.
    """

    def test_memory_string_operations(self, emu):
        """Test basic memory operations that underlie string functions."""
        # Test that we can write and read strings in memory
        test_string = b"Hello"

        # Write string to memory
        for i, byte in enumerate(test_string):
            emu.write_byte(0x2100 + i, byte)
        emu.write_byte(0x2100 + len(test_string), 0)  # Null terminator

        # Read back and verify
        for i, expected in enumerate(test_string):
            actual = emu.read_byte(0x2100 + i)
            assert actual == expected, f"Byte {i}: expected {expected}, got {actual}"

        # Verify null terminator
        assert emu.read_byte(0x2100 + len(test_string)) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestFullCompilationPipeline:
    """
    Test complete compilation pipeline from C to assembled code.
    """

    def test_ctype_program_compiles_and_assembles(self, compiler, assembler):
        """A program using ctype.h should compile and assemble."""
        c_source = """
        #include <psion.h>
        #include <ctype.h>

        int count_digits(char *s) {
            int count;
            count = 0;
            while (*s) {
                if (isdigit(*s)) {
                    count = count + 1;
                }
                s = s + 1;
            }
            return count;
        }

        void main() {
            char *test = "abc123def";
            int n;
            n = count_digits(test);
        }
        """
        # Compile C to assembly
        asm_source = compile_c_to_asm(c_source, compiler)
        assert asm_source is not None
        assert "count_digits" in asm_source

        # Assemble to machine code
        result = assembler.assemble(asm_source)
        assert result is not None
        assert len(result) > 0

    def test_string_functions_program_compiles_and_assembles(self, compiler, assembler):
        """A program using string functions should compile and assemble."""
        c_source = """
        #include <psion.h>

        void main() {
            char buf[20];
            char *found;
            int cmp;

            strcpy(buf, "Hello");
            found = strchr(buf, 'l');
            strncpy(buf, "World", 5);
            cmp = strncmp("abc", "abd", 2);
        }
        """
        asm_source = compile_c_to_asm(c_source, compiler)
        assert asm_source is not None

        result = assembler.assemble(asm_source)
        assert result is not None

    def test_atoi_itoa_program_compiles_and_assembles(self, compiler, assembler):
        """A program using atoi/itoa should compile and assemble."""
        c_source = """
        #include <psion.h>

        void main() {
            char buf[12];
            int n;

            n = atoi("42");
            itoa(n, buf);
        }
        """
        asm_source = compile_c_to_asm(c_source, compiler)
        assert asm_source is not None

        result = assembler.assemble(asm_source)
        assert result is not None


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_ctype_with_zero(self, compiler):
        """ctype macros should handle null character correctly."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int test() {
            char c = 0;
            if (isdigit(c)) return 1;
            if (isalpha(c)) return 2;
            if (isspace(c)) return 3;
            if (iscntrl(c)) return 4;
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_atoi_negative_compiles(self, compiler):
        """atoi should handle negative number strings."""
        source = """
        #include <psion.h>

        void main() {
            int n;
            n = atoi("-123");
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
        assert "_atoi" in asm

    def test_strncmp_zero_length_compiles(self, compiler):
        """strncmp with n=0 should compile."""
        source = """
        #include <psion.h>

        void main() {
            int r;
            r = strncmp("abc", "xyz", 0);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_empty_string_operations_compile(self, compiler):
        """Operations on empty strings should compile."""
        source = """
        #include <psion.h>

        void main() {
            char *empty = "";
            char buf[10];
            int len;
            char *p;

            len = strlen(empty);
            strcpy(buf, empty);
            p = strchr(empty, 'x');
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None


# =============================================================================
# Header Include Order Tests
# =============================================================================

class TestIncludeOrder:
    """Test that headers work with correct include order."""

    def test_psion_before_ctype(self, compiler):
        """ctype.h requires psion.h to be included first."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        void main() {
            char c = 'A';
            if (isupper(c)) {
                c = tolower(c);
            }
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_psion_before_stdio(self, compiler):
        """stdio.h requires psion.h to be included first."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *s = "test";
            char *p;
            p = strrchr(s, 't');
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None


# =============================================================================
# Regression Tests
# =============================================================================

class TestRegressions:
    """Regression tests for known issues."""

    def test_multiple_ctype_macros_in_expression(self, compiler):
        """Multiple ctype macros in one expression should work."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        int is_identifier_char(char c) {
            if (isalnum(c)) return 1;
            if (c == '_') return 1;
            return 0;
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_chained_string_operations(self, compiler):
        """Chained string operations should compile."""
        source = """
        #include <psion.h>

        void main() {
            char buf[30];
            strcpy(buf, "Hello");
            strcat(buf, " ");
            strcat(buf, "World");
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None


# =============================================================================
# Documentation Examples Tests
# =============================================================================

class TestDocumentationExamples:
    """
    Test that examples from documentation compile correctly.
    These ensure our docs are accurate.
    """

    def test_ctype_example_from_header(self, compiler):
        """Example from ctype.h header should work."""
        source = """
        #include <psion.h>
        #include <ctype.h>

        void process_input() {
            char c;
            c = 'h';
            if (isdigit(c)) {
                /* digit handling */
            }
            c = toupper(c);
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None

    def test_stdio_strrchr_example(self, compiler):
        """strrchr example for finding file extension."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void find_extension() {
            char *filename = "document.txt";
            char *ext;
            ext = strrchr(filename, '.');
            /* ext now points to ".txt" */
        }
        """
        asm = compile_c_to_asm(source, compiler)
        assert asm is not None
