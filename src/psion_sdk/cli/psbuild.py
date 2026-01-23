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

Pipeline Architecture
---------------------
For C sources (.c):

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  .c file │────▶│ .asm file│────▶│ .ob3 file│────▶│ .opk file│
    │ (source) │pscc │  (temp)  │psasm│  (temp)  │psopk│ (output) │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘

For assembly sources (.asm):

    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ .asm file│────▶│ .ob3 file│────▶│ .opk file│
    │ (source) │psasm│  (temp)  │psopk│ (output) │
    └──────────┘     └──────────┘     └──────────┘

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
"""

import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.smallc import SmallCCompiler, CompilerOptions
from psion_sdk.smallc.errors import SmallCError
from psion_sdk.assembler import Assembler
from psion_sdk.errors import PsionError, OPKError
from psion_sdk.opk import PackBuilder, validate_ob3


# =============================================================================
# Constants
# =============================================================================

# Supported source file extensions (lowercase for comparison)
C_EXTENSIONS = frozenset({".c"})
ASM_EXTENSIONS = frozenset({".asm", ".s"})

# Valid target models (same as pscc and psasm)
VALID_MODELS = ("CM", "XP", "LA", "LZ", "LZ64", "PORTABLE")


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
    source_file: Path,
) -> list[str]:
    """
    Build the complete list of include search paths.

    The search order is important for correct file resolution:
    1. User-specified paths (-I flags) - highest priority
    2. Source file's directory - for relative includes
    3. SDK include directory - for standard headers

    Args:
        user_includes: Paths specified via -I flags
        source_file: The source file being compiled/assembled

    Returns:
        List of include path strings in search order.
    """
    paths: list[str] = []

    # 1. User-specified include paths (preserve order)
    for p in user_includes:
        paths.append(str(p))

    # 2. Source file's parent directory (for relative includes)
    source_dir = source_file.parent.resolve()
    if str(source_dir) not in paths:
        paths.append(str(source_dir))

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
) -> None:
    """
    Compile C source to HD6303 assembly using pscc.

    Args:
        source_file: Path to the .c file
        output_asm: Path for the output .asm file
        include_paths: List of include search directories
        model: Target model (CM, XP, LZ, etc.) or None for default
        verbose: If True, print detailed progress

    Raises:
        SmallCError: If compilation fails
    """
    if verbose:
        click.echo(f"[1/3] Compiling {source_file.name} → {output_asm.name}")
        click.echo(f"      Model: {model or 'XP (default)'}")
        click.echo(f"      Include paths: {', '.join(include_paths)}")

    # Create compiler options
    # model=None means "use pragma or default (XP)"
    options = CompilerOptions(
        include_paths=include_paths,
        output_comments=verbose,
        target_model=model.upper() if model else None,
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
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output OPK file (default: INPUT.opk in current directory, uppercase)",
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
    help="Keep intermediate files (.asm, .ob3) instead of cleaning up",
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
    input_file: Path,
    output: Optional[Path],
    model: Optional[str],
    include: tuple[Path, ...],
    relocatable: bool,
    keep: bool,
    optimize: bool,
    verbose: bool,
) -> None:
    """
    Build a Psion Organiser II program from C or assembly source.

    INPUT_FILE is the source file to build (.c or .asm).

    This tool combines pscc, psasm, and psopk into a single command,
    automatically detecting the source type and running the appropriate
    build pipeline.

    \b
    For C sources (.c):
        psbuild hello.c -o HELLO.opk

        Pipeline: hello.c → hello.asm → HELLO.ob3 → HELLO.opk
        Note: -r (relocatable) is always enabled for C programs.

    \b
    For assembly sources (.asm):
        psbuild hello.asm -o HELLO.opk

        Pipeline: hello.asm → HELLO.ob3 → HELLO.opk
        Use -r if your assembly uses internal symbol references.

    \b
    Examples:
        psbuild hello.c                    # → HELLO.opk
        psbuild hello.c -o myapp.opk       # Custom output name
        psbuild -m LZ hello.c              # Target 4-line display
        psbuild -v hello.c                 # Verbose output
        psbuild -k hello.c                 # Keep intermediate files
        psbuild -r hello.asm               # Assembly with relocation

    \b
    The SDK include directory is found automatically, so you don't need
    to specify -I include explicitly (though you still can for additional
    include paths).
    """
    try:
        # =====================================================================
        # Step 1: Detect source type and resolve paths
        # =====================================================================
        source_type = detect_source_type(input_file)
        output_opk = resolve_output_path(output, input_file)
        include_paths = build_include_paths(include, input_file)

        # For C sources, relocatable is always enabled
        # For assembly sources, respect the user's choice
        use_relocatable = True if source_type == "c" else relocatable

        if verbose:
            click.echo(f"Building {input_file} ({source_type.upper()} source)")
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

            # Derive procedure name from output OPK (this determines the name
            # in the pack). The OB3 filename MUST match the desired procedure
            # name because psopk derives the procedure name from the OB3 filename.
            proc_name = derive_procedure_name(output_opk)

            # Intermediate file names use the procedure name (uppercase, valid)
            # Assembly file can keep original case for readability
            temp_asm = temp_path / f"{proc_name.lower()}.asm"
            temp_ob3 = temp_path / f"{proc_name}.ob3"  # MUST be uppercase for psopk

            # =================================================================
            # Step 3: Run the appropriate pipeline
            # =================================================================

            if source_type == "c":
                # C pipeline: pscc → psasm → psopk

                # Stage 1: Compile C to assembly
                compile_c_to_asm(
                    source_file=input_file,
                    output_asm=temp_asm,
                    include_paths=include_paths,
                    model=model,
                    verbose=verbose,
                )

                # Stage 2: Assemble to OB3 (always relocatable for C)
                assemble_to_ob3(
                    source_asm=temp_asm,
                    output_ob3=temp_ob3,
                    include_paths=include_paths,
                    model=model,
                    relocatable=True,  # Always for C
                    optimize=optimize,
                    verbose=verbose,
                )

                # Stage 3: Package to OPK
                package_to_opk(
                    ob3_file=temp_ob3,
                    output_opk=output_opk,
                    verbose=verbose,
                    from_c=True,
                )

            else:
                # Assembly pipeline: psasm → psopk

                # Stage 1: Assemble to OB3
                assemble_to_ob3(
                    source_asm=input_file,
                    output_ob3=temp_ob3,
                    include_paths=include_paths,
                    model=model,
                    relocatable=use_relocatable,
                    optimize=optimize,
                    verbose=verbose,
                )

                # Stage 2: Package to OPK
                package_to_opk(
                    ob3_file=temp_ob3,
                    output_opk=output_opk,
                    verbose=verbose,
                    from_c=False,
                )

            # =================================================================
            # Step 4: Handle intermediate files
            # =================================================================

            if keep:
                # Copy intermediate files to output directory
                # Use procedure name for consistency with OPK contents
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

        # =====================================================================
        # Step 5: Report success
        # =====================================================================

        if verbose:
            click.echo()
        click.echo(f"Built {output_opk}")

    except SmallCError as e:
        # Compilation error (C → ASM stage)
        click.echo(f"Compilation error: {e}", err=True)
        sys.exit(1)

    except PsionError as e:
        # Assembly or packaging error
        click.echo(f"Build error: {e}", err=True)
        sys.exit(1)

    except click.BadParameter as e:
        # Invalid arguments
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    except Exception as e:
        # Unexpected error - show traceback in verbose mode
        click.echo(f"Internal error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
