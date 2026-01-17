"""
Psion Organiser II SDK Definitions
==================================

This module provides comprehensive programmatic access to Psion Organiser II
system definitions, including system variables, system calls, model information,
and utilities for generating assembly include files.

Overview
--------
The SDK module is organized into three main components:

**models.py**: Psion model definitions and detection
    - PsionModel enum with all supported models
    - ModelInfo dataclass with display, memory, and ROM info
    - Utilities for model detection from memory bytes

**sysvars.py**: System variable definitions
    - SystemVariable dataclass for each OS variable
    - Comprehensive database of ~150+ variables
    - Categories: processor, display, keyboard, file, time, etc.

**syscalls.py**: System call definitions
    - SystemCall dataclass for each OS service
    - Comprehensive database of ~120+ system calls
    - Categories: allocator, display, keyboard, file, math, etc.

Quick Start
-----------
Look up system definitions:
    >>> from psion_sdk.sdk import get_variable, get_syscall, PsionModel
    >>> var = get_variable("UTW_S0")
    >>> var.address
    65
    >>> call = get_syscall("DP$EMIT")
    >>> call.number
    16

Generate assembly include files:
    >>> from psion_sdk.sdk import generate_include_file
    >>> content = generate_include_file(model="LZ")
    >>> with open("psion.inc", "w") as f:
    ...     f.write(content)

Generate markdown documentation:
    >>> from psion_sdk.sdk import generate_syscall_documentation
    >>> doc = generate_syscall_documentation()
    >>> print(doc)

Model detection:
    >>> from psion_sdk.sdk import PsionModel, decode_model_byte
    >>> info = decode_model_byte(0x86)
    >>> info['model']
    <PsionModel.LZ: 6>

Reference
---------
- System services: https://www.jaapsch.net/psion/mcosintr.htm
- System variables: https://www.jaapsch.net/psion/sysvars.htm
- Model identification: https://www.jaapsch.net/psion/model.htm
"""

# =============================================================================
# Model Definitions
# =============================================================================

from psion_sdk.sdk.models import (
    # Enums
    PsionModel,

    # Dataclasses
    ModelInfo,
    DisplayInfo,
    MemoryInfo,

    # Constants
    MODEL_BYTE_ADDRESS,
    ROMVER_ADDRESS,
    MODEL_INFO,
    ALL_MODELS,
    TWO_LINE_MODELS,
    FOUR_LINE_MODELS,
    BANKING_MODELS,
    EXTENDED_SERVICE_MODELS,

    # Functions
    decode_model_byte,
    decode_rom_version,
    format_rom_version,
    get_model_by_name,
    get_supported_models,
    get_all_models_info,
    is_compatible,
)

# =============================================================================
# System Variable Definitions
# =============================================================================

from psion_sdk.sdk.sysvars import (
    # Enums
    VarCategory,

    # Dataclasses
    SystemVariable,

    # Data
    SYSTEM_VARIABLES,

    # Functions
    get_variable,
    get_variables_at_address,
    get_variables_for_model,
    get_variables_by_category,
    get_all_variable_names,
    generate_sysvars_inc,
)

# =============================================================================
# System Call Definitions
# =============================================================================

from psion_sdk.sdk.syscalls import (
    # Enums
    CallCategory,

    # Dataclasses
    SystemCall,
    Parameter,

    # Data
    SYSTEM_CALLS,

    # Functions
    get_syscall,
    get_syscall_by_number,
    get_syscalls_for_model,
    get_syscalls_by_category,
    get_all_syscall_names,
    generate_syscalls_inc,
)


# =============================================================================
# Unified Include File Generation
# =============================================================================

