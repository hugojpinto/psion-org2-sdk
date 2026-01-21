"""
pslink - Serial Transfer Command-Line Interface
=================================================

This module implements the command-line interface for the serial
transfer tool. It transfers files between PC and Psion Organiser II
using the Psion Link Protocol and FTRAN file transfer protocol.

Protocol Architecture
---------------------
**Important**: The FTRAN protocol operates in server-client mode where
the Psion acts as client and the PC acts as server:

- **Psion RECEIVE mode**: Psion requests files from PC. The PC waits
  for the request and serves the file content.

- **Psion SEND mode**: Psion pushes files to PC. The PC receives and
  acknowledges each data packet.

Usage Examples
--------------
List available serial ports:
    $ pslink ports

Send a file to the Psion (serve mode):
    $ pslink send program.opl
    # Then on Psion: COMMS > RECEIVE > enter "PROGRAM.OPL"

Receive a file from the Psion:
    $ pslink receive output.bin
    # Then on Psion: COMMS > SEND > select file

List files on a Psion pack:
    $ pslink list B:
    # Psion must be in COMMS > TRANSMIT mode

Hardware Setup
--------------
Before using pslink, ensure:
1. The Psion Comms Link is connected to the serial port
2. The serial port has proper permissions (dialout group on Linux)
3. The Psion is in the appropriate COMMS mode

The baud rate must match the Psion's settings (default 9600).

Exit Codes
----------
0 - Success
1 - Connection or transfer error
2 - Invalid arguments or configuration error
"""

import logging
from pathlib import Path
from typing import Optional

import click

from psion_sdk import __version__
from psion_sdk.comms import (
    DEFAULT_BAUD_RATE,
    VALID_BAUD_RATES,
    FileTransfer,
    FileType,
    LinkProtocol,
    OpenMode,
    close_serial_port,
    find_psion_port,
    format_port_list,
    list_serial_ports,
    open_serial_port,
    BootTransfer,
)
from psion_sdk.errors import CommsError, ConnectionError, TransferError

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# CLI Context and Utilities
# =============================================================================

class Context:
    """
    Shared context for CLI commands.

    Stores common options like port, baud rate, and verbosity.
    """

    def __init__(self) -> None:
        self.port: Optional[str] = None
        self.baud: int = DEFAULT_BAUD_RATE
        self.verbose: bool = False
        self.timeout: float = 30.0

    def setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(levelname)s: %(message)s" if self.verbose else "%(message)s",
        )


pass_context = click.make_pass_decorator(Context, ensure=True)


def progress_bar(current: int, total: int) -> None:
    """Simple text progress bar for file transfers."""
    if total == 0:
        return
    percent = current * 100 // total
    filled = percent // 2
    bar = "=" * filled + "-" * (50 - filled)
    click.echo(f"\r[{bar}] {percent:3d}% ({current}/{total} bytes)", nl=False)
    if current >= total:
        click.echo()  # Newline at end


def progress_unknown(current: int) -> None:
    """Progress indicator when total is unknown."""
    click.echo(f"\rReceived: {current} bytes", nl=False)


def convert_opl_line_endings(data: bytes) -> bytes:
    """
    Convert OPL line endings from NULL to CRLF.

    OPL files on the Psion use NULL (0x00) as line terminators.
    The original CommsLink software converts these to CRLF (0x0d 0x0a)
    when receiving files, making them compatible with PC text editors.

    Args:
        data: Raw OPL file data with NULL line terminators

    Returns:
        Data with CRLF line endings
    """
    return data.replace(b"\x00", b"\r\n")


