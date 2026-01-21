"""
HD6303 Assembly Peephole Optimizer
===================================

This module implements safe, conservative peephole optimizations for HD6303
assembly code. It operates on parsed Statement objects from the parser,
transforming instruction sequences to produce smaller or faster code.

Design Philosophy
-----------------
The optimizer follows these principles:

1. **Safety First**: Only apply optimizations that are provably correct.
   Never optimize if there's any doubt about correctness.

2. **Conservative**: Prefer correctness over aggressive optimization.
   Missing an optimization is acceptable; breaking code is not.

3. **Transparent**: All optimizations are clearly documented with the
   patterns they match and the transformations they apply.

4. **Label-Aware**: Never optimize across labels or branch targets, as
   the label might be a jump target from elsewhere in the program.

5. **Side-Effect Aware**: Consider instruction side effects (flags, memory)
   when determining if optimizations are safe.

Supported Optimizations
-----------------------
1. **Compare Zero**: CMPA #0 → TSTA, CMPB #0 → TSTB (saves 1 byte)
2. **Redundant Load**: Consecutive identical loads → keep only first
3. **Push/Pull Pairs**: Adjacent PSHA/PULA, PSHB/PULB, PSHX/PULX → remove both
4. **Redundant TSX**: Consecutive TSX instructions → keep only last
5. **Dead Code**: Unreachable instructions after unconditional branches

Flag Safety Note
----------------
Some common "optimizations" are intentionally NOT implemented because they
change CPU flag behavior, which can break code that depends on specific flags:

- LDAA #0 → CLRA: CLR clears Carry, LD doesn't affect it
- ADDA #1 → INCA: INC doesn't set Carry, ADD does
- SUBA #1 → DECA: DEC doesn't set Carry, SUB does

The optimizations above are flag-safe: CMPA #0 and TSTA both set N, Z, V
identically (V=0, N and Z based on A value). CMP clears C while TST doesn't
modify C, but this is safe because code using CMP #0 for flags uses N/Z.

Architecture
------------
The optimizer uses a multi-pass peephole approach:

1. **Single-instruction pass**: Transform individual instructions
   (e.g., CMPA #0 → TSTA)

2. **Two-instruction pass**: Transform instruction pairs
   (e.g., PSHA + PULA → nothing)

3. **Dead code elimination**: Remove unreachable code after unconditional
   branches (only within basic blocks)

Passes run iteratively until no more changes are made (fixpoint).

Usage
-----
>>> from psion_sdk.assembler.parser import parse_source
>>> from psion_sdk.assembler.optimizer import PeepholeOptimizer
>>> statements = parse_source(source)
>>> optimizer = PeepholeOptimizer()
>>> optimized = optimizer.optimize(statements)

The optimizer can be disabled by passing enable=False to the constructor,
which returns statements unchanged.

Limitations
-----------
- Does not perform data flow analysis (would require full CFG construction)
- Does not optimize across basic block boundaries (labels)
- Does not optimize code involving macro expansions (macros expand first)
- Does not track register values through function calls

These limitations are intentional to keep the optimizer simple and safe.

Copyright (c) 2025-2026 Hugo Jose Pinto & Contributors
"""

from dataclasses import dataclass, field
from typing import Optional
from copy import deepcopy

from psion_sdk.assembler.parser import (
    Statement,
    Instruction,
    LabelDef,
    Directive,
    Operand,
    ParsedAddressingMode,
    MacroDef,
    MacroCall,
    ConditionalBlock,
)
from psion_sdk.assembler.lexer import Token, TokenType
from psion_sdk.cpu import UNCONDITIONAL_BRANCHES


# =============================================================================
# Optimization Statistics
# =============================================================================

