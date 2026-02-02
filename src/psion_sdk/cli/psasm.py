"""
psasm - HD6303 Assembler Command-Line Interface
=================================================

This module implements the command-line interface for the HD6303 assembler.
It provides a user-friendly interface for assembling Psion Organiser II
programs from the terminal.

Usage Examples
--------------
Basic assembly:
    $ psasm hello.asm

With output file:
    $ psasm hello.asm -o hello.ob3

Generate all output files:
    $ psasm hello.asm -o hello.ob3 -l hello.lst -s hello.sym

With include path and defines:
    $ psasm -I ./include -D DEBUG=1 program.asm

Verbose mode:
    $ psasm -v hello.asm
"""

from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.assembler import Assembler
from psion_sdk.cli.errors import handle_cli_exception


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
    help="Output OB3 file (default: input.ob3)",
)
@click.option(
    "-l", "--listing",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generate listing file",
)
@click.option(
    "-s", "--symbols",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generate symbol file",
)
@click.option(
    "-b", "--binary",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generate raw binary output (machine code only, no wrapper)",
)
@click.option(
    "-p", "--proc",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generate procedure output (OPL wrapper, no OB3 header)",
)
@click.option(
    "-I", "--include",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Add include search path (can be repeated)",
)
@click.option(
    "-D", "--define",
    multiple=True,
    help="Define symbol (format: NAME=VALUE)",
)
@click.option(
    "-r", "--relocatable",
    is_flag=True,
    help="Generate self-relocating code with position-independent stub",
)
@click.option(
    "-m", "--model",
    type=click.Choice(["CM", "XP", "LA", "LZ", "LZ64", "PORTABLE"], case_sensitive=False),
    default=None,
    help="Target Psion model. 2-line: CM, XP, LA. 4-line: LZ, LZ64. "
         "PORTABLE: runs on any model. Default: XP. Overrides .MODEL directive. "
         "See dev_docs/TARGET_MODELS.md for details.",
)
@click.option(
    "-O", "--optimize/--no-optimize",
    default=True,
    help="Enable/disable peephole optimization. Default: enabled. "
         "Optimizations include: LDAA #0→CLRA, ADDA #1→INCA, removing "
         "redundant push/pull pairs, etc.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "-g", "--debug",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generate debug symbol file (.dbg) with symbol addresses and source mappings",
)
@click.version_option(version=__version__, prog_name="psasm")
def main(
    input_file: Path,
    output: Optional[Path],
    listing: Optional[Path],
    symbols: Optional[Path],
    binary: Optional[Path],
    proc: Optional[Path],
    include: tuple[Path, ...],
    define: tuple[str, ...],
    relocatable: bool,
    model: Optional[str],
    optimize: bool,
    verbose: bool,
    debug: Optional[Path],
) -> None:
    """
    Assemble HD6303 source code for Psion Organiser II.

    INPUT_FILE is the assembly source file (.asm) to assemble.

    The assembler produces a Psion-compatible OB3 object file that can
    be packaged into an OPK file for transfer to the device.

    \b
    Examples:
        psasm hello.asm              # Outputs hello.ob3
        psasm hello.asm -o out.ob3   # Specify output file
        psasm -I inc/ hello.asm      # Add include path
        psasm -D DEBUG=1 hello.asm   # Define symbol

    For more information about HD6303 assembly language:
    https://www.jaapsch.net/psion/mcmnemal.htm
    """
    # Check for mutually exclusive output options
    output_options = sum([output is not None, binary is not None, proc is not None])
    if output_options > 1:
        click.echo("Error: -o/--output, -b/--binary, and -p/--proc are mutually exclusive", err=True)
        sys.exit(1)

    # Determine output mode and filename
    if binary is not None:
        output_mode = "binary"
        output_file = binary
    elif proc is not None:
        output_mode = "proc"
        output_file = proc
    else:
        output_mode = "ob3"
        output_file = output if output is not None else input_file.with_suffix(".ob3")

    # Create assembler with optional target model and debug support
    asm = Assembler(
        verbose=verbose,
        relocatable=relocatable,
        target_model=model.upper() if model else None,
        optimize=optimize,
        debug=debug is not None,  # Enable debug if output path specified
    )

    if verbose:
        target = model.upper() if model else "XP (default)"
        click.echo(f"Target model: {target}")
        if relocatable:
            click.echo("Relocatable mode enabled: output will include self-relocating stub")
        if optimize:
            click.echo("Peephole optimization: enabled")
        else:
            click.echo("Peephole optimization: disabled")
        if debug:
            click.echo(f"Debug symbols: {debug}")

    # Add include paths
    for inc_path in include:
        asm.add_include_path(inc_path)

    # Parse and add defines
    for defn in define:
        if "=" in defn:
            name, value_str = defn.split("=", 1)
            try:
                # Parse value (support hex with $ or 0x prefix)
                value_str = value_str.strip()
                if value_str.startswith("$"):
                    value = int(value_str[1:], 16)
                elif value_str.startswith("0x") or value_str.startswith("0X"):
                    value = int(value_str[2:], 16)
                else:
                    value = int(value_str)
                asm.define_symbol(name.strip(), value)
            except ValueError:
                click.echo(f"Error: invalid value in -D {defn}", err=True)
                sys.exit(1)
        else:
            # Symbol without value defaults to 1
            asm.define_symbol(defn.strip(), 1)

    # Assemble
    try:
        if verbose:
            click.echo(f"Assembling {input_file}...")

        asm.assemble_file(input_file)

        # Check for errors
        if asm.has_errors():
            click.echo(asm.get_error_report(), err=True)
            sys.exit(1)

        # Write primary output file based on mode
        if output_mode == "binary":
            asm.write_binary(output_file)
            if verbose:
                code = asm.get_code()
                click.echo(f"Wrote {len(code)} bytes raw binary to {output_file}")
        elif output_mode == "proc":
            asm.write_proc(output_file)
            if verbose:
                click.echo(f"Wrote procedure (OPL wrapper) to {output_file}")
        else:
            asm.write_ob3(output_file)
            if verbose:
                code = asm.get_code()
                click.echo(f"Wrote {len(code)} bytes to {output_file}")

        # Write optional auxiliary files
        if listing:
            asm.write_listing(listing)
            if verbose:
                click.echo(f"Wrote listing to {listing}")

        if symbols:
            asm.write_symbols(symbols)
            if verbose:
                click.echo(f"Wrote symbols to {symbols}")

        if debug:
            asm.write_debug(debug)
            if verbose:
                click.echo(f"Wrote debug symbols to {debug}")

        # Print summary
        if verbose:
            origin = asm.get_origin()
            code = asm.get_code()
            sym_count = len(asm.get_symbols())
            click.echo(f"Assembly complete: {len(code)} bytes at ${origin:04X}")
            click.echo(f"Defined {sym_count} symbols")

            # Print relocation info if enabled
            if asm.is_relocatable():
                fixup_count = asm.get_fixup_count()
                # Stub is 93 bytes, fixup table is 2 + (2 * count) bytes
                stub_size = 93
                table_size = 2 + (2 * fixup_count)
                overhead = stub_size + table_size
                click.echo(f"Relocation: {fixup_count} fixups, {overhead} bytes overhead")

            # Print optimization stats if available
            opt_stats = asm.get_optimization_stats()
            if opt_stats and opt_stats.total_optimizations > 0:
                click.echo(f"Optimizations: {opt_stats.total_optimizations} applied in {opt_stats.total_passes} pass(es)")

    except Exception as e:
        handle_cli_exception(e, verbose=verbose, error_type="Assembly")


if __name__ == "__main__":
    main()
