"""
Tests for psbuild - Unified Build Tool
======================================

These tests verify that psbuild correctly builds Psion programs from
C and assembly source files.
"""

import tempfile
from pathlib import Path

import pytest

from psion_sdk.cli.psbuild import (
    detect_source_type,
    find_sdk_include_dir,
    sanitize_procedure_name,
    resolve_output_path,
    derive_procedure_name,
)


# =============================================================================
# Test Source Type Detection
# =============================================================================

class TestSourceTypeDetection:
    """Tests for detect_source_type()."""

    def test_c_extension(self):
        """Should detect .c files as C source."""
        assert detect_source_type(Path("hello.c")) == "c"
        assert detect_source_type(Path("/path/to/program.c")) == "c"
        assert detect_source_type(Path("MY_PROG.C")) == "c"  # Case insensitive

    def test_asm_extension(self):
        """Should detect .asm files as assembly source."""
        assert detect_source_type(Path("hello.asm")) == "asm"
        assert detect_source_type(Path("/path/to/program.asm")) == "asm"
        assert detect_source_type(Path("BEEP.ASM")) == "asm"  # Case insensitive

    def test_s_extension(self):
        """Should detect .s files as assembly source."""
        assert detect_source_type(Path("hello.s")) == "asm"
        assert detect_source_type(Path("program.S")) == "asm"

    def test_invalid_extension(self):
        """Should raise error for unrecognized extensions."""
        import click
        with pytest.raises(click.BadParameter, match="Unrecognized source file"):
            detect_source_type(Path("hello.txt"))
        with pytest.raises(click.BadParameter):
            detect_source_type(Path("program.py"))


# =============================================================================
# Test Procedure Name Sanitization
# =============================================================================

class TestSanitizeProcedureName:
    """Tests for sanitize_procedure_name()."""

    def test_simple_name(self):
        """Should uppercase simple names."""
        assert sanitize_procedure_name("hello") == "HELLO"
        assert sanitize_procedure_name("HELLO") == "HELLO"
        assert sanitize_procedure_name("Hello") == "HELLO"

    def test_removes_underscores(self):
        """Should remove underscores from names."""
        assert sanitize_procedure_name("my_prog") == "MYPROG"
        assert sanitize_procedure_name("test_one_two") == "TESTONET"  # Truncated

    def test_truncates_to_8_chars(self):
        """Should truncate names longer than 8 characters."""
        assert sanitize_procedure_name("verylongname") == "VERYLONG"
        assert sanitize_procedure_name("abcdefghij") == "ABCDEFGH"

    def test_alphanumeric_allowed(self):
        """Should allow alphanumeric characters."""
        assert sanitize_procedure_name("test123") == "TEST123"
        assert sanitize_procedure_name("a1b2c3d4e5") == "A1B2C3D4"

    def test_removes_special_chars(self):
        """Should remove special characters."""
        assert sanitize_procedure_name("hello-world") == "HELLOWORLD"[:8]
        assert sanitize_procedure_name("test.prog") == "TESTPROG"

    def test_error_on_empty_result(self):
        """Should raise error if sanitization results in empty name."""
        import click
        with pytest.raises(click.BadParameter, match="at least one alphanumeric"):
            sanitize_procedure_name("___")
        with pytest.raises(click.BadParameter):
            sanitize_procedure_name("---")

    def test_error_on_digit_start(self):
        """Should raise error if name starts with digit after sanitization."""
        import click
        with pytest.raises(click.BadParameter, match="must start with a letter"):
            sanitize_procedure_name("123test")
        with pytest.raises(click.BadParameter):
            sanitize_procedure_name("_1test")  # Underscore removed, starts with 1


# =============================================================================
# Test Output Path Resolution
# =============================================================================

class TestResolveOutputPath:
    """Tests for resolve_output_path()."""

    def test_explicit_output_returned(self):
        """Should return explicit output path unchanged."""
        output = Path("/tmp/MY_OUTPUT.opk")
        source = Path("/some/path/hello.c")
        assert resolve_output_path(output, source) == output

    def test_derives_from_source_name(self):
        """Should derive output name from source file when not specified."""
        source = Path("/some/path/hello.c")
        result = resolve_output_path(None, source)
        assert result.name == "HELLO.opk"
        assert result.parent == Path.cwd()

    def test_sanitizes_source_name(self):
        """Should sanitize source name for procedure compatibility."""
        source = Path("/path/my_program.c")
        result = resolve_output_path(None, source)
        # Underscore removed, uppercased, truncated to 8 chars
        # "my_program" → "MYPROGRAM" (9 chars) → "MYPROGRA" (8 chars)
        assert result.name == "MYPROGRA.opk"