def convert_pc_line_endings(data: bytes) -> bytes:
    """
    Convert PC line endings from CRLF to NULL for Psion.

    When sending OPL files to the Psion, CRLF (0x0d 0x0a) line endings
    must be converted back to NULL (0x00) terminators.

    Args:
        data: File data with CRLF line endings

    Returns:
        Data with NULL line terminators for Psion
    """
    return data.replace(b"\r\n", b"\x00")


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.option(
    "-p", "--port",
    type=str,
    default=None,
    help="Serial port device (auto-detect if not specified)",
)
@click.option(
    "-b", "--baud",
    type=click.Choice([str(b) for b in VALID_BAUD_RATES]),
    default=str(DEFAULT_BAUD_RATE),
    help=f"Baud rate (default: {DEFAULT_BAUD_RATE})",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds (default: 30)",
)
@click.version_option(version=__version__, prog_name="pslink")
@pass_context
def main(ctx: Context, port: Optional[str], baud: str, verbose: bool, timeout: float) -> None:
    """
    Transfer files to/from Psion Organiser II via serial connection.

    The Psion Link Protocol uses a server-client model where the Psion
    initiates all file transfer requests.

    For SENDING files to Psion:
      1. Run: pslink send myfile.opl
      2. On Psion: COMMS > RECEIVE > enter filename

    For RECEIVING files from Psion:
      1. Run: pslink receive
      2. On Psion: COMMS > SEND > select file

    Use 'pslink ports' to list available serial ports.
    """
    ctx.port = port
    ctx.baud = int(baud)
    ctx.verbose = verbose
    ctx.timeout = timeout
    ctx.setup_logging()


# =============================================================================
# Ports Command
# =============================================================================

@main.command()
@click.option(
    "--detailed", "-d",
    is_flag=True,
    help="Show detailed port information",
)
@pass_context
def ports(ctx: Context, detailed: bool) -> None:
    """
    List available serial ports.

    Shows all serial ports detected on the system. USB-serial adapters
    are marked with their vendor (e.g., FTDI, Silicon Labs).

    Example:
        pslink ports
        pslink ports --detailed
    """
    port_list = list_serial_ports()

    if not port_list:
        click.echo("No serial ports found.")
        click.echo("\nTips:")
        click.echo("  - Connect your USB-serial adapter")
        click.echo("  - On Linux, ensure you have permission (dialout group)")
        return

    click.echo("Available serial ports:")
    click.echo(format_port_list(port_list, verbose=detailed))

    # Try auto-detection
    auto_port = find_psion_port()
    if auto_port:
        click.echo(f"\nSuggested port for Psion: {auto_port}")
    else:
        click.echo("\nNo USB-serial adapter auto-detected.")


# =============================================================================
# List Command
# =============================================================================

@main.command("list")
@click.argument("device", default="B:")
@pass_context
def list_files(ctx: Context, device: str) -> None:
    """
    List files on a Psion device/pack.

    DEVICE is the pack or internal memory to list:
      A: - Internal memory
      B: - Pack slot B (default)
      C: - Pack slot C
      M: - Main device

    Example:
        pslink list B:
        pslink list --port /dev/ttyUSB0 A:

    Before running, start COMMS > TRANSMIT on the Psion.
    """
    # Get port (auto-detect if not specified)
    port_device = ctx.port or find_psion_port()
    if not port_device:
        click.echo("Error: No serial port specified and auto-detect failed.")
        click.echo("Use --port option or 'pslink ports' to find available ports.")
        raise SystemExit(1)

    # Ensure device format
    if not device.endswith(':'):
        device += ':'

    try:
        click.echo(f"Connecting to Psion on {port_device}...")
        serial_port = open_serial_port(port_device, baud_rate=ctx.baud)

        try:
            link = LinkProtocol(serial_port)
            click.echo("Waiting for Psion... (start COMMS > TRANSMIT on device)")
            link.connect(timeout=ctx.timeout)

            transfer = FileTransfer(link)
            files = transfer.list_directory(device)

            click.echo(f"\nFiles on {device}")
            click.echo("-" * 40)
            if files:
                for name in files:
                    click.echo(f"  {name}")
                click.echo("-" * 40)
                click.echo(f"{len(files)} file(s)")
            else:
                click.echo("  (empty)")

            link.disconnect()

        finally:
            close_serial_port(serial_port)

    except ConnectionError as e:
        click.echo(f"Connection error: {e}")
        raise SystemExit(1)
    except TransferError as e:
        click.echo(f"Transfer error: {e}")
        raise SystemExit(1)
    except CommsError as e:
        click.echo(f"Communication error: {e}")
        raise SystemExit(1)


