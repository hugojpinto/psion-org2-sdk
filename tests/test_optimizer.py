# =============================================================================
# test_optimizer.py - Peephole Optimizer Tests
# =============================================================================
# Tests for the HD6303 assembly peephole optimizer.
#
# The optimizer applies safe transformations to reduce code size and improve
# performance. These tests verify:
#   - Individual optimizations work correctly
#   - Optimizations don't break code semantics
#   - Optimization can be disabled
#   - Statistics are tracked correctly
#   - Labels are respected (no optimization across labels)
# =============================================================================

import pytest
from psion_sdk.assembler import Assembler, PeepholeOptimizer, OptimizationStats
from psion_sdk.assembler.parser import parse_source, Instruction, LabelDef
from psion_sdk.assembler.optimizer import optimize_statements


# =============================================================================
# Single-Instruction Optimization Tests
# =============================================================================

class TestCompareZeroOptimization:
    """Test CMPA #0 -> TSTA optimization."""

    def test_cmpa_zero_to_tsta(self):
        """CMPA #0 should become TSTA."""
        source = "CMPA #0"
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "TSTA"
        assert optimizer.stats.compare_zero == 1

    def test_cmpb_zero_to_tstb(self):
        """CMPB #0 should become TSTB."""
        source = "CMPB #0"
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "TSTB"
        assert optimizer.stats.compare_zero == 1

    def test_cmpa_nonzero_unchanged(self):
        """CMPA #5 should remain unchanged."""
        source = "CMPA #5"
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "CMPA"
        assert optimizer.stats.compare_zero == 0


# =============================================================================
# Two-Instruction Optimization Tests
# =============================================================================

class TestPushPullElimination:
    """Test push/pull pair elimination."""

    def test_psha_pula_eliminated(self):
        """PSHA + PULA should be eliminated."""
        source = """
            PSHA
            PULA
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 0
        assert optimizer.stats.push_pull_pairs == 1

    def test_pshb_pulb_eliminated(self):
        """PSHB + PULB should be eliminated."""
        source = """
            PSHB
            PULB
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 0
        assert optimizer.stats.push_pull_pairs == 1

    def test_pshx_pulx_eliminated(self):
        """PSHX + PULX should be eliminated."""
        source = """
            PSHX
            PULX
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 0
        assert optimizer.stats.push_pull_pairs == 1

    def test_psha_pulb_not_eliminated(self):
        """PSHA + PULB should NOT be eliminated (different registers)."""
        source = """
            PSHA
            PULB
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 2
        assert optimizer.stats.push_pull_pairs == 0


class TestTransferNotOptimized:
    """
    Verify that transfer pairs are NOT optimized.

    TAB+TBA is NOT a no-op: while A is restored, B is changed.
    Example: A=5,B=10 → TAB makes B=5 → TBA leaves A=5 → Final: A=5,B=5
    B has changed from 10 to 5!
    """

    def test_tab_tba_not_eliminated(self):
        """TAB + TBA should NOT be eliminated (B is changed!)."""
        source = """
            TAB
            TBA
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 2  # Both instructions remain
        assert instructions[0].mnemonic == "TAB"
        assert instructions[1].mnemonic == "TBA"


class TestRedundantLoadElimination:
    """Test consecutive identical load elimination."""

    def test_consecutive_ldaa_eliminated(self):
        """Two identical LDAA should be merged to one."""
        source = """
            LDAA #$42
            LDAA #$42
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "LDAA"
        assert optimizer.stats.redundant_load == 1

    def test_different_ldaa_not_eliminated(self):
        """Two different LDAA should both remain."""
        source = """
            LDAA #$42
            LDAA #$43
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 2
        assert optimizer.stats.redundant_load == 0


class TestRedundantTSXElimination:
    """Test consecutive TSX elimination."""

    def test_consecutive_tsx_eliminated(self):
        """Two TSX should be reduced to one."""
        source = """
            TSX
            TSX
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "TSX"
        assert optimizer.stats.redundant_tsx == 1


# =============================================================================
# Label Preservation Tests
# =============================================================================

class TestLabelPreservation:
    """Test that optimizations don't break label behavior."""

    def test_no_optimization_across_labels(self):
        """PSHA + label + PULA should NOT be eliminated."""
        source = """
            PSHA
        target:
            PULA
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        labels = [s for s in result if isinstance(s, LabelDef)]

        # Both instructions should remain (label in between)
        assert len(instructions) == 2
        assert len(labels) == 1
        assert optimizer.stats.push_pull_pairs == 0

    def test_labels_preserved(self):
        """Labels should be preserved after optimization."""
        source = """
        start:
            CMPA #0
            NOP
        end:
            RTS
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        labels = [s for s in result if isinstance(s, LabelDef)]
        assert len(labels) == 2
        assert labels[0].name == "start"
        assert labels[1].name == "end"


# =============================================================================
# Dead Code Elimination Tests
# =============================================================================

