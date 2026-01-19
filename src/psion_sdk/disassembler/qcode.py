"""
QCode Disassembler
==================

Disassembles OPL QCode (Query Code) bytecode into human-readable form.
QCode is the bytecode format executed by the Psion Organiser II's OPL
interpreter.

QCode Overview:
    OPL source code is compiled into QCode by the Psion's built-in translator.
    The QCode interpreter reads opcodes from memory (tracked by RTA_PC at $A9/$AA)
    and dispatches to handler routines.

Opcode Categories:
    - Control flow: RETURN ($7B), STOP ($59), procedure calls ($7D)
    - Stack operations: Push integer ($22), push string, operators
    - Functions: Built-in functions like USR ($9F), PEEKW ($9C), SIN ($B2)
    - Variables: Load/store local and global variables
    - I/O: PRINT, INPUT, BEEP, etc.

This disassembler focuses on opcodes relevant for debugging procedure call
injection (the _call_opl mechanism), but includes common opcodes for
general debugging.

Reference:
    https://www.jaapsch.net/psion/qcodes.htm
    Psion Technical Manual Section 17

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto


# =============================================================================
# QCode Opcode Definitions
# =============================================================================
# This table defines QCode opcodes, their mnemonics, and operand formats.
# Operand format codes:
#   "" = no operand
#   "b" = 1 byte
#   "w" = 2 bytes (big-endian word)
#   "s" = length-prefixed string (1 byte length + chars)
#   "p" = procedure name (1 byte length + chars, for $7D)
# =============================================================================

class QCodeCategory(Enum):
    """Categories of QCode operations for documentation."""
    CONTROL = auto()      # Flow control (return, stop)
    STACK = auto()        # Stack manipulation (push values)
    OPERATOR = auto()     # Arithmetic/logic operators
    FUNCTION = auto()     # Built-in functions (USR, PEEKW, etc.)
    VARIABLE = auto()     # Variable access
    IO = auto()           # Input/output operations
    SPECIAL = auto()      # Special/system opcodes


@dataclass
class QCodeInfo:
    """Information about a QCode opcode."""
    opcode: int
    mnemonic: str
    operand_format: str  # "", "b", "w", "s", "p"
    category: QCodeCategory
    description: str


# =============================================================================
# QCode Opcode Table
# =============================================================================
# This is a subset focusing on opcodes most relevant for debugging.
# A complete table would have ~256 entries.
#
# Key opcodes for _call_opl debugging:
#   $7D = QCO_PROC (procedure call - the main one we're injecting)
#   $22 = Push 16-bit integer (used to push addresses)
#   $9F = USR() function (calls machine code)
#   $7B = RETURN (exits procedure)
#   $59 = STOP (halts execution)
# =============================================================================

QCODE_TABLE: Dict[int, QCodeInfo] = {
    # =========================================================================
    # Control Flow
    # =========================================================================
    0x59: QCodeInfo(0x59, "STOP", "", QCodeCategory.CONTROL,
                    "Stop execution (also used with SIN for LZ prefix)"),
    0x7B: QCodeInfo(0x7B, "RETURN", "", QCodeCategory.CONTROL,
                    "Return from procedure"),
    0x7D: QCodeInfo(0x7D, "QCO_PROC", "p", QCodeCategory.CONTROL,
                    "Call procedure by name"),

    # =========================================================================
    # Stack Operations - Push Values
    # =========================================================================
    0x20: QCodeInfo(0x20, "PUSH_0", "", QCodeCategory.STACK,
                    "Push integer 0"),
    0x21: QCodeInfo(0x21, "PUSH_1", "", QCodeCategory.STACK,
                    "Push integer 1"),
    0x22: QCodeInfo(0x22, "PUSH_W", "w", QCodeCategory.STACK,
                    "Push 16-bit integer (big-endian)"),
    0x23: QCodeInfo(0x23, "PUSH_B", "b", QCodeCategory.STACK,
                    "Push 8-bit integer"),

    # =========================================================================
    # Arithmetic Operators (binary, pop 2, push 1)
    # =========================================================================
    0x46: QCodeInfo(0x46, "ADD", "", QCodeCategory.OPERATOR,
                    "Add top two stack values"),
    0x47: QCodeInfo(0x47, "SUB", "", QCodeCategory.OPERATOR,
                    "Subtract (second - top)"),
    0x48: QCodeInfo(0x48, "MUL", "", QCodeCategory.OPERATOR,
                    "Multiply"),
    0x49: QCodeInfo(0x49, "DIV", "", QCodeCategory.OPERATOR,
                    "Integer divide"),
    0x4A: QCodeInfo(0x4A, "MOD", "", QCodeCategory.OPERATOR,
                    "Modulo"),
    0x4B: QCodeInfo(0x4B, "POW", "", QCodeCategory.OPERATOR,
                    "Power (second ** top)"),
    0x4C: QCodeInfo(0x4C, "NEG", "", QCodeCategory.OPERATOR,
                    "Negate top of stack"),
    0x4D: QCodeInfo(0x4D, "ARG_SEP", "", QCodeCategory.OPERATOR,
                    "Argument separator"),

    # =========================================================================
    # Comparison Operators
    # =========================================================================
    0x52: QCodeInfo(0x52, "EQ", "", QCodeCategory.OPERATOR,
                    "Equal (==)"),
    0x53: QCodeInfo(0x53, "NE", "", QCodeCategory.OPERATOR,
                    "Not equal (<>)"),
    0x54: QCodeInfo(0x54, "GT", "", QCodeCategory.OPERATOR,
                    "Greater than (>)"),
    0x55: QCodeInfo(0x55, "LT", "", QCodeCategory.OPERATOR,
                    "Less than (<)"),
    0x56: QCodeInfo(0x56, "GE", "", QCodeCategory.OPERATOR,
                    "Greater or equal (>=)"),
    0x57: QCodeInfo(0x57, "LE", "", QCodeCategory.OPERATOR,
                    "Less or equal (<=)"),

    # =========================================================================
    # Logic Operators
    # =========================================================================
    0x58: QCodeInfo(0x58, "NOT", "", QCodeCategory.OPERATOR,
                    "Logical NOT"),
    0x5A: QCodeInfo(0x5A, "AND", "", QCodeCategory.OPERATOR,
                    "Logical AND"),
    0x5B: QCodeInfo(0x5B, "OR", "", QCodeCategory.OPERATOR,
                    "Logical OR"),

    # =========================================================================
    # Built-in Functions
    # =========================================================================
    0x9C: QCodeInfo(0x9C, "PEEKW", "", QCodeCategory.FUNCTION,
                    "Read word from memory address"),
    0x9D: QCodeInfo(0x9D, "PEEKB", "", QCodeCategory.FUNCTION,
                    "Read byte from memory address"),
    0x9E: QCodeInfo(0x9E, "ADDR", "", QCodeCategory.FUNCTION,
                    "Get address of variable"),
    0x9F: QCodeInfo(0x9F, "USR", "", QCodeCategory.FUNCTION,
                    "Call machine code (address, arg) -> result"),
    0xA0: QCodeInfo(0xA0, "POKEW", "", QCodeCategory.FUNCTION,
                    "Write word to memory address"),
    0xA1: QCodeInfo(0xA1, "POKEB", "", QCodeCategory.FUNCTION,
                    "Write byte to memory address"),

    # Math functions
    0xB0: QCodeInfo(0xB0, "ABS", "", QCodeCategory.FUNCTION,
                    "Absolute value"),
    0xB1: QCodeInfo(0xB1, "INT", "", QCodeCategory.FUNCTION,
                    "Integer part"),
    0xB2: QCodeInfo(0xB2, "SIN", "", QCodeCategory.FUNCTION,
                    "Sine (also part of LZ STOP+SIN prefix)"),
    0xB3: QCodeInfo(0xB3, "COS", "", QCodeCategory.FUNCTION,
                    "Cosine"),
    0xB4: QCodeInfo(0xB4, "TAN", "", QCodeCategory.FUNCTION,
                    "Tangent"),
    0xB5: QCodeInfo(0xB5, "EXP", "", QCodeCategory.FUNCTION,
                    "Exponential"),
    0xB6: QCodeInfo(0xB6, "LN", "", QCodeCategory.FUNCTION,
                    "Natural logarithm"),
    0xB7: QCodeInfo(0xB7, "LOG", "", QCodeCategory.FUNCTION,
                    "Base-10 logarithm"),
    0xB8: QCodeInfo(0xB8, "SQR", "", QCodeCategory.FUNCTION,
                    "Square root"),
    0xB9: QCodeInfo(0xB9, "RAD", "", QCodeCategory.FUNCTION,
                    "Degrees to radians"),
    0xBA: QCodeInfo(0xBA, "DEG", "", QCodeCategory.FUNCTION,
                    "Radians to degrees"),

    # =========================================================================
    # I/O Operations
    # =========================================================================
    0x84: QCodeInfo(0x84, "PRINT", "", QCodeCategory.IO,
                    "Print value (after expression)"),
    0x85: QCodeInfo(0x85, "LPRINT", "", QCodeCategory.IO,
                    "Print to printer"),
    0x86: QCodeInfo(0x86, "INPUT", "", QCodeCategory.IO,
                    "Input value"),

    # Display operations
    0xC0: QCodeInfo(0xC0, "CLS", "", QCodeCategory.IO,
                    "Clear screen"),
    0xC1: QCodeInfo(0xC1, "AT", "", QCodeCategory.IO,
                    "Position cursor (row, col)"),
    0xC2: QCodeInfo(0xC2, "BEEP", "", QCodeCategory.IO,
                    "Sound beep (duration, pitch)"),
    0xC3: QCodeInfo(0xC3, "PAUSE", "", QCodeCategory.IO,
                    "Pause for centiseconds"),

    # =========================================================================
    # Variable Access
    # =========================================================================
    0x00: QCodeInfo(0x00, "LOAD_L0", "", QCodeCategory.VARIABLE,
                    "Load local variable 0"),
    0x01: QCodeInfo(0x01, "LOAD_L1", "", QCodeCategory.VARIABLE,
                    "Load local variable 1"),
    0x02: QCodeInfo(0x02, "LOAD_L2", "", QCodeCategory.VARIABLE,
                    "Load local variable 2"),
    0x03: QCodeInfo(0x03, "LOAD_L3", "", QCodeCategory.VARIABLE,
                    "Load local variable 3"),
    0x04: QCodeInfo(0x04, "LOAD_L4", "", QCodeCategory.VARIABLE,
                    "Load local variable 4"),
    0x05: QCodeInfo(0x05, "LOAD_L5", "", QCodeCategory.VARIABLE,
                    "Load local variable 5"),
    0x06: QCodeInfo(0x06, "LOAD_L6", "", QCodeCategory.VARIABLE,
                    "Load local variable 6"),
    0x07: QCodeInfo(0x07, "LOAD_L7", "", QCodeCategory.VARIABLE,
                    "Load local variable 7"),

    0x08: QCodeInfo(0x08, "STORE_L0", "", QCodeCategory.VARIABLE,
                    "Store to local variable 0"),
    0x09: QCodeInfo(0x09, "STORE_L1", "", QCodeCategory.VARIABLE,
                    "Store to local variable 1"),
    0x0A: QCodeInfo(0x0A, "STORE_L2", "", QCodeCategory.VARIABLE,
                    "Store to local variable 2"),
    0x0B: QCodeInfo(0x0B, "STORE_L3", "", QCodeCategory.VARIABLE,
                    "Store to local variable 3"),
    0x0C: QCodeInfo(0x0C, "STORE_L4", "", QCodeCategory.VARIABLE,
                    "Store to local variable 4"),
    0x0D: QCodeInfo(0x0D, "STORE_L5", "", QCodeCategory.VARIABLE,
                    "Store to local variable 5"),
    0x0E: QCodeInfo(0x0E, "STORE_L6", "", QCodeCategory.VARIABLE,
                    "Store to local variable 6"),
    0x0F: QCodeInfo(0x0F, "STORE_L7", "", QCodeCategory.VARIABLE,
                    "Store to local variable 7"),

    0x10: QCodeInfo(0x10, "LOAD_G0", "", QCodeCategory.VARIABLE,
                    "Load global variable 0"),
    0x11: QCodeInfo(0x11, "LOAD_G1", "", QCodeCategory.VARIABLE,
                    "Load global variable 1"),
    0x12: QCodeInfo(0x12, "LOAD_G2", "", QCodeCategory.VARIABLE,
                    "Load global variable 2"),
    0x13: QCodeInfo(0x13, "LOAD_G3", "", QCodeCategory.VARIABLE,
                    "Load global variable 3"),

    0x18: QCodeInfo(0x18, "STORE_G0", "", QCodeCategory.VARIABLE,
                    "Store to global variable 0"),
    0x19: QCodeInfo(0x19, "STORE_G1", "", QCodeCategory.VARIABLE,
                    "Store to global variable 1"),
    0x1A: QCodeInfo(0x1A, "STORE_G2", "", QCodeCategory.VARIABLE,
                    "Store to global variable 2"),
    0x1B: QCodeInfo(0x1B, "STORE_G3", "", QCodeCategory.VARIABLE,
                    "Store to global variable 3"),

    # =========================================================================
    # Flow Control / Branches
    # =========================================================================
    0x60: QCodeInfo(0x60, "GOTO", "w", QCodeCategory.CONTROL,
                    "Unconditional jump (offset)"),
    0x61: QCodeInfo(0x61, "IF_FALSE", "w", QCodeCategory.CONTROL,
                    "Jump if top of stack is false"),
    0x62: QCodeInfo(0x62, "ELSE", "w", QCodeCategory.CONTROL,
                    "Jump (used after IF block)"),

    # =========================================================================
    # Procedure/Function Handling
    # =========================================================================
    0x78: QCodeInfo(0x78, "GLOBAL", "b", QCodeCategory.VARIABLE,
                    "Declare global variable"),
    0x79: QCodeInfo(0x79, "LOCAL", "b", QCodeCategory.VARIABLE,
                    "Declare local variable"),
    0x7A: QCodeInfo(0x7A, "EXTERNAL", "p", QCodeCategory.VARIABLE,
                    "Declare external reference"),
    0x7C: QCodeInfo(0x7C, "PROC_CALL", "b", QCodeCategory.CONTROL,
                    "Call with parameter count"),
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class DisassembledQCode:
    """
    Represents a single disassembled QCode instruction.

    Attributes:
        address: Memory address of the opcode
        opcode: The opcode byte
        mnemonic: Human-readable mnemonic
        operand_bytes: Raw operand bytes
        operand_str: Formatted operand string
        size: Total size in bytes
        raw_bytes: All bytes of this instruction
        description: Opcode description
        comment: Additional context (e.g., decoded procedure names)
    """
    address: int
    opcode: int
    mnemonic: str
    operand_bytes: bytes
    operand_str: str
    size: int
    raw_bytes: bytes
    description: str
    comment: str = ""

    def __str__(self) -> str:
        """Format as readable line."""
        hex_bytes = " ".join(f"{b:02X}" for b in self.raw_bytes)
        # Pad to consistent width
        hex_bytes = hex_bytes.ljust(17)  # Max: "7D 08 XX XX XX XX" = 17 chars

        if self.operand_str:
            asm = f"{self.mnemonic} {self.operand_str}"
        else:
            asm = self.mnemonic

        if self.comment:
            return f"${self.address:04X}: {hex_bytes}  {asm:<20} ; {self.comment}"
        else:
            return f"${self.address:04X}: {hex_bytes}  {asm}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "address": f"${self.address:04X}",
            "address_int": self.address,
            "opcode": f"${self.opcode:02X}",
            "mnemonic": self.mnemonic,
            "operand": self.operand_str,
            "size": self.size,
            "bytes": [f"${b:02X}" for b in self.raw_bytes],
            "description": self.description,
            "comment": self.comment,
        }


# =============================================================================
# QCode Disassembler
# =============================================================================

class QCodeDisassembler:
    """
    Disassembler for OPL QCode bytecode.

    This disassembler decodes QCode opcodes into human-readable form,
    which is particularly useful for:
    - Understanding OPL procedure behavior
    - Debugging the _call_opl QCode injection mechanism
    - Analyzing QCode buffers built at runtime

    The disassembler handles:
    - Simple opcodes (no operand)
    - Opcodes with byte/word operands
    - Procedure calls with name strings
    - The LZ STOP+SIN prefix sequence

    Usage:
        disasm = QCodeDisassembler()
        instructions = disasm.disassemble(qcode_bytes, start_address=0x2711)
        for instr in instructions:
            print(instr)
    """

    def __init__(self):
        """Initialize the QCode disassembler."""
        pass

    def disassemble_one(
        self,
        data: bytes,
        address: int = 0,
        offset: int = 0
    ) -> DisassembledQCode:
        """
        Disassemble a single QCode instruction.

        Args:
            data: Byte buffer containing QCode
            address: Memory address (for display)
            offset: Offset into buffer

        Returns:
            DisassembledQCode with decoded information
        """
        if offset >= len(data):
            raise ValueError(f"Offset {offset} beyond data length {len(data)}")

        opcode = data[offset]

        # Check if this is a known opcode
        if opcode in QCODE_TABLE:
            info = QCODE_TABLE[opcode]
            return self._decode_known_opcode(data, address, offset, info)
        else:
            # Unknown opcode - return as raw byte
            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=f"???_{opcode:02X}",
                operand_bytes=bytes(),
                operand_str="",
                size=1,
                raw_bytes=bytes([opcode]),
                description="Unknown opcode",
                comment=""
            )

    def _decode_known_opcode(
        self,
        data: bytes,
        address: int,
        offset: int,
        info: QCodeInfo
    ) -> DisassembledQCode:
        """
        Decode an opcode with known format.

        Args:
            data: Byte buffer
            address: Memory address
            offset: Offset into buffer
            info: QCode opcode information

        Returns:
            DisassembledQCode instance
        """
        opcode = data[offset]
        operand_format = info.operand_format
        comment = ""

        if operand_format == "":
            # No operand
            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=info.mnemonic,
                operand_bytes=bytes(),
                operand_str="",
                size=1,
                raw_bytes=bytes([opcode]),
                description=info.description,
                comment=""
            )

        elif operand_format == "b":
            # 1-byte operand
            if offset + 1 >= len(data):
                return self._incomplete_instruction(address, opcode, info)

            operand = data[offset + 1]
            operand_str = f"${operand:02X}"

            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=info.mnemonic,
                operand_bytes=bytes([operand]),
                operand_str=operand_str,
                size=2,
                raw_bytes=bytes(data[offset:offset + 2]),
                description=info.description,
                comment=""
            )

        elif operand_format == "w":
            # 2-byte word operand (big-endian)
            if offset + 2 >= len(data):
                return self._incomplete_instruction(address, opcode, info)

            hi = data[offset + 1]
            lo = data[offset + 2]
            word = (hi << 8) | lo
            operand_str = f"${word:04X}"

            # Add ASCII comment for small printable values
            if 0x20 <= word < 0x7F:
                comment = f"'{chr(word)}'"

            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=info.mnemonic,
                operand_bytes=bytes([hi, lo]),
                operand_str=operand_str,
                size=3,
                raw_bytes=bytes(data[offset:offset + 3]),
                description=info.description,
                comment=comment
            )

        elif operand_format == "p":
            # Procedure name: 1 byte length + name chars
            if offset + 1 >= len(data):
                return self._incomplete_instruction(address, opcode, info)

            name_len = data[offset + 1]
            if offset + 2 + name_len > len(data):
                return self._incomplete_instruction(address, opcode, info)

            name_bytes = data[offset + 2:offset + 2 + name_len]
            # Try to decode as ASCII
            try:
                name = name_bytes.decode('ascii')
            except UnicodeDecodeError:
                name = "".join(f"\\x{b:02X}" for b in name_bytes)

            operand_str = f'"{name}"'
            comment = f"length={name_len}"

            total_size = 2 + name_len  # opcode + length + name

            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=info.mnemonic,
                operand_bytes=bytes(data[offset + 1:offset + total_size]),
                operand_str=operand_str,
                size=total_size,
                raw_bytes=bytes(data[offset:offset + total_size]),
                description=info.description,
                comment=comment
            )

        else:
            # Unknown format - treat as no operand
            return DisassembledQCode(
                address=address,
                opcode=opcode,
                mnemonic=info.mnemonic,
                operand_bytes=bytes(),
                operand_str="",
                size=1,
                raw_bytes=bytes([opcode]),
                description=info.description,
                comment=f"unknown format: {operand_format}"
            )

    def _incomplete_instruction(
        self,
        address: int,
        opcode: int,
        info: QCodeInfo
    ) -> DisassembledQCode:
        """Create result for incomplete instruction at end of buffer."""
        return DisassembledQCode(
            address=address,
            opcode=opcode,
            mnemonic=info.mnemonic,
            operand_bytes=bytes(),
            operand_str="???",
            size=1,
            raw_bytes=bytes([opcode]),
            description=info.description,
            comment="incomplete - truncated data"
        )

    def disassemble(
        self,
        data: bytes,
        start_address: int = 0,
        count: Optional[int] = None,
        max_bytes: Optional[int] = None
    ) -> List[DisassembledQCode]:
        """
        Disassemble multiple QCode instructions.

        Args:
            data: Byte buffer containing QCode
            start_address: Memory address of first byte
            count: Maximum number of instructions (None = all)
            max_bytes: Maximum bytes to process (None = all)

        Returns:
            List of DisassembledQCode objects
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

        Args:
            data: Byte buffer containing QCode
            start_address: Memory address of first byte
            count: Maximum number of instructions

        Returns:
            Multi-line string with disassembly listing
        """
        instructions = self.disassemble(data, start_address, count)
        return "\n".join(str(instr) for instr in instructions)

    def disassemble_call_opl_buffer(
        self,
        data: bytes,
        start_address: int = 0
    ) -> str:
        """
        Specialized disassembly for _call_opl QCode buffers.

        This method provides enhanced output for the specific buffer format
        used by the _call_opl mechanism:
            $7D len name...  (QCO_PROC - call procedure)
            $22 HH LL        (push restore address)
            $22 HH LL        (push saved SP)
            $9F              (USR - call restore function)

        Args:
            data: The QCode buffer bytes
            start_address: Memory address of buffer

        Returns:
            Annotated disassembly string
        """
        result = []
        result.append(f"=== _call_opl Buffer Disassembly ===")
        result.append(f"Address: ${start_address:04X}")
        result.append(f"Size: {len(data)} bytes")
        result.append("")

        instructions = self.disassemble(data, start_address)

        for i, instr in enumerate(instructions):
            # Add annotations for known pattern
            annotation = ""
            if instr.opcode == 0x7D:
                annotation = "<-- QCO_PROC: Call procedure"
            elif instr.opcode == 0x22:
                if i > 0 and instructions[i-1].opcode == 0x7D:
                    annotation = "<-- Push _call_opl_restore address"
                elif i > 1 and instructions[i-2].opcode == 0x7D:
                    annotation = "<-- Push saved SP (for stack restore)"
            elif instr.opcode == 0x9F:
                annotation = "<-- USR: Call restore, return to C code"

            if annotation:
                result.append(f"{instr}  {annotation}")
            else:
                result.append(str(instr))

        result.append("")
        result.append("=== End of Buffer ===")

        return "\n".join(result)


# =============================================================================
# Convenience Functions
# =============================================================================

def detect_lz_prefix(data: bytes) -> bool:
    """
    Detect if QCode starts with the LZ 4-line mode prefix.

    The LZ prefix is $59 $B2 (STOP + SIN), which tells the LZ interpreter
    to stay in 4-line mode. On CM/XP, STOP executes first and terminates.

    Args:
        data: QCode bytes

    Returns:
        True if LZ prefix is present
    """
    if len(data) >= 2:
        return data[0] == 0x59 and data[1] == 0xB2
    return False


def is_call_opl_buffer(data: bytes) -> bool:
    """
    Heuristically detect if data looks like a _call_opl buffer.

    Pattern: $7D ... $22 ... $22 ... $9F

    Args:
        data: Byte buffer

    Returns:
        True if buffer matches _call_opl pattern
    """
    if len(data) < 7:  # Minimum: 7D 01 X 22 HH LL 9F
        return False

    # Should start with $7D (QCO_PROC)
    if data[0] != 0x7D:
        return False

    # Should end with $9F (USR)
    if data[-1] != 0x9F:
        return False

    # Should have two $22 opcodes before $9F
    count_22 = sum(1 for b in data[-7:-1] if b == 0x22)
    return count_22 >= 2
