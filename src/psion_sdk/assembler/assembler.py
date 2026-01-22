"""
HD6303 Assembler - Main Interface
==================================

This module provides the main Assembler class, which is the primary interface
for assembling HD6303 source code. It coordinates the lexer, parser, optimizer,
and code generator to produce Psion-compatible object code.

Example Usage
-------------
>>> from psion_sdk.assembler import Assembler
>>>
>>> # Create assembler instance
>>> asm = Assembler()
>>>
>>> # Assemble from string
>>> asm.assemble_string('''
...     ORG $8000
... start:
...     LDAA #'H'
...     JSR print
...     RTS
... ''')
>>>
>>> # Get generated code
>>> code = asm.get_code()
>>> print(f"Generated {len(code)} bytes")
>>>
>>> # Write OB3 file
>>> asm.write_ob3("hello.ob3")

Command-Line Usage
------------------
The assembler can also be invoked from the command line:

    $ psasm hello.asm -o hello.ob3 -l hello.lst -s hello.sym

Options:
    -o, --output FILE      Output OB3 file
    -l, --listing FILE     Generate listing file
    -s, --symbols FILE     Generate symbol file
    -I, --include PATH     Add include search path
    -D, --define SYM=VAL   Pre-define symbol
    -O, --optimize         Enable peephole optimization (default: enabled)
    --no-optimize          Disable peephole optimization
    -v, --verbose          Verbose output
"""

from pathlib import Path
from typing import Optional

from psion_sdk.assembler.parser import parse_source
from psion_sdk.assembler.codegen import CodeGenerator
from psion_sdk.assembler.optimizer import PeepholeOptimizer, OptimizationStats
from psion_sdk.errors import AssemblerError