class TestDeadCodeElimination:
    """Test removal of unreachable code after unconditional branches."""

    def test_dead_code_after_jmp_removed(self):
        """Code after JMP should be removed (if no label before it)."""
        source = """
            JMP done
            NOP
            NOP
        done:
            RTS
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        # Should have: JMP, RTS (2 NOPs removed)
        assert len(instructions) == 2
        mnemonics = [i.mnemonic for i in instructions]
        assert "JMP" in mnemonics
        assert "RTS" in mnemonics
        assert "NOP" not in mnemonics
        assert optimizer.stats.dead_code == 2

    def test_dead_code_after_rts_removed(self):
        """Code after RTS should be removed (if no label before it)."""
        source = """
            RTS
            NOP
        done:
            RTS
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        # Should have: RTS, RTS (1 NOP removed)
        assert len(instructions) == 2
        assert optimizer.stats.dead_code == 1

    def test_label_stops_dead_code_elimination(self):
        """Code after unconditional branch is NOT dead if preceded by label."""
        source = """
            JMP skip
        reachable:
            NOP
        skip:
            RTS
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        # All instructions should remain (label makes NOP reachable)
        assert len(instructions) == 3
        assert optimizer.stats.dead_code == 0


# =============================================================================
# Optimizer Control Tests
# =============================================================================

class TestOptimizerControl:
    """Test optimizer enable/disable and configuration."""

    def test_optimizer_disabled(self):
        """When disabled, no optimizations should be applied."""
        source = "CMPA #0"
        statements = parse_source(source)
        optimizer = PeepholeOptimizer(enabled=False)
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        # Should still be CMPA, not TSTA
        assert instructions[0].mnemonic == "CMPA"
        assert optimizer.stats.total_optimizations == 0

    def test_statistics_tracking(self):
        """Statistics should accurately track optimizations."""
        source = """
            CMPA #0
            CMPB #0
            PSHA
            PULA
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        assert optimizer.stats.compare_zero == 2  # CMPA #0 -> TSTA, CMPB #0 -> TSTB
        assert optimizer.stats.push_pull_pairs == 1  # PSHA + PULA eliminated
        assert optimizer.stats.total_optimizations == 3


