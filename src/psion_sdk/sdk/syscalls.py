"""
Psion Organiser II System Call Definitions
==========================================

This module provides comprehensive definitions of all system calls (services)
available on the Psion Organiser II operating system. System calls are invoked
using the SWI (Software Interrupt) instruction.

System Call Convention
----------------------
System calls are invoked by loading the service number into register A
and executing SWI:

    LDAA    #service_number     ; Load service number into A
    [setup parameters]          ; Set up B, X, UTW_S0-S5 as needed
    SWI                         ; Execute system call
    BCS     error_handler       ; Check carry flag for errors

Register Conventions:
- A: Service number (input), return value (output)
- B: Parameter or error code
- X: Parameter (often pointer) or return value
- UTW_S0-S5: Additional parameters ($41-$4C)
- Carry flag: 0=success, 1=error

Important: Assume all registers and UTW_S0-S5 are trashed by system
calls unless the documentation explicitly states they are preserved.

Reference
---------
- System services: https://www.jaapsch.net/psion/mcosintr.htm
- CM/XP services: https://www.jaapsch.net/psion/mcosxp1.htm
- LZ services: https://www.jaapsch.net/psion/mcoslz.htm
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from psion_sdk.sdk.models import (
    PsionModel,
    ALL_MODELS,
    TWO_LINE_MODELS,
    EXTENDED_SERVICE_MODELS,
)


# =============================================================================
# System Call Categories
# =============================================================================

class CallCategory(Enum):
    """
    Category of system call for organization and documentation.

    Calls are grouped by their functional area, matching the Psion
    naming convention (AL$xxx for allocator, DP$xxx for display, etc.)
    """
    ALLOCATOR = auto()      # AL$xxx - Memory allocation
    BATTERY = auto()        # BT$xxx - Power/NMI control
    BUZZER = auto()         # BZ$xxx - Sound output
    DISPLAY = auto()        # DP$xxx - LCD display
    DEVICE = auto()         # DV$xxx - Device management
    EDITOR = auto()         # ED$xxx - Line editing
    ERROR = auto()          # ER$xxx - Error handling
    FILE = auto()           # FL$xxx - File system
    FLOAT = auto()          # FN$xxx - Floating-point math
    INTERPRETER = auto()    # IT$xxx - Table interpreter
    KEYBOARD = auto()       # KB$xxx - Keyboard input
    LANGUAGE = auto()       # LG$xxx, LN$xxx - OPL language
    MENU = auto()           # MN$xxx - Menu display
    MATH = auto()           # MT$xxx - Math conversions
    PACK = auto()           # PK$xxx - Pack access
    RUNTIME = auto()        # RM$xxx - Program execution
    TOPLEVEL = auto()       # TL$xxx - Top-level menu
    TIME = auto()           # TM$xxx - Real-time clock
    UTILITY = auto()        # UT$xxx - General utilities
    EXTENDED = auto()       # LZ-specific extensions


# =============================================================================
# Parameter and Return Value Descriptions
# =============================================================================

@dataclass(frozen=True)
class Parameter:
    """
    Description of a system call parameter or return value.

    Attributes:
        register: Register name (A, B, X, D, UTW_S0, etc.)
        description: What this parameter represents
        optional: Whether the parameter is optional
    """
    register: str
    description: str
    optional: bool = False

    def __str__(self) -> str:
        opt = " (optional)" if self.optional else ""
        return f"{self.register}={self.description}{opt}"


# =============================================================================
# System Call Definition
# =============================================================================

@dataclass(frozen=True)
class SystemCall:
    """
    Definition of a Psion Organiser II system call.

    Each system call has a unique service number and documented
    parameter conventions.

    Attributes:
        name: Service name (e.g., "DP$EMIT", "KB$GETK")
        number: Service number (0x00-0xFF)
        description: Brief description of the service
        category: Functional category
        inputs: Tuple of input parameters
        outputs: Tuple of output values
        models: Set of models supporting this call
        notes: Additional usage notes
        errors: Common error codes returned

    Example:
        >>> call = SystemCall(
        ...     name="DP$EMIT",
        ...     number=0x10,
        ...     description="Output single character to display",
        ...     category=CallCategory.DISPLAY,
        ...     inputs=(Parameter("A", "character code"),),
        ...     outputs=(),
        ...     models=ALL_MODELS,
        ... )
    """
    name: str
    number: int
    description: str
    category: CallCategory
    models: frozenset[PsionModel]
    inputs: tuple[Parameter, ...] = field(default_factory=tuple)
    outputs: tuple[Parameter, ...] = field(default_factory=tuple)
    notes: str = ""
    errors: tuple[str, ...] = field(default_factory=tuple)

    def is_supported_on(self, model: PsionModel) -> bool:
        """Check if this call is supported on the given model."""
        return model in self.models

    def format_asm_equ(self, width: int = 12) -> str:
        """
        Format as an assembly EQU directive.

        Args:
            width: Minimum width for the name field

        Returns:
            Assembly line like "DP$EMIT      EQU $10    ; Output character"
        """
        return f"{self.name:<{width}} EQU ${self.number:02X}    ; {self.description}"

    def format_usage_example(self) -> str:
        """
        Generate an example usage pattern for this system call.

        Returns:
            Multi-line string showing typical usage
        """
        lines = [f"; {self.name} - {self.description}"]

        # Document inputs
        for param in self.inputs:
            if param.register == "A":
                lines.append(f"    LDAA    #{self.name}")
            elif param.register == "B":
                lines.append(f"    LDAB    #value      ; {param.description}")
            elif param.register == "X":
                lines.append(f"    LDX     #address    ; {param.description}")
            elif param.register == "D":
                lines.append(f"    LDD     #value      ; {param.description}")
            elif param.register.startswith("UTW_"):
                lines.append(f"    LDD     #value")
                lines.append(f"    STD     {param.register}  ; {param.description}")

        # Service number if not already loaded in A
        if not any(p.register == "A" for p in self.inputs):
            lines.append(f"    LDAA    #{self.name}")

        lines.append("    SWI")

        # Document outputs
        if self.outputs:
            for param in self.outputs:
                if param.register == "C":
                    lines.append("    BCS     error       ; Check for error")
                elif param.register == "Z":
                    lines.append("    BEQ     zero_result ; Check Z flag")

        return "\n".join(lines)


# =============================================================================
# Comprehensive System Call Definitions
# =============================================================================
# These definitions are based on the official Psion technical documentation
# and the comprehensive reference at https://www.jaapsch.net/psion/mcosintr.htm
# =============================================================================

SYSTEM_CALLS: tuple[SystemCall, ...] = (
    # =========================================================================
    # Allocator Services (AL$xxx) - Memory Management
    # =========================================================================

    SystemCall(
        name="AL$FREE", number=0x00,
        description="Deallocate memory cell",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(Parameter("X", "cell tag ($2000-$203E)"),),
        outputs=(),
        notes="Releases memory allocated by AL$GRAB",
    ),
    SystemCall(
        name="AL$GRAB", number=0x01,
        description="Allocate new memory cell",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(Parameter("D", "size in bytes"),),
        outputs=(
            Parameter("X", "cell tag"),
            Parameter("C", "error flag"),
        ),
        errors=("254: out of memory", "255: no free cells"),
    ),
    SystemCall(
        name="AL$GROW", number=0x02,
        description="Expand memory cell size",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(
            Parameter("X", "cell tag"),
            Parameter("D", "bytes to add"),
            Parameter("UTW_S0", "offset for insertion"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="AL$REPL", number=0x03,
        description="Replace portion of cell",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(
            Parameter("X", "cell tag"),
            Parameter("UTW_S0", "offset"),
            Parameter("D", "old size"),
            Parameter("UTW_S1", "new size"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="AL$SHNK", number=0x04,
        description="Shrink memory cell",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(
            Parameter("X", "cell tag"),
            Parameter("D", "bytes to remove"),
            Parameter("UTW_S0", "offset"),
        ),
        outputs=(),
    ),
    SystemCall(
        name="AL$SIZE", number=0x05,
        description="Get cell size",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(Parameter("X", "cell tag"),),
        outputs=(Parameter("D", "cell size in bytes"),),
    ),
    SystemCall(
        name="AL$ZERO", number=0x06,
        description="Shrink cell to zero bytes",
        category=CallCategory.ALLOCATOR, models=ALL_MODELS,
        inputs=(Parameter("X", "cell tag"),),
        outputs=(),
        notes="Cell remains allocated but empty",
    ),

    # =========================================================================
    # Battery/Power Services (BT$xxx)
    # =========================================================================

    SystemCall(
        name="BT$NMDN", number=0x07,
        description="Disable NMI (stops clock)",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="D and X are preserved. Stops real-time clock updates.",
    ),
    SystemCall(
        name="BT$NMEN", number=0x08,
        description="Re-enable NMI",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="D and X are preserved. Use after BT$NMDN.",
    ),
    SystemCall(
        name="BT$NOF", number=0x09,
        description="Disable NMI (preserves clock)",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Clock continues running but NMI processing is delayed.",
    ),
    SystemCall(
        name="BT$NON", number=0x0A,
        description="Re-enable NMI with sync",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Waits for next NMI before returning. Syncs clock.",
    ),
    SystemCall(
        name="BT$PPRG", number=0x0B,
        description="Push/pop scratch registers",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Data byte follows SWI instruction. Bit 7: push/pop.",
    ),
    SystemCall(
        name="BT$SWOF", number=0x0C,
        description="Switch off device",
        category=CallCategory.BATTERY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Returns after device is switched back on.",
    ),
    SystemCall(
        name="BT$TOFF", number=0x81,
        description="Switch off for specified time",
        category=CallCategory.BATTERY, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("D", "duration in seconds (2-1800)"),),
        outputs=(),
        notes="LZ only. Auto wake-up after specified time.",
    ),

    # =========================================================================
    # Buzzer Services (BZ$xxx)
    # =========================================================================

    SystemCall(
        name="BZ$ALRM", number=0x0D,
        description="Sound alarm tone",
        category=CallCategory.BUZZER, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Distinctive alarm sound pattern.",
    ),
    SystemCall(
        name="BZ$BELL", number=0x0E,
        description="Sound standard beep",
        category=CallCategory.BUZZER, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Short confirmation beep.",
    ),
    SystemCall(
        name="BZ$TONE", number=0x0F,
        description="Sound custom tone",
        category=CallCategory.BUZZER, models=ALL_MODELS,
        inputs=(
            Parameter("D", "pitch (lower value = higher pitch)"),
            Parameter("X", "duration in milliseconds"),
        ),
        outputs=(),
    ),

    # =========================================================================
    # Display Services (DP$xxx)
    # =========================================================================

    SystemCall(
        name="DP$EMIT", number=0x10,
        description="Output single character",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(Parameter("A", "ASCII character code"),),
        outputs=(),
        notes="Handles control characters and scrolling.",
    ),
    SystemCall(
        name="DP$PRNT", number=0x11,
        description="Print string at cursor",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(
            Parameter("X", "pointer to string"),
            Parameter("B", "string length"),
        ),
        outputs=(Parameter("X", "advanced past string"),),
        notes="String is NOT null-terminated; length is explicit.",
    ),
    SystemCall(
        name="DP$REST", number=0x12,
        description="Restore saved screen",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Restores screen saved by DP$SAVE.",
    ),
    SystemCall(
        name="DP$SAVE", number=0x13,
        description="Save screen state",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Saves screen contents and cursor position.",
    ),
    SystemCall(
        name="DP$STAT", number=0x14,
        description="Set cursor position and state",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(
            Parameter("A", "cursor position"),
            Parameter("B", "cursor state flags"),
        ),
        outputs=(),
        notes="Position: 0-31 (2-line) or 0-79 (4-line).",
    ),
    SystemCall(
        name="DP$VIEW", number=0x15,
        description="Display scrolling string",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(
            Parameter("X", "string address"),
            Parameter("A", "display line"),
            Parameter("B", "string length"),
            Parameter("UTW_S0", "initial pause (50ms units)"),
        ),
        outputs=(Parameter("B", "exit key code"),),
        notes="String scrolls horizontally until key pressed.",
    ),
    SystemCall(
        name="DP$WRDY", number=0x16,
        description="Wait for display ready",
        category=CallCategory.DISPLAY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Waits until LCD controller is ready.",
    ),
    SystemCall(
        name="DP$MSET", number=0x82,
        description="Set display mode (2/4 lines)",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("A", "mode (0=2-line, 1=4-line)"),),
        outputs=(Parameter("A", "previous mode"),),
        notes="LZ only.",
    ),
    SystemCall(
        name="DP$CSET", number=0x83,
        description="Set UDG clock status",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("B", "position/flags"),),
        outputs=(Parameter("B", "previous status"),),
        notes="LZ only. Manages clock display in status line.",
    ),
    SystemCall(
        name="DP$CPRN", number=0x84,
        description="Update clock UDG patterns",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("A", "update mode"),),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="DP$UDG", number=0x85,
        description="Read/write UDG patterns",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "operation flags"),
            Parameter("B", "UDG character number"),
            Parameter("X", "pattern buffer address"),
        ),
        outputs=(Parameter("X", "next byte address"),),
        notes="LZ only. User-Defined Graphics.",
    ),
    SystemCall(
        name="DP$PVEW", number=0xA3,
        description="Scroll text at cursor position",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("X", "string address"),
            Parameter("A", "flags"),
            Parameter("B", "string length"),
        ),
        outputs=(Parameter("B", "exit key code"),),
        notes="LZ only. Partial-line scrolling.",
    ),

    # =========================================================================
    # Device Services (DV$xxx)
    # =========================================================================

    SystemCall(
        name="DV$BOOT", number=0x17,
        description="Boot connected devices",
        category=CallCategory.DEVICE, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Initializes all devices during startup.",
    ),
    SystemCall(
        name="DV$CLER", number=0x18,
        description="Clear device code",
        category=CallCategory.DEVICE, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Deactivates booted device code.",
    ),
    SystemCall(
        name="DV$LKUP", number=0x19,
        description="Look up device vector",
        category=CallCategory.DEVICE, models=ALL_MODELS,
        inputs=(Parameter("X", "procedure name (LBC string)"),),
        outputs=(
            Parameter("A", "device number"),
            Parameter("B", "vector number"),
        ),
        notes="Finds device handler for named procedure.",
    ),
    SystemCall(
        name="DV$LOAD", number=0x1A,
        description="Load relocatable code",
        category=CallCategory.DEVICE, models=ALL_MODELS,
        inputs=(
            Parameter("X", "pack address"),
            Parameter("D", "load address"),
            Parameter("UTW_S0", "fixup address"),
        ),
        outputs=(),
    ),
    SystemCall(
        name="DV$VECT", number=0x1B,
        description="Call device vector",
        category=CallCategory.DEVICE, models=ALL_MODELS,
        inputs=(
            Parameter("A", "device number"),
            Parameter("B", "vector number"),
            Parameter("X", "parameters"),
        ),
        outputs=(),
        notes="Returns depend on specific device/vector.",
    ),

    # =========================================================================
    # Editor Services (ED$xxx)
    # =========================================================================

    SystemCall(
        name="ED$EDIT", number=0x1C,
        description="Line editor (cursor at start)",
        category=CallCategory.EDITOR, models=ALL_MODELS,
        inputs=(
            Parameter("A", "flags"),
            Parameter("B", "maximum length"),
        ),
        outputs=(
            Parameter("B", "exit key"),
            Parameter("RTT_BF", "edited text"),
        ),
        notes="Text in RTT_BF buffer.",
    ),
    SystemCall(
        name="ED$EPOS", number=0x1D,
        description="Line editor with position",
        category=CallCategory.EDITOR, models=ALL_MODELS,
        inputs=(
            Parameter("A", "flags"),
            Parameter("B", "maximum length"),
            Parameter("UTW_S0", "cursor position"),
        ),
        outputs=(
            Parameter("B", "exit key"),
            Parameter("RTT_BF", "edited text"),
        ),
    ),
    SystemCall(
        name="ED$VIEW", number=0x1E,
        description="View/scroll display string",
        category=CallCategory.EDITOR, models=ALL_MODELS,
        inputs=(
            Parameter("X", "first call: string address; then: 0"),
            Parameter("UTW_S0", "pause ticks"),
        ),
        outputs=(Parameter("B", "exit key"),),
        notes="RTT_BF contains display text.",
    ),

    # =========================================================================
    # Error Services (ER$xxx)
    # =========================================================================

    SystemCall(
        name="ER$LKUP", number=0x1F,
        description="Look up error message",
        category=CallCategory.ERROR, models=ALL_MODELS,
        inputs=(Parameter("B", "error code"),),
        outputs=(Parameter("X", "LBC error string"),),
    ),
    SystemCall(
        name="ER$MESS", number=0x20,
        description="Display error message",
        category=CallCategory.ERROR, models=ALL_MODELS,
        inputs=(Parameter("B", "error code"),),
        outputs=(),
        notes="Displays message and waits for keypress.",
    ),
    SystemCall(
        name="ER$PRNT", number=0xA9,
        description="Display error string",
        category=CallCategory.ERROR, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("X", "message string address"),),
        outputs=(),
        notes="LZ only. Custom error message.",
    ),

    # =========================================================================
    # File Services (FL$xxx)
    # =========================================================================

    SystemCall(
        name="FL$BACK", number=0x21,
        description="Move to previous record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("X", "new record number"),),
    ),
    SystemCall(
        name="FL$BCAT", number=0x22,
        description="Catalog block files",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("A", "1=first, 0=next"),
            Parameter("B", "pack number"),
            Parameter("X", "result address"),
            Parameter("UTW_S0", "file type filter"),
        ),
        outputs=(),
        notes="Returns file info in result buffer.",
    ),
    SystemCall(
        name="FL$BDEL", number=0x23,
        description="Delete block file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("X", "filename (LBC)"),
            Parameter("B", "file type ($82-$8F)"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$BOPN", number=0x24,
        description="Open block file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("X", "filename (LBC)"),
            Parameter("B", "file type ($82-$8F)"),
        ),
        outputs=(
            Parameter("D", "data block length"),
            Parameter("C", "error flag"),
        ),
    ),
    SystemCall(
        name="FL$BSAV", number=0x25,
        description="Save block file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("X", "filename (LBC)"),
            Parameter("B", "file type"),
            Parameter("UTW_S0", "data length"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$CATL", number=0x26,
        description="Catalog ordinary files",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("A", "1=first, 0=next"),
            Parameter("B", "pack number"),
            Parameter("X", "result address"),
        ),
        outputs=(Parameter("C", "error/end flag"),),
    ),
    SystemCall(
        name="FL$COPY", number=0x27,
        description="Copy file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("D", "source filename"),
            Parameter("X", "target filename"),
            Parameter("UTW_S0", "type/flags"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$CRET", number=0x28,
        description="Create ordinary file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("X", "filename (LBC)"),),
        outputs=(
            Parameter("A", "record type"),
            Parameter("C", "error flag"),
        ),
    ),
    SystemCall(
        name="FL$DELN", number=0x29,
        description="Delete ordinary file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("X", "filename (LBC)"),),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$ERAS", number=0x2A,
        description="Erase current record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$FFND", number=0x2B,
        description="Find record with string",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("A", "search string length"),
            Parameter("B", "record type"),
            Parameter("X", "search string address"),
        ),
        outputs=(
            Parameter("RTB_BL", "found record"),
            Parameter("C", "not found flag"),
        ),
    ),
    SystemCall(
        name="FL$FIND", number=0x2C,
        description="Find next matching record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("D", "search string address"),
            Parameter("X", "result address"),
        ),
        outputs=(
            Parameter("A", "record type"),
            Parameter("C", "not found flag"),
        ),
    ),
    SystemCall(
        name="FL$FREC", number=0x2D,
        description="Get record information",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("D", "record number"),),
        outputs=(
            Parameter("A", "record length"),
            Parameter("B", "record type"),
            Parameter("X", "pack address low"),
            Parameter("UTW_S0", "pack address high"),
        ),
    ),
    SystemCall(
        name="FL$NEXT", number=0x2E,
        description="Move to next record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("C", "end of file flag"),),
    ),
    SystemCall(
        name="FL$OPEN", number=0x2F,
        description="Open existing file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("X", "filename (LBC)"),),
        outputs=(
            Parameter("A", "record type"),
            Parameter("C", "error flag"),
        ),
    ),
    SystemCall(
        name="FL$PARS", number=0x30,
        description="Parse filename",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("X", "filename"),
            Parameter("D", "result address"),
            Parameter("UTW_S0h", "default device"),
        ),
        outputs=(Parameter("C", "error flag"),),
        notes="Validates and parses device:filename format.",
    ),
    SystemCall(
        name="FL$READ", number=0x31,
        description="Read current record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("X", "buffer address"),),
        outputs=(
            Parameter("B", "record type"),
            Parameter("C", "error flag"),
        ),
    ),
    SystemCall(
        name="FL$RECT", number=0x32,
        description="Set record type filter",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("B", "record type ($81-$FE)"),),
        outputs=(),
        notes="Filters which records are seen by FL$NEXT/FL$READ.",
    ),
    SystemCall(
        name="FL$RENM", number=0x33,
        description="Rename file",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(
            Parameter("D", "new name (LBC)"),
            Parameter("X", "old name (LBC)"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$RSET", number=0x34,
        description="Set file position",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("D", "record number"),),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$SETP", number=0x35,
        description="Select pack device",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("B", "pack number (0=A:, 1=B:, 2=C:)"),),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="FL$SIZE", number=0x36,
        description="Get pack space information",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(),
        outputs=(
            Parameter("X", "record count"),
            Parameter("D/UTW_S1h", "free space"),
            Parameter("UTW_S1l/UTW_S0", "pack address"),
        ),
    ),
    SystemCall(
        name="FL$WRIT", number=0x37,
        description="Write/append record",
        category=CallCategory.FILE, models=ALL_MODELS,
        inputs=(Parameter("X", "data (LBC, max 254 bytes)"),),
        outputs=(Parameter("C", "error flag"),),
    ),

    # LZ extended file services
    SystemCall(
        name="FL$WCAT", number=0x90,
        description="Wildcard file catalog",
        category=CallCategory.FILE, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "flags"),
            Parameter("B", "pack"),
            Parameter("X", "result address"),
        ),
        outputs=(
            Parameter("A", "file type"),
            Parameter("UTW_S0", "size/records"),
        ),
        notes="LZ only. Supports wildcards in filename.",
    ),
    SystemCall(
        name="FL$WCPY", number=0x91,
        description="Wildcard file copy",
        category=CallCategory.FILE, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("D", "source pattern"),
            Parameter("X", "target pattern"),
            Parameter("UTW_S0", "callback routine"),
        ),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="FL$WDEL", number=0x92,
        description="Wildcard file delete",
        category=CallCategory.FILE, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("X", "wildcard pattern"),
            Parameter("UTW_S0", "callback routine"),
        ),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="FL$WFND", number=0x93,
        description="Wildcard record find",
        category=CallCategory.FILE, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("D", "search pattern"),
            Parameter("X", "result address"),
        ),
        outputs=(Parameter("A", "record type"),),
        notes="LZ only.",
    ),
    SystemCall(
        name="FL$FDEL", number=0xB0,
        description="Delete record range",
        category=CallCategory.FILE, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("D", "start record"),
            Parameter("X", "count"),
        ),
        outputs=(),
        notes="LZ only.",
    ),

    # =========================================================================
    # Floating Point Services (FN$xxx)
    # =========================================================================
    # These operate on the runtime floating-point stack.

    SystemCall(
        name="FN$ATAN", number=0x38,
        description="Arctangent",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Replaces stack top with its arctangent.",
        errors=("253: domain error",),
    ),
    SystemCall(
        name="FN$COS", number=0x39,
        description="Cosine",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Replaces stack top with its cosine.",
        errors=("247: overflow",),
    ),
    SystemCall(
        name="FN$EXP", number=0x3A,
        description="Exponential (e^x)",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Replaces stack top with e raised to that power.",
        errors=("247: overflow",),
    ),
    SystemCall(
        name="FN$LN", number=0x3B,
        description="Natural logarithm",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Replaces stack top with its natural log.",
        errors=("247: domain error",),
    ),
    SystemCall(
        name="FN$LOG", number=0x3C,
        description="Base-10 logarithm",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Replaces stack top with its log base 10.",
        errors=("247: domain error",),
    ),
    SystemCall(
        name="FN$POWR", number=0x3D,
        description="Power (x^y)",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Computes x^y from top two stack values.",
        errors=("247: overflow",),
    ),
    SystemCall(
        name="FN$RND", number=0x3E,
        description="Random number (0-1)",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Pushes random value between 0 and 1.",
    ),
    SystemCall(
        name="FN$SIN", number=0x3F,
        description="Sine",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        errors=("247: overflow",),
    ),
    SystemCall(
        name="FN$SQRT", number=0x40,
        description="Square root",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        errors=("247: domain error (negative input)",),
    ),
    SystemCall(
        name="FN$TAN", number=0x41,
        description="Tangent",
        category=CallCategory.FLOAT, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        errors=("247: overflow",),
    ),
    SystemCall(
        name="FN$ASIN", number=0xAC,
        description="Arcsine",
        category=CallCategory.FLOAT, models=EXTENDED_SERVICE_MODELS,
        inputs=(),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="FN$ACOS", number=0xAD,
        description="Arccosine",
        category=CallCategory.FLOAT, models=EXTENDED_SERVICE_MODELS,
        inputs=(),
        outputs=(),
        notes="LZ only.",
    ),

    # =========================================================================
    # Table Interpreter Services (IT$xxx)
    # =========================================================================

    SystemCall(
        name="IT$GVAL", number=0x42,
        description="Get byte parameter from table",
        category=CallCategory.INTERPRETER, models=ALL_MODELS,
        inputs=(Parameter("B", "offset to parameter"),),
        outputs=(Parameter("B", "parameter value"),),
    ),
    SystemCall(
        name="IT$RADD", number=0x43,
        description="Get variable address",
        category=CallCategory.INTERPRETER, models=ALL_MODELS,
        inputs=(Parameter("B", "offset to parameter"),),
        outputs=(Parameter("X", "address of variable"),),
    ),
    SystemCall(
        name="IT$STRT", number=0x44,
        description="Start table interpreter",
        category=CallCategory.INTERPRETER, models=ALL_MODELS,
        inputs=(Parameter("D", "table program address"),),
        outputs=(Parameter("B", "error code or 0"),),
        notes="Executes table-driven program.",
    ),
    SystemCall(
        name="IT$TADD", number=0x45,
        description="Get word parameter from table",
        category=CallCategory.INTERPRETER, models=ALL_MODELS,
        inputs=(Parameter("B", "offset to parameter"),),
        outputs=(Parameter("D", "parameter value"),),
    ),

    # =========================================================================
    # Keyboard Services (KB$xxx)
    # =========================================================================

    SystemCall(
        name="KB$BREK", number=0x46,
        description="Test for ON/CLEAR break",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("C", "1 if ON/CLEAR pressed"),),
        notes="Also flushes keyboard buffer if pressed.",
    ),
    SystemCall(
        name="KB$FLSH", number=0x47,
        description="Flush keyboard buffer",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Clears all pending keypresses.",
    ),
    SystemCall(
        name="KB$GETK", number=0x48,
        description="Wait for keypress",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("B", "key code"),),
        notes="Blocks until key pressed. Uses SLP for power saving.",
    ),
    SystemCall(
        name="KB$INIT", number=0x49,
        description="Initialize keyboard",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Called during cold boot. Sets up interrupts.",
    ),
    SystemCall(
        name="KB$STAT", number=0x4A,
        description="Set keyboard status",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(Parameter("B", "new status flags"),),
        outputs=(),
        notes="Sets CAPS, NUM, SHIFT state.",
    ),
    SystemCall(
        name="KB$TEST", number=0x4B,
        description="Test for key available",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(),
        outputs=(
            Parameter("B", "key code (0 if none)"),
            Parameter("Z", "set if no key"),
        ),
        notes="Non-blocking key check.",
    ),
    SystemCall(
        name="KB$UGET", number=0x4C,
        description="Unget key (push back)",
        category=CallCategory.KEYBOARD, models=ALL_MODELS,
        inputs=(Parameter("B", "key to unget"),),
        outputs=(),
        notes="Key will be returned by next KB$GETK/KB$TEST.",
    ),
    SystemCall(
        name="KB$CONK", number=0xB1,
        description="Get key with cursor control",
        category=CallCategory.KEYBOARD, models=EXTENDED_SERVICE_MODELS,
        inputs=(),
        outputs=(Parameter("B", "ASCII value"),),
        notes="LZ only. Handles cursor keys.",
    ),

    # =========================================================================
    # Language Services (LG$xxx, LN$xxx)
    # =========================================================================

    SystemCall(
        name="LG$NEWP", number=0x4D,
        description="Create new OPL text block",
        category=CallCategory.LANGUAGE, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="LG$RLED", number=0x4E,
        description="Run/List/Edit/Delete program",
        category=CallCategory.LANGUAGE, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="File name in RTT_FF; type in LGB_LANT.",
    ),
    SystemCall(
        name="LN$STRT", number=0x4F,
        description="Start OPL translator",
        category=CallCategory.LANGUAGE, models=ALL_MODELS,
        inputs=(Parameter("B", "function (0-3)"),),
        outputs=(Parameter("B", "error code"),),
        notes="0=translate proc, 1=translate calc, 2-3=locate error.",
    ),

    # =========================================================================
    # Menu Services (MN$xxx)
    # =========================================================================

    SystemCall(
        name="MN$DISP", number=0x50,
        description="Display menu",
        category=CallCategory.MENU, models=ALL_MODELS,
        inputs=(
            Parameter("X", "menu string address"),
            Parameter("D", "exit key bit mask"),
        ),
        outputs=(
            Parameter("B", "exit key pressed"),
            Parameter("UTW_S0", "chosen item number"),
        ),
        notes="Menu string is comma-separated items.",
    ),
    SystemCall(
        name="MN$XDSP", number=0x86,
        description="Menu below cursor line",
        category=CallCategory.MENU, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("X", "menu string"),
            Parameter("D", "exit key mask"),
        ),
        outputs=(
            Parameter("B", "exit key"),
            Parameter("A/X/UTW_S0", "selection data"),
        ),
        notes="LZ only.",
    ),
    SystemCall(
        name="MN$1DSP", number=0x87,
        description="Single-line menu",
        category=CallCategory.MENU, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("X", "menu string"),
            Parameter("D", "exit key mask"),
        ),
        outputs=(
            Parameter("B", "exit key"),
            Parameter("A/X/UTW_S0", "selection data"),
        ),
        notes="LZ only.",
    ),
    SystemCall(
        name="MN$TITL", number=0x88,
        description="Menu with header",
        category=CallCategory.MENU, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("X", "menu string"),
            Parameter("D", "exit key mask"),
        ),
        outputs=(
            Parameter("B", "exit key"),
        ),
        notes="LZ only. Displays icon/clock in header.",
    ),

    # =========================================================================
    # Math Conversion Services (MT$xxx)
    # =========================================================================

    SystemCall(
        name="MT$BTOF", number=0x51,
        description="String to float",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Converts ASCII string to floating point.",
    ),
    SystemCall(
        name="MT$FADD", number=0x52,
        description="Add floats (Acc + Oper)",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FBDC", number=0x53,
        description="Float to decimal string",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FBEX", number=0x54,
        description="Float to exponential string",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FBGN", number=0x55,
        description="Float to general format string",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FBIN", number=0x56,
        description="Float to integer string",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FDIV", number=0x57,
        description="Divide floats (Oper / Acc)",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FMUL", number=0x58,
        description="Multiply floats",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FNGT", number=0x59,
        description="Negate float",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="MT$FSUB", number=0x5A,
        description="Subtract floats (Acc - Oper)",
        category=CallCategory.MATH, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),

    # =========================================================================
    # Pack Services (PK$xxx)
    # =========================================================================

    SystemCall(
        name="PK$PKOF", number=0x5B,
        description="Turn off packs",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Powers down all pack slots.",
    ),
    SystemCall(
        name="PK$QADD", number=0x5C,
        description="Query pack address",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(),
        outputs=(
            Parameter("B", "high byte"),
            Parameter("X", "low bytes"),
        ),
    ),
    SystemCall(
        name="PK$RBYT", number=0x5D,
        description="Read byte from pack",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("B", "byte read"),),
        notes="Advances pack address.",
    ),
    SystemCall(
        name="PK$READ", number=0x5E,
        description="Read bytes from pack",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(
            Parameter("D", "byte count"),
            Parameter("X", "target address"),
        ),
        outputs=(),
    ),
    SystemCall(
        name="PK$RWRD", number=0x5F,
        description="Read word from pack",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(),
        outputs=(Parameter("D", "word read"),),
    ),
    SystemCall(
        name="PK$SADD", number=0x60,
        description="Set pack address",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="May power up packs.",
    ),
    SystemCall(
        name="PK$SAVE", number=0x61,
        description="Write bytes to pack",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(
            Parameter("D", "byte count"),
            Parameter("X", "source address"),
        ),
        outputs=(),
        notes="For RAM packs only.",
    ),
    SystemCall(
        name="PK$SETP", number=0x62,
        description="Select pack slot",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(
            Parameter("A", "error flag behavior"),
            Parameter("B", "pack number (0-3)"),
        ),
        outputs=(Parameter("C", "error flag"),),
    ),
    SystemCall(
        name="PK$SKIP", number=0x63,
        description="Skip bytes in pack",
        category=CallCategory.PACK, models=ALL_MODELS,
        inputs=(Parameter("D", "bytes to skip (0-$7FFF)"),),
        outputs=(),
    ),

    # =========================================================================
    # Runtime Services (RM$xxx)
    # =========================================================================

    SystemCall(
        name="RM$RUNP", number=0x64,
        description="Run OPL program",
        category=CallCategory.RUNTIME, models=ALL_MODELS,
        inputs=(Parameter("B", "0=procedure, non-zero=calculator"),),
        outputs=(),
        notes="Loads and executes OPL procedure.",
    ),

    # =========================================================================
    # Top-Level Menu Services (TL$xxx)
    # =========================================================================

    SystemCall(
        name="TL$ADDI", number=0x65,
        description="Add menu item",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Inserts item into top-level menu.",
    ),
    SystemCall(
        name="TL$CPYX", number=0x66,
        description="Copy file operation",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="FROM/TO file prompts.",
    ),
    SystemCall(
        name="TL$DELI", number=0x67,
        description="Delete menu item",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="TL$XXMD", number=0x68,
        description="Filename editor",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="MODE key selects pack.",
    ),
    SystemCall(
        name="TL$RSTR", number=0x7F,
        description="Restore menu",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="ROM 2.7+. Restores initial menu state.",
    ),
    SystemCall(
        name="TL$LSET", number=0x80,
        description="Set language",
        category=CallCategory.TOPLEVEL, models=ALL_MODELS,
        inputs=(Parameter("B", "language code (0-10)"),),
        outputs=(),
        notes="Multi-lingual machines only.",
    ),
    SystemCall(
        name="TL$ZZMD", number=0x9B,
        description="Multi-line editor",
        category=CallCategory.TOPLEVEL, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "flags"),
            Parameter("B", "max length"),
            Parameter("X", "prompt address"),
        ),
        outputs=(
            Parameter("TLB_CPAK", "pack"),
            Parameter("C", "exit mode"),
        ),
        notes="LZ only. No screen clear.",
    ),

    # =========================================================================
    # Time Services (TM$xxx)
    # =========================================================================

    SystemCall(
        name="TM$DAYV", number=0x69,
        description="Get day of week",
        category=CallCategory.TIME, models=ALL_MODELS,
        inputs=(Parameter("X", "3-byte date address"),),
        outputs=(
            Parameter("B", "weekday (0-6, 0=Sunday)"),
            Parameter("X", "3-char day name"),
        ),
    ),
    SystemCall(
        name="TM$TGET", number=0x6A,
        description="Get system time",
        category=CallCategory.TIME, models=ALL_MODELS,
        inputs=(Parameter("X", "6-byte buffer address"),),
        outputs=(),
        notes="Buffer: year, month, day, hour, minute, second.",
    ),
    SystemCall(
        name="TM$UPDT", number=0x6B,
        description="Add time offset",
        category=CallCategory.TIME, models=ALL_MODELS,
        inputs=(
            Parameter("A", "minutes to add"),
            Parameter("B", "seconds to add"),
            Parameter("X", "date/time buffer"),
        ),
        outputs=(),
    ),
    SystemCall(
        name="TM$WAIT", number=0x6C,
        description="Wait for ticks",
        category=CallCategory.TIME, models=ALL_MODELS,
        inputs=(Parameter("D", "ticks (1 tick = ~50ms)"),),
        outputs=(),
        notes="Uses keyboard interrupt timing.",
    ),
    SystemCall(
        name="TM$TSET", number=0xB3,
        description="Set system time",
        category=CallCategory.TIME, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("X", "6-byte time/date buffer"),),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="TM$DNAM", number=0x97,
        description="Day number to name",
        category=CallCategory.TIME, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("B", "day (0-6)"),),
        outputs=(Parameter("X", "3-char day name"),),
        notes="LZ only.",
    ),
    SystemCall(
        name="TM$MNAM", number=0xAA,
        description="Month number to name",
        category=CallCategory.TIME, models=EXTENDED_SERVICE_MODELS,
        inputs=(Parameter("B", "month (0-11)"),),
        outputs=(Parameter("X", "3-char month name"),),
        notes="LZ only.",
    ),

    # =========================================================================
    # Utility Services (UT$xxx)
    # =========================================================================

    SystemCall(
        name="UT$CPYB", number=0x6D,
        description="Copy memory block",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(
            Parameter("X", "source address"),
            Parameter("UTW_S0", "destination address"),
            Parameter("D", "byte count"),
        ),
        outputs=(),
        notes="Handles overlapping regions correctly.",
    ),
    SystemCall(
        name="UT$DDSP", number=0x6E,
        description="Format display output",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(Parameter("D", "format string address"),),
        outputs=(),
        notes="Printf-like formatted output.",
    ),
    SystemCall(
        name="UT$DISP", number=0x6F,
        description="Inline display string",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Format string follows SWI instruction.",
    ),
    SystemCall(
        name="UT$ENTR", number=0x70,
        description="Call with error handling",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(
            Parameter("X", "routine address"),
            Parameter("D/UTW_S1-5", "parameters"),
        ),
        outputs=(),
        notes="Use UT$LEAV to return with error code.",
    ),
    SystemCall(
        name="UT$FILL", number=0x71,
        description="Fill memory",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(
            Parameter("A", "fill value"),
            Parameter("B", "byte count"),
            Parameter("X", "start address"),
        ),
        outputs=(),
    ),
    SystemCall(
        name="UT$ICPB", number=0x72,
        description="Case-insensitive compare",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Compares two ASCII strings.",
    ),
    SystemCall(
        name="UT$ISBF", number=0x73,
        description="Find substring",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$LEAV", number=0x74,
        description="Exit with error code",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(Parameter("B", "error code"),),
        outputs=(),
        notes="Used with UT$ENTR.",
    ),
    SystemCall(
        name="UT$SDIV", number=0x75,
        description="Signed 16-bit divide",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$SMUL", number=0x76,
        description="Signed 16-bit multiply",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$SPLT", number=0x77,
        description="Split string on separator",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$UDIV", number=0x78,
        description="Unsigned 16-bit divide",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$UMUL", number=0x79,
        description="Unsigned 16-bit multiply",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$UTOB", number=0x7A,
        description="Unsigned to decimal string",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$XCAT", number=0x7B,
        description="Display files by type",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$XTOB", number=0x7C,
        description="Unsigned to hex string",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
    ),
    SystemCall(
        name="UT$YSNO", number=0x7D,
        description="Yes/No prompt",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="Waits for Y, N, or ON/CLEAR.",
    ),
    SystemCall(
        name="UT$CDSP", number=0x7E,
        description="Clear and display",
        category=CallCategory.UTILITY, models=ALL_MODELS,
        inputs=(),
        outputs=(),
        notes="ROM 2.5+. Clears screen then displays inline string.",
    ),
    SystemCall(
        name="UT$CMPB", number=0xB2,
        description="Case-sensitive compare",
        category=CallCategory.UTILITY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "length 1"),
            Parameter("B", "length 2"),
            Parameter("X", "string 1 address"),
            Parameter("UTW_S0", "string 2 address"),
        ),
        outputs=(Parameter("B", "comparison result"),),
        notes="LZ only.",
    ),
    SystemCall(
        name="UT$SORT", number=0xA5,
        description="Quicksort",
        category=CallCategory.UTILITY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("D", "item count"),
            Parameter("X", "user compare routine"),
        ),
        outputs=(),
        notes="LZ only.",
    ),
    SystemCall(
        name="UT$WILD", number=0x94,
        description="Wildcard match",
        category=CallCategory.UTILITY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "pattern length"),
            Parameter("B", "string length"),
            Parameter("X", "pattern address"),
            Parameter("UTW_S0", "string address"),
        ),
        outputs=(Parameter("B", "match offset"),),
        notes="LZ only. Supports * and ? wildcards.",
    ),

    # =========================================================================
    # Bar Graph Service
    # =========================================================================

    SystemCall(
        name="XT$BAR", number=0xA2,
        description="Create bar graph",
        category=CallCategory.DISPLAY, models=EXTENDED_SERVICE_MODELS,
        inputs=(
            Parameter("A", "black percentage"),
            Parameter("B", "grey percentage"),
        ),
        outputs=(Parameter("RTT_BF", "20-char bar string"),),
        notes="LZ only. Creates UDG bar characters.",
    ),
)


# =============================================================================
# System Call Lookup Functions
# =============================================================================

# Build lookup dictionaries for efficient access
_CALLS_BY_NAME: dict[str, SystemCall] = {
    call.name: call for call in SYSTEM_CALLS
}

_CALLS_BY_NUMBER: dict[int, SystemCall] = {
    call.number: call for call in SYSTEM_CALLS
}


def get_syscall(name: str) -> Optional[SystemCall]:
    """
    Look up a system call by name.

    Args:
        name: Call name (e.g., "DP$EMIT"), case-insensitive

    Returns:
        SystemCall if found, None otherwise

    Example:
        >>> call = get_syscall("DP$EMIT")
        >>> call.number
        16
    """
    return _CALLS_BY_NAME.get(name.upper())


def get_syscall_by_number(number: int) -> Optional[SystemCall]:
    """
    Look up a system call by service number.

    Args:
        number: Service number (0x00-0xFF)

    Returns:
        SystemCall if found, None otherwise

    Example:
        >>> call = get_syscall_by_number(0x10)
        >>> call.name
        'DP$EMIT'
    """
    return _CALLS_BY_NUMBER.get(number)


def get_syscalls_for_model(model: PsionModel) -> list[SystemCall]:
    """
    Get all system calls supported on a specific model.

    Args:
        model: Target Psion model

    Returns:
        List of SystemCalls supported on that model, sorted by number
    """
    return sorted(
        [call for call in SYSTEM_CALLS if call.is_supported_on(model)],
        key=lambda c: c.number
    )


def get_syscalls_by_category(category: CallCategory) -> list[SystemCall]:
    """
    Get all system calls in a specific category.

    Args:
        category: Call category

    Returns:
        List of SystemCalls in that category, sorted by number
    """
    return sorted(
        [call for call in SYSTEM_CALLS if call.category == category],
        key=lambda c: c.number
    )


def get_all_syscall_names() -> list[str]:
    """
    Get a sorted list of all system call names.

    Returns:
        List of call names in alphabetical order
    """
    return sorted(_CALLS_BY_NAME.keys())


# =============================================================================
# Include File Generation
# =============================================================================

def generate_syscalls_inc(
    model: Optional[str] = None,
    categories: Optional[list[CallCategory]] = None,
    include_usage: bool = False,
) -> str:
    """
    Generate assembly include file with system call definitions.

    Args:
        model: Target model name ("CM", "XP", "LZ", etc.) or None for all
        categories: List of categories to include, or None for all
        include_usage: If True, include usage examples as comments

    Returns:
        Assembly include file content as a string

    Example:
        >>> content = generate_syscalls_inc(model="LZ")
        >>> print(content[:100])
        ; =============================================================================
        ; SYSCALLS.INC - Psion Organiser II System Calls
    """
    lines = [
        "; =============================================================================",
        "; SYSCALLS.INC - Psion Organiser II System Calls",
        "; =============================================================================",
        "; Generated by psion-sdk",
    ]

    if model:
        lines.append(f"; Target model: {model}")
    else:
        lines.append("; Target model: ALL")

    lines.extend([
        ";",
        "; Usage:",
        ";     LDAA    #service    ; Load service number",
        ";     [setup parameters]  ; Set up B, X, UTW_S0-S5",
        ";     SWI                 ; Execute system call",
        ";",
        "; =============================================================================",
        "",
    ])

    # Determine target model
    target_model = None
    if model:
        from psion_sdk.sdk.models import get_model_by_name
        target_model = get_model_by_name(model)

    # Category display names
    category_names = {
        CallCategory.ALLOCATOR: "Memory Allocation (AL$xxx)",
        CallCategory.BATTERY: "Power/NMI Control (BT$xxx)",
        CallCategory.BUZZER: "Sound Output (BZ$xxx)",
        CallCategory.DISPLAY: "Display Control (DP$xxx)",
        CallCategory.DEVICE: "Device Management (DV$xxx)",
        CallCategory.EDITOR: "Line Editing (ED$xxx)",
        CallCategory.ERROR: "Error Handling (ER$xxx)",
        CallCategory.FILE: "File System (FL$xxx)",
        CallCategory.FLOAT: "Floating Point (FN$xxx)",
        CallCategory.INTERPRETER: "Table Interpreter (IT$xxx)",
        CallCategory.KEYBOARD: "Keyboard Input (KB$xxx)",
        CallCategory.LANGUAGE: "OPL Language (LG$xxx, LN$xxx)",
        CallCategory.MENU: "Menu Display (MN$xxx)",
        CallCategory.MATH: "Math Conversions (MT$xxx)",
        CallCategory.PACK: "Pack Access (PK$xxx)",
        CallCategory.RUNTIME: "Program Execution (RM$xxx)",
        CallCategory.TOPLEVEL: "Top-Level Menu (TL$xxx)",
        CallCategory.TIME: "Real-Time Clock (TM$xxx)",
        CallCategory.UTILITY: "General Utilities (UT$xxx)",
        CallCategory.EXTENDED: "Extended Services (LZ)",
    }

    categories_to_include = categories or list(CallCategory)

    for category in categories_to_include:
        calls_in_category = [
            call for call in SYSTEM_CALLS
            if call.category == category and
            (target_model is None or call.is_supported_on(target_model))
        ]

        if not calls_in_category:
            continue

        # Sort by service number
        calls_in_category.sort(key=lambda c: c.number)

        category_name = category_names.get(category, category.name)
        lines.extend([
            f"; -----------------------------------------------------------------------------",
            f"; {category_name}",
            f"; -----------------------------------------------------------------------------",
            "",
        ])

        for call in calls_in_category:
            line = call.format_asm_equ()
            if call.notes:
                # Truncate long notes
                note = call.notes[:40] + "..." if len(call.notes) > 40 else call.notes
                if "only" in note.lower():
                    # Highlight model-specific notes
                    line += f"  ({note})"
            lines.append(line)

            if include_usage:
                lines.append(f";   Usage: {call.format_usage_example()}")

        lines.append("")

    # Add SYSCALL macro
    lines.extend([
        "; =============================================================================",
        "; SYSCALL Macro",
        "; =============================================================================",
        "; Convenience macro for invoking system calls.",
        ";",
        "; Usage: SYSCALL DP$EMIT",
        "; Expands to: LDAA #DP$EMIT",
        ";             SWI",
        "; =============================================================================",
        "",
        "MACRO SYSCALL, service",
        "    LDAA    #\\service",
        "    SWI",
        "ENDM",
        "",
        "; =============================================================================",
        "; End of syscalls.inc",
        "; =============================================================================",
    ])

    return "\n".join(lines)