def generate_include_file(
    model: str | None = None,
    include_variables: bool = True,
    include_syscalls: bool = True,
    include_macros: bool = True,
    include_notes: bool = False,
) -> str:
    """
    Generate a complete assembly include file for Psion development.

    This function generates a comprehensive include file containing:
    - System variable definitions (EQU statements)
    - System call service numbers
    - Useful macros for common operations

    Args:
        model: Target model ("CM", "XP", "LZ", etc.) or None for all
        include_variables: Include system variable definitions
        include_syscalls: Include system call definitions
        include_macros: Include helper macros
        include_notes: Include usage notes as comments

    Returns:
        Complete assembly include file as a string

    Example:
        >>> content = generate_include_file(model="LZ")
        >>> # Write to file
        >>> with open("psion.inc", "w") as f:
        ...     f.write(content)

        >>> # Or use in assembler directly
        >>> from psion_sdk.assembler import Assembler
        >>> asm = Assembler()
        >>> asm.add_include_content("psion.inc", content)
    """
    lines = [
        "; =============================================================================",
        "; PSION.INC - Psion Organiser II System Definitions",
        "; =============================================================================",
        "; Generated by psion-sdk",
        ";",
    ]

    if model:
        lines.append(f"; Target model: {model}")
    else:
        lines.append("; Target model: ALL")

    lines.extend([
        ";",
        "; This file provides comprehensive definitions for developing HD6303",
        "; assembly programs targeting the Psion Organiser II.",
        ";",
        "; Usage:",
        ";     INCLUDE \"psion.inc\"",
        ";",
        "; Reference: https://www.jaapsch.net/psion/",
        "; =============================================================================",
        "",
    ])

    # System variables section
    if include_variables:
        lines.append("; ---------------------------------------------------------------------------")
        lines.append("; SYSTEM VARIABLES")
        lines.append("; ---------------------------------------------------------------------------")
        lines.append("")

        vars_content = generate_sysvars_inc(
            model=model,
            include_notes=include_notes
        )
        # Extract just the variable definitions (skip header/footer)
        in_vars = False
        for line in vars_content.split("\n"):
            if "EQU" in line:
                lines.append(line)
            elif line.startswith("; ---"):
                lines.append(line)
                in_vars = True
            elif in_vars and line.strip() == "":
                lines.append("")

        lines.append("")

    # System calls section
    if include_syscalls:
        lines.append("; ---------------------------------------------------------------------------")
        lines.append("; SYSTEM CALLS")
        lines.append("; ---------------------------------------------------------------------------")
        lines.append("")

        calls_content = generate_syscalls_inc(model=model)
        # Extract just the call definitions
        for line in calls_content.split("\n"):
            if "EQU" in line and not line.startswith(";"):
                lines.append(line)
            elif line.startswith("; ---"):
                lines.append(line)
            elif "MACRO" in line or "ENDM" in line:
                lines.append(line)

        lines.append("")

    # Macros section
    if include_macros:
        lines.extend([
            "; ---------------------------------------------------------------------------",
            "; HELPER MACROS",
            "; ---------------------------------------------------------------------------",
            "",
            "; System call invocation",
            "MACRO SYSCALL, service",
            "    LDAA    #\\service",
            "    SWI",
            "ENDM",
            "",
            "; Print LBC string",
            "MACRO PRINT, addr",
            "    LDX     #\\addr",
            "    LDAB    #0              ; Auto-detect length from LBC",
            "    LDAA    #DP_PRNT",
            "    SWI",
            "ENDM",
            "",
            "; Get keypress (blocking)",
            "MACRO GETKEY",
            "    LDAA    #KB_GETK",
            "    SWI",
            "ENDM",
            "",
            "; Sound beep",
            "MACRO BEEP",
            "    LDAA    #BZ_BELL",
            "    SWI",
            "ENDM",
            "",
            "; Wait for specified ticks (1 tick = ~50ms)",
            "MACRO PAUSE, ticks",
            "    LDD     #\\ticks",
            "    LDAA    #TM_WAIT",
            "    SWI",
            "ENDM",
            "",
            "; Push all registers",
            "MACRO PUSHALL",
            "    PSHA",
            "    PSHB",
            "    PSHX",
            "ENDM",
            "",
            "; Pull all registers",
            "MACRO PULLALL",
            "    PULX",
            "    PULB",
            "    PULA",
            "ENDM",
            "",
        ])

    lines.extend([
        "; =============================================================================",
        "; END OF PSION.INC",
        "; =============================================================================",
    ])

    return "\n".join(lines)


# =============================================================================
# Documentation Generation
# =============================================================================