# =============================================================================
# Send Command (Server Mode)
# =============================================================================

@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--name", "-n",
    type=str,
    default=None,
    help="Filename for Psion (default: derived from file, max 8 chars)",
)
@click.option(
    "--opl/--odb", "is_opl",
    default=True,
    help="File type: --opl for program files (default), --odb for data files",
)
@pass_context
def send(ctx: Context, file: str, name: Optional[str], is_opl: bool) -> None:
    """
    Send a file to the Psion device.

    This command serves a file to the Psion. The Psion initiates the
    transfer by requesting the file, so you must:

    1. Run this command first
    2. On Psion: COMMS > RECEIVE > enter the filename

    FILE is the local file to send.

    The filename for Psion is derived from the local file unless
    you specify --name. Psion filenames are max 8 characters.

    Example:
        pslink send program.opl
        pslink send hello.opl --name HELLO
        pslink send data.odb --odb

    Workflow:
        $ pslink send myprogram.opl
        Connecting to Psion on /dev/tty.usbserial-110...
        Ready to serve: MYPROGRA (1234 bytes)

        On Psion: COMMS > RECEIVE > enter "MYPROGRA.OPL"

        Waiting for Psion to request file...
        [==================================] 100% (1234/1234 bytes)
        Transfer complete!
    """
    # Get port (auto-detect if not specified)
    port_device = ctx.port or find_psion_port()
    if not port_device:
        click.echo("Error: No serial port specified and auto-detect failed.")
        click.echo("Use --port option or 'pslink ports' to find available ports.")
        raise SystemExit(1)

    # Read local file
    file_path = Path(file)
    try:
        data = file_path.read_bytes()
    except IOError as e:
        click.echo(f"Error reading file: {e}")
        raise SystemExit(2)

    # Determine filename for Psion
    if name:
        psion_name = name[:8].upper()
    else:
        psion_name = file_path.stem[:8].upper()

    # Determine file type
    file_type = FileType.OPL if is_opl else FileType.ODB
    ext = ".OPL" if is_opl else ".ODB"

    # Convert line endings for OPL files (CRLF -> NULL)
    if is_opl and b"\r\n" in data:
        original_size = len(data)
        data = convert_pc_line_endings(data)
        click.echo(f"Converted line endings (CRLF -> NULL): {original_size} -> {len(data)} bytes")

    click.echo(f"Connecting to Psion on {port_device}...")

    try:
        serial_port = open_serial_port(port_device, baud_rate=ctx.baud)

        try:
            link = LinkProtocol(serial_port)

            click.echo("")
            click.echo("=" * 60)
            click.echo(f"Ready to serve: {psion_name} ({len(data)} bytes)")
            click.echo("")
            click.echo(f"On Psion: COMMS > RECEIVE > enter \"{psion_name}{ext}\"")
            click.echo("=" * 60)
            click.echo("")

            click.echo("Waiting for Psion...")
            transfer = FileTransfer(link)
            transfer.serve_file(
                psion_name,
                data,
                file_type=file_type,
                progress=progress_bar,
            )

            click.echo("")
            click.echo("Transfer complete!")

        finally:
            close_serial_port(serial_port)

    except ConnectionError as e:
        click.echo(f"\nConnection error: {e}")
        raise SystemExit(1)
    except TransferError as e:
        click.echo(f"\nTransfer error: {e}")
        raise SystemExit(1)
    except CommsError as e:
        click.echo(f"\nCommunication error: {e}")
        raise SystemExit(1)


# =============================================================================
# Receive Command
# =============================================================================

