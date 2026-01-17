"""
Small-C Compiler Test Suite
===========================

This module provides comprehensive tests for the Small-C compiler,
covering the lexer, parser, code generator, and full compilation
pipeline.

Test Organization
-----------------
- TestLexer: Token generation tests
- TestParser: AST generation tests
- TestCodeGen: Assembly output tests
- TestPreprocessor: Macro and include tests
- TestIntegration: End-to-end compilation tests
"""

import pytest
from psion_sdk.smallc.lexer import CLexer, CTokenType, CToken
from psion_sdk.smallc.parser import CParser, parse_source
from psion_sdk.smallc.codegen import CodeGenerator
from psion_sdk.smallc.preprocessor import Preprocessor, preprocess
from psion_sdk.smallc.compiler import SmallCCompiler, compile_c, CompilerOptions
from psion_sdk.smallc.ast import (
    ProgramNode,
    FunctionNode,
    VariableDeclaration,
    BinaryExpression,
    NumberLiteral,
    IdentifierExpression,
    CallExpression,
    BinaryOperator,
    ASTPrinter,
)
from psion_sdk.smallc.types import CType, BaseType, TYPE_INT, TYPE_CHAR
from psion_sdk.smallc.errors import CSyntaxError, CPreprocessorError, SmallCError


# =============================================================================
# Lexer Tests
# =============================================================================

