"""
HD6303 CPU Emulator
===================

Faithful port of JAPE's hd6303.js to Python with instrumentation hooks.

The HD6303 is a Hitachi derivative of the Motorola 6801/6803 with:
- 8-bit registers: A, B (combined as 16-bit D)
- 16-bit registers: X (index), SP (stack pointer), PC (program counter)
- Flags: H (half-carry), I (interrupt), N (negative), Z (zero), V (overflow), C (carry)

Key differences from 6800:
- TSX gives X=SP directly (not X=SP+1)
- Additional instructions: XGDX, SLP, AIM, OIM, EIM, TIM
- 16-bit operations: SUBD, ADDD, LDD, STD

All instruction timing and flag behavior matches JAPE exactly.

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Callable, Optional, Protocol


class Flags(IntFlag):
    """
    CPU condition code (CC) flags.

    Bit layout of CC register:
        7  6  5  4  3  2  1  0
        1  1  H  I  N  Z  V  C

    Bits 7 and 6 are always 1 when read via TPA instruction.
    """
    C = 0x01  # Carry/Borrow
    V = 0x02  # Overflow
    Z = 0x04  # Zero
    N = 0x08  # Negative
    I = 0x10  # Interrupt mask (1=disabled)
    H = 0x20  # Half-carry (for BCD)


class BusProtocol(Protocol):
    """
    Protocol defining the memory bus interface.

    The CPU interacts with memory and I/O through this interface.
    """
    def read(self, address: int) -> int:
        """Read byte from address."""
        ...

    def write(self, address: int, value: int) -> None:
        """Write byte to address."""
        ...

    def is_nmi_due(self) -> bool:
        """Check if NMI interrupt is pending."""
        ...

    def is_oci_due(self) -> bool:
        """Check if Output Compare Interrupt is pending."""
        ...

    def inc_frame(self, ticks: int) -> None:
        """Advance bus timing counters."""
        ...

    def is_switched_off(self) -> bool:
        """Check if system is powered off."""
        ...


@dataclass
class CPUState:
    """
    Complete CPU state for snapshotting.

    All values stored as Python ints but represent:
    - A, B: 8-bit unsigned (0-255)
    - X, SP, PC: 16-bit unsigned (0-65535)
    - flags: 8-bit flag register
    - sleep: boolean (CPU in sleep mode)
    """
    a: int = 0
    b: int = 0
    x: int = 0
    sp: int = 0
    pc: int = 0
    flags: int = 0xFF  # All flags set on reset (matches JAPE)
    sleep: bool = False


class HD6303:
    """
    HD6303 CPU emulator with instrumentation support.

    This is a direct port of JAPE's hd6303.js maintaining:
    - Exact instruction timing (cycle counts)
    - Precise flag behavior for all operations
    - Interrupt handling (NMI, OCI)
    - Sleep mode behavior

    Instrumentation hooks allow:
    - Tracing every instruction before execution
    - Monitoring all memory reads/writes
    - Implementing breakpoints and watchpoints

    Example:
        >>> cpu = HD6303(bus)
        >>> cpu.reset()
        >>> cycles = cpu.execute(1000)  # Run for 1000 cycles
        >>> print(f"A=${cpu.a:02X} B=${cpu.b:02X} PC=${cpu.pc:04X}")
    """

    def __init__(self, bus: BusProtocol):
        """
        Initialize CPU with memory bus.

        Args:
            bus: Memory bus implementing BusProtocol
        """
        self.bus = bus
        self.state = CPUState()

        # Instrumentation hooks
        # on_instruction(pc, opcode) -> bool: return False to stop execution
        self.on_instruction: Optional[Callable[[int, int], bool]] = None
        # on_memory_read(address, value) -> bool: return False to stop execution
        self.on_memory_read: Optional[Callable[[int, int], bool]] = None
        # on_memory_write(address, value) -> bool: return False to stop execution
        self.on_memory_write: Optional[Callable[[int, int], bool]] = None

        # Flag set by memory hooks to request execution stop
        self._memory_break_requested: bool = False

    # ========================================
    # Register Properties (match JAPE naming)
    # ========================================

    @property
    def a(self) -> int:
        """Accumulator A (8-bit)."""
        return self.state.a

    @a.setter
    def a(self, value: int) -> None:
        self.state.a = value & 0xFF

    @property
    def b(self) -> int:
        """Accumulator B (8-bit)."""
        return self.state.b

    @b.setter
    def b(self, value: int) -> None:
        self.state.b = value & 0xFF

    @property
    def d(self) -> int:
        """Combined D register (A:B, 16-bit). A is high byte."""
        return (self.state.a << 8) | self.state.b

    @d.setter
    def d(self, value: int) -> None:
        self.state.a = (value >> 8) & 0xFF
        self.state.b = value & 0xFF

    @property
    def x(self) -> int:
        """Index register X (16-bit)."""
        return self.state.x

    @x.setter
    def x(self, value: int) -> None:
        self.state.x = value & 0xFFFF

    @property
    def sp(self) -> int:
        """Stack pointer (16-bit)."""
        return self.state.sp

    @sp.setter
    def sp(self, value: int) -> None:
        self.state.sp = value & 0xFFFF

    @property
    def pc(self) -> int:
        """Program counter (16-bit)."""
        return self.state.pc

    @pc.setter
    def pc(self, value: int) -> None:
        self.state.pc = value & 0xFFFF

    # ========================================
    # Flag Properties
    # ========================================

    @property
    def flag_c(self) -> bool:
        """Carry flag."""
        return bool(self.state.flags & Flags.C)

    @flag_c.setter
    def flag_c(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.C
        else:
            self.state.flags &= ~Flags.C

    @property
    def flag_v(self) -> bool:
        """Overflow flag."""
        return bool(self.state.flags & Flags.V)

    @flag_v.setter
    def flag_v(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.V
        else:
            self.state.flags &= ~Flags.V

    @property
    def flag_z(self) -> bool:
        """Zero flag."""
        return bool(self.state.flags & Flags.Z)

    @flag_z.setter
    def flag_z(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.Z
        else:
            self.state.flags &= ~Flags.Z

    @property
    def flag_n(self) -> bool:
        """Negative flag."""
        return bool(self.state.flags & Flags.N)

    @flag_n.setter
    def flag_n(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.N
        else:
            self.state.flags &= ~Flags.N

    @property
    def flag_i(self) -> bool:
        """Interrupt mask flag."""
        return bool(self.state.flags & Flags.I)

    @flag_i.setter
    def flag_i(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.I
        else:
            self.state.flags &= ~Flags.I

    @property
    def flag_h(self) -> bool:
        """Half-carry flag."""
        return bool(self.state.flags & Flags.H)

    @flag_h.setter
    def flag_h(self, value: bool) -> None:
        if value:
            self.state.flags |= Flags.H
        else:
            self.state.flags &= ~Flags.H

    def _get_p(self) -> int:
        """Get processor status byte (flags with bits 6,7 set)."""
        return self.state.flags | 0xC0

    def _set_p(self, value: int) -> None:
        """Set processor status byte."""
        self.state.flags = value & 0x3F

    # ========================================
    # Memory Access
    # ========================================

    def _read_byte(self, addr: int) -> int:
        """Read byte from bus with optional watchpoint check."""
        value = self.bus.read(addr & 0xFFFF) & 0xFF
        if self.on_memory_read:
            if not self.on_memory_read(addr & 0xFFFF, value):
                self._memory_break_requested = True
        return value

    def _write_byte(self, addr: int, value: int) -> None:
        """Write byte to bus with optional watchpoint check."""
        addr = addr & 0xFFFF
        value = value & 0xFF
        if self.on_memory_write:
            if not self.on_memory_write(addr, value):
                self._memory_break_requested = True
        self.bus.write(addr, value)

    def _read_word(self, addr: int) -> int:
        """Read 16-bit word from bus (big-endian)."""
        hi = self._read_byte(addr)
        lo = self._read_byte(addr + 1)
        return (hi << 8) | lo

    def _write_word(self, addr: int, value: int) -> None:
        """Write 16-bit word to bus (big-endian)."""
        self._write_byte(addr, (value >> 8) & 0xFF)
        self._write_byte(addr + 1, value & 0xFF)

    # ========================================
    # Stack Operations
    # ========================================

    def _push_byte(self, value: int) -> None:
        """Push byte onto stack (pre-decrement)."""
        self.sp = (self.sp - 1) & 0xFFFF
        self._write_byte(self.sp, value)

    def _pop_byte(self) -> int:
        """Pop byte from stack (post-increment)."""
        value = self._read_byte(self.sp)
        self.sp = (self.sp + 1) & 0xFFFF
        return value

    def _push_word(self, value: int) -> None:
        """Push word onto stack (high byte at lower address)."""
        self.sp = (self.sp - 2) & 0xFFFF
        self._write_word(self.sp, value)

    def _pop_word(self) -> int:
        """Pop word from stack."""
        value = self._read_word(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return value

    # ========================================
    # Program Counter Operations
    # ========================================

    def _fetch_byte(self) -> int:
        """Fetch next byte at PC and increment PC."""
        value = self._read_byte(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value

    def _fetch_word(self) -> int:
        """Fetch next word at PC and increment PC by 2."""
        value = self._read_word(self.pc)
        self.pc = (self.pc + 2) & 0xFFFF
        return value

    # ========================================
    # Reset and Interrupts
    # ========================================

    def reset(self) -> None:
        """
        Reset CPU to power-on state.

        Loads PC from reset vector at $FFFE-$FFFF.
        Sets all flags high, clears registers.
        """
        self.pc = self._read_word(0xFFFE)
        self.sp = 0
        self.d = 0
        self.x = 0
        self.state.flags = 0xFF  # All flags set (matches JAPE setP(255))
        self.state.sleep = False

    def on_switch_on_off(self) -> None:
        """Handle power on/off event from bus."""
        if self.bus.is_switched_off():
            self.state.sleep = True
        else:
            self.reset()

    def _do_interrupt(self, vector: int) -> int:
        """
        Handle interrupt: push state, load vector, set I flag.

        Stack layout (pushed in order):
            PCL, PCH, XL, XH, A, B, P

        Args:
            vector: Memory address of interrupt vector

        Returns:
            Number of cycles consumed (11)
        """
        self._push_word(self.pc)
        self._push_word(self.x)
        self._push_byte(self.a)
        self._push_byte(self.b)
        self._push_byte(self._get_p())
        self.flag_i = True
        self.pc = self._read_word(vector)
        return 11

    # ========================================
    # Main Execution Loop
    # ========================================

    def execute(self, ticks_to_execute: int) -> int:
        """
        Execute instructions for specified number of cycles.

        This is the main emulation entry point matching JAPE's execute().

        Args:
            ticks_to_execute: Maximum number of CPU cycles to execute

        Returns:
            Actual number of cycles executed

        Note:
            Execution may stop early if:
            - A breakpoint is hit (on_instruction returns False)
            - CPU enters sleep mode
            - Stack error detected
        """
        total_ticks = 0

        while ticks_to_execute > 0:
            ticks = 0

            # Check for NMI
            if self.bus.is_nmi_due():
                ticks += self._do_interrupt(0xFFFC)
                self.state.sleep = False

            # Check for OCI (Output Compare Interrupt)
            if self.bus.is_oci_due() and not self.flag_i:
                ticks += self._do_interrupt(0xFFF4)
                self.state.sleep = False

            # Stack error detection (same as JAPE line 185-188)
            sp = self.sp
            if (sp > 0 and sp < 0x00E0) or (sp >= 0x100 and sp < 0x400) or sp > 0x8000:
                raise RuntimeError(f"Stack error: SP=${sp:04X}")

            # Fetch instruction
            if self.state.sleep or self.bus.is_switched_off():
                inst = 1  # NOP when sleeping
            else:
                # Call instruction hook if set
                if self.on_instruction:
                    next_inst = self._read_byte(self.pc)
                    if not self.on_instruction(self.pc, next_inst):
                        # Hook returned False - stop execution (breakpoint hit)
                        return total_ticks

                inst = self._fetch_byte()

            ticks += 1
            ticks += self._execute_instruction(inst)

            # Check if a memory watchpoint was triggered
            if self._memory_break_requested:
                self._memory_break_requested = False
                self.bus.inc_frame(ticks)
                return total_ticks + ticks

            # Update bus timing
            self.bus.inc_frame(ticks)

            ticks_to_execute -= ticks
            total_ticks += ticks

        return total_ticks

    def step(self) -> int:
        """
        Execute exactly one instruction.

        Returns:
            Number of cycles consumed by the instruction
        """
        # Temporarily disable instruction hook to ensure we execute one instruction
        saved_hook = self.on_instruction
        self.on_instruction = None

        try:
            # Execute minimal cycles - will complete one instruction
            return self.execute(1)
        finally:
            self.on_instruction = saved_hook

    # ========================================
    # ALU Operations (match JAPE exactly)
    # ========================================

    def _ld8(self, value: int) -> int:
        """Load 8-bit value, set N,Z flags, clear V."""
        self.flag_n = (value & 0x80) != 0
        self.flag_z = value == 0
        self.flag_v = False
        return value

    def _ld16(self, value: int) -> int:
        """Load 16-bit value, set N,Z flags, clear V."""
        self.flag_n = (value & 0x8000) != 0
        self.flag_z = value == 0
        self.flag_v = False
        return value

    def _add8(self, a: int, b: int) -> int:
        """Add 8-bit values, set H,N,Z,C,V flags."""
        result = a + b
        self.flag_h = ((a & 0x0F) + (b & 0x0F)) >= 0x10
        self.flag_n = (result & 0x80) != 0
        self.flag_z = (result & 0xFF) == 0
        self.flag_c = (result & 0x100) != 0
        # Overflow: same sign inputs, different sign result
        self.flag_v = ((a ^ ~b) & (a ^ result) & 0x80) != 0
        return result & 0xFF

    def _adc8(self, a: int, b: int) -> int:
        """Add 8-bit values with carry, set H,N,Z,C,V flags."""
        c = 1 if self.flag_c else 0
        result = a + b + c
        self.flag_h = ((a & 0x0F) + (b & 0x0F) + c) >= 0x10
        self.flag_n = (result & 0x80) != 0
        self.flag_z = (result & 0xFF) == 0
        self.flag_c = (result & 0x100) != 0
        self.flag_v = ((a ^ ~b) & (a ^ result) & 0x80) != 0
        return result & 0xFF

    def _sub8(self, a: int, b: int) -> int:
        """Subtract 8-bit values, set N,Z,C,V flags."""
        result = a - b
        self.flag_n = (result & 0x80) != 0
        self.flag_z = (result & 0xFF) == 0
        self.flag_c = (result & 0x100) != 0
        # Overflow: different sign inputs, result sign differs from a
        self.flag_v = ((a ^ b) & (a ^ result) & 0x80) != 0
        return result & 0xFF

    def _sbc8(self, a: int, b: int) -> int:
        """Subtract 8-bit values with carry, set N,Z,C,V flags."""
        b2 = b + (1 if self.flag_c else 0)
        result = a - b2
        self.flag_n = (result & 0x80) != 0
        self.flag_z = (result & 0xFF) == 0
        self.flag_c = (result & 0x100) != 0
        self.flag_v = ((a ^ b2) & (a ^ result) & 0x80) != 0
        return result & 0xFF

    def _add16(self, a: int, b: int) -> int:
        """Add 16-bit values, set N,Z,C,V flags."""
        result = a + b
        self.flag_n = (result & 0x8000) != 0
        self.flag_z = (result & 0xFFFF) == 0
        self.flag_c = (result & 0x10000) != 0
        self.flag_v = ((a ^ ~b) & (a ^ result) & 0x8000) != 0
        return result & 0xFFFF

    def _sub16(self, a: int, b: int) -> int:
        """Subtract 16-bit values, set N,Z,C,V flags."""
        result = a - b
        self.flag_n = (result & 0x8000) != 0
        self.flag_z = (result & 0xFFFF) == 0
        self.flag_c = (result & 0x10000) != 0
        self.flag_v = ((a ^ b) & (a ^ result) & 0x8000) != 0
        return result & 0xFFFF

    def _neg8(self, value: int) -> int:
        """Negate 8-bit value, set N,Z,C,V flags."""
        result = (-value) & 0xFF
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        self.flag_c = result != 0
        self.flag_v = result == 0x80
        return result

    def _com8(self, value: int) -> int:
        """Complement 8-bit value, set N,Z,C,V flags."""
        result = value ^ 0xFF
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        self.flag_v = False
        self.flag_c = True
        return result

    def _lsr8(self, value: int) -> int:
        """Logical shift right 8-bit, set N,Z,C,V flags."""
        c = (value & 1) != 0
        self.flag_c = c
        self.flag_v = c
        result = value >> 1
        self.flag_n = False
        self.flag_z = result == 0
        return result

    def _ror8(self, value: int) -> int:
        """Rotate right 8-bit through carry, set N,Z,C,V flags."""
        c = (value & 1) != 0
        n = self.flag_c
        result = value >> 1
        if n:
            result |= 0x80
        self.flag_c = c
        self.flag_n = n
        self.flag_z = result == 0
        self.flag_v = n != c
        return result

    def _asr8(self, value: int) -> int:
        """Arithmetic shift right 8-bit (preserve sign), set N,Z,C,V flags."""
        c = (value & 1) != 0
        msb = value & 0x80
        n = msb != 0
        self.flag_c = c
        result = (value >> 1) + msb
        self.flag_n = n
        self.flag_z = result == 0
        self.flag_v = n != c
        return result

    def _asl8(self, value: int) -> int:
        """Arithmetic shift left 8-bit, set N,Z,C,V flags."""
        c = (value & 0x80) != 0
        result = (value << 1) & 0xFF
        n = (result & 0x80) != 0
        self.flag_n = n
        self.flag_z = result == 0
        self.flag_c = c
        self.flag_v = n != c
        return result

    def _asl16(self, value: int) -> int:
        """Arithmetic shift left 16-bit, set N,Z,C,V flags."""
        c = (value & 0x8000) != 0
        result = (value << 1) & 0xFFFF
        n = (result & 0x8000) != 0
        self.flag_n = n
        self.flag_z = result == 0
        self.flag_c = c
        self.flag_v = n != c
        return result

    def _rol8(self, value: int) -> int:
        """Rotate left 8-bit through carry, set N,Z,C,V flags."""
        c = (value & 0x80) != 0
        result = (value << 1) & 0xFF
        n = (result & 0x80) != 0
        if self.flag_c:
            result += 1
        self.flag_c = c
        self.flag_n = n
        self.flag_z = result == 0
        self.flag_v = n != c
        return result

    def _dec8(self, value: int) -> int:
        """Decrement 8-bit value, set N,Z,V flags."""
        self.flag_v = value == 0x80
        result = (value - 1) & 0xFF
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        return result

    def _inc8(self, value: int) -> int:
        """Increment 8-bit value, set N,Z,V flags."""
        result = (value + 1) & 0xFF
        self.flag_v = result == 0x80
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        return result

    def _tst8(self, value: int) -> None:
        """Test 8-bit value, set N,Z,V,C flags."""
        self.flag_v = False
        self.flag_c = False
        self.flag_n = (value & 0x80) != 0
        self.flag_z = value == 0

    def _clr8(self) -> int:
        """Clear (return 0), set N,Z,V,C flags."""
        self.flag_v = False
        self.flag_c = False
        self.flag_n = False
        self.flag_z = True
        return 0

    def _and8(self, a: int, b: int) -> int:
        """AND 8-bit values, set N,Z,V flags."""
        result = a & b
        self.flag_v = False
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        return result

    def _or8(self, a: int, b: int) -> int:
        """OR 8-bit values, set N,Z,V flags."""
        result = a | b
        self.flag_v = False
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        return result

    def _eor8(self, a: int, b: int) -> int:
        """XOR 8-bit values, set N,Z,V flags."""
        result = a ^ b
        self.flag_v = False
        self.flag_n = (result & 0x80) != 0
        self.flag_z = result == 0
        return result

    def _daa(self) -> None:
        """
        Decimal Adjust Accumulator.

        Adjusts A register after BCD addition. Sets N,Z,C,V flags.
        """
        ans = self.a
        if self.flag_h:
            ans += 0x06
        if (ans & 0x0F) > 0x09:
            ans += 0x06
        if self.flag_c:
            ans += 0x60
        if ans > 0x9F:
            ans += 0x60
        if ans > 0x99:
            self.flag_c = True

        self.flag_n = (ans & 0x80) != 0
        self.flag_z = (ans & 0xFF) == 0
        self.flag_v = ((self.a ^ ans) & 0x80) != 0
        self.a = ans & 0xFF

    # ========================================
    # Instruction Execution (ported from JAPE)
    # ========================================

    def _execute_instruction(self, opcode: int) -> int:
        """
        Execute a single instruction.

        This is a direct port of JAPE's switch statement in execute().
        Each case returns the additional cycles consumed (beyond the
        initial fetch cycle).

        Args:
            opcode: The instruction opcode byte

        Returns:
            Additional cycles consumed (not including fetch)
        """
        match opcode:
            # ============================================
            # Control Instructions (0x00-0x0F)
            # ============================================
            case 0x00:  # TRAP
                return self._do_interrupt(0xFFEE)
            case 0x01:  # NOP
                return 0
            case 0x04:  # LSRD
                self.d = self._lsr8(self.d)  # Note: JAPE uses lsr which handles 16-bit
                return 0
            case 0x05:  # ASLD
                self.d = self._asl16(self.d)
                return 0
            case 0x06:  # TAP
                self._set_p(self.a)
                return 0
            case 0x07:  # TPA
                self.a = self._get_p()
                return 0
            case 0x08:  # INX
                self.x = (self.x + 1) & 0xFFFF
                self.flag_z = self.x == 0
                return 0
            case 0x09:  # DEX
                self.x = (self.x - 1) & 0xFFFF
                self.flag_z = self.x == 0
                return 0
            case 0x0A:  # CLV
                self.flag_v = False
                return 0
            case 0x0B:  # SEV
                self.flag_v = True
                return 0
            case 0x0C:  # CLC
                self.flag_c = False
                return 0
            case 0x0D:  # SEC
                self.flag_c = True
                return 0
            case 0x0E:  # CLI
                self.flag_i = False
                return 0
            case 0x0F:  # SEI
                self.flag_i = True
                return 0

            # ============================================
            # Register Transfer (0x10-0x1B)
            # ============================================
            case 0x10:  # SBA
                self.a = self._sub8(self.a, self.b)
                return 0
            case 0x11:  # CBA
                self._sub8(self.a, self.b)
                return 0
            case 0x16:  # TAB
                self.b = self._ld8(self.a)
                return 0
            case 0x17:  # TBA
                self.a = self._ld8(self.b)
                return 0
            case 0x18:  # XGDX (HD6303 specific)
                tmp = self.x
                self.x = self.d
                self.d = tmp
                return 1
            case 0x19:  # DAA
                self._daa()
                return 1
            case 0x1A:  # SLP (HD6303 specific)
                self.state.sleep = True
                return 3
            case 0x1B:  # ABA
                self.a = self._add8(self.a, self.b)
                return 0

            # ============================================
            # Branch Instructions (0x20-0x2F)
            # ============================================
            case 0x20:  # BRA
                d = self._fetch_byte()
                if d >= 0x80:
                    d -= 0x100
                self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x21:  # BRN
                self._fetch_byte()  # Consume offset but don't branch
                return 2
            case 0x22:  # BHI (C=0 and Z=0)
                d = self._fetch_byte()
                if not self.flag_c and not self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x23:  # BLS (C=1 or Z=1)
                d = self._fetch_byte()
                if self.flag_c or self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x24:  # BCC/BHS (C=0)
                d = self._fetch_byte()
                if not self.flag_c:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x25:  # BCS/BLO (C=1)
                d = self._fetch_byte()
                if self.flag_c:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x26:  # BNE (Z=0)
                d = self._fetch_byte()
                if not self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x27:  # BEQ (Z=1)
                d = self._fetch_byte()
                if self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x28:  # BVC (V=0)
                d = self._fetch_byte()
                if not self.flag_v:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x29:  # BVS (V=1)
                d = self._fetch_byte()
                if self.flag_v:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2A:  # BPL (N=0)
                d = self._fetch_byte()
                if not self.flag_n:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2B:  # BMI (N=1)
                d = self._fetch_byte()
                if self.flag_n:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2C:  # BGE (N=V)
                d = self._fetch_byte()
                if self.flag_n == self.flag_v:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2D:  # BLT (N!=V)
                d = self._fetch_byte()
                if self.flag_n != self.flag_v:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2E:  # BGT (N=V and Z=0)
                d = self._fetch_byte()
                if self.flag_n == self.flag_v and not self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2
            case 0x2F:  # BLE (N!=V or Z=1)
                d = self._fetch_byte()
                if self.flag_n != self.flag_v or self.flag_z:
                    if d >= 0x80:
                        d -= 0x100
                    self.pc = (self.pc + d) & 0xFFFF
                return 2

            # ============================================
            # Stack/Transfer (0x30-0x3F)
            # ============================================
            case 0x30:  # TSX (HD6303: X = SP directly)
                self.x = self.sp
                return 0
            case 0x31:  # INS
                self.sp = (self.sp + 1) & 0xFFFF
                return 0
            case 0x32:  # PULA
                self.a = self._pop_byte()
                return 2
            case 0x33:  # PULB
                self.b = self._pop_byte()
                return 2
            case 0x34:  # DES
                self.sp = (self.sp - 1) & 0xFFFF
                return 0
            case 0x35:  # TXS
                self.sp = self.x
                return 0
            case 0x36:  # PSHA
                self._push_byte(self.a)
                return 3
            case 0x37:  # PSHB
                self._push_byte(self.b)
                return 3
            case 0x38:  # PULX
                self.x = self._pop_word()
                return 3
            case 0x39:  # RTS
                self.pc = self._pop_word()
                return 4
            case 0x3A:  # ABX
                self.x = (self.x + self.b) & 0xFFFF
                return 0
            case 0x3B:  # RTI
                self._set_p(self._pop_byte())
                self.b = self._pop_byte()
                self.a = self._pop_byte()
                self.x = self._pop_word()
                self.pc = self._pop_word()
                return 9
            case 0x3C:  # PSHX
                self._push_word(self.x)
                return 4
            case 0x3D:  # MUL
                self.d = self.a * self.b
                self.flag_c = (self.b & 0x80) != 0
                return 6
            case 0x3E:  # WAI
                return 8
            case 0x3F:  # SWI
                return self._do_interrupt(0xFFFA)

            # ============================================
            # Accumulator A Operations (0x40-0x4F)
            # ============================================
            case 0x40:  # NEGA
                self.a = self._neg8(self.a)
                return 0
            case 0x43:  # COMA
                self.a = self._com8(self.a)
                return 0
            case 0x44:  # LSRA
                self.a = self._lsr8(self.a)
                return 0
            case 0x46:  # RORA
                self.a = self._ror8(self.a)
                return 0
            case 0x47:  # ASRA
                self.a = self._asr8(self.a)
                return 0
            case 0x48:  # ASLA
                self.a = self._asl8(self.a)
                return 0
            case 0x49:  # ROLA
                self.a = self._rol8(self.a)
                return 0
            case 0x4A:  # DECA
                self.a = self._dec8(self.a)
                return 0
            case 0x4C:  # INCA
                self.a = self._inc8(self.a)
                return 0
            case 0x4D:  # TSTA
                self._tst8(self.a)
                return 0
            case 0x4F:  # CLRA
                self.a = self._clr8()
                return 0

            # ============================================
            # Accumulator B Operations (0x50-0x5F)
            # ============================================
            case 0x50:  # NEGB
                self.b = self._neg8(self.b)
                return 0
            case 0x53:  # COMB
                self.b = self._com8(self.b)
                return 0
            case 0x54:  # LSRB
                self.b = self._lsr8(self.b)
                return 0
            case 0x56:  # RORB
                self.b = self._ror8(self.b)
                return 0
            case 0x57:  # ASRB
                self.b = self._asr8(self.b)
                return 0
            case 0x58:  # ASLB
                self.b = self._asl8(self.b)
                return 0
            case 0x59:  # ROLB
                self.b = self._rol8(self.b)
                return 0
            case 0x5A:  # DECB
                self.b = self._dec8(self.b)
                return 0
            case 0x5C:  # INCB
                self.b = self._inc8(self.b)
                return 0
            case 0x5D:  # TSTB
                self._tst8(self.b)
                return 0
            case 0x5F:  # CLRB
                self.b = self._clr8()
                return 0

            # ============================================
            # Indexed Operations (0x60-0x6F)
            # ============================================
            case 0x60:  # NEG d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._neg8(self._read_byte(m)))
                return 5
            case 0x61:  # AIM #,d,X (HD6303)
                imm = self._fetch_byte()
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._and8(imm, self._read_byte(m)))
                return 6
            case 0x62:  # OIM #,d,X (HD6303)
                imm = self._fetch_byte()
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._or8(imm, self._read_byte(m)))
                return 6
            case 0x63:  # COM d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._com8(self._read_byte(m)))
                return 5
            case 0x64:  # LSR d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._lsr8(self._read_byte(m)))
                return 5
            case 0x65:  # EIM #,d,X (HD6303)
                imm = self._fetch_byte()
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._eor8(imm, self._read_byte(m)))
                return 6
            case 0x66:  # ROR d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._ror8(self._read_byte(m)))
                return 5
            case 0x67:  # ASR d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._asr8(self._read_byte(m)))
                return 5
            case 0x68:  # ASL d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._asl8(self._read_byte(m)))
                return 5
            case 0x69:  # ROL d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._rol8(self._read_byte(m)))
                return 5
            case 0x6A:  # DEC d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._dec8(self._read_byte(m)))
                return 5
            case 0x6B:  # TIM #,d,X (HD6303)
                imm = self._fetch_byte()
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._and8(imm, self._read_byte(m))
                return 4
            case 0x6C:  # INC d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._inc8(self._read_byte(m)))
                return 5
            case 0x6D:  # TST d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._tst8(self._read_byte(m))
                return 3
            case 0x6E:  # JMP d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self.pc = m
                return 2
            case 0x6F:  # CLR d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._clr8())
                return 4

            # ============================================
            # Extended Operations (0x70-0x7F)
            # ============================================
            case 0x70:  # NEG mm
                m = self._fetch_word()
                self._write_byte(m, self._neg8(self._read_byte(m)))
                return 5
            case 0x71:  # AIM #,0m (HD6303 - direct page)
                imm = self._fetch_byte()
                m = self._fetch_byte()
                self._write_byte(m, self._and8(imm, self._read_byte(m)))
                return 5
            case 0x72:  # OIM #,0m (HD6303 - direct page)
                imm = self._fetch_byte()
                m = self._fetch_byte()
                self._write_byte(m, self._or8(imm, self._read_byte(m)))
                return 5
            case 0x73:  # COM mm
                m = self._fetch_word()
                self._write_byte(m, self._com8(self._read_byte(m)))
                return 5
            case 0x74:  # LSR mm
                m = self._fetch_word()
                self._write_byte(m, self._lsr8(self._read_byte(m)))
                return 5
            case 0x75:  # EIM #,0m (HD6303 - direct page)
                imm = self._fetch_byte()
                m = self._fetch_byte()
                self._write_byte(m, self._eor8(imm, self._read_byte(m)))
                return 5
            case 0x76:  # ROR mm
                m = self._fetch_word()
                self._write_byte(m, self._ror8(self._read_byte(m)))
                return 5
            case 0x77:  # ASR mm
                m = self._fetch_word()
                self._write_byte(m, self._asr8(self._read_byte(m)))
                return 5
            case 0x78:  # ASL mm
                m = self._fetch_word()
                self._write_byte(m, self._asl8(self._read_byte(m)))
                return 5
            case 0x79:  # ROL mm
                m = self._fetch_word()
                self._write_byte(m, self._rol8(self._read_byte(m)))
                return 5
            case 0x7A:  # DEC mm
                m = self._fetch_word()
                self._write_byte(m, self._dec8(self._read_byte(m)))
                return 5
            case 0x7B:  # TIM #,0m (HD6303 - direct page)
                imm = self._fetch_byte()
                m = self._fetch_byte()
                self._and8(imm, self._read_byte(m))
                return 3
            case 0x7C:  # INC mm
                m = self._fetch_word()
                self._write_byte(m, self._inc8(self._read_byte(m)))
                return 5
            case 0x7D:  # TST mm
                m = self._fetch_word()
                self._tst8(self._read_byte(m))
                return 3
            case 0x7E:  # JMP mm
                m = self._fetch_word()
                self.pc = m
                return 2
            case 0x7F:  # CLR mm
                m = self._fetch_word()
                self._write_byte(m, self._clr8())
                return 4

            # ============================================
            # Accumulator A with Immediate (0x80-0x8F)
            # ============================================
            case 0x80:  # SUBA #
                m = self._fetch_byte()
                self.a = self._sub8(self.a, m)
                return 1
            case 0x81:  # CMPA #
                m = self._fetch_byte()
                self._sub8(self.a, m)
                return 1
            case 0x82:  # SBCA #
                m = self._fetch_byte()
                self.a = self._sbc8(self.a, m)
                return 1
            case 0x83:  # SUBD ##
                m = self._fetch_word()
                self.d = self._sub16(self.d, m)
                return 2
            case 0x84:  # ANDA #
                m = self._fetch_byte()
                self.a = self._and8(self.a, m)
                return 1
            case 0x85:  # BITA #
                m = self._fetch_byte()
                self._and8(self.a, m)
                return 1
            case 0x86:  # LDAA #
                m = self._fetch_byte()
                self.a = self._ld8(m)
                return 1
            case 0x88:  # EORA #
                m = self._fetch_byte()
                self.a = self._eor8(self.a, m)
                return 1
            case 0x89:  # ADCA #
                m = self._fetch_byte()
                self.a = self._adc8(self.a, m)
                return 1
            case 0x8A:  # ORAA #
                m = self._fetch_byte()
                self.a = self._or8(self.a, m)
                return 1
            case 0x8B:  # ADDA #
                m = self._fetch_byte()
                self.a = self._add8(self.a, m)
                return 1
            case 0x8C:  # CPX ##
                m = self._fetch_word()
                self._sub16(self.x, m)
                return 2
            case 0x8D:  # BSR d
                d = self._fetch_byte()
                self._push_word(self.pc)
                if d >= 0x80:
                    d -= 0x100
                self.pc = (self.pc + d) & 0xFFFF
                return 4
            case 0x8E:  # LDS ##
                m = self._fetch_word()
                self.sp = self._ld16(m)
                return 2

            # ============================================
            # Accumulator A with Direct Page (0x90-0x9F)
            # ============================================
            case 0x90:  # SUBA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._sub8(self.a, m)
                return 2
            case 0x91:  # CMPA 0m
                m = self._read_byte(self._fetch_byte())
                self._sub8(self.a, m)
                return 2
            case 0x92:  # SBCA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._sbc8(self.a, m)
                return 2
            case 0x93:  # SUBD 0m
                m = self._read_word(self._fetch_byte())
                self.d = self._sub16(self.d, m)
                return 3
            case 0x94:  # ANDA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._and8(self.a, m)
                return 2
            case 0x95:  # BITA 0m
                m = self._read_byte(self._fetch_byte())
                self._and8(self.a, m)
                return 2
            case 0x96:  # LDAA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._ld8(m)
                return 2
            case 0x97:  # STAA 0m
                m = self._fetch_byte()
                self._write_byte(m, self._ld8(self.a))
                return 2
            case 0x98:  # EORA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._eor8(self.a, m)
                return 2
            case 0x99:  # ADCA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._adc8(self.a, m)
                return 2
            case 0x9A:  # ORAA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._or8(self.a, m)
                return 2
            case 0x9B:  # ADDA 0m
                m = self._read_byte(self._fetch_byte())
                self.a = self._add8(self.a, m)
                return 2
            case 0x9C:  # CPX 0m
                m = self._read_word(self._fetch_byte())
                self._sub16(self.x, m)
                return 3
            case 0x9D:  # JSR 0m
                m = self._fetch_byte()
                self._push_word(self.pc)
                self.pc = m
                return 4
            case 0x9E:  # LDS 0m
                m = self._read_word(self._fetch_byte())
                self.sp = self._ld16(m)
                return 3
            case 0x9F:  # STS 0m
                m = self._fetch_byte()
                self._write_word(m, self._ld16(self.sp))
                return 3

            # ============================================
            # Accumulator A with Indexed (0xA0-0xAF)
            # ============================================
            case 0xA0:  # SUBA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._sub8(self.a, m)
                return 3
            case 0xA1:  # CMPA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self._sub8(self.a, m)
                return 3
            case 0xA2:  # SBCA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._sbc8(self.a, m)
                return 3
            case 0xA3:  # SUBD d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self.d = self._sub16(self.d, m)
                return 4
            case 0xA4:  # ANDA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._and8(self.a, m)
                return 3
            case 0xA5:  # BITA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self._and8(self.a, m)
                return 3
            case 0xA6:  # LDAA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._ld8(m)
                return 3
            case 0xA7:  # STAA d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._ld8(self.a))
                return 3
            case 0xA8:  # EORA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._eor8(self.a, m)
                return 3
            case 0xA9:  # ADCA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._adc8(self.a, m)
                return 3
            case 0xAA:  # ORAA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._or8(self.a, m)
                return 3
            case 0xAB:  # ADDA d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.a = self._add8(self.a, m)
                return 3
            case 0xAC:  # CPX d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self._sub16(self.x, m)
                return 4
            case 0xAD:  # JSR d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._push_word(self.pc)
                self.pc = m
                return 4
            case 0xAE:  # LDS d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self.sp = self._ld16(m)
                return 4
            case 0xAF:  # STS d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_word(m, self._ld16(self.sp))
                return 4

            # ============================================
            # Accumulator A with Extended (0xB0-0xBF)
            # ============================================
            case 0xB0:  # SUBA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._sub8(self.a, m)
                return 3
            case 0xB1:  # CMPA mm
                m = self._read_byte(self._fetch_word())
                self._sub8(self.a, m)
                return 3
            case 0xB2:  # SBCA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._sbc8(self.a, m)
                return 3
            case 0xB3:  # SUBD mm
                m = self._read_word(self._fetch_word())
                self.d = self._sub16(self.d, m)
                return 4
            case 0xB4:  # ANDA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._and8(self.a, m)
                return 3
            case 0xB5:  # BITA mm
                m = self._read_byte(self._fetch_word())
                self._and8(self.a, m)
                return 3
            case 0xB6:  # LDAA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._ld8(m)
                return 3
            case 0xB7:  # STAA mm
                m = self._fetch_word()
                self._write_byte(m, self._ld8(self.a))
                return 3
            case 0xB8:  # EORA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._eor8(self.a, m)
                return 3
            case 0xB9:  # ADCA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._adc8(self.a, m)
                return 3
            case 0xBA:  # ORAA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._or8(self.a, m)
                return 3
            case 0xBB:  # ADDA mm
                m = self._read_byte(self._fetch_word())
                self.a = self._add8(self.a, m)
                return 3
            case 0xBC:  # CPX mm
                m = self._read_word(self._fetch_word())
                self._sub16(self.x, m)
                return 4
            case 0xBD:  # JSR mm
                m = self._fetch_word()
                self._push_word(self.pc)
                self.pc = m
                return 5
            case 0xBE:  # LDS mm
                m = self._read_word(self._fetch_word())
                self.sp = self._ld16(m)
                return 4
            case 0xBF:  # STS mm
                m = self._fetch_word()
                self._write_word(m, self._ld16(self.sp))
                return 4

            # ============================================
            # Accumulator B with Immediate (0xC0-0xCF)
            # ============================================
            case 0xC0:  # SUBB #
                m = self._fetch_byte()
                self.b = self._sub8(self.b, m)
                return 1
            case 0xC1:  # CMPB #
                m = self._fetch_byte()
                self._sub8(self.b, m)
                return 1
            case 0xC2:  # SBCB #
                m = self._fetch_byte()
                self.b = self._sbc8(self.b, m)
                return 1
            case 0xC3:  # ADDD ##
                m = self._fetch_word()
                self.d = self._add16(self.d, m)
                return 2
            case 0xC4:  # ANDB #
                m = self._fetch_byte()
                self.b = self._and8(self.b, m)
                return 1
            case 0xC5:  # BITB #
                m = self._fetch_byte()
                self._and8(self.b, m)
                return 1
            case 0xC6:  # LDAB #
                m = self._fetch_byte()
                self.b = self._ld8(m)
                return 1
            case 0xC8:  # EORB #
                m = self._fetch_byte()
                self.b = self._eor8(self.b, m)
                return 1
            case 0xC9:  # ADCB #
                m = self._fetch_byte()
                self.b = self._adc8(self.b, m)
                return 1
            case 0xCA:  # ORAB #
                m = self._fetch_byte()
                self.b = self._or8(self.b, m)
                return 1
            case 0xCB:  # ADDB #
                m = self._fetch_byte()
                self.b = self._add8(self.b, m)
                return 1
            case 0xCC:  # LDD ##
                m = self._fetch_word()
                self.d = self._ld16(m)
                return 2
            case 0xCE:  # LDX ##
                m = self._fetch_word()
                self.x = self._ld16(m)
                return 2

            # ============================================
            # Accumulator B with Direct Page (0xD0-0xDF)
            # ============================================
            case 0xD0:  # SUBB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._sub8(self.b, m)
                return 2
            case 0xD1:  # CMPB 0m
                m = self._read_byte(self._fetch_byte())
                self._sub8(self.b, m)
                return 2
            case 0xD2:  # SBCB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._sbc8(self.b, m)
                return 2
            case 0xD3:  # ADDD 0m
                m = self._read_word(self._fetch_byte())
                self.d = self._add16(self.d, m)
                return 3
            case 0xD4:  # ANDB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._and8(self.b, m)
                return 2
            case 0xD5:  # BITB 0m
                m = self._read_byte(self._fetch_byte())
                self._and8(self.b, m)
                return 2
            case 0xD6:  # LDAB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._ld8(m)
                return 2
            case 0xD7:  # STAB 0m
                m = self._fetch_byte()
                self._write_byte(m, self._ld8(self.b))
                return 2
            case 0xD8:  # EORB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._eor8(self.b, m)
                return 2
            case 0xD9:  # ADCB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._adc8(self.b, m)
                return 2
            case 0xDA:  # ORAB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._or8(self.b, m)
                return 2
            case 0xDB:  # ADDB 0m
                m = self._read_byte(self._fetch_byte())
                self.b = self._add8(self.b, m)
                return 2
            case 0xDC:  # LDD 0m
                m = self._read_word(self._fetch_byte())
                self.d = self._ld16(m)
                return 3
            case 0xDD:  # STD 0m
                m = self._fetch_byte()
                self._write_word(m, self._ld16(self.d))
                return 3
            case 0xDE:  # LDX 0m
                m = self._read_word(self._fetch_byte())
                self.x = self._ld16(m)
                return 3
            case 0xDF:  # STX 0m
                m = self._fetch_byte()
                self._write_word(m, self._ld16(self.x))
                return 3

            # ============================================
            # Accumulator B with Indexed (0xE0-0xEF)
            # ============================================
            case 0xE0:  # SUBB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._sub8(self.b, m)
                return 3
            case 0xE1:  # CMPB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self._sub8(self.b, m)
                return 3
            case 0xE2:  # SBCB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._sbc8(self.b, m)
                return 3
            case 0xE3:  # ADDD d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self.d = self._add16(self.d, m)
                return 4
            case 0xE4:  # ANDB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._and8(self.b, m)
                return 3
            case 0xE5:  # BITB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self._and8(self.b, m)
                return 3
            case 0xE6:  # LDAB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._ld8(m)
                return 3
            case 0xE7:  # STAB d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_byte(m, self._ld8(self.b))
                return 3
            case 0xE8:  # EORB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._eor8(self.b, m)
                return 3
            case 0xE9:  # ADCB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._adc8(self.b, m)
                return 3
            case 0xEA:  # ORAB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._or8(self.b, m)
                return 3
            case 0xEB:  # ADDB d,X
                m = self._read_byte((self.x + self._fetch_byte()) & 0xFFFF)
                self.b = self._add8(self.b, m)
                return 3
            case 0xEC:  # LDD d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self.d = self._ld16(m)
                return 4
            case 0xED:  # STD d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_word(m, self._ld16(self.d))
                return 4
            case 0xEE:  # LDX d,X
                m = self._read_word((self.x + self._fetch_byte()) & 0xFFFF)
                self.x = self._ld16(m)
                return 4
            case 0xEF:  # STX d,X
                m = (self.x + self._fetch_byte()) & 0xFFFF
                self._write_word(m, self._ld16(self.x))
                return 4

            # ============================================
            # Accumulator B with Extended (0xF0-0xFF)
            # ============================================
            case 0xF0:  # SUBB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._sub8(self.b, m)
                return 3
            case 0xF1:  # CMPB mm
                m = self._read_byte(self._fetch_word())
                self._sub8(self.b, m)
                return 3
            case 0xF2:  # SBCB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._sbc8(self.b, m)
                return 3
            case 0xF3:  # ADDD mm
                m = self._read_word(self._fetch_word())
                self.d = self._add16(self.d, m)
                return 4
            case 0xF4:  # ANDB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._and8(self.b, m)
                return 3
            case 0xF5:  # BITB mm
                m = self._read_byte(self._fetch_word())
                self._and8(self.b, m)
                return 3
            case 0xF6:  # LDAB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._ld8(m)
                return 3
            case 0xF7:  # STAB mm
                m = self._fetch_word()
                self._write_byte(m, self._ld8(self.b))
                return 3
            case 0xF8:  # EORB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._eor8(self.b, m)
                return 3
            case 0xF9:  # ADCB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._adc8(self.b, m)
                return 3
            case 0xFA:  # ORAB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._or8(self.b, m)
                return 3
            case 0xFB:  # ADDB mm
                m = self._read_byte(self._fetch_word())
                self.b = self._add8(self.b, m)
                return 3
            case 0xFC:  # LDD mm
                m = self._read_word(self._fetch_word())
                self.d = self._ld16(m)
                return 4
            case 0xFD:  # STD mm
                m = self._fetch_word()
                self._write_word(m, self._ld16(self.d))
                return 4
            case 0xFE:  # LDX mm
                m = self._read_word(self._fetch_word())
                self.x = self._ld16(m)
                return 4
            case 0xFF:  # STX mm
                m = self._fetch_word()
                self._write_word(m, self._ld16(self.x))
                return 4

            case _:
                # Invalid/undefined opcodes - switch off (matches JAPE)
                self.bus.write(0x01C0, 0)  # switchOff address
                return 0

    # ========================================
    # Snapshot Support
    # ========================================

    def get_snapshot_data(self) -> list[int]:
        """
        Get CPU state as byte list for snapshot.

        Format matches JAPE: [A, B, P, Xhi, Xlo, PChi, PClo, SPhi, SPlo, sleep]
        """
        return [
            self.a,
            self.b,
            self._get_p(),
            (self.x >> 8) & 0xFF,
            self.x & 0xFF,
            (self.pc >> 8) & 0xFF,
            self.pc & 0xFF,
            (self.sp >> 8) & 0xFF,
            self.sp & 0xFF,
            1 if self.state.sleep else 0
        ]

    def apply_snapshot_data(self, data: list[int], offset: int = 0) -> int:
        """
        Restore CPU state from snapshot data.

        Returns:
            Number of bytes consumed from data (10)
        """
        self.a = data[offset]
        self.b = data[offset + 1]
        self._set_p(data[offset + 2])
        self.x = (data[offset + 3] << 8) | data[offset + 4]
        self.pc = (data[offset + 5] << 8) | data[offset + 6]
        self.sp = (data[offset + 7] << 8) | data[offset + 8]
        self.state.sleep = data[offset + 9] != 0
        return 10
