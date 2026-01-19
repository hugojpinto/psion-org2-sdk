"""
Psion Organiser II Emulator - Main Orchestrator
================================================

This module provides the main `Emulator` class that orchestrates all emulator
components to provide a clean, high-level API for running and testing programs.

The Emulator class:
- Initializes all components (CPU, memory, display, keyboard, bus, packs)
- Provides program loading from OPK files or raw bytes
- Supports execution control (run, step, run_until_text, run_until_pc)
- Integrates breakpoints and watchpoints for debugging
- Offers display output inspection
- Supports keyboard input simulation

Example usage:
    >>> from psion_sdk.emulator import Emulator, EmulatorConfig
    >>> emu = Emulator(EmulatorConfig(model="XP"))
    >>> emu.reset()
    >>> emu.load_opk("hello.opk")
    >>> success = emu.run_until_text("Hello", max_cycles=1_000_000)
    >>> print(emu.display_text)

Ported from JAPE's psion.js orchestration logic, enhanced with:
- Type hints for all public methods
- Breakpoint integration via on_instruction hook
- Comprehensive error handling

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, List, Callable

from .cpu import HD6303, CPUState
from .bus import Bus, BusState
from .memory import Memory
from .display import Display
from .keyboard import Keyboard
from .pack import Pack
from .breakpoints import BreakpointManager, BreakEvent, BreakReason
from .models import PsionModel, get_model, get_rom_path


@dataclass(frozen=True)
class EmulatorConfig:
    """
    Configuration for emulator initialization.

    Specifies which Psion model to emulate and optionally a custom ROM path.

    Attributes:
        model: Model code ("CM", "XP", "LZ", "LZ64"). Default is "XP" (32KB).
        rom_path: Optional path to a custom ROM file. If not provided,
                  uses the default ROM for the specified model.

    Example:
        >>> config = EmulatorConfig(model="LZ")  # Use default LZ ROM
        >>> config = EmulatorConfig(model="XP", rom_path=Path("custom.rom"))
    """
    model: str = "XP"
    rom_path: Optional[Path] = None


class Emulator:
    """
    Psion Organiser II Emulator with instrumentation support.

    This is the main entry point for emulator usage. It orchestrates the
    CPU, memory, display, keyboard, and pack subsystems into a cohesive
    whole, providing high-level methods for common operations.

    The emulator integrates with the BreakpointManager to support:
    - PC breakpoints (stop at specific addresses, optionally with register conditions)
    - Memory watchpoints (stop on read/write to addresses, optionally with register conditions)
    - Syscall hooks (intercept OS calls)

    Attributes:
        config: The EmulatorConfig used to initialize this instance
        cpu: The HD6303 CPU instance (accessible for low-level control)
        bus: The memory bus controller
        display: The LCD display controller
        keyboard: The keyboard matrix controller
        breakpoints: The breakpoint/watchpoint manager

    Example:
        >>> emu = Emulator()
        >>> emu.reset()
        >>> emu.load_opk("hello.opk")
        >>> success = emu.run_until_text("Hello", max_cycles=1_000_000)
        >>> print(emu.display_text)
        Hello World
    """

    def __init__(self, config: Optional[EmulatorConfig] = None):
        """
        Initialize the emulator with given configuration.

        Args:
            config: EmulatorConfig specifying model and ROM. If None,
                    defaults to XP (32KB) model with default ROM.

        Raises:
            ValueError: If model code is invalid
            FileNotFoundError: If ROM file cannot be found
        """
        self.config = config or EmulatorConfig()
        self._model = get_model(self.config.model)

        # Load ROM data
        # Priority: custom rom_path > default for model
        if self.config.rom_path:
            rom_path = self.config.rom_path
            if not rom_path.exists():
                raise FileNotFoundError(f"ROM file not found: {rom_path}")
            rom_data = rom_path.read_bytes()
        else:
            rom_path = get_rom_path(self._model.default_rom)
            rom_data = rom_path.read_bytes()

        # Initialize memory subsystem
        # Memory constructor: Memory(ram_size_kb: int, rom_data: Optional[bytes])
        self._memory = Memory(self._model.ram_kb, rom_data)

        # Initialize display controller
        # Display constructor: Display(num_lines: int)
        self.display = Display(self._model.display_lines)

        # Initialize keyboard
        self.keyboard = Keyboard()

        # Initialize pack slots (3 empty slots)
        self._packs: List[Pack] = [Pack(), Pack(), Pack()]

        # Initialize bus (connects CPU to all peripherals)
        # Bus constructor: Bus(memory, display, keyboard, packs)
        self.bus = Bus(self._memory, self.display, self.keyboard, self._packs)

        # Initialize CPU with bus
        self.cpu = HD6303(self.bus)

        # Initialize breakpoint manager
        self.breakpoints = BreakpointManager()

        # Connect CPU instruction hook to breakpoint manager
        # CRITICAL: The CPU hook signature is on_instruction(pc, opcode) -> bool
        # We wrap to pass CPU reference to breakpoints.check_instruction(cpu, pc, opcode)
        self.cpu.on_instruction = self._instruction_hook

        # Connect memory hooks to breakpoint manager for watchpoints
        self.cpu.on_memory_read = self._memory_read_hook
        self.cpu.on_memory_write = self._memory_write_hook

        # State tracking
        self._is_running = False
        self._total_cycles = 0

    def _instruction_hook(self, pc: int, opcode: int) -> bool:
        """
        Internal hook called before each CPU instruction.

        This connects the CPU's execution loop to the breakpoint manager.

        Args:
            pc: Current program counter value
            opcode: Opcode about to be executed

        Returns:
            True to continue execution, False to stop (breakpoint hit)
        """
        return self.breakpoints.check_instruction(self.cpu, pc, opcode)

    def _memory_read_hook(self, address: int, value: int) -> bool:
        """
        Internal hook called on memory read.

        This connects memory reads to the breakpoint manager for watchpoints.

        Args:
            address: Memory address being read
            value: Value read from memory

        Returns:
            True to continue execution, False to stop (watchpoint hit)
        """
        return self.breakpoints.check_memory_read(self.cpu, address, value)

    def _memory_write_hook(self, address: int, value: int) -> bool:
        """
        Internal hook called on memory write.

        This connects memory writes to the breakpoint manager for watchpoints.

        Args:
            address: Memory address being written
            value: Value being written

        Returns:
            True to continue execution, False to stop (watchpoint hit)
        """
        return self.breakpoints.check_memory_write(self.cpu, address, value)

    # =========================================================================
    # Program Loading
    # =========================================================================

    def load_opk(self, path: Union[str, Path], slot: int = 0) -> None:
        """
        Load an OPK pack file into a pack slot.

        The OPK format is the standard distribution format for Psion programs.
        After loading, the pack contents are available to the emulated system.

        Args:
            path: Path to the .opk file
            slot: Pack slot (0-2) to load into. Slot 0 is default.

        Raises:
            FileNotFoundError: If OPK file doesn't exist
            ValueError: If slot is out of range or OPK format is invalid
        """
        if not 0 <= slot <= 2:
            raise ValueError(f"Pack slot must be 0-2, got {slot}")

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"OPK file not found: {path}")

        pack = Pack.from_opk(path)
        self._packs[slot] = pack
        self.bus.set_pack(pack, slot)

    def load_bytes(self, data: bytes, address: int) -> None:
        """
        Load raw bytes directly into memory.

        This is useful for testing or injecting data without using OPK format.

        Args:
            data: Bytes to load
            address: Starting memory address

        Note:
            Writes to ROM addresses ($8000-$FFFF) will be silently ignored
            by the memory subsystem.
        """
        for i, byte in enumerate(data):
            self._memory.write(address + i, byte)

    def inject_program(self, code: bytes, entry_point: int = 0x2000) -> None:
        """
        Inject machine code directly and set PC to entry point.

        This bypasses normal program loading and is useful for testing
        small code snippets or unit testing specific instructions.

        Args:
            code: Machine code bytes to inject
            entry_point: Address to load code at and set PC to

        Example:
            >>> emu = Emulator()
            >>> emu.reset()
            >>> # Load a simple LDA #$42, RTS sequence
            >>> emu.inject_program(bytes([0x86, 0x42, 0x39]), entry_point=0x2000)
            >>> emu.run(100)
            >>> print(f"A = ${emu.cpu.a:02X}")  # A = $42
        """
        self.load_bytes(code, entry_point)
        self.cpu.pc = entry_point

    # =========================================================================
    # Execution Control
    # =========================================================================

    def reset(self) -> None:
        """
        Reset emulator to power-on state.

        This performs a full system reset:
        - CPU registers cleared
        - Display initialized and switched on
        - Bus timers reset
        - Cycle counter reset

        Call this before running a new program to ensure clean state.
        """
        self.cpu.reset()
        self.display.switch_on()
        self.bus.switch_on()
        self._memory.reset_bank()
        self._is_running = False
        self._total_cycles = 0
        self.breakpoints.clear_break_request()

    def step(self) -> BreakEvent:
        """
        Execute a single instruction.

        Returns immediately after executing one instruction, regardless
        of breakpoints.

        Returns:
            BreakEvent with reason=STEP and current PC

        Example:
            >>> emu.reset()
            >>> event = emu.step()
            >>> print(f"PC after step: ${emu.cpu.pc:04X}")
        """
        # Use CPU's step() method which bypasses hooks to execute exactly one instruction
        cycles = self.cpu.step()
        self._total_cycles += cycles

        # Return a step event
        return BreakEvent(
            BreakReason.STEP,
            address=self.cpu.pc,
            message=f"Step at ${self.cpu.pc:04X}"
        )

    def run(self, max_cycles: int = 1_000_000) -> BreakEvent:
        """
        Run until breakpoint or max cycles reached.

        Execution continues until:
        - A breakpoint or watchpoint is triggered
        - A register condition is met
        - max_cycles are consumed
        - The system is switched off

        Args:
            max_cycles: Maximum CPU cycles to execute

        Returns:
            BreakEvent describing why execution stopped

        Example:
            >>> emu.add_breakpoint(0x8100)
            >>> event = emu.run(1_000_000)
            >>> if event.reason == BreakReason.PC_BREAKPOINT:
            ...     print(f"Hit breakpoint at ${event.address:04X}")
        """
        self._is_running = True
        cycles = self.cpu.execute(max_cycles)
        self._total_cycles += cycles
        self._is_running = False

        # Return last event or max cycles reached
        return self.breakpoints.last_event or BreakEvent(
            BreakReason.MAX_CYCLES,
            message=f"Reached max cycles ({max_cycles})"
        )

    def run_until_pc(self, address: int, max_cycles: int = 10_000_000) -> bool:
        """
        Run until PC reaches a specific address.

        Creates a temporary breakpoint at the address and runs until hit.

        Args:
            address: 16-bit address to stop at
            max_cycles: Maximum cycles before giving up

        Returns:
            True if address was reached, False if max_cycles hit first

        Example:
            >>> # Run until program reaches exit routine
            >>> if emu.run_until_pc(0x8350):
            ...     print("Reached exit")
            ... else:
            ...     print("Timed out")
        """
        # Add temporary breakpoint
        was_set = self.breakpoints.has_breakpoint(address)
        if not was_set:
            self.breakpoints.add_breakpoint(address)

        try:
            event = self.run(max_cycles)
            return (event.reason == BreakReason.PC_BREAKPOINT and
                    event.address == address)
        finally:
            # Remove temporary breakpoint only if we added it
            if not was_set:
                self.breakpoints.remove_breakpoint(address)

    def run_until_text(
        self,
        text: str,
        max_cycles: int = 10_000_000,
        check_interval: int = 10000
    ) -> bool:
        """
        Run until display contains specified text.

        Periodically checks the display buffer for the target text.

        Args:
            text: Text to search for in display
            max_cycles: Maximum cycles before giving up
            check_interval: Cycles between display checks

        Returns:
            True if text was found, False if max_cycles hit first

        Example:
            >>> emu.load_opk("hello.opk")
            >>> if emu.run_until_text("Hello"):
            ...     print("Program displayed greeting")
        """
        cycles_executed = 0

        while cycles_executed < max_cycles:
            # Run for a short burst
            self.run(check_interval)
            cycles_executed += check_interval

            # Check display for target text
            if text in self.display_text:
                return True

        return False

    # =========================================================================
    # Breakpoint Management (delegates to BreakpointManager)
    # =========================================================================

    def add_breakpoint(self, address: int) -> None:
        """
        Add a PC breakpoint at the specified address.

        Execution will stop when PC reaches this address, before the
        instruction at that address is executed.

        Args:
            address: 16-bit memory address
        """
        self.breakpoints.add_breakpoint(address)

    def remove_breakpoint(self, address: int) -> None:
        """
        Remove a PC breakpoint at the specified address.

        Args:
            address: 16-bit memory address
        """
        self.breakpoints.remove_breakpoint(address)

    def add_watchpoint(
        self,
        address: int,
        on_write: bool = True,
        on_read: bool = False
    ) -> None:
        """
        Add a memory watchpoint at the specified address.

        Execution will stop when the address is read from or written to,
        depending on the flags.

        Args:
            address: 16-bit memory address
            on_write: Break on write (default True)
            on_read: Break on read (default False)
        """
        if on_read:
            self.breakpoints.add_read_watchpoint(address)
        if on_write:
            self.breakpoints.add_write_watchpoint(address)

    def clear_breakpoints(self) -> None:
        """Remove all breakpoints and watchpoints."""
        self.breakpoints.clear_all()

    # =========================================================================
    # Keyboard Input
    # =========================================================================

    def press_key(self, key: str) -> None:
        """
        Press a key (key down event).

        The key remains pressed until release_key() is called.

        Args:
            key: Key name (e.g., 'A', 'B', 'EXE', 'ON', '1', etc.)
        """
        self.keyboard.key_down(key)

    def release_key(self, key: str) -> None:
        """
        Release a key (key up event).

        Args:
            key: Key name that was previously pressed
        """
        self.keyboard.key_up(key)

    def tap_key(self, key: str, hold_cycles: int = 50000) -> None:
        """
        Tap a key (press, run, release).

        Simulates a brief key press. The key is pressed, emulation runs
        for hold_cycles, then the key is released.

        Args:
            key: Key name to tap
            hold_cycles: How long to hold the key (in CPU cycles)
        """
        self.press_key(key)
        self.run(hold_cycles)
        self.release_key(key)

    def type_text(self, text: str, delay_cycles: int = 10000) -> None:
        """
        Type a sequence of characters.

        Each character is tapped with a delay between characters to allow
        the system to process input.

        Args:
            text: Text to type (converted to uppercase)
            delay_cycles: Cycles to run between each character

        Note:
            Only characters that have corresponding keys will work.
            The text is automatically converted to uppercase since
            the Psion keyboard has no lowercase letters.
        """
        for char in text.upper():
            self.tap_key(char)
            self.run(delay_cycles)

    # =========================================================================
    # Display Output
    # =========================================================================

    @property
    def display_text(self) -> str:
        """
        Get current display content as a single string.

        Returns:
            All display lines concatenated into one string
        """
        return self.display.get_text()

    @property
    def display_lines(self) -> List[str]:
        """
        Get current display content as a list of lines.

        Returns:
            List of strings, one per display line
        """
        return self.display.get_text_grid()

    @property
    def display_pixels(self) -> bytes:
        """
        Get raw pixel buffer data.

        Returns:
            Raw pixel data bytes (5x8 pixels per character)
        """
        return self.display.get_pixel_buffer()

    def render_display(self, scale: int = 3, format: str = 'png') -> bytes:
        """
        Render display to an image.

        Args:
            scale: Pixel scaling factor (default 3)
            format: Image format ('png')

        Returns:
            Image data as bytes
        """
        return self.display.render_image(scale=scale, format=format)

    # =========================================================================
    # Memory Access
    # =========================================================================

    def read_byte(self, address: int) -> int:
        """
        Read a single byte from memory.

        Args:
            address: 16-bit memory address

        Returns:
            Byte value (0-255)
        """
        return self._memory.read(address)

    def read_word(self, address: int) -> int:
        """
        Read a 16-bit word from memory (big-endian).

        Args:
            address: 16-bit memory address

        Returns:
            16-bit word value
        """
        hi = self._memory.read(address)
        lo = self._memory.read(address + 1)
        return (hi << 8) | lo

    def read_bytes(self, address: int, count: int) -> bytes:
        """
        Read multiple bytes from memory.

        Args:
            address: Starting address
            count: Number of bytes to read

        Returns:
            Bytes object with the data
        """
        return bytes(self._memory.read(address + i) for i in range(count))

    def write_byte(self, address: int, value: int) -> None:
        """
        Write a single byte to memory.

        Args:
            address: 16-bit memory address
            value: Byte value to write
        """
        self._memory.write(address, value)

    def write_word(self, address: int, value: int) -> None:
        """
        Write a 16-bit word to memory (big-endian).

        Args:
            address: 16-bit memory address
            value: 16-bit word value
        """
        self._memory.write(address, (value >> 8) & 0xFF)
        self._memory.write(address + 1, value & 0xFF)

    def write_bytes(self, address: int, data: bytes) -> None:
        """
        Write multiple bytes to memory.

        Args:
            address: Starting address
            data: Bytes to write
        """
        for i, byte in enumerate(data):
            self._memory.write(address + i, byte)

    # =========================================================================
    # State Inspection
    # =========================================================================

    @property
    def model(self) -> PsionModel:
        """Get the Psion model configuration."""
        return self._model

    @property
    def registers(self) -> dict:
        """
        Get current CPU register values as a dictionary.

        Returns:
            Dictionary with keys: a, b, d, x, sp, pc, c, v, z, n, i, h
        """
        return {
            'a': self.cpu.a,
            'b': self.cpu.b,
            'd': self.cpu.d,
            'x': self.cpu.x,
            'sp': self.cpu.sp,
            'pc': self.cpu.pc,
            'c': self.cpu.flag_c,
            'v': self.cpu.flag_v,
            'z': self.cpu.flag_z,
            'n': self.cpu.flag_n,
            'i': self.cpu.flag_i,
            'h': self.cpu.flag_h,
        }

    @property
    def total_cycles(self) -> int:
        """
        Get total CPU cycles executed since last reset.

        Returns:
            Cumulative cycle count
        """
        return self._total_cycles

    @property
    def is_running(self) -> bool:
        """
        Check if emulator is currently running.

        Returns:
            True if in the middle of run(), False otherwise
        """
        return self._is_running

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def save_snapshot(self, path: Union[str, Path]) -> None:
        """
        Save complete emulator state to a file.

        The snapshot includes CPU registers, memory contents, display state,
        and all other component state needed to restore execution later.

        Args:
            path: Path to save snapshot file

        Note:
            Pack contents are NOT saved in the snapshot. To fully restore
            a session, you must also reload the same OPK files.
        """
        path = Path(path)

        # Build snapshot data
        data = bytearray()

        # Magic header 'SNA' + version byte
        data.extend(b'SNA\x01')

        # CPU state
        cpu_data = self.cpu.get_snapshot_data()
        data.extend(bytes(cpu_data))

        # Bus state
        bus_data = self.bus.get_snapshot_data()
        data.extend(bytes(bus_data))

        # Display state
        display_data = self.display.get_snapshot_data()
        data.extend(bytes(display_data))

        # Memory state (this can be large)
        mem_data = self._memory.get_snapshot_data()
        data.extend(bytes(mem_data))

        path.write_bytes(bytes(data))

    def load_snapshot(self, path: Union[str, Path]) -> None:
        """
        Load emulator state from a snapshot file.

        Restores complete emulator state as saved by save_snapshot().

        Args:
            path: Path to snapshot file

        Raises:
            ValueError: If snapshot format is invalid
            FileNotFoundError: If file doesn't exist

        Note:
            You should load the same ROM and OPK files before loading
            a snapshot for full compatibility.
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {path}")

        data = list(path.read_bytes())

        # Validate header
        if data[:4] != [ord('S'), ord('N'), ord('A'), 0x01]:
            raise ValueError("Invalid snapshot format (bad header)")

        # Restore each component
        offset = 4

        # CPU state
        offset += self.cpu.apply_snapshot_data(data, offset)

        # Bus state
        offset += self.bus.apply_snapshot_data(data, offset)

        # Display state
        offset += self.display.apply_snapshot_data(data, offset)

        # Memory state
        offset += self._memory.apply_snapshot_data(data, offset)

    # =========================================================================
    # Debug Helpers
    # =========================================================================

    def disassemble_at(self, address: int, count: int = 10) -> List[str]:
        """
        Disassemble instructions at the given address.

        This is a simple disassembler for debugging purposes.

        Args:
            address: Starting address
            count: Number of instructions to disassemble

        Returns:
            List of disassembly strings

        Note:
            This is a basic implementation. For full disassembly,
            use the psasm tool.
        """
        # Basic opcode to mnemonic mapping for common instructions
        # This is a simplified subset for debugging
        MNEMONICS = {
            0x01: ('NOP', 1),
            0x20: ('BRA', 2),
            0x39: ('RTS', 1),
            0x3B: ('RTI', 1),
            0x3E: ('WAI', 1),
            0x3F: ('SWI', 1),
            0x4F: ('CLRA', 1),
            0x5F: ('CLRB', 1),
            0x7E: ('JMP', 3),
            0x86: ('LDAA #', 2),
            0x8E: ('LDS #', 3),
            0xBD: ('JSR', 3),
            0xC6: ('LDAB #', 2),
            0xCE: ('LDX #', 3),
            0xDE: ('LDX', 2),
        }

        result = []
        addr = address

        for _ in range(count):
            opcode = self._memory.read(addr)

            if opcode in MNEMONICS:
                mnem, size = MNEMONICS[opcode]
                if size == 1:
                    result.append(f"${addr:04X}: {mnem}")
                elif size == 2:
                    operand = self._memory.read(addr + 1)
                    result.append(f"${addr:04X}: {mnem}${operand:02X}")
                else:
                    hi = self._memory.read(addr + 1)
                    lo = self._memory.read(addr + 2)
                    operand = (hi << 8) | lo
                    result.append(f"${addr:04X}: {mnem}${operand:04X}")
                addr += size
            else:
                result.append(f"${addr:04X}: ${opcode:02X}")
                addr += 1

        return result

    def __repr__(self) -> str:
        """Return string representation of emulator state."""
        return (
            f"Emulator(model={self._model.model_type}, "
            f"pc=${self.cpu.pc:04X}, "
            f"cycles={self._total_cycles})"
        )
