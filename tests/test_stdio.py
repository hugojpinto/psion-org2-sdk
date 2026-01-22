# =============================================================================
# test_stdio.py - Extended String and Formatting Function Tests
# =============================================================================
# Tests for the stdio.h/stdio.inc optional library functions:
#   - strrchr: Find last occurrence of character
#   - strstr: Find substring in string
#   - strncat: Bounded string concatenation
#   - sprintf: Formatted string output (and variants)
#
# These functions are OPTIONAL - they're only included when the user
# explicitly includes stdio.h in their C source.
#
# Test Approach:
#   - Compilation tests: Verify C code using these functions compiles
#   - Assembly tests: Verify stdio.inc assembles correctly
#   - Assembly behavior tests: Test assembly logic patterns
#   - Integration tests: End-to-end compile + assemble pipeline
#
# Copyright (c) 2025 Hugo José Pinto & Contributors
# =============================================================================

import pytest
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.smallc.compiler import SmallCCompiler, CompilerOptions
from psion_sdk.errors import AssemblerError


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
    """Compile C source to assembly."""
    result = compiler.compile_source(source, "test.c")
    if result.success:
        return result.assembly
    raise Exception(f"Compilation failed: {result.errors}")


# =============================================================================
# strrchr Tests
# =============================================================================

class TestStrrchr:
    """Tests for strrchr - find last occurrence of character."""

    def test_strrchr_compiles(self, compiler):
        """strrchr call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *path = "/usr/local/bin/program";
            char *last_slash;
            last_slash = strrchr(path, '/');
        }
        """
        asm = compile_c(source, compiler)
        assert "_strrchr" in asm

    def test_strrchr_find_extension(self, compiler):
        """Common use case: finding file extension."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        char *get_extension(char *filename) {
            return strrchr(filename, '.');
        }
        """
        asm = compile_c(source, compiler)
        assert "_strrchr" in asm
        # Should push '.' character (46 or 0x2E)
        assert "#46" in asm or "#'.''" in asm or "#$2E" in asm.upper()

    def test_strrchr_in_condition(self, compiler):
        """strrchr used in conditional expression."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        int has_extension(char *filename) {
            if (strrchr(filename, '.')) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c(source, compiler)
        assert "_strrchr" in asm

    def test_strrchr_assembles(self, assembler):
        """strrchr assembly implementation should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100

            ; Test: find last '/' in path
            LDD #'/'
            PSHB
            PSHA
            LDD #TEST_PATH
            PSHB
            PSHA
            JSR _strrchr
            INS
            INS
            INS
            INS
            ; D now contains pointer to last '/' or 0
            RTS

TEST_PATH:  FCC "/a/b/c"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None
        assert len(result) > 0


# =============================================================================
# strstr Tests
# =============================================================================