# =============================================================================
# Test SDK Include Directory Finding
# =============================================================================

class TestFindSdkIncludeDir:
    """Tests for find_sdk_include_dir()."""

    def test_finds_include_directory(self):
        """Should find the SDK include directory."""
        include_dir = find_sdk_include_dir()
        # Should find the include directory relative to the module
        assert include_dir is not None
        assert include_dir.exists()
        assert include_dir.is_dir()
        # Should contain expected files
        assert (include_dir / "psion.h").exists()
        assert (include_dir / "runtime.inc").exists()


# =============================================================================
# Test Derive Procedure Name
# =============================================================================

class TestDeriveProcedureName:
    """Tests for derive_procedure_name()."""

    def test_derives_from_opk_stem(self):
        """Should derive procedure name from OPK filename stem."""
        assert derive_procedure_name(Path("/tmp/HELLO.opk")) == "HELLO"
        assert derive_procedure_name(Path("MYPROG.opk")) == "MYPROG"

    def test_sanitizes_name(self):
        """Should sanitize the derived name."""
        assert derive_procedure_name(Path("my_app.opk")) == "MYAPP"
        assert derive_procedure_name(Path("test-prog.opk")) == "TESTPROG"


# =============================================================================
# Integration Tests (require actual compilation)
# =============================================================================

class TestPsbuildIntegration:
    """Integration tests that verify the full build pipeline."""

    def test_build_c_source(self):
        """Should build a C program to OPK."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        # Create a simple C program
        c_source = """
#include <psion.h>

void main() {
    cls();
    print("Test");
    getkey();
}
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Write source file
            Path("test.c").write_text(c_source)

            # Run psbuild
            result = runner.invoke(main, ["test.c", "-o", "TEST.opk"])

            # Check success
            assert result.exit_code == 0, f"Build failed: {result.output}"
            assert Path("TEST.opk").exists()
            assert Path("TEST.opk").stat().st_size > 0

    def test_build_asm_source(self):
        """Should build an assembly program to OPK."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        # Create a simple assembly program
        asm_source = """
        INCLUDE "psion.inc"

        ORG $2000

START:  RTS
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Write source file
            Path("test.asm").write_text(asm_source)

            # Run psbuild
            result = runner.invoke(main, ["test.asm", "-o", "TEST.opk"])

            # Check success
            assert result.exit_code == 0, f"Build failed: {result.output}"
            assert Path("TEST.opk").exists()

    def test_verbose_output(self):
        """Should show build stages in verbose mode."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        c_source = """
#include <psion.h>
void main() { cls(); }
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.c").write_text(c_source)
            result = runner.invoke(main, ["-v", "test.c", "-o", "TEST.opk"])

            assert result.exit_code == 0
            # Should show all three stages for C
            assert "[1/3]" in result.output
            assert "[2/3]" in result.output
            assert "[3/3]" in result.output
            assert "Compiling" in result.output
            assert "Assembling" in result.output
            assert "Packaging" in result.output

    def test_keep_intermediate_files(self):
        """Should keep intermediate files with -k flag."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        c_source = """
#include <psion.h>
void main() { cls(); }
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.c").write_text(c_source)
            result = runner.invoke(main, ["-k", "test.c", "-o", "TEST.opk"])

            assert result.exit_code == 0
            # Should have intermediate files
            assert Path("test.asm").exists()
            assert Path("TEST.ob3").exists()

    def test_model_flag(self):
        """Should pass model flag through to compilation."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        c_source = """
#include <psion.h>
void main() { cls(); }
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.c").write_text(c_source)
            result = runner.invoke(main, ["-m", "LZ", "-v", "test.c", "-o", "TEST.opk"])

            assert result.exit_code == 0
            # Verbose output should mention model
            assert "LZ" in result.output or "Model" in result.output