def generate_syscall_documentation(model: str | None = None) -> str:
    """
    Generate markdown documentation for all system calls.

    Args:
        model: Target model to filter for, or None for all calls

    Returns:
        Markdown-formatted documentation string
    """
    lines = [
        "# Psion Organiser II System Call Reference",
        "",
        "This document describes the system calls available on the "
        "Psion Organiser II operating system.",
        "",
        "## Calling Convention",
        "",
        "System calls are invoked using the SWI instruction:",
        "",
        "```asm",
        "    LDAA    #service_number     ; Load service number into A",
        "    [setup parameters]          ; Set up B, X, UTW_S0-S5",
        "    SWI                         ; Execute system call",
        "    BCS     error_handler       ; Check carry flag for errors",
        "```",
        "",
        "**Important**: Assume all registers and UTW_S0-S5 are trashed by "
        "system calls unless documented otherwise.",
        "",
    ]

    # Determine target model
    target_model = None
    if model:
        target_model = get_model_by_name(model)
        lines.append(f"*Filtered for model: {model}*")
        lines.append("")

    # Group by category
    category_names = {
        CallCategory.ALLOCATOR: "Memory Allocation",
        CallCategory.BATTERY: "Power/NMI Control",
        CallCategory.BUZZER: "Sound Output",
        CallCategory.DISPLAY: "Display Control",
        CallCategory.DEVICE: "Device Management",
        CallCategory.EDITOR: "Line Editing",
        CallCategory.ERROR: "Error Handling",
        CallCategory.FILE: "File System",
        CallCategory.FLOAT: "Floating Point Math",
        CallCategory.INTERPRETER: "Table Interpreter",
        CallCategory.KEYBOARD: "Keyboard Input",
        CallCategory.LANGUAGE: "OPL Language",
        CallCategory.MENU: "Menu Display",
        CallCategory.MATH: "Math Conversions",
        CallCategory.PACK: "Pack Access",
        CallCategory.RUNTIME: "Program Execution",
        CallCategory.TOPLEVEL: "Top-Level Menu",
        CallCategory.TIME: "Real-Time Clock",
        CallCategory.UTILITY: "General Utilities",
        CallCategory.EXTENDED: "Extended Services (LZ)",
    }

    for category in CallCategory:
        calls = get_syscalls_by_category(category)
        if target_model:
            calls = [c for c in calls if c.is_supported_on(target_model)]

        if not calls:
            continue

        cat_name = category_names.get(category, category.name)
        lines.extend([
            f"## {cat_name}",
            "",
        ])

        for call in sorted(calls, key=lambda c: c.number):
            models_str = ", ".join(sorted(m.name for m in call.models))
            lines.extend([
                f"### {call.name} (${call.number:02X})",
                "",
                f"**Description:** {call.description}",
                "",
                f"**Models:** {models_str}",
                "",
            ])

            if call.inputs:
                lines.append("**Inputs:**")
                for param in call.inputs:
                    lines.append(f"- {param}")
                lines.append("")

            if call.outputs:
                lines.append("**Outputs:**")
                for param in call.outputs:
                    lines.append(f"- {param}")
                lines.append("")

            if call.notes:
                lines.append(f"**Notes:** {call.notes}")
                lines.append("")

            if call.errors:
                lines.append("**Errors:**")
                for err in call.errors:
                    lines.append(f"- {err}")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def generate_sysvar_documentation(model: str | None = None) -> str:
    """
    Generate markdown documentation for all system variables.

    Args:
        model: Target model to filter for, or None for all variables

    Returns:
        Markdown-formatted documentation string
    """
    lines = [
        "# Psion Organiser II System Variables Reference",
        "",
        "This document describes the system variables used by the "
        "Psion Organiser II operating system.",
        "",
        "## Memory Map Overview",
        "",
        "| Address Range | Description |",
        "|---------------|-------------|",
        "| $0000-$003F | HD6303 internal registers |",
        "| $0040-$00FF | Zero page RAM (fast access) |",
        "| $0100-$03FF | Semi-custom chip I/O |",
        "| $0400-$1FFF | System RAM |",
        "| $2000-$7FFF | Extended RAM (banked on LZ) |",
        "| $8000-$FFFF | ROM |",
        "",
    ]

    # Determine target model
    target_model = None
    if model:
        target_model = get_model_by_name(model)
        lines.append(f"*Filtered for model: {model}*")
        lines.append("")

    # Group by category
    category_names = {
        VarCategory.PROCESSOR: "HD6303 Internal Registers",
        VarCategory.UTILITY: "Utility Scratch Registers",
        VarCategory.BATTERY: "Battery/Power Control",
        VarCategory.DISPLAY: "Display Control",
        VarCategory.KEYBOARD: "Keyboard Input",
        VarCategory.PACK: "Pack/Datapack Access",
        VarCategory.FILE: "File System",
        VarCategory.TIME: "Real-Time Clock",
        VarCategory.ALARM: "Alarm System",
        VarCategory.EDITOR: "Line Editor",
        VarCategory.MATH: "Floating Point Math",
        VarCategory.LANGUAGE: "OPL Language Runtime",
        VarCategory.MENU: "Menu System",
        VarCategory.COMMS: "Serial Communications",
        VarCategory.SYSTEM: "System/Runtime",
        VarCategory.HARDWARE: "Hardware I/O Addresses",
        VarCategory.ROM: "ROM Constants",
    }

    for category in VarCategory:
        vars_list = get_variables_by_category(category)
        if target_model:
            vars_list = [v for v in vars_list if v.is_supported_on(target_model)]

        if not vars_list:
            continue

        cat_name = category_names.get(category, category.name)
        lines.extend([
            f"## {cat_name}",
            "",
            "| Name | Address | Size | Description |",
            "|------|---------|------|-------------|",
        ])

        for var in sorted(vars_list, key=lambda v: v.address):
            size_str = f"{var.size}B" if var.size > 1 else "1B"
            desc = var.description
            if var.read_only:
                desc += " (RO)"
            lines.append(f"| {var.name} | ${var.address:04X} | {size_str} | {desc} |")

        lines.extend(["", ""])

    return "\n".join(lines)


