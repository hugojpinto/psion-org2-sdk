"""
Breakpoint and Watchpoint System for Psion Emulator
====================================================

Provides comprehensive debugging capabilities:
- PC breakpoints (break when PC reaches address)
- Memory watchpoints (break on read/write)
- Register conditions (break when registers match)
- Syscall interception (hook OS calls)

This module is integrated with the CPU via instruction hooks and memory
access hooks. The BreakpointManager is attached to the CPU and checked
during execution to detect break conditions.

Example usage:

    >>> from psion_sdk.emulator import Emulator, BreakpointManager, BreakReason
    >>> emu = Emulator()
    >>> emu.breakpoints.add_breakpoint(0x8100)  # Break at address
    >>> emu.breakpoints.add_write_watchpoint(0x0050)  # Break on write
    >>> event = emu.run(1_000_000)
    >>> if event.reason == BreakReason.PC_BREAKPOINT:
    ...     print(f"Hit breakpoint at ${event.address:04X}")

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional, Set, Dict, List, TYPE_CHECKING

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
    REGISTER_CONDITION = auto()  # Register condition met
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
            case BreakReason.REGISTER_CONDITION:
                return "Register condition met"
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


class RegisterCondition:
    """
    Condition on CPU registers.

    Defines a condition that can be checked against CPU state. When the
    condition evaluates to True, execution stops.

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
        >>> cond = RegisterCondition('a', '==', 0x42)  # A equals 0x42
        >>> cond = RegisterCondition('x', '>', 0x1000)  # X greater than 0x1000
        >>> cond = RegisterCondition('flag_z', '==', True)  # Zero flag set
        >>> cond = RegisterCondition('d', '&', 0x8000)  # High bit of D set
    """

    def __init__(
        self,
        register: str,
        operator: str,
        value: int | bool,
        description: str = ""
    ):
        """
        Create a register condition.

        Args:
            register: Register name (a, b, d, x, sp, pc, flag_*)
            operator: Comparison operator (==, !=, <, <=, >, >=, &)
            value: Value to compare against
            description: Optional description for debugging
        """
        self.register = register.lower()
        self.operator = operator
        self.value = value
        self.description = description or f"{register} {operator} {value}"

        # Validate register name
        valid_registers = {
            'a', 'b', 'd', 'x', 'sp', 'pc',
            'flag_c', 'flag_v', 'flag_z', 'flag_n', 'flag_i', 'flag_h',
            'flags'
        }
        if self.register not in valid_registers:
            raise ValueError(
                f"Unknown register '{register}'. Valid registers: {', '.join(sorted(valid_registers))}"
            )

        # Validate operator
        valid_operators = {'==', '!=', '<', '<=', '>', '>=', '&'}
        if self.operator not in valid_operators:
            raise ValueError(
                f"Unknown operator '{operator}'. Valid operators: {', '.join(sorted(valid_operators))}"
            )

    def check(self, cpu: "HD6303") -> bool:
        """
        Check if condition is met against CPU state.

        Args:
            cpu: CPU instance to check

        Returns:
            True if condition is met, False otherwise
        """
        # Get actual register value
        actual = getattr(cpu, self.register)

        # Evaluate condition
        match self.operator:
            case '==':
                return actual == self.value
            case '!=':
                return actual != self.value
            case '<':
                return actual < self.value
            case '<=':
                return actual <= self.value
            case '>':
                return actual > self.value
            case '>=':
                return actual >= self.value
            case '&':
                return (actual & self.value) != 0
            case _:
                return False

    def __repr__(self) -> str:
        return f"RegisterCondition({self.register!r}, {self.operator!r}, {self.value!r})"


class BreakpointManager:
    """
    Manages breakpoints, watchpoints, and register conditions.

    This class is the central debugging controller. It maintains collections
    of breakpoints and watchpoints, and provides methods to add, remove, and
    check them during emulation.

    The manager integrates with the CPU via hooks:
    - check_instruction: Called before each instruction
    - check_memory_read: Called on memory reads
    - check_memory_write: Called on memory writes

    Example:
        >>> mgr = BreakpointManager()
        >>> mgr.add_breakpoint(0x8100)
        >>> mgr.add_write_watchpoint(0x0050)
        >>> mgr.add_register_condition(RegisterCondition('a', '==', 0x00))
        >>> # Hooks are called by CPU during execution
        >>> cpu.on_instruction = lambda pc, op: mgr.check_instruction(cpu, pc, op)
    """

    def __init__(self):
        """Initialize empty breakpoint manager."""
        # PC breakpoints (set of addresses)
        self._pc_breakpoints: Set[int] = set()

        # Memory watchpoints (sets of addresses)
        self._read_watchpoints: Set[int] = set()
        self._write_watchpoints: Set[int] = set()

        # Register conditions (list with possible None holes)
        self._register_conditions: List[Optional[RegisterCondition]] = []

        # Syscall hooks (syscall number → callback)
        # Callback receives syscall number and CPU, returns True to continue
        self._syscall_hooks: Dict[int, Callable[[int, "HD6303"], bool]] = {}

        # Last break event (for inspection after break)
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

    def add_breakpoint(self, address: int) -> None:
        """
        Add PC breakpoint at address.

        Execution will stop when PC reaches this address, before the
        instruction at that address is executed.

        Args:
            address: 16-bit memory address
        """
        self._pc_breakpoints.add(address & 0xFFFF)

    def remove_breakpoint(self, address: int) -> None:
        """
        Remove PC breakpoint at address.

        Args:
            address: 16-bit memory address
        """
        self._pc_breakpoints.discard(address & 0xFFFF)

    def has_breakpoint(self, address: int) -> bool:
        """
        Check if breakpoint exists at address.

        Args:
            address: 16-bit memory address

        Returns:
            True if breakpoint exists
        """
        return (address & 0xFFFF) in self._pc_breakpoints

    def clear_breakpoints(self) -> None:
        """Remove all PC breakpoints."""
        self._pc_breakpoints.clear()

    def list_breakpoints(self) -> List[int]:
        """
        Get list of all breakpoint addresses.

        Returns:
            Sorted list of breakpoint addresses
        """
        return sorted(self._pc_breakpoints)

    # =========================================================================
    # Memory Watchpoints
    # =========================================================================

    def add_read_watchpoint(self, address: int) -> None:
        """
        Add watchpoint that triggers on memory read.

        Execution will stop when this address is read from.

        Args:
            address: 16-bit memory address
        """
        self._read_watchpoints.add(address & 0xFFFF)

    def add_write_watchpoint(self, address: int) -> None:
        """
        Add watchpoint that triggers on memory write.

        Execution will stop when this address is written to.

        Args:
            address: 16-bit memory address
        """
        self._write_watchpoints.add(address & 0xFFFF)

    def add_watchpoint(
        self,
        address: int,
        on_read: bool = False,
        on_write: bool = True
    ) -> None:
        """
        Add watchpoint with specified triggers.

        Args:
            address: 16-bit memory address
            on_read: Trigger on read (default False)
            on_write: Trigger on write (default True)
        """
        if on_read:
            self.add_read_watchpoint(address)
        if on_write:
            self.add_write_watchpoint(address)

    def remove_watchpoint(self, address: int) -> None:
        """
        Remove read and write watchpoints at address.

        Args:
            address: 16-bit memory address
        """
        self._read_watchpoints.discard(address & 0xFFFF)
        self._write_watchpoints.discard(address & 0xFFFF)

    def remove_read_watchpoint(self, address: int) -> None:
        """Remove read watchpoint at address."""
        self._read_watchpoints.discard(address & 0xFFFF)

    def remove_write_watchpoint(self, address: int) -> None:
        """Remove write watchpoint at address."""
        self._write_watchpoints.discard(address & 0xFFFF)

    def clear_watchpoints(self) -> None:
        """Remove all watchpoints."""
        self._read_watchpoints.clear()
        self._write_watchpoints.clear()

    def list_read_watchpoints(self) -> List[int]:
        """Get sorted list of read watchpoint addresses."""
        return sorted(self._read_watchpoints)

    def list_write_watchpoints(self) -> List[int]:
        """Get sorted list of write watchpoint addresses."""
        return sorted(self._write_watchpoints)

    # =========================================================================
    # Register Conditions
    # =========================================================================

    def add_register_condition(self, condition: RegisterCondition) -> int:
        """
        Add register condition.

        Execution will stop when the condition evaluates to True.

        Args:
            condition: RegisterCondition to add

        Returns:
            Condition ID for later removal
        """
        # Find first empty slot or append
        for i, c in enumerate(self._register_conditions):
            if c is None:
                self._register_conditions[i] = condition
                return i
        self._register_conditions.append(condition)
        return len(self._register_conditions) - 1

    def add_condition(
        self,
        register: str,
        operator: str,
        value: int | bool,
        description: str = ""
    ) -> int:
        """
        Add register condition using parameters.

        Convenience method that creates RegisterCondition internally.

        Args:
            register: Register name
            operator: Comparison operator
            value: Value to compare
            description: Optional description

        Returns:
            Condition ID
        """
        return self.add_register_condition(
            RegisterCondition(register, operator, value, description)
        )

    def remove_register_condition(self, condition_id: int) -> None:
        """
        Remove register condition by ID.

        Args:
            condition_id: ID returned by add_register_condition
        """
        if 0 <= condition_id < len(self._register_conditions):
            self._register_conditions[condition_id] = None

    def clear_register_conditions(self) -> None:
        """Remove all register conditions."""
        self._register_conditions.clear()

    def list_register_conditions(self) -> List[tuple[int, RegisterCondition]]:
        """
        Get list of active register conditions.

        Returns:
            List of (id, condition) tuples
        """
        return [
            (i, c) for i, c in enumerate(self._register_conditions)
            if c is not None
        ]

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
        It should return:
        - True: Continue normal execution
        - False: Break execution

        Args:
            syscall: Syscall number (value in A register before SWI)
            callback: Function to call when syscall is executed
        """
        self._syscall_hooks[syscall] = callback

    def remove_syscall_hook(self, syscall: int) -> None:
        """
        Remove syscall hook.

        Args:
            syscall: Syscall number
        """
        self._syscall_hooks.pop(syscall, None)

    def clear_syscall_hooks(self) -> None:
        """Remove all syscall hooks."""
        self._syscall_hooks.clear()

    # =========================================================================
    # Break Control
    # =========================================================================

    def request_break(self) -> None:
        """
        Request execution to break at next opportunity.

        Can be called from another thread to interrupt execution.
        """
        self._break_requested = True

    def clear_break_request(self) -> None:
        """Clear any pending break request."""
        self._break_requested = False

    def clear_all(self) -> None:
        """Remove all breakpoints, watchpoints, conditions, and hooks."""
        self.clear_breakpoints()
        self.clear_watchpoints()
        self.clear_register_conditions()
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

        This is called by the CPU before each instruction via the
        on_instruction hook. It checks all break conditions.

        Args:
            cpu: CPU instance
            pc: Current program counter
            opcode: Opcode about to be executed

        Returns:
            True to continue execution, False to break
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
            self._last_event = BreakEvent(
                BreakReason.PC_BREAKPOINT,
                address=pc,
                message=f"Breakpoint at ${pc:04X}"
            )
            return False

        # Check register conditions
        for cond in self._register_conditions:
            if cond is not None and cond.check(cpu):
                self._last_event = BreakEvent(
                    BreakReason.REGISTER_CONDITION,
                    address=pc,
                    message=f"Condition: {cond.description}"
                )
                return False

        # Check syscall detection (SWI instruction = 0x3F)
        if opcode == 0x3F:
            syscall = cpu.a  # Syscall number is in A register
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

    def check_memory_read(self, address: int, value: int) -> bool:
        """
        Check if we should break on memory read.

        This is called by the CPU on each memory read via the
        on_memory_read hook (if set).

        Args:
            address: Address being read
            value: Value read

        Returns:
            True to continue execution, False to break
        """
        if address in self._read_watchpoints:
            self._last_event = BreakEvent(
                BreakReason.MEMORY_READ,
                address=address,
                value=value,
                message=f"Read ${value:02X} from ${address:04X}"
            )
            return False
        return True

    def check_memory_write(self, address: int, value: int) -> bool:
        """
        Check if we should break on memory write.

        This is called by the CPU on each memory write via the
        on_memory_write hook (if set).

        Args:
            address: Address being written
            value: Value being written

        Returns:
            True to continue execution, False to break
        """
        if address in self._write_watchpoints:
            self._last_event = BreakEvent(
                BreakReason.MEMORY_WRITE,
                address=address,
                value=value,
                message=f"Write ${value:02X} to ${address:04X}"
            )
            return False
        return True
