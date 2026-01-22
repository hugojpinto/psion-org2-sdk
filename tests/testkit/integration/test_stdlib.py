"""
Integration Tests - Standard Library
====================================

Automated tests for the Psion SDK standard library by running
stdlib_test.c on the emulator and verifying all tests pass.

The stdlib_test.c program tests:
- ctype.h: isdigit, isupper, islower, isalpha, isalnum, toupper, tolower
- runtime: atoi, itoa, strchr
- stdio.h: strrchr, strstr, sprintf

The program displays results screen by screen, requiring key presses
to advance. The final screen shows a summary with pass/fail counts.

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.testkit import (
    psion_test,
    for_models,
    with_program,
    PsionTestContext,
    NavigateToMenu,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Run program from B: drive
# ═══════════════════════════════════════════════════════════════════════════════


def run_program_from_b_drive(ctx: PsionTestContext, program_name: str):
    """
    Navigate to PROG menu and run a translated program from B: drive.

    Args:
        ctx: Test context
        program_name: Name of the procedure to run (max 8 chars)
    """
    # Navigate to PROG menu
    NavigateToMenu.execute(ctx, "PROG")

    # Press R for RUN, MODE to switch to B:, type name, EXE to run
    ctx.press("R")
    ctx.press("MODE")  # Switch from A: to B:
    ctx.type_text(program_name)
    ctx.press("EXE")

    # Wait for program to start
    ctx.run_cycles(3_000_000)
    ctx.wait_until_idle()


# ═══════════════════════════════════════════════════════════════════════════════
# STDLIB TEST - C VERSION
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
@with_program("examples/stdlib_test.c", slot=0, procedure_name="STDLIBC")
def test_stdlib_c_all_pass(ctx: PsionTestContext):
    """
    Run stdlib_test.c and verify all tests pass.

    The test program displays multiple screens of test results,
    requiring key presses to advance. We verify:
    1. Program starts correctly
    2. All test screens complete
    3. Final summary shows 0 failures
    """
    # Run the program from B: drive
    run_program_from_b_drive(ctx, "STDLIBC")

    # The title screen shows "Press any key..."
    # Press through all screens: 1 title + 9 test screens = 10 keypresses
    # The 9th keypress shows the summary, 10th exits
    for _ in range(9):
        ctx.press("EXE")
        ctx.run_cycles(1_000_000)
        ctx.wait_until_idle()

    # Verify summary shows no failures
    ctx.assert_display_contains("Failed: 0")


@psion_test(requires_boot=True)
@with_program("examples/stdlib_test.c", slot=0, procedure_name="STDLIBC")
def test_stdlib_c_shows_pass_count(ctx: PsionTestContext):
    """
    Run stdlib_test.c and verify it shows the correct pass count.
    """
    run_program_from_b_drive(ctx, "STDLIBC")

    # Press through to summary
    for _ in range(9):
        ctx.press("EXE")
        ctx.run_cycles(1_000_000)
        ctx.wait_until_idle()

    # Verify pass count (16 tests total)
    ctx.assert_display_contains("Passed: 16")


@psion_test(requires_boot=True)
@for_models("LZ", "LZ64")
@with_program("examples/stdlib_test.c", slot=0, build_args={"model": "LZ"}, procedure_name="STDLIBC")
def test_stdlib_c_on_4line(ctx: PsionTestContext):
    """
    Run stdlib_test.c on 4-line display models (LZ/LZ64).

    This verifies the stdlib works correctly with the LZ target
    and 4-line display mode.
    """
    run_program_from_b_drive(ctx, "STDLIBC")

    # Press through to summary
    for _ in range(9):
        ctx.press("EXE")
        ctx.run_cycles(1_000_000)
        ctx.wait_until_idle()

    # Verify no failures
    ctx.assert_display_contains("Failed: 0")


# ═══════════════════════════════════════════════════════════════════════════════
# STDLIB TEST - ASSEMBLY VERSION
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
@for_models("LZ", "LZ64")
@with_program("examples/stdlib_asm_test.asm", slot=0, build_args={"model": "LZ", "relocatable": True}, procedure_name="ASMTEST")
def test_stdlib_asm_all_pass(ctx: PsionTestContext):
    """
    Run stdlib_asm_test.asm and verify all tests pass.

    Tests ctype.inc macros (TO_UPPER, TO_LOWER, CHAR_TO_DIGIT, etc.)
    and stdio.inc functions (STRRCHR, STRSTR).

    Program flow:
    1. Title screen with PAUSE 64 (~2 seconds)
    2. First 4 tests (CONST, TOUPPER, TOLOWER, DIGIT CVT) - waits for key
    3. Second 3 tests + summary (HEX_TO_CHAR, STRRCHR, STRSTR, P:7/7) - waits for key
    4. Exit
    """
    run_program_from_b_drive(ctx, "ASMTEST")

    # Wait for PAUSE 64 to complete (~2 seconds = ~2M cycles at 1MHz)
    # run_program_from_b_drive already ran 3M cycles, but PAUSE timer is separate
    # Run more cycles to ensure PAUSE completes and tests run
    ctx.run_cycles(5_000_000)
    ctx.wait_until_idle()

    # Program should be at first GETKEY showing first 4 tests
    ctx.assert_display_contains("CONST")

    # Press key to advance past first test section
    ctx.press("EXE")
    ctx.run_cycles(2_000_000)
    ctx.wait_until_idle()

    # Now on second section, verify summary shows 7/7
    ctx.assert_display_contains("7/7")


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
@with_program("examples/stdlib_test.c", slot=0, procedure_name="STDLIBC")
def test_stdlib_starts_and_shows_title(ctx: PsionTestContext):
    """
    Quick test to verify the stdlib test program starts.
    """
    run_program_from_b_drive(ctx, "STDLIBC")

    # Title screen should show "Press" (which fits on one line)
    ctx.assert_display_contains("Press", case_sensitive=False)


@psion_test(requires_boot=True)
@with_program("examples/stdlib_test.c", slot=0, procedure_name="STDLIBC")
def test_stdlib_first_test_passes(ctx: PsionTestContext):
    """
    Verify the first test (isdigit from ctype) passes.
    """
    run_program_from_b_drive(ctx, "STDLIBC")

    # Press key to advance past title
    ctx.press("EXE")
    ctx.run_cycles(1_000_000)
    ctx.wait_until_idle()

    # First test screen should show "OK" for at least one test
    ctx.assert_display_contains("OK")
