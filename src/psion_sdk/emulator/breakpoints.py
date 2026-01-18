"""
Breakpoint and Watchpoint System for Psion Emulator
====================================================

Provides comprehensive debugging capabilities:
- PC breakpoints (break when PC reaches address, optionally with condition)
- Memory watchpoints (break on read/write, optionally with condition)
- Syscall interception (hook OS calls)

Breakpoints and watchpoints can have optional conditions attached.
A condition is a register test (e.g., "A == 0x42") that must also be true
for the break to fire.

Example usage:

    >>> from psion_sdk.emulator import Emulator, BreakpointManager, BreakReason
    >>> emu = Emulator()
    >>> # Simple breakpoint
    >>> emu.breakpoints.add_breakpoint(0x8100)
    >>> # Conditional breakpoint: break at $8100 only when A == 0x42
    >>> emu.breakpoints.add_breakpoint(0x8100, condition=("a", "==", 0x42))
    >>> # Watchpoint with condition
    >>> emu.breakpoints.add_write_watchpoint(0x0050, condition=("x", ">", 0x1000))

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional, Dict, List, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .cpu import HD6303


class BreakReason(Enum):
    """
    Enumeration of reasons why execution stopped.

    Used in BreakEvent to indicate what triggered the break.
    """
    NONE = auto()           # No specific reason (normal termination)
    PC_BREAKPOINT = auto()  # PC reached a breakpoint address
    MEMORY_READ = auto()    # Memory read watchpoint triggered
    MEMORY_WRITE = auto()   # Memory write watchpoint triggered
    SYSCALL = auto()        # Syscall hook requested stop
    STEP = auto()           # Single-step mode
    USER_INTERRUPT = auto() # User requested stop
    MAX_CYCLES = auto()     # Maximum cycle count reached
    ERROR = auto()          # Runtime error occurred


@dataclass
class BreakEvent:
    """
    Information about why execution stopped.

    Contains the reason for the break and relevant context such as
    the address, value, or syscall number involved.

    Attributes:
        reason: Why execution stopped
        address: Memory/PC address involved (if applicable)
        value: Value read/written (if applicable)
        syscall: Syscall number (if applicable)
        message: Human-readable description
    """
    reason: BreakReason
    address: Optional[int] = None
    value: Optional[int] = None
    syscall: Optional[int] = None
    message: str = ""

    def __str__(self) -> str:
        """Return human-readable description."""
        if self.message:
            return self.message
        match self.reason:
            case BreakReason.PC_BREAKPOINT:
                return f"Breakpoint at ${self.address:04X}" if self.address else "Breakpoint"
            case BreakReason.MEMORY_READ:
                return f"Read ${self.value:02X} from ${self.address:04X}" if self.address else "Memory read"
            case BreakReason.MEMORY_WRITE:
                return f"Write ${self.value:02X} to ${self.address:04X}" if self.address else "Memory write"
            case BreakReason.SYSCALL:
                return f"Syscall ${self.syscall:02X}" if self.syscall else "Syscall"
            case BreakReason.STEP:
                return "Single step"
            case BreakReason.MAX_CYCLES:
                return "Maximum cycles reached"
            case BreakReason.ERROR:
                return "Runtime error"
            case _:
                return "Unknown"


class Condition:
    """
    Condition on CPU registers that can be attached to breakpoints.

    A condition is checked along with the address match. The breakpoint
    only fires if both the address matches AND the condition is true.

    Supported registers: a, b, d, x, sp, pc, flag_c, flag_v, flag_z, flag_n, flag_i, flag_h

    Supported operators:
    - '==' : Equal
    - '!=' : Not equal
    - '<'  : Less than
    - '<=' : Less than or equal
    - '>'  : Greater than
    - '>=' : Greater than or equal
    - '&'  : Bitwise AND test (true if result non-zero)

    Examples:
        >>> cond = Condition('a', '==', 0x42)  # A equals 0x42
        >>> cond = Condition('x', '>', 0x1000)  # X greater than 0x1000
        >>> cond = Condition('flag_z', '==', True)  # Zero flag set
    """

    VALID_REGISTERS = {
        'a', 'b', 'd', 'x', 'sp', 'pc',
        'flag_c', 'flag_v', 'flag_z', 'flag_n', 'flag_i', 'flag_h'
    }
    VALID_OPERATORS = {'==', '!=', '<', '<=', '>', '>=', '&'}

    def __init__(
        self,
        register: str,
        operator: str,
        value: int | bool
    ):
        """
        Create a condition.

        Args:
            register: Register name (a, b, d, x, sp, pc, flag_*)
            operator: Comparison operator (==, !=, <, <=, >, >=, &)
            value: Value to compare against
        """
        self.register = register.lower()
        self.operator = operator
        self.value = value

        # Validate
        if self.register not in self.VALID_REGISTERS:
            raise ValueError(
                f"Unknown register '{register}'. "
                f"Valid: {', '.join(sorted(self.VALID_REGISTERS))}"
            )
        if self.operator not in self.VALID_OPERATORS:
            raise ValueError(
                f"Unknown operator '{operator}'. "
                f"Valid: {', '.join(sorted(self.VALID_OPERATORS))}"
            )

    def check(self, cpu: "HD6303") -> bool:
        """Check if condition is met against CPU state."""
        actual = getattr(cpu, self.register)
        match self.operator:
            case '==': return actual == self.value
            case '!=': return actual != self.value
            case '<': return actual < self.value
            case '<=': return actual <= self.value
            case '>': return actual > self.value
            case '>=': return actual >= self.value
            case '&': return (actual & self.value) != 0
            case _: return False

    def __str__(self) -> str:
        return f"{self.register} {self.operator} {self.value}"

    def __repr__(self) -> str:
        return f"Condition({self.register!r}, {self.operator!r}, {self.value!r})"


# Type alias for condition specification (can be Condition or tuple)
ConditionSpec = Union[Condition, Tuple[str, str, int], None]


def _make_condition(spec: ConditionSpec) -> Optional[Condition]:
    """Convert condition specification to Condition object."""
    if spec is None:
        return None
    if isinstance(spec, Condition):
        return spec
    if isinstance(spec, tuple) and len(spec) == 3:
        return Condition(spec[0], spec[1], spec[2])
    raise ValueError(f"Invalid condition specification: {spec}")




class BreakpointManager:
    """
    Manages breakpoints and watchpoints with optional conditions.

    Breakpoints and watchpoints can have optional conditions attached.
    A break only fires if the address matches AND the condition is true
    (or if there's no condition).

    Example:
        >>> mgr = BreakpointManager()
        >>> # Simple breakpoint
        >>> mgr.add_breakpoint(0x8100)
        >>> # Conditional: break at $8100 only when A == 0x42
        >>> mgr.add_breakpoint(0x8200, condition=("a", "==", 0x42))
        >>> # Watchpoint with condition
        >>> mgr.add_write_watchpoint(0x0050, condition=("x", ">", 0x1000))
    """

    def __init__(self):
        """Initialize empty breakpoint manager."""
        # Breakpoints: address -> optional condition
        self._pc_breakpoints: Dict[int, Optional[Condition]] = {}
        self._read_watchpoints: Dict[int, Optional[Condition]] = {}
        self._write_watchpoints: Dict[int, Optional[Condition]] = {}

        # Syscall hooks (syscall number → callback)
        self._syscall_hooks: Dict[int, Callable[[int, "HD6303"], bool]] = {}

        # Last break event
        self._last_event: Optional[BreakEvent] = None

        # Step mode flag
        self._step_mode: bool = False

        # Break request flag (for external interrupt)
        self._break_requested: bool = False

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def last_event(self) -> Optional[BreakEvent]:
        """Get the last break event that occurred."""
        return self._last_event

    @property
    def step_mode(self) -> bool:
        """Check if step mode is active."""
        return self._step_mode

    @step_mode.setter
    def step_mode(self, value: bool) -> None:
        """Set step mode."""
        self._step_mode = value

    @property
    def breakpoint_count(self) -> int:
        """Number of active PC breakpoints."""
        return len(self._pc_breakpoints)

    @property
    def watchpoint_count(self) -> int:
        """Number of active watchpoints (read + write)."""
        return len(self._read_watchpoints) + len(self._write_watchpoints)

    # =========================================================================
    # PC Breakpoints
    # =========================================================================

    def add_breakpoint(
        self,
        address: int,
        condition: ConditionSpec = None
    ) -> None:
        """
        Add PC breakpoint at address with optional condition.

        Args:
            address: 16-bit memory address
            condition: Optional condition as Condition or (register, operator, value) tuple
        """
        self._pc_breakpoints[address & 0xFFFF] = _make_condition(condition)

    def remove_breakpoint(self, address: int) -> None:
        """Remove PC breakpoint at address."""
        self._pc_breakpoints.pop(address & 0xFFFF, None)

    def has_breakpoint(self, address: int) -> bool:
        """Check if breakpoint exists at address."""
        return (address & 0xFFFF) in self._pc_breakpoints

    def get_breakpoint_condition(self, address: int) -> Optional[Condition]:
        """Get condition for breakpoint at address, or None."""
        return self._pc_breakpoints.get(address & 0xFFFF)

    def clear_breakpoints(self) -> None:
        """Remove all PC breakpoints."""
        self._pc_breakpoints.clear()

    def list_breakpoints(self) -> List[Tuple[int, Optional[Condition]]]:
        """
        Get list of all breakpoints with their conditions.

        Returns:
            List of (address, condition) tuples, sorted by address
        """
        return sorted(self._pc_breakpoints.items())

    # =========================================================================
    # Memory Watchpoints
    # =========================================================================

    def add_read_watchpoint(
        self,
        address: int,
        condition: ConditionSpec = None
    ) -> None:
        """Add watchpoint that triggers on memory read."""
        self._read_watchpoints[address & 0xFFFF] = _make_condition(condition)

    def add_write_watchpoint(
        self,
        address: int,
        condition: ConditionSpec = None
    ) -> None:
        """Add watchpoint that triggers on memory write."""
        self._write_watchpoints[address & 0xFFFF] = _make_condition(condition)

    def add_watchpoint(
        self,
        address: int,
        on_read: bool = False,
        on_write: bool = True,
        condition: ConditionSpec = None
    ) -> None:
        """Add watchpoint with specified triggers and optional condition."""
        if on_read:
            self.add_read_watchpoint(address, condition)
        if on_write:
            self.add_write_watchpoint(address, condition)

    def remove_watchpoint(self, address: int) -> None:
        """Remove read and write watchpoints at address."""
        self._read_watchpoints.pop(address & 0xFFFF, None)
        self._write_watchpoints.pop(address & 0xFFFF, None)

    def remove_read_watchpoint(self, address: int) -> None:
        """Remove read watchpoint at address."""
        self._read_watchpoints.pop(address & 0xFFFF, None)

    def remove_write_watchpoint(self, address: int) -> None:
        """Remove write watchpoint at address."""
        self._write_watchpoints.pop(address & 0xFFFF, None)

    def clear_watchpoints(self) -> None:
        """Remove all watchpoints."""
        self._read_watchpoints.clear()
        self._write_watchpoints.clear()

    def list_read_watchpoints(self) -> List[Tuple[int, Optional[Condition]]]:
        """Get list of read watchpoints with conditions."""
        return sorted(self._read_watchpoints.items())

    def list_write_watchpoints(self) -> List[Tuple[int, Optional[Condition]]]:
        """Get list of write watchpoints with conditions."""
        return sorted(self._write_watchpoints.items())

    # =========================================================================
    # Syscall Hooks
    # =========================================================================

    def add_syscall_hook(
        self,
        syscall: int,
        callback: Callable[[int, "HD6303"], bool]
    ) -> None:
        """
        Add hook for syscall.

        The callback receives the syscall number and CPU instance.
        Return True to continue, False to break.
        """
        self._syscall_hooks[syscall] = callback

    def remove_syscall_hook(self, syscall: int) -> None:
        """Remove syscall hook."""
        self._syscall_hooks.pop(syscall, None)

    def clear_syscall_hooks(self) -> None:
        """Remove all syscall hooks."""
        self._syscall_hooks.clear()

    # =========================================================================
    # Break Control
    # =========================================================================

    def request_break(self) -> None:
        """Request execution to break at next opportunity."""
        self._break_requested = True

    def clear_break_request(self) -> None:
        """Clear any pending break request."""
        self._break_requested = False

    def clear_all(self) -> None:
        """Remove all breakpoints, watchpoints, and hooks."""
        self.clear_breakpoints()
        self.clear_watchpoints()
        self.clear_syscall_hooks()
        self._step_mode = False
        self._break_requested = False
        self._last_event = None

    # =========================================================================
    # Check Functions (called by CPU hooks)
    # =========================================================================

    def check_instruction(
        self,
        cpu: "HD6303",
        pc: int,
        opcode: int
    ) -> bool:
        """
        Check if we should break before executing instruction.

        Returns True to continue, False to break.
        """
        # Check external break request
        if self._break_requested:
            self._break_requested = False
            self._last_event = BreakEvent(
                BreakReason.USER_INTERRUPT,
                address=pc,
                message="User interrupt"
            )
            return False

        # Check step mode
        if self._step_mode:
            self._step_mode = False
            self._last_event = BreakEvent(
                BreakReason.STEP,
                address=pc,
                message=f"Step at ${pc:04X}"
            )
            return False

        # Check PC breakpoints
        if pc in self._pc_breakpoints:
            condition = self._pc_breakpoints[pc]
            # Break if no condition, or condition is met
            if condition is None or condition.check(cpu):
                msg = f"Breakpoint at ${pc:04X}"
                if condition:
                    msg += f" (when {condition})"
                self._last_event = BreakEvent(
                    BreakReason.PC_BREAKPOINT,
                    address=pc,
                    message=msg
                )
                return False

        # Check syscall detection (SWI instruction = 0x3F)
        if opcode == 0x3F:
            syscall = cpu.a
            if syscall in self._syscall_hooks:
                if not self._syscall_hooks[syscall](syscall, cpu):
                    self._last_event = BreakEvent(
                        BreakReason.SYSCALL,
                        address=pc,
                        syscall=syscall,
                        message=f"Syscall ${syscall:02X}"
                    )
                    return False

        return True

    def check_memory_read(self, cpu: "HD6303", address: int, value: int) -> bool:
        """
        Check if we should break on memory read.

        Returns True to continue, False to break.
        """
        if address in self._read_watchpoints:
            condition = self._read_watchpoints[address]
            if condition is None or condition.check(cpu):
                msg = f"Read ${value:02X} from ${address:04X}"
                if condition:
                    msg += f" (when {condition})"
                self._last_event = BreakEvent(
                    BreakReason.MEMORY_READ,
                    address=address,
                    value=value,
                    message=msg
                )
                return False
        return True

    def check_memory_write(self, cpu: "HD6303", address: int, value: int) -> bool:
        """
        Check if we should break on memory write.

        Returns True to continue, False to break.
        """
        if address in self._write_watchpoints:
            condition = self._write_watchpoints[address]
            if condition is None or condition.check(cpu):
                msg = f"Write ${value:02X} to ${address:04X}"
                if condition:
                    msg += f" (when {condition})"
                self._last_event = BreakEvent(
                    BreakReason.MEMORY_WRITE,
                    address=address,
                    value=value,
                    message=msg
                )
                return False
        return True

