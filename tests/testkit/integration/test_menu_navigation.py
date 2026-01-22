"""
Integration Tests - Menu Navigation
===================================

Tests for navigating the Psion Organiser II menu system.
These tests verify that menu navigation works correctly across
different methods (arrow keys, first-letter shortcuts, etc.).

These tests demonstrate:
- Using NavigateToMenu sequence
- Using compound actions (navigate_menu)
- Testing navigation with arrow keys

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
# FIRST-LETTER NAVIGATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_navigate_to_prog_with_sequence(ctx: PsionTestContext):
    """
    Test navigating to PROG menu using NavigateToMenu sequence.
    """
    NavigateToMenu.execute(ctx, "PROG")

    # Should now be in PROG submenu - shows "EDIT LIST DIR" / "NEW RUN ERASE"
    # Note: Menu items are uppercase on CM/XP
    ctx.assert_display_contains("NEW", case_sensitive=False)


@psion_test(requires_boot=True)
def test_navigate_to_calc_with_sequence(ctx: PsionTestContext):
    """
    Test navigating to CALC using NavigateToMenu sequence.

    Note: CALC appears to require EXE to enter (unlike PROG which enters
    on first-letter press). This may be because CALC is a standalone app
    rather than a submenu.
    """
    NavigateToMenu.execute(ctx, "CALC", confirm=True)

    # Calculator should be ready - check we're not at main menu
    ctx.assert_display_not_contains("FIND", case_sensitive=False)


@psion_test(requires_boot=True)
def test_navigate_to_find_with_compound_action(ctx: PsionTestContext):
    """
    Test using the navigate_menu compound action.
    """
    ctx.navigate_menu("FIND")

    # Should be in FIND mode
    ctx.assert_display_not_contains("FIND")


@psion_test(requires_boot=True)
def test_navigate_without_confirm(ctx: PsionTestContext):
    """
    Test navigating to PROG menu without extra EXE press.

    On the Psion, pressing a unique first letter enters that menu immediately.
    Since all main menu items have unique first letters, pressing P enters
    the PROG submenu directly.
    """
    # Press P to enter PROG menu (no EXE needed for unique first letter)
    NavigateToMenu.execute(ctx, "PROG")

    # Should be in PROG submenu showing: EDIT LIST DIR / NEW RUN ERASE
    ctx.assert_display_contains("NEW", case_sensitive=False)
    ctx.assert_display_contains("EDIT", case_sensitive=False)


# ═══════════════════════════════════════════════════════════════════════════════
# ARROW KEY NAVIGATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_navigate_with_arrow_keys(ctx: PsionTestContext):
    """
    Test navigating the menu with arrow keys.
    """
    # Press right to move selection
    ctx.press("RIGHT")

    # Press down to move to second row
    ctx.press("DOWN")

    # We should still be at the main menu
    ctx.assert_display_contains("FIND", case_sensitive=False)


@psion_test(requires_boot=True)
def test_navigate_up_and_down(ctx: PsionTestContext):
    """
    Test moving up and down in menu.
    """
    # Use compound actions
    ctx.go_down()
    ctx.go_down()
    ctx.go_up()

    # Still at main menu
    ctx.assert_display_contains("FIND", case_sensitive=False)


@psion_test(requires_boot=True)
def test_navigate_left_and_right(ctx: PsionTestContext):
    """
    Test moving left and right in menu.
    """
    # Move around
    ctx.go_right()
    ctx.go_right()
    ctx.go_left()

    # Still at main menu
    ctx.assert_display_contains("FIND", case_sensitive=False)


# ═══════════════════════════════════════════════════════════════════════════════
# RETURN TO MAIN MENU TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
def test_return_from_calc_with_mode(ctx: PsionTestContext):
    """
    Test returning to main menu from CALC using MODE.

    Note: On the Psion, pressing MODE in CALC may show a calculator menu
    rather than exiting. The ON/CLEAR key might be needed to exit.
    """
    # Enter CALC (requires EXE because C is shared with COPY)
    NavigateToMenu.execute(ctx, "CALC", confirm=True)
    ctx.assert_display_not_contains("FIND", case_sensitive=False)

    # Press ON/CLEAR to exit (MODE shows calc menu, doesn't exit)
    ctx.press("ON")

    # Should be back at main menu (use case-insensitive for LZ compatibility)
    ctx.wait_for("FIND", case_sensitive=False)
    ctx.assert_display_contains("FIND", case_sensitive=False)


@psion_test(requires_boot=True)
def test_return_from_prog_with_mode(ctx: PsionTestContext):
    """
    Test returning to main menu from PROG using ON/CLEAR.

    Note: On the Psion, pressing MODE in PROG may show a submenu
    rather than exiting. The ON/CLEAR key is used to go back.
    """
    # Enter PROG (pressing P enters immediately since unique first letter)
    NavigateToMenu.execute(ctx, "PROG")
    ctx.assert_display_contains("NEW", case_sensitive=False)

    # Press ON/CLEAR to exit back to main menu
    ctx.press("ON")

    # Should be back at main menu (use case-insensitive for LZ compatibility)
    ctx.wait_for("FIND", case_sensitive=False)
    ctx.assert_display_contains("FIND", case_sensitive=False)


# ═══════════════════════════════════════════════════════════════════════════════
# ALL MENU ITEMS TEST
# ═══════════════════════════════════════════════════════════════════════════════


@psion_test(requires_boot=True)
@pytest.mark.parametrize("menu_item", ["FIND", "SAVE", "DIARY", "PROG", "ERASE"])
def test_navigate_to_all_menu_items(ctx: PsionTestContext, menu_item: str):
    """
    Test that main menu items can be accessed via first-letter navigation.

    This parameterized test runs once for each menu item.

    Note: CALC is excluded because it requires EXE to enter (tested separately
    in test_navigate_to_calc_with_sequence).
    """
    # Navigate to the menu (pressing first letter enters immediately for these items)
    NavigateToMenu.execute(ctx, menu_item)

    # Should no longer be at main menu (unless item doesn't open a submenu)
    # For some items like FIND, it goes to a search mode
    # We just verify navigation succeeded by checking main menu is not visible
    # Use case-insensitive matching for LZ compatibility (shows "Find" not "FIND")
    display_upper = ctx.display_text.upper()
    main_menu_count = sum(
        1 for item in ["FIND", "SAVE", "DIARY", "CALC", "PROG", "ERASE"]
        if item in display_upper
    )

    # If 3 or more main menu items visible, we're probably still at main menu
    # (failed navigation). Otherwise, we successfully entered a submenu.
    assert main_menu_count < 3, f"Navigation to {menu_item} may have failed (found {main_menu_count} menu items: {ctx.display_text!r})"
