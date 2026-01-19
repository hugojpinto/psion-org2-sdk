"""
Psion SDK Disassembler Module
=============================

This module provides disassembly capabilities for:
- HD6303 machine code (the CPU used in Psion Organiser II)
- QCode (the bytecode used by the OPL interpreter)

The disassemblers are designed to support debugging workflows, particularly
for the MCP emulator integration where understanding executed code is crucial.

Usage:
    from psion_sdk.disassembler import HD6303Disassembler, QCodeDisassembler

    # Disassemble HD6303 machine code
    disasm = HD6303Disassembler()
    instructions = disasm.disassemble(memory_bytes, start_address=0x8000)

    # Disassemble QCode
    qcode_disasm = QCodeDisassembler()
    opcodes = qcode_disasm.disassemble(qcode_bytes, start_address=0x7EC8)

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from .hd6303 import HD6303Disassembler, DisassembledInstruction
from .qcode import QCodeDisassembler, DisassembledQCode

__all__ = [
    "HD6303Disassembler",
    "DisassembledInstruction",
    "QCodeDisassembler",
    "DisassembledQCode",
]