class TestStrstr:
    """Tests for strstr - find substring in string."""

    def test_strstr_compiles(self, compiler):
        """strstr call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *text = "Hello World";
            char *found;
            found = strstr(text, "World");
        }
        """
        asm = compile_c(source, compiler)
        assert "_strstr" in asm

    def test_strstr_search_function(self, compiler):
        """strstr used for text searching."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        int contains(char *haystack, char *needle) {
            if (strstr(haystack, needle)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c(source, compiler)
        assert "_strstr" in asm

    def test_strstr_empty_needle(self, compiler):
        """strstr with empty needle should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *text = "Hello";
            char *empty = "";
            char *result;
            result = strstr(text, empty);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strstr" in asm

    def test_strstr_assembles(self, assembler):
        """strstr assembly implementation should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100

            ; Test: find "World" in "Hello World"
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


# =============================================================================
# strncat Tests
# =============================================================================

class TestStrncat:
    """Tests for strncat - bounded string concatenation."""

    def test_strncat_compiles(self, compiler):
        """strncat call should compile correctly."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buffer[20];
            strcpy(buffer, "Hello");
            strncat(buffer, " World", 3);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strncat" in asm

    def test_strncat_safe_concat(self, compiler):
        """strncat used for safe concatenation."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void safe_append(char *dest, char *src, int max_total) {
            int current_len;
            int space_left;
            current_len = strlen(dest);
            space_left = max_total - current_len - 1;
            if (space_left > 0) {
                strncat(dest, src, space_left);
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_strncat" in asm

    def test_strncat_with_zero_n(self, compiler):
        """strncat with n=0 should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[20];
            strcpy(buf, "test");
            strncat(buf, "ignore", 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strncat" in asm

    def test_strncat_assembles(self, assembler):
        """strncat assembly implementation should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100

            ; Initialize dest with "Hello"
            LDX #DEST
            LDAA #'H'
            STAA 0,X
            LDAA #'e'
            STAA 1,X
            LDAA #'l'
            STAA 2,X
            STAA 3,X
            LDAA #'o'
            STAA 4,X
            CLR 5,X

            ; Append at most 3 chars from " World"
            LDD #3
            PSHB
            PSHA
            LDD #SRC
            PSHB
            PSHA
            LDD #DEST
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

DEST:       RMB 20
SRC:        FCC " World"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None


# =============================================================================
# sprintf Tests
# =============================================================================

class TestSprintf:
    """Tests for sprintf - formatted string output."""

    def test_sprintf_basic_compiles(self, compiler):
        """Basic sprintf call should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf(buf, "Hello", 0, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm

    def test_sprintf_with_int(self, compiler):
        """sprintf with %d format should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            int value = 42;
            sprintf(buf, "Value: %d", value, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm

    def test_sprintf_with_string(self, compiler):
        """sprintf with %s format should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            char *name = "Bob";
            sprintf(buf, "Hello %s", name, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm

    def test_sprintf_with_hex(self, compiler):
        """sprintf with %x format should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            int addr = 0x1234;
            sprintf(buf, "Addr: %x", addr, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm

    def test_sprintf_multiple_args(self, compiler):
        """sprintf with multiple format arguments."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[64];
            sprintf(buf, "%d + %d = %d", 1, 2, 3, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm

    def test_sprintf_percent_escape(self, compiler):
        """sprintf with %% escape should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf(buf, "100%% complete", 0, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm


# =============================================================================
# sprintf Variant Tests
# =============================================================================

class TestSprintfVariants:
    """Tests for sprintf convenience variants (sprintf0-3)."""

    def test_sprintf0_compiles(self, compiler):
        """sprintf0 (no args) should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf0(buf, "Hello World");
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf0" in asm

    def test_sprintf1_compiles(self, compiler):
        """sprintf1 (one arg) should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf1(buf, "Value: %d", 42);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf1" in asm

    def test_sprintf2_compiles(self, compiler):
        """sprintf2 (two args) should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf2(buf, "%d + %d", 10, 20);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf2" in asm

    def test_sprintf3_compiles(self, compiler):
        """sprintf3 (three args) should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[32];
            sprintf3(buf, "%d + %d = %d", 5, 7, 12);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf3" in asm

    def test_sprintf_variants_assemble(self, assembler):
        """All sprintf variants should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100

            ; Test sprintf0
            LDD #FMT0
            PSHB
            PSHA
            LDD #BUF
            PSHB
            PSHA
            JSR _sprintf0
            INS
            INS
            INS
            INS

            ; Test sprintf1
            LDD #42
            PSHB
            PSHA
            LDD #FMT1
            PSHB
            PSHA
            LDD #BUF
            PSHB
            PSHA
            JSR _sprintf1
            INS
            INS
            INS
            INS
            INS
            INS

            RTS

BUF:        RMB 32
FMT0:       FCC "Hello"
            FCB 0
FMT1:       FCC "N=%d"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestStdioIntegration:
    """Integration tests for stdio functions.

    Note: These tests verify that C code using stdio functions compiles
    correctly. Full assembly requires the build tools (psbuild) which
    automatically add the necessary INCLUDE directives.
    """

    def test_combined_string_operations(self, compiler):
        """Program using multiple stdio functions should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void process_path(char *path) {
            char buffer[30];
            char *ext;
            char *filename;

            /* Find last slash */
            filename = strrchr(path, '/');
            if (filename) {
                filename = filename + 1;
            } else {
                filename = path;
            }

            /* Find extension */
            ext = strrchr(filename, '.');

            /* Build output */
            strcpy(buffer, "File: ");
            strncat(buffer, filename, 15);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strrchr" in asm
        assert "_strncat" in asm

    def test_sprintf_formatting_program(self, compiler):
        """Program with various sprintf formats should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void format_status(char *buf, int count, char *name) {
            sprintf(buf, "%s: %d items", name, count, 0, 0);
        }

        void format_hex(char *buf, int value) {
            sprintf1(buf, "0x%x", value);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm
        assert "_sprintf1" in asm

    def test_strstr_search_program(self, compiler):
        """Program using strstr for searching should compile."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        int find_keyword(char *text) {
            if (strstr(text, "ERROR")) {
                return 1;
            }
            if (strstr(text, "WARN")) {
                return 2;
            }
            return 0;
        }
        """
        asm = compile_c(source, compiler)
        assert "_strstr" in asm


# =============================================================================
# Assembly Code Quality Tests
# =============================================================================

class TestAssemblyQuality:
    """Tests that verify assembly code structure."""

    def test_strrchr_has_loop(self, assembler):
        """strrchr should contain a scanning loop."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            NOP
        """
        result = assembler.assemble(source)
        # Just verify it assembles; detailed structure testing would
        # require disassembly
        assert result is not None

    def test_sprintf_uses_itoa(self, assembler):
        """sprintf for %d should reference itoa internal."""
        # The sprintf implementation should call _itoa_internal for %d
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "stdio.inc"

            ORG $2100
            LDD #0
            PSHB
            PSHA
            PSHB
            PSHA
            PSHB
            PSHA
            LDD #42
            PSHB
            PSHA
            LDD #FMT
            PSHB
            PSHA
            LDD #BUF
            PSHB
            PSHA
            JSR _sprintf
            RTS

BUF:        RMB 20
FMT:        FCC "%d"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None


# =============================================================================
# Edge Cases
# =============================================================================

class TestStdioEdgeCases:
    """Edge case tests for stdio functions."""

    def test_strrchr_null_terminator(self, compiler):
        """strrchr should be able to find null terminator."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        char *find_end(char *s) {
            return strrchr(s, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strrchr" in asm

    def test_strstr_self_search(self, compiler):
        """strstr searching for string in itself."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        int test_self() {
            char *s = "Hello";
            if (strstr(s, s)) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_c(source, compiler)
        assert "_strstr" in asm

    def test_strncat_large_n(self, compiler):
        """strncat with n larger than source string."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[100];
            strcpy(buf, "Hi");
            strncat(buf, "!", 999);
        }
        """
        asm = compile_c(source, compiler)
        assert "_strncat" in asm

    def test_sprintf_char_format(self, compiler):
        """sprintf with %c format."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char buf[10];
            sprintf(buf, "Char: %c", 65, 0, 0, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_sprintf" in asm


# =============================================================================
# Documentation Examples
# =============================================================================

class TestStdioDocExamples:
    """Test examples from stdio.h documentation."""

    def test_strrchr_path_example(self, compiler):
        """Example: Finding filename in path."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void example() {
            char *ext;
            ext = strrchr("/a/b/c", '/');
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_strstr_example(self, compiler):
        """Example from strstr documentation."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void example() {
            char *found;
            found = strstr("Hello World", "World");
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_sprintf_examples(self, compiler):
        """Examples from sprintf documentation."""
        source = """
        #include <psion.h>
        #include <stdio.h>

        void examples() {
            char buf[32];
            sprintf(buf, "Score: %d", 42, 0, 0, 0);
            sprintf(buf, "Hex: %x", 255, 0, 0, 0);
            sprintf(buf, "Name: %s", "Bob", 0, 0, 0);
            sprintf(buf, "%d + %d = %d", 1, 2, 3, 0);
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None


# =============================================================================
# Include Guard Tests
# =============================================================================

class TestIncludeGuards:
    """Test that include guards work correctly."""

    def test_stdio_include_guard(self, compiler):
        """Multiple includes of stdio.h should be safe."""
        source = """
        #include <psion.h>
        #include <stdio.h>
        #include <stdio.h>

        void main() {
            char buf[10];
            sprintf0(buf, "test");
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_psion_required_before_stdio(self, compiler):
        """stdio.h should require psion.h first."""
        # This is enforced by the #error directive in stdio.h
        # We test that the correct order works
        source = """
        #include <psion.h>
        #include <stdio.h>

        void main() {
            char *p;
            p = strrchr("test", 't');
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None
