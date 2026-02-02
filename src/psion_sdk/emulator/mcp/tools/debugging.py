"""
MCP Debugging Tools
===================

Tools for breakpoints, disassembly, tracing, and register manipulation.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from typing import Any, Dict

from ..server import SessionManager, ToolResult
from .core import error_result, success_result
from .decorators import mcp_tool, requires_session
from .parsing import parse_address, parse_byte
from .session import OPL_SYSTEM_VARS


@mcp_tool
@requires_session
async def set_breakpoint(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Set a breakpoint or watchpoint with optional condition.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "type": str,           # "pc" (default), "read", or "write"
            "address": int|str,    # Memory address (required)
                                   # Accepts hex strings: "0x8100", "$8100"

            # Optional condition - break only fires when condition is also true:
            "when_register": str,  # a, b, d, x, sp, pc, flag_c, flag_v, flag_z, flag_n
            "when_op": str,        # ==, !=, <, <=, >, >=, &
            "when_value": int|str  # Accepts hex strings for value
        }

    Examples:
        - Simple: {type: "pc", address: "0x8000"}
        - Conditional: {type: "pc", address: "$8000", when_register: "a", when_op: "==", when_value: "0x42"}
          → Break at $8000 only when A == 0x42

    Returns:
        ToolResult indicating success
    """
    bp_type = args.get("type", "pc").lower()

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    # Build optional condition
    # The when_value parameter also supports hex strings for consistency
    condition = None
    when_register = args.get("when_register")
    when_op = args.get("when_op")
    raw_when_value = args.get("when_value")

    if when_register and when_op and raw_when_value is not None:
        # Parse when_value as 16-bit (for registers like x, sp, pc, d)
        # 8-bit registers (a, b, flags) will be masked by the breakpoint handler
        when_value = parse_address(raw_when_value, "when_value")
        condition = (when_register, when_op, when_value)

    emu = session.emulator

    if bp_type == "pc":
        emu.breakpoints.add_breakpoint(address, condition=condition)
        msg = f"Breakpoint set at ${address:04X}"
    elif bp_type == "read":
        emu.breakpoints.add_read_watchpoint(address, condition=condition)
        msg = f"Read watchpoint set at ${address:04X}"
    elif bp_type == "write":
        emu.breakpoints.add_write_watchpoint(address, condition=condition)
        msg = f"Write watchpoint set at ${address:04X}"
    else:
        return error_result(f"Unknown type: {bp_type}. Use pc, read, or write.")

    if condition:
        msg += f" (when {when_register} {when_op} {when_value})"

    return success_result(msg)


@mcp_tool
@requires_session
async def remove_breakpoint(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Remove a breakpoint or watchpoint at an address.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,    # Memory address (required)
                                   # Accepts hex strings: "0x8100", "$8100"
            "type": str            # "all" (default), "pc", "read", or "write"
        }

    Returns:
        ToolResult indicating what was removed
    """
    bp_type = args.get("type", "all").lower()

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    emu = session.emulator
    removed = []

    if bp_type in ("pc", "all"):
        if emu.breakpoints.has_breakpoint(address):
            emu.breakpoints.remove_breakpoint(address)
            removed.append("PC breakpoint")

    if bp_type in ("read", "all"):
        if address in emu.breakpoints._read_watchpoints:
            emu.breakpoints.remove_read_watchpoint(address)
            removed.append("read watchpoint")

    if bp_type in ("write", "all"):
        if address in emu.breakpoints._write_watchpoints:
            emu.breakpoints.remove_write_watchpoint(address)
            removed.append("write watchpoint")

    if removed:
        return success_result(
            f"Removed at ${address:04X}: {', '.join(removed)}"
        )
    else:
        return success_result(
            f"No breakpoints/watchpoints at ${address:04X}"
        )


@mcp_tool
@requires_session
async def list_breakpoints(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    List all active breakpoints and watchpoints.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with all active debugging points and their conditions
    """
    emu = session.emulator
    bp_mgr = emu.breakpoints
    result_lines = []

    def format_entry(addr: int, cond) -> str:
        """Format a breakpoint/watchpoint entry with optional condition."""
        if cond:
            return f"  ${addr:04X}  when {cond}"
        return f"  ${addr:04X}"

    # PC Breakpoints
    pc_breakpoints = bp_mgr.list_breakpoints()
    if pc_breakpoints:
        result_lines.append(f"PC Breakpoints ({len(pc_breakpoints)}):")
        for addr, cond in pc_breakpoints:
            result_lines.append(format_entry(addr, cond))
    else:
        result_lines.append("PC Breakpoints: (none)")

    # Read Watchpoints
    read_watchpoints = bp_mgr.list_read_watchpoints()
    if read_watchpoints:
        result_lines.append(f"\nRead Watchpoints ({len(read_watchpoints)}):")
        for addr, cond in read_watchpoints:
            result_lines.append(format_entry(addr, cond))
    else:
        result_lines.append("\nRead Watchpoints: (none)")

    # Write Watchpoints
    write_watchpoints = bp_mgr.list_write_watchpoints()
    if write_watchpoints:
        result_lines.append(f"\nWrite Watchpoints ({len(write_watchpoints)}):")
        for addr, cond in write_watchpoints:
            result_lines.append(format_entry(addr, cond))
    else:
        result_lines.append("\nWrite Watchpoints: (none)")

    # Summary
    total = len(pc_breakpoints) + len(read_watchpoints) + len(write_watchpoints)
    result_lines.append(f"\nTotal: {total} active")

    return success_result('\n'.join(result_lines))


