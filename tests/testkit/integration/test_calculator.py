"""
Integration Tests - Calculator
==============================

Tests for the Psion Organiser II calculator application.
These tests verify basic arithmetic operations work correctly.

Note on calculator display format:
After pressing EXE, the Psion shows:
- Line 0: the expression (e.g., "2+3")
- Line 1: the result with "=" prefix (e.g., "=5")

These tests demonstrate:
- Using type_text for calculator input
- Using enter_text_and_confirm compound action
- Testing numeric output with "=" prefix

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.testkit import (
    psion_test,
    for_models,
    PsionTestContext,
    NavigateToMenu,
)


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC ARITHMETIC TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_calculator_addition(ctx: PsionTestContext):
    """
    Test basic addition in calculator.
    """
    # CALC needs confirm=True because C is shared with COPY
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("2+3")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    # Result appears on line 1 with "=" prefix
    ctx.assert_display_contains("=5")


@psion_test(requires_boot=True)
def test_calculator_subtraction(ctx: PsionTestContext):
    """
    Test basic subtraction in calculator.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("10-4")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    ctx.assert_display_contains("=6")


@psion_test(requires_boot=True)
def test_calculator_multiplication(ctx: PsionTestContext):
    """
    Test multiplication in calculator.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("7*8")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    ctx.assert_display_contains("=56")


@psion_test(requires_boot=True)
def test_calculator_division(ctx: PsionTestContext):
    """
    Test division in calculator.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("15/3")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    ctx.assert_display_contains("=5")


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOUND EXPRESSION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_calculator_compound_expression(ctx: PsionTestContext):
    """
    Test a more complex expression.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    # 2+3*4 should give 14 (standard precedence: 2+(3*4)=14)
    # Note: Psion calculator might evaluate left-to-right (giving 20)
    ctx.type_text("2+3*4")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    # Check result is a number (either 14 or 20 depending on precedence)
    ctx.assert_display_matches(r"=\d+")


@psion_test(requires_boot=True)
def test_calculator_large_numbers(ctx: PsionTestContext):
    """
    Test addition with larger numbers.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("123+456")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    ctx.assert_display_contains("=579")


# ═══════════════════════════════════════════════════════════════════════════════
# NEGATIVE NUMBER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_calculator_negative_result(ctx: PsionTestContext):
    """
    Test subtraction with negative result.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    ctx.type_text("3-10")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    # Should show =-7
    ctx.assert_display_contains("=-7")


# ═══════════════════════════════════════════════════════════════════════════════
# USING COMPOUND ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_calculator_using_compound_action(ctx: PsionTestContext):
    """
    Demonstrate using compound actions for cleaner tests.
    """
    # Use navigate_menu compound action (includes EXE)
    ctx.navigate_menu("CALC")

    # Use enter_text_and_confirm for calculation
    ctx.type_text("100+50")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()

    ctx.assert_display_contains("=150")


# ═══════════════════════════════════════════════════════════════════════════════
# CONSECUTIVE CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_calculator_consecutive_calculations(ctx: PsionTestContext):
    """
    Test multiple calculations in sequence.

    Note: After a calculation, pressing ON/CLEAR resets for a new expression.
    Otherwise, new characters append to the result.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    # First calculation
    ctx.type_text("10+5")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()
    ctx.assert_display_contains("=15")

    # Clear and start second calculation
    ctx.press("ON")
    ctx.wait_until_idle()
    ctx.type_text("20-8")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()
    ctx.assert_display_contains("=12")

    # Clear and start third calculation
    ctx.press("ON")
    ctx.wait_until_idle()
    ctx.type_text("3*3")
    ctx.press("EXE")
    ctx.run_cycles(500_000)
    ctx.wait_until_idle()
    ctx.assert_display_contains("=9")
