"""
psopk - OPK Pack Builder Command-Line Interface
=================================================

This module implements the command-line interface for the OPK pack builder.
It provides tools for creating, inspecting, and extracting Psion pack images.

Commands
--------
- **create**: Create a new OPK file from OB3 files
- **list**: List contents of an OPK file
- **info**: Show detailed pack information
- **extract**: Extract files from an OPK file
- **validate**: Validate an OPK file format

Usage Examples
--------------
Create a pack from OB3 files:
    $ psopk create -o hello.opk hello.ob3

Create a pack with multiple files:
    $ psopk create -o tools.opk -s 32 tool1.ob3 tool2.ob3 tool3.ob3

Create a Rampak image:
    $ psopk create -o data.opk -t rampak -s 16 program.ob3

List pack contents:
    $ psopk list mypack.opk

Show detailed information:
    $ psopk info mypack.opk

Extract all procedures:
    $ psopk extract -o ./output/ mypack.opk

Validate a pack file:
    $ psopk validate mypack.opk
"""

import sys
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.errors import OPKError, OPKFormatError, PackSizeError
from psion_sdk.opk import (
    PackBuilder,
    PackParser,
    PackType,
    PackSize,
    ProcedureRecord,
    DataFileRecord,
    validate_ob3,
    OB3File,
)


# =============================================================================
# Pack Type Parameter Type
# =============================================================================

class PackTypeChoice(click.ParamType):
    """
    Click parameter type for pack type selection.

    Accepts: datapak, rampak, flashpak (case-insensitive)
    """
    name = "pack_type"

    # Mapping of names to PackType values
    # Note: "datapak" uses DATAPAK_SIMPLE (0x4a) which works reliably with BOOT protocol
    TYPE_MAP = {
        "datapak": PackType.DATAPAK_SIMPLE,  # Default, works with BOOT protocol on real hardware
        "datapak_paged": PackType.DATAPAK_PAGED,  # JAPE format (0x46), for rampaks
        "rampak": PackType.RAMPAK,
        "flashpak": PackType.FLASHPAK,
        "datapak_linear": PackType.DATAPAK,  # Original linear addressing (0x56)
    }

    def convert(self, value: str, param: Optional[click.Parameter],
                ctx: Optional[click.Context]) -> PackType:
        """Convert string to PackType."""
        if isinstance(value, PackType):
            return value

        key = value.lower()
        if key not in self.TYPE_MAP:
            self.fail(
                f"Invalid pack type '{value}'. "
                f"Choose from: {', '.join(self.TYPE_MAP.keys())}",
                param, ctx
            )
        return self.TYPE_MAP[key]


PACK_TYPE = PackTypeChoice()


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.version_option(__version__, "--version", "-V", prog_name="psopk")
def main() -> None:
    """
    OPK Pack Builder for Psion Organiser II.

    Create, inspect, and extract Psion pack image files (.opk).

    \b
    Commands:
      create    Create new OPK from OB3 files
      list      List contents of OPK file
      info      Show detailed pack information
      extract   Extract files from OPK
      validate  Validate OPK file format

    \b
    Examples:
      psopk create -o hello.opk hello.ob3
      psopk list mypack.opk
      psopk info mypack.opk
      psopk extract -o ./output/ mypack.opk

    For more information: https://www.jaapsch.net/psion/fileform.htm
    """
    pass


# =============================================================================
# Create Command
# =============================================================================