@mcp_tool
@requires_session
async def get_registers(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Get current CPU register values.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with register values
    """
    emu = session.emulator
    regs = emu.registers

    return success_result(
        f"CPU Registers:\n"
        f"  A:  ${regs['a']:02X} ({regs['a']:3d})\n"
        f"  B:  ${regs['b']:02X} ({regs['b']:3d})\n"
        f"  D:  ${regs['d']:04X} ({regs['d']:5d})\n"
        f"  X:  ${regs['x']:04X}\n"
        f"  SP: ${regs['sp']:04X}\n"
        f"  PC: ${regs['pc']:04X}\n"
        f"Flags:\n"
        f"  C (Carry):     {regs['c']}\n"
        f"  V (Overflow):  {regs['v']}\n"
        f"  Z (Zero):      {regs['z']}\n"
        f"  N (Negative):  {regs['n']}\n"
        f"  I (Interrupt): {regs['i']}\n"
        f"  H (Half-Carry):{regs['h']}"
    )


@mcp_tool
@requires_session
async def set_registers(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Set CPU register values.

    Modify the HD6303 CPU registers directly. Useful for:
    - Setting up test conditions
    - Modifying execution flow
    - Injecting values for debugging

    Available registers:
        a, b: 8-bit accumulators (0-255)
        d: 16-bit combined A:B (0-65535) - sets both A and B
        x: 16-bit index register (0-65535)
        sp: 16-bit stack pointer (0-65535)
        pc: 16-bit program counter (0-65535)

    Note: Modifying PC will change where execution continues.
    Modifying SP can cause stack corruption if not careful.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "a": int|str,     # Optional: Set A register (0-255)
                              # Accepts hex strings: "0x42", "$42"
            "b": int|str,     # Optional: Set B register (0-255)
            "d": int|str,     # Optional: Set D register (0-65535), overrides a/b
            "x": int|str,     # Optional: Set X register (0-65535)
            "sp": int|str,    # Optional: Set SP register (0-65535)
            "pc": int|str     # Optional: Set PC register (0-65535)
        }

    Returns:
        ToolResult confirming changes
    """
    emu = session.emulator
    cpu = emu.cpu
    changes = []

    # Set D first (if specified) since it sets both A and B
    # parse_address handles 16-bit values, parse_byte handles 8-bit
    if "d" in args:
        d_val = parse_address(args["d"], "d")
        cpu.a = (d_val >> 8) & 0xFF
        cpu.b = d_val & 0xFF
        changes.append(f"D=${d_val:04X} (A=${cpu.a:02X}, B=${cpu.b:02X})")

    # Set individual 8-bit registers
    if "a" in args and "d" not in args:
        a_val = parse_byte(args["a"], "a")
        cpu.a = a_val
        changes.append(f"A=${a_val:02X}")

    if "b" in args and "d" not in args:
        b_val = parse_byte(args["b"], "b")
        cpu.b = b_val
        changes.append(f"B=${b_val:02X}")

    # Set 16-bit registers
    if "x" in args:
        x_val = parse_address(args["x"], "x")
        cpu.x = x_val
        changes.append(f"X=${x_val:04X}")

    if "sp" in args:
        sp_val = parse_address(args["sp"], "sp")
        cpu.sp = sp_val
        changes.append(f"SP=${sp_val:04X}")

    if "pc" in args:
        pc_val = parse_address(args["pc"], "pc")
        cpu.pc = pc_val
        changes.append(f"PC=${pc_val:04X}")

    if not changes:
        return error_result(
            "No registers specified. Use: a, b, d, x, sp, pc"
        )

    # Show final state
    regs = emu.registers
    result = "Registers modified:\n"
    result += "  " + ", ".join(changes) + "\n\n"
    result += "Current state:\n"
    result += f"  A=${regs['a']:02X} B=${regs['b']:02X} D=${regs['d']:04X}\n"
    result += f"  X=${regs['x']:04X} SP=${regs['sp']:04X} PC=${regs['pc']:04X}"

    return success_result(result)


@mcp_tool
@requires_session
async def disassemble(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Disassemble HD6303 machine code at a memory address.

    Reads memory from the emulator and disassembles it into HD6303
    assembly language mnemonics. Useful for understanding what machine
    code is executing, examining ROM routines, or debugging C-compiled code.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,   # Starting address to disassemble
                                  # Accepts hex strings: "0x8100", "$8100"
            "count": int,         # Number of instructions (default: 16)
            "show_bytes": bool    # Include raw bytes in output (default: True)
        }

    Returns:
        ToolResult with disassembly listing
    """
    count = args.get("count", 16)
    show_bytes = args.get("show_bytes", True)

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    # Validate count
    if count < 1 or count > 100:
        return error_result("Count must be 1-100")

    # Import disassembler
    from psion_sdk.disassembler import HD6303Disassembler

    emu = session.emulator

    # Read enough bytes for disassembly (max 3 bytes per instruction)
    max_bytes = min(count * 3, 0x10000 - address)
    data = emu.read_bytes(address, max_bytes)

    # Disassemble
    disasm = HD6303Disassembler()
    instructions = disasm.disassemble(data, start_address=address, count=count)

    # Format output
    result_lines = [f"Disassembly at ${address:04X} ({count} instructions):"]
    result_lines.append("")

    for instr in instructions:
        if show_bytes:
            result_lines.append(str(instr))
        else:
            # Compact format without bytes
            if instr.operand_str:
                line = f"${instr.address:04X}: {instr.mnemonic} {instr.operand_str}"
            else:
                line = f"${instr.address:04X}: {instr.mnemonic}"
            if instr.comment:
                line += f"  ; {instr.comment}"
            result_lines.append(line)

    return success_result('\n'.join(result_lines))


@mcp_tool
@requires_session
async def disassemble_qcode(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Disassemble OPL QCode bytecode at a memory address.

    QCode is the bytecode format used by the Psion OPL interpreter.
    This tool decodes QCode opcodes into human-readable form, which is
    essential for:
    - Understanding OPL procedure behavior
    - Debugging _call_opl QCode injection buffers
    - Analyzing QCode stored in memory

    Key QCode opcodes:
        $7D = QCO_PROC (procedure call)
        $22 = Push 16-bit integer
        $9F = USR() function call
        $7B = RETURN
        $59 $B2 = LZ 4-line mode prefix (STOP+SIN)

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "address": int|str,   # Starting address
                                  # Accepts hex strings: "0x8100", "$8100"
            "count": int,         # Number of opcodes (default: 16)
            "call_opl_mode": bool # Special formatting for _call_opl buffers
        }

    Returns:
        ToolResult with QCode disassembly
    """
    count = args.get("count", 16)
    call_opl_mode = args.get("call_opl_mode", False)

    # Parse and validate address (supports hex strings like "0x8100" or "$8100")
    address = parse_address(args.get("address"), "address")

    # Validate count
    if count < 1 or count > 100:
        return error_result("Count must be 1-100")

    # Import disassembler
    from psion_sdk.disassembler import QCodeDisassembler

    emu = session.emulator

    # Read bytes - QCode can have variable-length instructions
    max_bytes = min(count * 12, 0x10000 - address)  # 12 bytes max per QCode
    data = emu.read_bytes(address, max_bytes)

    # Disassemble
    disasm = QCodeDisassembler()

    if call_opl_mode:
        # Special formatting for _call_opl buffers
        result = disasm.disassemble_call_opl_buffer(data, start_address=address)
    else:
        # Normal disassembly
        instructions = disasm.disassemble(data, start_address=address, count=count)
        result_lines = [f"QCode Disassembly at ${address:04X}:"]
        result_lines.append("")
        for instr in instructions:
            result_lines.append(str(instr))
        result = '\n'.join(result_lines)

    return success_result(result)


@mcp_tool
@requires_session
async def run_with_trace(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Run emulator with instruction tracing.

    Executes the emulator while recording the last N instructions executed.
    This is invaluable for debugging complex execution flows where you need
    to understand exactly what code path was taken.

    The trace captures:
    - PC address for each instruction
    - Optionally: full register state at each step

    Use this when:
    - Debugging why _call_opl_restore is never reached
    - Understanding QCO_PROC handler behavior
    - Tracing OPL interpreter dispatch

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "max_cycles": int,        # Max cycles to run (default: 100000)
            "trace_depth": int,       # Instructions to keep in trace (default: 50)
            "stop_address": int|str,  # Optional: stop when PC reaches this address
                                      # Accepts hex strings: "0x8100", "$8100"
            "include_registers": bool # Include full registers in trace (default: False)
        }

    Returns:
        ToolResult with execution trace
    """
    max_cycles = args.get("max_cycles", 100_000)
    trace_depth = args.get("trace_depth", 50)
    raw_stop_address = args.get("stop_address", None)
    include_registers = args.get("include_registers", False)

    # Parse optional stop_address (supports hex strings like "0x8100" or "$8100")
    stop_address = None
    if raw_stop_address is not None:
        stop_address = parse_address(raw_stop_address, "stop_address")

    # Validate
    if trace_depth < 1 or trace_depth > 1000:
        return error_result("trace_depth must be 1-1000")
    if max_cycles < 1 or max_cycles > 10_000_000:
        return error_result("max_cycles must be 1-10000000")

    emu = session.emulator
    trace = []
    cycles_run = 0
    hit_stop_address = False

    # Step through execution, recording trace
    while cycles_run < max_cycles:
        pc = emu.cpu.pc

        # Check stop condition
        if stop_address is not None and pc == stop_address:
            hit_stop_address = True
            break

        # Record trace entry
        if include_registers:
            regs = emu.registers
            entry = {
                "pc": pc,
                "a": regs["a"],
                "b": regs["b"],
                "x": regs["x"],
                "sp": regs["sp"],
            }
        else:
            entry = {"pc": pc}

        trace.append(entry)

        # Keep only last N entries
        if len(trace) > trace_depth:
            trace.pop(0)

        # Execute one instruction
        event = emu.step()
        cycles_run += 1

        # Check for breakpoints
        if event.reason.name != "MAX_CYCLES":
            break

    # Format output
    result_lines = [f"Execution Trace (last {len(trace)} instructions):"]
    result_lines.append(f"Cycles executed: {cycles_run:,}")

    if hit_stop_address:
        result_lines.append(f"Stopped at target address: ${stop_address:04X}")

    result_lines.append("")

    # Try to disassemble trace entries
    try:
        from psion_sdk.disassembler import HD6303Disassembler
        disasm = HD6303Disassembler()
        has_disasm = True
    except ImportError:
        has_disasm = False

    for i, entry in enumerate(trace):
        pc = entry["pc"]

        if has_disasm:
            # Read a few bytes and disassemble
            data = emu.read_bytes(pc, 3)
            instr = disasm.disassemble_one(data, address=pc)
            if instr.operand_str:
                asm = f"{instr.mnemonic} {instr.operand_str}"
            else:
                asm = instr.mnemonic
        else:
            asm = ""

        if include_registers:
            line = (
                f"[{i:3d}] ${pc:04X}: {asm:<16} "
                f"A=${entry['a']:02X} B=${entry['b']:02X} "
                f"X=${entry['x']:04X} SP=${entry['sp']:04X}"
            )
        else:
            line = f"[{i:3d}] ${pc:04X}: {asm}"

        result_lines.append(line)

    return success_result('\n'.join(result_lines))


@mcp_tool
@requires_session
async def step_with_disasm(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Execute a single CPU instruction with disassembly output.

    Enhanced version of 'step' that shows the disassembled instruction
    that was just executed, along with full register state.

    This provides much better visibility than the basic step command
    when tracing through code.

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {
            "session_id": str,
            "count": int          # Number of steps (default: 1, max: 100)
        }

    Returns:
        ToolResult with disassembled instruction(s) and register state
    """
    count = args.get("count", 1)

    # Validate
    if count < 1 or count > 100:
        return error_result("Count must be 1-100")

    # Import disassembler
    try:
        from psion_sdk.disassembler import HD6303Disassembler
        disasm = HD6303Disassembler()
        has_disasm = True
    except ImportError:
        has_disasm = False

    emu = session.emulator
    result_lines = []

    for i in range(count):
        pc_before = emu.cpu.pc

        # Get instruction bytes before stepping
        if has_disasm:
            data = emu.read_bytes(pc_before, 3)
            instr = disasm.disassemble_one(data, address=pc_before)
            instr_str = str(instr)
        else:
            opcode = emu.read_bytes(pc_before, 1)[0]
            instr_str = f"${pc_before:04X}: ${opcode:02X}"

        # Step
        event = emu.step()

        # Get register state after
        regs = emu.registers
        flags = f"Z={regs['z']} N={regs['n']} C={regs['c']} V={regs['v']}"

        # Format output
        result_lines.append(instr_str)
        result_lines.append(
            f"        → A=${regs['a']:02X} B=${regs['b']:02X} "
            f"X=${regs['x']:04X} SP=${regs['sp']:04X} [{flags}]"
        )

        # Stop early on breakpoint
        if event.reason.name != "MAX_CYCLES":
            result_lines.append(f"        Stop: {event.reason.name}")
            break

    if count > 1:
        result_lines.insert(0, f"Executed {min(i+1, count)} instruction(s):\n")

    return success_result('\n'.join(result_lines))


@mcp_tool
@requires_session
async def get_opl_state(
    session,
    manager: SessionManager,
    args: Dict[str, Any]
) -> ToolResult:
    """
    Read OPL interpreter system variables.

    This tool provides quick access to the key OPL runtime variables that
    control QCode execution. Essential for debugging procedure calls and
    the _call_opl QCode injection mechanism.

    The addresses are STABLE across all Psion II models.

    Variables returned:
        RTA_SP ($A5/$A6): Language expression stack pointer
        RTA_FP ($A7/$A8): Current procedure frame pointer
        RTA_PC ($A9/$AA): QCode program counter (current execution point)
        DEFAULT_DEV ($B5): Default device letter for procedure lookup

    Args:
        session: Emulator session (injected by @requires_session)
        manager: Session manager
        args: {"session_id": str}

    Returns:
        ToolResult with OPL interpreter state
    """
    emu = session.emulator
    result_lines = ["OPL Interpreter State:"]
    result_lines.append("=" * 50)

    for name, (addr, size, desc) in OPL_SYSTEM_VARS.items():
        if size == 1:
            value = emu.read_bytes(addr, 1)[0]
            # Show ASCII for device letter
            if name == "DEFAULT_DEV" and 0x41 <= value <= 0x5A:
                result_lines.append(
                    f"  {name:12} ${addr:02X}     = ${value:02X} ('{chr(value)}')"
                )
            else:
                result_lines.append(
                    f"  {name:12} ${addr:02X}     = ${value:02X}"
                )
        else:
            # 16-bit value (big-endian in memory for these vars)
            hi = emu.read_bytes(addr, 1)[0]
            lo = emu.read_bytes(addr + 1, 1)[0]
            value = (hi << 8) | lo
            result_lines.append(
                f"  {name:12} ${addr:02X}/${addr+1:02X}  = ${value:04X}"
            )

    result_lines.append("")
    result_lines.append("Description:")
    for name, (addr, size, desc) in OPL_SYSTEM_VARS.items():
        result_lines.append(f"  {name}: {desc}")

    return success_result('\n'.join(result_lines))
