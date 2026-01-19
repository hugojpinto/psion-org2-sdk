"""
Breakpoint System Unit Tests
============================

Tests for breakpoints, watchpoints with optional conditions, and syscall hooks.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.emulator import (
    BreakpointManager,
    BreakEvent,
    BreakReason,
)
from psion_sdk.emulator.breakpoints import Condition


# =============================================================================
# Mock CPU for Testing
# =============================================================================

class MockCPU:
    """Mock CPU for breakpoint testing."""

    def __init__(self):
        self.a = 0
        self.b = 0
        self.d = 0
        self.x = 0
        self.sp = 0x0100
        self.pc = 0x8000
        self.flag_c = False
        self.flag_v = False
        self.flag_z = False
        self.flag_n = False
        self.flag_i = False
        self.flag_h = False
        self.flags = 0


# =============================================================================
# BreakpointManager Tests
# =============================================================================

class TestBreakpointManager:
    """Test BreakpointManager initialization and basic operations."""

    def test_initial_state(self):
        """Manager starts with no breakpoints."""
        mgr = BreakpointManager()
        assert mgr.breakpoint_count == 0
        assert mgr.watchpoint_count == 0
        assert mgr.last_event is None

    def test_step_mode(self):
        """Step mode can be set and cleared."""
        mgr = BreakpointManager()

        assert mgr.step_mode is False
        mgr.step_mode = True
        assert mgr.step_mode is True
        mgr.step_mode = False
        assert mgr.step_mode is False


# =============================================================================
# PC Breakpoint Tests
# =============================================================================

class TestPCBreakpoints:
    """Test PC breakpoint functionality."""

    @pytest.fixture
    def mgr(self):
        return BreakpointManager()

    def test_add_breakpoint(self, mgr):
        """add_breakpoint adds a breakpoint."""
        mgr.add_breakpoint(0x8000)
        assert mgr.breakpoint_count == 1
        assert mgr.has_breakpoint(0x8000)

    def test_remove_breakpoint(self, mgr):
        """remove_breakpoint removes a breakpoint."""
        mgr.add_breakpoint(0x8000)
        mgr.remove_breakpoint(0x8000)
        assert mgr.breakpoint_count == 0
        assert not mgr.has_breakpoint(0x8000)

    def test_multiple_breakpoints(self, mgr):
        """Multiple breakpoints work."""
        mgr.add_breakpoint(0x8000)
        mgr.add_breakpoint(0x8100)
        mgr.add_breakpoint(0x8200)

        assert mgr.breakpoint_count == 3
        assert mgr.has_breakpoint(0x8000)
        assert mgr.has_breakpoint(0x8100)
        assert mgr.has_breakpoint(0x8200)

    def test_clear_breakpoints(self, mgr):
        """clear_breakpoints removes all."""
        mgr.add_breakpoint(0x8000)
        mgr.add_breakpoint(0x8100)
        mgr.clear_breakpoints()

        assert mgr.breakpoint_count == 0

    def test_list_breakpoints(self, mgr):
        """list_breakpoints returns sorted list of (address, condition) tuples."""
        mgr.add_breakpoint(0x8200)
        mgr.add_breakpoint(0x8000)
        mgr.add_breakpoint(0x8100)

        bp_list = mgr.list_breakpoints()
        addresses = [addr for addr, cond in bp_list]
        assert addresses == [0x8000, 0x8100, 0x8200]

    def test_duplicate_breakpoint(self, mgr):
        """Adding same breakpoint twice replaces it."""
        mgr.add_breakpoint(0x8000)
        mgr.add_breakpoint(0x8000)

        assert mgr.breakpoint_count == 1

    def test_remove_nonexistent(self, mgr):
        """Removing nonexistent breakpoint is safe."""
        mgr.remove_breakpoint(0x9999)  # Should not crash
        assert mgr.breakpoint_count == 0

    def test_address_masking(self, mgr):
        """Address is masked to 16 bits."""
        mgr.add_breakpoint(0x18000)  # 17-bit address
        assert mgr.has_breakpoint(0x8000)  # Masked to 16 bits

    def test_conditional_breakpoint(self, mgr):
        """Breakpoint with condition is stored."""
        mgr.add_breakpoint(0x8000, condition=("a", "==", 0x42))

        bp_list = mgr.list_breakpoints()
        addr, cond = bp_list[0]
        assert addr == 0x8000
        assert cond is not None
        assert cond.register == "a"
        assert cond.operator == "=="
        assert cond.value == 0x42


# =============================================================================
# Memory Watchpoint Tests
# =============================================================================

class TestWatchpoints:
    """Test memory watchpoint functionality."""

    @pytest.fixture
    def mgr(self):
        return BreakpointManager()

    @pytest.fixture
    def cpu(self):
        return MockCPU()

    def test_add_read_watchpoint(self, mgr):
        """add_read_watchpoint works."""
        mgr.add_read_watchpoint(0x0050)
        addresses = [addr for addr, cond in mgr.list_read_watchpoints()]
        assert 0x0050 in addresses

    def test_add_write_watchpoint(self, mgr):
        """add_write_watchpoint works."""
        mgr.add_write_watchpoint(0x0050)
        addresses = [addr for addr, cond in mgr.list_write_watchpoints()]
        assert 0x0050 in addresses

    def test_add_watchpoint_both(self, mgr):
        """add_watchpoint can set both."""
        mgr.add_watchpoint(0x0050, on_read=True, on_write=True)
        read_addrs = [addr for addr, cond in mgr.list_read_watchpoints()]
        write_addrs = [addr for addr, cond in mgr.list_write_watchpoints()]
        assert 0x0050 in read_addrs
        assert 0x0050 in write_addrs

    def test_remove_watchpoint(self, mgr):
        """remove_watchpoint removes both."""
        mgr.add_watchpoint(0x0050, on_read=True, on_write=True)
        mgr.remove_watchpoint(0x0050)
        read_addrs = [addr for addr, cond in mgr.list_read_watchpoints()]
        write_addrs = [addr for addr, cond in mgr.list_write_watchpoints()]
        assert 0x0050 not in read_addrs
        assert 0x0050 not in write_addrs

    def test_clear_watchpoints(self, mgr):
        """clear_watchpoints removes all."""
        mgr.add_read_watchpoint(0x0050)
        mgr.add_write_watchpoint(0x0060)
        mgr.clear_watchpoints()

        assert mgr.watchpoint_count == 0

    def test_check_memory_read(self, mgr, cpu):
        """check_memory_read triggers on watched address."""
        mgr.add_read_watchpoint(0x0050)

        result = mgr.check_memory_read(cpu, 0x0050, 0x42)

        assert result is False  # Should break
        assert mgr.last_event.reason == BreakReason.MEMORY_READ
        assert mgr.last_event.address == 0x0050
        assert mgr.last_event.value == 0x42

    def test_check_memory_read_unwatched(self, mgr, cpu):
        """check_memory_read passes unwatched address."""
        mgr.add_read_watchpoint(0x0050)

        result = mgr.check_memory_read(cpu, 0x0060, 0x42)

        assert result is True  # Continue

    def test_check_memory_write(self, mgr, cpu):
        """check_memory_write triggers on watched address."""
        mgr.add_write_watchpoint(0x0050)

        result = mgr.check_memory_write(cpu, 0x0050, 0x42)

        assert result is False  # Should break
        assert mgr.last_event.reason == BreakReason.MEMORY_WRITE

    def test_conditional_watchpoint(self, mgr, cpu):
        """Watchpoint with condition only fires when condition met."""
        mgr.add_write_watchpoint(0x0050, condition=("a", "==", 0x42))

        # Condition not met - should continue
        cpu.a = 0x00
        result = mgr.check_memory_write(cpu, 0x0050, 0xFF)
        assert result is True

        # Condition met - should break
        cpu.a = 0x42
        result = mgr.check_memory_write(cpu, 0x0050, 0xFF)
        assert result is False
        assert mgr.last_event.reason == BreakReason.MEMORY_WRITE


# =============================================================================
# Condition Tests
# =============================================================================

class TestCondition:
    """Test Condition class."""

    def test_create_condition(self):
        """Create basic condition."""
        cond = Condition('a', '==', 0x42)
        assert cond.register == 'a'
        assert cond.operator == '=='
        assert cond.value == 0x42

    def test_check_equal_true(self):
        """Condition checks equality correctly."""
        cpu = MockCPU()
        cpu.a = 0x42

        cond = Condition('a', '==', 0x42)
        assert cond.check(cpu) is True

    def test_check_equal_false(self):
        """Condition equality false."""
        cpu = MockCPU()
        cpu.a = 0x41

        cond = Condition('a', '==', 0x42)
        assert cond.check(cpu) is False

    def test_check_not_equal(self):
        """Condition != works."""
        cpu = MockCPU()
        cpu.a = 0x41

        cond = Condition('a', '!=', 0x42)
        assert cond.check(cpu) is True

    def test_check_less_than(self):
        """Condition < works."""
        cpu = MockCPU()
        cpu.a = 0x10

        cond = Condition('a', '<', 0x20)
        assert cond.check(cpu) is True

        cpu.a = 0x20
        assert cond.check(cpu) is False

    def test_check_less_equal(self):
        """Condition <= works."""
        cpu = MockCPU()
        cpu.a = 0x20

        cond = Condition('a', '<=', 0x20)
        assert cond.check(cpu) is True

    def test_check_greater_than(self):
        """Condition > works."""
        cpu = MockCPU()
        cpu.a = 0x30

        cond = Condition('a', '>', 0x20)
        assert cond.check(cpu) is True

    def test_check_greater_equal(self):
        """Condition >= works."""
        cpu = MockCPU()
        cpu.a = 0x20

        cond = Condition('a', '>=', 0x20)
        assert cond.check(cpu) is True

    def test_check_bitwise_and(self):
        """Condition & works (test bits set)."""
        cpu = MockCPU()
        cpu.a = 0b10101010

        # Test if bit 1 is set
        cond = Condition('a', '&', 0b00000010)
        assert cond.check(cpu) is True

        # Test if bit 0 is set (it's not)
        cond = Condition('a', '&', 0b00000001)
        assert cond.check(cpu) is False

    def test_16bit_register(self):
        """Condition on 16-bit register."""
        cpu = MockCPU()
        cpu.x = 0x1234

        cond = Condition('x', '==', 0x1234)
        assert cond.check(cpu) is True

    def test_flag_register(self):
        """Condition on flag register."""
        cpu = MockCPU()
        cpu.flag_z = True

        cond = Condition('flag_z', '==', True)
        assert cond.check(cpu) is True

    def test_invalid_register(self):
        """Invalid register name raises error."""
        with pytest.raises(ValueError):
            Condition('invalid_reg', '==', 0)

    def test_invalid_operator(self):
        """Invalid operator raises error."""
        with pytest.raises(ValueError):
            Condition('a', '??', 0)

    def test_case_insensitive_register(self):
        """Register names are case-insensitive."""
        cond = Condition('A', '==', 0x42)
        assert cond.register == 'a'

    def test_str_representation(self):
        """Condition has string representation."""
        cond = Condition('a', '==', 0x42)
        assert str(cond) == "a == 66"


# =============================================================================
# Syscall Hook Tests
# =============================================================================

class TestSyscallHooks:
    """Test syscall hook functionality."""

    @pytest.fixture
    def mgr(self):
        return BreakpointManager()

    def test_add_syscall_hook(self, mgr):
        """add_syscall_hook registers callback."""
        callback = lambda n, cpu: True
        mgr.add_syscall_hook(0x42, callback)
        # Hook is stored internally

    def test_remove_syscall_hook(self, mgr):
        """remove_syscall_hook removes callback."""
        callback = lambda n, cpu: True
        mgr.add_syscall_hook(0x42, callback)
        mgr.remove_syscall_hook(0x42)

    def test_clear_syscall_hooks(self, mgr):
        """clear_syscall_hooks removes all."""
        mgr.add_syscall_hook(0x42, lambda n, cpu: True)
        mgr.add_syscall_hook(0x43, lambda n, cpu: True)
        mgr.clear_syscall_hooks()


# =============================================================================
# Check Instruction Tests
# =============================================================================

class TestCheckInstruction:
    """Test check_instruction hook behavior."""

    @pytest.fixture
    def mgr(self):
        return BreakpointManager()

    @pytest.fixture
    def cpu(self):
        return MockCPU()

    def test_no_break(self, mgr, cpu):
        """No breakpoints means continue."""
        result = mgr.check_instruction(cpu, 0x8000, 0x01)
        assert result is True

    def test_pc_breakpoint_hit(self, mgr, cpu):
        """PC breakpoint stops execution."""
        mgr.add_breakpoint(0x8000)

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is False
        assert mgr.last_event.reason == BreakReason.PC_BREAKPOINT
        assert mgr.last_event.address == 0x8000

    def test_pc_breakpoint_miss(self, mgr, cpu):
        """PC breakpoint at different address continues."""
        mgr.add_breakpoint(0x9000)

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is True

    def test_step_mode_stops(self, mgr, cpu):
        """Step mode stops after one instruction."""
        mgr.step_mode = True

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is False
        assert mgr.last_event.reason == BreakReason.STEP
        assert mgr.step_mode is False  # Auto-cleared

    def test_conditional_breakpoint_met(self, mgr, cpu):
        """Conditional breakpoint stops when condition met."""
        cpu.a = 0x42
        mgr.add_breakpoint(0x8000, condition=("a", "==", 0x42))

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is False
        assert mgr.last_event.reason == BreakReason.PC_BREAKPOINT

    def test_conditional_breakpoint_not_met(self, mgr, cpu):
        """Conditional breakpoint continues when condition not met."""
        cpu.a = 0x00  # Condition not met
        mgr.add_breakpoint(0x8000, condition=("a", "==", 0x42))

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is True  # Continue, condition not met

    def test_syscall_hook_swi(self, mgr, cpu):
        """Syscall hook triggers on SWI instruction."""
        cpu.a = 0x10  # Syscall number

        hook_called = []
        def hook(syscall, cpu):
            hook_called.append(syscall)
            return False  # Stop

        mgr.add_syscall_hook(0x10, hook)

        # SWI opcode is 0x3F
        result = mgr.check_instruction(cpu, 0x8000, 0x3F)

        assert result is False
        assert hook_called == [0x10]
        assert mgr.last_event.reason == BreakReason.SYSCALL

    def test_syscall_hook_continue(self, mgr, cpu):
        """Syscall hook returning True continues."""
        cpu.a = 0x10

        mgr.add_syscall_hook(0x10, lambda n, cpu: True)

        result = mgr.check_instruction(cpu, 0x8000, 0x3F)

        assert result is True  # Hook returned True

    def test_break_request(self, mgr, cpu):
        """Break request stops execution."""
        mgr.request_break()

        result = mgr.check_instruction(cpu, 0x8000, 0x01)

        assert result is False
        assert mgr.last_event.reason == BreakReason.USER_INTERRUPT


# =============================================================================
# BreakEvent Tests
# =============================================================================

class TestBreakEvent:
    """Test BreakEvent dataclass."""

    def test_create_event(self):
        """Create basic event."""
        event = BreakEvent(BreakReason.PC_BREAKPOINT, address=0x8000)
        assert event.reason == BreakReason.PC_BREAKPOINT
        assert event.address == 0x8000

    def test_event_str(self):
        """Event has string representation."""
        event = BreakEvent(BreakReason.PC_BREAKPOINT, address=0x8000)
        s = str(event)
        assert '8000' in s.upper()

    def test_event_with_message(self):
        """Event with custom message."""
        event = BreakEvent(BreakReason.PC_BREAKPOINT, message="Custom message")
        assert str(event) == "Custom message"

    def test_memory_event(self):
        """Memory event with value."""
        event = BreakEvent(
            BreakReason.MEMORY_WRITE,
            address=0x0050,
            value=0x42
        )
        s = str(event)
        assert '0050' in s.upper() or '50' in s


# =============================================================================
# Clear All Tests
# =============================================================================

class TestClearAll:
    """Test clear_all functionality."""

    def test_clear_all(self):
        """clear_all removes everything."""
        mgr = BreakpointManager()

        # Add various things
        mgr.add_breakpoint(0x8000)
        mgr.add_watchpoint(0x0050, on_read=True, on_write=True)
        mgr.add_syscall_hook(0x10, lambda n, cpu: True)
        mgr.step_mode = True
        mgr.request_break()

        # Clear all
        mgr.clear_all()

        assert mgr.breakpoint_count == 0
        assert mgr.watchpoint_count == 0
        assert mgr.step_mode is False
