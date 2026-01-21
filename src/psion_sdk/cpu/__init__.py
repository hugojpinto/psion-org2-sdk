"""
Psion SDK CPU Package
=====================

This package contains CPU architecture definitions used by multiple tools
in the Psion SDK, including the assembler, disassembler, and emulator.

The HD6303 is the CPU used in the Psion Organiser II series. It's a Hitachi
derivative of the Motorola 6800 family with enhancements for embedded systems.

Modules:
    hd6303: Complete HD6303 instruction set definitions, addressing modes,
            and helper functions for instruction encoding/decoding.

This package provides a shared foundation that avoids duplication of CPU
knowledge across different tools. Both the assembler (which encodes instructions)
and the disassembler (which decodes them) use the same definitions, ensuring
consistency and reducing maintenance burden.

Usage:
    from psion_sdk.cpu import (
        AddressingMode,
        InstructionInfo,
        OPCODE_TABLE,
        get_instruction_info,
    )

Copyright (c) 2025-2026 Hugo Jose Pinto & Contributors
"""

# =============================================================================
# Public API Exports
# =============================================================================
# Import and re-export all public symbols from the hd6303 module for
# convenient access via `from psion_sdk.cpu import ...`

from psion_sdk.cpu.hd6303 import (
    # Core types
    AddressingMode,
    InstructionInfo,
    # Master instruction database
    OPCODE_TABLE,
    # Instruction set reference lists
    MNEMONICS,
    BRANCH_INSTRUCTIONS,
    BRANCH_INVERSION,
    CONDITIONAL_BRANCHES,
    UNCONDITIONAL_BRANCHES,
    WORD_IMMEDIATE_INSTRUCTIONS,
    NO_IMMEDIATE_INSTRUCTIONS,
    INHERENT_ONLY_INSTRUCTIONS,
    # Lookup functions
    get_instruction_info,
    get_valid_modes,
    is_valid_instruction,
    is_branch_instruction,
    uses_word_immediate,
    # Branch relaxation helpers
    get_inverted_branch,
    is_conditional_branch,
    is_unconditional_branch,
    get_long_branch_size,
    get_short_branch_size,
)

__all__ = [
    # Core types
    "AddressingMode",
    "InstructionInfo",
    # Master instruction database
    "OPCODE_TABLE",
    # Instruction set reference lists
    "MNEMONICS",
    "BRANCH_INSTRUCTIONS",
    "BRANCH_INVERSION",
    "CONDITIONAL_BRANCHES",
    "UNCONDITIONAL_BRANCHES",
    "WORD_IMMEDIATE_INSTRUCTIONS",
    "NO_IMMEDIATE_INSTRUCTIONS",
    "INHERENT_ONLY_INSTRUCTIONS",
    # Lookup functions
    "get_instruction_info",
    "get_valid_modes",
    "is_valid_instruction",
    "is_branch_instruction",
    "uses_word_immediate",
    # Branch relaxation helpers
    "get_inverted_branch",
    "is_conditional_branch",
    "is_unconditional_branch",
    "get_long_branch_size",
    "get_short_branch_size",
]
