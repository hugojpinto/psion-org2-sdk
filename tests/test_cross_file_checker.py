# =============================================================================
# test_cross_file_checker.py - Cross-File Extern Type Checking Tests
# =============================================================================
# Tests for the cross-file extern type validation feature.
#
# When building multi-file C projects, extern declarations tell the compiler
# that a function or variable is defined elsewhere. If the extern declaration's
# signature differs from the actual definition, this can cause subtle runtime
# bugs. This module validates extern declarations at compile time.
#
# Key Feature Behavior:
# ---------------------
# 1. collect_declarations(): Traverses ASTs to extract function/variable
#    definitions and extern declarations
#
# 2. validate_extern_signatures(): Checks each extern against definitions:
#    - Function return type must match
#    - Function parameter count must match
#    - Function parameter types must match
#    - Variable types must match (with array/pointer decay)
#
# 3. Array/pointer decay: extern char[] matches char* and char[N]
#    (using -1 sentinel for unsized arrays in CType.array_size)
#
# 4. OPL procedures: Skipped during validation (handled differently)
#
# Test coverage includes:
#   - Matching extern declarations (should pass)
#   - Return type mismatches
#   - Parameter count mismatches
#   - Parameter type mismatches
#   - Variable type mismatches
#   - Undefined extern warnings
#   - Array/pointer decay handling
# =============================================================================

import pytest
from pathlib import Path

from psion_sdk.smallc.cross_file_checker import (
    validate_extern_signatures,
    collect_declarations,
    types_match,
    FunctionDefinition,
    FunctionExtern,
    VariableDefinition,
    VariableExtern,
)
from psion_sdk.smallc.compiler import parse_source
from psion_sdk.smallc.types import CType, BaseType
from psion_sdk.smallc.errors import ExternMismatchError
from psion_sdk.errors import SourceLocation

# =============================================================================
# Test Configuration
# =============================================================================

# Path to SDK include directory (relative to project root)
# This is needed for tests that use #include <psion.h>
INCLUDE_DIR = str(Path(__file__).parent.parent / "include")


# =============================================================================
# Helper Functions
# =============================================================================

def parse_files(*sources: tuple[str, str], use_stdlib: bool = False) -> list[tuple[str, any]]:
    """
    Parse multiple C source files and return list of (filename, ast) tuples.

    Args:
        sources: Tuples of (filename, source_code)
        use_stdlib: If True, add include path for psion.h and other headers

    Returns:
        List of (filename, ProgramNode) tuples
    """
    include_paths = [INCLUDE_DIR] if use_stdlib else None
    asts = []
    for filename, source in sources:
        ast = parse_source(source, filename, include_paths=include_paths)
        asts.append((filename, ast))
    return asts


def expect_no_errors(asts):
    """Assert that validating the ASTs produces no errors."""
    errors, warnings = validate_extern_signatures(asts, warn_undefined=False)
    assert len(errors) == 0, f"Expected no errors, got: {errors}"


def expect_error(asts, error_type: str):
    """Assert that validating produces an error of the given type."""
    errors, warnings = validate_extern_signatures(asts, warn_undefined=False)
    assert len(errors) > 0, "Expected at least one error"
    assert any(e.mismatch_type == error_type for e in errors), \
        f"Expected error type '{error_type}', got: {[e.mismatch_type for e in errors]}"


# =============================================================================
# types_match() Unit Tests
# =============================================================================

class TestTypesMatch:
    """Test the types_match() helper function."""

    def test_same_int_types_match(self):
        """Same int types should match."""
        t1 = CType(BaseType.INT)
        t2 = CType(BaseType.INT)
        assert types_match(t1, t2)

    def test_same_char_types_match(self):
        """Same char types should match."""
        t1 = CType(BaseType.CHAR)
        t2 = CType(BaseType.CHAR)
        assert types_match(t1, t2)

    def test_int_and_char_dont_match(self):
        """int and char should not match."""
        t1 = CType(BaseType.INT)
        t2 = CType(BaseType.CHAR)
        assert not types_match(t1, t2)

    def test_pointer_vs_non_pointer_dont_match(self):
        """Pointer and non-pointer types should not match."""
        t1 = CType(BaseType.INT, is_pointer=True, pointer_depth=1)
        t2 = CType(BaseType.INT)
        assert not types_match(t1, t2)

    def test_same_pointers_match(self):
        """Same pointer types should match."""
        t1 = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
        t2 = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
        assert types_match(t1, t2)

    def test_array_decays_to_pointer(self):
        """Array should match pointer after decay."""
        # char[10] decays to char*
        array_type = CType(BaseType.CHAR, array_size=10)
        pointer_type = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
        assert types_match(array_type, pointer_type)

    def test_unsized_array_decays_to_pointer(self):
        """Unsized array (extern char[];) should match pointer."""
        # extern char[] has array_size=-1 (unsized/incomplete)
        unsized_array = CType(BaseType.CHAR, array_size=-1)
        pointer_type = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
        assert types_match(unsized_array, pointer_type)

    def test_unsigned_matters(self):
        """Unsigned vs signed should not match."""
        t1 = CType(BaseType.INT, is_unsigned=True)
        t2 = CType(BaseType.INT, is_unsigned=False)
        assert not types_match(t1, t2)

    def test_pointer_depth_matters(self):
        """Different pointer depths should not match."""
        t1 = CType(BaseType.INT, is_pointer=True, pointer_depth=1)
        t2 = CType(BaseType.INT, is_pointer=True, pointer_depth=2)
        assert not types_match(t1, t2)


