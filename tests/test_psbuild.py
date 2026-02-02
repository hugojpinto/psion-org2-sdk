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
    classify_input_files,
    find_main_file,
    concatenate_assembly_files,
    ClassifiedFiles,
    MainFileResult,
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


# =============================================================================
# Multi-File Build Tests
# =============================================================================

class TestClassifyInputFiles:
    """Tests for classify_input_files()."""

    def test_classify_single_c_file(self):
        """Should classify single C file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test.c"
            c_file.write_text("int main() { return 0; }")

            result = classify_input_files([c_file])

            assert len(result.c_files) == 1
            assert len(result.asm_files) == 0
            assert result.c_files[0] == c_file

    def test_classify_single_asm_file(self):
        """Should classify single assembly file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            asm_file = Path(tmpdir) / "test.asm"
            asm_file.write_text("RTS")

            result = classify_input_files([asm_file])

            assert len(result.c_files) == 0
            assert len(result.asm_files) == 1
            assert result.asm_files[0] == asm_file

    def test_classify_mixed_files(self):
        """Should classify mix of C and assembly files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "main.c"
            asm_file = Path(tmpdir) / "helper.asm"
            c_file.write_text("int main() { return 0; }")
            asm_file.write_text("RTS")

            result = classify_input_files([c_file, asm_file])

            assert len(result.c_files) == 1
            assert len(result.asm_files) == 1
            assert c_file in result.c_files
            assert asm_file in result.asm_files

    def test_classify_multiple_c_files(self):
        """Should classify multiple C files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_c = Path(tmpdir) / "main.c"
            helper_c = Path(tmpdir) / "helper.c"
            main_c.write_text("int main() { return 0; }")
            helper_c.write_text("int helper() { return 1; }")

            result = classify_input_files([main_c, helper_c])

            assert len(result.c_files) == 2
            assert len(result.asm_files) == 0

    def test_preserve_order(self):
        """Should preserve order of files within categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for name in ["a.c", "b.c", "c.c"]:
                f = Path(tmpdir) / name
                f.write_text("int x;")
                files.append(f)

            result = classify_input_files(files)

            assert [f.name for f in result.c_files] == ["a.c", "b.c", "c.c"]


class TestFindMainFile:
    """Tests for find_main_file()."""

    def test_find_main_in_single_file(self):
        """Should find main() in single C file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_c = Path(tmpdir) / "main.c"
            main_c.write_text("void main() { }")

            result = find_main_file([main_c], include_paths=[])

            assert result.found
            assert result.main_file == main_c
            assert len(result.library_c_files) == 0
            assert result.error is None

    def test_find_main_among_multiple_files(self):
        """Should find main() among multiple C files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_c = Path(tmpdir) / "main.c"
            helper_c = Path(tmpdir) / "helper.c"
            main_c.write_text("void main() { helper(); }")
            helper_c.write_text("int helper() { return 1; }")

            result = find_main_file([helper_c, main_c], include_paths=[])

            assert result.found
            assert result.main_file == main_c
            assert helper_c in result.library_c_files

    def test_no_main_found(self):
        """Should report error when no main() is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            helper_c = Path(tmpdir) / "helper.c"
            helper_c.write_text("int helper() { return 1; }")

            result = find_main_file([helper_c], include_paths=[])

            assert not result.found
            assert result.main_file is None
            assert result.error is not None
            assert "main()" in result.error

    def test_multiple_main_found(self):
        """Should report error when multiple main() found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main1_c = Path(tmpdir) / "main1.c"
            main2_c = Path(tmpdir) / "main2.c"
            main1_c.write_text("void main() { }")
            main2_c.write_text("void main() { }")

            result = find_main_file([main1_c, main2_c], include_paths=[])

            assert not result.found
            assert result.error is not None
            assert "multiple" in result.error.lower()

    def test_main_with_return_type(self):
        """Should find main() with int return type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_c = Path(tmpdir) / "main.c"
            main_c.write_text("int main() { return 0; }")

            result = find_main_file([main_c], include_paths=[])

            assert result.found
            assert result.main_file == main_c

    def test_main_with_args(self):
        """Should find main() with arguments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_c = Path(tmpdir) / "main.c"
            # Note: Small-C doesn't support argc/argv but parser should still find it
            main_c.write_text("void main(void) { }")

            result = find_main_file([main_c], include_paths=[])

            assert result.found


class TestConcatenateAssemblyFiles:
    """Tests for concatenate_assembly_files()."""

    def test_single_main_file_passes_through(self):
        """Single main assembly file should pass through unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main_asm = Path(tmpdir) / "main.asm"
            main_asm.write_text("_entry:\n    RTS\n    END\n")
            output = Path(tmpdir) / "merged.asm"

            # No library files, no user asm files, just main
            concatenate_assembly_files([], [], main_asm, output)

            content = output.read_text()
            assert "_entry:" in content
            assert "RTS" in content
            assert "END" in content

    def test_library_file_stripped_of_includes(self):
        """Library files should have INCLUDE directives stripped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_asm = Path(tmpdir) / "lib.asm"
            main_asm = Path(tmpdir) / "main.asm"
            lib_asm.write_text('INCLUDE "psion.inc"\n_double:\n    ASLD\n    RTS\n')
            main_asm.write_text('INCLUDE "psion.inc"\n_entry:\n    BSR _double\n    RTS\n    END\n')
            output = Path(tmpdir) / "merged.asm"

            # lib_asm is a library file (from C compiled in library mode)
            concatenate_assembly_files([lib_asm], [], main_asm, output)

            content = output.read_text()
            # Main file's INCLUDE should remain
            assert 'INCLUDE "psion.inc"' in content
            # Library's INCLUDE should be stripped (commented out)
            lines = content.split('\n')
            stripped_includes = [l for l in lines if '[stripped:' in l and 'INCLUDE' in l]
            assert len(stripped_includes) == 1
            # Both functions should be present
            assert "_double:" in content
            assert "_entry:" in content

    def test_multiple_library_files(self):
        """Should concatenate multiple library files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib1 = Path(tmpdir) / "lib1.asm"
            lib2 = Path(tmpdir) / "lib2.asm"
            main_asm = Path(tmpdir) / "main.asm"
            lib1.write_text("_func1:\n    RTS\n")
            lib2.write_text("_func2:\n    RTS\n")
            main_asm.write_text("_entry:\n    BSR _func1\n    BSR _func2\n    RTS\n    END\n")
            output = Path(tmpdir) / "merged.asm"

            concatenate_assembly_files([lib1, lib2], [], main_asm, output)

            content = output.read_text()
            assert "_func1:" in content
            assert "_func2:" in content
            assert "_entry:" in content
            # Main should be last (has END directive)
            assert content.index("_func1:") < content.index("_entry:")
            assert content.index("_func2:") < content.index("_entry:")

    def test_preserves_function_labels(self):
        """Should preserve all function labels from library files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = Path(tmpdir) / "lib.asm"
            main_asm = Path(tmpdir) / "main.asm"
            lib.write_text("_helper:\n    PSHX\n_helper_loop:\n    INX\n    BNE _helper_loop\n    PULX\n    RTS\n")
            main_asm.write_text("_entry:\n    JSR _helper\n    RTS\n    END\n")
            output = Path(tmpdir) / "merged.asm"

            concatenate_assembly_files([lib], [], main_asm, output)

            content = output.read_text()
            assert "_helper:" in content
            assert "_helper_loop:" in content

    def test_user_asm_files_included(self):
        """User-provided assembly files should be included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_asm = Path(tmpdir) / "user.asm"
            main_asm = Path(tmpdir) / "main.asm"
            user_asm.write_text("_user_func:\n    LDD #42\n    RTS\n")
            main_asm.write_text("_entry:\n    JSR _user_func\n    RTS\n    END\n")
            output = Path(tmpdir) / "merged.asm"

            # User asm is in the user_asm_files list (second argument)
            concatenate_assembly_files([], [user_asm], main_asm, output)

            content = output.read_text()
            assert "_user_func:" in content
            assert "_entry:" in content