@dataclass
class OptimizationStats:
    """
    Statistics about optimizations performed.

    Used for reporting and debugging to understand what the optimizer did.

    Attributes:
        compare_zero: Count of CMP #0 → TST transformations
        redundant_load: Count of redundant loads removed
        push_pull_pairs: Count of push/pull pairs eliminated
        redundant_tsx: Count of redundant TSX instructions removed
        dead_code: Count of unreachable instructions removed
        total_passes: Number of optimization passes run
    """
    compare_zero: int = 0
    redundant_load: int = 0
    push_pull_pairs: int = 0
    redundant_tsx: int = 0
    dead_code: int = 0
    total_passes: int = 0

    @property
    def total_optimizations(self) -> int:
        """Total number of individual optimizations applied."""
        return (
            self.compare_zero +
            self.redundant_load +
            self.push_pull_pairs +
            self.redundant_tsx +
            self.dead_code
        )

    def __str__(self) -> str:
        """Human-readable summary of optimizations."""
        lines = ["Optimization Statistics:"]
        if self.compare_zero:
            lines.append(f"  Compare zero (CMPx #0 → TSTx): {self.compare_zero}")
        if self.redundant_load:
            lines.append(f"  Redundant loads removed: {self.redundant_load}")
        if self.push_pull_pairs:
            lines.append(f"  Push/pull pairs eliminated: {self.push_pull_pairs}")
        if self.redundant_tsx:
            lines.append(f"  Redundant TSX removed: {self.redundant_tsx}")
        if self.dead_code:
            lines.append(f"  Dead code removed: {self.dead_code}")
        lines.append(f"  Total optimizations: {self.total_optimizations}")
        lines.append(f"  Total passes: {self.total_passes}")
        return "\n".join(lines)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_immediate_value(operand: Optional[Operand]) -> Optional[int]:
    """
    Extract the immediate value from an operand, if it's a simple immediate.

    Args:
        operand: The instruction operand

    Returns:
        The immediate value as an integer, or None if not a simple immediate.
        Only handles literal numbers, not expressions or symbols.
    """
    if operand is None:
        return None
    if operand.mode != ParsedAddressingMode.IMMEDIATE:
        return None
    if len(operand.tokens) != 1:
        return None

    token = operand.tokens[0]
    if token.type == TokenType.NUMBER:
        return token.value
    return None


def _is_inherent(operand: Optional[Operand]) -> bool:
    """Check if an operand is inherent mode (no operand)."""
    return operand is None or operand.mode == ParsedAddressingMode.INHERENT


def _operands_match(op1: Optional[Operand], op2: Optional[Operand]) -> bool:
    """
    Check if two operands are semantically identical.

    Used for detecting redundant operations like consecutive identical loads.
    This is conservative - it only returns True for simple cases where we
    can be certain the operands are the same.

    Args:
        op1: First operand
        op2: Second operand

    Returns:
        True if operands are definitely identical, False if uncertain or different.
    """
    # Both inherent (no operand)
    if _is_inherent(op1) and _is_inherent(op2):
        return True

    # One inherent, one not
    if _is_inherent(op1) != _is_inherent(op2):
        return False

    # Both have operands
    if op1.mode != op2.mode:
        return False

    # Compare token sequences
    if len(op1.tokens) != len(op2.tokens):
        return False

    for t1, t2 in zip(op1.tokens, op2.tokens):
        if t1.type != t2.type:
            return False
        if t1.value != t2.value:
            return False

    # Check force flags
    if op1.is_force_direct != op2.is_force_direct:
        return False
    if op1.is_force_extended != op2.is_force_extended:
        return False

    return True


def _make_inherent_instruction(mnemonic: str, location) -> Instruction:
    """Create an inherent-mode instruction (no operand)."""
    return Instruction(
        location=location,
        mnemonic=mnemonic,
        operand=Operand(mode=ParsedAddressingMode.INHERENT)
    )


# =============================================================================
# Peephole Optimizer
# =============================================================================