# =============================================================================
# Matching Extern Declarations (Should Pass)
# =============================================================================

class TestMatchingExterns:
    """Test cases where extern declarations correctly match definitions."""

    def test_matching_function(self):
        """Extern function with matching signature should pass."""
        main_source = '''
        extern int helper(int x);
        void main() { int r; r = helper(1); }
        '''
        helper_source = '''
        int helper(int x) { return x + 1; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_no_errors(asts)

    def test_matching_variable(self):
        """Extern variable with matching type should pass."""
        main_source = '''
        extern int counter;
        void main() { counter = 0; }
        '''
        helper_source = '''
        int counter;
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_no_errors(asts)

    def test_matching_pointer_variable(self):
        """Extern pointer variable should match."""
        main_source = '''
        extern char *buffer;
        void main() { buffer[0] = 'x'; }
        '''
        helper_source = '''
        char *buffer;
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_no_errors(asts)

    def test_array_matches_unsized_extern(self):
        """Array definition should match unsized extern array."""
        main_source = '''
        extern char buffer[];  /* Unsized array */
        void main() { buffer[0] = 'x'; }
        '''
        helper_source = '''
        char buffer[16];  /* Sized array */
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_no_errors(asts)


# =============================================================================
# Return Type Mismatches
# =============================================================================

class TestReturnTypeMismatch:
    """Test detection of function return type mismatches."""

    def test_int_vs_char_return_type(self):
        """Extern declares int return but definition returns char."""
        main_source = '''
        extern int get_value();
        void main() { int x; x = get_value(); }
        '''
        helper_source = '''
        char get_value() { return 'A'; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "return_type")

    def test_void_vs_int_return_type(self):
        """Extern declares void but definition returns int."""
        main_source = '''
        extern void setup();
        void main() { setup(); }
        '''
        helper_source = '''
        int setup() { return 0; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "return_type")

    def test_pointer_vs_non_pointer_return(self):
        """Extern declares pointer return but definition returns int."""
        main_source = '''
        extern char *get_string();
        void main() { char *s; s = get_string(); }
        '''
        helper_source = '''
        int get_string() { return 0; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "return_type")


# =============================================================================
# Parameter Count Mismatches
# =============================================================================

class TestParameterCountMismatch:
    """Test detection of parameter count mismatches."""

    def test_more_params_in_extern(self):
        """Extern declares more parameters than definition."""
        main_source = '''
        extern int add(int a, int b, int c);
        void main() { int r; r = add(1, 2, 3); }
        '''
        helper_source = '''
        int add(int a, int b) { return a + b; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "param_count")

    def test_fewer_params_in_extern(self):
        """Extern declares fewer parameters than definition."""
        main_source = '''
        extern int compute(int x);
        void main() { int r; r = compute(1); }
        '''
        helper_source = '''
        int compute(int x, int y) { return x + y; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "param_count")

    def test_zero_vs_nonzero_params(self):
        """Extern declares no params but definition has params."""
        main_source = '''
        extern int get_value();
        void main() { int r; r = get_value(); }
        '''
        helper_source = '''
        int get_value(int x) { return x; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "param_count")


# =============================================================================
# Parameter Type Mismatches
# =============================================================================

class TestParameterTypeMismatch:
    """Test detection of parameter type mismatches."""

    def test_int_vs_char_param(self):
        """Parameter type mismatch: int vs char."""
        main_source = '''
        extern int process(int x);
        void main() { int r; r = process(1); }
        '''
        helper_source = '''
        int process(char x) { return x; }
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "param_type")

    def test_pointer_vs_int_param(self):
        """Parameter type mismatch: pointer vs int."""
        main_source = '''
        extern void print_it(char *s);
        void main() { print_it("hello"); }
        '''
        helper_source = '''
        void print_it(int x) {}
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "param_type")


# =============================================================================
# Variable Type Mismatches
# =============================================================================