class TestMultiFileBuildIntegration:
    """Integration tests for multi-file builds."""

    def test_build_two_c_files(self):
        """Should build two C files into single OPK."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        helper_c = """
int double_it(int x) {
    return x + x;
}
"""
        main_c = """
#include <psion.h>

extern int double_it(int x);

void main() {
    int result;
    cls();
    result = double_it(21);
    print("Done");
    getkey();
}
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("helper.c").write_text(helper_c)
            Path("main.c").write_text(main_c)

            result = runner.invoke(main, ["helper.c", "main.c", "-o", "TEST.opk"])

            assert result.exit_code == 0, f"Build failed: {result.output}"
            assert Path("TEST.opk").exists()
            assert Path("TEST.opk").stat().st_size > 0

    def test_build_with_verbose_shows_linking(self):
        """Verbose output should indicate multi-file linking."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        helper_c = "int helper() { return 1; }"
        main_c = """
#include <psion.h>
extern int helper();
void main() { helper(); }
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("helper.c").write_text(helper_c)
            Path("main.c").write_text(main_c)

            result = runner.invoke(main, ["-v", "helper.c", "main.c", "-o", "TEST.opk"])

            assert result.exit_code == 0
            # Should mention linking or merging
            output_lower = result.output.lower()
            assert "linking" in output_lower or "merging" in output_lower or "main" in output_lower

    def test_build_error_no_main(self):
        """Should error when no main() is found in multi-file build."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        helper1_c = "int helper1() { return 1; }"
        helper2_c = "int helper2() { return 2; }"

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("helper1.c").write_text(helper1_c)
            Path("helper2.c").write_text(helper2_c)

            result = runner.invoke(main, ["helper1.c", "helper2.c", "-o", "TEST.opk"])

            assert result.exit_code != 0
            assert "main" in result.output.lower()

    def test_build_mixed_c_and_asm(self):
        """Should build mix of C and assembly files."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        asm_helper = """
