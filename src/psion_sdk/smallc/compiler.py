"""
Small-C Compiler Main Module
============================

This module provides the main compiler interface for Small-C.
It orchestrates the complete compilation process:

    Source → Preprocess → Lex → Parse → Generate → Assembly

Usage
-----
Command line:
    $ pscc hello.c -o hello.asm

Programmatic:
    >>> from psion_sdk.smallc import compile_c
    >>> asm = compile_c('void main() { }')

The compiler produces HD6303 assembly suitable for the psasm assembler.
The generated assembly includes:
- Function code with proper calling conventions
- Global variable declarations
- String literal pool
- Runtime library requirements

Compilation Pipeline
--------------------
1. **Preprocessing**: Expand macros, process includes
2. **Lexical Analysis**: Convert source to tokens
3. **Parsing**: Build Abstract Syntax Tree (AST)
4. **Code Generation**: Convert AST to HD6303 assembly

Error Handling
--------------
The compiler collects multiple errors when possible, reporting
all issues found rather than stopping at the first error.

References
----------
- Small-C by Ron Cain (original 1980)
- HD6303 Technical Reference Manual
- Psion Organiser II Technical Manual
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from psion_sdk.smallc.preprocessor import Preprocessor
from psion_sdk.smallc.lexer import CLexer
from psion_sdk.smallc.parser import CParser
from psion_sdk.smallc.codegen import CodeGenerator
from psion_sdk.smallc.ast import ProgramNode
from psion_sdk.smallc.errors import (
    SmallCError,
    SmallCCompilationError,
    CErrorCollector,
)


@dataclass
class CompilerOptions:
    """
    Compiler configuration options.

    Attributes:
        include_paths: Directories to search for include files
        output_comments: Include C source as comments in assembly
        optimize: Enable basic optimizations (future)
        debug_info: Include debug information (future)
        target_model: Target Psion model (CM, XP, LA, LZ, LZ64).
                     None means use pragma or default (XP).
        emit_runtime: If True (default), emit runtime library includes and entry
                     point. Set to False for "library mode" when compiling helper
                     files that will be linked with a main file.

                     When emit_runtime=False:
                     - No INCLUDE "runtime.inc" (or other runtime libs)
                     - No _entry: entry point that calls main
                     - psion.inc IS still included (constants are idempotent)
                     - Functions, globals, and strings are still emitted

                     This is used by psbuild when compiling multiple C files:
                     only the file containing main() should have emit_runtime=True.
    """
    include_paths: list[str] = None
    output_comments: bool = True
    optimize: bool = False
    debug_info: bool = False
    target_model: Optional[str] = None  # None = allow pragma to override, default is XP
    emit_runtime: bool = True  # False = library mode (no runtime includes, no entry point)

    def __post_init__(self):
        if self.include_paths is None:
            self.include_paths = ["."]


class SmallCCompiler:
    """
    Small-C compiler for the Psion Organiser II.

    This class provides the main interface for compiling Small-C
    source code to HD6303 assembly.

    Example:
        compiler = SmallCCompiler()
        result = compiler.compile_file("hello.c")
        print(result.assembly)

    Attributes:
        options: Compiler configuration options
    """

    def __init__(self, options: Optional[CompilerOptions] = None):
        """
        Initialize the compiler.

        Args:
            options: Compiler configuration (uses defaults if None)
        """
        self.options = options or CompilerOptions()
        self._errors = CErrorCollector()

    def compile_source(self, source: str, filename: str = "<input>") -> "CompilerResult":
        """
        Compile C source code to assembly.

        Args:
            source: C source code string
            filename: Source filename for error messages

        Returns:
            CompilerResult containing assembly output and diagnostics

        Raises:
            SmallCError: If compilation fails
        """
        self._errors.clear()
        result = CompilerResult(filename=filename)

        try:
            # Stage 1: Preprocessing
            # Returns preprocessed source, effective target model, and optional library flags
            preprocessed, effective_model, has_float_support, has_stdio_support, has_db_support = self._preprocess(source, filename)
            result.preprocessed_source = preprocessed
            result.target_model = effective_model

            # Stage 2: Lexical analysis
            tokens = self._lex(preprocessed, filename)
            result.token_count = len(tokens)

            # Stage 3: Parsing
            ast = self._parse(tokens, filename, preprocessed.splitlines())
            result.ast = ast

            # Stage 4: Code generation (with target model and optional library awareness)
            # emit_runtime=False enables "library mode" for multi-file linking
            assembly = self._generate(
                ast, effective_model, has_float_support, has_stdio_support,
                has_db_support, emit_runtime=self.options.emit_runtime
            )
            result.assembly = assembly
            result.success = True

        except SmallCCompilationError:
            # Aggregate error from parser - already formatted, just re-raise
            raise
        except SmallCError as e:
            # Individual error - add to collector for later reporting
            self._errors.add(e)
            result.success = False

        result.errors = list(self._errors.errors)
        result.warnings = list(self._errors.warnings)

        if self._errors.has_errors():
            raise SmallCCompilationError(self._errors.report())

        return result

    def compile_file(self, filepath: str) -> "CompilerResult":
        """
        Compile a C source file to assembly.

        Args:
            filepath: Path to the C source file

        Returns:
            CompilerResult containing assembly output and diagnostics

        Raises:
            SmallCError: If compilation fails
            FileNotFoundError: If source file not found
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {filepath}")

        source = path.read_text(encoding='utf-8')

        # Add source directory to include paths
        source_dir = str(path.parent)
        if source_dir not in self.options.include_paths:
            self.options.include_paths.insert(0, source_dir)

        return self.compile_source(source, filepath)

    def _preprocess(self, source: str, filename: str) -> tuple[str, str, bool, bool, bool]:
        """
        Run the preprocessor on source code.

        Args:
            source: C source code
            filename: Source filename

        Returns:
            Tuple of (preprocessed_source, effective_model, has_float_support,
                      has_stdio_support, has_db_support)
        """
        preprocessor = Preprocessor(
            source,
            filename,
            self.options.include_paths,
            target_model=self.options.target_model,
        )
        preprocessed = preprocessor.process()
        effective_model = preprocessor.get_effective_model()
        has_float_support = preprocessor.has_float_support()
        has_stdio_support = preprocessor.has_stdio_support()
        has_db_support = preprocessor.has_db_support()
        return preprocessed, effective_model, has_float_support, has_stdio_support, has_db_support

    def _lex(self, source: str, filename: str) -> list:
        """Tokenize preprocessed source."""
        lexer = CLexer(source, filename)
        return list(lexer.tokenize())

    def _parse(self, tokens: list, filename: str, source_lines: list[str]) -> ProgramNode:
        """Parse tokens into AST."""
        parser = CParser(tokens, filename, source_lines)
        return parser.parse()

    def _generate(
        self, ast: ProgramNode, target_model: str = "XP",
        has_float_support: bool = False, has_stdio_support: bool = False,
        has_db_support: bool = False, emit_runtime: bool = True
    ) -> str:
        """
        Generate assembly from AST.

        Args:
            ast: The parsed AST
            target_model: Target Psion model (CM, XP, LA, LZ, LZ64)
            has_float_support: Whether float.h was included
            has_stdio_support: Whether stdio.h was included
            has_db_support: Whether db.h was included
            emit_runtime: Whether to emit runtime includes and entry point.
                         Set False for library mode (multi-file linking).

        Returns:
            Generated HD6303 assembly code
        """
        generator = CodeGenerator(
            target_model=target_model,
            has_float_support=has_float_support,
            has_stdio_support=has_stdio_support,
            has_db_support=has_db_support,
            emit_runtime=emit_runtime
        )
        return generator.generate(ast)


