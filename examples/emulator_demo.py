#!/usr/bin/env python3
"""
Psion Organiser II Emulator Demo
================================

This script demonstrates how to use the Psion SDK emulator to:
1. Boot an emulator with a specific model
2. Load OPK packs
3. Navigate the menu system
4. Take screenshots
5. Run programs

Usage:
    source .venv/bin/activate
    python examples/emulator_demo.py

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from pathlib import Path
from psion_sdk.emulator import Emulator, EmulatorConfig


def main():
    # Output directory for screenshots
    output_dir = Path("trash")
    output_dir.mkdir(exist_ok=True)

    # ==========================================================================
    # 1. Create an emulator instance
    # ==========================================================================
    # Available models: "CM", "XP", "LZ", "LZ64"
    # - CM: 8KB RAM, 2-line display (16x2)
    # - XP: 32KB RAM, 2-line display (16x2) - DEFAULT
    # - LZ: 32KB RAM, 4-line display (20x4)
    # - LZ64: 64KB RAM, 4-line display (20x4)

    print("Creating Psion Organiser II LZ64 emulator...")
    emu = Emulator(EmulatorConfig(model="LZ64"))

    print(f"  Model: {emu.model.name}")
    print(f"  RAM: {emu.model.ram_kb}KB")
    print(f"  Display: {emu.model.display_lines} lines x {emu.model.display_cols} cols")

    # ==========================================================================
    # 2. Load an OPK pack (optional)
    # ==========================================================================
    # Packs can be loaded into slots:
    #   slot=0 -> A: (internal)
    #   slot=1 -> B: (first slot)
    #   slot=2 -> C: (second slot)

    games_pack = Path("thirdparty/jape/packs/games.opk")
    if games_pack.exists():
        print(f"\nLoading {games_pack.name} into B:...")
        emu.load_opk(games_pack, slot=1)

    # ==========================================================================
    # 3. Boot the emulator
    # ==========================================================================
    print("\nBooting emulator...")
    emu.reset()

    # Run enough cycles for the OS to boot (typically 5M cycles)
    emu.run(5_000_000)

    # The first screen is usually language selection
    print(f"  Display: {emu.display_lines}")

    # Select English by pressing EXE
    emu.tap_key("EXE", hold_cycles=50000)
    emu.run(2_000_000)

    print(f"  Main menu: {emu.display_lines}")

    # ==========================================================================
    # 4. Take screenshots
    # ==========================================================================
    # Two rendering modes:
    #   render_image(scale=N) - compact rendering
    #   render_image_lcd(scale=N, ...) - realistic LCD with pixel grid

    print("\nTaking screenshots...")

    # Compact rendering
    img = emu.display.render_image(scale=4)
    (output_dir / "demo_compact.png").write_bytes(img)
    print("  Saved demo_compact.png")

    # LCD matrix style rendering (realistic)
    img = emu.display.render_image_lcd(
        scale=4,        # Pixel size
        pixel_gap=1,    # Gap between pixels
        char_gap=3,     # Gap between characters
        bezel=12        # Border size
    )
    (output_dir / "demo_lcd.png").write_bytes(img)
    print("  Saved demo_lcd.png")

    # ==========================================================================
    # 5. Navigate the menu
    # ==========================================================================
    # Available keys:
    #   Navigation: UP, DOWN, LEFT, RIGHT
    #   Action: EXE (execute/enter), ON (back/cancel), MODE
    #   Letters: A-Z, 0-9
    #   Special: SHIFT, DEL, SPACE

    print("\nNavigating menu...")

    # LZ/LZ64 menu scrolls - press LEFT to see more options
    for _ in range(3):
        emu.tap_key("LEFT", hold_cycles=20000)
        emu.run(200_000)

    print(f"  Scrolled menu: {emu.display_lines}")

    # Navigate down to find Games
    emu.tap_key("DOWN", hold_cycles=20000)
    emu.run(200_000)
    emu.tap_key("DOWN", hold_cycles=20000)
    emu.run(200_000)

    # Enter Games menu
    emu.tap_key("EXE", hold_cycles=50000)
    emu.run(1_000_000)

    print(f"  Games menu: {emu.display_lines}")

    img = emu.display.render_image_lcd(scale=4, pixel_gap=1, char_gap=3, bezel=12)
    (output_dir / "demo_games_menu.png").write_bytes(img)
    print("  Saved demo_games_menu.png")

    # ==========================================================================
    # 6. Run a game
    # ==========================================================================
    print("\nRunning Slots game...")

    # Navigate to Slots (second row, second column)
    emu.tap_key("DOWN", hold_cycles=20000)
    emu.run(200_000)
    emu.tap_key("RIGHT", hold_cycles=20000)
    emu.run(200_000)

    # Press EXE to run
    emu.tap_key("EXE", hold_cycles=50000)
    emu.run(5_000_000)

    print(f"  Game: {emu.display_lines}")

    img = emu.display.render_image_lcd(scale=4, pixel_gap=1, char_gap=3, bezel=12)
    (output_dir / "demo_slots.png").write_bytes(img)
    print("  Saved demo_slots.png")

    # ==========================================================================
    # 7. Summary
    # ==========================================================================
    print(f"\nTotal cycles executed: {emu.total_cycles:,}")
    print(f"Screenshots saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