; Simple helper function
_helper:
        LDD     #42
        RTS
"""
        main_c = """
#include <psion.h>

extern int helper();

void main() {
    int x;
    cls();
    x = helper();
    print("Test");
    getkey();
}
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("helper.asm").write_text(asm_helper)
            Path("main.c").write_text(main_c)

            result = runner.invoke(main, ["helper.asm", "main.c", "-o", "TEST.opk"])

            assert result.exit_code == 0, f"Build failed: {result.output}"
            assert Path("TEST.opk").exists()

    def test_extern_function_called(self):
        """Should correctly call extern function from another file."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        helper_c = """
int add(int a, int b) {
    return a + b;
}
"""
        main_c = """
#include <psion.h>

extern int add(int a, int b);

void main() {
    int result;
    cls();
    result = add(10, 20);
    print("Done");
    getkey();
}
"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("helper.c").write_text(helper_c)
            Path("main.c").write_text(main_c)

            # Keep intermediate files to inspect
            result = runner.invoke(main, ["-k", "helper.c", "main.c", "-o", "TEST.opk"])

            assert result.exit_code == 0, f"Build failed: {result.output}"

            # Check merged assembly has both functions
            merged_asm = Path("test_merged.asm")
            if merged_asm.exists():
                content = merged_asm.read_text()
                assert "_add:" in content or "_add" in content
                assert "_main:" in content

    def test_order_independence(self):
        """Should work regardless of file order on command line."""
        from click.testing import CliRunner
        from psion_sdk.cli.psbuild import main

        helper_c = "int helper() { return 1; }"
        main_c = """
#include <psion.h>
extern int helper();
void main() { helper(); }
"""
        runner = CliRunner()

        # Test both orders
        for order in [["helper.c", "main.c"], ["main.c", "helper.c"]]:
            with runner.isolated_filesystem():
                Path("helper.c").write_text(helper_c)
                Path("main.c").write_text(main_c)

                result = runner.invoke(main, order + ["-o", "TEST.opk"])

                assert result.exit_code == 0, f"Build failed with order {order}: {result.output}"
                assert Path("TEST.opk").exists()