@dataclass
class CompilerResult:
    """
    Result of a compilation.

    Attributes:
        filename: Source filename
        success: True if compilation succeeded
        assembly: Generated assembly code (if successful)
        preprocessed_source: Source after preprocessing
        ast: Abstract syntax tree (if parsing succeeded)
        token_count: Number of tokens lexed
        target_model: Effective target Psion model (CM, XP, LA, LZ, LZ64)
        errors: List of error messages
        warnings: List of warning messages
    """
    filename: str = ""
    success: bool = False
    assembly: str = ""
    preprocessed_source: str = ""
    ast: Optional[ProgramNode] = None
    token_count: int = 0
    target_model: str = ""  # Will be set during compilation
    errors: list = None
    warnings: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


# =============================================================================
# Utility Functions
# =============================================================================

def source_has_main(source: str, filename: str = "<input>",
                    include_paths: Optional[list[str]] = None) -> bool:
    """
    Check if a C source file contains a main() function definition.

    This is a lightweight check used by psbuild to determine which file
    in a multi-file project should be compiled with the runtime.

    The check uses the full compiler pipeline (preprocess → lex → parse)
    to ensure accurate detection even with macros, conditional compilation,
    and includes. While slightly slower than a regex, it's 100% accurate.

    Args:
        source: C source code string
        filename: Source filename for error messages
        include_paths: Directories to search for includes

    Returns:
        True if the source contains a `void main()` function definition,
        False otherwise.

    Raises:
        SmallCError: If the source has syntax errors (can't parse)

    Note:
        This function will raise errors for invalid C code. Callers should
        handle SmallCError if the source may be invalid.

    Example:
        >>> source = 'void main() { }'
        >>> source_has_main(source)
        True
        >>> source = 'int helper() { return 42; }'
        >>> source_has_main(source)
        False
    """
    from psion_sdk.smallc.ast import FunctionNode

    # Use the compiler to parse the source
    options = CompilerOptions(
        include_paths=include_paths or ["."],
        emit_runtime=True,  # Doesn't matter for parsing
    )
    compiler = SmallCCompiler(options)

    # Run preprocessing and parsing only (no code generation)
    preprocessor = Preprocessor(
        source,
        filename,
        options.include_paths,
        target_model=None,
    )
    preprocessed = preprocessor.process()

    lexer = CLexer(preprocessed, filename)
    tokens = list(lexer.tokenize())

    parser = CParser(tokens, filename, preprocessed.splitlines())
    ast = parser.parse()

    # Check for main() function definition
    for decl in ast.declarations:
        if isinstance(decl, FunctionNode):
            if decl.name == "main" and not decl.is_forward_decl and not decl.is_opl:
                return True

    return False


