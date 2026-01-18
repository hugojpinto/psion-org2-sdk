"""
Psion Organiser II Emulator
===========================

A complete HD6303-based emulator for the Psion Organiser II series.

This package provides cycle-accurate emulation of the Psion Organiser II
hardware, including:

- **HD6303 CPU**: Full instruction set with accurate timing
- **Memory System**: RAM/ROM with bank switching
- **Display Controller**: HD44780-compatible LCD with text/pixel APIs
- **Keyboard Matrix**: Complete key mapping with ON/CLEAR detection
- **Pack Support**: Datapak, Rampak, and Flash pack emulation
- **Debugging**: Breakpoints, watchpoints, register conditions

Quick Start
-----------

Basic usage::

    >>> from psion_sdk.emulator import Emulator, EmulatorConfig
    >>> emu = Emulator(EmulatorConfig(model="XP"))
    >>> emu.reset()
    >>> emu.load_opk("hello.opk")
    >>> emu.run_until_text("Hello", max_cycles=1_000_000)
    True
    >>> print(emu.display_text)
    Hello World

With debugging::

    >>> emu = Emulator()
    >>> emu.reset()
    >>> emu.add_breakpoint(0x8100)
    >>> event = emu.run()
    >>> if event.reason == BreakReason.PC_BREAKPOINT:
    ...     print(f"Stopped at ${event.address:04X}")

Supported Models
----------------

- **CM**: 8KB RAM, 2-line display
- **XP**: 16-32KB RAM, 2-line display (default)
- **LZ**: 32KB RAM, 4-line display
- **LZ64**: 64KB RAM, 4-line display

Implementation Notes
--------------------

This emulator is ported from JAPE (Jaap's Psion Emulator) JavaScript
implementation by Jaap Scherphuis. The port maintains:

- Exact instruction timing and cycle counts
- Precise flag behavior for all operations
- Memory map compatibility
- Interrupt handling (NMI, OCI)

The main differences from JAPE are:
- Pure Python (no browser dependencies)
- Comprehensive breakpoint/watchpoint support
- Type hints for IDE integration
- Designed for testing workflows

Module Structure
----------------

- `emulator.py`: Main Emulator class (high-level API)
- `cpu.py`: HD6303 CPU implementation
- `bus.py`: Memory bus and I/O controller
- `memory.py`: RAM and ROM with bank switching
- `display.py`: LCD controller
- `keyboard.py`: Key matrix handling
- `pack.py`: Pack/cartridge emulation
- `breakpoints.py`: Debugging support
- `models.py`: Psion model configurations

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

# Main entry point
from .emulator import Emulator, EmulatorConfig

# CPU components
from .cpu import HD6303, CPUState, Flags

# Memory subsystem
from .memory import Memory, Ram, Rom

# I/O controllers
from .display import Display, DisplayState
from .keyboard import Keyboard, KeyboardLayout
from .bus import Bus, BusState

# Pack/cartridge support
from .pack import (
    Pack,
    PackPin,
    PackType,
    CommandType,
    PackCounter,
    PackCounterLinear,
    PackCounterPaged,
    PackCounterSegmented,
    PackController,
    PackControllerDummy,
    PackControllerRom,
    PackControllerEprom,
    PackControllerRam,
    PackControllerFlash,
)

# Debugging support
from .breakpoints import (
    BreakpointManager,
    BreakEvent,
    BreakReason,
    Condition,
)

# Model configurations
from .models import (
    PsionModel,
    KeyboardLayout,
    get_model,
    list_models,
    get_rom_path,
    get_model_for_ram,
    MODEL_CM,
    MODEL_XP,
    MODEL_XP_16K,
    MODEL_XP_32K,
    MODEL_LZ,
    MODEL_LZ64,
    MODEL_DEFAULT,
)

__all__ = [
    # Main API
    "Emulator",
    "EmulatorConfig",

    # CPU
    "HD6303",
    "CPUState",
    "Flags",

    # Memory
    "Memory",
    "Ram",
    "Rom",

    # Display
    "Display",
    "DisplayState",

    # Keyboard
    "Keyboard",
    "KeyboardLayout",

    # Bus
    "Bus",
    "BusState",

    # Pack
    "Pack",
    "PackPin",
    "PackType",
    "CommandType",
    "PackCounter",
    "PackCounterLinear",
    "PackCounterPaged",
    "PackCounterSegmented",
    "PackController",
    "PackControllerDummy",
    "PackControllerRom",
    "PackControllerEprom",
    "PackControllerRam",
    "PackControllerFlash",

    # Debugging
    "BreakpointManager",
    "BreakEvent",
    "BreakReason",
    "Condition",

    # Models
    "PsionModel",
    "get_model",
    "list_models",
    "get_rom_path",
    "get_model_for_ram",
    "MODEL_CM",
    "MODEL_XP",
    "MODEL_XP_16K",
    "MODEL_XP_32K",
    "MODEL_LZ",
    "MODEL_LZ64",
    "MODEL_DEFAULT",
]
