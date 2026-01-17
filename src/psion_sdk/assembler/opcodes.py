"""
HD6303 Instruction Set Definition
==================================

This module defines the complete HD6303 instruction set with opcodes,
addressing modes, and instruction sizes. The HD6303 is a Hitachi derivative
of the Motorola 6803, with additional instructions for bit manipulation.

The HD6303 in the Psion Organiser II runs at 921.6 kHz and uses big-endian
byte ordering (most significant byte first).

Addressing Modes
----------------
The HD6303 supports six addressing modes:

1. **INHERENT**: No operand (e.g., NOP, RTS, PSHA)
   - 1 byte instruction
   - Example: RTS -> $39

2. **IMMEDIATE**: Literal value follows opcode (e.g., LDAA #$41)
   - 2 bytes for 8-bit operand (#byte)
   - 3 bytes for 16-bit operand (##word) - used by LDX, LDD, LDS, CPX, ADDD, SUBD
   - Example: LDAA #$41 -> $86 $41

3. **DIRECT**: Zero-page address ($00-$FF)
   - 2 bytes: opcode + address byte
   - Fast access to first 256 bytes of memory
   - Example: LDAA $40 -> $96 $40

4. **EXTENDED**: Full 16-bit address
   - 3 bytes: opcode + high byte + low byte
   - Example: LDAA $1234 -> $B6 $12 $34

5. **INDEXED**: X register + 8-bit offset
   - 2 bytes: opcode + offset
   - Effective address = X + offset
   - Example: LDAA 5,X -> $A6 $05

6. **RELATIVE**: PC-relative branch
   - 2 bytes: opcode + signed offset
   - Range: -128 to +127 from next instruction
   - Example: BNE label -> $26 $offset

HD6303-Specific Instructions
----------------------------
The HD6303 adds these instructions not found in the 6801:

- AIM #,addr : AND immediate with memory
- OIM #,addr : OR immediate with memory
- EIM #,addr : XOR immediate with memory
- TIM #,addr : Test immediate with memory
- XGDX      : Exchange D and X registers
- SLP       : Sleep (low-power mode)

Reference
---------
- Psion Technical Reference: https://www.jaapsch.net/psion/mcmnemal.htm
- HD6303 Datasheet (Hitachi)
- Motorola M6800 Programming Reference Manual
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# =============================================================================
# Addressing Mode Enumeration
# =============================================================================

class AddressingMode(Enum):
    """
    HD6303 addressing modes.

    Each addressing mode determines how the operand is interpreted
    and affects the instruction encoding and size.
    """
    INHERENT = auto()   # No operand (NOP, RTS)
    IMMEDIATE = auto()  # #value or ##value (literal)
    DIRECT = auto()     # Zero page address ($00-$FF)
    EXTENDED = auto()   # Full 16-bit address
    INDEXED = auto()    # offset,X (X register + offset)
    RELATIVE = auto()   # Branch displacement (signed 8-bit)

    def __str__(self) -> str:
        """Return human-readable name for error messages."""
        return {
            AddressingMode.INHERENT: "inherent",
            AddressingMode.IMMEDIATE: "immediate",
            AddressingMode.DIRECT: "direct",
            AddressingMode.EXTENDED: "extended",
            AddressingMode.INDEXED: "indexed",
            AddressingMode.RELATIVE: "relative",
        }[self]


# =============================================================================
# Instruction Information
# =============================================================================

@dataclass(frozen=True)
class InstructionInfo:
    """
    Information about a specific instruction encoding.

    This dataclass is immutable (frozen) to prevent accidental modification
    of the opcode table at runtime.

    Attributes:
        opcode: The opcode byte(s) for this instruction
        size: Total instruction size in bytes (including operand)
        cycles: Number of CPU cycles (for timing analysis)
        operand_size: Size of operand in bytes (0, 1, or 2)
    """
    opcode: int          # Opcode byte (or first byte if multi-byte)
    size: int            # Total instruction size in bytes
    cycles: int          # CPU cycles for execution
    operand_size: int    # Size of operand (0=none, 1=byte, 2=word)

    def __repr__(self) -> str:
        return f"InstructionInfo(opcode=${self.opcode:02X}, size={self.size}, cycles={self.cycles})"


# =============================================================================
# Opcode Table
# =============================================================================
# This is the master table of all HD6303 instructions.
# Key: (mnemonic, addressing_mode)
# Value: InstructionInfo(opcode, total_size, cycles, operand_size)
#
# The table is built from the JAPE emulator's hd6303.js which contains
# a complete and verified implementation of the HD6303 instruction set.
# =============================================================================

OPCODE_TABLE: dict[tuple[str, AddressingMode], InstructionInfo] = {
    # =========================================================================
    # INHERENT INSTRUCTIONS (no operand)
    # These instructions operate on registers or have no operand.
    # =========================================================================

    # Control instructions
    ("TRAP", AddressingMode.INHERENT): InstructionInfo(0x00, 1, 12, 0),  # Software trap
    ("NOP", AddressingMode.INHERENT): InstructionInfo(0x01, 1, 1, 0),   # No operation
    ("LSRD", AddressingMode.INHERENT): InstructionInfo(0x04, 1, 1, 0),  # Logical shift D right
    ("ASLD", AddressingMode.INHERENT): InstructionInfo(0x05, 1, 1, 0),  # Arithmetic shift D left
    ("LSLD", AddressingMode.INHERENT): InstructionInfo(0x05, 1, 1, 0),  # Alias for ASLD
    ("TAP", AddressingMode.INHERENT): InstructionInfo(0x06, 1, 1, 0),   # Transfer A to CCR
    ("TPA", AddressingMode.INHERENT): InstructionInfo(0x07, 1, 1, 0),   # Transfer CCR to A
    ("INX", AddressingMode.INHERENT): InstructionInfo(0x08, 1, 1, 0),   # Increment X
    ("DEX", AddressingMode.INHERENT): InstructionInfo(0x09, 1, 1, 0),   # Decrement X
    ("CLV", AddressingMode.INHERENT): InstructionInfo(0x0A, 1, 1, 0),   # Clear overflow flag
    ("SEV", AddressingMode.INHERENT): InstructionInfo(0x0B, 1, 1, 0),   # Set overflow flag
    ("CLC", AddressingMode.INHERENT): InstructionInfo(0x0C, 1, 1, 0),   # Clear carry flag
    ("SEC", AddressingMode.INHERENT): InstructionInfo(0x0D, 1, 1, 0),   # Set carry flag
    ("CLI", AddressingMode.INHERENT): InstructionInfo(0x0E, 1, 1, 0),   # Clear interrupt mask
    ("SEI", AddressingMode.INHERENT): InstructionInfo(0x0F, 1, 1, 0),   # Set interrupt mask

    # Register operations
    ("SBA", AddressingMode.INHERENT): InstructionInfo(0x10, 1, 1, 0),   # Subtract B from A
    ("CBA", AddressingMode.INHERENT): InstructionInfo(0x11, 1, 1, 0),   # Compare B to A
    ("TAB", AddressingMode.INHERENT): InstructionInfo(0x16, 1, 1, 0),   # Transfer A to B
    ("TBA", AddressingMode.INHERENT): InstructionInfo(0x17, 1, 1, 0),   # Transfer B to A
    ("XGDX", AddressingMode.INHERENT): InstructionInfo(0x18, 1, 2, 0),  # Exchange D and X (HD6303)
    ("DAA", AddressingMode.INHERENT): InstructionInfo(0x19, 1, 2, 0),   # Decimal adjust A
    ("SLP", AddressingMode.INHERENT): InstructionInfo(0x1A, 1, 4, 0),   # Sleep (HD6303)
    ("ABA", AddressingMode.INHERENT): InstructionInfo(0x1B, 1, 1, 0),   # Add B to A

    # Stack operations
    ("TSX", AddressingMode.INHERENT): InstructionInfo(0x30, 1, 1, 0),   # Transfer SP to X
    ("INS", AddressingMode.INHERENT): InstructionInfo(0x31, 1, 1, 0),   # Increment SP
    ("PULA", AddressingMode.INHERENT): InstructionInfo(0x32, 1, 3, 0),  # Pull A from stack
    ("PULB", AddressingMode.INHERENT): InstructionInfo(0x33, 1, 3, 0),  # Pull B from stack
    ("DES", AddressingMode.INHERENT): InstructionInfo(0x34, 1, 1, 0),   # Decrement SP
    ("TXS", AddressingMode.INHERENT): InstructionInfo(0x35, 1, 1, 0),   # Transfer X to SP
    ("PSHA", AddressingMode.INHERENT): InstructionInfo(0x36, 1, 4, 0),  # Push A to stack
    ("PSHB", AddressingMode.INHERENT): InstructionInfo(0x37, 1, 4, 0),  # Push B to stack
    ("PULX", AddressingMode.INHERENT): InstructionInfo(0x38, 1, 4, 0),  # Pull X from stack
    ("RTS", AddressingMode.INHERENT): InstructionInfo(0x39, 1, 5, 0),   # Return from subroutine
    ("ABX", AddressingMode.INHERENT): InstructionInfo(0x3A, 1, 1, 0),   # Add B to X
    ("RTI", AddressingMode.INHERENT): InstructionInfo(0x3B, 1, 10, 0),  # Return from interrupt
    ("PSHX", AddressingMode.INHERENT): InstructionInfo(0x3C, 1, 5, 0),  # Push X to stack
    ("MUL", AddressingMode.INHERENT): InstructionInfo(0x3D, 1, 7, 0),   # Multiply A * B -> D
    ("WAI", AddressingMode.INHERENT): InstructionInfo(0x3E, 1, 9, 0),   # Wait for interrupt
    ("SWI", AddressingMode.INHERENT): InstructionInfo(0x3F, 1, 12, 0),  # Software interrupt

    # Accumulator A inherent operations
    ("NEGA", AddressingMode.INHERENT): InstructionInfo(0x40, 1, 1, 0),  # Negate A
    ("COMA", AddressingMode.INHERENT): InstructionInfo(0x43, 1, 1, 0),  # Complement A
    ("LSRA", AddressingMode.INHERENT): InstructionInfo(0x44, 1, 1, 0),  # Logical shift right A
    ("RORA", AddressingMode.INHERENT): InstructionInfo(0x46, 1, 1, 0),  # Rotate right A
    ("ASRA", AddressingMode.INHERENT): InstructionInfo(0x47, 1, 1, 0),  # Arithmetic shift right A
    ("ASLA", AddressingMode.INHERENT): InstructionInfo(0x48, 1, 1, 0),  # Arithmetic shift left A
    ("LSLA", AddressingMode.INHERENT): InstructionInfo(0x48, 1, 1, 0),  # Alias for ASLA
    ("ROLA", AddressingMode.INHERENT): InstructionInfo(0x49, 1, 1, 0),  # Rotate left A
    ("DECA", AddressingMode.INHERENT): InstructionInfo(0x4A, 1, 1, 0),  # Decrement A
    ("INCA", AddressingMode.INHERENT): InstructionInfo(0x4C, 1, 1, 0),  # Increment A
    ("TSTA", AddressingMode.INHERENT): InstructionInfo(0x4D, 1, 1, 0),  # Test A
    ("CLRA", AddressingMode.INHERENT): InstructionInfo(0x4F, 1, 1, 0),  # Clear A

    # Accumulator B inherent operations
    ("NEGB", AddressingMode.INHERENT): InstructionInfo(0x50, 1, 1, 0),  # Negate B
    ("COMB", AddressingMode.INHERENT): InstructionInfo(0x53, 1, 1, 0),  # Complement B
    ("LSRB", AddressingMode.INHERENT): InstructionInfo(0x54, 1, 1, 0),  # Logical shift right B
    ("RORB", AddressingMode.INHERENT): InstructionInfo(0x56, 1, 1, 0),  # Rotate right B
    ("ASRB", AddressingMode.INHERENT): InstructionInfo(0x57, 1, 1, 0),  # Arithmetic shift right B
    ("ASLB", AddressingMode.INHERENT): InstructionInfo(0x58, 1, 1, 0),  # Arithmetic shift left B
    ("LSLB", AddressingMode.INHERENT): InstructionInfo(0x58, 1, 1, 0),  # Alias for ASLB
    ("ROLB", AddressingMode.INHERENT): InstructionInfo(0x59, 1, 1, 0),  # Rotate left B
    ("DECB", AddressingMode.INHERENT): InstructionInfo(0x5A, 1, 1, 0),  # Decrement B
    ("INCB", AddressingMode.INHERENT): InstructionInfo(0x5C, 1, 1, 0),  # Increment B
    ("TSTB", AddressingMode.INHERENT): InstructionInfo(0x5D, 1, 1, 0),  # Test B
    ("CLRB", AddressingMode.INHERENT): InstructionInfo(0x5F, 1, 1, 0),  # Clear B

    # =========================================================================
    # INDEXED MEMORY OPERATIONS (offset,X)
    # These operate on memory at address X + offset
    # =========================================================================

    ("NEG", AddressingMode.INDEXED): InstructionInfo(0x60, 2, 6, 1),   # Negate memory
    ("COM", AddressingMode.INDEXED): InstructionInfo(0x63, 2, 6, 1),   # Complement memory
    ("LSR", AddressingMode.INDEXED): InstructionInfo(0x64, 2, 6, 1),   # Logical shift right memory
    ("ROR", AddressingMode.INDEXED): InstructionInfo(0x66, 2, 6, 1),   # Rotate right memory
    ("ASR", AddressingMode.INDEXED): InstructionInfo(0x67, 2, 6, 1),   # Arithmetic shift right memory
    ("ASL", AddressingMode.INDEXED): InstructionInfo(0x68, 2, 6, 1),   # Arithmetic shift left memory
    ("LSL", AddressingMode.INDEXED): InstructionInfo(0x68, 2, 6, 1),   # Alias for ASL
    ("ROL", AddressingMode.INDEXED): InstructionInfo(0x69, 2, 6, 1),   # Rotate left memory
    ("DEC", AddressingMode.INDEXED): InstructionInfo(0x6A, 2, 6, 1),   # Decrement memory
    ("INC", AddressingMode.INDEXED): InstructionInfo(0x6C, 2, 6, 1),   # Increment memory
    ("TST", AddressingMode.INDEXED): InstructionInfo(0x6D, 2, 4, 1),   # Test memory
    ("JMP", AddressingMode.INDEXED): InstructionInfo(0x6E, 2, 3, 1),   # Jump indexed
    ("CLR", AddressingMode.INDEXED): InstructionInfo(0x6F, 2, 5, 1),   # Clear memory

    # =========================================================================
    # EXTENDED MEMORY OPERATIONS (16-bit address)
    # =========================================================================

    ("NEG", AddressingMode.EXTENDED): InstructionInfo(0x70, 3, 6, 2),   # Negate memory
    ("COM", AddressingMode.EXTENDED): InstructionInfo(0x73, 3, 6, 2),   # Complement memory
    ("LSR", AddressingMode.EXTENDED): InstructionInfo(0x74, 3, 6, 2),   # Logical shift right memory
    ("ROR", AddressingMode.EXTENDED): InstructionInfo(0x76, 3, 6, 2),   # Rotate right memory
    ("ASR", AddressingMode.EXTENDED): InstructionInfo(0x77, 3, 6, 2),   # Arithmetic shift right memory
    ("ASL", AddressingMode.EXTENDED): InstructionInfo(0x78, 3, 6, 2),   # Arithmetic shift left memory
    ("LSL", AddressingMode.EXTENDED): InstructionInfo(0x78, 3, 6, 2),   # Alias for ASL
    ("ROL", AddressingMode.EXTENDED): InstructionInfo(0x79, 3, 6, 2),   # Rotate left memory
    ("DEC", AddressingMode.EXTENDED): InstructionInfo(0x7A, 3, 6, 2),   # Decrement memory
    ("INC", AddressingMode.EXTENDED): InstructionInfo(0x7C, 3, 6, 2),   # Increment memory
    ("TST", AddressingMode.EXTENDED): InstructionInfo(0x7D, 3, 4, 2),   # Test memory
    ("JMP", AddressingMode.EXTENDED): InstructionInfo(0x7E, 3, 3, 2),   # Jump extended
    ("CLR", AddressingMode.EXTENDED): InstructionInfo(0x7F, 3, 5, 2),   # Clear memory

    # =========================================================================
    # HD6303-SPECIFIC BIT MANIPULATION INSTRUCTIONS
    # These are unique to the HD6303 (not found in 6801/6803)
    # Format: AIM #mask, address (AND immediate with memory)
    #         OIM #mask, address (OR immediate with memory)
    #         EIM #mask, address (XOR immediate with memory)
    #         TIM #mask, address (Test immediate with memory, no store)
    # =========================================================================

    # Indexed mode (offset,X) - opcode + mask + offset = 3 bytes
    ("AIM", AddressingMode.INDEXED): InstructionInfo(0x61, 3, 7, 2),   # AND immediate with memory
    ("OIM", AddressingMode.INDEXED): InstructionInfo(0x62, 3, 7, 2),   # OR immediate with memory
    ("EIM", AddressingMode.INDEXED): InstructionInfo(0x65, 3, 7, 2),   # XOR immediate with memory
    ("TIM", AddressingMode.INDEXED): InstructionInfo(0x6B, 3, 5, 2),   # Test immediate with memory

    # Direct mode (zero page) - opcode + mask + address = 3 bytes
    ("AIM", AddressingMode.DIRECT): InstructionInfo(0x71, 3, 6, 2),    # AND immediate with memory
    ("OIM", AddressingMode.DIRECT): InstructionInfo(0x72, 3, 6, 2),    # OR immediate with memory
    ("EIM", AddressingMode.DIRECT): InstructionInfo(0x75, 3, 6, 2),    # XOR immediate with memory
    ("TIM", AddressingMode.DIRECT): InstructionInfo(0x7B, 3, 4, 2),    # Test immediate with memory

    # =========================================================================
    # ACCUMULATOR A OPERATIONS
    # =========================================================================

    # Immediate mode
    ("SUBA", AddressingMode.IMMEDIATE): InstructionInfo(0x80, 2, 2, 1),  # Subtract from A
    ("CMPA", AddressingMode.IMMEDIATE): InstructionInfo(0x81, 2, 2, 1),  # Compare A
    ("SBCA", AddressingMode.IMMEDIATE): InstructionInfo(0x82, 2, 2, 1),  # Subtract with borrow from A
    ("ANDA", AddressingMode.IMMEDIATE): InstructionInfo(0x84, 2, 2, 1),  # AND with A
    ("BITA", AddressingMode.IMMEDIATE): InstructionInfo(0x85, 2, 2, 1),  # Bit test A
    ("LDAA", AddressingMode.IMMEDIATE): InstructionInfo(0x86, 2, 2, 1),  # Load A
    ("EORA", AddressingMode.IMMEDIATE): InstructionInfo(0x88, 2, 2, 1),  # XOR with A
    ("ADCA", AddressingMode.IMMEDIATE): InstructionInfo(0x89, 2, 2, 1),  # Add with carry to A
    ("ORAA", AddressingMode.IMMEDIATE): InstructionInfo(0x8A, 2, 2, 1),  # OR with A
    ("ADDA", AddressingMode.IMMEDIATE): InstructionInfo(0x8B, 2, 2, 1),  # Add to A

    # Direct mode (zero page)
    ("SUBA", AddressingMode.DIRECT): InstructionInfo(0x90, 2, 3, 1),
    ("CMPA", AddressingMode.DIRECT): InstructionInfo(0x91, 2, 3, 1),
    ("SBCA", AddressingMode.DIRECT): InstructionInfo(0x92, 2, 3, 1),
    ("ANDA", AddressingMode.DIRECT): InstructionInfo(0x94, 2, 3, 1),
    ("BITA", AddressingMode.DIRECT): InstructionInfo(0x95, 2, 3, 1),
    ("LDAA", AddressingMode.DIRECT): InstructionInfo(0x96, 2, 3, 1),
    ("STAA", AddressingMode.DIRECT): InstructionInfo(0x97, 2, 3, 1),    # Store A
    ("EORA", AddressingMode.DIRECT): InstructionInfo(0x98, 2, 3, 1),
    ("ADCA", AddressingMode.DIRECT): InstructionInfo(0x99, 2, 3, 1),
    ("ORAA", AddressingMode.DIRECT): InstructionInfo(0x9A, 2, 3, 1),
    ("ADDA", AddressingMode.DIRECT): InstructionInfo(0x9B, 2, 3, 1),

    # Indexed mode
    ("SUBA", AddressingMode.INDEXED): InstructionInfo(0xA0, 2, 4, 1),
    ("CMPA", AddressingMode.INDEXED): InstructionInfo(0xA1, 2, 4, 1),
    ("SBCA", AddressingMode.INDEXED): InstructionInfo(0xA2, 2, 4, 1),
    ("ANDA", AddressingMode.INDEXED): InstructionInfo(0xA4, 2, 4, 1),
    ("BITA", AddressingMode.INDEXED): InstructionInfo(0xA5, 2, 4, 1),
    ("LDAA", AddressingMode.INDEXED): InstructionInfo(0xA6, 2, 4, 1),
    ("STAA", AddressingMode.INDEXED): InstructionInfo(0xA7, 2, 4, 1),
    ("EORA", AddressingMode.INDEXED): InstructionInfo(0xA8, 2, 4, 1),
    ("ADCA", AddressingMode.INDEXED): InstructionInfo(0xA9, 2, 4, 1),
    ("ORAA", AddressingMode.INDEXED): InstructionInfo(0xAA, 2, 4, 1),
    ("ADDA", AddressingMode.INDEXED): InstructionInfo(0xAB, 2, 4, 1),

    # Extended mode
    ("SUBA", AddressingMode.EXTENDED): InstructionInfo(0xB0, 3, 4, 2),
    ("CMPA", AddressingMode.EXTENDED): InstructionInfo(0xB1, 3, 4, 2),
    ("SBCA", AddressingMode.EXTENDED): InstructionInfo(0xB2, 3, 4, 2),
    ("ANDA", AddressingMode.EXTENDED): InstructionInfo(0xB4, 3, 4, 2),
    ("BITA", AddressingMode.EXTENDED): InstructionInfo(0xB5, 3, 4, 2),
    ("LDAA", AddressingMode.EXTENDED): InstructionInfo(0xB6, 3, 4, 2),
    ("STAA", AddressingMode.EXTENDED): InstructionInfo(0xB7, 3, 4, 2),
    ("EORA", AddressingMode.EXTENDED): InstructionInfo(0xB8, 3, 4, 2),
    ("ADCA", AddressingMode.EXTENDED): InstructionInfo(0xB9, 3, 4, 2),
    ("ORAA", AddressingMode.EXTENDED): InstructionInfo(0xBA, 3, 4, 2),
    ("ADDA", AddressingMode.EXTENDED): InstructionInfo(0xBB, 3, 4, 2),

    # =========================================================================
    # ACCUMULATOR B OPERATIONS
    # =========================================================================

    # Immediate mode
    ("SUBB", AddressingMode.IMMEDIATE): InstructionInfo(0xC0, 2, 2, 1),
    ("CMPB", AddressingMode.IMMEDIATE): InstructionInfo(0xC1, 2, 2, 1),
    ("SBCB", AddressingMode.IMMEDIATE): InstructionInfo(0xC2, 2, 2, 1),
    ("ANDB", AddressingMode.IMMEDIATE): InstructionInfo(0xC4, 2, 2, 1),
    ("BITB", AddressingMode.IMMEDIATE): InstructionInfo(0xC5, 2, 2, 1),
    ("LDAB", AddressingMode.IMMEDIATE): InstructionInfo(0xC6, 2, 2, 1),
    ("EORB", AddressingMode.IMMEDIATE): InstructionInfo(0xC8, 2, 2, 1),
    ("ADCB", AddressingMode.IMMEDIATE): InstructionInfo(0xC9, 2, 2, 1),
    ("ORAB", AddressingMode.IMMEDIATE): InstructionInfo(0xCA, 2, 2, 1),
    ("ADDB", AddressingMode.IMMEDIATE): InstructionInfo(0xCB, 2, 2, 1),

    # Direct mode
    ("SUBB", AddressingMode.DIRECT): InstructionInfo(0xD0, 2, 3, 1),
    ("CMPB", AddressingMode.DIRECT): InstructionInfo(0xD1, 2, 3, 1),
    ("SBCB", AddressingMode.DIRECT): InstructionInfo(0xD2, 2, 3, 1),
    ("ANDB", AddressingMode.DIRECT): InstructionInfo(0xD4, 2, 3, 1),
    ("BITB", AddressingMode.DIRECT): InstructionInfo(0xD5, 2, 3, 1),
    ("LDAB", AddressingMode.DIRECT): InstructionInfo(0xD6, 2, 3, 1),
    ("STAB", AddressingMode.DIRECT): InstructionInfo(0xD7, 2, 3, 1),
    ("EORB", AddressingMode.DIRECT): InstructionInfo(0xD8, 2, 3, 1),
    ("ADCB", AddressingMode.DIRECT): InstructionInfo(0xD9, 2, 3, 1),
    ("ORAB", AddressingMode.DIRECT): InstructionInfo(0xDA, 2, 3, 1),
    ("ADDB", AddressingMode.DIRECT): InstructionInfo(0xDB, 2, 3, 1),

    # Indexed mode
    ("SUBB", AddressingMode.INDEXED): InstructionInfo(0xE0, 2, 4, 1),
    ("CMPB", AddressingMode.INDEXED): InstructionInfo(0xE1, 2, 4, 1),
    ("SBCB", AddressingMode.INDEXED): InstructionInfo(0xE2, 2, 4, 1),
    ("ANDB", AddressingMode.INDEXED): InstructionInfo(0xE4, 2, 4, 1),
    ("BITB", AddressingMode.INDEXED): InstructionInfo(0xE5, 2, 4, 1),
    ("LDAB", AddressingMode.INDEXED): InstructionInfo(0xE6, 2, 4, 1),
    ("STAB", AddressingMode.INDEXED): InstructionInfo(0xE7, 2, 4, 1),
    ("EORB", AddressingMode.INDEXED): InstructionInfo(0xE8, 2, 4, 1),
    ("ADCB", AddressingMode.INDEXED): InstructionInfo(0xE9, 2, 4, 1),
    ("ORAB", AddressingMode.INDEXED): InstructionInfo(0xEA, 2, 4, 1),
    ("ADDB", AddressingMode.INDEXED): InstructionInfo(0xEB, 2, 4, 1),

    # Extended mode
    ("SUBB", AddressingMode.EXTENDED): InstructionInfo(0xF0, 3, 4, 2),
    ("CMPB", AddressingMode.EXTENDED): InstructionInfo(0xF1, 3, 4, 2),
    ("SBCB", AddressingMode.EXTENDED): InstructionInfo(0xF2, 3, 4, 2),
    ("ANDB", AddressingMode.EXTENDED): InstructionInfo(0xF4, 3, 4, 2),
    ("BITB", AddressingMode.EXTENDED): InstructionInfo(0xF5, 3, 4, 2),
    ("LDAB", AddressingMode.EXTENDED): InstructionInfo(0xF6, 3, 4, 2),
    ("STAB", AddressingMode.EXTENDED): InstructionInfo(0xF7, 3, 4, 2),
    ("EORB", AddressingMode.EXTENDED): InstructionInfo(0xF8, 3, 4, 2),
    ("ADCB", AddressingMode.EXTENDED): InstructionInfo(0xF9, 3, 4, 2),
    ("ORAB", AddressingMode.EXTENDED): InstructionInfo(0xFA, 3, 4, 2),
    ("ADDB", AddressingMode.EXTENDED): InstructionInfo(0xFB, 3, 4, 2),

    # =========================================================================
    # 16-BIT OPERATIONS (D register = A:B)
    # =========================================================================

    # SUBD - Subtract from D
    ("SUBD", AddressingMode.IMMEDIATE): InstructionInfo(0x83, 3, 3, 2),  # 16-bit immediate
    ("SUBD", AddressingMode.DIRECT): InstructionInfo(0x93, 2, 4, 1),
    ("SUBD", AddressingMode.INDEXED): InstructionInfo(0xA3, 2, 5, 1),
    ("SUBD", AddressingMode.EXTENDED): InstructionInfo(0xB3, 3, 5, 2),

    # ADDD - Add to D
    ("ADDD", AddressingMode.IMMEDIATE): InstructionInfo(0xC3, 3, 3, 2),  # 16-bit immediate
    ("ADDD", AddressingMode.DIRECT): InstructionInfo(0xD3, 2, 4, 1),
    ("ADDD", AddressingMode.INDEXED): InstructionInfo(0xE3, 2, 5, 1),
    ("ADDD", AddressingMode.EXTENDED): InstructionInfo(0xF3, 3, 5, 2),

    # LDD - Load D
    ("LDD", AddressingMode.IMMEDIATE): InstructionInfo(0xCC, 3, 3, 2),   # 16-bit immediate
    ("LDD", AddressingMode.DIRECT): InstructionInfo(0xDC, 2, 4, 1),
    ("LDD", AddressingMode.INDEXED): InstructionInfo(0xEC, 2, 5, 1),
    ("LDD", AddressingMode.EXTENDED): InstructionInfo(0xFC, 3, 5, 2),

    # STD - Store D
    ("STD", AddressingMode.DIRECT): InstructionInfo(0xDD, 2, 4, 1),
    ("STD", AddressingMode.INDEXED): InstructionInfo(0xED, 2, 5, 1),
    ("STD", AddressingMode.EXTENDED): InstructionInfo(0xFD, 3, 5, 2),

    # =========================================================================
    # INDEX REGISTER (X) OPERATIONS
    # =========================================================================

    # CPX - Compare X
    ("CPX", AddressingMode.IMMEDIATE): InstructionInfo(0x8C, 3, 3, 2),   # 16-bit immediate
    ("CPX", AddressingMode.DIRECT): InstructionInfo(0x9C, 2, 4, 1),
    ("CPX", AddressingMode.INDEXED): InstructionInfo(0xAC, 2, 5, 1),
    ("CPX", AddressingMode.EXTENDED): InstructionInfo(0xBC, 3, 5, 2),

    # NOTE: CPD (Compare D) is NOT an HD6303 instruction - it's 68HC11 only!
    # The HD6303 does not have CPD. Use CMPA/CMPB or SUBD for comparisons.
    # These entries have been removed to prevent generating invalid opcodes.

    # LDX - Load X
    ("LDX", AddressingMode.IMMEDIATE): InstructionInfo(0xCE, 3, 3, 2),   # 16-bit immediate
    ("LDX", AddressingMode.DIRECT): InstructionInfo(0xDE, 2, 4, 1),
    ("LDX", AddressingMode.INDEXED): InstructionInfo(0xEE, 2, 5, 1),
    ("LDX", AddressingMode.EXTENDED): InstructionInfo(0xFE, 3, 5, 2),

    # STX - Store X
    ("STX", AddressingMode.DIRECT): InstructionInfo(0xDF, 2, 4, 1),
    ("STX", AddressingMode.INDEXED): InstructionInfo(0xEF, 2, 5, 1),
    ("STX", AddressingMode.EXTENDED): InstructionInfo(0xFF, 3, 5, 2),

    # =========================================================================
    # STACK POINTER (S) OPERATIONS
    # =========================================================================

    # LDS - Load Stack Pointer
    ("LDS", AddressingMode.IMMEDIATE): InstructionInfo(0x8E, 3, 3, 2),   # 16-bit immediate
    ("LDS", AddressingMode.DIRECT): InstructionInfo(0x9E, 2, 4, 1),
    ("LDS", AddressingMode.INDEXED): InstructionInfo(0xAE, 2, 5, 1),
    ("LDS", AddressingMode.EXTENDED): InstructionInfo(0xBE, 3, 5, 2),

    # STS - Store Stack Pointer
    ("STS", AddressingMode.DIRECT): InstructionInfo(0x9F, 2, 4, 1),
    ("STS", AddressingMode.INDEXED): InstructionInfo(0xAF, 2, 5, 1),
    ("STS", AddressingMode.EXTENDED): InstructionInfo(0xBF, 3, 5, 2),

    # =========================================================================
    # BRANCH INSTRUCTIONS (relative addressing)
    # All branch instructions are 2 bytes: opcode + signed offset
    # Offset is relative to address of byte AFTER the branch instruction
    # Range: -128 to +127 bytes
    # =========================================================================

    ("BRA", AddressingMode.RELATIVE): InstructionInfo(0x20, 2, 3, 1),   # Branch always
    ("BRN", AddressingMode.RELATIVE): InstructionInfo(0x21, 2, 3, 1),   # Branch never (NOP)
    ("BHI", AddressingMode.RELATIVE): InstructionInfo(0x22, 2, 3, 1),   # Branch if higher (C=0 and Z=0)
    ("BLS", AddressingMode.RELATIVE): InstructionInfo(0x23, 2, 3, 1),   # Branch if lower or same (C=1 or Z=1)
    ("BCC", AddressingMode.RELATIVE): InstructionInfo(0x24, 2, 3, 1),   # Branch if carry clear
    ("BHS", AddressingMode.RELATIVE): InstructionInfo(0x24, 2, 3, 1),   # Alias: Branch if higher or same
    ("BCS", AddressingMode.RELATIVE): InstructionInfo(0x25, 2, 3, 1),   # Branch if carry set
    ("BLO", AddressingMode.RELATIVE): InstructionInfo(0x25, 2, 3, 1),   # Alias: Branch if lower
    ("BNE", AddressingMode.RELATIVE): InstructionInfo(0x26, 2, 3, 1),   # Branch if not equal (Z=0)
    ("BEQ", AddressingMode.RELATIVE): InstructionInfo(0x27, 2, 3, 1),   # Branch if equal (Z=1)
    ("BVC", AddressingMode.RELATIVE): InstructionInfo(0x28, 2, 3, 1),   # Branch if overflow clear
    ("BVS", AddressingMode.RELATIVE): InstructionInfo(0x29, 2, 3, 1),   # Branch if overflow set
    ("BPL", AddressingMode.RELATIVE): InstructionInfo(0x2A, 2, 3, 1),   # Branch if plus (N=0)
    ("BMI", AddressingMode.RELATIVE): InstructionInfo(0x2B, 2, 3, 1),   # Branch if minus (N=1)
    ("BGE", AddressingMode.RELATIVE): InstructionInfo(0x2C, 2, 3, 1),   # Branch if >= (signed)
    ("BLT", AddressingMode.RELATIVE): InstructionInfo(0x2D, 2, 3, 1),   # Branch if < (signed)
    ("BGT", AddressingMode.RELATIVE): InstructionInfo(0x2E, 2, 3, 1),   # Branch if > (signed)
    ("BLE", AddressingMode.RELATIVE): InstructionInfo(0x2F, 2, 3, 1),   # Branch if <= (signed)
    ("BSR", AddressingMode.RELATIVE): InstructionInfo(0x8D, 2, 5, 1),   # Branch to subroutine

    # =========================================================================
    # JUMP/CALL INSTRUCTIONS
    # JSR - Jump to Subroutine (pushes return address)
    # =========================================================================

    ("JSR", AddressingMode.DIRECT): InstructionInfo(0x9D, 2, 5, 1),
    ("JSR", AddressingMode.INDEXED): InstructionInfo(0xAD, 2, 5, 1),
    ("JSR", AddressingMode.EXTENDED): InstructionInfo(0xBD, 3, 6, 2),
}


# =============================================================================
# Instruction Set Reference Lists
# =============================================================================

# Set of all valid mnemonics (for lexer/parser validation)
MNEMONICS: frozenset[str] = frozenset({
    mnemonic for mnemonic, _ in OPCODE_TABLE.keys()
})

# Branch instructions that use relative addressing
BRANCH_INSTRUCTIONS: frozenset[str] = frozenset({
    "BRA", "BRN", "BHI", "BLS", "BCC", "BHS", "BCS", "BLO",
    "BNE", "BEQ", "BVC", "BVS", "BPL", "BMI", "BGE", "BLT",
    "BGT", "BLE", "BSR",
})

# Instructions that require 16-bit immediate operand
WORD_IMMEDIATE_INSTRUCTIONS: frozenset[str] = frozenset({
    "LDD", "LDX", "LDS", "CPX", "ADDD", "SUBD",  # Note: CPD removed - not valid HD6303
})

# Instructions that cannot use immediate mode (store instructions)
NO_IMMEDIATE_INSTRUCTIONS: frozenset[str] = frozenset({
    "STAA", "STAB", "STD", "STX", "STS",
})

# Instructions that only have inherent mode
INHERENT_ONLY_INSTRUCTIONS: frozenset[str] = frozenset({
    "NOP", "RTS", "RTI", "SWI", "WAI", "SLP", "TRAP",
    "TAB", "TBA", "TAP", "TPA", "ABA", "SBA", "CBA",
    "ASLD", "LSLD", "LSRD", "MUL", "DAA", "XGDX",
    "INX", "DEX", "INS", "DES", "TSX", "TXS", "ABX",
    "PSHA", "PSHB", "PSHX", "PULA", "PULB", "PULX",
    "NEGA", "NEGB", "COMA", "COMB", "LSRA", "LSRB",
    "RORA", "RORB", "ASRA", "ASRB", "ASLA", "ASLB",
    "LSLA", "LSLB", "ROLA", "ROLB", "DECA", "DECB",
    "INCA", "INCB", "TSTA", "TSTB", "CLRA", "CLRB",
    "CLC", "SEC", "CLV", "SEV", "CLI", "SEI",
})


# =============================================================================
# Lookup Functions
# =============================================================================

def get_instruction_info(
    mnemonic: str,
    mode: AddressingMode
) -> Optional[InstructionInfo]:
    """
    Look up instruction information by mnemonic and addressing mode.

    Args:
        mnemonic: The instruction mnemonic (e.g., "LDAA")
        mode: The addressing mode

    Returns:
        InstructionInfo if found, None if the combination is invalid
    """
    return OPCODE_TABLE.get((mnemonic.upper(), mode))


def get_valid_modes(mnemonic: str) -> list[AddressingMode]:
    """
    Get all valid addressing modes for an instruction.

    Args:
        mnemonic: The instruction mnemonic

    Returns:
        List of valid AddressingModes for this instruction
    """
    mnemonic = mnemonic.upper()
    return [
        mode for (m, mode) in OPCODE_TABLE.keys()
        if m == mnemonic
    ]


def is_valid_instruction(mnemonic: str) -> bool:
    """
    Check if a mnemonic is a valid HD6303 instruction.

    Args:
        mnemonic: The instruction mnemonic to check

    Returns:
        True if valid, False otherwise
    """
    return mnemonic.upper() in MNEMONICS


def is_branch_instruction(mnemonic: str) -> bool:
    """
    Check if an instruction is a branch (uses relative addressing).

    Args:
        mnemonic: The instruction mnemonic

    Returns:
        True if it's a branch instruction
    """
    return mnemonic.upper() in BRANCH_INSTRUCTIONS


def uses_word_immediate(mnemonic: str) -> bool:
    """
    Check if an instruction uses 16-bit immediate values.

    Instructions like LDX, LDD, LDS, CPX use 16-bit immediate
    values instead of 8-bit.

    Args:
        mnemonic: The instruction mnemonic

    Returns:
        True if 16-bit immediate, False if 8-bit
    """
    return mnemonic.upper() in WORD_IMMEDIATE_INSTRUCTIONS