def file_has_main(filepath: str) -> bool:
    """
    Check if a C source file contains a main() function definition.

    Convenience wrapper around source_has_main() that reads from a file.

    Args:
        filepath: Path to the C source file

    Returns:
        True if the file contains a main() function definition.

    Raises:
        FileNotFoundError: If the file doesn't exist
        SmallCError: If the source has syntax errors

    Example:
        >>> file_has_main("hello.c")
        True
        >>> file_has_main("helper.c")
        False
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {filepath}")

    source = path.read_text(encoding='utf-8')

    # Add source directory to include paths
    include_paths = [str(path.parent)]

    # Also add SDK include directory if available
    sdk_include = Path(__file__).parent.parent.parent.parent / "include"
    if sdk_include.exists():
        include_paths.append(str(sdk_include))

    return source_has_main(source, filepath, include_paths)


# =============================================================================
# Convenience Functions
# =============================================================================

def compile_c(
    source: str,
    filename: str = "<input>",
    include_paths: Optional[list[str]] = None,
) -> str:
    """
    Compile C source code to HD6303 assembly.

    This is the primary high-level interface for compiling Small-C.

    Args:
        source: C source code
        filename: Source filename for error messages
        include_paths: Directories to search for includes

    Returns:
        Generated HD6303 assembly code

    Raises:
        SmallCError: If compilation fails

    Example:
        >>> source = '''
        ... #include <psion.h>
        ... void main() {
        ...     cls();
        ...     print("Hello!");
        ...     getkey();
        ... }
        ... '''
        >>> asm = compile_c(source)
        >>> print(asm)
    """
    options = CompilerOptions(include_paths=include_paths or ["."])
    compiler = SmallCCompiler(options)
    result = compiler.compile_source(source, filename)
    return result.assembly


def compile_file(
    filepath: str,
    output_path: Optional[str] = None,
    include_paths: Optional[list[str]] = None,
) -> str:
    """
    Compile a C source file to HD6303 assembly.

    Args:
        filepath: Path to C source file
        output_path: Optional path to write assembly output
        include_paths: Directories to search for includes

    Returns:
        Generated HD6303 assembly code

    Raises:
        SmallCError: If compilation fails
        FileNotFoundError: If source file not found

    Example:
        >>> asm = compile_file("hello.c", "hello.asm")
    """
    options = CompilerOptions(include_paths=include_paths or ["."])
    compiler = SmallCCompiler(options)
    result = compiler.compile_file(filepath)

    if output_path:
        Path(output_path).write_text(result.assembly, encoding='utf-8')

    return result.assembly
