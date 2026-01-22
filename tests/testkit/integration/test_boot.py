"""
Integration Tests - Boot Sequence
=================================

Tests for the Psion Organiser II boot sequence across different models.
These tests verify that the emulator boots correctly to the main menu.

These tests demonstrate:
- Using @psion_test decorator with requires_boot=True
- Using @for_models for model parameterization
- Basic display assertions

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.testkit import (
    psion_test,
    for_models,
    PsionTestContext,
    BootSequence,
)


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC BOOT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_default_model_boots(ctx: PsionTestContext):
    """
    Test that the default model (XP) boots successfully.

    The boot sequence should complete and display the main menu.
    """
    # Boot is done by @psion_test, just verify menu is shown
    # Use case_sensitive=False because LZ models show "Find" not "FIND"
    ctx.assert_display_contains("FIND", case_sensitive=False)
    ctx.assert_display_contains("CALC", case_sensitive=False)


@psion_test(requires_boot=True)
@for_models("CM", "XP")
def test_2line_boot_shows_main_menu(ctx: PsionTestContext):
    """
    Test 2-line models (CM, XP) boot to expected menu layout.

    The main menu should show:
    - Line 0: FIND  SAVE  DIARY
    - Line 1: CALC  PROG  ERASE
    """
    # Check menu items are visible (CM/XP use uppercase)
    # Use case_sensitive=False for robustness
    ctx.assert_display_contains("FIND", case_sensitive=False)
    ctx.assert_display_contains("SAVE", case_sensitive=False)
    ctx.assert_display_contains("CALC", case_sensitive=False)
    ctx.assert_display_contains("PROG", case_sensitive=False)


@psion_test(requires_boot=True)
@for_models("LZ", "LZ64")
def test_4line_boot_shows_main_menu(ctx: PsionTestContext):
    """
    Test 4-line models (LZ, LZ64) boot to main menu.

    4-line displays show more menu options with Title Case (Find, Save, etc.)
    and have different menu items visible (Time, Notes, World, Alarm, Month).
    PROG is accessible via P key but may not be visible without scrolling.
    """
    # LZ models use Title Case: "Find Save Diary" not "FIND SAVE DIARY"
    # Use case_sensitive=False for cross-model compatibility
    ctx.assert_display_contains("Find", case_sensitive=False)
    ctx.assert_display_contains("Calc", case_sensitive=False)
    ctx.assert_display_contains("Save", case_sensitive=False)


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test()
def test_manual_boot_sequence(ctx: PsionTestContext):
    """
    Test manually executing the boot sequence.

    This demonstrates using BootSequence directly rather than
    relying on requires_boot=True.
    """
    # Execute boot manually
    BootSequence.execute(ctx, verify=True)

    # Verify we're at the main menu (case-insensitive for LZ models)
    ctx.assert_display_contains("FIND", case_sensitive=False)


@psion_test()
def test_boot_without_verification(ctx: PsionTestContext):
    """
    Test boot sequence without automatic verification.

    Useful for tests that need to verify boot behavior themselves.
    """
    # Boot without automatic verification
    BootSequence.execute(ctx, verify=False)

    # Do our own verification
    display_text = ctx.display_text
    assert "FIND" in display_text or "CALC" in display_text, (
        "Main menu not detected after boot"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY STATE TESTS AFTER BOOT
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_cursor_position_after_boot(ctx: PsionTestContext):
    """
    Test cursor position after boot.

    After boot, the cursor should be positioned at the start of
    the first selectable menu item.
    """
    # Just verify cursor exists and position is valid
    row, col = ctx.cursor
    assert 0 <= row < 4, f"Cursor row out of range: {row}"
    assert 0 <= col < 20, f"Cursor col out of range: {col}"


@psion_test(requires_boot=True)
def test_display_dimensions_match_model(ctx: PsionTestContext):
    """
    Test that display dimensions match the model.
    """
    model = ctx.model
    lines = ctx.display

    if model in ("LZ", "LZ64"):
        assert len(lines) == 4, f"Expected 4 lines for {model}, got {len(lines)}"
    else:
        assert len(lines) == 2, f"Expected 2 lines for {model}, got {len(lines)}"
