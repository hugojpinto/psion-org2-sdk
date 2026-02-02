"""
psbuild - Unified Build Tool for Psion Organiser II
====================================================

This module implements a unified build tool that combines the entire toolchain
(pscc → psasm → psopk) into a single command for building Psion programs
from C or assembly source files.

The tool automatically detects the source type based on file extension and
runs the appropriate pipeline:

    .c files:   pscc → psasm (with -r) → psopk
    .asm files: psasm → psopk

Key Features
------------
- **Auto-detection**: Determines source type from file extension
- **Smart defaults**: Automatically finds SDK include directory
- **C-aware**: Always enables relocatable code (-r) for C sources
- **Single command**: Replaces the 3-command pipeline with one command
- **Clean operation**: Uses temp files, cleans up on success
- **Pass-through flags**: Common options work across all pipeline stages
- **Multi-file linking**: Build from multiple C and assembly files

Usage Examples
--------------
Build C program (auto-detects .c, runs full pipeline):
    $ psbuild hello.c -o HELLO.opk

Build assembly program (auto-detects .asm, skips compiler):
    $ psbuild hello.asm -o HELLO.opk

Target 4-line display (LZ/LZ64):
    $ psbuild -m LZ hello.c -o HELLO.opk

Verbose mode (shows each pipeline stage):
    $ psbuild -v hello.c

Keep intermediate files for debugging:
    $ psbuild -k hello.c -o HELLO.opk

Multi-file builds (C with external assembly helpers):
    $ psbuild main.c helpers.asm -o MYAPP.opk

Multi-file builds (multiple C files):
    $ psbuild main.c utils.c math.c -o MYAPP.opk

Pipeline Architecture
---------------------
For single C source (.c):

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  .c file │────▶│ .asm file│────▶│ .ob3 file│────▶│ .opk file│
    │ (source) │pscc │  (temp)  │psasm│  (temp)  │psopk│ (output) │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘

For single assembly source (.asm):

    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ .asm file│────▶│ .ob3 file│────▶│ .opk file│
    │ (source) │psasm│  (temp)  │psopk│ (output) │
    └──────────┘     └──────────┘     └──────────┘

For multi-file builds:

    ┌──────────┐     ┌──────────┐
    │ helper.c │────▶│helper.asm│──┐  (library mode: no runtime)
    └──────────┘pscc └──────────┘  │
                                   │
    ┌──────────┐     ┌──────────┐  │  ┌───────────┐     ┌──────────┐     ┌──────────┐
    │  main.c  │────▶│ main.asm │──┼─▶│merged.asm │────▶│ .ob3 file│────▶│ .opk file│
    └──────────┘pscc └──────────┘  │  │ (concat)  │psasm│  (temp)  │psopk│ (output) │
                                   │  └───────────┘     └──────────┘     └──────────┘
    ┌──────────┐                   │
    │helpers.as│───────────────────┘  (user assembly)
    └──────────┘

Multi-File Build Process
------------------------
When multiple input files are provided:

1. **Classification**: Files are sorted into C sources and assembly sources.

2. **Main Detection**: The C file containing `main()` is identified as the
   "main file". Only one C file should contain main().

3. **Library Compilation**: All C files except the main file are compiled
   in "library mode" (emit_runtime=False), which:
   - Omits the _entry point
   - Omits runtime.inc inclusion (runtime code)
   - Still includes psion.inc (constants are idempotent)

4. **Main Compilation**: The main file is compiled normally with runtime.

5. **Concatenation**: Assembly files are concatenated in order:
   - Library assembly files (from non-main C files)
   - User-provided assembly files
   - Main assembly file (last, contains _entry)

6. **Assembly**: The merged assembly is assembled to OB3.

7. **Packaging**: The OB3 is packaged into OPK.

This approach works because:
- The Psion OB3 format has no symbol table, so linking must happen at
  assembly source level
- Forward references are resolved by the assembler's two-pass design
- Runtime code is included only once (from main file)
- Constants in psion.inc are idempotent (safe to include multiple times)

Include Path Resolution
-----------------------
The SDK's include directory is automatically located relative to this module's
installation path. The search order for include files is:

1. Directories explicitly specified with -I (in order given)
2. The source file's parent directory
3. The SDK's include/ directory (auto-detected)

This ensures that #include <psion.h> and INCLUDE "runtime.inc" work without
requiring the user to specify -I include explicitly.

Exit Codes
----------
0 - Success
1 - Build failed (compilation, assembly, or packaging error)
2 - Invalid arguments or file not found

Notes
-----
- C sources (.c) always have -r (relocatable) enabled because C programs
  require self-relocation to work on the Psion's dynamic memory layout.

- Assembly sources (.asm) do NOT have -r enabled by default, as hand-written
  assembly may use absolute addressing intentionally. Use -r explicitly if
  your assembly code uses internal symbol references that need relocation.

- The procedure name in the OPK is derived from the output filename (uppercase,
  max 8 characters). E.g., -o HELLO.opk creates a procedure named "HELLO".

- For multi-file builds, exactly one C file should contain main(). If no C
  files have main() (all assembly), assembly order determines the entry point.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.smallc import SmallCCompiler, CompilerOptions
from psion_sdk.smallc.compiler import source_has_main
from psion_sdk.assembler import Assembler
from psion_sdk.opk import PackBuilder, validate_ob3
from psion_sdk.cli.errors import handle_cli_exception


# =============================================================================
# Constants
# =============================================================================

# Supported source file extensions (lowercase for comparison)
C_EXTENSIONS = frozenset({".c"})
ASM_EXTENSIONS = frozenset({".asm", ".s"})

# Valid target models (same as pscc and psasm)
VALID_MODELS = ("CM", "XP", "LA", "LZ", "LZ64", "PORTABLE")


# =============================================================================
# Multi-File Build Data Structures
# =============================================================================

@dataclass
class ClassifiedFiles:
    """
    Result of classifying input files by type.

    This data class holds the categorized input files for a multi-file build,
    separating C sources from assembly sources for proper pipeline handling.

    Attributes:
        c_files: List of C source files (.c) in input order
        asm_files: List of assembly source files (.asm, .s) in input order
        all_files: Combined list of all input files in original order
    """
    c_files: list[Path] = field(default_factory=list)
    asm_files: list[Path] = field(default_factory=list)
    all_files: list[Path] = field(default_factory=list)

    @property
    def is_multi_file(self) -> bool:
        """True if this is a multi-file build (more than one input file)."""
        return len(self.all_files) > 1

    @property
    def has_c_files(self) -> bool:
        """True if at least one C source file is present."""
        return len(self.c_files) > 0

    @property
    def has_asm_files(self) -> bool:
        """True if at least one assembly source file is present."""
        return len(self.asm_files) > 0

    @property
    def is_c_only(self) -> bool:
        """True if all input files are C sources."""
        return self.has_c_files and not self.has_asm_files

    @property
    def is_asm_only(self) -> bool:
        """True if all input files are assembly sources."""
        return self.has_asm_files and not self.has_c_files


@dataclass
class MainFileResult:
    """
    Result of detecting the main file in a multi-file build.

    For C builds, exactly one file should contain the main() function.
    This file receives special handling: it's compiled with the runtime
    (emit_runtime=True) while other C files are compiled in library mode.

    Attributes:
        main_file: Path to the file containing main() (None if not found)
        library_c_files: C files that don't contain main() (library mode)
        found: True if a main file was successfully identified
        error: Error message if detection failed (multiple main(), etc.)
    """
    main_file: Optional[Path] = None
    library_c_files: list[Path] = field(default_factory=list)
    found: bool = False
    error: Optional[str] = None


# =============================================================================
# Multi-File Build Helper Functions
# =============================================================================

def classify_input_files(input_files: tuple[Path, ...]) -> ClassifiedFiles:
    """
    Classify input files by their type (C or assembly).

    This function examines the file extensions of all input files and
    categorizes them for appropriate pipeline handling. Files are validated
    to ensure they have recognized extensions.

    Args:
        input_files: Tuple of input file paths (from CLI)

    Returns:
        ClassifiedFiles with c_files, asm_files, and all_files lists

    Raises:
        click.BadParameter: If any file has an unrecognized extension

    Example:
        >>> files = classify_input_files((Path("main.c"), Path("helper.asm")))
        >>> files.c_files
        [Path("main.c")]
        >>> files.asm_files
        [Path("helper.asm")]
    """
    result = ClassifiedFiles()

    for file_path in input_files:
        suffix = file_path.suffix.lower()
        result.all_files.append(file_path)

        if suffix in C_EXTENSIONS:
            result.c_files.append(file_path)
        elif suffix in ASM_EXTENSIONS:
            result.asm_files.append(file_path)
        else:
            # Unrecognized extension - raise helpful error
            raise click.BadParameter(
                f"Unrecognized source file extension: '{suffix}' for '{file_path.name}'. "
                f"Expected .c for C or .asm/.s for assembly.",
                param_hint="INPUT_FILES"
            )

    return result


def find_main_file(
    c_files: list[Path],
    include_paths: list[str],
    verbose: bool = False,
) -> MainFileResult:
    """
    Find which C file contains the main() function.

    In a multi-file build, exactly one C file should contain main().
    This file is compiled with the full runtime (emit_runtime=True),
    while all other C files are compiled in "library mode" without
    the entry point and runtime includes.

    The detection uses the compiler's full preprocessing and parsing
    pipeline to ensure accurate detection even with macros, conditional
    compilation, and includes.

    Args:
        c_files: List of C source file paths to check
        include_paths: Include search paths for preprocessing
        verbose: If True, print progress messages

    Returns:
        MainFileResult containing:
        - main_file: The file containing main() (or None)
        - library_c_files: Files not containing main()
        - found: True if exactly one main was found
        - error: Error message if detection failed

    Notes:
        - If no C files contain main(), found=False and error is set
        - If multiple C files contain main(), found=False and error is set
        - Assembly-only builds skip this check entirely

    Example:
        >>> result = find_main_file([Path("main.c"), Path("util.c")], ["."])
        >>> result.main_file
        Path("main.c")
        >>> result.library_c_files
        [Path("util.c")]
    """
    result = MainFileResult()
    files_with_main: list[Path] = []

    for c_file in c_files:
        if verbose:
            click.echo(f"      Checking {c_file.name} for main()...")

        try:
            source = c_file.read_text(encoding='utf-8')
            has_main = source_has_main(source, str(c_file), include_paths)

            if has_main:
                files_with_main.append(c_file)
                if verbose:
                    click.echo(f"      → Found main() in {c_file.name}")
            else:
                result.library_c_files.append(c_file)
                if verbose:
                    click.echo(f"      → {c_file.name} is a library file")

        except SmallCError as e:
            # If we can't parse a file, report it but continue
            # The actual compilation will give a better error
            result.error = f"Cannot check {c_file.name} for main(): {e}"
            return result

    # Validate the results
    if len(files_with_main) == 0:
        result.error = (
            "No main() function found in any C file. "
            "Multi-file C builds require exactly one file to contain main()."
        )
        return result

    if len(files_with_main) > 1:
        names = ", ".join(f.name for f in files_with_main)
        result.error = (
            f"Multiple main() functions found in: {names}. "
            f"Multi-file builds require exactly one file to contain main()."
        )
        return result

    # Success: exactly one file with main()
    result.main_file = files_with_main[0]
    result.found = True
    return result


def concatenate_assembly_files(
    library_asm_files: list[Path],
    user_asm_files: list[Path],
    main_asm_file: Optional[Path],
    output_file: Path,
    verbose: bool = False,
) -> None:
    """
    Concatenate multiple assembly files into a single merged file.

    The concatenation order is critical for correct linking:

    1. Library assembly files (from C sources compiled in library mode)
       - These contain helper functions called by main
       - No entry point, no runtime includes

    2. User-provided assembly files (from command line)
       - Hand-written assembly helper functions
       - May define additional procedures

    3. Main assembly file (from the C source containing main())
       - Contains _entry point at the top (branches to _main)
       - Contains _main function
       - Contains runtime includes at the bottom

    This ordering ensures:
    - Forward references work (assembler's two-pass design)
    - Entry point is at a known position (start of main file section)
    - Runtime code is included exactly once

    Each file section is marked with a comment header for debugging.

    Args:
        library_asm_files: Assembly from C files compiled in library mode
        user_asm_files: Assembly files provided directly by user
        main_asm_file: Assembly from the C file containing main() (or None)
        output_file: Path to write the merged assembly
        verbose: If True, print progress messages

    Note:
        The main_asm_file should be the last one because it contains
        the runtime includes (runtime.inc) which should only appear once
        at the end. Library files are compiled with emit_runtime=False
        so they don't include the runtime.

    Example merged output structure:
        ; =============================================================================
        ; Multi-file build - Merged assembly
        ; =============================================================================

        ; --- Begin: helper.asm (library) ---
        ; [helper functions without runtime]
        ; --- End: helper.asm ---

        ; --- Begin: math.asm (user) ---
        ; [user assembly code]
        ; --- End: math.asm ---

        ; --- Begin: main.asm (main with runtime) ---
        ; [entry point, main function, runtime]
        ; --- End: main.asm ---
    """
    merged_lines: list[str] = []

    # Header comment
    merged_lines.extend([
        "; =============================================================================",
        "; Multi-file build - Merged assembly",
        "; Generated by psbuild",
        "; =============================================================================",
        "",
    ])

    def append_file(file_path: Path, label: str, strip_includes: bool = False) -> None:
        """
        Append a file's contents with section markers.

        Args:
            file_path: Path to the assembly file
            label: Label for section markers (e.g., "library", "user assembly")
            strip_includes: If True, remove INCLUDE directives to avoid duplicates
                           when the main file will provide them.
        """
        merged_lines.append(f"; --- Begin: {file_path.name} ({label}) ---")
        merged_lines.append("")

        content = file_path.read_text(encoding='utf-8')
        lines = content.rstrip().split('\n')

        # Filter lines for non-main files
        if label != "main with runtime":
            filtered_lines = []
            for line in lines:
                stripped = line.strip().upper()
                # Skip END directive (we'll add one at the end)
                if stripped.startswith('END'):
                    continue
                # Skip INCLUDE directives to avoid duplicates
                # The main file will provide psion.inc, runtime.inc, etc.
                if strip_includes and stripped.startswith('INCLUDE'):
                    # Add comment showing what was stripped
                    filtered_lines.append(f"; [stripped: {line.strip()}]")
                    continue
                filtered_lines.append(line)
            lines = filtered_lines

        merged_lines.extend(lines)
        merged_lines.append("")
        merged_lines.append(f"; --- End: {file_path.name} ---")
        merged_lines.append("")

    # 1. Library assembly files (from C compiled in library mode)
    # Strip INCLUDEs since main file will provide them
    for lib_asm in library_asm_files:
        if verbose:
            click.echo(f"      Adding {lib_asm.name} (library)")
        append_file(lib_asm, "library", strip_includes=True)

    # 2. User-provided assembly files
    # Strip INCLUDEs since main file will provide them
    for user_asm in user_asm_files:
        if verbose:
            click.echo(f"      Adding {user_asm.name} (user assembly)")
        append_file(user_asm, "user assembly", strip_includes=True)

    # 3. Main assembly file (with runtime)
    if main_asm_file is not None:
        if verbose:
            click.echo(f"      Adding {main_asm_file.name} (main with runtime)")
        # For main file, include the END directive
        merged_lines.append(f"; --- Begin: {main_asm_file.name} (main with runtime) ---")
        merged_lines.append("")
        content = main_asm_file.read_text(encoding='utf-8')
        merged_lines.append(content.rstrip())
        merged_lines.append("")
        merged_lines.append(f"; --- End: {main_asm_file.name} ---")
    else:
        # Assembly-only build: user assembly files are already added
        # Add a final END if needed
        if not any("END" in line.upper() for line in merged_lines[-20:]):
            merged_lines.append("        END")

    # Write merged assembly
    output_file.write_text('\n'.join(merged_lines) + '\n', encoding='utf-8')

    if verbose:
        click.echo(f"      Merged {len(library_asm_files) + len(user_asm_files) + (1 if main_asm_file else 0)} files")


# =============================================================================
# Include Path Resolution
# =============================================================================

def find_sdk_include_dir() -> Optional[Path]:
    """
    Find the SDK's include directory relative to this module's location.

    The include directory contains essential header files:
    - psion.h: C function prototypes
    - psion.inc: Assembly macros and constants
    - runtime.inc: C runtime library implementation
    - syscalls.inc: OS system call definitions
    - sysvars.inc: System variable addresses

    Returns:
        Path to the include directory if found, None otherwise.

    Directory Structure:
        This module: src/psion_sdk/cli/psbuild.py
        Include dir: include/

        Navigation: psbuild.py → cli/ → psion_sdk/ → src/ → project root → include/
                    (4 levels up from this file)
    """
    # Navigate from this file to the project root
    # Path: src/psion_sdk/cli/psbuild.py
    #       ↑     ↑          ↑     ↑
    #       4     3          2     1 (levels from __file__)
    project_root = Path(__file__).parent.parent.parent.parent
    include_dir = project_root / "include"

    if include_dir.exists() and include_dir.is_dir():
        return include_dir

    return None


def build_include_paths(
    user_includes: tuple[Path, ...],
    source_files: list[Path],
) -> list[str]:
    """
    Build the complete list of include search paths.

    The search order is important for correct file resolution:
    1. User-specified paths (-I flags) - highest priority
    2. Source files' directories - for relative includes (in order, deduplicated)
    3. SDK include directory - for standard headers

    For multi-file builds, directories from all source files are included
    to support relative includes between files in different directories.

    Args:
        user_includes: Paths specified via -I flags
        source_files: List of source files being compiled/assembled

    Returns:
        List of include path strings in search order.

    Example:
        >>> paths = build_include_paths(
        ...     (Path("/usr/include"),),
        ...     [Path("src/main.c"), Path("lib/util.c")]
        ... )
        >>> # Returns: ["/usr/include", "src", "lib", "<sdk>/include"]
    """
    paths: list[str] = []

    # 1. User-specified include paths (preserve order)
    for p in user_includes:
        path_str = str(p)
        if path_str not in paths:
            paths.append(path_str)

    # 2. Source files' parent directories (for relative includes)
    # Add each unique directory, preserving order of first occurrence
    for source_file in source_files:
        source_dir = str(source_file.parent.resolve())
        if source_dir not in paths:
            paths.append(source_dir)

    # 3. SDK include directory (auto-detected)
    sdk_include = find_sdk_include_dir()
    if sdk_include and str(sdk_include) not in paths:
        paths.append(str(sdk_include))

    return paths


# =============================================================================
# Source Type Detection
# =============================================================================

def detect_source_type(source_file: Path) -> str:
    """
    Detect the source file type based on extension.

    Args:
        source_file: Path to the source file

    Returns:
        "c" for C sources, "asm" for assembly sources

    Raises:
        click.BadParameter: If the extension is not recognized
    """
    suffix = source_file.suffix.lower()

    if suffix in C_EXTENSIONS:
        return "c"
    elif suffix in ASM_EXTENSIONS:
        return "asm"
    else:
        raise click.BadParameter(
            f"Unrecognized source file extension: '{suffix}'. "
            f"Expected .c for C or .asm/.s for assembly.",
            param_hint="INPUT_FILE"
        )


# =============================================================================
# Output Path Resolution
# =============================================================================

def sanitize_procedure_name(name: str) -> str:
    """
    Sanitize a name to be a valid Psion procedure name.

    Psion procedure names must be:
    - 1-8 characters long
    - Alphanumeric only (A-Z, 0-9)
    - Start with a letter

    This function:
    - Converts to uppercase
    - Removes invalid characters (underscores, etc.)
    - Truncates to 8 characters
    - Ensures it starts with a letter

    Args:
        name: The raw name to sanitize

    Returns:
        A valid Psion procedure name

    Raises:
        click.BadParameter: If the name cannot be sanitized to a valid name

    Examples:
        "hello"      → "HELLO"
        "my_prog"    → "MYPROG"
        "test123"    → "TEST123"
        "123test"    → Error (starts with digit)
        "very_long_name" → "VERYLONG"
    """
    # Convert to uppercase and remove non-alphanumeric characters
    sanitized = "".join(c for c in name.upper() if c.isalnum())

    # Check if empty after sanitization
    if not sanitized:
        raise click.BadParameter(
            f"Cannot derive a valid procedure name from '{name}'. "
            f"The name must contain at least one alphanumeric character.",
            param_hint="INPUT_FILE or -o/--output"
        )

    # Ensure it starts with a letter
    if not sanitized[0].isalpha():
        raise click.BadParameter(
            f"Cannot derive a valid procedure name from '{name}'. "
            f"Psion procedure names must start with a letter (A-Z), "
            f"but '{sanitized}' starts with '{sanitized[0]}'.",
            param_hint="INPUT_FILE or -o/--output"
        )

    # Truncate to 8 characters
    sanitized = sanitized[:8]

    return sanitized


def resolve_output_path(
    output: Optional[Path],
    source_file: Path,
) -> Path:
    """
    Determine the output OPK file path.

    If no output is specified, derives the name from the source file:
    - Uses uppercase filename (Psion convention)
    - Removes invalid characters (underscores become nothing)
    - Replaces extension with .opk
    - Places in current working directory

    Args:
        output: User-specified output path (may be None)
        source_file: The input source file

    Returns:
        Resolved output path for the OPK file.

    Examples:
        hello.c     → HELLO.opk
        my_prog.asm → MYPROG.opk (underscore removed)
    """
    if output is not None:
        return output

    # Derive from source filename, sanitized for Psion
    proc_name = sanitize_procedure_name(source_file.stem)
    return Path.cwd() / f"{proc_name}.opk"


def derive_procedure_name(output_opk: Path) -> str:
    """
    Derive the procedure name from the output OPK path.

    The procedure name is the OPK filename (without extension), sanitized
    to be a valid Psion procedure name.

    Args:
        output_opk: Path to the output OPK file

    Returns:
        Valid Psion procedure name (1-8 chars, alphanumeric, starts with letter)

    Raises:
        click.BadParameter: If the name cannot be sanitized
    """
    return sanitize_procedure_name(output_opk.stem)


# =============================================================================
# Pipeline Stages
# =============================================================================

def compile_c_to_asm(
    source_file: Path,
    output_asm: Path,
    include_paths: list[str],
    model: Optional[str],
    verbose: bool,
    step_label: str = "[1/3]",
    emit_runtime: bool = True,
) -> None:
    """
    Compile C source to HD6303 assembly using pscc.

    This function compiles a single C source file to assembly. It supports
    both normal mode (with runtime) and library mode (without runtime).

    Args:
        source_file: Path to the .c file
        output_asm: Path for the output .asm file
        include_paths: List of include search directories
        model: Target model (CM, XP, LZ, etc.) or None for default
        verbose: If True, print detailed progress
        step_label: Step label for verbose output (e.g., "[1/3]")
        emit_runtime: If True, emit runtime includes and entry point.
                     Set to False for library mode in multi-file builds.

    Raises:
        SmallCError: If compilation fails

    Notes:
        Library mode (emit_runtime=False) produces assembly that:
        - Has no _entry point (no BSR _main / RTS wrapper)
        - Omits INCLUDE "runtime.inc" (runtime code)
        - Still includes psion.inc (EQU constants are idempotent)
        - Contains function definitions ready for linking

    Example:
        # Normal compilation (single-file or main file)
        compile_c_to_asm(main_c, main_asm, paths, "XP", True)

        # Library mode (helper file in multi-file build)
        compile_c_to_asm(helper_c, helper_asm, paths, "XP", True,
                         step_label="[1/5]", emit_runtime=False)
    """
    mode_desc = "normal" if emit_runtime else "library"

    if verbose:
        click.echo(f"{step_label} Compiling {source_file.name} → {output_asm.name} ({mode_desc})")
        click.echo(f"      Model: {model or 'XP (default)'}")
        if not emit_runtime:
            click.echo("      Mode: library (no runtime, no entry point)")

    # Create compiler options
    # model=None means "use pragma or default (XP)"
    # emit_runtime=False enables library mode for multi-file linking
    options = CompilerOptions(
        include_paths=include_paths,
        output_comments=verbose,
        target_model=model.upper() if model else None,
        emit_runtime=emit_runtime,
    )

    # Read source and compile
    source = source_file.read_text(encoding='utf-8')
    compiler = SmallCCompiler(options)
    result = compiler.compile_source(source, str(source_file))

    # Write assembly output
    output_asm.write_text(result.assembly, encoding='utf-8')

    if verbose:
        click.echo(f"      Generated {len(result.assembly)} bytes of assembly")


def assemble_to_ob3(
    source_asm: Path,
    output_ob3: Path,
    include_paths: list[str],
    model: Optional[str],
    relocatable: bool,
    optimize: bool,
    verbose: bool,
) -> None:
    """
    Assemble HD6303 source to OB3 object file using psasm.

    Args:
        source_asm: Path to the .asm file
        output_ob3: Path for the output .ob3 file
        include_paths: List of include search directories
        model: Target model (CM, XP, LZ, etc.) or None for default
        relocatable: If True, generate self-relocating code
        optimize: If True, enable peephole optimization
        verbose: If True, print detailed progress

    Raises:
        AssemblerError: If assembly fails
    """
    # Determine step number based on whether we're building from C or asm
    # (This is for display purposes in verbose mode)
    step = "2/3" if relocatable else "1/2"  # C pipeline vs asm pipeline

    if verbose:
        click.echo(f"[{step}] Assembling {source_asm.name} → {output_ob3.name}")
        click.echo(f"      Relocatable: {relocatable}")
        click.echo(f"      Optimization: {'enabled' if optimize else 'disabled'}")

    # Create assembler instance
    asm = Assembler(
        verbose=False,  # We handle our own verbosity
        relocatable=relocatable,
        target_model=model.upper() if model else None,
        optimize=optimize,
    )

    # Add include paths
    for path in include_paths:
        asm.add_include_path(Path(path))

    # Assemble
    asm.assemble_file(source_asm)

    # Write OB3 output
    asm.write_ob3(output_ob3)

    if verbose:
        code_size = len(asm.get_code())
        click.echo(f"      Generated {code_size} bytes of object code")

        # Show relocation info if applicable
        if relocatable:
            fixup_count = asm.get_fixup_count()
            click.echo(f"      Relocations: {fixup_count} fixups")


def package_to_opk(
    ob3_file: Path,
    output_opk: Path,
    verbose: bool,
    from_c: bool,
) -> None:
    """
    Package OB3 file into OPK pack file using psopk.

    Args:
        ob3_file: Path to the .ob3 file
        output_opk: Path for the output .opk file
        verbose: If True, print detailed progress
        from_c: True if building from C (affects step numbering)

    Raises:
        OPKError: If packaging fails
    """
    step = "3/3" if from_c else "2/2"

    if verbose:
        click.echo(f"[{step}] Packaging {ob3_file.name} → {output_opk.name}")

    # Validate OB3 file
    ob3_data = ob3_file.read_bytes()
    if not validate_ob3(ob3_data):
        raise OPKError(f"Invalid OB3 file: {ob3_file}")

    # Create pack builder (default 32KB datapak)
    builder = PackBuilder(size_kb=32)
    builder.add_ob3_file(ob3_file)

    # Check space (shouldn't be an issue for 32KB but good practice)
    if builder.get_free_bytes() < 0:
        used = builder.get_used_bytes()
        raise OPKError(
            f"Program too large: {used} bytes exceeds pack capacity. "
            f"The program may need optimization to fit."
        )

    # Build and write
    bytes_written = builder.build_to_file(output_opk)

    if verbose:
        proc_name = builder.list_procedures()[0]
        click.echo(f"      Procedure: {proc_name}")
        click.echo(f"      Pack size: {bytes_written} bytes")


# =============================================================================
# CLI Definition
# =============================================================================

@click.command()
@click.argument(
    "input_files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output OPK file (default: derived from first input file, uppercase)",
)
@click.option(
    "-m", "--model",
    type=click.Choice(VALID_MODELS, case_sensitive=False),
    default=None,
    help="Target Psion model. 2-line: CM, XP, LA. 4-line: LZ, LZ64. "
         "PORTABLE: runs on any model. Default: XP.",
)
@click.option(
    "-I", "--include",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Add include search path (can be repeated). "
         "The SDK include/ directory is added automatically.",
)
@click.option(
    "-r", "--relocatable",
    is_flag=True,
    default=False,
    help="Generate self-relocating code for assembly sources. "
         "(Always enabled for C sources, this flag is for .asm files only)",
)
@click.option(
    "-k", "--keep",
    is_flag=True,
    help="Keep intermediate files (.asm, .ob3, merged.asm) instead of cleaning up",
)
@click.option(
    "-O", "--optimize/--no-optimize",
    default=True,
    help="Enable/disable peephole optimization. Default: enabled.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Show detailed progress for each build stage",
)
@click.version_option(version=__version__, prog_name="psbuild")
def main(
    input_files: tuple[Path, ...],
    output: Optional[Path],
    model: Optional[str],
    include: tuple[Path, ...],
    relocatable: bool,
    keep: bool,
    optimize: bool,
    verbose: bool,
) -> None:
    """
    Build a Psion Organiser II program from C or assembly source(s).

    INPUT_FILES are the source file(s) to build (.c and/or .asm).
    Multiple files are linked together at the assembly level.

    This tool combines pscc, psasm, and psopk into a single command,
    automatically detecting the source type and running the appropriate
    build pipeline.

    \b
    Single-file builds:
        psbuild hello.c -o HELLO.opk
        psbuild hello.asm -o HELLO.opk

    \b
    Multi-file builds (C with assembly helpers):
        psbuild main.c helpers.asm -o MYAPP.opk

        The C file's functions can call assembly routines directly.
        Assembly files should export labels with underscores (_myhelper).

    \b
    Multi-file builds (multiple C files):
        psbuild main.c utils.c math.c -o MYAPP.opk

        Exactly one C file must contain main(). Other C files are
        compiled in "library mode" (no runtime, no entry point).
        Functions call each other using extern declarations.

    \b
    Examples:
        psbuild hello.c                       # Single C file → HELLO.opk
        psbuild hello.c -o myapp.opk          # Custom output name
        psbuild -m LZ hello.c                 # Target 4-line display
        psbuild -v hello.c                    # Verbose output
        psbuild -k hello.c                    # Keep intermediate files
        psbuild -r hello.asm                  # Assembly with relocation
        psbuild main.c util.c -o APP.opk      # Multiple C files
        psbuild main.c fast.asm -o APP.opk    # C with assembly helpers

    \b
    Notes:
        - C sources (.c) always use -r (relocatable) mode
        - For multi-file C builds, exactly one file must contain main()
        - Assembly helpers should use C calling convention (args at 4,X)
        - The SDK include directory is found automatically

    \b
    Multi-file linking order:
        1. Library C files (compiled without runtime)
        2. User assembly files (in command-line order)
        3. Main C file (with entry point and runtime)

        This ensures forward references work and runtime is included once.
    """
    try:
        # =====================================================================
        # Step 1: Validate inputs and classify files
        # =====================================================================
        if not input_files:
            raise click.BadParameter(
                "At least one input file is required.",
                param_hint="INPUT_FILES"
            )

        # Classify input files by type
        classified = classify_input_files(input_files)

        # Resolve output path (default: derive from first input file)
        first_input = classified.all_files[0]
        output_opk = resolve_output_path(output, first_input)

        # Build include paths from all source file directories
        include_paths = build_include_paths(include, classified.all_files)

        # Determine if this is a multi-file build
        is_multi_file = classified.is_multi_file

        if verbose:
            if is_multi_file:
                click.echo(f"Multi-file build: {len(classified.all_files)} input files")
                click.echo(f"  C files: {', '.join(f.name for f in classified.c_files) or 'none'}")
                click.echo(f"  ASM files: {', '.join(f.name for f in classified.asm_files) or 'none'}")
            else:
                source_type = "C" if classified.has_c_files else "ASM"
                click.echo(f"Building {first_input} ({source_type} source)")
            click.echo(f"Output: {output_opk}")
            click.echo(f"Model: {model or 'XP (default)'}")
            click.echo(f"Include paths:")
            for p in include_paths:
                click.echo(f"  - {p}")
            click.echo()

        # =====================================================================
        # Step 2: Create temporary directory for intermediate files
        # =====================================================================
        # We use a context manager to ensure cleanup even on errors
        # (unless -k/--keep is specified)

        with tempfile.TemporaryDirectory(prefix="psbuild_") as temp_dir:
            temp_path = Path(temp_dir)

            # Derive procedure name from output OPK
            proc_name = derive_procedure_name(output_opk)

            # Intermediate file paths
            temp_ob3 = temp_path / f"{proc_name}.ob3"  # MUST be uppercase for psopk

            # =================================================================
            # Step 3: Handle single-file vs multi-file builds
            # =================================================================

            if not is_multi_file:
                # -------------------------------------------------------------
                # SINGLE-FILE BUILD (original behavior)
                # -------------------------------------------------------------
                source_type = detect_source_type(first_input)
                temp_asm = temp_path / f"{proc_name.lower()}.asm"

                # For C sources, relocatable is always enabled
                use_relocatable = True if source_type == "c" else relocatable

                if source_type == "c":
                    # C pipeline: pscc → psasm → psopk
                    compile_c_to_asm(
                        source_file=first_input,
                        output_asm=temp_asm,
                        include_paths=include_paths,
                        model=model,
                        verbose=verbose,
                        step_label="[1/3]",
                        emit_runtime=True,
                    )

                    assemble_to_ob3(
                        source_asm=temp_asm,
                        output_ob3=temp_ob3,
                        include_paths=include_paths,
                        model=model,
                        relocatable=True,
                        optimize=optimize,
                        verbose=verbose,
                    )

                    package_to_opk(
                        ob3_file=temp_ob3,
                        output_opk=output_opk,
                        verbose=verbose,
                        from_c=True,
                    )

                else:
                    # Assembly pipeline: psasm → psopk
                    assemble_to_ob3(
                        source_asm=first_input,
                        output_ob3=temp_ob3,
                        include_paths=include_paths,
                        model=model,
                        relocatable=use_relocatable,
                        optimize=optimize,
                        verbose=verbose,
                    )

                    package_to_opk(
                        ob3_file=temp_ob3,
                        output_opk=output_opk,
                        verbose=verbose,
                        from_c=False,
                    )

                # Keep intermediate files if requested
                if keep:
                    output_dir = output_opk.parent
                    if source_type == "c" and temp_asm.exists():
                        keep_asm = output_dir / f"{proc_name.lower()}.asm"
                        keep_asm.write_text(temp_asm.read_text(encoding='utf-8'), encoding='utf-8')
                        if verbose:
                            click.echo(f"Kept: {keep_asm}")
                    if temp_ob3.exists():
                        keep_ob3 = output_dir / f"{proc_name}.ob3"
                        keep_ob3.write_bytes(temp_ob3.read_bytes())
                        if verbose:
                            click.echo(f"Kept: {keep_ob3}")

            else:
                # -------------------------------------------------------------
                # MULTI-FILE BUILD
                # -------------------------------------------------------------
                # This is a multi-file build. The process is:
                # 1. Find which C file contains main()
                # 2. Compile non-main C files in library mode
                # 3. Compile main C file with runtime
                # 4. Concatenate all assembly (libraries first, main last)
                # 5. Assemble merged assembly
                # 6. Package to OPK

                library_asm_files: list[Path] = []  # From library-mode C compilation
                main_asm_file: Optional[Path] = None  # From main C compilation

                # Calculate total steps for progress display
                # Steps: detect main + compile each C file + concatenate + assemble + package
                total_steps = 1 + len(classified.c_files) + 1 + 1 + 1
                current_step = 0

                def step_label() -> str:
                    """Generate step label like [1/7]."""
                    return f"[{current_step}/{total_steps}]"

                # ---------------------------------------------------------
                # Step 3a: Find the main file (for C builds)
                # ---------------------------------------------------------
                main_c_file: Optional[Path] = None
                library_c_files: list[Path] = []

                if classified.has_c_files:
                    current_step += 1
                    if verbose:
                        click.echo(f"{step_label()} Detecting main() function...")

                    main_result = find_main_file(
                        classified.c_files,
                        include_paths,
                        verbose=verbose,
                    )

                    if not main_result.found:
                        raise click.BadParameter(
                            main_result.error or "Could not determine main file",
                            param_hint="INPUT_FILES"
                        )

                    main_c_file = main_result.main_file
                    library_c_files = main_result.library_c_files

                    if verbose:
                        click.echo(f"      Main file: {main_c_file.name}")
                        if library_c_files:
                            lib_names = ", ".join(f.name for f in library_c_files)
                            click.echo(f"      Library files: {lib_names}")
                        click.echo()

                # ---------------------------------------------------------
                # Step 3b: Compile library C files (emit_runtime=False)
                # ---------------------------------------------------------
                for lib_c in library_c_files:
                    current_step += 1
                    lib_asm = temp_path / f"{lib_c.stem.lower()}_lib.asm"

                    compile_c_to_asm(
                        source_file=lib_c,
                        output_asm=lib_asm,
                        include_paths=include_paths,
                        model=model,
                        verbose=verbose,
                        step_label=step_label(),
                        emit_runtime=False,  # Library mode
                    )

                    library_asm_files.append(lib_asm)

                # ---------------------------------------------------------
                # Step 3c: Compile main C file (emit_runtime=True)
                # ---------------------------------------------------------
                if main_c_file is not None:
                    current_step += 1
                    main_asm_file = temp_path / f"{main_c_file.stem.lower()}_main.asm"

                    compile_c_to_asm(
                        source_file=main_c_file,
                        output_asm=main_asm_file,
                        include_paths=include_paths,
                        model=model,
                        verbose=verbose,
                        step_label=step_label(),
                        emit_runtime=True,  # Full runtime
                    )

                # ---------------------------------------------------------
                # Step 3d: Concatenate assembly files
                # ---------------------------------------------------------
                current_step += 1
                merged_asm = temp_path / f"{proc_name.lower()}_merged.asm"

                if verbose:
                    click.echo(f"{step_label()} Merging assembly files...")

                concatenate_assembly_files(
                    library_asm_files=library_asm_files,
                    user_asm_files=classified.asm_files,
                    main_asm_file=main_asm_file,
                    output_file=merged_asm,
                    verbose=verbose,
                )

                if verbose:
                    click.echo()

                # ---------------------------------------------------------
                # Step 3e: Assemble merged assembly
                # ---------------------------------------------------------
                current_step += 1

                # Multi-file builds with C always use relocatable
                # (assembly-only multi-file respects -r flag)
                use_relocatable = True if classified.has_c_files else relocatable

                assemble_to_ob3(
                    source_asm=merged_asm,
                    output_ob3=temp_ob3,
                    include_paths=include_paths,
                    model=model,
                    relocatable=use_relocatable,
                    optimize=optimize,
                    verbose=verbose,
                )

                # ---------------------------------------------------------
                # Step 3f: Package to OPK
                # ---------------------------------------------------------
                current_step += 1

                package_to_opk(
                    ob3_file=temp_ob3,
                    output_opk=output_opk,
                    verbose=verbose,
                    from_c=classified.has_c_files,
                )

                # ---------------------------------------------------------
                # Step 3g: Keep intermediate files if requested
                # ---------------------------------------------------------
                if keep:
                    output_dir = output_opk.parent

                    # Keep individual C-compiled assembly files
                    for lib_asm in library_asm_files:
                        keep_path = output_dir / lib_asm.name
                        keep_path.write_text(lib_asm.read_text(encoding='utf-8'), encoding='utf-8')
                        if verbose:
                            click.echo(f"Kept: {keep_path}")

                    if main_asm_file and main_asm_file.exists():
                        keep_path = output_dir / main_asm_file.name
                        keep_path.write_text(main_asm_file.read_text(encoding='utf-8'), encoding='utf-8')
                        if verbose:
                            click.echo(f"Kept: {keep_path}")

                    # Keep merged assembly
                    if merged_asm.exists():
                        keep_merged = output_dir / f"{proc_name.lower()}_merged.asm"
                        keep_merged.write_text(merged_asm.read_text(encoding='utf-8'), encoding='utf-8')
                        if verbose:
                            click.echo(f"Kept: {keep_merged}")

                    # Keep OB3
                    if temp_ob3.exists():
                        keep_ob3 = output_dir / f"{proc_name}.ob3"
                        keep_ob3.write_bytes(temp_ob3.read_bytes())
                        if verbose:
                            click.echo(f"Kept: {keep_ob3}")

        # =====================================================================
        # Step 4: Report success
        # =====================================================================

        if verbose:
            click.echo()

        if is_multi_file:
            file_count = len(classified.all_files)
            click.echo(f"Built {output_opk} (from {file_count} source files)")
        else:
            click.echo(f"Built {output_opk}")

    except Exception as e:
        handle_cli_exception(e, verbose=verbose, error_type="Build")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