def generate_model_documentation() -> str:
    """
    Generate markdown documentation for all supported models.

    Returns:
        Markdown-formatted documentation string
    """
    lines = [
        "# Psion Organiser II Model Reference",
        "",
        "This document describes the different Psion Organiser II models "
        "and their characteristics.",
        "",
        "## Model Overview",
        "",
        "| Model | RAM | Display | ROM Versions | Notes |",
        "|-------|-----|---------|--------------|-------|",
    ]

    for model_info in get_all_models_info():
        ram = f"{model_info.memory.ram_kb}-{model_info.memory.max_ram_kb}KB"
        if model_info.memory.ram_kb == model_info.memory.max_ram_kb:
            ram = f"{model_info.memory.ram_kb}KB"
        display = f"{model_info.display.rows}x{model_info.display.columns}"
        rom_min = format_rom_version(model_info.rom_versions[0])
        rom_max = format_rom_version(model_info.rom_versions[1])
        rom = f"{rom_min}-{rom_max}"

        lines.append(
            f"| {model_info.model.name} | {ram} | {display} | {rom} | {model_info.notes} |"
        )

    lines.extend([
        "",
        "## Model Detection",
        "",
        "The model can be identified by reading the byte at ROM address $FFE8:",
        "",
        "```asm",
        "    LDAB    $FFE8       ; Load model byte",
        "    ANDB    #$07        ; Mask to bits 0-2",
        "    ; B now contains model ID (0=CM, 1=XP, 2=LA, 4=P350, 5=LZ64, 6=LZ)",
        "```",
        "",
        "The ROM version is at $FFE9 in BCD format (e.g., $46 = version 4.6).",
        "",
    ])

    for model_info in get_all_models_info():
        lines.extend([
            f"## {model_info.name}",
            "",
            f"**Model ID:** {model_info.model.value}",
            "",
            f"**Display:** {model_info.display.rows} rows x "
            f"{model_info.display.columns} columns",
            "",
            f"**RAM:** {model_info.memory.ram_kb}KB base, "
            f"{model_info.memory.max_ram_kb}KB maximum",
            "",
            f"**RAM Banking:** {'Yes' if model_info.memory.has_banking else 'No'}",
            "",
            f"**ROM Versions:** {format_rom_version(model_info.rom_versions[0])} to "
            f"{format_rom_version(model_info.rom_versions[1])}",
            "",
            f"**Notes:** {model_info.notes}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


# =============================================================================
# Public API Exports
# =============================================================================

__all__ = [
    # Models
    "PsionModel",
    "ModelInfo",
    "DisplayInfo",
    "MemoryInfo",
    "MODEL_BYTE_ADDRESS",
    "ROMVER_ADDRESS",
    "MODEL_INFO",
    "ALL_MODELS",
    "TWO_LINE_MODELS",
    "FOUR_LINE_MODELS",
    "BANKING_MODELS",
    "EXTENDED_SERVICE_MODELS",
    "decode_model_byte",
    "decode_rom_version",
    "format_rom_version",
    "get_model_by_name",
    "get_supported_models",
    "get_all_models_info",
    "is_compatible",

    # System Variables
    "VarCategory",
    "SystemVariable",
    "SYSTEM_VARIABLES",
    "get_variable",
    "get_variables_at_address",
    "get_variables_for_model",
    "get_variables_by_category",
    "get_all_variable_names",
    "generate_sysvars_inc",

    # System Calls
    "CallCategory",
    "SystemCall",
    "Parameter",
    "SYSTEM_CALLS",
    "get_syscall",
    "get_syscall_by_number",
    "get_syscalls_for_model",
    "get_syscalls_by_category",
    "get_all_syscall_names",
    "generate_syscalls_inc",

    # Unified Generation
    "generate_include_file",
    "generate_syscall_documentation",
    "generate_sysvar_documentation",
    "generate_model_documentation",
]
