"""
Psion Organiser II System Variable Definitions
===============================================

This module provides comprehensive definitions of all system variables
used by the Psion Organiser II operating system. These variables are
located in:

- HD6303 internal registers ($00-$3F)
- Zero page RAM ($40-$FF) - fast single-byte addressing
- Semi-custom chip I/O ($100-$3FF)
- Main system RAM ($2000+)
- High RAM (LZ only, $7F00+)
- ROM constants ($FF00+)

Usage
-----
Access system variable definitions:
    >>> from psion_sdk.sdk.sysvars import SYSTEM_VARIABLES, get_variable
    >>> var = get_variable("UTW_S0")
    >>> var.address
    65  # $41
    >>> var.size
    2

Generate assembly include definitions:
    >>> from psion_sdk.sdk.sysvars import generate_sysvars_inc
    >>> content = generate_sysvars_inc(model="LZ")
    >>> print(content)
    ; System variable definitions for LZ
    UTW_S0       EQU $0041  ; Scratch register 0
    ...

Reference
---------
- System variables: https://www.jaapsch.net/psion/sysvars.htm
- Memory map: https://www.jaapsch.net/psion/memmap.htm
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from psion_sdk.sdk.models import (
    PsionModel,
    ALL_MODELS,
    TWO_LINE_MODELS,
    FOUR_LINE_MODELS,
    EXTENDED_SERVICE_MODELS,
)


# =============================================================================
# System Variable Categories
# =============================================================================

class VarCategory(Enum):
    """
    Category of system variable for organization and documentation.

    Variables are grouped by their functional area in the operating system.
    """
    PROCESSOR = auto()      # HD6303 internal registers
    UTILITY = auto()        # General-purpose scratch registers
    BATTERY = auto()        # Power management
    DISPLAY = auto()        # LCD display control
    KEYBOARD = auto()       # Keyboard input handling
    PACK = auto()           # Pack/datapack access
    FILE = auto()           # File system
    TIME = auto()           # Real-time clock
    ALARM = auto()          # Alarm system
    EDITOR = auto()         # Line editor
    MATH = auto()           # Floating-point math
    LANGUAGE = auto()       # OPL interpreter
    MENU = auto()           # Menu system
    COMMS = auto()          # Serial communications
    SYSTEM = auto()         # System/runtime
    HARDWARE = auto()       # Hardware I/O addresses
    ROM = auto()            # ROM constants


# =============================================================================
# System Variable Definition
# =============================================================================

@dataclass(frozen=True)
class SystemVariable:
    """
    Definition of a Psion Organiser II system variable.

    Each system variable has a fixed address in memory with specific
    characteristics documented by Psion.

    Attributes:
        name: Variable name (uppercase with underscore prefix, e.g., "UTW_S0")
        address: Memory address (0x0000-0xFFFF)
        size: Size in bytes (1 for byte, 2 for word, or larger for buffers)
        description: Brief description of the variable's purpose
        category: Functional category for organization
        models: Set of models that support this variable
        read_only: True if variable should not be written by user code
        notes: Additional information or usage notes

    Example:
        >>> var = SystemVariable(
        ...     name="UTW_S0",
        ...     address=0x41,
        ...     size=2,
        ...     description="Scratch register 0",
        ...     category=VarCategory.UTILITY,
        ...     models=ALL_MODELS,
        ... )
    """
    name: str
    address: int
    size: int
    description: str
    category: VarCategory
    models: frozenset[PsionModel]
    read_only: bool = False
    notes: str = ""

    def is_supported_on(self, model: PsionModel) -> bool:
        """Check if this variable is supported on the given model."""
        return model in self.models

    def format_asm_equ(self, width: int = 12) -> str:
        """
        Format as an assembly EQU directive.

        Args:
            width: Minimum width for the name field

        Returns:
            Assembly line like "UTW_S0       EQU $0041  ; Scratch register 0"
        """
        return f"{self.name:<{width}} EQU ${self.address:04X}  ; {self.description}"


# =============================================================================
# Comprehensive System Variable Definitions
# =============================================================================
# These definitions are based on the official Psion technical documentation
# and the comprehensive reference at https://www.jaapsch.net/psion/sysvars.htm
# =============================================================================

SYSTEM_VARIABLES: tuple[SystemVariable, ...] = (
    # =========================================================================
    # HD6303 Internal Registers ($00-$3F)
    # =========================================================================
    # These are hardware registers built into the HD6303 processor itself.
    # They control I/O ports, timers, and serial communication.

    SystemVariable(
        name="P1DDR", address=0x00, size=1,
        description="Port 1 data direction register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="0=input, 1=output for each bit",
    ),
    SystemVariable(
        name="P2DDR", address=0x01, size=1,
        description="Port 2 data direction register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Port 2 is used as data bus to pack slots",
    ),
    SystemVariable(
        name="PORT1", address=0x02, size=1,
        description="Port 1 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PORT2", address=0x03, size=1,
        description="Port 2 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Data bus to slots",
    ),
    SystemVariable(
        name="P3CSR", address=0x04, size=1,
        description="Port 3 control/status register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PORT3", address=0x05, size=1,
        description="Port 3 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="P4DDR", address=0x06, size=1,
        description="Port 4 data direction register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PORT4", address=0x07, size=1,
        description="Port 4 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TCSR1", address=0x08, size=1,
        description="Timer control/status register 1",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Used for OCI interrupts (keyboard scanning)",
    ),
    SystemVariable(
        name="FRCH", address=0x09, size=1,
        description="Free running counter high byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="FRCL", address=0x0A, size=1,
        description="Free running counter low byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="FRC", address=0x09, size=2,
        description="Free running counter (word)",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
        notes="Automatically incremented by timer",
    ),
    SystemVariable(
        name="OCR1H", address=0x0B, size=1,
        description="Output compare register 1 high byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCR1L", address=0x0C, size=1,
        description="Output compare register 1 low byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCR1", address=0x0B, size=2,
        description="Output compare register 1 (word)",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Used for keyboard interrupt timing",
    ),
    SystemVariable(
        name="ICRH", address=0x0D, size=1,
        description="Input capture register high byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="ICRL", address=0x0E, size=1,
        description="Input capture register low byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="TCSR2", address=0x0F, size=1,
        description="Timer control/status register 2",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RMCR", address=0x10, size=1,
        description="Rate and mode control register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Controls serial baud rate",
    ),
    SystemVariable(
        name="TRCSR", address=0x11, size=1,
        description="Transmit/receive control status register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Serial port control",
    ),
    SystemVariable(
        name="RDR", address=0x12, size=1,
        description="Receive data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
        notes="Serial input data",
    ),
    SystemVariable(
        name="TDR", address=0x13, size=1,
        description="Transmit data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Serial output data",
    ),
    SystemVariable(
        name="RAMCR", address=0x14, size=1,
        description="RAM control register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Used for cold/warm boot detection",
    ),
    SystemVariable(
        name="PORT5", address=0x15, size=1,
        description="Port 5 data register (input only)",
        category=VarCategory.PROCESSOR, models=ALL_MODELS, read_only=True,
        notes="Keyboard row inputs and battery status",
    ),
    SystemVariable(
        name="P6DDR", address=0x16, size=1,
        description="Port 6 data direction register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PORT6", address=0x17, size=1,
        description="Port 6 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
        notes="Pack slot selection and timing",
    ),
    SystemVariable(
        name="PORT7", address=0x18, size=1,
        description="Port 7 data register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TCSR3", address=0x1B, size=1,
        description="Timer control/status register 3",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TCONR", address=0x1C, size=1,
        description="Timer constant register",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCR2H", address=0x21, size=1,
        description="Output compare register 2 high byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCR2L", address=0x22, size=1,
        description="Output compare register 2 low byte",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCR2", address=0x21, size=2,
        description="Output compare register 2 (word)",
        category=VarCategory.PROCESSOR, models=ALL_MODELS,
    ),

    # =========================================================================
    # Zero Page Utility Variables ($40-$5F)
    # =========================================================================
    # These are general-purpose scratch registers available for system calls
    # and user programs. S0-S5 are trashed by system calls; R0-R6 are preserved.

    SystemVariable(
        name="UTW_S0", address=0x41, size=2,
        description="Scratch register 0 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls. Used for parameters.",
    ),
    SystemVariable(
        name="UTB_S0", address=0x41, size=1,
        description="Scratch register 0 high byte",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_S1", address=0x43, size=2,
        description="Scratch register 1 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls.",
    ),
    SystemVariable(
        name="UTW_S2", address=0x45, size=2,
        description="Scratch register 2 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls.",
    ),
    SystemVariable(
        name="UTW_S3", address=0x47, size=2,
        description="Scratch register 3 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls.",
    ),
    SystemVariable(
        name="UTW_S4", address=0x49, size=2,
        description="Scratch register 4 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls.",
    ),
    SystemVariable(
        name="UTW_S5", address=0x4B, size=2,
        description="Scratch register 5 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Freely usable. Trashed by system calls.",
    ),
    SystemVariable(
        name="UTW_R0", address=0x4D, size=2,
        description="Preserved register 0 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
        notes="Must be preserved by system calls. Safe across calls.",
    ),
    SystemVariable(
        name="UTW_R1", address=0x4F, size=2,
        description="Preserved register 1 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_R2", address=0x51, size=2,
        description="Preserved register 2 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_R3", address=0x53, size=2,
        description="Preserved register 3 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_R4", address=0x55, size=2,
        description="Preserved register 4 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_R5", address=0x57, size=2,
        description="Preserved register 5 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="UTW_R6", address=0x59, size=2,
        description="Preserved register 6 (word)",
        category=VarCategory.UTILITY, models=ALL_MODELS,
    ),

    # =========================================================================
    # Battery/Power Variables ($5B-$61)
    # =========================================================================

    SystemVariable(
        name="BTB_NMFL", address=0x5B, size=1,
        description="NMI detection flag",
        category=VarCategory.BATTERY, models=ALL_MODELS,
        notes="Cleared when NMI occurs. Check for NMI processing.",
    ),
    SystemVariable(
        name="BTW_CCNT", address=0x5C, size=2,
        description="Countdown to switch-off (seconds)",
        category=VarCategory.BATTERY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="BTA_RTOP", address=0x5E, size=2,
        description="RAM top address",
        category=VarCategory.BATTERY, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="RTB_LBAT", address=0x60, size=1,
        description="Low battery flag",
        category=VarCategory.BATTERY, models=ALL_MODELS, read_only=True,
        notes="Non-zero when batteries are low",
    ),

    # =========================================================================
    # Display Variables ($62-$70)
    # =========================================================================

    SystemVariable(
        name="DPB_CPOS", address=0x62, size=1,
        description="Current cursor position",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="0-31 for 2-line, 0-79 for 4-line displays",
    ),
    SystemVariable(
        name="DPB_CUST", address=0x63, size=1,
        description="Cursor state flags",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Bit 0: cursor on/off. Bit 1: block/line cursor",
    ),
    SystemVariable(
        name="DPB_VLIN", address=0x64, size=1,
        description="Scrolling line position",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Line being scrolled, or current menu item",
    ),
    SystemVariable(
        name="DPB_VSIZ", address=0x65, size=1,
        description="Scrolling text size",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Characters to scroll, or total menu items",
    ),
    SystemVariable(
        name="DPB_VDIR", address=0x66, size=1,
        description="Scroll direction",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="0=paused, 1=right, 2=left",
    ),
    SystemVariable(
        name="DPB_SPOS", address=0x67, size=1,
        description="Saved cursor position",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Saved by DP$SAVE, restored by DP$REST",
    ),
    SystemVariable(
        name="DPB_SCUS", address=0x68, size=1,
        description="Saved cursor state",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
    ),
    SystemVariable(
        name="DPW_SPED", address=0x69, size=2,
        description="Horizontal scroll speed (50ms units)",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Default is 4 (200ms between scroll steps)",
    ),
    SystemVariable(
        name="DPW_DELY", address=0x6B, size=2,
        description="Vertical scroll delay (50ms units)",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Default is 10 (500ms pause between scrolls)",
    ),
    SystemVariable(
        name="DPW_REDY", address=0x6D, size=2,
        description="Display ready countdown",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Decremented every 50ms until zero",
    ),
    SystemVariable(
        name="DPA_VADD", address=0x6F, size=2,
        description="VIEW string address",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="Address of string being scrolled by DP$VIEW",
    ),

    # =========================================================================
    # Keyboard Variables ($71-$7B)
    # =========================================================================

    SystemVariable(
        name="KBW_TDEL", address=0x71, size=2,
        description="Keyboard interrupt timing",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Default $B3DD for 0.05 second interval",
    ),
    SystemVariable(
        name="KBB_BACK", address=0x73, size=1,
        description="Keyboard buffer back index",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Offset to oldest key in circular buffer",
    ),
    SystemVariable(
        name="KBB_NKYS", address=0x74, size=1,
        description="Number of keys in buffer",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
    ),
    SystemVariable(
        name="KBB_PREV", address=0x75, size=1,
        description="Previous key pressed",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Used for auto-repeat detection",
    ),
    SystemVariable(
        name="KBB_WAIT", address=0x76, size=1,
        description="Unget key buffer",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Zero if no unget key, otherwise the key code",
    ),
    SystemVariable(
        name="KBB_DLAY", address=0x77, size=1,
        description="Auto-repeat initial delay",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Default 14 interrupts before repeat starts",
    ),
    SystemVariable(
        name="KBB_REPT", address=0x78, size=1,
        description="Auto-repeat rate",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Default 0 for fastest repeat",
    ),
    SystemVariable(
        name="KBB_CNTR", address=0x79, size=1,
        description="Auto-repeat counter",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
    ),
    SystemVariable(
        name="KBB_KNUM", address=0x7A, size=1,
        description="Keyboard table offset",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
    ),
    SystemVariable(
        name="KBB_STAT", address=0x7B, size=1,
        description="Keyboard status flags",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Bit 0: CAPS lock, Bit 1: NUM lock, Bit 2: SHIFT pressed",
    ),

    # =========================================================================
    # Time/Power Variables ($7C-$7E)
    # =========================================================================

    SystemVariable(
        name="TMB_SWOF", address=0x7C, size=1,
        description="Auto switch-off enabled flag",
        category=VarCategory.TIME, models=ALL_MODELS,
        notes="Clear to disable auto switch-off",
    ),
    SystemVariable(
        name="TMW_TOUT", address=0x7D, size=2,
        description="Time until switch-off",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),

    # =========================================================================
    # Editor Variables ($7F-$8A)
    # =========================================================================

    SystemVariable(
        name="EDB_MLEN", address=0x7F, size=1,
        description="Maximum input length",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDB_PLEN", address=0x80, size=1,
        description="Prompt length",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDB_FLIN", address=0x81, size=1,
        description="First editable line",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDB_POFF", address=0x82, size=1,
        description="First editable column",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDB_CLIN", address=0x83, size=1,
        description="Current editing line",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDB_STAT", address=0x84, size=1,
        description="Editor status",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDW_CPOS", address=0x85, size=2,
        description="Current cursor position in text",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDW_CB", address=0x87, size=2,
        description="Current buffer offset",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),
    SystemVariable(
        name="EDW_BL", address=0x89, size=2,
        description="Total buffer length",
        category=VarCategory.EDITOR, models=ALL_MODELS,
    ),

    # =========================================================================
    # Pack Variables ($8B-$95)
    # =========================================================================

    SystemVariable(
        name="PKB_CURP", address=0x8B, size=1,
        description="Current pack device",
        category=VarCategory.PACK, models=ALL_MODELS,
        notes="Set by PK$SETP (0=A:, 1=B:, 2=C:)",
    ),
    SystemVariable(
        name="PKB_CPAK", address=0x8C, size=1,
        description="Actual current pack slot",
        category=VarCategory.PACK, models=ALL_MODELS,
        notes="$FF when packs powered off",
    ),
    SystemVariable(
        name="PKW_RASI", address=0x8D, size=2,
        description="Internal RAM pack size",
        category=VarCategory.PACK, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PKW_CMAD", address=0x8F, size=2,
        description="Current pack memory address",
        category=VarCategory.PACK, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PKB_HPAD", address=0x91, size=1,
        description="High byte of pack address",
        category=VarCategory.PACK, models=ALL_MODELS,
        notes="For large packs (>64KB)",
    ),
    SystemVariable(
        name="PKW_CPAD", address=0x92, size=2,
        description="Current pack address (low 16 bits)",
        category=VarCategory.PACK, models=ALL_MODELS,
    ),
    SystemVariable(
        name="PKA_PKID", address=0x94, size=2,
        description="Pack ID string pointer",
        category=VarCategory.PACK, models=ALL_MODELS,
    ),

    # =========================================================================
    # File System Variables ($96-$A1)
    # =========================================================================

    SystemVariable(
        name="FLB_RECT", address=0x96, size=1,
        description="Current record type",
        category=VarCategory.FILE, models=ALL_MODELS,
        notes="Set by FL$RECT ($81-$FE)",
    ),
    SystemVariable(
        name="FLB_CPAK", address=0x97, size=1,
        description="Current file device",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="FLB_CONT", address=0x98, size=1,
        description="Device being cataloged",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="FLW_DREC", address=0x99, size=2,
        description="Next directory record number",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="FLW_CREC", address=0x9B, size=2,
        description="Current record number",
        category=VarCategory.FILE, models=ALL_MODELS,
        notes="First record is 1, not 0",
    ),
    SystemVariable(
        name="FLW_FNAD", address=0x9D, size=2,
        description="Address of current filename",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="FLW_NREC", address=0x9F, size=2,
        description="Total number of records",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="XFB_RECT", address=0xA1, size=1,
        description="Extended file record type",
        category=VarCategory.FILE, models=ALL_MODELS,
    ),

    # =========================================================================
    # Menu/Top-Level Variables ($A2-$A4)
    # =========================================================================

    SystemVariable(
        name="TLB_CPAK", address=0xA2, size=1,
        description="Default pack for top-level",
        category=VarCategory.MENU, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TLB_MODE", address=0xA3, size=1,
        description="Current top-level operation",
        category=VarCategory.MENU, models=ALL_MODELS,
        notes="FIND, SAVE, or ERASE mode",
    ),
    SystemVariable(
        name="BZB_MUTE", address=0xA4, size=1,
        description="Buzzer mute flag",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="Non-zero to silence buzzer",
    ),

    # =========================================================================
    # Runtime/Language Variables ($A5-$CF)
    # =========================================================================

    SystemVariable(
        name="RTA_SP", address=0xA5, size=2,
        description="Language stack pointer",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RTA_FP", address=0xA7, size=2,
        description="Frame (procedure) pointer",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RTA_PC", address=0xA9, size=2,
        description="Program counter (OPL)",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),

    # =========================================================================
    # Math Variables ($C5-$D6)
    # =========================================================================

    SystemVariable(
        name="MTT_AMAN", address=0xC5, size=7,
        description="Math accumulator mantissa",
        category=VarCategory.MATH, models=ALL_MODELS,
        notes="8-byte floating point accumulator",
    ),
    SystemVariable(
        name="MTB_AEXP", address=0xCC, size=1,
        description="Math accumulator exponent",
        category=VarCategory.MATH, models=ALL_MODELS,
    ),
    SystemVariable(
        name="MTB_ASGN", address=0xCD, size=1,
        description="Math accumulator sign",
        category=VarCategory.MATH, models=ALL_MODELS,
    ),
    SystemVariable(
        name="MTT_OMAN", address=0xCE, size=7,
        description="Math operand mantissa",
        category=VarCategory.MATH, models=ALL_MODELS,
    ),
    SystemVariable(
        name="MTB_OEXP", address=0xD5, size=1,
        description="Math operand exponent",
        category=VarCategory.MATH, models=ALL_MODELS,
    ),
    SystemVariable(
        name="MTB_OSGN", address=0xD6, size=1,
        description="Math operand sign",
        category=VarCategory.MATH, models=ALL_MODELS,
    ),

    # =========================================================================
    # Semi-Custom Chip I/O Addresses ($180-$3FF)
    # =========================================================================
    # These are memory-mapped I/O addresses for the Psion's custom ASIC.

    SystemVariable(
        name="SCA_LCDCTRL", address=0x0180, size=1,
        description="LCD control register",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
        notes="Commands and status for LCD controller",
    ),
    SystemVariable(
        name="SCA_LCDDATA", address=0x0181, size=1,
        description="LCD data register",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
        notes="Character/pattern data for LCD",
    ),
    SystemVariable(
        name="SCA_SWITCHOFF", address=0x01C0, size=1,
        description="Switch-off trigger address",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
        notes="Write to power off device",
    ),
    SystemVariable(
        name="SCA_PULSEENABLE", address=0x0200, size=1,
        description="High voltage pulse enable",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
        notes="For programming datapaks",
    ),
    SystemVariable(
        name="SCA_PULSEDISABLE", address=0x0240, size=1,
        description="High voltage pulse disable",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_ALARMON", address=0x0280, size=1,
        description="Buzzer on",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_ALARMOFF", address=0x02C0, size=1,
        description="Buzzer off",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_COUNTERRESET", address=0x0300, size=1,
        description="Counter reset",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
        notes="Reset keyboard/clock counter",
    ),
    SystemVariable(
        name="SCA_COUNTERCLOCK", address=0x0340, size=1,
        description="Counter clock increment",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_BANKRESET", address=0x0360, size=1,
        description="Reset RAM/ROM banks",
        category=VarCategory.HARDWARE, models=EXTENDED_SERVICE_MODELS,
        notes="LZ/P350/M-XP only",
    ),
    SystemVariable(
        name="SCA_NMIMPU", address=0x0380, size=1,
        description="Enable NMI to processor",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_NEXTRAM", address=0x03A0, size=1,
        description="Select next RAM bank",
        category=VarCategory.HARDWARE, models=frozenset({PsionModel.LZ, PsionModel.LZ64, PsionModel.P350}),
        notes="LZ/P350 only - bank switching",
    ),
    SystemVariable(
        name="SCA_NMICOUNTER", address=0x03C0, size=1,
        description="Enable NMI to counter",
        category=VarCategory.HARDWARE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SCA_NEXTROM", address=0x03E0, size=1,
        description="Select next ROM bank",
        category=VarCategory.HARDWARE, models=EXTENDED_SERVICE_MODELS,
        notes="LZ/M-XP only - ROM bank switching",
    ),

    # =========================================================================
    # Main RAM System Variables ($2000+)
    # =========================================================================

    SystemVariable(
        name="PERMCELL", address=0x2000, size=2,
        description="Permanent cell pointer",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="Code/data from booted devices",
    ),
    SystemVariable(
        name="MENUCELL", address=0x2002, size=2,
        description="Top-level menu cell",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
    ),
    SystemVariable(
        name="DIRYCELL", address=0x2004, size=2,
        description="Diary cell pointer",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TEXTCELL", address=0x2006, size=2,
        description="Language text cell",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="SYMBCELL", address=0x2008, size=2,
        description="Symbol table cell",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="GLOBCELL", address=0x200A, size=2,
        description="Global record cell",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="OCODCELL", address=0x200C, size=2,
        description="Q-code output cell",
        category=VarCategory.LANGUAGE, models=ALL_MODELS,
    ),
    SystemVariable(
        name="ALA_FREE", address=0x2040, size=2,
        description="Top of allocator area",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="End of last allocated cell",
    ),

    # Interrupt re-vector addresses
    SystemVariable(
        name="BTA_SWI", address=0x2052, size=2,
        description="SWI re-vector address",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="System call dispatch can be hooked here",
    ),
    SystemVariable(
        name="BTA_NMI", address=0x2054, size=2,
        description="NMI re-vector address",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
    ),
    SystemVariable(
        name="BTA_POLL", address=0x205A, size=2,
        description="Keyboard poll vector",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Routine that polls keyboard matrix",
    ),
    SystemVariable(
        name="BTA_TRAN", address=0x205C, size=2,
        description="Key translation vector",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Translates key number to ASCII",
    ),
    SystemVariable(
        name="BTA_TABL", address=0x205E, size=2,
        description="Keyboard table vector",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Points to 72-character translation table",
    ),

    # Display buffers
    SystemVariable(
        name="DPT_TLIN", address=0x2070, size=16,
        description="Top line display buffer",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
        notes="16 bytes for 2-line models",
    ),
    SystemVariable(
        name="DPT_BLIN", address=0x2080, size=16,
        description="Bottom line display buffer",
        category=VarCategory.DISPLAY, models=ALL_MODELS,
    ),

    # 4-line display variables (LZ)
    SystemVariable(
        name="DPA_SCRN", address=0x2090, size=2,
        description="Screen buffer address",
        category=VarCategory.DISPLAY, models=FOUR_LINE_MODELS,
    ),
    SystemVariable(
        name="DPB_NLIN", address=0x2092, size=1,
        description="Number of screen lines",
        category=VarCategory.DISPLAY, models=FOUR_LINE_MODELS,
        notes="2 or 4",
    ),
    SystemVariable(
        name="DPB_WIDE", address=0x2093, size=1,
        description="Screen width",
        category=VarCategory.DISPLAY, models=FOUR_LINE_MODELS,
        notes="16 or 20 characters",
    ),

    # Menu variables (LZ)
    SystemVariable(
        name="MNB_CPTZ", address=0x209C, size=1,
        description="Menu capitalization flag",
        category=VarCategory.MENU, models=EXTENDED_SERVICE_MODELS,
        notes="Set to 1 to disable auto-capitalization",
    ),

    # Keyboard buffer
    SystemVariable(
        name="KBT_BUFF", address=0x20B0, size=16,
        description="Keyboard circular buffer",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="16-character wrap-around buffer",
    ),
    SystemVariable(
        name="KBB_CLIK", address=0x20C0, size=1,
        description="Key click duration (ms)",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
        notes="Default 1ms",
    ),
    SystemVariable(
        name="KBB_SHFK", address=0x20C4, size=1,
        description="Shift key disable flag",
        category=VarCategory.KEYBOARD, models=ALL_MODELS,
    ),

    # Real-time clock variables
    SystemVariable(
        name="TMB_YEAR", address=0x20C5, size=1,
        description="Current year",
        category=VarCategory.TIME, models=ALL_MODELS,
        notes="0-99 on CM/XP, 0-255 on LZ",
    ),
    SystemVariable(
        name="TMB_MONS", address=0x20C6, size=1,
        description="Current month (0-11)",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TMB_DAYS", address=0x20C7, size=1,
        description="Current day (0-30)",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TMB_HOUR", address=0x20C8, size=1,
        description="Current hour (0-23)",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TMB_MINS", address=0x20C9, size=1,
        description="Current minute (0-59)",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TMB_SECS", address=0x20CA, size=1,
        description="Current second (0-59)",
        category=VarCategory.TIME, models=ALL_MODELS,
    ),
    SystemVariable(
        name="TMW_FRAM", address=0x20CB, size=2,
        description="Frame counter",
        category=VarCategory.TIME, models=ALL_MODELS,
        notes="Incremented on each keyboard interrupt (~20Hz)",
    ),
    SystemVariable(
        name="TMW_TCNT", address=0x20CD, size=2,
        description="Default switch-off time (seconds)",
        category=VarCategory.TIME, models=ALL_MODELS,
        notes="Default $012C = 300 = 5 minutes",
    ),

    # Pack ID storage
    SystemVariable(
        name="PKT_ID", address=0x20D7, size=40,
        description="Pack ID strings array",
        category=VarCategory.PACK, models=ALL_MODELS,
        notes="4 entries x 10 bytes each",
    ),

    # Calculator memory
    SystemVariable(
        name="RTT_NUMB", address=0x20FF, size=80,
        description="Calculator memory slots",
        category=VarCategory.MATH, models=ALL_MODELS,
        notes="10 slots x 8 bytes each",
    ),

    # Communications variables
    SystemVariable(
        name="RSB_BAUD", address=0x2150, size=1,
        description="Serial baud rate code",
        category=VarCategory.COMMS, models=ALL_MODELS,
        notes="0-9 for 50 to 9600 baud",
    ),
    SystemVariable(
        name="RSB_PARITY", address=0x2151, size=1,
        description="Serial parity setting",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RSB_BITS", address=0x2152, size=1,
        description="Serial data bits (7 or 8)",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RSB_STOP", address=0x2153, size=1,
        description="Serial stop bits (1 or 2)",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RSB_HAND", address=0x2154, size=1,
        description="Serial handshake setting",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RSB_PROTO", address=0x2155, size=1,
        description="File transfer protocol",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RSB_ECHO", address=0x2156, size=1,
        description="Terminal echo setting",
        category=VarCategory.COMMS, models=ALL_MODELS,
    ),

    # Assembler entry point
    SystemVariable(
        name="RST_ENTRY", address=0x2174, size=3,
        description="Machine code entry point",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="JSR entry for assembled programs",
    ),

    # Runtime buffer
    SystemVariable(
        name="RTB_BL", address=0x2187, size=1,
        description="Runtime buffer length",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
    ),
    SystemVariable(
        name="RTT_BF", address=0x2188, size=256,
        description="Runtime buffer",
        category=VarCategory.SYSTEM, models=ALL_MODELS,
        notes="256 bytes freely usable in machine code",
    ),

    # Alarm table
    SystemVariable(
        name="AMT_TAB", address=0x22F9, size=48,
        description="Alarm table",
        category=VarCategory.ALARM, models=ALL_MODELS,
        notes="8 alarms x 6 bytes each",
    ),

    # LZ-specific display buffer
    SystemVariable(
        name="DPT_4LIN", address=0x262C, size=80,
        description="4-line screen buffer",
        category=VarCategory.DISPLAY, models=FOUR_LINE_MODELS,
        notes="4 lines x 20 characters",
    ),

    # World time variables (LZ)
    SystemVariable(
        name="WLB_GMT", address=0x268A, size=1,
        description="GMT offset (half-hours)",
        category=VarCategory.TIME, models=EXTENDED_SERVICE_MODELS,
    ),

    # =========================================================================
    # ROM Constants ($FF00+)
    # =========================================================================

    SystemVariable(
        name="FFE7_LANG", address=0xFFE7, size=1,
        description="Language byte",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
        notes="Indicates available languages in ROM",
    ),
    SystemVariable(
        name="FFE8_MODEL", address=0xFFE8, size=1,
        description="Model identification byte",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
        notes="Bits 0-2 = model type",
    ),
    SystemVariable(
        name="FFE9_ROMVER", address=0xFFE9, size=1,
        description="ROM version (BCD)",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
        notes="e.g., $46 = version 4.6",
    ),
    SystemVariable(
        name="FFFA_SWI", address=0xFFFA, size=2,
        description="SWI vector address",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="FFFC_NMI", address=0xFFFC, size=2,
        description="NMI vector address",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
    ),
    SystemVariable(
        name="FFFE_RESET", address=0xFFFE, size=2,
        description="Reset vector address",
        category=VarCategory.ROM, models=ALL_MODELS, read_only=True,
    ),
)


# =============================================================================
# Variable Lookup Functions
# =============================================================================

# Build lookup dictionaries for efficient access
_VARIABLES_BY_NAME: dict[str, SystemVariable] = {
    var.name: var for var in SYSTEM_VARIABLES
}

_VARIABLES_BY_ADDRESS: dict[int, list[SystemVariable]] = {}
for var in SYSTEM_VARIABLES:
    if var.address not in _VARIABLES_BY_ADDRESS:
        _VARIABLES_BY_ADDRESS[var.address] = []
    _VARIABLES_BY_ADDRESS[var.address].append(var)


def get_variable(name: str) -> Optional[SystemVariable]:
    """
    Look up a system variable by name.

    Args:
        name: Variable name (case-insensitive)

    Returns:
        SystemVariable if found, None otherwise

    Example:
        >>> var = get_variable("UTW_S0")
        >>> var.address
        65
    """
    return _VARIABLES_BY_NAME.get(name.upper())


def get_variables_at_address(address: int) -> list[SystemVariable]:
    """
    Get all variables defined at a specific address.

    Multiple variables may share an address when one is a byte view
    and another is a word view of the same location.

    Args:
        address: Memory address

    Returns:
        List of SystemVariables at that address (may be empty)

    Example:
        >>> vars = get_variables_at_address(0x41)
        >>> [v.name for v in vars]
        ['UTW_S0', 'UTB_S0']
    """
    return _VARIABLES_BY_ADDRESS.get(address, [])


def get_variables_for_model(model: PsionModel) -> list[SystemVariable]:
    """
    Get all system variables supported on a specific model.

    Args:
        model: Target Psion model

    Returns:
        List of SystemVariables supported on that model
    """
    return [var for var in SYSTEM_VARIABLES if var.is_supported_on(model)]


def get_variables_by_category(category: VarCategory) -> list[SystemVariable]:
    """
    Get all system variables in a specific category.

    Args:
        category: Variable category

    Returns:
        List of SystemVariables in that category
    """
    return [var for var in SYSTEM_VARIABLES if var.category == category]


def get_all_variable_names() -> list[str]:
    """
    Get a sorted list of all variable names.

    Returns:
        List of variable names in alphabetical order
    """
    return sorted(_VARIABLES_BY_NAME.keys())


# =============================================================================
# Include File Generation
# =============================================================================

def generate_sysvars_inc(
    model: Optional[str] = None,
    categories: Optional[list[VarCategory]] = None,
    include_notes: bool = False,
) -> str:
    """
    Generate assembly include file with system variable definitions.

    Args:
        model: Target model name ("CM", "XP", "LZ", etc.) or None for all
        categories: List of categories to include, or None for all
        include_notes: If True, include notes as comments

    Returns:
        Assembly include file content as a string

    Example:
        >>> content = generate_sysvars_inc(model="LZ")
        >>> print(content[:100])
        ; =============================================================================
        ; SYSVARS.INC - Psion Organiser II System Variables
    """
    lines = [
        "; =============================================================================",
        "; SYSVARS.INC - Psion Organiser II System Variables",
        "; =============================================================================",
        "; Generated by psion-sdk",
    ]

    if model:
        lines.append(f"; Target model: {model}")
    else:
        lines.append("; Target model: ALL")

    lines.extend([
        ";",
        "; Usage: INCLUDE \"sysvars.inc\"",
        "; =============================================================================",
        "",
    ])

    # Determine target model
    target_model = None
    if model:
        from psion_sdk.sdk.models import get_model_by_name
        target_model = get_model_by_name(model)

    # Group variables by category
    categories_to_include = categories or list(VarCategory)
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

    for category in categories_to_include:
        vars_in_category = [
            var for var in SYSTEM_VARIABLES
            if var.category == category and
            (target_model is None or var.is_supported_on(target_model))
        ]

        if not vars_in_category:
            continue

        category_name = category_names.get(category, category.name)
        lines.extend([
            f"; -----------------------------------------------------------------------------",
            f"; {category_name}",
            f"; -----------------------------------------------------------------------------",
            "",
        ])

        for var in vars_in_category:
            line = var.format_asm_equ()
            if include_notes and var.notes:
                line += f"  ({var.notes})"
            lines.append(line)

        lines.append("")

    lines.extend([
        "; =============================================================================",
        "; End of sysvars.inc",
        "; =============================================================================",
    ])

    return "\n".join(lines)