class TestConvenienceFunction:
    """Test the optimize_statements convenience function."""

    def test_optimize_statements_function(self):
        """Convenience function should work correctly."""
        source = "CMPA #0"
        statements = parse_source(source)
        result, stats = optimize_statements(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "TSTA"
        assert stats.compare_zero == 1

    def test_optimize_statements_disabled(self):
        """Convenience function with enabled=False should not optimize."""
        source = "CMPA #0"
        statements = parse_source(source)
        result, stats = optimize_statements(statements, enabled=False)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        assert instructions[0].mnemonic == "CMPA"
        assert stats.total_optimizations == 0


# =============================================================================
# Assembler Integration Tests
# =============================================================================

class TestAssemblerIntegration:
    """Test optimizer integration with the full assembler."""

    def test_assembler_with_optimization(self):
        """Assembler with optimization enabled should produce smaller code."""
        source = """
            ORG $2100
            CMPA #0
            CMPB #0
            RTS
        """
        # With optimization
        asm_opt = Assembler(optimize=True)
        asm_opt.assemble(source)
        code_opt = asm_opt.get_code()

        # Without optimization
        asm_no_opt = Assembler(optimize=False)
        asm_no_opt.assemble(source)
        code_no_opt = asm_no_opt.get_code()

        # Optimized code should be smaller
        # CMPA #0 (2 bytes) -> TSTA (1 byte) = saves 1 byte
        # CMPB #0 (2 bytes) -> TSTB (1 byte) = saves 1 byte
        # Total savings: 2 bytes
        assert len(code_opt) < len(code_no_opt)

    def test_assembler_optimization_disabled(self):
        """Assembler with optimization disabled should preserve instructions."""
        source = """
            ORG $2100
            CMPA #0
            RTS
        """
        asm = Assembler(optimize=False)
        asm.assemble(source)

        # Optimization should be disabled
        assert not asm.is_optimizing()
        # Stats should be None
        assert asm.get_optimization_stats() is None

    def test_assembler_optimization_stats(self):
        """Assembler should provide optimization statistics."""
        source = """
            ORG $2100
            CMPA #0
            CMPB #0
            RTS
        """
        asm = Assembler(optimize=True, verbose=False)
        asm.assemble(source)

        stats = asm.get_optimization_stats()
        assert stats is not None
        assert stats.compare_zero == 2
        assert stats.total_optimizations == 2

    def test_optimized_code_still_works(self):
        """Optimized code should still assemble and produce valid output."""
        source = """
            ORG $2100
            ; This should optimize: CMPA #0 -> TSTA
            CMPA #0
            ; This should optimize: PSHA/PULA -> nothing
            PSHA
            PULA
            ; This should optimize: CMPB #0 -> TSTB
            CMPB #0
            RTS
        """
        asm = Assembler(optimize=True)
        result = asm.assemble(source)

        # Should produce valid OB3
        assert result is not None
        assert len(result) > 0
        assert result[:3] == b"ORG"


# =============================================================================
# Complex Pattern Tests
# =============================================================================

class TestComplexPatterns:
    """Test optimization of more complex instruction patterns."""

    def test_multiple_optimizations_same_type(self):
        """Multiple CMPA #0 should each become TSTA."""
        source = """
            CMPA #0
            NOP
            CMPA #0
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        tsta_count = sum(1 for i in instructions if i.mnemonic == "TSTA")
        assert tsta_count == 2
        assert optimizer.stats.compare_zero == 2

    def test_sequential_compare_optimizations(self):
        """Sequential CMP #0 instructions should all optimize."""
        source = """
            CMPA #0
            CMPB #0
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 2
        assert instructions[0].mnemonic == "TSTA"
        assert instructions[1].mnemonic == "TSTB"

    def test_mixed_optimizations(self):
        """Mix of different optimization types."""
        source = """
            CMPA #0       ; -> TSTA
            PSHA
            PULA          ; -> eliminated with above PSHA
            CMPB #0       ; -> TSTB
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        mnemonics = [i.mnemonic for i in instructions]

        # Should have: TSTA, TSTB
        assert "TSTA" in mnemonics
        assert "TSTB" in mnemonics
        assert "CMPA" not in mnemonics
        assert "CMPB" not in mnemonics
        assert "PSHA" not in mnemonics
        assert "PULA" not in mnemonics


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_source(self):
        """Empty source should produce empty result."""
        source = ""
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)
        assert len(result) == 0

    def test_only_labels(self):
        """Source with only labels should preserve them."""
        source = """
        label1:
        label2:
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        labels = [s for s in result if isinstance(s, LabelDef)]
        assert len(labels) == 2

    def test_inherent_instructions_unchanged(self):
        """Inherent instructions that don't match patterns stay unchanged."""
        source = """
            NOP
            SEC
            CLC
            SEI
            CLI
            RTS
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 6
        assert optimizer.stats.total_optimizations == 0

    def test_max_passes_limit(self):
        """Optimizer should respect max_passes limit."""
        source = """
            CMPA #0
            CMPB #0
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer(max_passes=1)
        result = optimizer.optimize(statements)

        # Should still work, just limited iterations
        assert optimizer.stats.total_passes <= 1

    def test_expression_operands_not_optimized(self):
        """Instructions with expression operands should be handled safely."""
        # These use symbols that the optimizer doesn't evaluate
        source = """
        VALUE EQU 0
            CMPA #VALUE
        """
        statements = parse_source(source)
        optimizer = PeepholeOptimizer()
        result = optimizer.optimize(statements)

        # Should NOT optimize CMPA #VALUE because we can't evaluate VALUE
        # The optimizer only handles literal numeric values
        instructions = [s for s in result if isinstance(s, Instruction)]
        assert len(instructions) == 1
        # Should remain CMPA (symbol not evaluated at optimization time)
        assert instructions[0].mnemonic == "CMPA"


# =============================================================================
# Example File Test
# =============================================================================

class TestOptimizerExample:
    """Test the optimizer_test.asm example file."""

    def test_optimizer_example_file(self):
        """The optimizer_test.asm example should assemble and optimize correctly."""
        import os

        example_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "optimizer_test.asm"
        )

        # Skip if example file doesn't exist
        if not os.path.exists(example_path):
            pytest.skip("optimizer_test.asm example not found")

        with open(example_path, "r") as f:
            source = f.read()

        # Assemble with optimization
        asm_opt = Assembler(optimize=True, include_paths=["include"])
        asm_opt.assemble(source)
        assert not asm_opt.has_errors(), f"Assembly errors: {asm_opt.get_error_report()}"

        stats = asm_opt.get_optimization_stats()
        assert stats is not None

        # Verify expected optimizations were applied
        assert stats.compare_zero == 2, "Should have 2 compare zero optimizations"
        assert stats.push_pull_pairs == 2, "Should have 2 push/pull eliminations"
        assert stats.redundant_load == 1, "Should have 1 redundant load removal"
        assert stats.dead_code == 4, "Should have 4 dead code eliminations"
        assert stats.total_optimizations == 9, "Should have 9 total optimizations"

        # Assemble without optimization for size comparison
        asm_noopt = Assembler(optimize=False, include_paths=["include"])
        asm_noopt.assemble(source)
        assert not asm_noopt.has_errors()

        # Optimized code should be smaller
        code_opt = asm_opt.get_code()
        code_noopt = asm_noopt.get_code()
        assert len(code_opt) < len(code_noopt), "Optimized code should be smaller"

        # Should save approximately 14 bytes
        savings = len(code_noopt) - len(code_opt)
        assert savings >= 10, f"Expected at least 10 bytes savings, got {savings}"
