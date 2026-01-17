#!/usr/bin/env python3
"""
Psion Organiser II Games Demo
=============================

This script demonstrates loading and playing games from an OPK pack
on the Psion Organiser II emulator.

Prerequisites:
- Games pack at: thirdparty/jape/packs/games.opk

Usage:
    source .venv/bin/activate
    python examples/emulator_play_games.py

Games available in games.opk:
- Sub: Submarine game
- Runner: Running game
- Tenpin: Bowling game
- Slots: Slot machine
- Poker: Video poker
- Pontoon: Card game (21/Blackjack)

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

from pathlib import Path
from psion_sdk.emulator import Emulator, EmulatorConfig


class GamePlayer:
    """Helper class for playing Psion games."""

    def __init__(self, model: str = "LZ64"):
        self.emu = Emulator(EmulatorConfig(model=model))
        self.output_dir = Path("trash")
        self.output_dir.mkdir(exist_ok=True)
        self.screenshot_count = 0

    def load_games_pack(self, pack_path: str = "thirdparty/jape/packs/games.opk"):
        """Load the games pack into slot B."""
        pack = Path(pack_path)
        if not pack.exists():
            raise FileNotFoundError(f"Games pack not found: {pack}")
        self.emu.load_opk(pack, slot=1)
        print(f"Loaded: {pack.name}")

    def boot(self):
        """Boot the emulator and select English."""
        self.emu.reset()
        self.emu.run(5_000_000)
        self.emu.tap_key("EXE", hold_cycles=50000)
        self.emu.run(2_000_000)
        print("Booted to main menu")

    def screenshot(self, name: str = None) -> Path:
        """Take a screenshot and save it."""
        self.screenshot_count += 1
        if name is None:
            name = f"game_{self.screenshot_count:02d}"

        img = self.emu.display.render_image_lcd(
            scale=4,
            pixel_gap=1,
            char_gap=3,
            bezel=12
        )
        path = self.output_dir / f"{name}.png"
        path.write_bytes(img)
        print(f"Screenshot: {path.name} - {self.display_text}")
        return path

    @property
    def display_text(self) -> str:
        """Get current display as single line."""
        return " | ".join(line.strip() for line in self.emu.display_lines if line.strip())

    def navigate_to_games_menu(self):
        """Navigate from main menu to Games menu."""
        # Scroll left to reveal Games option
        for _ in range(3):
            self.emu.tap_key("LEFT", hold_cycles=20000)
            self.emu.run(200_000)

        # Navigate down to Games row
        self.emu.tap_key("DOWN", hold_cycles=20000)
        self.emu.run(200_000)
        self.emu.tap_key("DOWN", hold_cycles=20000)
        self.emu.run(200_000)

        # Enter Games menu
        self.emu.tap_key("EXE", hold_cycles=50000)
        self.emu.run(1_000_000)
        print(f"Games menu: {self.display_text}")

    def select_game(self, row: int, col: int):
        """Select a game by its position in the menu.

        Games menu layout:
            Row 0: Sub(0,0)     Runner(0,1)
            Row 1: Tenpin(1,0)  Slots(1,1)
            Row 2: Poker(2,0)   Pontoon(2,1)
        """
        for _ in range(row):
            self.emu.tap_key("DOWN", hold_cycles=20000)
            self.emu.run(200_000)

        for _ in range(col):
            self.emu.tap_key("RIGHT", hold_cycles=20000)
            self.emu.run(200_000)

    def run_game(self, cycles: int = 5_000_000):
        """Press EXE to run selected game and wait."""
        self.emu.tap_key("EXE", hold_cycles=50000)
        self.emu.run(cycles)

    def press(self, key: str, cycles: int = 500_000):
        """Press a key and run for specified cycles."""
        self.emu.tap_key(key, hold_cycles=30000)
        self.emu.run(cycles)

    def run(self, cycles: int):
        """Run emulator for specified cycles."""
        self.emu.run(cycles)

    def back(self):
        """Press ON to go back."""
        self.emu.tap_key("ON", hold_cycles=50000)
        self.emu.run(500_000)


def play_slots(player: GamePlayer):
    """Play the Slots game."""
    print("\n" + "=" * 60)
    print("SLOTS - Slot Machine")
    print("=" * 60)

    player.navigate_to_games_menu()
    player.screenshot("slots_menu")

    # Slots is at row 1, col 1
    player.select_game(row=1, col=1)
    player.run_game()
    player.screenshot("slots_start")

    # Spin a few times
    for i in range(3):
        player.press("EXE", cycles=2_000_000)
        player.screenshot(f"slots_spin_{i+1}")

    player.back()


def play_tenpin(player: GamePlayer):
    """Play Tenpin bowling."""
    print("\n" + "=" * 60)
    print("TENPIN - Bowling")
    print("=" * 60)

    player.navigate_to_games_menu()

    # Tenpin is at row 1, col 0
    player.select_game(row=1, col=0)
    player.run_game()
    player.screenshot("tenpin_start")

    # Bowl a few times
    for i in range(3):
        player.press("EXE", cycles=3_000_000)
        player.screenshot(f"tenpin_bowl_{i+1}")

    player.back()


def play_poker(player: GamePlayer):
    """Play Video Poker."""
    print("\n" + "=" * 60)
    print("POKER - Video Poker")
    print("=" * 60)

    player.navigate_to_games_menu()

    # Poker is at row 2, col 0
    player.select_game(row=2, col=0)
    player.run_game()
    player.screenshot("poker_start")

    # Deal cards
    player.press("EXE", cycles=3_000_000)
    player.screenshot("poker_deal")

    # Hold/draw
    player.press("EXE", cycles=3_000_000)
    player.screenshot("poker_result")

    player.back()


def main():
    print("Psion Organiser II Games Demo")
    print("=" * 60)

    # Create game player
    player = GamePlayer(model="LZ64")
    player.load_games_pack()
    player.boot()
    player.screenshot("main_menu")

    # Play each game
    play_slots(player)

    # Reset to main menu for next game
    player.boot()
    play_tenpin(player)

    player.boot()
    play_poker(player)

    print("\n" + "=" * 60)
    print(f"Total cycles: {player.emu.total_cycles:,}")
    print(f"Screenshots saved to: {player.output_dir.absolute()}")


if __name__ == "__main__":
    main()
