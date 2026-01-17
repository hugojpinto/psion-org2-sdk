"""
pscc - Small-C Compiler Command-Line Interface
==============================================

This module implements the command-line interface for the Small-C compiler.
It provides a user-friendly interface for compiling C programs for the
Psion Organiser II from the terminal.

Usage Examples
--------------
Basic compilation:
    $ pscc hello.c

With output file:
    $ pscc hello.c -o hello.asm

With include path:
    $ pscc -I ./include hello.c

Full pipeline to OPK:
    $ pscc hello.c -o hello.asm && psasm hello.asm && psopk hello.ob3

Verbose mode:
    $ pscc -v hello.c
"""

import sys
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.smallc import SmallCCompiler, CompilerOptions
from psion_sdk.smallc.errors import SmallCError


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
    help="Output assembly file (default: input.asm)",
)
@click.option(
    "-I", "--include",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Add include search path (can be repeated)",
)
@click.option(
    "-E", "--preprocess-only",
    is_flag=True,
    help="Preprocess only, output to stdout",
)
@click.option(
    "--ast",
    is_flag=True,
    help="Print AST and exit (for debugging)",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "-m", "--model",
    type=click.Choice(["CM", "XP", "LA", "LZ", "LZ64", "PORTABLE"], case_sensitive=False),
    default=None,
    help="Target Psion model. 2-line: CM, XP, LA. 4-line: LZ, LZ64. "
         "PORTABLE: runs on any model. Default: XP. Overrides #pragma. "
         "See dev_docs/TARGET_MODELS.md for details.",
)
@click.version_option(version=__version__, prog_name="pscc")
def main(
    input_file: Path,
    output: Optional[Path],
    include: tuple[Path, ...],
    preprocess_only: bool,
    ast: bool,
    verbose: bool,
    model: Optional[str],
) -> None:
    """
    Compile Small-C source code for Psion Organiser II.

    INPUT_FILE is the C source file (.c) to compile.

    The compiler produces HD6303 assembly code that can be assembled
    using psasm, then packaged into an OPK file for transfer to the device.

    \b
    Examples:
        pscc hello.c                 # Outputs hello.asm
        pscc hello.c -o out.asm      # Specify output file
        pscc -I inc/ hello.c         # Add include path
        pscc -E hello.c              # Preprocess only
        pscc -v hello.c              # Verbose output

    \b
    Supported C features:
        - int, char types (16-bit and 8-bit)
        - Pointers and arrays
        - if/else, while, for, do-while, switch
        - Functions with parameters and local variables
        - #define and #include preprocessor

    For more information about Small-C:
    https://en.wikipedia.org/wiki/Small-C
    """
    # Determine output filename
    if output is None:
        output = input_file.with_suffix(".asm")

    # Build include paths
    include_paths = [str(p) for p in include]

    # Add default include paths
    sdk_include = Path(__file__).parent.parent.parent.parent / "include"
    if sdk_include.exists():
        include_paths.append(str(sdk_include))

    # Add source file directory
    include_paths.insert(0, str(input_file.parent))

    # Create compiler options
    # model=None means "use pragma or default (XP)"
    options = CompilerOptions(
        include_paths=include_paths,
        output_comments=verbose,
        target_model=model.upper() if model else None,
    )

    try:
        # Read source file
        if verbose:
            click.echo(f"Compiling {input_file}...")
            model_str = model.upper() if model else "XP (default, or from #pragma)"
            click.echo(f"Target model: {model_str}")
            click.echo(f"Include paths: {', '.join(include_paths)}")

        source = input_file.read_text()

        # Create compiler
        compiler = SmallCCompiler(options)

        # Preprocess only mode
        if preprocess_only:
            from psion_sdk.smallc.preprocessor import Preprocessor
            pp = Preprocessor(source, str(input_file), include_paths)
            preprocessed = pp.process()
            click.echo(preprocessed)
            return

        # Compile
        result = compiler.compile_source(source, str(input_file))

        # AST dump mode
        if ast:
            from psion_sdk.smallc.ast import ASTPrinter
            printer = ASTPrinter()
            click.echo(printer.print(result.ast))
            return

        # Write output
        output.write_text(result.assembly)

        if verbose:
            click.echo(f"Wrote {len(result.assembly)} bytes to {output}")
            click.echo(f"Tokenized: {result.token_count} tokens")
            if result.ast:
                decl_count = len(result.ast.declarations)
                click.echo(f"Parsed: {decl_count} declarations")

        # Print success message
        click.echo(f"Compiled {input_file} -> {output}")

    except SmallCError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Internal error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