@main.command("create")
@click.argument(
    "input_files",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output OPK file path (required)",
)
@click.option(
    "-s", "--size",
    type=click.Choice(["8", "16", "32", "64", "128"]),
    default="32",
    help="Pack size in KB (default: 32)",
)
@click.option(
    "-t", "--type",
    "pack_type",
    type=PACK_TYPE,
    default="datapak",
    help="Pack type: datapak, rampak, flashpak (default: datapak)",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output",
)
def cmd_create(
    input_files: tuple[Path, ...],
    output: Path,
    size: str,
    pack_type: PackType,
    verbose: bool,
) -> None:
    """
    Create a new OPK pack file from OB3 object files.

    INPUT_FILES are one or more OB3 files to include in the pack.
    Each OB3 file becomes a procedure named after the filename.

    \b
    Examples:
      psopk create -o hello.opk hello.ob3
      psopk create -o tools.opk -s 32 tool1.ob3 tool2.ob3
      psopk create -o ram.opk -t rampak -s 16 program.ob3
    """
    try:
        size_kb = int(size)

        if verbose:
            click.echo(f"Creating {size_kb}KB {pack_type.get_description()}")

        # Create builder
        builder = PackBuilder(size_kb=size_kb, pack_type=pack_type)

        # Add each OB3 file
        for ob3_path in input_files:
            if verbose:
                click.echo(f"  Adding {ob3_path.name}...")

            # Validate OB3 file first
            data = ob3_path.read_bytes()
            if not validate_ob3(data):
                raise OPKFormatError(f"Invalid OB3 file: {ob3_path}")

            builder.add_ob3_file(ob3_path)

        # Check if we have any content
        if builder.get_record_count() == 0:
            click.echo("Error: No procedures to add to pack", err=True)
            sys.exit(1)

        # Check space
        if builder.get_free_bytes() < 0:
            used = builder.get_used_bytes()
            max_size = size_kb * 1024
            click.echo(
                f"Error: Pack data ({used} bytes) exceeds "
                f"pack size ({max_size} bytes)",
                err=True
            )
            click.echo(f"Hint: Try a larger pack size (-s 32, -s 64, etc.)", err=True)
            sys.exit(1)

        # Build and write
        bytes_written = builder.build_to_file(output)

        # Summary
        procedures = builder.list_procedures()
        used = builder.get_used_bytes()
        free = builder.get_free_bytes()

        if verbose:
            click.echo(f"Created {output}")
            click.echo(f"  Procedures: {len(procedures)}")
            for name in procedures:
                click.echo(f"    - {name}")
            click.echo(f"  Size: {bytes_written} bytes written")
            click.echo(f"  Used: {used} bytes ({100*used//(size_kb*1024)}%)")
            click.echo(f"  Free: {free} bytes")
        else:
            click.echo(f"Created {output} ({len(procedures)} procedures, {bytes_written} bytes)")

    except PackSizeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except OPKError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# =============================================================================
# List Command
# =============================================================================

@main.command("list")
@click.argument(
    "opk_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Show more details",
)
def cmd_list(opk_file: Path, verbose: bool) -> None:
    """
    List contents of an OPK pack file.

    \b
    Example:
      psopk list mypack.opk

    \b
    Output format:
      NAME     Type       Size
      HELLO    Procedure  256 bytes
      UTILS    Procedure  1024 bytes
    """
    try:
        parser = PackParser.from_file(opk_file)

        # Print header
        if verbose:
            click.echo(f"Contents of {opk_file}:")
            click.echo("-" * 40)

        # Table header
        click.echo(f"{'Name':<10} {'Type':<12} {'Size':>10}")
        click.echo("-" * 34)

        # List all records
        for record in parser.records:
            if isinstance(record, ProcedureRecord):
                size_str = f"{len(record.object_code)} bytes"
                click.echo(f"{record.name:<10} {'Procedure':<12} {size_str:>10}")
            elif isinstance(record, DataFileRecord):
                click.echo(f"{record.name:<10} {'Data File':<12} {'':>10}")
            else:
                type_name = f"0x{record.record_type:02X}"
                click.echo(f"{'':10} {type_name:<12} {'':>10}")

        # Summary
        if verbose:
            click.echo("-" * 34)
            click.echo(f"Total: {len(parser.records)} records")
            click.echo(f"Used: {parser.get_used_bytes()} bytes")
            click.echo(f"Free: {parser.get_free_bytes()} bytes")

    except OPKError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Info Command
# =============================================================================

