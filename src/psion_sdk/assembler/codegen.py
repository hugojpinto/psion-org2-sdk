"""
HD6303 Code Generator
======================

This module generates HD6303 machine code from parsed assembly statements.
It implements a two-pass assembly process:

Pass 1 (Symbol Collection)
--------------------------
- Scan all statements sequentially
- Calculate sizes and addresses for each statement
- Build symbol table with label addresses
- Track forward references

Pass 2 (Code Generation)
------------------------
- Generate machine code for each statement
- Resolve forward references using symbol table
- Calculate branch offsets
- Validate address ranges

Output Formats
--------------
The code generator can produce:
- Raw binary code
- OB3 format (Psion ORG file)
- Listing file with addresses and source
- Symbol table file

OB3 File Format
---------------
```
Offset  Size  Description
------  ----  -----------
0       3     Magic: "ORG" (ASCII)
3       2     Data length (big-endian)
5       1     File type: $83 (procedure)
6       2     Object code length (big-endian)
8       n     Object code bytes
```
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import struct

from psion_sdk.errors import (
    AssemblerError,
    UndefinedSymbolError,
    DuplicateSymbolError,
    AddressingModeError,
    BranchRangeError,
    ExpressionError,
    DirectiveError,
    IncludeError,
    SourceLocation,
    ErrorCollector,
)
from psion_sdk.assembler.lexer import Token, TokenType, Lexer
from psion_sdk.assembler.parser import (
    Statement,
    LabelDef,
    Instruction,
    Directive,
    MacroDef,
    MacroCall,
    ConditionalBlock,
    Operand,
    ParsedAddressingMode,
    Parser,
)
from psion_sdk.assembler.opcodes import (
    AddressingMode,
    OPCODE_TABLE,
    BRANCH_INSTRUCTIONS,
    WORD_IMMEDIATE_INSTRUCTIONS,
    NO_IMMEDIATE_INSTRUCTIONS,
    get_instruction_info,
    get_valid_modes,
)
from psion_sdk.assembler.expressions import ExpressionEvaluator
from psion_sdk.opk.records import OB3File


# =============================================================================
# Relocator Stub for Self-Relocating Code
# =============================================================================
#
# This stub is prepended to user code when --relocatable mode is enabled.
# It performs runtime address discovery and patches all absolute addresses
# before jumping to the user's main code.
#
# The stub uses only position-independent code (BSR, BRA, indexed addressing).
# It was extracted from a working hand-written implementation and is 93 bytes.
#
# Structure of relocatable output:
#   [RELOCATOR_STUB (93 bytes)] + [USER_CODE] + [FIXUP_COUNT (2)] + [FIXUP_TABLE]
#
# The stub needs two offsets patched at assembly time:
#   - Byte 0x0D-0x0E: main_code_offset (constant: STUB_SIZE - 2 = 91)
#   - Byte 0x15-0x16: fixup_count_offset (variable: STUB_SIZE + user_code_len - 2)
#
RELOCATOR_STUB_SIZE = 93

# The stub bytes with placeholder values (XX) that get patched:
# - Bytes 0x0D-0x0E: MAIN_CODE offset from _ref_point
# - Bytes 0x15-0x16: FIXUP_COUNT offset from _ref_point
#
# The stub implements:
#   1. BSR _getpc to discover runtime address
#   2. Calculate load_base = runtime_addr - _ref_point_offset
#   3. For each fixup: patch_addr = main_code + offset; *patch_addr += load_base
#   4. Jump to main_code
#
RELOCATOR_STUB_TEMPLATE = bytes([
    # _entry:
    0x8D, 0x58,             # 0x00: BSR _getpc (branch to $005A)
    # _ref_point:
    0x3C,                   # 0x02: PSHX
    0x18,                   # 0x03: XGDX
    0x83, 0x00, 0x02,       # 0x04: SUBD #2 (ref_point - entry)
    0x37,                   # 0x07: PSHB
    0x36,                   # 0x08: PSHA
    0x30,                   # 0x09: TSX
    0xEC, 0x02,             # 0x0A: LDD 2,X (ref_addr: TSX gives X=SP, so X+2=hi, X+3=lo)
    0xC3, 0x00, 0x5B,       # 0x0C: ADDD #$005B (main_code - ref_point = 91)
    0x37,                   # 0x0F: PSHB
    0x36,                   # 0x10: PSHA
    0x30,                   # 0x11: TSX
    0xEC, 0x04,             # 0x12: LDD 4,X (ref_addr: TSX gives X=SP, so X+4=hi, X+5=lo)
    0xC3, 0x00, 0x00,       # 0x14: ADDD #XXXX (fixup_count - ref_point) PATCHED!
    0x18,                   # 0x17: XGDX
    0xEC, 0x00,             # 0x18: LDD 0,X
    0x08,                   # 0x1A: INX
    0x08,                   # 0x1B: INX
    0x83, 0x00, 0x00,       # 0x1C: SUBD #0 (test if D==0)
    0x27, 0x2E,             # 0x1F: BEQ _execute ($004F)
    # push loop state:
    0x3C,                   # 0x21: PSHX
    0x37,                   # 0x22: PSHB
    0x36,                   # 0x23: PSHA
    # _fixup_loop:
    0x30,                   # 0x24: TSX
    0xEC, 0x00,             # 0x25: LDD 0,X (count at X+0,X+1)
    0x27, 0x22,             # 0x27: BEQ _fixup_done ($004B)
    0x83, 0x00, 0x01,       # 0x29: SUBD #1
    0xED, 0x00,             # 0x2C: STD 0,X (count-- at X+0,X+1)
    0xEE, 0x02,             # 0x2E: LDX 2,X (table_ptr at X+2,X+3)
    0xEC, 0x00,             # 0x30: LDD 0,X (offset from table)
    0x08,                   # 0x32: INX
    0x08,                   # 0x33: INX
    0x3C,                   # 0x34: PSHX (new_table_ptr)
    0x30,                   # 0x35: TSX
    0xE3, 0x06,             # 0x36: ADDD 6,X (main_code at X+6,X+7)
    0x18,                   # 0x38: XGDX
    0xEC, 0x00,             # 0x39: LDD 0,X (current value at patch_addr)
    0x3C,                   # 0x3B: PSHX
    0x30,                   # 0x3C: TSX
    0xE3, 0x0A,             # 0x3D: ADDD 10,X (load_base at X+10,X+11)
    0xEE, 0x00,             # 0x3F: LDX 0,X (patch_addr at X+0,X+1)
    0xED, 0x00,             # 0x41: STD 0,X (store fixed value)
    0x38,                   # 0x43: PULX
    0x38,                   # 0x44: PULX (new_table_ptr)
    0x18,                   # 0x45: XGDX
    0x30,                   # 0x46: TSX
    0xED, 0x02,             # 0x47: STD 2,X (update table_ptr at X+2,X+3)
    0x20, 0xD9,             # 0x49: BRA _fixup_loop ($0024)
    # _fixup_done:
    0x31,                   # 0x4B: INS
    0x31,                   # 0x4C: INS
    0x31,                   # 0x4D: INS
    0x31,                   # 0x4E: INS
    # _execute:
    0x38,                   # 0x4F: PULX (pops main_code into X correctly)
    0x31,                   # 0x50: INS (clean load_base_hi)
    0x31,                   # 0x51: INS (clean load_base_lo)
    0x31,                   # 0x52: INS (clean ref_addr_hi)
    0x31,                   # 0x53: INS (clean ref_addr_lo)
    0x01,                   # 0x54: NOP (padding)
    0x01,                   # 0x55: NOP (padding)
    0x01,                   # 0x56: NOP (padding)
    0x01,                   # 0x57: NOP (padding)
    0x6E, 0x00,             # 0x58: JMP 0,X (jump to main!)
    # _getpc:
    0x38,                   # 0x5A: PULX
    0x6E, 0x00,             # 0x5B: JMP 0,X
])

# Offset in stub template where fixup_count_offset needs to be patched (2 bytes, big-endian)
RELOCATOR_STUB_FIXUP_OFFSET_PATCH_POS = 0x15

# The main_code offset is fixed: STUB_SIZE - _ref_point_offset = 93 - 2 = 91 = 0x5B
# This is already baked into the template at bytes 0x0D-0x0E


# =============================================================================
# Symbol Table Entry
# =============================================================================

@dataclass
class Symbol:
    """
    Symbol table entry.

    Attributes:
        name: Symbol name
        value: Resolved value (address or constant)
        location: Where the symbol was defined
        is_local: True for local labels (.label, @label)
        parent: Parent global label for local labels
        is_constant: True for EQU/SET defined symbols
        is_external: True for symbols from include files or -D defines
                     (these don't need relocation as they refer to
                     fixed OS addresses or external memory locations)
    """
    name: str
    value: int
    location: SourceLocation
    is_local: bool = False
    parent: Optional[str] = None
    is_constant: bool = False
    is_external: bool = False


# =============================================================================
# Code Generator
# =============================================================================

class CodeGenerator:
    """
    Generates HD6303 object code from parsed statements.

    The code generator maintains:
    - Symbol table with all labels and constants
    - Program counter tracking
    - Output code buffer
    - Error collection for batch reporting

    Usage:
        codegen = CodeGenerator()
        codegen.generate(statements)
        code = codegen.get_code()
        codegen.write_ob3("output.ob3")
    """

    # =========================================================================
    # Target Model Constants
    # =========================================================================
    # Valid target models for OB3 generation.
    # See dev_docs/TARGET_MODELS.md for full documentation.
    # =========================================================================
    VALID_TARGETS = ("CM", "XP", "LA", "LZ", "LZ64", "PORTABLE")
    DEFAULT_TARGET = "XP"

    def __init__(self, relocatable: bool = False, model_callback=None,
                 target: str = "XP"):
        """
        Initialize the code generator.

        Args:
            relocatable: If True, generate self-relocating code with a
                         position-independent stub and fixup table.
            model_callback: Optional callback function to be called when
                           .MODEL directive is encountered. Called with
                           (model_name: str) as argument.
            target: Target Psion model for OB3 generation. This affects
                    whether the STOP+SIN prefix is added for 4-line mode.
                    Valid values: CM, XP, LA (2-line), LZ, LZ64 (4-line),
                    PORTABLE (runs on any model). Default: XP
        """
        self._symbols: dict[str, Symbol] = {}
        self._code = bytearray()
        self._origin = 0
        self._pc = 0
        self._current_global_label: Optional[str] = None
        self._evaluator = ExpressionEvaluator()
        self._errors = ErrorCollector()
        self._include_paths: list[Path] = []
        self._listing_lines: list[str] = []
        self._processed_includes: set[str] = set()

        # Relocation support
        self._relocatable = relocatable
        self._fixups: list[int] = []      # Offsets from user_code_start to address words
        self._user_code_start = 0          # Offset in _code where user code begins
        self._in_include_file = False      # Track if we're processing an include file

        # Model callback for .MODEL directive
        self._model_callback = model_callback

        # Target model for OB3 generation
        # This determines whether STOP+SIN prefix is added (LZ/LZ64 only)
        self._target = target.upper() if target else self.DEFAULT_TARGET
        if self._target not in self.VALID_TARGETS:
            self._target = self.DEFAULT_TARGET

    # =========================================================================
    # Public Interface
    # =========================================================================

    def set_include_paths(self, paths: list[Path]) -> None:
        """Set paths to search for include files."""
        self._include_paths = paths

    def define_symbol(self, name: str, value: int, is_external: bool = True) -> None:
        """
        Pre-define a symbol (e.g., from command line -D option).

        Args:
            name: Symbol name
            value: Symbol value
            is_external: If True, symbol is external (doesn't need relocation)
                         Defaults to True for -D defines.
        """
        self._symbols[name] = Symbol(
            name=name,
            value=value,
            location=SourceLocation("<predefined>", 0, 0),
            is_constant=True,
            is_external=is_external
        )
        self._evaluator.set_symbol(name, value)

    def generate(self, statements: list[Statement]) -> bytes:
        """
        Generate object code from parsed statements.

        This is the main entry point for code generation.

        Args:
            statements: List of parsed statements

        Returns:
            Generated object code as bytes

        Raises:
            AssemblerError: If assembly fails (also check has_errors())
        """
        # Reset state
        self._code.clear()
        self._origin = 0
        self._pc = 0
        self._current_global_label = None
        self._errors.clear()
        self._listing_lines.clear()
        self._fixups.clear()
        self._user_code_start = 0  # Will be set properly in build_ob3 for relocatable

        # Pass 1: Collect symbols
        self._pass1(statements)

        if self._errors.has_errors():
            raise AssemblerError(f"Assembly failed with {self._errors.error_count()} errors")

        # Pass 2: Generate code
        self._pass2(statements)

        if self._errors.has_errors():
            raise AssemblerError(f"Assembly failed with {self._errors.error_count()} errors")

        return self.build_ob3()

    def get_code(self) -> bytes:
        """
        Return the generated object code (raw bytes without OB3 header).

        In relocatable mode, this returns:
        - Relocator stub (93 bytes)
        - User code (with addresses adjusted by stub size)
        - Fixup count (2 bytes, big-endian)
        - Fixup table (2 bytes per entry, big-endian)
        """
        if not self._relocatable:
            return bytes(self._code)

        # Build relocatable output: stub + user_code + fixup_count + fixup_table
        result = bytearray()

        # 1. Create patched stub
        #    The stub needs fixup_count_offset patched at bytes 0x15-0x16
        #    fixup_count_offset = STUB_SIZE + user_code_len - 2 (relative to _ref_point)
        user_code_len = len(self._code)
        fixup_count_offset = RELOCATOR_STUB_SIZE + user_code_len - 2

        stub = bytearray(RELOCATOR_STUB_TEMPLATE)
        # Patch fixup_count_offset at position 0x15-0x16 (big-endian)
        stub[RELOCATOR_STUB_FIXUP_OFFSET_PATCH_POS] = (fixup_count_offset >> 8) & 0xFF
        stub[RELOCATOR_STUB_FIXUP_OFFSET_PATCH_POS + 1] = fixup_count_offset & 0xFF

        result.extend(stub)

        # 2. Adjust and append user code
        #    Each address that will be relocated needs STUB_SIZE added to it.
        #    This is because the user code was assembled at ORG $0000, but after
        #    the stub is prepended, all addresses shift by STUB_SIZE bytes.
        #    The runtime relocator adds load_base (which points to the stub start),
        #    so we need: final_addr = original_addr + STUB_SIZE + load_base
        #    We handle the STUB_SIZE part here; the relocator handles load_base.
        user_code = bytearray(self._code)
        for offset in self._fixups:
            # Read current address (big-endian)
            hi = user_code[offset]
            lo = user_code[offset + 1]
            addr = (hi << 8) | lo
            # Add stub size to account for prepended stub
            addr += RELOCATOR_STUB_SIZE
            # Write back (big-endian)
            user_code[offset] = (addr >> 8) & 0xFF
            user_code[offset + 1] = addr & 0xFF

        result.extend(user_code)

        # 3. Append fixup count (2 bytes, big-endian)
        result.extend(struct.pack(">H", len(self._fixups)))

        # 4. Append fixup table (2 bytes per entry, big-endian)
        #    Each entry is an offset from main_code start to the address word to patch
        for offset in self._fixups:
            result.extend(struct.pack(">H", offset))

        return bytes(result)

    def build_ob3(self) -> bytes:
        """
        Build OB3 (ORG) format output as bytes.

        OB3 Format:
        - 3 bytes: "ORG" magic
        - 2 bytes: data length (big-endian)
        - 2 bytes: load address (big-endian)
        - n bytes: object code

        Returns:
            OB3 formatted bytes
        """
        result = bytearray()
        # Magic number "ORG"
        result.extend(b"ORG")
        # Data length (big-endian): address (2) + code length
        data_len = 2 + len(self._code)
        result.extend(struct.pack(">H", data_len))
        # Load address (big-endian)
        result.extend(struct.pack(">H", self._origin))
        # Object code
        result.extend(self._code)
        return bytes(result)

    def get_origin(self) -> int:
        """Return the origin address."""
        return self._origin

    def get_symbols(self) -> dict[str, int]:
        """Return a dictionary of symbol names to values."""
        return {name: sym.value for name, sym in self._symbols.items()}

    def has_errors(self) -> bool:
        """Check if any errors occurred during assembly."""
        return self._errors.has_errors()

    def get_error_report(self) -> str:
        """Get formatted error report."""
        return self._errors.report()

    # =========================================================================
    # Output File Writing
    # =========================================================================

    def set_target(self, target: str) -> None:
        """
        Set the target model for OB3 generation.

        This affects whether the STOP+SIN prefix is added to the OPL
        procedure wrapper when write_ob3() is called.

        Args:
            target: Target model (CM, XP, LA, LZ, LZ64, PORTABLE)
        """
        target_upper = target.upper() if target else self.DEFAULT_TARGET
        if target_upper in self.VALID_TARGETS:
            self._target = target_upper

    def get_target(self) -> str:
        """
        Get the current target model.

        Returns:
            Target model name (e.g., "XP", "LZ", "PORTABLE")
        """
        return self._target

    def write_ob3(self, filepath: str | Path) -> None:
        """
        Write output to OB3 (ORG) file format.

        The assembler output is wrapped in an OPL procedure structure
        that allows the machine code to be executed on the Psion.
        This matches the format produced by MAKEPROC.

        For 4-line targets (LZ, LZ64), a STOP+SIN prefix (0x52 0xB2)
        is added to the QCode. This identifies the procedure as 4-line
        to the LZ OS and causes graceful termination on 2-line machines.

        In relocatable mode, the machine code includes the self-relocating
        stub and fixup table generated by get_code().

        OB3 Format:
        - 3 bytes: "ORG" magic
        - 2 bytes: data length (big-endian)
        - 1 byte: file type ($83 for procedure)
        - 2 bytes: object code length (big-endian)
        - n bytes: object code (OPL procedure with embedded machine code)
        - 2 bytes: source length (0)

        See dev_docs/TARGET_MODELS.md for full documentation on target models.
        """
        # Get the machine code (handles relocatable mode via get_code())
        machine_code = self.get_code()

        # Wrap in OPL procedure format, passing target for STOP+SIN prefix
        ob3 = OB3File.from_machine_code(machine_code, target=self._target)

        with open(filepath, "wb") as f:
            f.write(ob3.to_bytes())

    def write_proc(self, filepath: str | Path) -> None:
        """
        Write the OPL-wrapped procedure (without OB3 header).

        This outputs just the procedure bytes that would go inside an OB3 file,
        without the "ORG" magic and length headers. Useful for comparison with
        DOS SDK output or embedding in custom pack formats.

        The procedure includes:
        - VVVV (2 bytes): Variable space
        - QQQQ (2 bytes): QCode length
        - XX (1 byte): Parameter count
        - Tables (8 bytes): Empty tables
        - [STOP+SIN] (2 bytes): Only for LZ/LZ64 targets
        - QCode bootstrap (14 bytes): Address computation and USR call
        - Machine code: The assembled code
        """
        machine_code = self.get_code()
        ob3 = OB3File.from_machine_code(machine_code, target=self._target)
        # The object_code field contains the OPL-wrapped procedure
        with open(filepath, "wb") as f:
            f.write(ob3.object_code)

    def get_listing(self) -> str:
        """
        Get the assembly listing as a string.

        Returns:
            The listing showing addresses, generated bytes, and source lines.
        """
        lines = []
        lines.append("Psion Assembler Listing")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Addr  Code          Line  Source")
        lines.append("-" * 60)
        lines.extend(self._listing_lines)
        lines.append("")
        lines.append("Symbol Table")
        lines.append("-" * 30)
        for name, sym in sorted(self._symbols.items()):
            lines.append(f"{name:20s} = ${sym.value:04X}")
        return "\n".join(lines)

    def write_listing(self, filepath: str | Path) -> None:
        """
        Write assembly listing file.

        The listing shows addresses, generated bytes, and source lines.
        """
        with open(filepath, "w") as f:
            f.write(self.get_listing())

    def write_symbols(self, filepath: str | Path) -> None:
        """
        Write symbol table file.

        Format: name address (one per line)
        """
        with open(filepath, "w") as f:
            f.write(f"# Symbol table\n")
            f.write(f"# Generated by psasm\n")
            for name, sym in sorted(self._symbols.items()):
                f.write(f"{name} ${sym.value:04X}\n")

    # =========================================================================
    # Pass 1: Symbol Collection
    # =========================================================================

    def _pass1(self, statements: list[Statement]) -> None:
        """
        First pass: collect symbols and calculate addresses.

        This pass:
        - Processes ORG directives to set program counter
        - Records label addresses in symbol table
        - Calculates instruction/data sizes to update PC
        - Processes EQU/SET for constants
        """
        self._pc = self._origin

        for i, stmt in enumerate(statements):
            try:
                # Skip LabelDef if next statement is EQU/SET with same label
                # (the parser creates both LabelDef and Directive for "LABEL EQU value")
                if isinstance(stmt, LabelDef) and i + 1 < len(statements):
                    next_stmt = statements[i + 1]
                    if (isinstance(next_stmt, Directive) and
                        next_stmt.name.upper() in ("EQU", "SET") and
                        next_stmt.label == stmt.name):
                        continue  # Skip LabelDef, EQU will define the symbol

                self._pass1_statement(stmt)
            except AssemblerError as e:
                self._errors.add(e)

    def _pass1_statement(self, stmt: Statement) -> None:
        """Process a single statement in pass 1."""
        if isinstance(stmt, LabelDef):
            self._define_label(stmt)

        elif isinstance(stmt, Instruction):
            size = self._calculate_instruction_size(stmt)
            self._pc += size

        elif isinstance(stmt, Directive):
            self._pass1_directive(stmt)

        elif isinstance(stmt, ConditionalBlock):
            self._pass1_conditional(stmt)

        elif isinstance(stmt, MacroDef):
            # Macro definitions don't generate code in pass 1
            pass

        elif isinstance(stmt, MacroCall):
            # Macro calls would be expanded here
            # For now, just estimate size based on macro definition
            pass

    def _define_label(self, label: LabelDef) -> None:
        """Define a label in the symbol table."""
        # Normalize name to uppercase for case-insensitive matching
        name = label.name.upper()

        # Resolve local label name
        if label.is_local:
            if self._current_global_label is None:
                raise AssemblerError(
                    f"local label '{name}' before any global label",
                    label.location
                )
            full_name = f"{self._current_global_label}{name}"
        else:
            full_name = name
            self._current_global_label = name

        # Check for duplicate
        if full_name in self._symbols:
            existing = self._symbols[full_name]
            raise DuplicateSymbolError(
                full_name,
                location=label.location,
                original_location=existing.location
            )

        # Add to symbol table
        self._symbols[full_name] = Symbol(
            name=full_name,
            value=self._pc,
            location=label.location,
            is_local=label.is_local,
            parent=self._current_global_label if label.is_local else None
        )
        self._evaluator.set_symbol(full_name, self._pc)

        # Also add original name for local labels
        if label.is_local and name not in self._symbols:
            self._symbols[name] = self._symbols[full_name]
            self._evaluator.set_symbol(name, self._pc)

    def _calculate_instruction_size(self, inst: Instruction) -> int:
        """Calculate the size of an instruction."""
        mnemonic = inst.mnemonic.upper()
        operand = inst.operand

        if operand is None or operand.mode == ParsedAddressingMode.INHERENT:
            info = get_instruction_info(mnemonic, AddressingMode.INHERENT)
            return info.size if info else 1

        mode = operand.mode

        if mode == ParsedAddressingMode.IMMEDIATE:
            # Look up actual size from opcode table to handle HD6303 prefix instructions
            info = get_instruction_info(mnemonic, AddressingMode.IMMEDIATE)
            if info:
                return info.size
            # Fallback for unknown instructions
            if mnemonic in WORD_IMMEDIATE_INSTRUCTIONS:
                return 3  # opcode + 2 bytes
            return 2  # opcode + 1 byte

        if mode == ParsedAddressingMode.INDEXED:
            # Look up actual size from opcode table to handle HD6303 prefix instructions
            info = get_instruction_info(mnemonic, AddressingMode.INDEXED)
            if info:
                return info.size
            return 2  # opcode + offset

        if mode == ParsedAddressingMode.RELATIVE:
            return 2  # opcode + displacement

        if mode == ParsedAddressingMode.DIRECT_OR_EXTENDED:
            # Need to evaluate to determine, default to extended for safety
            # First check if direct mode is even supported by this instruction
            has_direct = get_instruction_info(mnemonic, AddressingMode.DIRECT) is not None

            if operand.is_force_direct:
                return 2
            if operand.is_force_extended:
                return 3
            # If instruction doesn't support direct mode, must use extended
            if not has_direct:
                # Look up actual size from opcode table for extended mode
                info = get_instruction_info(mnemonic, AddressingMode.EXTENDED)
                return info.size if info else 3

            # CRITICAL: In relocatable mode, any reference to internal symbols
            # MUST use extended addressing because direct mode addresses cannot
            # be patched during relocation. Direct mode uses only the low byte
            # of the address, so JSR $3E would always jump to $003E even if the
            # code is loaded at $7000+.
            if self._relocatable:
                # Check if operand references any non-constant symbols
                for token in operand.tokens:
                    if token.type == TokenType.IDENTIFIER:
                        sym_name = token.value.upper()
                        # If symbol exists, check if it's a constant
                        if sym_name in self._symbols:
                            sym = self._symbols[sym_name]
                            if not sym.is_constant:
                                return 3  # Force extended for relocatable symbols
                        else:
                            # Unknown symbol - assume it's an internal label
                            return 3  # Force extended

            # Try to evaluate
            try:
                self._evaluator.set_pc(self._pc)
                value = self._evaluator.evaluate(operand.tokens, allow_undefined=True)
                if value <= 0xFF and not self._evaluator.get_undefined_symbols():
                    return 2  # Direct
                return 3  # Extended
            except ExpressionError:
                return 3  # Default to extended

        if mode in (ParsedAddressingMode.IMMEDIATE_DIRECT, ParsedAddressingMode.IMMEDIATE_INDEXED):
            return 3  # opcode + mask + address/offset

        return 3  # Default to 3 bytes (extended)

    def _pass1_directive(self, directive: Directive) -> None:
        """Process a directive in pass 1."""
        name = directive.name.upper()

        if name == "ORG":
            value = self._evaluate_constant(directive.arguments[0], directive.location)
            self._origin = value
            self._pc = value

        elif name in ("EQU", "SET"):
            if directive.label is None:
                raise DirectiveError(
                    f"{name} requires a label",
                    directive.location
                )
            value = self._evaluate_constant(directive.arguments[0], directive.location)
            self._define_constant(directive.label, value, directive.location)

        elif name == "FCB":
            # One byte per argument
            self._pc += len(directive.arguments)

        elif name == "FDB":
            # Two bytes per argument
            self._pc += 2 * len(directive.arguments)

        elif name == "FCC":
            # Count string length
            if directive.arguments and directive.arguments[0]:
                tok = directive.arguments[0][0]
                if tok.type == TokenType.STRING:
                    self._pc += len(tok.value)

        elif name == "RMB":
            count = self._evaluate_constant(directive.arguments[0], directive.location)
            self._pc += count

        elif name == "FILL":
            count = self._evaluate_constant(directive.arguments[1], directive.location)
            self._pc += count

        elif name == "ALIGN":
            boundary = self._evaluate_constant(directive.arguments[0], directive.location)
            if boundary > 0:
                self._pc = (self._pc + boundary - 1) // boundary * boundary

        elif name == "INCLUDE":
            # Process include file in pass 1
            self._process_include(directive)

        elif name == "INCBIN":
            # Add binary file size to PC
            filepath = self._resolve_include_path(directive.arguments[0][0].value, directive.location)
            if filepath:
                self._pc += filepath.stat().st_size

        elif name == "MODEL":
            # .MODEL directive - set target Psion model
            # This affects symbol definitions (DISP_ROWS, DISP_COLS, etc.)
            if directive.arguments and directive.arguments[0]:
                # Model name should be an identifier token
                tok = directive.arguments[0][0]
                if tok.type == TokenType.IDENTIFIER:
                    model_name = tok.value.upper()
                    if self._model_callback:
                        try:
                            self._model_callback(model_name)
                        except Exception as e:
                            self._errors.add_error(
                                DirectiveError(str(e), directive.location)
                            )
                else:
                    self._errors.add_error(
                        DirectiveError(
                            ".MODEL requires a model name (CM, XP, LA, LZ, or LZ64)",
                            directive.location
                        )
                    )
            else:
                self._errors.add_error(
                    DirectiveError(
                        ".MODEL requires a model name (CM, XP, LA, LZ, or LZ64)",
                        directive.location
                    )
                )

    def _pass1_conditional(self, cond: ConditionalBlock) -> None:
        """Process conditional assembly in pass 1."""
        # Evaluate condition
        condition_met = self._evaluate_condition(cond)

        # Process appropriate body with lookahead logic for EQU labels
        if condition_met:
            self._pass1_statements_with_lookahead(cond.if_body)
        else:
            self._pass1_statements_with_lookahead(cond.else_body)

    def _pass1_statements_with_lookahead(self, statements: list) -> None:
        """Process statements with lookahead to skip LabelDef before EQU/SET."""
        for i, stmt in enumerate(statements):
            # Skip LabelDef if next statement is EQU/SET with same label
            # (the parser creates both LabelDef and Directive for "LABEL EQU value")
            if isinstance(stmt, LabelDef) and i + 1 < len(statements):
                next_stmt = statements[i + 1]
                if (isinstance(next_stmt, Directive) and
                    next_stmt.name.upper() in ("EQU", "SET") and
                    next_stmt.label == stmt.name):
                    continue  # Skip LabelDef, EQU will define the symbol
            self._pass1_statement(stmt)

    def _evaluate_condition(self, cond: ConditionalBlock) -> bool:
        """Evaluate a conditional assembly condition."""
        if cond.condition_type == "IFDEF":
            if cond.condition_tokens:
                tok = cond.condition_tokens[0]
                if tok.type == TokenType.IDENTIFIER:
                    return tok.value in self._symbols
            return False

        if cond.condition_type == "IFNDEF":
            if cond.condition_tokens:
                tok = cond.condition_tokens[0]
                if tok.type == TokenType.IDENTIFIER:
                    return tok.value not in self._symbols
            return True

        if cond.condition_type == "IF":
            try:
                self._evaluator.set_pc(self._pc)
                value = self._evaluator.evaluate(cond.condition_tokens, allow_undefined=True)
                return value != 0
            except ExpressionError:
                return False

        return False

    def _define_constant(self, name: str, value: int, location: SourceLocation) -> None:
        """Define a constant symbol (EQU/SET)."""
        # Normalize name to uppercase for case-insensitive matching
        name = name.upper()

        # Constants from include files are external (OS addresses, system vars)
        # and don't need relocation
        is_external = self._in_include_file

        if name in self._symbols:
            existing = self._symbols[name]
            if not existing.is_constant:
                raise DuplicateSymbolError(
                    name,
                    location=location,
                    original_location=existing.location
                )
            # SET allows redefinition
            if existing.is_constant:
                # Update value, preserve external status from original
                self._symbols[name] = Symbol(
                    name=name,
                    value=value,
                    location=location,
                    is_constant=True,
                    is_external=existing.is_external or is_external
                )
                self._evaluator.set_symbol(name, value)
                return

        self._symbols[name] = Symbol(
            name=name,
            value=value,
            location=location,
            is_constant=True,
            is_external=is_external
        )
        self._evaluator.set_symbol(name, value)

    def _evaluate_constant(self, tokens: list[Token], location: SourceLocation) -> int:
        """Evaluate an expression that must be constant (no forward refs)."""
        try:
            self._evaluator.set_pc(self._pc)
            return self._evaluator.evaluate(tokens, location, allow_undefined=False)
        except UndefinedSymbolError:
            # For pass 1, allow forward references and return 0
            return self._evaluator.evaluate(tokens, location, allow_undefined=True)

    # =========================================================================
    # Pass 2: Code Generation
    # =========================================================================

    def _pass2(self, statements: list[Statement]) -> None:
        """
        Second pass: generate object code.

        This pass:
        - Generates machine code for instructions
        - Resolves all forward references
        - Calculates branch offsets
        - Handles data directives
        """
        self._pc = self._origin

        for i, stmt in enumerate(statements):
            try:
                # Skip LabelDef if next statement is EQU/SET with same label
                # (matches the skip in pass1)
                if isinstance(stmt, LabelDef) and i + 1 < len(statements):
                    next_stmt = statements[i + 1]
                    if (isinstance(next_stmt, Directive) and
                        next_stmt.name.upper() in ("EQU", "SET") and
                        next_stmt.label == stmt.name):
                        continue

                self._pass2_statement(stmt)
            except AssemblerError as e:
                self._errors.add(e)

    def _pass2_statement(self, stmt: Statement) -> None:
        """Process a single statement in pass 2."""
        start_pc = self._pc
        code_start = len(self._code)

        if isinstance(stmt, LabelDef):
            # Labels are already processed, just update current global
            if not stmt.is_local:
                self._current_global_label = stmt.name

        elif isinstance(stmt, Instruction):
            self._generate_instruction(stmt)
            # Add listing line for instruction
            code_bytes = self._code[code_start:]
            hex_str = " ".join(f"{b:02X}" for b in code_bytes) if code_bytes else ""
            self._listing_lines.append(
                f"${start_pc:04X}  {hex_str:12s}  {stmt.location.line:4d}  {stmt.mnemonic}"
            )

        elif isinstance(stmt, Directive):
            self._pass2_directive(stmt)
            # Add listing line for directive
            if stmt.name.upper() == "ORG":
                self._listing_lines.append(
                    f"              {stmt.location.line:4d}  {stmt.name}"
                )

        elif isinstance(stmt, ConditionalBlock):
            self._pass2_conditional(stmt)

        elif isinstance(stmt, MacroCall):
            self._expand_macro(stmt)

    def _generate_instruction(self, inst: Instruction) -> None:
        """Generate machine code for an instruction."""
        mnemonic = inst.mnemonic.upper()
        operand = inst.operand
        start_pc = self._pc

        # Set PC in evaluator for * and $ references
        self._evaluator.set_pc(self._pc)

        # Determine addressing mode and generate code
        if operand is None or operand.mode == ParsedAddressingMode.INHERENT:
            self._emit_inherent(mnemonic, inst.location)

        elif operand.mode == ParsedAddressingMode.IMMEDIATE:
            self._emit_immediate(mnemonic, operand, inst.location)

        elif operand.mode == ParsedAddressingMode.INDEXED:
            self._emit_indexed(mnemonic, operand, inst.location)

        elif operand.mode == ParsedAddressingMode.RELATIVE:
            self._emit_relative(mnemonic, operand, inst.location)

        elif operand.mode == ParsedAddressingMode.DIRECT_OR_EXTENDED:
            self._emit_direct_or_extended(mnemonic, operand, inst.location)

        elif operand.mode == ParsedAddressingMode.IMMEDIATE_DIRECT:
            self._emit_bit_manip_direct(mnemonic, operand, inst.location)

        elif operand.mode == ParsedAddressingMode.IMMEDIATE_INDEXED:
            self._emit_bit_manip_indexed(mnemonic, operand, inst.location)

    def _emit_inherent(self, mnemonic: str, location: SourceLocation) -> None:
        """Emit an inherent mode instruction."""
        info = get_instruction_info(mnemonic, AddressingMode.INHERENT)
        if info is None:
            raise AddressingModeError(
                mnemonic, "inherent", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )
        self._emit_opcode(info.opcode)
        self._pc += info.size

    def _emit_immediate(self, mnemonic: str, operand: Operand, location: SourceLocation) -> None:
        """Emit an immediate mode instruction."""
        if mnemonic in NO_IMMEDIATE_INSTRUCTIONS:
            raise AddressingModeError(
                mnemonic, "immediate", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        info = get_instruction_info(mnemonic, AddressingMode.IMMEDIATE)
        if info is None:
            raise AddressingModeError(
                mnemonic, "immediate", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        value = self._evaluator.evaluate(operand.tokens, location)

        # For word immediate instructions (LDX#, LDD#, etc.), check if we need
        # to record a fixup for relocation (only when value is an internal address)
        needs_fixup = (mnemonic in WORD_IMMEDIATE_INSTRUCTIONS and
                       self._needs_fixup(operand))

        self._emit_opcode(info.opcode)

        if mnemonic in WORD_IMMEDIATE_INSTRUCTIONS:
            # 16-bit immediate
            self._emit_word(value)
            # Record fixup after emitting the address word
            if needs_fixup:
                self._record_fixup()
        else:
            # 8-bit immediate
            self._emit_byte(value & 0xFF)
        self._pc += info.size

    def _emit_indexed(self, mnemonic: str, operand: Operand, location: SourceLocation) -> None:
        """Emit an indexed mode instruction."""
        info = get_instruction_info(mnemonic, AddressingMode.INDEXED)
        if info is None:
            raise AddressingModeError(
                mnemonic, "indexed", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        offset = self._evaluator.evaluate(operand.tokens, location)

        # Allow negative offsets (two's complement)
        # Values 0xFF80-0xFFFF represent -128 to -1 in 16-bit two's complement
        if offset > 0xFF7F:  # Convert 16-bit negative to signed
            offset = offset - 0x10000

        if offset < -128 or offset > 255:
            raise ExpressionError(
                f"indexed offset {offset} out of range (-128 to 255)",
                location
            )

        self._emit_opcode(info.opcode)
        self._emit_byte(offset & 0xFF)  # Convert to unsigned byte
        self._pc += info.size

    def _emit_relative(self, mnemonic: str, operand: Operand, location: SourceLocation) -> None:
        """Emit a relative (branch) instruction."""
        info = get_instruction_info(mnemonic, AddressingMode.RELATIVE)
        if info is None:
            raise AddressingModeError(
                mnemonic, "relative", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        target = self._evaluator.evaluate(operand.tokens, location)

        # Calculate offset from next instruction
        offset = target - (self._pc + 2)

        if offset < -128 or offset > 127:
            # Find target name for error message
            target_name = "target"
            if operand.tokens and operand.tokens[0].type == TokenType.IDENTIFIER:
                target_name = operand.tokens[0].value
            raise BranchRangeError(target_name, offset, location)

        self._emit_opcode(info.opcode)
        self._emit_byte(offset & 0xFF)
        self._pc += info.size

    def _emit_direct_or_extended(
        self,
        mnemonic: str,
        operand: Operand,
        location: SourceLocation
    ) -> None:
        """Emit direct or extended mode instruction based on address."""
        value = self._evaluator.evaluate(operand.tokens, location)

        # Determine mode - must match pass 1 logic for consistency
        use_direct = False
        if operand.is_force_direct:
            use_direct = True
        elif operand.is_force_extended:
            use_direct = False
        elif value <= 0xFF:
            # CRITICAL: In relocatable mode, any reference to internal symbols
            # MUST use extended addressing because direct mode addresses cannot
            # be patched during relocation. Direct mode uses only the low byte
            # of the address, so JSR $3E would always jump to $003E even if the
            # code is loaded at $7000+.
            if self._relocatable:
                # Check if operand references any non-constant symbols
                refs_internal_symbol = False
                for token in operand.tokens:
                    if token.type == TokenType.IDENTIFIER:
                        sym_name = token.value.upper()
                        if sym_name in self._symbols:
                            sym = self._symbols[sym_name]
                            if not sym.is_constant:
                                refs_internal_symbol = True
                                break
                if refs_internal_symbol:
                    use_direct = False
                else:
                    use_direct = True
            else:
                # Non-relocatable: Check if this was a forward reference in pass 1
                # In pass 1, forward refs default to extended mode (3 bytes)
                # We must use the same mode here for symbol addresses to be correct
                #
                # A symbol was a forward reference if its address >= the PC at the
                # start of this instruction (meaning it was defined later in pass 1)
                is_forward_ref = False
                for token in operand.tokens:
                    if token.type == TokenType.IDENTIFIER:
                        sym_name = token.value.upper()
                        if sym_name in self._symbols:
                            sym = self._symbols[sym_name]
                            # Skip forward reference check for EQU/SET constants
                            # Constants are not addresses, so comparing to PC is meaningless
                            if sym.is_constant:
                                continue
                            # If symbol's value >= current PC, it was a forward ref
                            if sym.value >= self._pc:
                                is_forward_ref = True
                                break
                use_direct = not is_forward_ref

        if use_direct:
            info = get_instruction_info(mnemonic, AddressingMode.DIRECT)
            if info is None:
                # Try extended
                info = get_instruction_info(mnemonic, AddressingMode.EXTENDED)
                use_direct = False

            if info is None:
                raise AddressingModeError(
                    mnemonic, "direct", location,
                    valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
                )

            if use_direct:
                self._emit_opcode(info.opcode)
                self._emit_byte(value & 0xFF)
                self._pc += info.size
                return

        # Extended mode
        info = get_instruction_info(mnemonic, AddressingMode.EXTENDED)
        if info is None:
            raise AddressingModeError(
                mnemonic, "extended", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        # Track fixup for relocation if this references internal symbols
        needs_fixup = self._needs_fixup(operand)

        self._emit_opcode(info.opcode)
        self._emit_word(value)

        # Record fixup offset (after emitting the address word)
        if needs_fixup:
            self._record_fixup()

        self._pc += info.size

    def _emit_bit_manip_direct(
        self,
        mnemonic: str,
        operand: Operand,
        location: SourceLocation
    ) -> None:
        """Emit HD6303 bit manipulation instruction with direct addressing."""
        info = get_instruction_info(mnemonic, AddressingMode.DIRECT)
        if info is None:
            raise AddressingModeError(
                mnemonic, "direct", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        mask = self._evaluator.evaluate(operand.mask_tokens, location)
        addr = self._evaluator.evaluate(operand.tokens, location)

        self._emit_opcode(info.opcode)
        self._emit_byte(mask & 0xFF)
        self._emit_byte(addr & 0xFF)
        self._pc += info.size

    def _emit_bit_manip_indexed(
        self,
        mnemonic: str,
        operand: Operand,
        location: SourceLocation
    ) -> None:
        """Emit HD6303 bit manipulation instruction with indexed addressing."""
        info = get_instruction_info(mnemonic, AddressingMode.INDEXED)
        if info is None:
            raise AddressingModeError(
                mnemonic, "indexed", location,
                valid_modes=[str(m) for m in get_valid_modes(mnemonic)]
            )

        mask = self._evaluator.evaluate(operand.mask_tokens, location)
        offset = self._evaluator.evaluate(operand.tokens, location)

        self._emit_opcode(info.opcode)
        self._emit_byte(mask & 0xFF)
        self._emit_byte(offset & 0xFF)
        self._pc += info.size

    # =========================================================================
    # Pass 2: Directive Processing
    # =========================================================================

    def _pass2_directive(self, directive: Directive) -> None:
        """Process a directive in pass 2."""
        name = directive.name.upper()

        if name == "ORG":
            value = self._evaluator.evaluate(directive.arguments[0], directive.location)
            self._origin = value
            self._pc = value

        elif name in ("EQU", "SET"):
            # Already processed in pass 1
            pass

        elif name == "FCB":
            for arg_tokens in directive.arguments:
                if arg_tokens and arg_tokens[0].type == TokenType.STRING:
                    # String argument - emit each character
                    for char in arg_tokens[0].value:
                        self._emit_byte(ord(char))
                        self._pc += 1
                else:
                    value = self._evaluator.evaluate(arg_tokens, directive.location)
                    self._emit_byte(value & 0xFF)
                    self._pc += 1

        elif name == "FDB":
            for arg_tokens in directive.arguments:
                value = self._evaluator.evaluate(arg_tokens, directive.location)
                self._emit_word(value)
                self._pc += 2

        elif name == "FCC":
            if directive.arguments and directive.arguments[0]:
                tok = directive.arguments[0][0]
                if tok.type == TokenType.STRING:
                    for char in tok.value:
                        self._emit_byte(ord(char))
                        self._pc += 1

        elif name == "RMB":
            count = self._evaluator.evaluate(directive.arguments[0], directive.location)
            for _ in range(count):
                self._emit_byte(0)
                self._pc += 1

        elif name == "FILL":
            value = self._evaluator.evaluate(directive.arguments[0], directive.location)
            count = self._evaluator.evaluate(directive.arguments[1], directive.location)
            for _ in range(count):
                self._emit_byte(value & 0xFF)
                self._pc += 1

        elif name == "ALIGN":
            boundary = self._evaluator.evaluate(directive.arguments[0], directive.location)
            if boundary > 0:
                target = (self._pc + boundary - 1) // boundary * boundary
                while self._pc < target:
                    self._emit_byte(0)
                    self._pc += 1

        elif name == "INCLUDE":
            # Process include file in pass 2
            self._process_include_pass2(directive)

        elif name == "INCBIN":
            filepath = self._resolve_include_path(
                directive.arguments[0][0].value,
                directive.location
            )
            if filepath:
                with open(filepath, "rb") as f:
                    data = f.read()
                for byte in data:
                    self._emit_byte(byte)
                    self._pc += 1

    def _pass2_conditional(self, cond: ConditionalBlock) -> None:
        """Process conditional assembly in pass 2."""
        condition_met = self._evaluate_condition(cond)

        if condition_met:
            for stmt in cond.if_body:
                self._pass2_statement(stmt)
        else:
            for stmt in cond.else_body:
                self._pass2_statement(stmt)

    def _expand_macro(self, call: MacroCall) -> None:
        """Expand a macro invocation."""
        # Find macro definition
        if call.name not in self._symbols:
            raise UndefinedSymbolError(call.name, call.location)

        # Macro expansion would substitute parameters and process body
        # For now, this is a placeholder
        pass

    # =========================================================================
    # Include File Processing
    # =========================================================================

    def _process_include(self, directive: Directive) -> None:
        """Process an INCLUDE directive in pass 1."""
        filename = directive.arguments[0][0].value
        filepath = self._resolve_include_path(filename, directive.location)

        if filepath is None:
            raise IncludeError(
                filename,
                "file not found",
                directive.location,
                search_paths=[str(p) for p in self._include_paths]
            )

        # Check for circular include
        abs_path = str(filepath.resolve())
        if abs_path in self._processed_includes:
            raise IncludeError(
                filename,
                "circular include detected",
                directive.location
            )

        self._processed_includes.add(abs_path)

        # Read and parse include file
        try:
            source = filepath.read_text()
            lexer = Lexer(source, str(filepath))
            tokens = list(lexer.tokenize())
            parser = Parser(tokens, str(filepath))
            statements = parser.parse()

            # Mark that we're in an include file so constants are marked external
            # (they represent OS addresses/system vars that don't need relocation)
            was_in_include = self._in_include_file
            self._in_include_file = True

            try:
                # Process statements (using same logic as _pass1 to handle EQU labels)
                for i, stmt in enumerate(statements):
                    # Skip LabelDef if next statement is EQU/SET with same label
                    if isinstance(stmt, LabelDef) and i + 1 < len(statements):
                        next_stmt = statements[i + 1]
                        if (isinstance(next_stmt, Directive) and
                            next_stmt.name.upper() in ("EQU", "SET") and
                            next_stmt.label == stmt.name):
                            continue
                    self._pass1_statement(stmt)
            finally:
                self._in_include_file = was_in_include

        except Exception as e:
            raise IncludeError(filename, str(e), directive.location)

    def _process_include_pass2(self, directive: Directive) -> None:
        """Process an INCLUDE directive in pass 2."""
        filename = directive.arguments[0][0].value
        filepath = self._resolve_include_path(filename, directive.location)

        if filepath is None:
            return  # Error already reported in pass 1

        try:
            source = filepath.read_text()
            lexer = Lexer(source, str(filepath))
            tokens = list(lexer.tokenize())
            parser = Parser(tokens, str(filepath))
            statements = parser.parse()

            # Process statements (using same logic as _pass2 to handle EQU labels)
            for i, stmt in enumerate(statements):
                # Skip LabelDef if next statement is EQU/SET with same label
                if isinstance(stmt, LabelDef) and i + 1 < len(statements):
                    next_stmt = statements[i + 1]
                    if (isinstance(next_stmt, Directive) and
                        next_stmt.name.upper() in ("EQU", "SET") and
                        next_stmt.label == stmt.name):
                        continue
                self._pass2_statement(stmt)

        except Exception:
            pass  # Error already reported in pass 1

    def _resolve_include_path(
        self,
        filename: str,
        location: SourceLocation
    ) -> Optional[Path]:
        """Resolve an include filename to a full path."""
        # Try relative to current file
        if location.filename != "<input>":
            current_dir = Path(location.filename).parent
            candidate = current_dir / filename
            if candidate.exists():
                return candidate

        # Try include paths
        for include_path in self._include_paths:
            candidate = include_path / filename
            if candidate.exists():
                return candidate

        # Try current directory
        candidate = Path(filename)
        if candidate.exists():
            return candidate

        return None

    # =========================================================================
    # Relocation Helpers
    # =========================================================================

    def _needs_fixup(self, operand: Operand) -> bool:
        """
        Check if an operand expression needs relocation.

        An expression needs fixup based on "relocation balance":
        - Each internal symbol in additive position: +1
        - Each internal symbol in subtractive position: -1
        - If final balance is 0, no fixup needed (e.g., _label2 - _label1)
        - If final balance is non-zero, fixup needed

        This correctly handles:
        - Simple addresses: LDX #_label → balance=1 → needs fixup
        - Differences: LDD #_label2-_label1 → balance=0 → no fixup
        - Offsets: LDX #_label+5 → balance=1 → needs fixup

        Args:
            operand: The operand to check

        Returns:
            True if the operand needs a relocation fixup
        """
        if not self._relocatable:
            return False

        # Track relocation balance
        # Positive = additive context, Negative = subtractive context
        balance = 0
        sign = 1  # Start in additive context

        for token in operand.tokens:
            if token.type == TokenType.IDENTIFIER:
                sym_name = token.value.upper()
                if sym_name in self._symbols:
                    sym = self._symbols[sym_name]
                    # Internal symbols affect the balance
                    if not sym.is_external:
                        balance += sign
            elif token.type == TokenType.PLUS:
                sign = 1  # Next symbol is additive
            elif token.type == TokenType.MINUS:
                sign = -1  # Next symbol is subtractive

        # If balance is non-zero, we need a fixup
        return balance != 0

    def _record_fixup(self) -> None:
        """
        Record a fixup for the current code position.

        The fixup offset is calculated from user_code_start to the address word
        that was just emitted (current position - 2 bytes back for the word).
        """
        if self._relocatable:
            # The address word starts 2 bytes before the current code position
            fixup_offset = len(self._code) - self._user_code_start - 2
            self._fixups.append(fixup_offset)

    # =========================================================================
    # Code Emission Helpers
    # =========================================================================

    def _emit_byte(self, value: int) -> None:
        """Emit a single byte to the output."""
        self._code.append(value & 0xFF)

    def _emit_word(self, value: int) -> None:
        """Emit a 16-bit word to the output (big-endian)."""
        self._code.append((value >> 8) & 0xFF)
        self._code.append(value & 0xFF)

    def _emit_opcode(self, opcode: int) -> int:
        """
        Emit an opcode (handles both single and multi-byte opcodes).

        Some Motorola 6800-family instructions use a prefix byte for extended
        addressing modes. These are stored as 2-byte values in the opcode table.
        Note: The HD6303 in the Psion does NOT have CPD (that's 68HC11 only).

        Returns the number of bytes emitted.
        """
        if opcode > 0xFF:
            # Multi-byte opcode: emit prefix byte first
            self._emit_byte(opcode >> 8)
            self._emit_byte(opcode & 0xFF)
            return 2
        else:
            self._emit_byte(opcode)
            return 1