@main.command()
@click.argument("output", type=click.Path(dir_okay=False), required=False)
@click.option(
    "--simple", "-s",
    is_flag=True,
    help="Use single-connection mode (skip existence check handling)",
)
@click.option(
    "--raw", "-r",
    is_flag=True,
    help="Save raw data without line ending conversion (default: convert NULL to CRLF)",
)
@pass_context
def receive(ctx: Context, output: Optional[str], simple: bool, raw: bool) -> None:
    """
    Receive a file from the Psion device.

    The Psion initiates the transfer by sending the file, so you must:

    1. Run this command first
    2. On Psion: COMMS > SEND > select file to send

    OUTPUT is the local filename to save to (optional). If not specified,
    the filename sent by Psion is used.

    The standard protocol uses two connections:
    - First: Psion checks if file exists (you'll see "Waiting for confirmation")
    - Then: User confirms on Psion, actual transfer happens

    Use --simple to skip this and expect only one connection.

    By default, OPL files are converted from Psion format (NULL line terminators)
    to PC format (CRLF line endings). Use --raw to skip this conversion and
    save the raw data exactly as received.

    Example:
        pslink receive
        pslink receive myfile.opl
        pslink receive --simple myfile.opl
        pslink receive --raw myfile.opl

    Workflow:
        $ pslink receive
        Connecting to Psion on /dev/tty.usbserial-110...

        On Psion: COMMS > SEND > select file

        Waiting for Psion to send file...
        Received: 1234 bytes
        Saved to: MYFILE.opl
    """
    # Get port (auto-detect if not specified)
    port_device = ctx.port or find_psion_port()
    if not port_device:
        click.echo("Error: No serial port specified and auto-detect failed.")
        click.echo("Use --port option or 'pslink ports' to find available ports.")
        raise SystemExit(1)

    click.echo(f"Connecting to Psion on {port_device}...")

    try:
        serial_port = open_serial_port(port_device, baud_rate=ctx.baud)

        try:
            link = LinkProtocol(serial_port)

            click.echo("")
            click.echo("=" * 60)
            click.echo("On Psion: COMMS > SEND > select file to send")
            click.echo("=" * 60)
            click.echo("")

            click.echo("Waiting for Psion...")
            transfer = FileTransfer(link)

            if simple:
                filename, data = transfer.receive_file_simple(
                    progress=progress_unknown,
                )
            else:
                click.echo("(Psion may ask 'File exists. Overwrite?' - confirm on device)")
                filename, data = transfer.receive_file(
                    progress=progress_unknown,
                )

            click.echo()  # Newline after progress
            click.echo(f"Received: {filename} ({len(data)} bytes)")

            # Determine output filename
            if output is None:
                output = f"{filename.lower()}.opl"

            # Convert line endings for OPL files unless --raw specified
            output_path = Path(output)
            is_opl = output_path.suffix.lower() in (".opl", "")
            if is_opl and not raw:
                data = convert_opl_line_endings(data)
                click.echo(f"Converted line endings (NULL -> CRLF): {len(data)} bytes")

            # Write to local file
            output_path.write_bytes(data)
            click.echo(f"Saved to: {output_path}")

        finally:
            close_serial_port(serial_port)

    except ConnectionError as e:
        click.echo(f"\nConnection error: {e}")
        raise SystemExit(1)
    except TransferError as e:
        click.echo(f"\nTransfer error: {e}")
        raise SystemExit(1)
    except CommsError as e:
        click.echo(f"\nCommunication error: {e}")
        raise SystemExit(1)
    except IOError as e:
        click.echo(f"\nError writing file: {e}")
        raise SystemExit(2)


# =============================================================================
# Flash Command (Pack Flashing via BOOT Protocol)
# =============================================================================