@main.command("info")
@click.argument(
    "opk_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def cmd_info(opk_file: Path) -> None:
    """
    Show detailed information about an OPK pack file.

    \b
    Example:
      psopk info mypack.opk

    \b
    Output includes:
      - Pack type and size
      - Creation timestamp
      - Checksum information
      - Record counts
      - Space usage
    """
    try:
        parser = PackParser.from_file(opk_file)
        info = parser.get_info()

        click.echo(f"Pack Information: {opk_file}")
        click.echo("=" * 40)
        click.echo(f"Pack Type:   {info['pack_type']}")
        click.echo(f"Size:        {info['size_kb']} KB")
        click.echo(f"Created:     {info['timestamp']}")
        click.echo(f"Checksum:    {info['checksum']}")
        click.echo()
        click.echo("Contents:")
        click.echo(f"  Procedures:  {info['procedure_count']}")
        click.echo(f"  Data Files:  {info['data_file_count']}")
        click.echo(f"  Total:       {info['total_records']} records")
        click.echo()
        click.echo("Space Usage:")
        total = info['size_kb'] * 1024
        used = info['used_bytes']
        free = info['free_bytes']
        percent = (used * 100) // total if total > 0 else 0
        click.echo(f"  Used:        {used} bytes ({percent}%)")
        click.echo(f"  Free:        {free} bytes ({100-percent}%)")

        # Verify checksum
        if parser.header:
            from psion_sdk.opk.checksum import calculate_pack_checksum
            pack_data = parser.data[6:]
            records_data = pack_data[10:]
            calculated = calculate_pack_checksum(records_data)
            if calculated == parser.header.checksum:
                click.echo(f"\nChecksum:    Valid")
            else:
                click.echo(f"\nChecksum:    MISMATCH (calculated: 0x{calculated:04X})")

    except OPKError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Extract Command
# =============================================================================

@main.command("extract")
@click.argument(
    "opk_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o", "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("."),
    help="Output directory (default: current directory)",
)
@click.option(
    "-n", "--name",
    help="Extract only this procedure (by name)",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output",
)
def cmd_extract(
    opk_file: Path,
    output: Path,
    name: Optional[str],
    verbose: bool,
) -> None:
    """
    Extract files from an OPK pack.

    By default, extracts all procedures as OB3 files.
    Use --name to extract a specific procedure.

    \b
    Examples:
      psopk extract -o ./output/ mypack.opk
      psopk extract -n HELLO mypack.opk
    """
    try:
        # Ensure output directory exists
        output.mkdir(parents=True, exist_ok=True)

        parser = PackParser.from_file(opk_file)

        if name:
            # Extract specific procedure
            name = name.upper()
            record = parser.get_procedure(name)
            if record is None:
                click.echo(f"Error: Procedure '{name}' not found in pack", err=True)
                click.echo(f"Available procedures: {', '.join(parser.list_procedures())}", err=True)
                sys.exit(1)

            out_path = output / f"{name.lower()}.ob3"
            _write_ob3(record, out_path)
            click.echo(f"Extracted {name} to {out_path}")
        else:
            # Extract all procedures
            count = 0
            for record in parser.iter_procedures():
                out_path = output / f"{record.name.lower()}.ob3"
                _write_ob3(record, out_path)
                if verbose:
                    click.echo(f"  {record.name} -> {out_path}")
                count += 1

            if count == 0:
                click.echo("No procedures found in pack")
            else:
                click.echo(f"Extracted {count} procedures to {output}")

    except OPKError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _write_ob3(record: ProcedureRecord, path: Path) -> None:
    """Write a procedure record to an OB3 file."""
    ob3 = OB3File(
        object_code=record.object_code,
        source_code=record.source_code
    )
    path.write_bytes(ob3.to_bytes())


# =============================================================================
# Validate Command
# =============================================================================

@main.command("validate")
@click.argument(
    "opk_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Show validation details",
)
def cmd_validate(opk_file: Path, verbose: bool) -> None:
    """
    Validate an OPK pack file format.

    Checks:
    - Magic number
    - Length consistency
    - Header checksum
    - Record structure

    \b
    Example:
      psopk validate mypack.opk
    """
    try:
        data = opk_file.read_bytes()
        errors = []
        warnings = []

        # Check minimum size
        if len(data) < 16:
            errors.append(f"File too small ({len(data)} bytes, minimum 16)")

        # Check magic number
        if data[0:3] != b"OPK":
            errors.append(f"Invalid magic number: {data[0:3]!r}")

        # Check length
        if len(data) >= 6:
            declared_len = (data[3] << 16) | (data[4] << 8) | data[5]
            if declared_len + 6 != len(data) and declared_len + 8 != len(data):
                warnings.append(
                    f"Length mismatch: declared {declared_len}, "
                    f"file size {len(data)}"
                )

        # Parse and validate structure
        if not errors:
            try:
                parser = PackParser.from_file(opk_file)

                if verbose:
                    click.echo("Validation Details:")
                    click.echo(f"  Magic number: OK")
                    click.echo(f"  Pack header: OK")
                    click.echo(f"  Records parsed: {len(parser.records)}")

                # Verify checksum
                if parser.header:
                    from psion_sdk.opk.checksum import calculate_pack_checksum
                    pack_data = data[6:]
                    records_data = pack_data[10:]
                    calculated = calculate_pack_checksum(records_data)
                    if calculated != parser.header.checksum:
                        warnings.append(
                            f"Checksum mismatch: header 0x{parser.header.checksum:04X}, "
                            f"calculated 0x{calculated:04X}"
                        )
                    elif verbose:
                        click.echo(f"  Header checksum: OK (0x{calculated:04X})")

                # Validate records
                for i, record in enumerate(parser.records):
                    if isinstance(record, ProcedureRecord):
                        if not record.validate_name():
                            warnings.append(
                                f"Record {i}: Invalid procedure name '{record.name}'"
                            )

            except OPKError as e:
                errors.append(f"Parse error: {e}")

        # Report results
        if errors:
            click.echo("Validation FAILED:")
            for error in errors:
                click.echo(f"  ERROR: {error}")
            sys.exit(1)
        elif warnings:
            click.echo("Validation passed with warnings:")
            for warning in warnings:
                click.echo(f"  WARNING: {warning}")
            click.echo("\nFile is usable but may have minor issues.")
        else:
            click.echo(f"Validation PASSED: {opk_file}")
            if verbose:
                click.echo("All checks passed successfully.")

    except Exception as e:
        click.echo(f"Validation ERROR: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