class TestLexer:
    """Tests for the Small-C lexer (tokenizer)."""

    def test_empty_source(self):
        """Empty source should produce only EOF token."""
        lexer = CLexer("", "test.c")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 1
        assert tokens[0].type == CTokenType.EOF

    def test_whitespace_only(self):
        """Whitespace-only source should produce only EOF token."""
        lexer = CLexer("   \n\t  \n  ", "test.c")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 1
        assert tokens[0].type == CTokenType.EOF

    def test_single_line_comment(self):
        """Single-line comments should be skipped."""
        lexer = CLexer("// comment\n42", "test.c")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 2
        assert tokens[0].type == CTokenType.NUMBER
        assert tokens[0].value == 42

    def test_multi_line_comment(self):
        """Multi-line comments should be skipped."""
        lexer = CLexer("/* comment\n\nstuff */42", "test.c")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 2
        assert tokens[0].type == CTokenType.NUMBER
        assert tokens[0].value == 42

    def test_keywords(self):
        """Keywords should be tokenized correctly."""
        keywords = [
            ("int", CTokenType.INT),
            ("char", CTokenType.CHAR),
            ("void", CTokenType.VOID),
            ("if", CTokenType.IF),
            ("else", CTokenType.ELSE),
            ("while", CTokenType.WHILE),
            ("for", CTokenType.FOR),
            ("return", CTokenType.RETURN),
            ("break", CTokenType.BREAK),
            ("continue", CTokenType.CONTINUE),
            ("unsigned", CTokenType.UNSIGNED),
        ]
        for text, expected_type in keywords:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == expected_type
            assert tokens[0].value == text

    def test_identifiers(self):
        """Identifiers should be tokenized correctly."""
        identifiers = ["main", "foo", "_bar", "test123", "_123_abc"]
        for ident in identifiers:
            lexer = CLexer(ident, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.IDENTIFIER
            assert tokens[0].value == ident

    def test_decimal_numbers(self):
        """Decimal numbers should be tokenized correctly."""
        numbers = [("0", 0), ("1", 1), ("42", 42), ("65535", 65535)]
        for text, expected in numbers:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.NUMBER
            assert tokens[0].value == expected

    def test_hex_numbers(self):
        """Hexadecimal numbers should be tokenized correctly."""
        numbers = [("0x0", 0), ("0xFF", 255), ("0x7F", 127), ("0xABCD", 0xABCD)]
        for text, expected in numbers:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.NUMBER
            assert tokens[0].value == expected

    def test_binary_numbers(self):
        """Binary numbers should be tokenized correctly."""
        numbers = [("0b0", 0), ("0b1", 1), ("0b1010", 10), ("0b11111111", 255)]
        for text, expected in numbers:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.NUMBER
            assert tokens[0].value == expected

    def test_string_literal(self):
        """String literals should be tokenized correctly."""
        lexer = CLexer('"hello"', "test.c")
        tokens = list(lexer.tokenize())
        assert tokens[0].type == CTokenType.STRING
        assert tokens[0].value == "hello"

    def test_string_escape_sequences(self):
        """Escape sequences in strings should be processed."""
        cases = [
            ('"\\n"', "\n"),
            ('"\\t"', "\t"),
            ('"\\r"', "\r"),
            ('"\\\\"', "\\"),
            ('"\\""', '"'),
            ('"\\x41"', "A"),
        ]
        for text, expected in cases:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.STRING
            assert tokens[0].value == expected

    def test_char_literal(self):
        """Character literals should return their ASCII value."""
        cases = [
            ("'A'", 65),
            ("'0'", 48),
            ("' '", 32),
            ("'\\n'", 10),
            ("'\\t'", 9),
        ]
        for text, expected in cases:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == CTokenType.CHAR_LITERAL
            assert tokens[0].value == expected

    def test_operators(self):
        """Operators should be tokenized correctly."""
        operators = [
            ("+", CTokenType.PLUS),
            ("-", CTokenType.MINUS),
            ("*", CTokenType.STAR),
            ("/", CTokenType.SLASH),
            ("%", CTokenType.PERCENT),
            ("==", CTokenType.EQ),
            ("!=", CTokenType.NE),
            ("<", CTokenType.LT),
            (">", CTokenType.GT),
            ("<=", CTokenType.LE),
            (">=", CTokenType.GE),
            ("&&", CTokenType.AND),
            ("||", CTokenType.OR),
            ("!", CTokenType.NOT),
            ("&", CTokenType.AMPERSAND),
            ("|", CTokenType.PIPE),
            ("^", CTokenType.CARET),
            ("~", CTokenType.TILDE),
            ("<<", CTokenType.LSHIFT),
            (">>", CTokenType.RSHIFT),
            ("++", CTokenType.INCREMENT),
            ("--", CTokenType.DECREMENT),
            ("=", CTokenType.ASSIGN),
            ("+=", CTokenType.PLUS_ASSIGN),
            ("-=", CTokenType.MINUS_ASSIGN),
        ]
        for text, expected_type in operators:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == expected_type

    def test_delimiters(self):
        """Delimiters should be tokenized correctly."""
        delimiters = [
            ("(", CTokenType.LPAREN),
            (")", CTokenType.RPAREN),
            ("{", CTokenType.LBRACE),
            ("}", CTokenType.RBRACE),
            ("[", CTokenType.LBRACKET),
            ("]", CTokenType.RBRACKET),
            (";", CTokenType.SEMICOLON),
            (",", CTokenType.COMMA),
        ]
        for text, expected_type in delimiters:
            lexer = CLexer(text, "test.c")
            tokens = list(lexer.tokenize())
            assert tokens[0].type == expected_type

    def test_complete_function(self):
        """Complete function should tokenize correctly."""
        source = "int main() { return 42; }"
        lexer = CLexer(source, "test.c")
        tokens = list(lexer.tokenize())

        expected = [
            CTokenType.INT,
            CTokenType.IDENTIFIER,
            CTokenType.LPAREN,
            CTokenType.RPAREN,
            CTokenType.LBRACE,
            CTokenType.RETURN,
            CTokenType.NUMBER,
            CTokenType.SEMICOLON,
            CTokenType.RBRACE,
            CTokenType.EOF,
        ]
        assert [t.type for t in tokens] == expected

    def test_token_location(self):
        """Tokens should have correct line and column."""
        source = "int\nmain"
        lexer = CLexer(source, "test.c")
        tokens = list(lexer.tokenize())

        assert tokens[0].line == 1
        assert tokens[0].column == 1
        assert tokens[1].line == 2
        assert tokens[1].column == 1


# =============================================================================
# Parser Tests
# =============================================================================

class TestParser:
    """Tests for the Small-C parser."""

    def test_empty_program(self):
        """Empty program should parse to empty ProgramNode."""
        ast = parse_source("")
        assert isinstance(ast, ProgramNode)
        assert len(ast.declarations) == 0

    def test_simple_function(self):
        """Simple function should parse correctly."""
        source = "void main() { }"
        ast = parse_source(source)

        assert len(ast.declarations) == 1
        func = ast.declarations[0]
        assert isinstance(func, FunctionNode)
        assert func.name == "main"
        assert func.return_type.base_type == BaseType.VOID

    def test_function_with_return(self):
        """Function with return statement should parse."""
        source = "int main() { return 42; }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert func.name == "main"
        assert func.return_type.base_type == BaseType.INT
        assert len(func.body.statements) == 1

    def test_function_with_parameters(self):
        """Function with parameters should parse correctly."""
        source = "int add(int a, int b) { return a + b; }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert func.name == "add"
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "a"
        assert func.parameters[1].name == "b"

    def test_global_variable(self):
        """Global variable declaration should parse."""
        source = "int counter;"
        ast = parse_source(source)

        assert len(ast.declarations) == 1
        var = ast.declarations[0]
        assert isinstance(var, VariableDeclaration)
        assert var.name == "counter"
        assert var.is_global

    def test_local_variable(self):
        """Local variable in function should parse."""
        source = "void main() { int x; }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert len(func.body.declarations) == 1
        var = func.body.declarations[0]
        assert var.name == "x"
        assert not var.is_global

    def test_if_statement(self):
        """If statement should parse correctly."""
        source = "void main() { if (x) { y = 1; } }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert len(func.body.statements) == 1

    def test_if_else_statement(self):
        """If-else statement should parse correctly."""
        source = "void main() { if (x) { y = 1; } else { y = 2; } }"
        ast = parse_source(source)

        func = ast.declarations[0]
        stmt = func.body.statements[0]
        assert stmt.else_branch is not None

    def test_while_statement(self):
        """While loop should parse correctly."""
        source = "void main() { while (x > 0) { x = x - 1; } }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert len(func.body.statements) == 1

    def test_for_statement(self):
        """For loop should parse correctly."""
        source = "void main() { for (i = 0; i < 10; i = i + 1) { } }"
        ast = parse_source(source)

        func = ast.declarations[0]
        assert len(func.body.statements) == 1

    def test_binary_expression(self):
        """Binary expressions should parse with correct precedence."""
        source = "int main() { return 1 + 2 * 3; }"
        ast = parse_source(source)

        # 1 + (2 * 3) due to precedence
        func = ast.declarations[0]
        ret_stmt = func.body.statements[0]
        expr = ret_stmt.value

        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.ADD

    def test_comparison_operators(self):
        """Comparison operators should parse correctly."""
        source = "int main() { return a == b; }"
        ast = parse_source(source)

        func = ast.declarations[0]
        ret_stmt = func.body.statements[0]
        expr = ret_stmt.value

        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.EQUAL

    def test_function_call(self):
        """Function calls should parse correctly."""
        source = "void main() { foo(1, 2); }"
        ast = parse_source(source)

        func = ast.declarations[0]
        stmt = func.body.statements[0]
        call = stmt.expression

        assert isinstance(call, CallExpression)
        assert call.function_name == "foo"
        assert len(call.arguments) == 2

    def test_array_declaration(self):
        """Array declaration should parse correctly."""
        source = "int arr[10];"
        ast = parse_source(source)

        var = ast.declarations[0]
        assert var.var_type.array_size == 10

    def test_pointer_declaration(self):
        """Pointer declaration should parse correctly."""
        source = "int *ptr;"
        ast = parse_source(source)

        var = ast.declarations[0]
        assert var.var_type.is_pointer
        assert var.var_type.pointer_depth == 1

    def test_multi_variable_global_declaration(self):
        """Multi-variable global declaration should parse correctly."""
        source = "int a, b, c;"
        ast = parse_source(source)

        assert len(ast.declarations) == 3
        assert ast.declarations[0].name == "a"
        assert ast.declarations[1].name == "b"
        assert ast.declarations[2].name == "c"
        for decl in ast.declarations:
            assert decl.var_type.base_type == BaseType.INT
            assert decl.is_global

    def test_multi_variable_with_initializers(self):
        """Multi-variable declaration with initializers should parse."""
        source = "int x = 1, y = 2, z;"
        ast = parse_source(source)

        assert len(ast.declarations) == 3
        assert ast.declarations[0].name == "x"
        assert ast.declarations[0].initializer is not None
        assert ast.declarations[1].name == "y"
        assert ast.declarations[1].initializer is not None
        assert ast.declarations[2].name == "z"
        assert ast.declarations[2].initializer is None

    def test_multi_variable_mixed_types(self):
        """Multi-variable declaration with pointers and arrays."""
        source = "char *p, buf[10], c;"
        ast = parse_source(source)

        assert len(ast.declarations) == 3
        # *p - pointer
        assert ast.declarations[0].name == "p"
        assert ast.declarations[0].var_type.is_pointer
        # buf[10] - array
        assert ast.declarations[1].name == "buf"
        assert ast.declarations[1].var_type.is_array
        assert ast.declarations[1].var_type.array_size == 10
        # c - plain char
        assert ast.declarations[2].name == "c"
        assert not ast.declarations[2].var_type.is_pointer
        assert not ast.declarations[2].var_type.is_array

    def test_multi_variable_local_declaration(self):
        """Multi-variable local declaration should parse correctly."""
        source = """
        void main() {
            int a, b, c;
        }
        """
        ast = parse_source(source)

        func = ast.declarations[0]
        assert len(func.body.declarations) == 3
        assert func.body.declarations[0].name == "a"
        assert func.body.declarations[1].name == "b"
        assert func.body.declarations[2].name == "c"
        for decl in func.body.declarations:
            assert not decl.is_global


# =============================================================================
# Code Generator Tests
# =============================================================================

class TestCodeGen:
    """Tests for the HD6303 code generator."""

    def test_empty_function(self):
        """Empty function should generate valid assembly."""
        source = "void main() { }"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "_main:" in asm
        assert "RTS" in asm

    def test_return_constant(self):
        """Return with constant should generate LDD instruction."""
        source = "int main() { return 42; }"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "LDD" in asm
        assert "#42" in asm or "#$2A" in asm

    def test_global_variable(self):
        """Global variable should generate RMB directive."""
        source = "int counter;"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "_counter:" in asm
        assert "RMB" in asm

    def test_function_call(self):
        """Function call should generate JSR instruction."""
        source = "void main() { foo(); }"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "JSR" in asm
        assert "_foo" in asm

    def test_string_literal(self):
        """String literal should generate FCB/FCC directives."""
        source = 'void main() { char *s; s = "hello"; }'
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "FCC" in asm or "FCB" in asm

    def test_if_generates_branch(self):
        """If statement should generate conditional branch."""
        source = "int x; int y; void main() { if (x) { y = 1; } }"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "BEQ" in asm or "BNE" in asm

    def test_while_generates_loop(self):
        """While loop should generate loop structure."""
        source = "int x; void main() { while (x) { x = 0; } }"
        ast = parse_source(source)
        gen = CodeGenerator()
        asm = gen.generate(ast)

        assert "JMP" in asm  # Loop back (uses JMP for long jumps)


# =============================================================================
# Preprocessor Tests
# =============================================================================

class TestPreprocessor:
    """Tests for the C preprocessor."""

    def test_empty_source(self):
        """Empty source should preprocess to empty."""
        result = preprocess("")
        assert result == ""

    def test_simple_define(self):
        """Simple #define should expand correctly."""
        source = "#define MAX 100\nint x = MAX;"
        result = preprocess(source)
        assert "100" in result
        assert "MAX" not in result.split("\n")[-1]

    def test_function_macro(self):
        """Function-like macro should expand correctly."""
        source = "#define ADD(a,b) (a+b)\nint x = ADD(1,2);"
        result = preprocess(source)
        assert "(1+2)" in result

    def test_ifdef_defined(self):
        """#ifdef with defined macro should include content."""
        source = "#define FOO\n#ifdef FOO\nint x;\n#endif"
        result = preprocess(source)
        assert "int x;" in result

    def test_ifdef_undefined(self):
        """#ifdef with undefined macro should exclude content."""
        source = "#ifdef BAR\nint x;\n#endif\nint y;"
        result = preprocess(source)
        assert "int x;" not in result
        assert "int y;" in result

    def test_ifndef(self):
        """#ifndef should work correctly."""
        source = "#ifndef FOO\nint x;\n#endif"
        result = preprocess(source)
        assert "int x;" in result

    def test_else_branch(self):
        """#else should work correctly."""
        source = "#ifdef FOO\nint x;\n#else\nint y;\n#endif"
        result = preprocess(source)
        assert "int x;" not in result
        assert "int y;" in result

    def test_nested_conditionals(self):
        """Nested conditionals should work."""
        source = "#define A\n#ifdef A\n#ifdef B\n1\n#else\n2\n#endif\n#endif"
        result = preprocess(source)
        assert "2" in result
        assert "1" not in result

    def test_predefined_macros(self):
        """Predefined macros should be available."""
        source = "int x = __PSION__;"
        result = preprocess(source)
        assert "1" in result

    def test_undef(self):
        """#undef should remove macro definition."""
        source = "#define FOO 1\n#undef FOO\n#ifdef FOO\nyes\n#else\nno\n#endif"
        result = preprocess(source)
        assert "no" in result
        assert "yes" not in result


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end compilation tests."""

    def test_compile_empty(self):
        """Empty program should compile without error."""
        asm = compile_c("")
        assert "END" in asm

    def test_compile_hello_world(self):
        """Hello World should compile."""
        source = '''
        void main() {
            int x;
            x = 42;
        }
        '''
        asm = compile_c(source)
        assert "_main:" in asm
        assert "RTS" in asm

    def test_compile_with_function_call(self):
        """Program with function call should compile."""
        source = '''
        void foo() { }
        void main() {
            foo();
        }
        '''
        asm = compile_c(source)
        assert "_foo:" in asm
        assert "_main:" in asm
        assert "JSR" in asm

    def test_compile_arithmetic(self):
        """Arithmetic expressions should compile."""
        source = '''
        int add(int a, int b) {
            return a + b;
        }
        '''
        asm = compile_c(source)
        assert "_add:" in asm
        assert "ADDD" in asm

    def test_compile_control_flow(self):
        """Control flow should compile."""
        source = '''
        int abs(int x) {
            if (x < 0) {
                return 0 - x;
            }
            return x;
        }
        '''
        asm = compile_c(source)
        assert "_abs:" in asm

    def test_compile_loop(self):
        """Loop should compile."""
        source = '''
        int sum(int n) {
            int total;
            int i;
            total = 0;
            for (i = 1; i <= n; i = i + 1) {
                total = total + i;
            }
            return total;
        }
        '''
        asm = compile_c(source)
        assert "_sum:" in asm

    def test_compiler_class(self):
        """SmallCCompiler class should work correctly."""
        compiler = SmallCCompiler()
        result = compiler.compile_source("void main() { }", "test.c")

        assert result.success
        assert "_main:" in result.assembly

    def test_compiler_options(self):
        """Compiler options should be respected."""
        options = CompilerOptions(
            include_paths=["."],
            target_model="XP",
        )
        compiler = SmallCCompiler(options)
        result = compiler.compile_source("void main() { }", "test.c")

        assert result.success


# =============================================================================
# Type System Tests
# =============================================================================

class TestTypes:
    """Tests for the C type system."""

    def test_type_sizes(self):
        """Type sizes should be correct for HD6303."""
        assert TYPE_CHAR.size == 1
        assert TYPE_INT.size == 2

    def test_pointer_size(self):
        """Pointers should always be 2 bytes."""
        ptr_type = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
        assert ptr_type.size == 2

    def test_type_compatibility(self):
        """Type compatibility checks should work."""
        assert TYPE_INT.is_compatible_with(TYPE_INT)
        assert TYPE_INT.is_compatible_with(TYPE_CHAR)

    def test_pointer_to(self):
        """pointer_to should create correct type."""
        ptr = TYPE_INT.pointer_to()
        assert ptr.is_pointer
        assert ptr.pointer_depth == 1

    def test_dereference(self):
        """dereference should return pointed-to type."""
        ptr = TYPE_INT.pointer_to()
        deref = ptr.dereference()
        assert deref == TYPE_INT


# =============================================================================
# AST Printer Tests
# =============================================================================

class TestASTPrinter:
    """Tests for the AST printer."""

    def test_print_simple_program(self):
        """AST printer should produce output."""
        source = "void main() { return; }"
        ast = parse_source(source)
        printer = ASTPrinter()
        output = printer.print(ast)

        assert "Program" in output
        assert "Function" in output
        assert "main" in output


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrors:
    """Tests for error handling."""

    def test_unterminated_string(self):
        """Unterminated string should raise error."""
        lexer = CLexer('"hello', "test.c")
        with pytest.raises(CSyntaxError):
            list(lexer.tokenize())

    def test_invalid_character(self):
        """Invalid character should raise error."""
        lexer = CLexer("@invalid", "test.c")
        with pytest.raises(CSyntaxError):
            list(lexer.tokenize())

    def test_unterminated_comment(self):
        """Unterminated multi-line comment should raise error."""
        lexer = CLexer("/* comment", "test.c")
        with pytest.raises(CSyntaxError):
            list(lexer.tokenize())

    def test_missing_semicolon(self):
        """Missing semicolon should raise error."""
        with pytest.raises((CSyntaxError, SmallCError)):
            parse_source("int x")

    def test_unterminated_if(self):
        """Unterminated #if should raise error."""
        with pytest.raises(CPreprocessorError):
            preprocess("#ifdef FOO\nint x;")


# =============================================================================
# Model Support Tests
# =============================================================================

class TestModelSupport:
    """Tests for target model support in Small-C compiler."""

    def test_default_model_is_xp(self):
        """Default target model should be XP."""
        pp = Preprocessor("int x;", "test.c")
        pp.process()
        assert pp.get_effective_model() == "XP"
        assert "__PSION_XP__" in pp._macros
        assert "__PSION_2LINE__" in pp._macros
        assert pp._macros["DISP_ROWS"].body == "2"
        assert pp._macros["DISP_COLS"].body == "16"

    def test_pragma_psion_model_lz(self):
        """#pragma psion model LZ should set model to LZ."""
        source = "#pragma psion model LZ\nint x;"
        pp = Preprocessor(source, "test.c")
        pp.process()
        assert pp.get_detected_model() == "LZ"
        assert pp.get_effective_model() == "LZ"
        assert "__PSION_LZ__" in pp._macros
        assert "__PSION_4LINE__" in pp._macros
        assert pp._macros["DISP_ROWS"].body == "4"
        assert pp._macros["DISP_COLS"].body == "20"

    def test_pragma_psion_model_cm(self):
        """#pragma psion model CM should set model to CM."""
        source = "#pragma psion model CM\nint x;"
        pp = Preprocessor(source, "test.c")
        pp.process()
        assert pp.get_detected_model() == "CM"
        assert "__PSION_CM__" in pp._macros
        assert "__PSION_2LINE__" in pp._macros

    def test_pragma_psion_model_lz64(self):
        """#pragma psion model LZ64 should set model to LZ64."""
        source = "#pragma psion model LZ64\nint x;"
        pp = Preprocessor(source, "test.c")
        pp.process()
        assert pp.get_detected_model() == "LZ64"
        assert "__PSION_LZ64__" in pp._macros
        assert "__PSION_4LINE__" in pp._macros

    def test_cli_overrides_pragma(self):
        """CLI model should override #pragma psion model."""
        source = "#pragma psion model LZ\nint x;"
        pp = Preprocessor(source, "test.c", target_model="CM")
        pp.process()
        # Pragma was detected but CLI takes precedence
        assert pp.get_detected_model() == "LZ"
        assert pp.get_effective_model() == "CM"
        # Macros should reflect CLI model (CM), not pragma (LZ)
        assert "__PSION_CM__" in pp._macros
        assert "__PSION_2LINE__" in pp._macros

    def test_invalid_model_raises_error(self):
        """Invalid model name in pragma should raise error."""
        source = "#pragma psion model INVALID\nint x;"
        pp = Preprocessor(source, "test.c")
        with pytest.raises(CPreprocessorError):
            pp.process()

    def test_model_case_insensitive(self):
        """Model name should be case-insensitive."""
        source = "#pragma psion model lz\nint x;"
        pp = Preprocessor(source, "test.c")
        pp.process()
        assert pp.get_detected_model() == "LZ"

    def test_conditional_compilation_with_model(self):
        """Conditional compilation should work with model macros."""
        source = """
#pragma psion model LZ
#ifdef __PSION_4LINE__
int rows = 4;
#else
int rows = 2;
#endif
"""
        pp = Preprocessor(source, "test.c")
        result = pp.process()
        assert "int rows = 4;" in result
        assert "int rows = 2;" not in result

    def test_conditional_compilation_with_2line_model(self):
        """Conditional compilation should work with 2-line model macros."""
        source = """
#pragma psion model XP
#ifdef __PSION_4LINE__
int rows = 4;
#else
int rows = 2;
#endif
"""
        pp = Preprocessor(source, "test.c")
        result = pp.process()
        assert "int rows = 2;" in result
        assert "int rows = 4;" not in result

    def test_disp_rows_in_expression(self):
        """DISP_ROWS macro should work in expressions."""
        source = """
#pragma psion model LZ
int rows = DISP_ROWS;
"""
        pp = Preprocessor(source, "test.c")
        result = pp.process()
        assert "int rows = 4;" in result

    def test_compiler_passes_model_to_codegen(self):
        """Compiler should pass target model to code generator."""
        source = "#pragma psion model LZ\nint main() { return 0; }"
        options = CompilerOptions()
        compiler = SmallCCompiler(options)
        result = compiler.compile_source(source, "test.c")
        assert result.target_model == "LZ"
        # Check that generated assembly contains model info
        assert "; Target Model: LZ" in result.assembly
        assert ".MODEL  LZ" in result.assembly

    def test_compiler_cli_overrides_pragma(self):
        """Compiler CLI model should override pragma."""
        source = "#pragma psion model LZ\nint main() { return 0; }"
        options = CompilerOptions(target_model="CM")
        compiler = SmallCCompiler(options)
        result = compiler.compile_source(source, "test.c")
        assert result.target_model == "CM"
        assert "; Target Model: CM" in result.assembly
