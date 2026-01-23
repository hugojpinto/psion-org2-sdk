"""
psdisasm - HD6303/QCode Disassembler Command-Line Interface
============================================================

This module implements the command-line interface for the Psion Organiser II
disassembler. It can disassemble both HD6303 machine code and OPL QCode
bytecode.

Usage Examples
--------------
Disassemble machine code:
    $ psdisasm firmware.bin

With base address:
    $ psdisasm code.bin --address 0x8000

Limit number of instructions:
    $ psdisasm code.bin --count 20

Output to file:
    $ psdisasm code.bin -o listing.asm

Disassemble QCode:
    $ psdisasm qcode.bin --qcode

QCode with _call_opl buffer formatting:
    $ psdisasm buffer.bin --qcode --call-opl

Hex dump with disassembly:
    $ psdisasm code.bin --hex

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import sys
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.disassembler import HD6303Disassembler, QCodeDisassembler
from psion_sdk.disassembler.hd6303 import PSION_SYSTEM_SYMBOLS


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
    help="Output file (default: stdout)",
)
@click.option(
    "-a", "--address",
    type=str,
    default="0",
    help="Base address for disassembly (hex with 0x prefix or decimal). Default: 0",
)
@click.option(
    "-c", "--count",
    type=int,
    default=None,
    help="Maximum number of instructions to disassemble (default: all)",
)
@click.option(
    "-q", "--qcode",
    is_flag=True,
    help="Disassemble as OPL QCode bytecode instead of HD6303 machine code",
)
@click.option(
    "--call-opl",
    is_flag=True,
    help="Format output for _call_opl buffer analysis (implies --qcode)",
)
@click.option(
    "--hex",
    "show_hex",
    is_flag=True,
    help="Include hex dump before disassembly",
)
@click.option(
    "--no-bytes",
    is_flag=True,
    help="Omit raw bytes from output (show only mnemonic and operand)",
)
@click.option(
    "--symbols/--no-symbols",
    default=True,
    help="Include Psion system symbol annotations (default: enabled)",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output",
)
@click.version_option(version=__version__, prog_name="psdisasm")
def main(
    input_file: Path,
    output: Optional[Path],
    address: str,
    count: Optional[int],
    qcode: bool,
    call_opl: bool,
    show_hex: bool,
    no_bytes: bool,
    symbols: bool,
    verbose: bool,
) -> None:
    """
    Disassemble HD6303 machine code or OPL QCode.

    INPUT_FILE is the binary file to disassemble.

    By default, disassembles as HD6303 machine code. Use --qcode for OPL
    QCode bytecode.

    Examples:

        # Disassemble machine code at address $8000
        psdisasm code.bin --address 0x8000

        # Disassemble first 20 instructions
        psdisasm code.bin --count 20 -o listing.asm

        # Disassemble QCode
        psdisasm qcode.bin --qcode

        # Analyze _call_opl buffer
        psdisasm buffer.bin --call-opl
    """
    # Parse base address
    try:
        if address.lower().startswith("0x"):
            base_address = int(address, 16)
        elif address.startswith("$"):
            base_address = int(address[1:], 16)
        else:
            base_address = int(address)
    except ValueError:
        click.echo(f"Error: Invalid address '{address}'", err=True)
        sys.exit(1)

    if not 0 <= base_address <= 0xFFFF:
        click.echo(f"Error: Address must be 0-65535 (0x0000-0xFFFF)", err=True)
        sys.exit(1)

    # Read input file
    try:
        data = input_file.read_bytes()
    except IOError as e:
        click.echo(f"Error reading {input_file}: {e}", err=True)
        sys.exit(1)

    if len(data) == 0:
        click.echo(f"Error: {input_file} is empty", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Input file: {input_file} ({len(data)} bytes)", err=True)
        click.echo(f"Base address: ${base_address:04X}", err=True)

    # Build output
    output_lines = []

    # Header
    output_lines.append(f"; Disassembly of {input_file.name}")
    output_lines.append(f"; Size: {len(data)} bytes")
    output_lines.append(f"; Base address: ${base_address:04X}")
    if qcode or call_opl:
        output_lines.append("; Mode: QCode")
    else:
        output_lines.append("; Mode: HD6303")
    output_lines.append("")

    # Hex dump (if requested)
    if show_hex:
        output_lines.append("; Hex dump:")
        output_lines.append("; " + "-" * 60)
        for i in range(0, len(data), 16):
            addr = base_address + i
            chunk = data[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(
                chr(b) if 0x20 <= b < 0x7F else "."
                for b in chunk
            )
            output_lines.append(f"; ${addr:04X}: {hex_str:<48} {ascii_str}")
        output_lines.append("; " + "-" * 60)
        output_lines.append("")

    # Disassemble
    if call_opl or qcode:
        # QCode disassembly
        disasm = QCodeDisassembler()

        if call_opl:
            # Special _call_opl buffer formatting
            result = disasm.disassemble_call_opl_buffer(data, start_address=base_address)
            output_lines.append(result)
        else:
            # Normal QCode disassembly
            instructions = disasm.disassemble(data, start_address=base_address, count=count)
            for instr in instructions:
                output_lines.append(str(instr))
    else:
        # HD6303 disassembly
        if symbols:
            disasm = HD6303Disassembler(symbol_table=PSION_SYSTEM_SYMBOLS.copy())
        else:
            disasm = HD6303Disassembler()

        instructions = disasm.disassemble(data, start_address=base_address, count=count)

        for instr in instructions:
            if no_bytes:
                # Compact format
                if instr.operand_str:
                    line = f"${instr.address:04X}: {instr.mnemonic} {instr.operand_str}"
                else:
                    line = f"${instr.address:04X}: {instr.mnemonic}"
                if instr.comment:
                    line += f"  ; {instr.comment}"
                output_lines.append(line)
            else:
                # Full format with bytes
                output_lines.append(str(instr))

    # Write output
    result = "\n".join(output_lines) + "\n"

    if output:
        try:
            output.write_text(result, encoding='utf-8')
            if verbose:
                click.echo(f"Output written to: {output}", err=True)
        except IOError as e:
            click.echo(f"Error writing {output}: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(result, nl=False)

    if verbose:
        instr_count = len(instructions) if 'instructions' in dir() else "N/A"
        click.echo(f"Instructions disassembled: {instr_count}", err=True)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
