# =============================================================================
# test_function_return_types.py - Function Return Type Tracking Tests
# =============================================================================
# Tests for the function return type tracking feature in the Small-C compiler.
#
# This feature ensures that function return types are correctly inferred
# during expression type checking. Before this feature, all function calls
# were assumed to return TYPE_INT, which could hide type errors.
#
# Key Feature Behavior:
# ---------------------
# 1. User-defined functions: Return types tracked via _c_funcs registry
#    populated during AST traversal (codegen.py lines 622-635)
#
# 2. OPL functions: Return types tracked via _opl_funcs registry
#    (declared with 'opl' keyword in psion.h)
#
# 3. Built-in functions: Return types defined in _builtin_function_types
#    (runtime functions like strlen, strchr, atoi)
#
# 4. Void function errors: _get_expression_type() raises CCodeGenError
#    when void function is used in an expression (lines 1051-1056)
#
# 5. Type validation: _generate_assignment() calls _get_expression_type()
#    on the RHS to catch void function calls (line ~2850)
#
# Test coverage includes:
#   - User-defined function return types (void, int, char, pointers)
#   - Void function used in expression (error)
#   - Built-in function return types (psion.h, float.h, etc.)
#   - Forward declarations
#   - OPL procedure return types
# =============================================================================

import pytest
from pathlib import Path

from psion_sdk.smallc import compile_c
from psion_sdk.smallc.errors import SmallCError

# =============================================================================
# Test Configuration
# =============================================================================

# Path to SDK include directory (relative to project root)
# This is needed for tests that use #include <psion.h>
INCLUDE_DIR = str(Path(__file__).parent.parent / "include")


# =============================================================================
# Helper Functions
# =============================================================================

def compile_source(source: str, use_stdlib: bool = False) -> str:
    """
    Compile C source and return the assembly output.

    Args:
        source: C source code to compile
        use_stdlib: If True, add include path for psion.h and other headers

    Returns:
        Generated HD6303 assembly as string

    Raises:
        SmallCError: On compilation failure
    """
    include_paths = [INCLUDE_DIR] if use_stdlib else ["."]
    return compile_c(source, include_paths=include_paths)


def expect_compile_error(source: str, error_substring: str, use_stdlib: bool = False) -> None:
    """
    Assert that compiling the source raises an error containing the substring.

    Args:
        source: C source code expected to fail compilation
        error_substring: Text that must appear in the error message (case-insensitive)
        use_stdlib: If True, add include path for psion.h and other headers
    """
    include_paths = [INCLUDE_DIR] if use_stdlib else ["."]
    with pytest.raises(SmallCError) as exc_info:
        compile_c(source, include_paths=include_paths)
    assert error_substring.lower() in str(exc_info.value).lower(), \
        f"Expected error containing '{error_substring}', got: {exc_info.value}"


def asm_contains_function(asm: str, func_name: str) -> bool:
    """
    Check if assembly output contains a function definition.

    The Small-C compiler generates function labels as _funcname (lowercase,
    with underscore prefix). This helper does case-insensitive matching
    to be robust against any future changes.

    Args:
        asm: Assembly output from compiler
        func_name: Function name to search for (without underscore prefix)

    Returns:
        True if function label found in assembly
    """
    # Function labels are generated as _funcname:
    label_pattern = f"_{func_name}:"
    return label_pattern.lower() in asm.lower()


# =============================================================================
# User-defined Function Return Types
# =============================================================================

class TestUserDefinedFunctionReturnTypes:
    """
    Test that user-defined function return types are correctly tracked
    and used during expression type inference.

    The compiler populates _c_funcs during AST traversal (codegen.py:622-635)
    with CFunctionSignature objects containing return type information.
    """

    def test_int_function_return_type(self):
        """
        Function returning int should compile without error.

        The return type is tracked in _c_funcs and used when the function
        is called in an assignment context.
        """
        source = '''
        int get_value() { return 42; }
        void main() {
            int x;
            x = get_value();  /* Should work - int assigned to int */
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "get_value"), "Function should be defined"
        assert "JSR" in asm, "Should call the function"

    def test_char_function_return_type(self):
        """
        Function returning char should compile correctly.

        The return type (char) is tracked and the generated code
        uses appropriate char-sized operations.
        """
        source = '''
        char get_char() { return 'A'; }
        void main() {
            char c;
            c = get_char();
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "get_char")

    def test_pointer_function_return_type(self):
        """
        Function returning pointer should compile correctly.

        Pointer return types are tracked as CType with is_pointer=True.
        """
        source = '''
        char *get_string() { return "hello"; }
        void main() {
            char *s;
            s = get_string();
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "get_string")

    def test_forward_declared_function(self):
        """
        Forward declared functions should work correctly.

        When a forward declaration is seen before the definition,
        both are added to _c_funcs. The definition (is_forward_decl=False)
        takes precedence over the declaration (codegen.py:627-628).
        """
        source = '''
        int calculate();  /* Forward declaration */

        void main() {
            int result;
            result = calculate();
        }

        int calculate() { return 100; }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "calculate")


# =============================================================================
# Void Function Error Detection
# =============================================================================