@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--no-prompt", "-y",
    is_flag=True,
    help="Skip the prompt to insert pack (continue automatically)",
)
@pass_context
def flash(ctx: Context, file: str, no_prompt: bool) -> None:
    """
    Flash an OPK pack image directly to a Psion datapak/rampack.

    This command uses the BOOT protocol to transfer a pack image
    directly to a pack slot, essentially "flashing" the pack.

    FILE is the OPK file to flash.

    The BOOT protocol is a two-phase process:
    1. Bootloader uploads to Psion RAM
    2. Pack image data transfers to the datapak

    Before running:
    1. Run this command on PC
    2. On Psion: COMMS > BOOT > press EXE (name can be empty)
    3. Wait for "Making a pack" message on Psion
    4. Insert empty datapak/rampack in slot C when prompted
    5. Transfer completes

    Example:
        pslink flash program.opk
        pslink flash --no-prompt program.opk

    Workflow:
        $ pslink flash myprogram.opk
        Connecting to Psion on /dev/tty.usbserial-110...

        On Psion: COMMS > BOOT > press EXE

        Waiting for Psion to enter BOOT mode...
        Phase 1: Uploading bootloader...
        [==================================] 100% (3367/3367 bytes)

        Insert empty datapak/rampack in slot C, then press Enter...

        Phase 2: Sending pack data...
        [==================================] 100% (1234/1234 bytes)

        Transfer complete! Pack is ready to use.
    """
    # Get port (auto-detect if not specified)
    port_device = ctx.port or find_psion_port()
    if not port_device:
        click.echo("Error: No serial port specified and auto-detect failed.")
        click.echo("Use --port option or 'pslink ports' to find available ports.")
        raise SystemExit(1)

    # Read OPK file
    file_path = Path(file)
    try:
        opk_data = file_path.read_bytes()
    except IOError as e:
        click.echo(f"Error reading file: {e}")
        raise SystemExit(2)

    # Validate OPK
    if len(opk_data) < 6:
        click.echo("Error: File too small to be a valid OPK")
        raise SystemExit(2)

    if opk_data[:4] != b'OPK\x00':
        click.echo("Error: Invalid OPK file (missing OPK signature)")
        raise SystemExit(2)

    pack_size = len(opk_data) - 6  # Size after header
    click.echo(f"Connecting to Psion on {port_device}...")
    click.echo(f"OPK file: {file_path.name} ({len(opk_data)} bytes, pack image: {pack_size} bytes)")

    def user_prompt() -> bool:
        """Prompt user to insert pack."""
        if no_prompt:
            click.echo("\nContinuing automatically (--no-prompt)...")
            return True
        click.echo("")
        click.echo("=" * 60)
        click.echo("Insert empty datapak/rampack in slot C on the Psion")
        click.echo("=" * 60)
        try:
            input("Press Enter to continue (Ctrl+C to abort)...")
            return True
        except KeyboardInterrupt:
            click.echo("\nAborted by user")
            return False

    try:
        serial_port = open_serial_port(port_device, baud_rate=ctx.baud)

        try:
            link = LinkProtocol(serial_port)

            click.echo("")
            click.echo("=" * 60)
            click.echo("On Psion: COMMS > BOOT > press EXE (name can be empty)")
            click.echo("=" * 60)
            click.echo("")

            click.echo("Waiting for Psion to enter BOOT mode...")

            boot_transfer = BootTransfer(link)
            boot_transfer.flash_pack(
                opk_data,
                progress=progress_bar,
                user_prompt=user_prompt,
            )

            click.echo("")
            click.echo("Transfer complete! Pack is ready to use.")

        finally:
            close_serial_port(serial_port)

    except ConnectionError as e:
        click.echo(f"\nConnection error: {e}")
        raise SystemExit(1)
    except TransferError as e:
        click.echo(f"\nTransfer error: {e}")
        raise SystemExit(1)
    except CommsError as e:
        click.echo(f"\nCommunication error: {e}")
        raise SystemExit(1)


# =============================================================================
# Run Command (Future)
# =============================================================================

@main.command()
@click.argument("procedure")
@pass_context
def run(ctx: Context, procedure: str) -> None:
    """
    Run a procedure on the Psion device.

    PROCEDURE is the name of the procedure to execute (e.g., B:HELLO).

    Note: This command requires the Psion to be in a specific state
    and may not work with all procedures.

    Example:
        pslink run B:HELLO
    """
    click.echo("Error: The 'run' command is not yet implemented.")
    click.echo("This feature requires additional protocol support.")
    raise SystemExit(1)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