class Assembler:
    """
    Main HD6303 assembler class.

    This class provides a high-level interface for assembling HD6303
    source code into Psion-compatible object code format.

    The assembler supports:
    - Full HD6303 instruction set
    - Psion-specific extensions
    - Include files
    - Macros
    - Conditional assembly
    - Peephole optimization (enabled by default)
    - Multiple output formats (OB3, listing, symbols)
    - Target model specification (CM, XP, LA, LZ, LZ64)

    Attributes:
        verbose: If True, print progress messages
        target_model: Target Psion model (CM, XP, LA, LZ, LZ64)
        optimize: If True (default), apply peephole optimizations
    """

    # =========================================================================
    # Target Model Constants
    # =========================================================================
    # Valid target models for the assembler.
    # See dev_docs/TARGET_MODELS.md for full documentation.
    #
    # Categories:
    #   2-line displays: CM, XP, LA (16x2 characters)
    #   4-line displays: LZ, LZ64 (20x4 characters)
    #   Cross-platform:  PORTABLE (runs on any model, no STOP+SIN prefix)
    # =========================================================================
    VALID_MODELS = frozenset({"CM", "XP", "LA", "LZ", "LZ64", "PORTABLE"})

    # 2-line models (for categorization)
    MODELS_2LINE = frozenset({"CM", "XP", "LA"})

    # 4-line models (these get STOP+SIN prefix in OB3)
    MODELS_4LINE = frozenset({"LZ", "LZ64"})

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

    # Model identification bytes (same as ROM $FFE8 bits 0-2)
    MODEL_IDS = {
        "CM": 0,
        "XP": 1,
        "LA": 2,
        "LZ": 6,
        "LZ64": 5,
        "PORTABLE": 1,  # Default to XP ID for PORTABLE
    }

    def __init__(self, verbose: bool = False,
                 include_paths: list[str | Path] | None = None,
                 defines: dict[str, int] | None = None,
                 relocatable: bool = False,
                 target_model: str | None = None,
                 optimize: bool = True):
        """
        Initialize the assembler.

        Args:
            verbose: Enable verbose output
            include_paths: List of directories to search for include files
            defines: Dictionary of pre-defined symbols
            relocatable: Generate self-relocating code with position-independent
                         stub and fixup table
            target_model: Target Psion model (CM, XP, LA, LZ, LZ64).
                         If None, defaults to XP. Can be overridden by .MODEL
                         directive in source code, but CLI flag takes precedence.
            optimize: Enable peephole optimization (default: True). Applies safe
                     optimizations like converting LDAA #0 to CLRA, eliminating
                     redundant push/pull pairs, etc. Disable for debugging or
                     when exact instruction sequences must be preserved.
        """
        self._verbose = verbose
        self._relocatable = relocatable
        self._optimize = optimize
        self._include_paths: list[Path] = []
        self._defines: dict[str, int] = {}
        self._source_file: Optional[Path] = None
        self._opt_stats: Optional[OptimizationStats] = None  # Last optimization stats

        # Target model handling:
        # - _initial_model: Model specified via constructor (from CLI)
        # - _model_from_cli: True if constructor model was explicitly set
        # The effective model is determined after .MODEL directive is processed
        self._initial_model = (target_model or "XP").upper()
        self._model_from_cli = target_model is not None

        # Validate initial model
        if self._initial_model not in self.VALID_MODELS:
            self._initial_model = "XP"

        # Create CodeGenerator with model callback for .MODEL directive handling
        # Pass the target model so it can add STOP+SIN prefix for 4-line targets
        self._codegen = CodeGenerator(
            relocatable=relocatable,
            model_callback=self.set_model,
            target=self._initial_model
        )

        # Initialize model-specific symbols
        self._setup_model_symbols(self._initial_model)

        # Add include paths
        if include_paths:
            for path in include_paths:
                self.add_include_path(path)

        # Add defines
        if defines:
            for name, value in defines.items():
                self.define_symbol(name, value)

    def _setup_model_symbols(self, model: str) -> None:
        """
        Set up model-specific predefined symbols.

        This defines assembler symbols based on the target model:
        - __MODEL__ = model ID (0=CM, 1=XP, 2=LA, 5=LZ64, 6=LZ)
        - __PSION_CM__, __PSION_XP__, etc. = 1 if active model
        - __PSION_2LINE__ or __PSION_4LINE__ = 1 based on display type
        - DISP_ROWS, DISP_COLS = display dimensions

        Args:
            model: Target model name (CM, XP, LA, LZ, LZ64)
        """
        model_upper = model.upper()

        # Clear any existing model symbols first
        model_symbols = [
            "__MODEL__", "__PSION_CM__", "__PSION_XP__", "__PSION_LA__",
            "__PSION_LZ__", "__PSION_LZ64__", "__PSION_2LINE__",
            "__PSION_4LINE__", "DISP_ROWS", "DISP_COLS",
        ]
        for sym in model_symbols:
            if sym in self._defines:
                del self._defines[sym]

        # Model ID
        model_id = self.MODEL_IDS.get(model_upper, 1)
        self.define_symbol("__MODEL__", model_id)

        # Active model flag
        self.define_symbol(f"__PSION_{model_upper}__", 1)

        # Display characteristics
        rows, cols = self.MODEL_DISPLAY.get(model_upper, (2, 16))
        self.define_symbol("DISP_ROWS", rows)
        self.define_symbol("DISP_COLS", cols)

        # Display type flag
        if rows == 2:
            self.define_symbol("__PSION_2LINE__", 1)
        else:
            self.define_symbol("__PSION_4LINE__", 1)

    def set_model(self, model: str) -> None:
        """
        Set the target model (for .MODEL directive handling).

        This is called when a .MODEL directive is encountered in source code.
        If the CLI explicitly set a model, this call is ignored.

        This also updates the CodeGenerator's target, which affects whether
        the STOP+SIN prefix is added for 4-line mode detection.

        Args:
            model: Target model name (CM, XP, LA, LZ, LZ64, PORTABLE)
        """
        model_upper = model.upper()

        if model_upper not in self.VALID_MODELS:
            raise AssemblerError(
                f"unknown Psion model '{model}'. "
                f"Valid models: {', '.join(sorted(self.VALID_MODELS))}",
            )

        # CLI flag takes precedence over .MODEL directive
        if self._model_from_cli:
            if self._verbose:
                print(f"Note: .MODEL {model} overridden by CLI flag (-m {self._initial_model})")
            return

        # Update model symbols for preprocessor/conditional assembly
        self._setup_model_symbols(model_upper)

        # Update CodeGenerator's target for OB3 generation (STOP+SIN prefix)
        self._codegen.set_target(model_upper)

        if self._verbose:
            rows, cols = self.MODEL_DISPLAY.get(model_upper, (2, 16))
            display_type = "2-line" if rows == 2 else "4-line"
            print(f"Target model set to {model_upper} ({display_type} display, {cols}x{rows})")

    def get_target_model(self) -> str:
        """
        Get the effective target model.

        Returns:
            The target model name (CM, XP, LA, LZ, or LZ64)
        """
        return self._initial_model

    # =========================================================================
    # Configuration
    # =========================================================================

    def add_include_path(self, path: str | Path) -> None:
        """
        Add a directory to search for include files.

        Args:
            path: Directory path to add
        """
        path = Path(path)
        if path.is_dir():
            self._include_paths.append(path)
            self._codegen.set_include_paths(self._include_paths)
        else:
            if self._verbose:
                print(f"Warning: include path '{path}' is not a directory")

    def define_symbol(self, name: str, value: int) -> None:
        """
        Pre-define a symbol (like -D on command line).

        Args:
            name: Symbol name
            value: Symbol value
        """
        self._defines[name] = value
        self._codegen.define_symbol(name, value)

    # =========================================================================
    # Assembly Methods
    # =========================================================================

    def assemble(self, source: str, filename: str = "<input>",
                  output_format: str = "ob3", output_path: str | Path | None = None) -> bytes:
        """
        Assemble source code (alias for assemble_string with output options).

        Args:
            source: Assembly source code
            filename: Virtual filename for error messages
            output_format: Output format ('ob3' or 'binary')
            output_path: Optional output file path

        Returns:
            Generated object code as bytes
        """
        result = self.assemble_string(source, filename)

        if output_path:
            if output_format == "binary":
                self.write_binary(output_path)
            else:
                self.write_ob3(output_path)

        # Return raw binary if requested, otherwise OB3 format
        if output_format == "binary":
            return self._codegen.get_code()

        return result

    def assemble_string(self, source: str, filename: str = "<input>") -> bytes:
        """
        Assemble source code from a string.

        The assembly pipeline is:
        1. Parse source into statements (lexer -> parser)
        2. Optimize statements if enabled (peephole optimizer)
        3. Generate code (code generator)

        Args:
            source: Assembly source code
            filename: Virtual filename for error messages

        Returns:
            Generated object code as bytes

        Raises:
            AssemblerError: If assembly fails
        """
        if self._verbose:
            print(f"Assembling from string...")

        # Parse source (include_paths needed for macro pre-processing)
        include_paths_str = [str(p) for p in self._include_paths]
        statements = parse_source(source, filename, include_paths=include_paths_str)

        if self._verbose:
            print(f"Parsed {len(statements)} statements")

        # Optimize statements if enabled
        if self._optimize:
            optimizer = PeepholeOptimizer(enabled=True, verbose=self._verbose)
            statements = optimizer.optimize(statements)
            self._opt_stats = optimizer.stats

            if self._verbose and self._opt_stats.total_optimizations > 0:
                print(f"Applied {self._opt_stats.total_optimizations} optimizations")
        else:
            self._opt_stats = None

        # Generate code
        code = self._codegen.generate(statements)

        if self._verbose:
            print(f"Generated {len(code)} bytes of code")

        return code

    def assemble_file(self, filepath: str | Path) -> bytes:
        """
        Assemble source code from a file.

        Args:
            filepath: Path to assembly source file

        Returns:
            Generated object code as bytes

        Raises:
            AssemblerError: If assembly fails
            FileNotFoundError: If source file not found
        """
        filepath = Path(filepath)
        self._source_file = filepath

        if self._verbose:
            print(f"Assembling {filepath}...")

        # Add source file's directory to include paths
        source_dir = filepath.parent
        if source_dir not in self._include_paths:
            self._include_paths.insert(0, source_dir)
            self._codegen.set_include_paths(self._include_paths)

        # Read source
        source = filepath.read_text()

        # Assemble
        return self.assemble_string(source, str(filepath))

    # =========================================================================
    # Output Methods
    # =========================================================================

    def get_code(self) -> bytes:
        """
        Get the generated object code.

        Returns:
            Object code as bytes
        """
        return self._codegen.get_code()

    def get_origin(self) -> int:
        """
        Get the origin address.

        Returns:
            Origin address (first ORG value)
        """
        return self._codegen.get_origin()

    def get_symbols(self) -> dict[str, int]:
        """
        Get the symbol table.

        Returns:
            Dictionary mapping symbol names to values
        """
        return self._codegen.get_symbols()

    def get_listing(self) -> str:
        """
        Get the assembly listing as a string.

        Returns:
            Assembly listing with addresses, code bytes, and source
        """
        return self._codegen.get_listing()

    def is_relocatable(self) -> bool:
        """
        Check if assembler is in relocatable mode.

        Returns:
            True if generating self-relocating code
        """
        return self._relocatable

    def is_optimizing(self) -> bool:
        """
        Check if optimization is enabled.

        Returns:
            True if peephole optimization is enabled
        """
        return self._optimize

    def get_optimization_stats(self) -> Optional[OptimizationStats]:
        """
        Get statistics from the last optimization pass.

        Returns:
            OptimizationStats object with counts of each optimization type,
            or None if no assembly has been performed or optimization is disabled.
        """
        return self._opt_stats

    def get_fixup_count(self) -> int:
        """
        Get the number of relocation fixups.

        Returns:
            Number of address fixups (0 if not in relocatable mode)
        """
        return len(self._codegen._fixups) if self._relocatable else 0

    def write_ob3(self, filepath: str | Path) -> None:
        """
        Write output to OB3 (ORG) file format.

        The OB3 format is the standard Psion object file format
        for procedures and machine code.

        Args:
            filepath: Output file path
        """
        self._codegen.write_ob3(filepath)

        if self._verbose:
            print(f"Wrote {filepath}")

    def write_listing(self, filepath: str | Path) -> None:
        """
        Write assembly listing file.

        The listing file shows:
        - Addresses
        - Generated bytes
        - Source lines
        - Symbol table

        Args:
            filepath: Output file path
        """
        self._codegen.write_listing(filepath)

        if self._verbose:
            print(f"Wrote listing to {filepath}")

    def write_symbols(self, filepath: str | Path) -> None:
        """
        Write symbol table file.

        Args:
            filepath: Output file path
        """
        self._codegen.write_symbols(filepath)

        if self._verbose:
            print(f"Wrote symbols to {filepath}")

    def write_binary(self, filepath: str | Path) -> None:
        """
        Write raw binary output (machine code only, no wrapper).

        This writes just the machine code bytes without any OPL wrapper
        or OB3 header. Useful for ROM images or debugging.

        Args:
            filepath: Output file path
        """
        code = self.get_code()
        Path(filepath).write_bytes(code)

        if self._verbose:
            print(f"Wrote {len(code)} bytes to {filepath}")

    def write_proc(self, filepath: str | Path) -> None:
        """
        Write OPL-wrapped procedure (without OB3 header).

        This writes the procedure bytes that would go inside an OB3 file,
        without the "ORG" magic and length headers. Useful for comparison
        with DOS SDK output or embedding in custom pack formats.

        The output includes:
        - VVVV, QQQQ, XX: Procedure header
        - Tables: Empty table markers
        - [STOP+SIN]: For LZ/LZ64 targets only
        - QCode bootstrap: Address computation and USR call
        - Machine code: The assembled code

        Args:
            filepath: Output file path
        """
        self._codegen.write_proc(filepath)

        if self._verbose:
            print(f"Wrote procedure to {filepath}")

    # =========================================================================
    # Error Handling
    # =========================================================================

    def has_errors(self) -> bool:
        """
        Check if assembly produced errors.

        Returns:
            True if errors occurred
        """
        return self._codegen.has_errors()

    def get_error_report(self) -> str:
        """
        Get formatted error report.

        Returns:
            Error report string
        """
        return self._codegen.get_error_report()


# =============================================================================
# Convenience Functions
# =============================================================================

def assemble(source: str, filename: str = "<input>", optimize: bool = True) -> bytes:
    """
    Convenience function to assemble source code.

    Args:
        source: Assembly source code
        filename: Virtual filename for errors
        optimize: Enable peephole optimization (default: True)

    Returns:
        Generated object code

    Raises:
        AssemblerError: If assembly fails
    """
    asm = Assembler(optimize=optimize)
    return asm.assemble_string(source, filename)


def assemble_file(filepath: str | Path, optimize: bool = True) -> bytes:
    """
    Convenience function to assemble a file.

    Args:
        filepath: Path to source file
        optimize: Enable peephole optimization (default: True)

    Returns:
        Generated object code

    Raises:
        AssemblerError: If assembly fails
    """
    asm = Assembler(optimize=optimize)
    return asm.assemble_file(filepath)
