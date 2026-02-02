"""
Unified CLI Error Handling
==========================

Provides consistent error handling and exit codes across all CLI tools.
"""

import sys
import traceback
from enum import IntEnum
from typing import NoReturn

import click


class ExitCode(IntEnum):
    """Standard exit codes for CLI tools."""
    SUCCESS = 0
    BUILD_ERROR = 1      # Compilation, assembly, or packaging error
    INVALID_ARGS = 2     # Invalid arguments or missing files
    INTERNAL_ERROR = 3   # Unexpected internal error


def handle_cli_exception(
    error: Exception,
    verbose: bool = False,
    error_type: str | None = None
) -> NoReturn:
    """
    Unified exception handler for all CLI tools.

    Formats the error message appropriately, optionally prints traceback
    in verbose mode, and exits with the correct exit code.

    Args:
        error: The exception that was raised
        verbose: If True, print full traceback for internal errors
        error_type: Optional prefix for the error message (e.g., "Compilation")

    Raises:
        SystemExit: Always exits with an appropriate exit code
    """
    from psion_sdk.smallc.errors import SmallCError
    from psion_sdk.errors import PsionError

    # Determine exit code and message format based on exception type
    if isinstance(error, SmallCError):
        # Compiler errors already have good formatting with "error:" prefix
        # Don't add another prefix to avoid duplication
        click.echo(str(error), err=True)
        sys.exit(ExitCode.BUILD_ERROR)

    elif isinstance(error, PsionError):
        # Assembly or packaging errors
        prefix = f"{error_type} error: " if error_type else "Error: "
        click.echo(f"{prefix}{error}", err=True)
        sys.exit(ExitCode.BUILD_ERROR)

    elif isinstance(error, click.BadParameter):
        # Invalid command-line arguments
        click.echo(f"Error: {error}", err=True)
        sys.exit(ExitCode.INVALID_ARGS)

    elif isinstance(error, FileNotFoundError):
        # Missing input files
        click.echo(f"Error: {error}", err=True)
        sys.exit(ExitCode.INVALID_ARGS)

    elif isinstance(error, PermissionError):
        # Permission denied
        click.echo(f"Error: {error}", err=True)
        sys.exit(ExitCode.INVALID_ARGS)

    else:
        # Unexpected internal error
        click.echo(f"Internal error: {error}", err=True)
        if verbose:
            traceback.print_exc()
        sys.exit(ExitCode.INTERNAL_ERROR)
