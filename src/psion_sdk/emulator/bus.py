"""
Memory Bus Controller for Psion Organiser II Emulator
======================================================

Ported from JAPE's bus.js to Python.

The Bus class is the central hub connecting CPU to all peripherals:
- Memory (RAM/ROM with bank switching)
- Display controller (LCD)
- Keyboard matrix
- Pack slots (datapaks/rampaks)
- Semi-custom chip (timers, buzzer, power control)
- Processor internal registers (ports, timers)

Memory Map:
    $0000-$003F  Processor internal registers
    $0040-$00FF  Processor RAM (zero page)
    $0100-$017F  Ignored
    $0180-$01BF  Display controller
    $01C0-$03FF  Semi-custom chip functions
    $0400-$7FFF  Main RAM
    $8000-$FFFF  ROM

Semi-custom chip addresses:
    $01C0: Switch off
    $0200: Enable 21V programming voltage
    $0240: Disable 21V programming voltage
    $0280: Buzzer on / set 21V onto pack
    $02C0: Buzzer off / set 5V onto pack
    $0300: Reset keyboard counter
    $0340: Increment keyboard counter
    $0360: Reset memory banks
    $0380: Enable NMI to processor
    $03A0: Next RAM bank
    $03C0: Enable NMI to counter
    $03E0: Next ROM bank

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import Memory
    from .display import Display
    from .keyboard import Keyboard
    from .pack import Pack


@dataclass
class BusState:
    """
    Complete bus controller state for snapshotting.
    """
    switched_off: bool = True  # System power state

    # Interrupt state
    oci_due: bool = False  # Output Compare Interrupt pending
    nmi_to_counter: bool = True  # NMI goes to counter (True) or CPU (False)
    ticks_since_nmi: int = 0  # Ticks since last NMI

    # Port 2 (data bus for packs)
    port2_proc: int = 0  # Value written by processor
    port2_actual: int = 0  # Current actual value
    port2_ddr: int = 0  # Data Direction Register (1=output)

    # Port 6 (pack control)
    port6_proc: int = 0
    port6_actual: int = 0
    port6_ddr: int = 0

    # Timer 1 (OCI interrupt)
    timer1_ocr: int = 0xFFFF  # Output Compare Register
    timer1_frc: int = 0  # Free Running Counter
    timer1_csr: int = 0  # Control/Status Register

    # Other
    port5_rcr: int = 0  # Port 5 Rate Control Register
    sca_alarm_high: bool = False  # Semi-custom alarm/buzzer state
    vpp21_charged: bool = False  # 21V programming voltage charged


class Bus:
    """
    Central bus controller for Psion Organiser II.

    Routes memory accesses between CPU and:
    - Main memory (RAM/ROM)
    - Display controller
    - Keyboard
    - Pack slots
    - Semi-custom chip functions

    Also manages:
    - Timer 1 for OCI interrupts
    - NMI generation and routing
    - Power on/off control

    The Bus implements the BusProtocol required by the CPU.

    Example:
        >>> bus = Bus(memory, display, keyboard)
        >>> bus.switch_on()
        >>> value = bus.read(0x8000)  # Read from ROM
        >>> bus.write(0x0400, 0x42)   # Write to RAM
    """

    # NMI timing: triggers every second (921600 ticks at 921.6 kHz)
    TICKS_PER_NMI = 921600 - 35  # Slight adjustment from JAPE

    def __init__(
        self,
        memory: "Memory",
        display: "Display",
        keyboard: "Keyboard",
        packs: Optional[List["Pack"]] = None
    ):
        """
        Initialize bus controller.

        Args:
            memory: Memory subsystem instance
            display: Display controller instance
            keyboard: Keyboard controller instance
            packs: List of 3 pack instances (or None for empty slots)
        """
        self._memory = memory
        self._display = display
        self._keyboard = keyboard

        # Initialize pack slots (3 slots, can be None for empty)
        if packs is None:
            from .pack import Pack
            self._packs: List["Pack"] = [Pack(), Pack(), Pack()]
        else:
            self._packs = packs

        # Initialize state
        self._state = BusState()

        # Callback for power on/off events
        self.on_switch_on_off: Optional[Callable[[bool], None]] = None

        # Initial setup
        self._display.switch_off()
        self._memory.reset_bank()

        # Connect keyboard to get key status from memory
        def get_key_stat() -> int:
            return self._memory.read(0x7B) & 0xFF
        self._keyboard.get_key_stat = get_key_stat

    @property
    def packs(self) -> List["Pack"]:
        """Access to pack slots."""
        return self._packs

    def set_pack(self, pack: "Pack", slot: int) -> None:
        """
        Install a pack in a slot.

        Args:
            pack: Pack instance to install
            slot: Slot number (0, 1, or 2)
        """
        if 0 <= slot <= 2 and self._packs[slot] is not pack:
            self._packs[slot] = pack

    def is_ready(self) -> bool:
        """Check if all components are ready."""
        return (
            self._memory.is_ready() and
            all(p.is_ready() for p in self._packs)
        )

    # =========================================================================
    # Power Control
    # =========================================================================

    def is_switched_off(self) -> bool:
        """Check if system is powered off."""
        return self._state.switched_off

    def switch_off(self) -> None:
        """Power off the system."""
        self._state.switched_off = True
        self._display.switch_off()
        if self.on_switch_on_off:
            self.on_switch_on_off(False)

    def switch_on(self) -> None:
        """Power on the system."""
        self._state.switched_off = False
        self._display.switch_on()
        if self.on_switch_on_off:
            self.on_switch_on_off(True)

    # =========================================================================
    # Memory Access (Main interface for CPU)
    # =========================================================================

    def read(self, address: int) -> int:
        """
        Read byte from memory/IO.

        Routes read to appropriate handler based on address:
        - $00-$3F: Processor internal registers
        - $40-$FF: Processor RAM (via memory)
        - $100-$3FF: Semi-custom chip / display
        - $400+: Main memory

        Args:
            address: 16-bit address

        Returns:
            Byte value (0-255)
        """
        address = address & 0xFFFF

        if address < 0x40:
            return self._processor_read(address)
        elif address < 0x100:
            return self._memory.read(address)
        elif address < 0x400:
            return self._semicustom(address, 0, write=False)
        else:
            return self._memory.read(address)

    def write(self, address: int, value: int) -> None:
        """
        Write byte to memory/IO.

        Routes write to appropriate handler based on address.

        Args:
            address: 16-bit address
            value: Byte value (0-255)
        """
        address = address & 0xFFFF
        value = value & 0xFF

        if address < 0x40:
            self._processor_write(address, value)
        elif address < 0x100:
            self._memory.write(address, value)
        elif address < 0x400:
            self._semicustom(address, value, write=True)
        else:
            self._memory.write(address, value)

    # =========================================================================
    # Processor Internal Registers
    # =========================================================================

    def _processor_read(self, address: int) -> int:
        """
        Read from processor internal register.

        Key registers:
        - $01: Port 2 DDR
        - $03: Port 2 data
        - $08: Timer 1 CSR
        - $09: Timer 1 FRC high
        - $0A: Timer 1 FRC low
        - $0B: Timer 1 OCR high
        - $0C: Timer 1 OCR low
        - $14: Port 5 RCR
        - $15: Port 5 (keyboard)
        - $16: Port 6 DDR
        - $17: Port 6 data
        """
        if address == 0x15:  # Port 5 - keyboard
            result = self._keyboard.read_port5()
            if self._state.vpp21_charged:
                result |= 0x02
            return result
        elif address == 0x17:  # Port 6 - pack control
            return self._state.port6_actual
        elif address == 0x16:  # Port 6 DDR
            return self._state.port6_ddr
        elif address == 0x01:  # Port 2 DDR
            return self._state.port2_ddr
        elif address == 0x03:  # Port 2
            self._read_port2()
            return self._state.port2_actual
        elif address == 0x14:  # Port 5 RCR
            return self._state.port5_rcr
        elif address == 0x08:  # Timer 1 CSR
            return self._state.timer1_csr
        elif address == 0x09:  # Timer 1 FRC high
            return (self._state.timer1_frc >> 8) & 0xFF
        elif address == 0x0A:  # Timer 1 FRC low
            return self._state.timer1_frc & 0xFF
        elif address == 0x0B:  # Timer 1 OCR high
            return (self._state.timer1_ocr >> 8) & 0xFF
        elif address == 0x0C:  # Timer 1 OCR low
            return self._state.timer1_ocr & 0xFF

        return 0

    def _processor_write(self, address: int, data: int) -> None:
        """Write to processor internal register."""
        if address == 0x17:  # Port 6 - pack control
            self._state.port6_proc = data
            new_p6 = ((self._state.port6_proc & self._state.port6_ddr) +
                      (self._state.port6_actual & (self._state.port6_ddr ^ 0xFF))) & 0xFF
            if new_p6 != self._state.port6_actual:
                self._state.port6_actual = new_p6
                self._write_port2_or_6()

        elif address == 0x16:  # Port 6 DDR
            if data != self._state.port6_ddr:
                self._state.port6_ddr = data
                self._write_port2_or_6()

        elif address == 0x01:  # Port 2 DDR
            if data != self._state.port2_ddr:
                self._state.port2_ddr = data
                new_p2 = ((self._state.port2_proc & self._state.port2_ddr) +
                          (self._state.port2_actual & (self._state.port2_ddr ^ 0xFF))) & 0xFF
                if self._state.port2_actual != new_p2:
                    self._state.port2_actual = new_p2
                self._write_port2_or_6()

        elif address == 0x03:  # Port 2
            self._state.port2_proc = data
            new_p2 = ((self._state.port2_proc & self._state.port2_ddr) +
                      (self._state.port2_actual & (self._state.port2_ddr ^ 0xFF))) & 0xFF
            if self._state.port2_actual != new_p2:
                self._state.port2_actual = new_p2
                self._write_port2_or_6()

        elif address == 0x14:  # Port 5 RCR
            self._state.port5_rcr = data

        elif address == 0x08:  # Timer 1 CSR
            self._state.timer1_csr = data

        elif address == 0x09:  # Timer 1 FRC high
            self._state.timer1_frc = (self._state.timer1_frc & 0xFF) | ((data & 0xFF) << 8)

        elif address == 0x0A:  # Timer 1 FRC low
            self._state.timer1_frc = (self._state.timer1_frc & 0xFF00) | (data & 0xFF)

        elif address == 0x0B:  # Timer 1 OCR high
            self._state.timer1_ocr = (self._state.timer1_ocr & 0xFF) | ((data & 0xFF) << 8)

        elif address == 0x0C:  # Timer 1 OCR low
            self._state.timer1_ocr = (self._state.timer1_ocr & 0xFF00) | (data & 0xFF)

    # =========================================================================
    # Semi-Custom Chip
    # =========================================================================

    def _semicustom(self, address: int, data: int, write: bool) -> int:
        """
        Handle semi-custom chip I/O.

        Address ranges:
        - $100-$17F: Ignored
        - $180-$1BF: Display controller
        - $1C0-$3FF: Semi-custom functions
        """
        if address < 0x180:
            # Ignored range
            return 0

        elif address < 0x1BF:
            # Display controller
            display_addr = address & 0x181

            if display_addr == 0x180:
                # Command register
                if write:
                    self._display.command(data)
                return 0
            else:
                # Data register
                if write:
                    self._display.set_data(data)
                    return 0
                return self._display.get_data()

        else:
            # Semi-custom functions (address bits 0-4 ignored)
            func_addr = address & 0xFFE0

            if func_addr == 0x01C0:  # Switch off
                self.switch_off()

            elif func_addr == 0x0200:  # Pulse enable (generate 21V)
                self._state.vpp21_charged = True

            elif func_addr == 0x0240:  # Pulse disable
                pass  # Just stops generating, but charge may remain

            elif func_addr == 0x0280:  # Buzzer on / set 21V onto pack
                self._state.sca_alarm_high = True

            elif func_addr == 0x02C0:  # Buzzer off / set 5V onto pack
                self._state.sca_alarm_high = False

            elif func_addr == 0x0300:  # Reset keyboard counter
                self._keyboard.reset_counter()

            elif func_addr == 0x0340:  # Increment keyboard counter
                self._keyboard.increment_counter()

            elif func_addr == 0x0360:  # Reset memory banks
                self._memory.reset_bank()

            elif func_addr == 0x0380:  # Enable NMI to processor
                self._state.nmi_to_counter = False

            elif func_addr == 0x03A0:  # Next RAM bank
                self._memory.next_ram()

            elif func_addr == 0x03C0:  # Enable NMI to counter
                self._state.nmi_to_counter = True

            elif func_addr == 0x03E0:  # Next ROM bank
                self._memory.next_rom()

        return 0

    # =========================================================================
    # Pack Port Handling
    # =========================================================================

    def _write_port2_or_6(self) -> None:
        """Handle changes to port 2 (data bus) or port 6 (control bus)."""
        from .pack import PackPin

        # Extract control lines from port 6
        control = self._state.port6_actual & 0x0F

        # Add special flags
        if (self._state.port2_ddr & 0xFF) != 0xFF:
            control |= PackPin.P2DDR
        if self._state.sca_alarm_high:
            control |= PackPin.SVPP
        if self._state.vpp21_charged:
            control |= PackPin.V21V

        wrote = False

        # Check if packs are powered down (bit 7 of port 6)
        if (self._state.port6_actual & 0x80) != 0 or (self._state.port6_ddr & 0x80) == 0:
            # Packs powered down - reset them
            self._packs[0].reset()
            self._packs[1].reset()
            self._packs[2].reset()
        else:
            # Check each pack slot
            # Slot 0 (bit 4)
            if ((self._state.port6_actual & 0x10) == 0 and
                    (self._state.port6_ddr & 0x10) != 0):
                wrote |= self._packs[0].write_control_port(control, self._state.port2_actual)

            # Slot 1 (bit 5)
            if ((self._state.port6_actual & 0x20) == 0 and
                    (self._state.port6_ddr & 0x20) != 0):
                wrote |= self._packs[1].write_control_port(control, self._state.port2_actual)

            # Slot 2/top slot (bit 6) - gets SPGM_B flag
            if ((self._state.port6_actual & 0x40) == 0 and
                    (self._state.port6_ddr & 0x40) != 0):
                wrote |= self._packs[2].write_control_port(
                    control | PackPin.SPGM_B, self._state.port2_actual)
            else:
                self._packs[2].reset()

        # Writing consumes the 21V charge
        if self._state.vpp21_charged and wrote:
            self._state.vpp21_charged = False

    def _read_port2(self) -> None:
        """Update port 2 value from pack data bus."""
        # Check if packs are powered up and port 2 has input bits
        if ((self._state.port6_actual & 0x80) == 0 and
                (self._state.port6_ddr & 0x80) != 0 and
                (self._state.port2_ddr & 0xFF) != 0xFF):

            result = 0

            # Read from each selected pack
            if ((self._state.port6_actual & 0x10) == 0 and
                    (self._state.port6_ddr & 0x10) != 0):
                result |= self._packs[0].read_data_bus()

            if ((self._state.port6_actual & 0x20) == 0 and
                    (self._state.port6_ddr & 0x20) != 0):
                result |= self._packs[1].read_data_bus()

            if ((self._state.port6_actual & 0x40) == 0 and
                    (self._state.port6_ddr & 0x40) != 0):
                result |= self._packs[2].read_data_bus()

            # Combine with output bits
            self._state.port2_actual = ((self._state.port2_proc & self._state.port2_ddr) +
                                        (result & (self._state.port2_ddr ^ 0xFF))) & 0xFF

    # =========================================================================
    # Timer and Interrupt Handling
    # =========================================================================

    def inc_frame(self, ticks: int) -> None:
        """
        Advance timing counters by specified ticks.

        Called by CPU after each instruction to track time for interrupts.

        Args:
            ticks: Number of CPU cycles elapsed
        """
        # Update Timer 1 FRC
        self._state.timer1_frc = (self._state.timer1_frc + ticks) & 0xFFFF

        # Check for OCI (Output Compare Interrupt)
        if self._state.timer1_frc >= self._state.timer1_ocr:
            self._state.oci_due = True
            self._state.timer1_frc = 0

        # Track ticks for NMI timing
        self._state.ticks_since_nmi += ticks

    def is_oci_due(self) -> bool:
        """
        Check if OCI interrupt is pending.

        Also handles power-on via ON/CLEAR key.

        Returns:
            True if OCI should be triggered
        """
        if not self._state.oci_due:
            return False

        self._state.oci_due = False

        # Check for power on via ON/CLEAR
        if self._state.switched_off and self._keyboard.is_on_pressed():
            self.switch_on()

        # Only trigger if enabled in CSR
        return (self._state.timer1_csr & 0x08) != 0

    def is_nmi_due(self) -> bool:
        """
        Check if NMI interrupt is pending.

        NMI occurs once per second (921600 ticks).
        Can go to CPU or keyboard counter depending on mode.

        Returns:
            True if NMI should be triggered to CPU
        """
        if self._state.ticks_since_nmi < self.TICKS_PER_NMI:
            return False

        self._state.ticks_since_nmi = 0

        if self._state.nmi_to_counter:
            # NMI goes to keyboard counter instead of CPU
            self._keyboard.increment_counter()
            if self._keyboard.counter_has_overflowed():
                self.switch_on()
            return False

        # NMI goes to CPU
        return True

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def get_snapshot_data(self) -> List[int]:
        """Get complete bus state for snapshot."""
        result = [
            1 if self._state.switched_off else 0,
            0,  # Unused byte (for compatibility)
            1 if self._state.oci_due else 0,
            1 if self._state.nmi_to_counter else 0,
            1 if self._state.sca_alarm_high else 0,
            1 if self._state.vpp21_charged else 0,
            self._state.port2_proc,
            self._state.port2_actual,
            self._state.port2_ddr,
            self._state.port6_proc,
            self._state.port6_actual,
            self._state.port6_ddr,
            self._state.port5_rcr,
            (self._state.timer1_ocr >> 8) & 0xFF,
            self._state.timer1_ocr & 0xFF,
            (self._state.timer1_frc >> 8) & 0xFF,
            self._state.timer1_frc & 0xFF,
            self._state.timer1_csr,
            (self._state.ticks_since_nmi >> 16) & 0xFF,
            (self._state.ticks_since_nmi >> 8) & 0xFF,
            self._state.ticks_since_nmi & 0xFF,
        ]
        return result

    def apply_snapshot_data(self, data: List[int], offset: int = 0) -> int:
        """Restore bus state from snapshot."""
        self._state.switched_off = data[offset] != 0
        # data[offset + 1] is unused
        self._state.oci_due = data[offset + 2] != 0
        self._state.nmi_to_counter = data[offset + 3] != 0
        self._state.sca_alarm_high = data[offset + 4] != 0
        self._state.vpp21_charged = data[offset + 5] != 0
        self._state.port2_proc = data[offset + 6]
        self._state.port2_actual = data[offset + 7]
        self._state.port2_ddr = data[offset + 8]
        self._state.port6_proc = data[offset + 9]
        self._state.port6_actual = data[offset + 10]
        self._state.port6_ddr = data[offset + 11]
        self._state.port5_rcr = data[offset + 12]
        self._state.timer1_ocr = (data[offset + 13] << 8) | data[offset + 14]
        self._state.timer1_frc = (data[offset + 15] << 8) | data[offset + 16]
        self._state.timer1_csr = data[offset + 17]
        self._state.ticks_since_nmi = (
            (data[offset + 18] << 16) |
            (data[offset + 19] << 8) |
            data[offset + 20]
        )
        return 21
