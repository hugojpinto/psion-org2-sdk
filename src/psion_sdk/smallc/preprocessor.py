"""
Small-C Preprocessor
====================

This module implements a C preprocessor for Small-C source code.
It handles:
- #define macros (simple and function-like)
- #include directives
- Conditional compilation (#ifdef, #ifndef, #if, #else, #endif)
- #pragma directives (especially #pragma psion model XXX)

The preprocessor runs before lexing and produces expanded source code
that can be tokenized by the lexer.

Supported Directives
--------------------
#define NAME value          - Simple macro
#define NAME(args) body     - Function-like macro
#undef NAME                 - Undefine macro
#include "filename"         - Include local file
#include <filename>         - Include from system path
#ifdef NAME                 - If macro defined
#ifndef NAME                - If macro not defined
#if expression              - Conditional (constants only)
#elif expression            - Else if
#else                       - Else branch
#endif                      - End conditional
#pragma psion model XXX     - Set target Psion model (CM, XP, LA, LZ, LZ64)

Predefined Macros
-----------------
__PSION__       - Always defined (value 1)
__SMALLC__      - Always defined (value 1)
__LINE__        - Current line number
__FILE__        - Current filename

Model-Specific Macros (defined based on target model)
-----------------------------------------------------
__PSION_CM__    - Defined (value 1) when targeting CM model
__PSION_XP__    - Defined (value 1) when targeting XP model
__PSION_LA__    - Defined (value 1) when targeting LA model
__PSION_LZ__    - Defined (value 1) when targeting LZ model
__PSION_LZ64__  - Defined (value 1) when targeting LZ64 model
__PSION_2LINE__ - Defined (value 1) when targeting 2-line display models (CM, XP)
__PSION_4LINE__ - Defined (value 1) when targeting 4-line display models (LA, LZ, LZ64)
DISP_ROWS       - Display rows for target model (2 or 4)
DISP_COLS       - Display columns for target model (16 or 20)

Example
-------
>>> from psion_sdk.smallc.preprocessor import Preprocessor
>>> source = '''
... #pragma psion model LZ
... #define MAX 100
... int arr[MAX];
... '''
>>> pp = Preprocessor(source, "test.c")
>>> expanded = pp.process()
>>> print(expanded)
int arr[100];
>>> pp.get_detected_model()
'LZ'
"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from psion_sdk.errors import SourceLocation
from psion_sdk.smallc.errors import (
    CPreprocessorError,
    CIncludeError,
    MacroExpansionError,
)


@dataclass
class Macro:
    """
    Represents a preprocessor macro.

    Attributes:
        name: Macro name
        body: Replacement text
        parameters: Parameter names for function-like macros (None for simple)
        location: Where the macro was defined
    """
    name: str
    body: str
    parameters: Optional[list[str]] = None
    location: Optional[SourceLocation] = None

    @property
    def is_function_like(self) -> bool:
        """Return True if this is a function-like macro."""
        return self.parameters is not None


class Preprocessor:
    """
    C preprocessor for Small-C source code.

    Processes #define, #include, and conditional compilation directives.
    The preprocessor operates line-by-line, expanding macros and
    processing directives to produce expanded source code.

    Attributes:
        source: Original source code
        filename: Source filename for error reporting
        include_paths: Directories to search for include files
    """

    # Pattern for identifying preprocessor directives
    DIRECTIVE_PATTERN = re.compile(r'^\s*#\s*(\w+)')

    # Pattern for #define with optional parameters
    DEFINE_PATTERN = re.compile(
        r'^\s*#\s*define\s+(\w+)(?:\(([^)]*)\))?\s*(.*?)$'
    )

    # Pattern for #include
    INCLUDE_PATTERN = re.compile(
        r'^\s*#\s*include\s+([<"])([^>"]+)[>"]'
    )

    # Pattern for identifier (for macro expansion)
    IDENTIFIER_PATTERN = re.compile(r'\b([A-Za-z_]\w*)\b')

    # =========================================================================
    # Target Model Constants
    # =========================================================================
    # Valid Psion model names (uppercase)
    # See dev_docs/TARGET_MODELS.md for full documentation.
    #
    # Categories:
    #   2-line displays: CM, XP, LA (16x2 characters)
    #   4-line displays: LZ, LZ64 (20x4 characters)
    #   Cross-platform:  PORTABLE (runs on any model)
    # =========================================================================
    VALID_MODELS = frozenset({"CM", "XP", "LA", "LZ", "LZ64", "PORTABLE"})

    # Model display characteristics: model -> (rows, columns)
    # Note: LA is 2-line despite being in the "L" series
    MODEL_DISPLAY = {
        "CM": (2, 16),
        "XP": (2, 16),
        "LA": (2, 16),      # LA is 2-line, NOT 4-line
        "LZ": (4, 20),
        "LZ64": (4, 20),
        "PORTABLE": (2, 16),  # Default to 2-line dimensions for PORTABLE
    }

    # Pattern for #pragma psion model directive
    PRAGMA_PSION_MODEL_PATTERN = re.compile(
        r'^\s*#\s*pragma\s+psion\s+model\s+(\w+)\s*$', re.IGNORECASE
    )

    def __init__(
        self,
        source: str,
        filename: str = "<input>",
        include_paths: Optional[list[str]] = None,
        target_model: Optional[str] = None,
    ):
        """
        Initialize the preprocessor.

        Args:
            source: Source code to preprocess
            filename: Source filename for error reporting
            include_paths: Directories to search for includes
            target_model: Target Psion model (CM, XP, LA, LZ, LZ64).
                         If None, uses "LZ" as default. Can be overridden
                         by #pragma psion model directive in source code.
        """
        self.source = source
        self.filename = filename
        self.include_paths = include_paths or ["."]

        # Target model handling:
        # - _initial_model: Model specified via constructor (from CLI)
        # - _detected_model: Model found via #pragma in source
        # - _model_from_cli: True if constructor model was explicitly set
        self._initial_model = (target_model or "XP").upper()
        self._detected_model: Optional[str] = None
        self._model_from_cli = target_model is not None

        # Validate initial model
        if self._initial_model not in self.VALID_MODELS:
            # Fall back to XP for invalid models (broad 2-line compatibility)
            self._initial_model = "XP"

        # Macro table
        self._macros: dict[str, Macro] = {}

        # Conditional compilation stack
        # Each entry is (skip_this_branch, any_branch_taken)
        self._condition_stack: list[tuple[bool, bool]] = []

        # Include stack to detect circular includes
        self._include_stack: list[str] = []

        # Set of included file basenames (e.g., "float.h", "psion.h")
        self._included_files: set[str] = set()

        # Output lines
        self._output: list[str] = []

        # Current state
        self._current_line = 0
        self._current_file = filename

        # Initialize predefined macros (including model-specific ones)
        self._init_predefined_macros()

    def _init_predefined_macros(self) -> None:
        """
        Initialize predefined macros.

        This sets up:
        - __PSION__ and __SMALLC__ (always defined as 1)
        - Model-specific macros based on initial target model
        - Display dimension constants (DISP_ROWS, DISP_COLS)
        - __LINE__ and __FILE__ are handled specially during expansion
        """
        self._macros["__PSION__"] = Macro("__PSION__", "1")
        self._macros["__SMALLC__"] = Macro("__SMALLC__", "1")

        # Set up model-specific macros based on initial model
        self._setup_model_macros(self._initial_model)

    def _setup_model_macros(self, model: str) -> None:
        """
        Set up model-specific predefined macros.

        This clears any existing model macros and defines new ones
        based on the specified model.

        Args:
            model: Target model name (CM, XP, LA, LZ, LZ64)
        """
        # First, remove any existing model-specific macros
        model_macro_names = [
            "__PSION_CM__", "__PSION_XP__", "__PSION_LA__",
            "__PSION_LZ__", "__PSION_LZ64__",
            "__PSION_2LINE__", "__PSION_4LINE__",
            "DISP_ROWS", "DISP_COLS",
        ]
        for name in model_macro_names:
            self._macros.pop(name, None)

        # Define the active model macro
        model_upper = model.upper()
        self._macros[f"__PSION_{model_upper}__"] = Macro(f"__PSION_{model_upper}__", "1")

        # Get display characteristics
        rows, cols = self.MODEL_DISPLAY.get(model_upper, (4, 20))

        # Define display type macro
        if rows == 2:
            self._macros["__PSION_2LINE__"] = Macro("__PSION_2LINE__", "1")
        else:
            self._macros["__PSION_4LINE__"] = Macro("__PSION_4LINE__", "1")

        # Define display dimension constants
        self._macros["DISP_ROWS"] = Macro("DISP_ROWS", str(rows))
        self._macros["DISP_COLS"] = Macro("DISP_COLS", str(cols))

    def process(self) -> str:
        """
        Process the source code and return expanded result.

        Returns:
            Preprocessed source code with all macros expanded
            and directives processed.

        Raises:
            CPreprocessorError: If preprocessing fails
        """
        self._output = []
        self._include_stack = [self.filename]

        lines = self.source.splitlines()

        for i, line in enumerate(lines):
            self._current_line = i + 1
            self._process_line(line)

        # Check for unclosed conditionals
        if self._condition_stack:
            raise CPreprocessorError(
                "unterminated #if/#ifdef/#ifndef",
                SourceLocation(self.filename, self._current_line, 1),
            )

        return "\n".join(self._output)

    def _process_line(self, line: str) -> None:
        """Process a single line of source code."""
        # Check for preprocessor directive
        match = self.DIRECTIVE_PATTERN.match(line)
        if match:
            directive = match.group(1).lower()
            self._process_directive(directive, line)
            return

        # If we're skipping due to conditional compilation, don't output
        if self._should_skip():
            return

        # Expand macros in the line
        expanded = self._expand_macros(line)
        self._output.append(expanded)

    def _should_skip(self) -> bool:
        """Check if we should skip lines due to conditional compilation."""
        for skip, _ in self._condition_stack:
            if skip:
                return True
        return False

    def _process_directive(self, directive: str, line: str) -> None:
        """Process a preprocessor directive."""
        # Conditional directives are always processed
        if directive in ("ifdef", "ifndef", "if", "elif", "else", "endif"):
            self._process_conditional(directive, line)
            return

        # Other directives only processed if not skipping
        if self._should_skip():
            return

        if directive == "define":
            self._process_define(line)
        elif directive == "undef":
            self._process_undef(line)
        elif directive == "include":
            self._process_include(line)
        elif directive == "error":
            self._process_error(line)
        elif directive == "warning":
            self._process_warning(line)
        elif directive == "pragma":
            self._process_pragma(line)
        elif directive == "line":
            # Ignore line directives
            pass
        else:
            raise CPreprocessorError(
                f"unknown preprocessor directive '#{directive}'",
                SourceLocation(self._current_file, self._current_line, 1),
            )

    def _process_define(self, line: str) -> None:
        """Process #define directive."""
        match = self.DEFINE_PATTERN.match(line)
        if not match:
            raise CPreprocessorError(
                "invalid #define syntax",
                SourceLocation(self._current_file, self._current_line, 1),
            )

        name = match.group(1)
        params_str = match.group(2)
        body = match.group(3).strip()

        # Parse parameters for function-like macros
        parameters = None
        if params_str is not None:
            parameters = [p.strip() for p in params_str.split(",") if p.strip()]

        self._macros[name] = Macro(
            name=name,
            body=body,
            parameters=parameters,
            location=SourceLocation(self._current_file, self._current_line, 1),
        )

    def _process_undef(self, line: str) -> None:
        """Process #undef directive."""
        match = re.match(r'^\s*#\s*undef\s+(\w+)', line)
        if not match:
            raise CPreprocessorError(
                "invalid #undef syntax",
                SourceLocation(self._current_file, self._current_line, 1),
            )

        name = match.group(1)
        if name in self._macros:
            del self._macros[name]

    def _process_include(self, line: str) -> None:
        """Process #include directive."""
        match = self.INCLUDE_PATTERN.match(line)
        if not match:
            raise CPreprocessorError(
                "invalid #include syntax",
                SourceLocation(self._current_file, self._current_line, 1),
            )

        delimiter = match.group(1)
        filename = match.group(2)

        # Determine search paths
        if delimiter == '"':
            # Local include: search current directory first
            search_paths = [Path(self._current_file).parent] + [Path(p) for p in self.include_paths]
        else:
            # System include: search include paths only
            search_paths = [Path(p) for p in self.include_paths]

        # Find the file
        include_path = None
        for path in search_paths:
            candidate = path / filename
            if candidate.exists():
                include_path = candidate
                break

        if include_path is None:
            raise CIncludeError(
                filename,
                "file not found",
                SourceLocation(self._current_file, self._current_line, 1),
                search_paths=[str(p) for p in search_paths],
            )

        # Check for circular include
        resolved_path = str(include_path.resolve())
        if resolved_path in self._include_stack:
            raise CIncludeError(
                filename,
                "circular include detected",
                SourceLocation(self._current_file, self._current_line, 1),
            )

        # Track included file basename (e.g., "float.h")
        self._included_files.add(Path(filename).name.lower())

        # Read and process the included file
        try:
            include_source = include_path.read_text(encoding='utf-8')
        except OSError as e:
            raise CIncludeError(
                filename,
                str(e),
                SourceLocation(self._current_file, self._current_line, 1),
            )

        # Save state
        saved_file = self._current_file
        saved_line = self._current_line

        # Process include
        self._include_stack.append(resolved_path)
        self._current_file = str(include_path)

        include_lines = include_source.splitlines()
        for i, include_line in enumerate(include_lines):
            self._current_line = i + 1
            self._process_line(include_line)

        # Restore state
        self._include_stack.pop()
        self._current_file = saved_file
        self._current_line = saved_line

    def _process_conditional(self, directive: str, line: str) -> None:
        """Process conditional compilation directives."""
        if directive == "ifdef":
            match = re.match(r'^\s*#\s*ifdef\s+(\w+)', line)
            if not match:
                raise CPreprocessorError(
                    "invalid #ifdef syntax",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            name = match.group(1)
            defined = name in self._macros
            self._condition_stack.append((not defined, defined))

        elif directive == "ifndef":
            match = re.match(r'^\s*#\s*ifndef\s+(\w+)', line)
            if not match:
                raise CPreprocessorError(
                    "invalid #ifndef syntax",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            name = match.group(1)
            defined = name in self._macros
            self._condition_stack.append((defined, not defined))

        elif directive == "if":
            match = re.match(r'^\s*#\s*if\s+(.+)$', line)
            if not match:
                raise CPreprocessorError(
                    "invalid #if syntax",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            expr = match.group(1).strip()
            result = self._evaluate_condition(expr)
            self._condition_stack.append((not result, result))

        elif directive == "elif":
            if not self._condition_stack:
                raise CPreprocessorError(
                    "#elif without matching #if",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            match = re.match(r'^\s*#\s*elif\s+(.+)$', line)
            if not match:
                raise CPreprocessorError(
                    "invalid #elif syntax",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            _, any_taken = self._condition_stack.pop()
            if any_taken:
                # A previous branch was taken, skip this one
                self._condition_stack.append((True, True))
            else:
                expr = match.group(1).strip()
                result = self._evaluate_condition(expr)
                self._condition_stack.append((not result, result))

        elif directive == "else":
            if not self._condition_stack:
                raise CPreprocessorError(
                    "#else without matching #if",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            _, any_taken = self._condition_stack.pop()
            # Take else only if no previous branch was taken
            self._condition_stack.append((any_taken, True))

        elif directive == "endif":
            if not self._condition_stack:
                raise CPreprocessorError(
                    "#endif without matching #if",
                    SourceLocation(self._current_file, self._current_line, 1),
                )
            self._condition_stack.pop()

    def _evaluate_condition(self, expr: str) -> bool:
        """
        Evaluate a preprocessor conditional expression.

        Supports:
        - Integer constants
        - defined(NAME) and defined NAME
        - Basic arithmetic and comparison operators
        """
        # Handle defined() operator
        expr = re.sub(
            r'defined\s*\(\s*(\w+)\s*\)',
            lambda m: "1" if m.group(1) in self._macros else "0",
            expr,
        )
        expr = re.sub(
            r'defined\s+(\w+)',
            lambda m: "1" if m.group(1) in self._macros else "0",
            expr,
        )

        # Expand macros
        expr = self._expand_macros(expr)

        # Replace identifiers with 0 (undefined macros are 0)
        expr = re.sub(r'\b[A-Za-z_]\w*\b', "0", expr)

        # Evaluate expression (only integer arithmetic)
        try:
            # Safe eval with only arithmetic operations
            result = eval(expr, {"__builtins__": {}}, {})
            return bool(result)
        except Exception:
            # If evaluation fails, treat as false
            return False

    def _process_error(self, line: str) -> None:
        """Process #error directive."""
        match = re.match(r'^\s*#\s*error\s*(.*)$', line)
        message = match.group(1).strip() if match else "error"
        raise CPreprocessorError(
            f"#error: {message}",
            SourceLocation(self._current_file, self._current_line, 1),
        )

    def _process_warning(self, line: str) -> None:
        """Process #warning directive (emit as comment)."""
        match = re.match(r'^\s*#\s*warning\s*(.*)$', line)
        message = match.group(1).strip() if match else "warning"
        self._output.append(f"/* #warning: {message} */")

    def _process_pragma(self, line: str) -> None:
        """
        Process #pragma directive.

        Currently supports:
        - #pragma psion model XXX - Set target Psion model

        Other pragmas are silently ignored (standard C behavior).
        """
        # Check for #pragma psion model XXX
        match = self.PRAGMA_PSION_MODEL_PATTERN.match(line)
        if match:
            model_name = match.group(1).upper()

            # Validate model name
            if model_name not in self.VALID_MODELS:
                raise CPreprocessorError(
                    f"unknown Psion model '{model_name}' in #pragma psion model. "
                    f"Valid models: {', '.join(sorted(self.VALID_MODELS))}",
                    SourceLocation(self._current_file, self._current_line, 1),
                )

            # Store detected model from source code
            self._detected_model = model_name

            # Only update macros if CLI didn't override
            # (CLI takes precedence over pragma)
            if not self._model_from_cli:
                self._setup_model_macros(model_name)

            return

        # Other pragmas are silently ignored (standard C behavior)
        # This is intentional - unknown pragmas should not cause errors

    def get_detected_model(self) -> Optional[str]:
        """
        Return the model detected from #pragma psion model directive.

        Returns:
            The model name found in source code, or None if no pragma was found.
        """
        return self._detected_model

    def get_effective_model(self) -> str:
        """
        Return the effective target model for code generation.

        The precedence is:
        1. CLI-specified model (highest priority)
        2. Source code #pragma psion model directive
        3. Default (LZ)

        Returns:
            The effective model name (CM, XP, LA, LZ, or LZ64)
        """
        if self._model_from_cli:
            return self._initial_model
        if self._detected_model:
            return self._detected_model
        return self._initial_model

    def has_float_support(self) -> bool:
        """
        Return True if the source code uses floating point support.

        This checks if float.h was included during preprocessing.
        Used by codegen to conditionally include fpruntime.inc.

        Returns:
            True if float.h was included, False otherwise.
        """
        return "float.h" in self._included_files

    def has_stdio_support(self) -> bool:
        """
        Return True if the source code uses extended stdio functions.

        This checks if stdio.h was included during preprocessing.
        Used by codegen to conditionally include stdio.inc which provides
        strrchr, strstr, strncat, and sprintf functions.

        Returns:
            True if stdio.h was included, False otherwise.
        """
        return "stdio.h" in self._included_files

    def get_included_files(self) -> set[str]:
        """
        Return the set of included file basenames.

        Returns:
            Set of lowercase filenames that were included (e.g., {"float.h", "psion.h"})
        """
        return self._included_files.copy()

    def _expand_macros(self, line: str) -> str:
        """Expand all macros in a line of text."""
        # Track which macros are being expanded to prevent infinite recursion
        expanded_macros: set[str] = set()
        return self._expand_macros_impl(line, expanded_macros)

    def _expand_macros_impl(self, text: str, expanded_macros: set[str]) -> str:
        """Implementation of macro expansion with recursion tracking."""
        result = text

        # Handle __LINE__ and __FILE__ specially
        result = result.replace("__LINE__", str(self._current_line))
        result = result.replace("__FILE__", f'"{self._current_file}"')

        # Find and expand macros
        changed = True
        iterations = 0
        max_iterations = 100  # Prevent infinite loops

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for match in self.IDENTIFIER_PATTERN.finditer(result):
                name = match.group(1)

                # Skip if already expanding this macro (prevent recursion)
                if name in expanded_macros:
                    continue

                # Skip if not a defined macro
                if name not in self._macros:
                    continue

                macro = self._macros[name]

                # Handle function-like macros
                if macro.is_function_like:
                    # Look for opening parenthesis after the name
                    start = match.end()
                    if start < len(result) and result[start] == "(":
                        # Find matching close parenthesis
                        args, end = self._parse_macro_args(result, start)
                        if args is not None:
                            # Expand the macro
                            expanded_macros.add(name)
                            expansion = self._expand_function_macro(macro, args, expanded_macros)
                            expanded_macros.discard(name)

                            result = result[:match.start()] + expansion + result[end:]
                            changed = True
                            break
                else:
                    # Simple macro: direct substitution
                    expanded_macros.add(name)
                    expansion = self._expand_macros_impl(macro.body, expanded_macros)
                    expanded_macros.discard(name)

                    result = result[:match.start()] + expansion + result[match.end():]
                    changed = True
                    break

        return result

    def _parse_macro_args(self, text: str, start: int) -> tuple[Optional[list[str]], int]:
        """
        Parse macro arguments from text starting at '('.

        Returns:
            Tuple of (argument_list, end_position) or (None, 0) if not valid
        """
        if text[start] != "(":
            return None, 0

        args = []
        current_arg = []
        depth = 1
        i = start + 1

        while i < len(text) and depth > 0:
            char = text[i]

            if char == "(":
                depth += 1
                current_arg.append(char)
            elif char == ")":
                depth -= 1
                if depth > 0:
                    current_arg.append(char)
            elif char == "," and depth == 1:
                args.append("".join(current_arg).strip())
                current_arg = []
            else:
                current_arg.append(char)

            i += 1

        if depth != 0:
            return None, 0

        # Add last argument
        if current_arg or args:
            args.append("".join(current_arg).strip())

        return args, i

    def _expand_function_macro(
        self,
        macro: Macro,
        args: list[str],
        expanded_macros: set[str],
    ) -> str:
        """Expand a function-like macro with arguments."""
        if len(args) != len(macro.parameters):
            raise MacroExpansionError(
                macro.name,
                f"expected {len(macro.parameters)} arguments, got {len(args)}",
                macro.location,
            )

        # Substitute parameters in body
        result = macro.body
        for param, arg in zip(macro.parameters, args):
            # Replace parameter with argument
            result = re.sub(rf'\b{param}\b', arg, result)

        # Recursively expand macros in result
        return self._expand_macros_impl(result, expanded_macros)


# =============================================================================
# Convenience Function
# =============================================================================

def preprocess(
    source: str,
    filename: str = "<input>",
    include_paths: Optional[list[str]] = None,
) -> str:
    """
    Preprocess C source code.

    Args:
        source: Source code to preprocess
        filename: Source filename for error reporting
        include_paths: Directories to search for includes

    Returns:
        Preprocessed source code
    """
    pp = Preprocessor(source, filename, include_paths)
    return pp.process()