class TestVoidFunctionErrors:
    """
    Test that using void functions in expressions produces errors.
    This is a compile-time error in C because void has no value.

    The error is detected in _get_expression_type() (codegen.py:1051-1056)
    when a CallExpression references a void function.

    Type validation is triggered from _generate_assignment() which calls
    _get_expression_type(expr.value) to validate the RHS expression.
    """

    def test_void_function_in_assignment(self):
        """
        Using void function return value in assignment should error.

        The error is raised in _get_expression_type() when the call
        expression is validated by _generate_assignment().
        """
        source = '''
        void do_nothing() {}
        void main() {
            int x;
            x = do_nothing();  /* ERROR: void used in expression */
        }
        '''
        expect_compile_error(source, "void")

    def test_void_function_in_arithmetic(self):
        """
        Using void function in arithmetic should error.

        The error is raised when _generate_binary() calls
        _get_expression_type() on the operands.
        """
        source = '''
        void setup() {}
        void main() {
            int x;
            x = 1 + setup();  /* ERROR: void in arithmetic */
        }
        '''
        expect_compile_error(source, "void")

    def test_void_function_standalone_ok(self):
        """
        Calling void function as statement should work.

        When a void function is called as a standalone statement
        (not in an expression), no error is raised because the
        return value is not used.
        """
        source = '''
        void do_work() {}
        void main() {
            do_work();  /* OK - void function called as statement */
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "do_work")


# =============================================================================
# Built-in Function Return Types (requires psion.h)
# =============================================================================

class TestBuiltinFunctionReturnTypes:
    """
    Test that built-in functions from headers have correct return types.

    Built-in function types are defined in _builtin_function_types dict
    (codegen.py). These include functions from:
    - psion.h: strlen, strchr, getkey, atoi, etc.
    - Runtime library functions
    """

    def test_strlen_returns_int(self):
        """
        strlen() should return int (length of string).

        strlen is declared in psion.h and its return type is tracked
        in _builtin_function_types.
        """
        source = '''
        #include <psion.h>
        void main() {
            int len;
            len = strlen("hello");  /* Should work - int return */
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        # strlen is implemented as a runtime function
        assert "STRLEN" in asm.upper() or asm_contains_function(asm, "strlen")

    def test_getkey_returns_int(self):
        """
        getkey() should return int (keycode).

        getkey is an OPL procedure that returns an integer keycode.
        """
        source = '''
        #include <psion.h>
        void main() {
            int key;
            key = getkey();
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        # getkey is implemented via OPL bridge - look for KEY opcode
        assert "KEY" in asm.upper()

    def test_strchr_returns_pointer(self):
        """
        strchr() should return char* (pointer to found char).

        strchr returns a pointer to the first occurrence of a character,
        or NULL if not found.
        """
        source = '''
        #include <psion.h>
        void main() {
            char *p;
            p = strchr("hello", 'l');
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        assert "STRCHR" in asm.upper() or asm_contains_function(asm, "strchr")


# =============================================================================
# OPL Procedure Return Types
# =============================================================================

class TestOplProcedureReturnTypes:
    """
    Test that OPL procedure return types are correctly tracked.

    OPL procedures are declared with the 'opl' keyword in psion.h.
    Their signatures are tracked in _opl_funcs (codegen.py:567).

    When a call to an OPL procedure is processed, _get_expression_type()
    checks _opl_funcs first (line 1038) and raises an error if the
    procedure is void and used in an expression (lines 1041-1045).
    """

    def test_opl_void_procedure(self):
        """
        OPL void procedure (cls) should be callable as statement.

        cls() clears the screen and returns void.
        """
        source = '''
        #include <psion.h>
        void main() {
            cls();  /* OPL procedure, returns void */
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        # OPL calls use special QCode calling convention
        assert "CLS" in asm.upper()

    def test_opl_int_function(self):
        """
        OPL function returning int (getkey) should be usable in expressions.
        """
        source = '''
        #include <psion.h>
        void main() {
            int key;
            key = getkey();  /* Returns int */
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        assert asm  # Should compile without error


# =============================================================================
# Edge Cases
# =============================================================================

class TestReturnTypeEdgeCases:
    """
    Test edge cases in function return type handling.
    """

    def test_recursive_function(self):
        """
        Recursive functions should have correct return type tracking.

        The function signature is registered before its body is generated,
        so recursive calls can look up the return type correctly.
        """
        source = '''
        int factorial(int n) {
            if (n <= 1) return 1;
            return n * factorial(n - 1);
        }
        void main() {
            int result;
            result = factorial(5);
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "factorial")

    def test_chained_function_calls(self):
        """
        Chained function calls should work with type tracking.

        When one function call is passed as argument to another,
        both return types must be correctly inferred.
        """
        source = '''
        int add(int a, int b) { return a + b; }
        int double_it(int x) { return x * 2; }
        void main() {
            int result;
            result = double_it(add(1, 2));
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "add")
        assert asm_contains_function(asm, "double_it")

    def test_function_as_array_index(self):
        """
        Function return value used as array index.

        The return type must be int for array subscript computation.
        """
        source = '''
        int get_index() { return 2; }
        void main() {
            int arr[5];
            int x;
            x = arr[get_index()];
        }
        '''
        asm = compile_source(source)
        assert asm_contains_function(asm, "get_index")


# =============================================================================
# Integration with Standard Library
# =============================================================================

class TestStdlibReturnTypes:
    """
    Test function return types for standard library functions.
    """

    def test_atoi_returns_int(self):
        """
        atoi() should return int.

        atoi converts a string to integer.
        """
        source = '''
        #include <psion.h>
        void main() {
            int num;
            num = atoi("123");
        }
        '''
        asm = compile_source(source, use_stdlib=True)
        assert "ATOI" in asm.upper() or asm_contains_function(asm, "atoi")

    def test_print_is_void(self):
        """
        print() is void and should not be used in expressions.

        print() writes to the display and returns nothing.
        Using it in an expression should raise an error.
        """
        source = '''
        #include <psion.h>
        void main() {
            int x;
            x = print("hello");  /* ERROR: print returns void */
        }
        '''
        expect_compile_error(source, "void", use_stdlib=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
