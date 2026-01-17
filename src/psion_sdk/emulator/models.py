"""
Psion Organiser II Model Definitions
====================================

Defines the hardware configurations for different Psion Organiser II models.

Supported models:
- CM: Entry model with 8KB RAM, 2-line display
- XP: Extended with 16-32KB RAM, 2-line display
- LZ: Large display with 32KB RAM, 4-line display
- LZ64: Large display with 64KB RAM, 4-line display
- Various POS (Point of Sale) variants

Each model has specific characteristics:
- RAM size (8K, 16K, 32K, 64K, 96K)
- Display lines (2 or 4)
- Display columns (16 for 2-line, 20 for 4-line)
- Default ROM version
- Keyboard layout

The model configuration is used by the Emulator class to set up the
correct hardware emulation.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class KeyboardLayout(Enum):
    """
    Keyboard layout types.

    Different Psion models use different keyboard layouts.
    """
    NORMAL = "normal"       # Standard Organiser II keyboard
    POS200 = "pos200"       # POS 200 numeric keypad
    ALPHA_POS = "alpha_pos" # Alpha POS with letters


@dataclass(frozen=True)
class PsionModel:
    """
    Configuration for a Psion Organiser II model.

    Defines the hardware characteristics of a specific model/variant.

    Attributes:
        name: Human-readable model name (e.g., "XP (32K)")
        model_type: Model type code (e.g., "XP", "LZ")
        ram_kb: RAM size in kilobytes
        display_lines: Number of display lines (2 or 4)
        display_cols: Number of display columns (16 or 20)
        keyboard_layout: Keyboard type
        default_rom: Default ROM filename
        model_byte: Model identification byte from ROM ($FFE8)
    """
    name: str
    model_type: str
    ram_kb: int
    display_lines: int
    display_cols: int
    keyboard_layout: KeyboardLayout
    default_rom: str
    model_byte: int

    @property
    def is_2line(self) -> bool:
        """Check if model has 2-line display."""
        return self.display_lines == 2

    @property
    def is_4line(self) -> bool:
        """Check if model has 4-line display."""
        return self.display_lines == 4


# =============================================================================
# Predefined Model Configurations
# =============================================================================

# Model byte values from ROM at $FFE8
# (Used for snapshot compatibility checking)
MODEL_BYTE_CM = 0x00
MODEL_BYTE_XP_16K = 0x01
MODEL_BYTE_XP_32K = 0x02
MODEL_BYTE_LZ = 0x0E
MODEL_BYTE_LZ64 = 0x0D

# Standard model configurations
# Based on JAPE's PsionModels array from psion.js

MODEL_CM = PsionModel(
    name="CM (8K)",
    model_type="CM",
    ram_kb=8,
    display_lines=2,
    display_cols=16,
    keyboard_layout=KeyboardLayout.NORMAL,
    default_rom="33-cm.rom",
    model_byte=MODEL_BYTE_CM,
)

MODEL_XP_16K = PsionModel(
    name="XP (16K)",
    model_type="XP",
    ram_kb=16,
    display_lines=2,
    display_cols=16,
    keyboard_layout=KeyboardLayout.NORMAL,
    default_rom="31-xp.rom",
    model_byte=MODEL_BYTE_XP_16K,
)

MODEL_XP_32K = PsionModel(
    name="XP (32K)",
    model_type="XP",
    ram_kb=32,
    display_lines=2,
    display_cols=16,
    keyboard_layout=KeyboardLayout.NORMAL,
    default_rom="37-lam.rom",
    model_byte=MODEL_BYTE_XP_32K,
)

MODEL_LZ = PsionModel(
    name="LZ (32K)",
    model_type="LZ",
    ram_kb=32,
    display_lines=4,
    display_cols=20,
    keyboard_layout=KeyboardLayout.NORMAL,
    default_rom="46-lz.rom",
    model_byte=MODEL_BYTE_LZ,
)

MODEL_LZ64 = PsionModel(
    name="LZ64 (64K)",
    model_type="LZ64",
    ram_kb=64,
    display_lines=4,
    display_cols=20,
    keyboard_layout=KeyboardLayout.NORMAL,
    default_rom="46b-lz64.rom",
    model_byte=MODEL_BYTE_LZ64,
)

# Alias for common default model
MODEL_XP = MODEL_XP_32K
MODEL_DEFAULT = MODEL_XP

# Dictionary mapping model codes to configurations
_MODEL_MAP = {
    "CM": MODEL_CM,
    "XP": MODEL_XP_32K,  # Default XP is 32K
    "XP16": MODEL_XP_16K,
    "XP32": MODEL_XP_32K,
    "LZ": MODEL_LZ,
    "LZ64": MODEL_LZ64,
}

# Additional ROM variants (for reference)
# These can be used with custom EmulatorConfig.rom_path
ROM_VARIANTS = {
    # CM variants
    "cm_24": "24-cm.rom",
    "cm_26": "26-cm.rom",
    "cm_33": "33-cm.rom",
    "cm_33f": "33-cmf.rom",  # French
    "cm_36f": "36-cmf.rom",  # French

    # XP variants
    "xp_24": "24-xp.rom",
    "xp_26": "26-xp.rom",
    "xp_31": "31-xp.rom",
    "xp_33": "33-la.rom",
    "xp_34g": "34-lag.rom",  # German
    "xp_36": "36-la.rom",
    "xp_36f": "36-laf.rom",  # French
    "xp_36g": "36-lag.rom",  # German
    "xp_37": "37-lam.rom",   # Multilingual

    # LZ variants
    "lz_42": "42-lz.rom",
    "lz_44": "44-lz.rom",
    "lz_45": "45-lz.rom",
    "lz_45i": "45-lzi.rom",  # Italian/Spanish
    "lz_45s": "45-lzs.rom",  # Swedish/Danish
    "lz_46": "46-lz.rom",
    "lz_46i": "46-lzi.rom",  # Italian/Spanish

    # LZ64 variants
    "lz64_43": "43-lz64.rom",
    "lz64_44": "44-lz64.rom",
    "lz64_45": "45-lz64.rom",
    "lz64_46a": "46a-lz64.rom",
    "lz64_46b": "46b-lz64.rom",
    "lz64_46i": "46-lz64i.rom",  # Italian/Spanish
    "lz64_46s": "46-lz64s.rom",  # Swedish/Danish
}


# =============================================================================
# Model Selection Functions
# =============================================================================

def get_model(model_code: str) -> PsionModel:
    """
    Get model configuration by code.

    Supported codes:
    - "CM": CM 8KB
    - "XP" or "XP32": XP 32KB (default XP)
    - "XP16": XP 16KB
    - "LZ": LZ 32KB
    - "LZ64": LZ 64KB

    Args:
        model_code: Model code string (case-insensitive)

    Returns:
        PsionModel configuration

    Raises:
        ValueError: If model code is not recognized
    """
    code = model_code.upper().strip()

    if code in _MODEL_MAP:
        return _MODEL_MAP[code]

    # Try some common variations
    if code in ("LA", "LAHP"):
        return MODEL_XP_32K
    if code == "LZ32":
        return MODEL_LZ
    if code in ("DEFAULT", ""):
        return MODEL_DEFAULT

    available = ", ".join(sorted(_MODEL_MAP.keys()))
    raise ValueError(
        f"Unknown model code '{model_code}'. Available: {available}"
    )


def list_models() -> list[PsionModel]:
    """
    Get list of all predefined model configurations.

    Returns:
        List of PsionModel instances
    """
    return [
        MODEL_CM,
        MODEL_XP_16K,
        MODEL_XP_32K,
        MODEL_LZ,
        MODEL_LZ64,
    ]


def get_rom_path(rom_name: str, rom_dir: Optional[Path] = None) -> Path:
    """
    Get full path to ROM file.

    Args:
        rom_name: ROM filename or variant key
        rom_dir: Optional ROM directory (defaults to thirdparty/jape/roms)

    Returns:
        Path to ROM file

    Raises:
        FileNotFoundError: If ROM file doesn't exist
    """
    # Check if it's a variant key
    if rom_name.lower() in ROM_VARIANTS:
        rom_name = ROM_VARIANTS[rom_name.lower()]

    # Determine ROM directory
    if rom_dir is None:
        # First check emulator/roms directory (primary location)
        emulator_roms = Path(__file__).parent / "roms"
        if (emulator_roms / rom_name).exists():
            rom_dir = emulator_roms
        else:
            # Fall back to thirdparty/jape/roms (legacy location)
            rom_dir = Path(__file__).parent.parent.parent.parent / "thirdparty" / "jape" / "roms"

    rom_path = rom_dir / rom_name

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM file not found: {rom_path}")

    return rom_path


def get_model_for_ram(ram_kb: int, display_lines: int = 2) -> PsionModel:
    """
    Get appropriate model configuration for given RAM size and display.

    Args:
        ram_kb: RAM size in kilobytes
        display_lines: Number of display lines (2 or 4)

    Returns:
        Best matching PsionModel configuration
    """
    if display_lines == 4:
        if ram_kb >= 64:
            return MODEL_LZ64
        return MODEL_LZ

    # 2-line display
    if ram_kb <= 8:
        return MODEL_CM
    if ram_kb <= 16:
        return MODEL_XP_16K
    return MODEL_XP_32K