class PeepholeOptimizer:
    """
    Peephole optimizer for HD6303 assembly code.

    The optimizer transforms sequences of instructions to produce more
    efficient code. It works on parsed Statement objects and preserves
    the semantic meaning of the program.

    Attributes:
        enabled: Whether optimization is enabled
        verbose: Whether to print optimization statistics
        stats: Statistics about optimizations performed
        max_passes: Maximum number of optimization passes (prevents infinite loops)
    """

    # Instructions that end a basic block (unconditional control flow transfer)
    # After these, subsequent code is only reachable via a label.
    #
    # NOTE: SWI and WAI are NOT in this list because:
    #   - SWI (Software Interrupt) returns to the next instruction after
    #     the OS call completes - it's like a function call, not a branch
    #   - WAI (Wait for Interrupt) suspends execution until an interrupt
    #     occurs, but then continues from the next instruction
    #
    # Only truly unconditional transfers that never return go here.
    BLOCK_ENDING = frozenset({
        "JMP",  # Unconditional jump - never returns
        "RTS",  # Return from subroutine - never returns (to this code)
        "RTI",  # Return from interrupt - never returns (to this code)
        "BRA",  # Unconditional branch - always taken
    })

    # Push/pull pairs that can be eliminated
    PUSH_PULL_PAIRS = {
        "PSHA": "PULA",
        "PSHB": "PULB",
        "PSHX": "PULX",
    }

    # NOTE: Transfer pairs (TAB+TBA, TBA+TAB) are NOT optimized because
    # while the first register is restored, the second register IS changed.
    # Example: TAB+TBA with A=5,B=10 → ends with A=5,B=5 (B changed!)
    # This is NOT a no-op and cannot be safely removed.

    def __init__(
        self,
        enabled: bool = True,
        verbose: bool = False,
        max_passes: int = 10
    ):
        """
        Initialize the optimizer.

        Args:
            enabled: If False, optimize() returns statements unchanged
            verbose: If True, print optimization statistics
            max_passes: Maximum optimization passes to prevent infinite loops
        """
        self.enabled = enabled
        self.verbose = verbose
        self.max_passes = max_passes
        self.stats = OptimizationStats()

    def optimize(self, statements: list[Statement]) -> list[Statement]:
        """
        Optimize a list of statements.

        Runs peephole optimization passes until no more improvements can be
        made or max_passes is reached.

        Args:
            statements: List of parsed statements

        Returns:
            Optimized list of statements (may be shorter)
        """
        if not self.enabled:
            return statements

        # Reset statistics
        self.stats = OptimizationStats()

        # Work on a copy to avoid modifying the original
        result = list(statements)

        # Run optimization passes until fixpoint
        for pass_num in range(self.max_passes):
            self.stats.total_passes += 1

            changes_before = self.stats.total_optimizations

            # Run each optimization type
            result = self._single_instruction_pass(result)
            result = self._two_instruction_pass(result)
            result = self._dead_code_pass(result)

            # Check for fixpoint (no changes this pass)
            if self.stats.total_optimizations == changes_before:
                break

        if self.verbose and self.stats.total_optimizations > 0:
            print(str(self.stats))

        return result

    # =========================================================================
    # Single-Instruction Optimizations
    # =========================================================================

    def _single_instruction_pass(
        self,
        statements: list[Statement]
    ) -> list[Statement]:
        """
        Apply single-instruction optimizations.

        These transform individual instructions without looking at context.

        Optimizations:
        - CMPA #0 → TSTA (saves 1 byte, flag-safe)
        - CMPB #0 → TSTB (saves 1 byte, flag-safe)

        Note: Many common "optimizations" are intentionally NOT implemented
        because they change CPU flag behavior:
        - LDAA #0 → CLRA: CLR clears Carry, LD doesn't affect Carry
        - ADDA #1 → INCA: INC doesn't set Carry, ADD does
        - SUBA #1 → DECA: DEC doesn't set Carry, SUB does

        The CMP #0 → TST optimization is safe because:
        - Both set N and Z based on the register value
        - Both set V = 0
        - CMP clears C while TST doesn't modify C, but code using CMP #0
          for comparison purposes uses N/Z flags, not C
        """
        result: list[Statement] = []

        for stmt in statements:
            if not isinstance(stmt, Instruction):
                result.append(stmt)
                continue

            mnemonic = stmt.mnemonic
            imm_value = _get_immediate_value(stmt.operand)

            # CMPA #0 → TSTA (flag-safe: both set N, Z based on A; V=0)
            if mnemonic == "CMPA" and imm_value == 0:
                result.append(_make_inherent_instruction("TSTA", stmt.location))
                self.stats.compare_zero += 1
                continue

            # CMPB #0 → TSTB (flag-safe: both set N, Z based on B; V=0)
            if mnemonic == "CMPB" and imm_value == 0:
                result.append(_make_inherent_instruction("TSTB", stmt.location))
                self.stats.compare_zero += 1
                continue

            # No optimization applied - keep original
            result.append(stmt)

        return result

    # =========================================================================
    # Two-Instruction Optimizations
    # =========================================================================

    def _two_instruction_pass(
        self,
        statements: list[Statement]
    ) -> list[Statement]:
        """
        Apply two-instruction peephole optimizations.

        These look at consecutive instruction pairs and optimize them.

        Optimizations:
        - PSHA + PULA → nothing (stack unchanged, A unchanged)
        - PSHB + PULB → nothing
        - PSHX + PULX → nothing
        - Consecutive identical loads → keep only first
        - Consecutive TSX → keep only last

        NOT optimized (unsafe):
        - TAB + TBA: While A is unchanged, B IS changed (B gets A's value)

        Important: Never optimize across labels, as they may be branch targets.
        """
        if len(statements) < 2:
            return statements

        result: list[Statement] = []
        i = 0

        while i < len(statements):
            stmt1 = statements[i]

            # If current is not an instruction, can't optimize
            if not isinstance(stmt1, Instruction):
                result.append(stmt1)
                i += 1
                continue

            # If next statement doesn't exist or is not an instruction, can't optimize
            if i + 1 >= len(statements):
                result.append(stmt1)
                i += 1
                continue

            stmt2 = statements[i + 1]

            # Never optimize across labels - they may be branch targets
            if isinstance(stmt2, LabelDef):
                result.append(stmt1)
                i += 1
                continue

            if not isinstance(stmt2, Instruction):
                result.append(stmt1)
                i += 1
                continue

            # Check for push/pull pairs
            if stmt1.mnemonic in self.PUSH_PULL_PAIRS:
                expected_pull = self.PUSH_PULL_PAIRS[stmt1.mnemonic]
                if stmt2.mnemonic == expected_pull:
                    # Both have inherent operands by definition
                    # Remove both instructions
                    self.stats.push_pull_pairs += 1
                    i += 2  # Skip both
                    continue

            # NOTE: Transfer pairs (TAB+TBA) are NOT optimized - see class comment

            # Check for consecutive identical loads
            # e.g., LDAA $40 followed by LDAA $40
            if stmt1.mnemonic == stmt2.mnemonic and stmt1.mnemonic.startswith("LD"):
                if _operands_match(stmt1.operand, stmt2.operand):
                    # Second load is redundant
                    result.append(stmt1)
                    self.stats.redundant_load += 1
                    i += 2  # Skip second instruction
                    continue

            # Check for consecutive TSX (frame pointer restore)
            # Second TSX makes first redundant
            if stmt1.mnemonic == "TSX" and stmt2.mnemonic == "TSX":
                # Skip first TSX, keep second
                self.stats.redundant_tsx += 1
                i += 1  # Only skip first, second will be kept in next iteration
                continue

            # No optimization - keep first instruction
            result.append(stmt1)
            i += 1

        return result

    # =========================================================================
    # Dead Code Elimination
    # =========================================================================

    def _dead_code_pass(self, statements: list[Statement]) -> list[Statement]:
        """
        Remove unreachable code after unconditional control transfers.

        Code after JMP, RTS, RTI, or unconditional BRA is unreachable
        unless there's a label making it a branch target.

        This is conservative - we only remove code within the same basic
        block (i.e., until the next label).

        IMPORTANT: Only Instructions are removed as dead code. Directives
        (like INCLUDE, EQU, FCB, etc.) are always preserved because:
        - INCLUDE directives need to be processed during code generation
        - Data directives (FCB, FDB, FCC) may be referenced by other code
        - EQU/SET directives define symbols that may be needed elsewhere

        Example:
            JMP done
            LDAA #5   ; This is unreachable - REMOVED
            STAA foo  ; This too - REMOVED
            FCB $00   ; This is a directive - PRESERVED
        done:
            ...       ; This is reachable (has label)
        """
        result: list[Statement] = []
        skip_until_label = False

        for stmt in statements:
            # Labels end the unreachable region
            if isinstance(stmt, LabelDef):
                skip_until_label = False
                result.append(stmt)
                continue

            # Non-instruction statements are ALWAYS preserved (never considered dead code)
            # This includes:
            # - Directives (INCLUDE, FCB, FDB, EQU, etc.) - needed for code generation
            # - MacroDef/MacroCall - macro processing happens elsewhere
            # - ConditionalBlock - conditional assembly processing happens elsewhere
            if not isinstance(stmt, Instruction):
                result.append(stmt)
                continue

            # If we're skipping unreachable code, count it (only for Instructions)
            if skip_until_label:
                if isinstance(stmt, Instruction):
                    self.stats.dead_code += 1
                continue

            # Check for unconditional control transfer
            if isinstance(stmt, Instruction):
                mnemonic = stmt.mnemonic

                # Handle unconditional branches (BRA converts to this check)
                if mnemonic in self.BLOCK_ENDING:
                    result.append(stmt)
                    skip_until_label = True
                    continue

            result.append(stmt)

        return result


# =============================================================================
# Convenience Function
# =============================================================================

def optimize_statements(
    statements: list[Statement],
    enabled: bool = True,
    verbose: bool = False
) -> tuple[list[Statement], OptimizationStats]:
    """
    Convenience function to optimize statements.

    Args:
        statements: List of parsed statements
        enabled: Whether to apply optimizations
        verbose: Whether to print statistics

    Returns:
        Tuple of (optimized statements, optimization statistics)
    """
    optimizer = PeepholeOptimizer(enabled=enabled, verbose=verbose)
    result = optimizer.optimize(statements)
    return result, optimizer.stats
