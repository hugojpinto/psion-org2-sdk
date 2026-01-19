"""
HD6303 Disassembler
===================

Disassembles HD6303 machine code into human-readable assembly language.
This is the inverse operation of the assembler's code generation.

The HD6303 is the CPU used in the Psion Organiser II. It's a Hitachi
derivative of the Motorola 6800 family with additional instructions
for bit manipulation (AIM, OIM, EIM, TIM) and other enhancements (XGDX, SLP).

Architecture:
    - 8-bit data bus, 16-bit address bus
    - Registers: A, B (8-bit), D (A:B combined, 16-bit), X (16-bit index), SP, PC
    - Big-endian byte ordering (most significant byte first)

Addressing Modes:
    - INHERENT: No operand (NOP, RTS, PSHA)
    - IMMEDIATE: Literal value (#$xx or ##$xxxx)
    - DIRECT: Zero-page address ($00-$FF)
    - EXTENDED: Full 16-bit address ($xxxx)
    - INDEXED: X register + offset (offset,X)
    - RELATIVE: PC-relative branch (signed 8-bit displacement)

Usage:
    disasm = HD6303Disassembler()

    # Disassemble from bytes
    instructions = disasm.disassemble(memory_bytes, start_address=0x8000, count=10)

    # Disassemble single instruction
    instr = disasm.disassemble_one(memory_bytes, address=0x8000)
    print(f"{instr.address:04X}: {instr.mnemonic} {instr.operand_str}")

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Tuple

from ..assembler.opcodes import OPCODE_TABLE, AddressingMode


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class DisassembledInstruction:
    """
    Represents a single disassembled HD6303 instruction.

    Attributes:
        address: Memory address of the instruction
        opcode: The opcode byte(s)
        mnemonic: The instruction mnemonic (e.g., "LDAA", "JSR")
        mode: The addressing mode used
        operand_bytes: Raw operand bytes (may be empty)
        operand_str: Formatted operand string for display
        size: Total instruction size in bytes
        raw_bytes: All bytes comprising this instruction
        comment: Optional comment (e.g., for branch targets, known addresses)
    """
    address: int
    opcode: int
    mnemonic: str
    mode: AddressingMode
    operand_bytes: bytes
    operand_str: str
    size: int
    raw_bytes: bytes
    comment: str = ""

    def __str__(self) -> str:
        """Format as assembly line: ADDRESS: MNEMONIC OPERAND"""
        hex_bytes = " ".join(f"{b:02X}" for b in self.raw_bytes)
        # Pad hex bytes to consistent width (max 3 bytes = 8 chars with spaces)
        hex_bytes = hex_bytes.ljust(8)

        if self.operand_str:
            asm = f"{self.mnemonic} {self.operand_str}"
        else:
            asm = self.mnemonic

        if self.comment:
            return f"${self.address:04X}: {hex_bytes}  {asm:<16} ; {self.comment}"
        else:
            return f"${self.address:04X}: {hex_bytes}  {asm}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "address": f"${self.address:04X}",
            "address_int": self.address,
            "opcode": f"${self.opcode:02X}",
            "mnemonic": self.mnemonic,
            "mode": str(self.mode),
            "operand": self.operand_str,
            "size": self.size,
            "bytes": [f"${b:02X}" for b in self.raw_bytes],
            "comment": self.comment,
        }


# =============================================================================
# HD6303 Disassembler
# =============================================================================

class HD6303Disassembler:
    """
    Disassembler for HD6303 machine code.

    This class builds a reverse lookup table from the assembler's OPCODE_TABLE
    to efficiently decode instructions from their binary representation.

    The disassembler handles all HD6303 addressing modes and produces
    output compatible with the psasm assembler syntax.

    Attributes:
        _reverse_table: Maps opcode byte to (mnemonic, mode, size, operand_size)
        _symbol_table: Optional symbol table for address annotation
    """

    def __init__(self, symbol_table: Optional[Dict[int, str]] = None):
        """
        Initialize the disassembler.

        Args:
            symbol_table: Optional dict mapping addresses to symbol names.
                         Used to annotate disassembly with meaningful labels.
        """
        self._symbol_table = symbol_table or {}
        self._reverse_table = self._build_reverse_table()

    def _build_reverse_table(self) -> Dict[int, Tuple[str, AddressingMode, int, int]]:
        """
        Build reverse lookup table: opcode -> (mnemonic, mode, size, operand_size).

        The assembler's OPCODE_TABLE is keyed by (mnemonic, mode). We invert this
        to create a table keyed by opcode byte for efficient disassembly.

        Note: Some opcodes have multiple mnemonics (aliases like ASLA/LSLA).
        We prefer the canonical form (first one encountered).

        Returns:
            Dictionary mapping opcode bytes to instruction info tuples.
        """
        reverse = {}

        for (mnemonic, mode), info in OPCODE_TABLE.items():
            opcode = info.opcode

            # Skip aliases - keep first mnemonic encountered
            # (ASLD vs LSLD, ASLA vs LSLA, etc.)
            if opcode in reverse:
                continue

            reverse[opcode] = (mnemonic, mode, info.size, info.operand_size)

        return reverse

    def disassemble_one(
        self,
        data: bytes,
        address: int = 0,
        offset: int = 0
    ) -> DisassembledInstruction:
        """
        Disassemble a single instruction.

        Args:
            data: Byte buffer containing the instruction
            address: Memory address of the instruction (for display and branch targets)
            offset: Offset into data buffer where instruction starts

        Returns:
            DisassembledInstruction with decoded information

        Raises:
            ValueError: If data is too short or opcode is invalid
        """
        if offset >= len(data):
            raise ValueError(f"Offset {offset} beyond data length {len(data)}")

        opcode = data[offset]

        # Look up instruction info
        if opcode not in self._reverse_table:
            # Unknown opcode - return as data byte
            return DisassembledInstruction(
                address=address,
                opcode=opcode,
                mnemonic=".BYTE",
                mode=AddressingMode.INHERENT,
                operand_bytes=bytes(),
                operand_str=f"${opcode:02X}",
                size=1,
                raw_bytes=bytes([opcode]),
                comment="unknown opcode"
            )

        mnemonic, mode, size, operand_size = self._reverse_table[opcode]

        # Ensure we have enough bytes
        if offset + size > len(data):
            # Partial instruction - return what we have
            partial = data[offset:]
            return DisassembledInstruction(
                address=address,
                opcode=opcode,
                mnemonic=mnemonic,
                mode=mode,
                operand_bytes=bytes(),
                operand_str="???",
                size=len(partial),
                raw_bytes=bytes(partial),
                comment="incomplete instruction"
            )

        # Extract raw bytes
        raw_bytes = data[offset:offset + size]
        operand_bytes = raw_bytes[1:]  # Everything after opcode

        # Format operand based on addressing mode
        operand_str, comment = self._format_operand(
            mnemonic, mode, operand_bytes, address, size
        )

        return DisassembledInstruction(
            address=address,
            opcode=opcode,
            mnemonic=mnemonic,
            mode=mode,
            operand_bytes=bytes(operand_bytes),
            operand_str=operand_str,
            size=size,
            raw_bytes=bytes(raw_bytes),
            comment=comment
        )

    def _format_operand(
        self,
        mnemonic: str,
        mode: AddressingMode,
        operand_bytes: bytes,
        address: int,
        size: int
    ) -> Tuple[str, str]:
        """
        Format the operand string based on addressing mode.

        Args:
            mnemonic: The instruction mnemonic
            mode: The addressing mode
            operand_bytes: The operand bytes (after opcode)
            address: Instruction address (for relative branch calculation)
            size: Total instruction size

        Returns:
            Tuple of (operand_string, comment_string)
        """
        comment = ""

        if mode == AddressingMode.INHERENT:
            # No operand
            return "", ""

        elif mode == AddressingMode.IMMEDIATE:
            # #$xx or #$xxxx
            if len(operand_bytes) == 1:
                value = operand_bytes[0]
                operand_str = f"#${value:02X}"
                # Add ASCII comment for printable chars
                if 0x20 <= value < 0x7F:
                    comment = f"'{chr(value)}'"
            else:
                # 16-bit immediate (big-endian)
                value = (operand_bytes[0] << 8) | operand_bytes[1]
                operand_str = f"#${value:04X}"
                # Check symbol table
                if value in self._symbol_table:
                    comment = self._symbol_table[value]
            return operand_str, comment

        elif mode == AddressingMode.DIRECT:
            # Zero-page address
            addr = operand_bytes[0]
            operand_str = f"${addr:02X}"
            # Check for known zero-page variables
            if addr in self._symbol_table:
                comment = self._symbol_table[addr]
            return operand_str, comment

        elif mode == AddressingMode.EXTENDED:
            # Full 16-bit address (big-endian)
            addr = (operand_bytes[0] << 8) | operand_bytes[1]
            operand_str = f"${addr:04X}"
            # Check symbol table
            if addr in self._symbol_table:
                comment = self._symbol_table[addr]
            return operand_str, comment

        elif mode == AddressingMode.INDEXED:
            # Check for HD6303 bit manipulation instructions (AIM, OIM, EIM, TIM)
            # These have format: opcode, mask, offset (3 bytes)
            if mnemonic in ("AIM", "OIM", "EIM", "TIM"):
                mask = operand_bytes[0]
                offset = operand_bytes[1]
                operand_str = f"#${mask:02X},${offset:02X},X"
                return operand_str, comment

            # Normal indexed: offset,X
            offset = operand_bytes[0]
            operand_str = f"${offset:02X},X"
            return operand_str, comment

        elif mode == AddressingMode.RELATIVE:
            # PC-relative branch
            # Displacement is signed 8-bit, relative to address AFTER instruction
            disp = operand_bytes[0]
            if disp >= 0x80:
                disp = disp - 256  # Sign extend

            target = address + size + disp
            operand_str = f"${target:04X}"

            # Calculate displacement for comment
            if disp >= 0:
                comment = f"+{disp}"
            else:
                comment = f"{disp}"

            # Check symbol table for target
            if target in self._symbol_table:
                comment = self._symbol_table[target]

            return operand_str, comment

        else:
            # Fallback: show raw bytes
            hex_str = " ".join(f"${b:02X}" for b in operand_bytes)
            return hex_str, "unknown mode"

    def disassemble(
        self,
        data: bytes,
        start_address: int = 0,
        count: Optional[int] = None,
        max_bytes: Optional[int] = None
    ) -> List[DisassembledInstruction]:
        """
        Disassemble multiple instructions.

        Args:
            data: Byte buffer containing machine code
            start_address: Memory address of first byte
            count: Maximum number of instructions to disassemble (None = all)
            max_bytes: Maximum number of bytes to process (None = all)

        Returns:
            List of DisassembledInstruction objects
        """
        result = []
        offset = 0
        address = start_address
        instructions = 0

        while offset < len(data):
            # Check limits
            if count is not None and instructions >= count:
                break
            if max_bytes is not None and offset >= max_bytes:
                break

            instr = self.disassemble_one(data, address, offset)
            result.append(instr)

            offset += instr.size
            address += instr.size
            instructions += 1

        return result

    def disassemble_to_text(
        self,
        data: bytes,
        start_address: int = 0,
        count: Optional[int] = None
    ) -> str:
        """
        Disassemble and return formatted text output.

        This is a convenience method for getting a complete disassembly listing.

        Args:
            data: Byte buffer containing machine code
            start_address: Memory address of first byte
            count: Maximum number of instructions

        Returns:
            Multi-line string with disassembly listing
        """
        instructions = self.disassemble(data, start_address, count)
        return "\n".join(str(instr) for instr in instructions)

    def add_symbol(self, address: int, name: str) -> None:
        """
        Add a symbol to the symbol table.

        Args:
            address: The address value
            name: The symbol name
        """
        self._symbol_table[address] = name

    def add_symbols(self, symbols: Dict[int, str]) -> None:
        """
        Add multiple symbols to the symbol table.

        Args:
            symbols: Dictionary mapping addresses to names
        """
        self._symbol_table.update(symbols)


# =============================================================================
# Well-Known Psion II Addresses
# =============================================================================

# These are common addresses that can be used to annotate disassembly output.
# They are defined as module constants for easy reference.

PSION_SYSTEM_SYMBOLS = {
    # OPL Runtime Variables (stable across all models)
    0xA5: "RTA_SP",      # Language stack pointer
    0xA7: "RTA_FP",      # Frame pointer
    0xA9: "RTA_PC",      # QCode program counter
    0xB5: "DEFAULT_DEV", # Default device letter

    # Zero-page work areas
    0x40: "UTW_S0",
    0x80: "UTW_T0",
    0x84: "UTW_W0",
    0x86: "UTW_W1",
    0x88: "UTW_W2",

    # Hardware registers
    0x00: "P1DDR",
    0x02: "PORT1",
    0x06: "PORT6",
    0x08: "TCSR",

    # Common ROM entry points (may vary by ROM version)
    # These are examples from LZ64 ROM
}


def create_psion_disassembler() -> HD6303Disassembler:
    """
    Create a disassembler pre-configured with Psion system symbols.

    Returns:
        HD6303Disassembler with common Psion addresses annotated.
    """
    return HD6303Disassembler(symbol_table=PSION_SYSTEM_SYMBOLS.copy())
