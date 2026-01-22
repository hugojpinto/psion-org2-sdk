"""
Psion Testing Framework - Sequences
===================================

Reusable multi-step workflows for common testing scenarios. These
Level 5 operations encapsulate complex interactions that would
otherwise require multiple steps.

Available Sequences:
    BootSequence     - Boot emulator to main menu
    NavigateToMenu   - Navigate to a main menu option
    ProgMenu         - Operations in the PROG menu
    Editor           - OPL editor operations

Usage:
    from psion_sdk.testkit import BootSequence, NavigateToMenu

    @psion_test(requires_boot=True)
    def test_prog_menu(ctx):
        NavigateToMenu.execute(ctx, "PROG")
        ctx.assert_display_contains("New")

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import PsionTestContext


class BootSequence:
    """
    Boot the emulator to main menu.

    Handles the complete boot sequence:
    1. Run initial cycles for OS startup
    2. Detect if language selection is needed (LZ and multi-language ROMs)
    3. Press language selection key only if needed
    4. Wait for main menu to appear

    Different ROMs behave differently:
    - CM and standard XP ROMs: Boot directly to main menu (no language selection)
    - LZ and multi-language XP ROMs: Show language selection screen first
    - LZ/LZ64 menus: Use Title Case ("Find Save Diary") not uppercase

    The sequence auto-detects whether language selection is needed by checking
    if the main menu is already visible after initial boot cycles.

    Usage:
        # Full boot with verification
        BootSequence.execute(ctx)

        # Boot with custom language key
        BootSequence.execute(ctx, language_key="DOWN")  # French

        # Boot without verification (faster)
        BootSequence.execute(ctx, verify=False)
    """

    # Expected menu items on main menu (used for verification)
    # Note: LZ models show these in Title Case, so we check case-insensitively
    MAIN_MENU_ITEMS = ["FIND", "SAVE", "DIARY", "CALC", "PROG", "ERASE"]

    @staticmethod
    def _is_at_main_menu(ctx: "PsionTestContext") -> bool:
        """
        Check if the display shows the main menu.

        Uses case-insensitive matching because LZ/LZ64 models show
        "Find Save Diary" (Title Case) instead of "FIND SAVE DIARY".

        Returns:
            True if main menu items are visible
        """
        display_upper = ctx.display_text.upper()
        # Check for multiple menu items to be confident we're at main menu
        # (not just seeing "FIND" in "FIND A:" prompt)
        menu_items_found = sum(
            1 for item in ["FIND", "CALC", "SAVE", "DIARY"]
            if item in display_upper
        )
        return menu_items_found >= 2

    @staticmethod
    def execute(
        ctx: "PsionTestContext",
        *,
        language_key: str = None,
        verify: bool = True,
    ) -> None:
        """
        Execute the boot sequence.

        Args:
            ctx: Test context
            language_key: Key to press for language selection (default: from config)
            verify: If True, assert main menu appears after boot

        Raises:
            TestTimeoutError: If boot doesn't complete within timeout
            TestAssertionError: If verify=True and menu doesn't appear
        """
        from .exceptions import TestAssertionError

        config = ctx.config

        # Use config default if no language key specified
        if language_key is None:
            language_key = config.boot_language_key

        # Run initial boot cycles
        ctx.run_cycles(config.boot_cycles)

        # Check if we're already at the main menu (no language selection needed)
        # Some ROMs (CM, standard XP) boot directly to menu, while LZ and
        # multi-language ROMs show language selection first.
        if not BootSequence._is_at_main_menu(ctx):
            # Not at main menu yet - likely at language selection screen
            # Press key to select language and continue
            ctx.press(language_key, wait="none")

        # Run post-boot cycles
        ctx.run_cycles(config.post_boot_cycles)

        # Wait until idle (menu ready)
        ctx.wait_until_idle()

        # Verify main menu appeared (case-insensitive for LZ models)
        if verify:
            if not BootSequence._is_at_main_menu(ctx):
                raise TestAssertionError(
                    "Boot verification failed: Main menu not detected",
                    assertion_type="boot_verification",
                    expected="Main menu with FIND, CALC, etc.",
                    actual=ctx.display_text,
                    display_state=ctx.display,
                    cursor_position=ctx.cursor,
                )


class NavigateToMenu:
    """
    Navigate to a specific main menu option.

    Uses first-letter navigation for efficiency. On the Psion:
    - If only ONE menu item starts with that letter → enters immediately
    - If MULTIPLE items start with same letter → cycles between them, need EXE

    Main menu items: FIND, SAVE, DIARY, CALC, **COPY**, PROG, ERASE
    Note that CALC and COPY both start with C, so pressing C cycles between
    them and requires EXE to confirm which one to enter.

    The `confirm` parameter controls whether EXE is pressed:
    - confirm=False (default): Just press the letter key
    - confirm=True: Press letter key followed by EXE

    For items with unique first letters (F, S, D, P, E), no EXE is needed.
    For CALC (shares C with COPY), use confirm=True.

    Supported Menus:
        FIND, SAVE, DIARY, CALC, PROG, ERASE
        (On LZ/LZ64: also GAMES, UTILS, OFF via scrolling)

    Usage:
        # Navigate to PROG menu (P is unique, enters immediately)
        NavigateToMenu.execute(ctx, "PROG")

        # Navigate to CALC (C is shared with COPY, needs EXE)
        NavigateToMenu.execute(ctx, "CALC", confirm=True)
    """

    # Map menu names to their first-letter keys
    MENU_KEYS = {
        "FIND": "F",
        "SAVE": "S",
        "DIARY": "D",
        "CALC": "C",
        "PROG": "P",
        "ERASE": "E",
        # LZ-specific (may need scrolling)
        "GAMES": "G",
        "UTILS": "U",
        "OFF": "O",
    }

    @staticmethod
    def execute(
        ctx: "PsionTestContext",
        menu: str,
        *,
        confirm: bool = False,
    ) -> None:
        """
        Navigate to a menu option.

        On the Psion, pressing the first letter of a menu item enters
        that menu/application immediately - no EXE confirmation needed.

        Args:
            ctx: Test context
            menu: Menu name (FIND, SAVE, DIARY, CALC, PROG, ERASE)
            confirm: If True, press EXE after entering (default: False)
                     WARNING: This may select the first submenu item!

        Raises:
            ValueError: If menu name is not recognized
        """
        menu_upper = menu.upper()
        if menu_upper not in NavigateToMenu.MENU_KEYS:
            raise ValueError(
                f"Unknown menu: {menu}. Valid options: {list(NavigateToMenu.MENU_KEYS.keys())}"
            )

        key = NavigateToMenu.MENU_KEYS[menu_upper]

        # Press the first letter to enter the menu
        # On Psion, this immediately enters the menu/app
        ctx.press(key)

        # Optionally press EXE (WARNING: may select first submenu item)
        if confirm:
            ctx.press("EXE")


class ProgMenu:
    """
    Operations in the PROG menu.

    The PROG menu provides access to OPL programming features:
    - New: Create new procedure
    - Edit: Modify existing procedure
    - Dir: List procedures on a drive
    - Copy: Copy a procedure
    - Erase: Delete a procedure
    - TRAN: Run translated (compiled) procedures

    Usage:
        # Create a new procedure
        ProgMenu.create_new(ctx, "TEST", drive="A:")

        # Run an existing translated procedure
        ProgMenu.run_translated(ctx, "HELLO")

        # Edit an existing procedure
        ProgMenu.edit(ctx, "MYPROC")
    """

    @staticmethod
    def create_new(
        ctx: "PsionTestContext",
        name: str,
        *,
        drive: str = "A:",
    ) -> None:
        """
        Create a new procedure.

        After calling this, the editor will be open with the procedure
        name line showing (e.g., "TEST:"). You can then type OPL code.

        Args:
            ctx: Test context
            name: Procedure name (max 8 characters)
            drive: Target drive (A:, B:, or C:)

        Raises:
            TestTimeoutError: If operation doesn't complete
        """
        # Press N for New
        ctx.press("N")

        # Select drive if not A:
        if drive != "A:":
            ctx.select_drive(drive)

        # Type procedure name
        ctx.type_text(name)

        # Confirm
        ctx.press("EXE")

        # Wait for editor to open (shows "NAME:")
        ctx.wait_for(f"{name}:")

    @staticmethod
    def run_translated(ctx: "PsionTestContext", name: str) -> None:
        """
        Run a translated (compiled) procedure.

        The procedure must already exist and be translated.

        Args:
            ctx: Test context
            name: Procedure name to run

        Raises:
            TestTimeoutError: If procedure not found
        """
        # Look for the procedure name in the list
        ctx.wait_for(name)

        # Select it and run
        ctx.press("EXE")

    @staticmethod
    def edit(ctx: "PsionTestContext", name: str) -> None:
        """
        Enter editor for existing procedure.

        Args:
            ctx: Test context
            name: Procedure name to edit
        """
        # Press E for Edit
        ctx.press("E")

        # Type procedure name
        ctx.type_text(name)

        # Confirm
        ctx.press("EXE")

        # Wait for editor to open
        ctx.wait_for(f"{name}:")

    @staticmethod
    def delete(ctx: "PsionTestContext", name: str) -> None:
        """
        Delete a procedure.

        WARNING: This permanently deletes the procedure!

        Args:
            ctx: Test context
            name: Procedure name to delete
        """
        # Press E twice for Erase (first E is Edit, second is Erase)
        ctx.press("E")
        ctx.press("E")

        # Type procedure name
        ctx.type_text(name)

        # Confirm deletion
        ctx.press("EXE")
        ctx.press("EXE")  # Confirm "Are you sure?"


class Editor:
    """
    OPL editor operations.

    The editor is used to write and modify OPL procedures. Key operations:
    - Type code line by line (press EXE after each line)
    - Translate (compile) the procedure
    - Save and exit
    - Quit without saving

    Usage:
        # Type some OPL code
        Editor.type_line(ctx, 'PRINT "HELLO"')
        Editor.type_line(ctx, 'GET')

        # Translate the procedure
        Editor.translate(ctx)

        # Or save and exit
        Editor.save_and_exit(ctx)
    """

    @staticmethod
    def type_line(ctx: "PsionTestContext", code: str) -> None:
        """
        Type a line of OPL code and press EXE.

        Each line of OPL code must be terminated with EXE to move
        to the next line.

        Args:
            ctx: Test context
            code: OPL code to type (single line)
        """
        ctx.type_text(code)
        ctx.press("EXE")

    @staticmethod
    def translate(ctx: "PsionTestContext", *, output_name: str = None) -> None:
        """
        Translate (compile) the current procedure.

        Opens the editor context menu and selects TRAN. If successful,
        returns to the PROG menu. If there are errors, they will be
        displayed on screen.

        Args:
            ctx: Test context
            output_name: Override output name (default: same as source)
        """
        # Press MODE to open context menu
        ctx.press("MODE")

        # Select TRAN (translate)
        ctx.press("T")

        # Confirm output filename
        if output_name:
            # Clear default and type new name
            ctx.type_text(output_name)

        ctx.press("EXE")

        # Confirm source filename
        ctx.press("EXE")

        # Wait for translation to complete (returns to PROG menu or shows error)
        ctx.wait_until_idle()

    @staticmethod
    def save_and_exit(ctx: "PsionTestContext") -> None:
        """
        Save and exit the editor.

        Args:
            ctx: Test context
        """
        # Press MODE to open context menu
        ctx.press("MODE")

        # Select SAVE
        ctx.press("S")

        # Wait for save to complete
        ctx.wait_until_idle()

    @staticmethod
    def quit_without_saving(ctx: "PsionTestContext") -> None:
        """
        Exit without saving.

        Args:
            ctx: Test context
        """
        # Press MODE to open context menu
        ctx.press("MODE")

        # Select QUIT
        ctx.press("Q")

        # Confirm quit
        ctx.press("EXE")

        # Wait for return to menu
        ctx.wait_until_idle()
