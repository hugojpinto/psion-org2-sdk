"""
Psion SDK - Cross-Development Toolchain for Psion Organiser II
==============================================================

This package provides a complete toolchain for developing machine code programs
targeting the Psion Organiser II series of vintage handheld computers.

The Psion Organiser II uses a Hitachi HD6303 CPU (a Motorola 6803 derivative)
running at 921.6 kHz. Programs are distributed in "packs" (cartridges) using
the OPK file format.

Main Components
---------------
- **assembler**: HD6303 assembler (psasm)
    Converts assembly source files (.asm) to Psion object code format (.ob3)

- **opk**: OPK file handling (psopk)
    Creates and manipulates OPK pack image files for distribution

- **comms**: Communication tools (pslink)
    Transfers files between PC and Psion device via serial link

- **sdk**: SDK definitions
    System variables, system calls, and include file generation

Quick Start
-----------
Assemble a program:
    >>> from psion_sdk.assembler import Assembler
    >>> asm = Assembler()
    >>> code = asm.assemble_file("hello.asm")
    >>> asm.write_ob3("hello.ob3")

Create a pack from OB3 files:
    >>> from psion_sdk.opk import PackBuilder
    >>> builder = PackBuilder(size_kb=16)
    >>> builder.add_ob3_file("hello.ob3")
    >>> builder.build_to_file("hello.opk")

Read an existing pack:
    >>> from psion_sdk.opk import PackParser
    >>> parser = PackParser.from_file("hello.opk")
    >>> for name in parser.list_procedures():
    ...     print(f"Procedure: {name}")

Or use the command-line tools:
    $ psasm hello.asm -o hello.ob3
    $ psopk create -o hello.opk hello.ob3
    $ pslink --upload hello.opk

Reference Documentation
-----------------------
- Psion Technical Reference: https://www.jaapsch.net/psion/
- HD6303 Instruction Set: https://www.jaapsch.net/psion/mcmnemal.htm
- File Formats: https://www.jaapsch.net/psion/fileform.htm

Version History
---------------
1.0.0 - Initial release with assembler, OPK builder, and serial transfer
"""

__version__ = "1.0.0"
__author__ = "Hugo José Pinto & Contributors"

# =============================================================================
# Public API Exports
# =============================================================================
# These are the main classes and functions that users of the library will use.
# We import them here so they can be accessed directly from psion_sdk.
# =============================================================================

from psion_sdk.assembler import Assembler
from psion_sdk.errors import (
    PsionError,
    AssemblerError,
    AssemblySyntaxError,
    UndefinedSymbolError,
    DuplicateSymbolError,
    AddressingModeError,
    BranchRangeError,
    ExpressionError,
    OPKError,
    OPKFormatError,
    PackSizeError,
)

# OPK module exports
from psion_sdk.opk import (
    PackBuilder,
    PackParser,
    PackType,
    PackSize,
    PackHeader,
    ProcedureRecord,
    OB3File,
    validate_ob3,
    create_opk,
    create_opk_from_ob3,
)

# Communication module exports
from psion_sdk.comms import (
    LinkProtocol,
    FileTransfer,
    Packet,
    PacketType,
    FileType,
    OpenMode,
    PortInfo,
    list_serial_ports,
    find_psion_port,
    open_serial_port,
    close_serial_port,
    crc_ccitt_fast,
)

# Communication-related errors
from psion_sdk.errors import (
    CommsError,
    ConnectionError as PsionConnectionError,  # Avoid collision with builtin
    TransferError,
    ProtocolError,
)

# SDK module exports - system variables, system calls, and model definitions
from psion_sdk.sdk import (
    # Model definitions
    PsionModel,
    ModelInfo,
    DisplayInfo,
    MemoryInfo,
    MODEL_INFO,
    ALL_MODELS,
    TWO_LINE_MODELS,
    FOUR_LINE_MODELS,
    EXTENDED_SERVICE_MODELS,
    decode_model_byte,
    decode_rom_version,
    format_rom_version,
    get_model_by_name,
    get_supported_models,
    is_compatible,

    # System variables
    VarCategory,
    SystemVariable,
    SYSTEM_VARIABLES,
    get_variable,
    get_variables_for_model,
    get_variables_by_category,

    # System calls
    CallCategory,
    SystemCall,
    Parameter,
    SYSTEM_CALLS,
    get_syscall,
    get_syscall_by_number,
    get_syscalls_for_model,
    get_syscalls_by_category,

    # Include file generation
    generate_include_file,
    generate_sysvars_inc,
    generate_syscalls_inc,

    # Documentation generation
    generate_syscall_documentation,
    generate_sysvar_documentation,
    generate_model_documentation,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Assembler
    "Assembler",
    # OPK Builder and Parser
    "PackBuilder",
    "PackParser",
    "PackType",
    "PackSize",
    "PackHeader",
    "ProcedureRecord",
    "OB3File",
    "validate_ob3",
    "create_opk",
    "create_opk_from_ob3",
    # Exception hierarchy
    "PsionError",
    "AssemblerError",
    "AssemblySyntaxError",
    "UndefinedSymbolError",
    "DuplicateSymbolError",
    "AddressingModeError",
    "BranchRangeError",
    "ExpressionError",
    "OPKError",
    "OPKFormatError",
    "PackSizeError",
    # Communication
    "LinkProtocol",
    "FileTransfer",
    "Packet",
    "PacketType",
    "FileType",
    "OpenMode",
    "PortInfo",
    "list_serial_ports",
    "find_psion_port",
    "open_serial_port",
    "close_serial_port",
    "crc_ccitt_fast",
    # Communication errors
    "CommsError",
    "PsionConnectionError",
    "TransferError",
    "ProtocolError",
    # SDK - Model definitions
    "PsionModel",
    "ModelInfo",
    "DisplayInfo",
    "MemoryInfo",
    "MODEL_INFO",
    "ALL_MODELS",
    "TWO_LINE_MODELS",
    "FOUR_LINE_MODELS",
    "EXTENDED_SERVICE_MODELS",
    "decode_model_byte",
    "decode_rom_version",
    "format_rom_version",
    "get_model_by_name",
    "get_supported_models",
    "is_compatible",
    # SDK - System variables
    "VarCategory",
    "SystemVariable",
    "SYSTEM_VARIABLES",
    "get_variable",
    "get_variables_for_model",
    "get_variables_by_category",
    # SDK - System calls
    "CallCategory",
    "SystemCall",
    "Parameter",
    "SYSTEM_CALLS",
    "get_syscall",
    "get_syscall_by_number",
    "get_syscalls_for_model",
    "get_syscalls_by_category",
    # SDK - Include file generation
    "generate_include_file",
    "generate_sysvars_inc",
    "generate_syscalls_inc",
    # SDK - Documentation generation
    "generate_syscall_documentation",
    "generate_sysvar_documentation",
    "generate_model_documentation",
]