class TestVariableTypeMismatch:
    """Test detection of variable type mismatches."""

    def test_int_vs_char_variable(self):
        """Extern int vs definition char."""
        main_source = '''
        extern int value;
        void main() { value = 100; }
        '''
        helper_source = '''
        char value;
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "var_type")

    def test_pointer_vs_non_pointer_variable(self):
        """Extern pointer vs definition non-pointer."""
        main_source = '''
        extern char *buffer;
        void main() { buffer[0] = 'x'; }
        '''
        helper_source = '''
        char buffer;  /* Not a pointer! */
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
        )
        expect_error(asts, "var_type")


# =============================================================================
# Undefined Extern Warnings
# =============================================================================

class TestUndefinedExternWarnings:
    """Test that undefined externs generate warnings (not errors)."""

    def test_undefined_extern_function_warning(self):
        """Undefined extern function should warn, not error."""
        main_source = '''
        extern int helper();  /* No definition provided */
        void main() { int r; r = helper(); }
        '''
        asts = parse_files(("main.c", main_source))
        errors, warnings = validate_extern_signatures(asts, warn_undefined=True)
        assert len(errors) == 0  # No errors
        assert len(warnings) > 0  # But we should have a warning
        assert "helper" in str(warnings[0]).lower()

    def test_undefined_extern_variable_warning(self):
        """Undefined extern variable should warn, not error."""
        main_source = '''
        extern int counter;  /* No definition provided */
        void main() { counter = 0; }
        '''
        asts = parse_files(("main.c", main_source))
        errors, warnings = validate_extern_signatures(asts, warn_undefined=True)
        assert len(errors) == 0
        assert len(warnings) > 0
        assert "counter" in str(warnings[0]).lower()


# =============================================================================
# collect_declarations() Unit Tests
# =============================================================================

class TestCollectDeclarations:
    """Test the collect_declarations() function."""

    def test_collects_function_definitions(self):
        """Should collect function definitions."""
        source = '''
        int helper(int x) { return x; }
        void main() {}
        '''
        asts = parse_files(("test.c", source))
        collected = collect_declarations(asts)
        assert "helper" in collected.func_definitions
        assert "main" in collected.func_definitions

    def test_collects_function_externs(self):
        """Should collect extern function declarations."""
        source = '''
        extern int helper(int x);
        void main() {}
        '''
        asts = parse_files(("test.c", source))
        collected = collect_declarations(asts)
        assert len(collected.func_externs) == 1
        assert collected.func_externs[0].name == "helper"

    def test_collects_variable_definitions(self):
        """Should collect global variable definitions."""
        source = '''
        int counter;
        void main() { counter = 0; }
        '''
        asts = parse_files(("test.c", source))
        collected = collect_declarations(asts)
        assert "counter" in collected.var_definitions

    def test_collects_variable_externs(self):
        """Should collect extern variable declarations."""
        source = '''
        extern int counter;
        void main() { counter = 0; }
        '''
        asts = parse_files(("test.c", source))
        collected = collect_declarations(asts)
        assert len(collected.var_externs) == 1
        assert collected.var_externs[0].name == "counter"

    def test_skips_opl_procedures(self):
        """
        Should skip OPL procedure declarations.

        OPL procedures (declared with 'opl' keyword in psion.h) are handled
        separately from regular C functions. They should not appear in the
        func_externs list because they use a different calling convention
        (QCode bridge) and don't participate in cross-file type checking.
        """
        source = '''
        #include <psion.h>
        void main() { cls(); }
        '''
        # Note: use_stdlib=True to include psion.h which declares cls() as OPL
        asts = parse_files(("test.c", source), use_stdlib=True)
        collected = collect_declarations(asts)
        # cls is an OPL procedure, should not appear as extern
        assert all(e.name != "cls" for e in collected.func_externs)


# =============================================================================
# Multiple Files
# =============================================================================

class TestMultipleFiles:
    """Test validation across multiple files."""

    def test_three_file_chain(self):
        """Validate externs across three files."""
        main_source = '''
        extern int helper(int x);
        extern int counter;
        void main() { counter = helper(1); }
        '''
        helper_source = '''
        extern int counter;
        int helper(int x) { return x + counter; }
        '''
        data_source = '''
        int counter;
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
            ("data.c", data_source),
        )
        expect_no_errors(asts)

    def test_multiple_externs_same_symbol(self):
        """Multiple files can extern the same symbol."""
        main_source = '''
        extern int counter;
        void main() { counter = 0; }
        '''
        helper_source = '''
        extern int counter;
        void helper() { counter++; }
        '''
        data_source = '''
        int counter;
        '''
        asts = parse_files(
            ("main.c", main_source),
            ("helper.c", helper_source),
            ("data.c", data_source),
        )
        expect_no_errors(asts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
