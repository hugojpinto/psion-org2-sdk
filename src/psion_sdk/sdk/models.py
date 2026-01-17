"""
Psion Organiser II Model Definitions and Detection
===================================================

This module provides model-specific information for the Psion Organiser II
family of handheld computers. It defines the different models, their capabilities,
memory configurations, and display characteristics.

Model Detection
---------------
The Psion stores model identification at ROM address $FFE8 (model byte 1).
Bits 0-2 encode the model type:
    - 0: CM (entry-level, 8KB RAM, 2x16 display)
    - 1: XP (extended, 16-32KB RAM, 2x16 display)
    - 2: LA (4-line, 32KB RAM, 4x20 display)
    - 4: P350 (point-of-sale variant)
    - 5: LZ64 (maximum RAM, 64-96KB, 4x20 display)
    - 6: LZ (advanced, 32-64KB RAM, 4x20 display)

The ROM version is stored at $FFE9 in BCD format (e.g., $46 = version 4.6).

Reference
---------
- Model identification: https://www.jaapsch.net/psion/model.htm
- System variables: https://www.jaapsch.net/psion/sysvars.htm
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


# =============================================================================
# ROM Constants for Model Detection
# =============================================================================

# Address of model identification byte in ROM (bits 0-2 = model type)
MODEL_BYTE_ADDRESS = 0xFFE8

# Address of ROM version byte (BCD format)
ROMVER_ADDRESS = 0xFFE9

# Address of language byte (indicates available languages)
LANGBYTE_ADDRESS = 0xFFE7

# Second model byte for additional identification
MODEL_BYTE2_ADDRESS = 0xFFCB


# =============================================================================
# Model Enumeration
# =============================================================================

class PsionModel(IntEnum):
    """
    Psion Organiser II model identifiers.

    These values correspond to bits 0-2 of the model byte at $FFE8.
    The model byte encodes both the model type and various hardware
    feature flags.

    Usage:
        >>> model = PsionModel.LZ
        >>> model.value
        6
        >>> model.name
        'LZ'
        >>> PsionModel(0)
        <PsionModel.CM: 0>

    Note:
        Value 3 is not used in production models.
    """
    CM = 0      # Entry-level model with 8KB RAM
    XP = 1      # Extended model with 16-32KB RAM
    LA = 2      # 4-line display model
    P350 = 4    # Point-of-sale variant (no built-in applications)
    LZ64 = 5    # Maximum RAM variant (64-96KB)
    LZ = 6      # Advanced 4-line model (most capable)

    @classmethod
    def from_model_byte(cls, byte: int) -> Optional["PsionModel"]:
        """
        Extract model type from the model byte at $FFE8.

        The model byte contains the model ID in bits 0-2. Other bits
        indicate various hardware features.

        Args:
            byte: The raw model byte value from $FFE8

        Returns:
            The corresponding PsionModel, or None if the model ID is invalid

        Example:
            >>> PsionModel.from_model_byte(0x86)  # LZ with some feature flags
            <PsionModel.LZ: 6>
        """
        model_id = byte & 0x07  # Extract bits 0-2
        try:
            return cls(model_id)
        except ValueError:
            return None

    def get_info(self) -> "ModelInfo":
        """
        Get detailed information about this model.

        Returns:
            ModelInfo dataclass with full model specifications
        """
        return MODEL_INFO.get(self, _UNKNOWN_MODEL)


# =============================================================================
# Model Capabilities
# =============================================================================

@dataclass(frozen=True)
class DisplayInfo:
    """
    Display characteristics for a Psion model.

    Attributes:
        rows: Number of text rows (2 or 4)
        columns: Number of text columns (16 or 20)
        has_graphics: Whether custom UDG (User-Defined Graphics) is supported
    """
    rows: int
    columns: int
    has_graphics: bool = True

    @property
    def total_positions(self) -> int:
        """Total number of character positions on the display."""
        return self.rows * self.columns


@dataclass(frozen=True)
class MemoryInfo:
    """
    Memory configuration for a Psion model.

    The Psion memory map varies by model, but generally:
    - $0000-$003F: HD6303 internal registers
    - $0040-$00FF: Zero page RAM (fast access)
    - $0100-$03FF: Semi-custom chip I/O
    - $0400-$1FFF: System RAM
    - $2000-$7FFF: Extended RAM (banked on LZ)
    - $8000-$FFFF: ROM (banked on some models)

    Attributes:
        ram_kb: Base RAM in kilobytes
        max_ram_kb: Maximum expandable RAM in kilobytes
        has_banking: Whether RAM/ROM banking is supported
        ram_start: Start address of user-accessible RAM
        ram_end: End address of user-accessible RAM
    """
    ram_kb: int
    max_ram_kb: int
    has_banking: bool
    ram_start: int
    ram_end: int

    @property
    def ram_size(self) -> int:
        """Base RAM size in bytes."""
        return self.ram_kb * 1024


@dataclass(frozen=True)
class ModelInfo:
    """
    Complete specifications for a Psion Organiser II model.

    This dataclass aggregates all model-specific information including
    display characteristics, memory configuration, and ROM version range.

    Attributes:
        model: The PsionModel enum value
        name: Full marketing name (e.g., "Organiser II XP")
        display: Display characteristics
        memory: Memory configuration
        rom_versions: Tuple of (min_version, max_version) in BCD format
        notes: Additional information about the model
    """
    model: PsionModel
    name: str
    display: DisplayInfo
    memory: MemoryInfo
    rom_versions: tuple[int, int]  # (min, max) BCD format
    notes: str = ""

    @property
    def is_4_line(self) -> bool:
        """Return True if this is a 4-line display model."""
        return self.display.rows == 4

    @property
    def is_2_line(self) -> bool:
        """Return True if this is a 2-line display model."""
        return self.display.rows == 2

    @property
    def supports_extended_services(self) -> bool:
        """Return True if model supports LZ extended system services."""
        return self.model in (PsionModel.LA, PsionModel.LZ, PsionModel.LZ64)


# =============================================================================
# Model Information Database
# =============================================================================

# Predefined model specifications based on Psion technical documentation
MODEL_INFO: dict[PsionModel, ModelInfo] = {
    PsionModel.CM: ModelInfo(
        model=PsionModel.CM,
        name="Organiser II CM",
        display=DisplayInfo(rows=2, columns=16),
        memory=MemoryInfo(
            ram_kb=8,
            max_ram_kb=8,
            has_banking=False,
            ram_start=0x2000,
            ram_end=0x3FFF,
        ),
        rom_versions=(0x24, 0x36),  # 2.4 to 3.6F
        notes="Entry-level model. Limited RAM, 2-line display.",
    ),

    PsionModel.XP: ModelInfo(
        model=PsionModel.XP,
        name="Organiser II XP",
        display=DisplayInfo(rows=2, columns=16),
        memory=MemoryInfo(
            ram_kb=16,
            max_ram_kb=32,
            has_banking=False,
            ram_start=0x2000,
            ram_end=0x5FFF,
        ),
        rom_versions=(0x24, 0x37),  # 2.4 to 3.7
        notes="Extended model with more RAM. Multi-lingual versions available.",
    ),

    PsionModel.LA: ModelInfo(
        model=PsionModel.LA,
        name="Organiser II LA",
        display=DisplayInfo(rows=4, columns=20),
        memory=MemoryInfo(
            ram_kb=32,
            max_ram_kb=32,
            has_banking=False,
            ram_start=0x0400,
            ram_end=0x7FFF,
        ),
        rom_versions=(0x40, 0x42),  # 4.0 to 4.2
        notes="4-line display model. Also known as Model LA.",
    ),

    PsionModel.P350: ModelInfo(
        model=PsionModel.P350,
        name="P350 (Workabout)",
        display=DisplayInfo(rows=4, columns=20),
        memory=MemoryInfo(
            ram_kb=32,
            max_ram_kb=64,
            has_banking=True,
            ram_start=0x0400,
            ram_end=0x7FFF,
        ),
        rom_versions=(0x40, 0x46),  # 4.0 to 4.6
        notes="Point-of-sale variant. No built-in diary/notepad/world applications.",
    ),

    PsionModel.LZ64: ModelInfo(
        model=PsionModel.LZ64,
        name="Organiser II LZ64",
        display=DisplayInfo(rows=4, columns=20, has_graphics=True),
        memory=MemoryInfo(
            ram_kb=64,
            max_ram_kb=96,
            has_banking=True,
            ram_start=0x0400,
            ram_end=0x7FFF,
        ),
        rom_versions=(0x43, 0x46),  # 4.3 to 4.6
        notes="Maximum RAM model. Uses RAM banking for extended memory.",
    ),

    PsionModel.LZ: ModelInfo(
        model=PsionModel.LZ,
        name="Organiser II LZ",
        display=DisplayInfo(rows=4, columns=20, has_graphics=True),
        memory=MemoryInfo(
            ram_kb=32,
            max_ram_kb=64,
            has_banking=True,
            ram_start=0x0400,
            ram_end=0x7FFF,
        ),
        rom_versions=(0x42, 0x46),  # 4.2 to 4.6
        notes="Most capable standard model. Supports all extended services.",
    ),
}

# Placeholder for unknown model types
_UNKNOWN_MODEL = ModelInfo(
    model=PsionModel.CM,  # Fallback
    name="Unknown Model",
    display=DisplayInfo(rows=2, columns=16),
    memory=MemoryInfo(ram_kb=8, max_ram_kb=8, has_banking=False,
                      ram_start=0x2000, ram_end=0x3FFF),
    rom_versions=(0x00, 0xFF),
    notes="Unknown or unsupported model.",
)


# =============================================================================
# Model Detection Utilities
# =============================================================================

def decode_model_byte(byte: int) -> dict[str, any]:
    """
    Decode all information from the model byte at $FFE8.

    The model byte encodes several pieces of information:
    - Bits 0-2: Model type (CM=0, XP=1, LA=2, P350=4, LZ64=5, LZ=6)
    - Bit 3: Multi-lingual flag (1 = multi-lingual ROM)
    - Bit 4: Type B variant flag
    - Bits 5-7: Reserved/variant specific

    Args:
        byte: The raw model byte value from $FFE8

    Returns:
        Dictionary with decoded information:
        - 'model': PsionModel enum or None
        - 'model_id': Raw model ID (0-7)
        - 'multi_lingual': True if multi-lingual ROM
        - 'type_b': True if Type B hardware variant
        - 'raw': Original byte value

    Example:
        >>> info = decode_model_byte(0x86)
        >>> info['model']
        <PsionModel.LZ: 6>
        >>> info['multi_lingual']
        True
    """
    model_id = byte & 0x07
    model = PsionModel.from_model_byte(byte)

    return {
        "model": model,
        "model_id": model_id,
        "multi_lingual": bool(byte & 0x08),
        "type_b": bool(byte & 0x10),
        "raw": byte,
    }


def decode_rom_version(bcd_byte: int) -> tuple[int, int]:
    """
    Decode ROM version from BCD format at $FFE9.

    The ROM version is stored as two BCD digits in a single byte.
    For example, $46 represents version 4.6.

    Args:
        bcd_byte: The ROM version byte in BCD format

    Returns:
        Tuple of (major, minor) version numbers

    Example:
        >>> decode_rom_version(0x46)
        (4, 6)
        >>> decode_rom_version(0x37)
        (3, 7)
    """
    major = (bcd_byte >> 4) & 0x0F
    minor = bcd_byte & 0x0F
    return (major, minor)


def format_rom_version(bcd_byte: int) -> str:
    """
    Format ROM version as a human-readable string.

    Args:
        bcd_byte: The ROM version byte in BCD format

    Returns:
        Version string in "X.Y" format

    Example:
        >>> format_rom_version(0x46)
        '4.6'
    """
    major, minor = decode_rom_version(bcd_byte)
    return f"{major}.{minor}"


def get_model_by_name(name: str) -> Optional[PsionModel]:
    """
    Look up a Psion model by its string name.

    Accepts various forms of the model name:
    - Short names: "CM", "XP", "LA", "LZ", "LZ64", "P350"
    - Full names: "Organiser II LZ"

    The search is case-insensitive.

    Args:
        name: Model name to look up

    Returns:
        PsionModel enum value, or None if not found

    Example:
        >>> get_model_by_name("LZ")
        <PsionModel.LZ: 6>
        >>> get_model_by_name("organiser ii xp")
        <PsionModel.XP: 1>
    """
    name_upper = name.upper().strip()

    # Try direct enum name match
    for model in PsionModel:
        if model.name == name_upper:
            return model

    # Try exact match against full names first (before substring matching)
    for model, info in MODEL_INFO.items():
        if name_upper == info.name.upper():
            return model

    # Fall back to substring matching (try longer names first to avoid LZ64 matching before LZ)
    # Sort by name length descending to prefer more specific matches
    sorted_models = sorted(MODEL_INFO.items(), key=lambda x: len(x[1].name), reverse=True)
    for model, info in sorted_models:
        if name_upper in info.name.upper():
            return model

    return None


def get_supported_models() -> list[PsionModel]:
    """
    Return a list of all supported Psion models.

    Returns:
        List of PsionModel enum values, ordered by typical capability level

    Example:
        >>> models = get_supported_models()
        >>> [m.name for m in models]
        ['CM', 'XP', 'LA', 'P350', 'LZ', 'LZ64']
    """
    return [
        PsionModel.CM,
        PsionModel.XP,
        PsionModel.LA,
        PsionModel.P350,
        PsionModel.LZ,
        PsionModel.LZ64,
    ]


def get_all_models_info() -> list[ModelInfo]:
    """
    Return detailed information for all supported models.

    Returns:
        List of ModelInfo dataclasses for all supported models
    """
    return [MODEL_INFO[model] for model in get_supported_models()]


# =============================================================================
# Model Family Groupings
# =============================================================================

# 2-line display models (CM, XP)
TWO_LINE_MODELS = frozenset({PsionModel.CM, PsionModel.XP})

# 4-line display models (LA, P350, LZ, LZ64)
FOUR_LINE_MODELS = frozenset({PsionModel.LA, PsionModel.P350,
                              PsionModel.LZ, PsionModel.LZ64})

# Models with RAM banking support
BANKING_MODELS = frozenset({PsionModel.P350, PsionModel.LZ, PsionModel.LZ64})

# Models with extended system services (LZ-specific calls)
EXTENDED_SERVICE_MODELS = frozenset({PsionModel.LA, PsionModel.P350,
                                     PsionModel.LZ, PsionModel.LZ64})

# All production models as a frozenset
ALL_MODELS = frozenset(PsionModel)


def is_compatible(target_model: PsionModel, code_model: PsionModel) -> bool:
    """
    Check if code written for one model is compatible with another.

    Generally, code written for simpler models (CM) will work on more
    capable models (LZ), but not vice versa. Extended services available
    on LZ won't work on CM/XP.

    Args:
        target_model: Model the code is intended to run on
        code_model: Model the code was written for

    Returns:
        True if the code should be compatible

    Example:
        >>> is_compatible(PsionModel.LZ, PsionModel.CM)
        True  # CM code runs on LZ
        >>> is_compatible(PsionModel.CM, PsionModel.LZ)
        False  # LZ code may use extended services unavailable on CM
    """
    # Code for the same model is always compatible
    if target_model == code_model:
        return True

    # CM/XP code can run on any model
    if code_model in TWO_LINE_MODELS:
        return True

    # Extended service models can run each other's code (display permitting)
    if (target_model in EXTENDED_SERVICE_MODELS and
        code_model in EXTENDED_SERVICE_MODELS):
        return True

    # 2-line models cannot run 4-line or extended service code
    return False
