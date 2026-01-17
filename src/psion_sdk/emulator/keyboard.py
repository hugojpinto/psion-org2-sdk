"""
Keyboard Controller for Psion Organiser II Emulator
====================================================

Ported from JAPE's keyboard.js to Python.

The Psion Organiser II has a 6x6 key matrix (plus ON/CLEAR):
- Row scan via keyboard counter register
- Column read via port 5

Key Matrix Layout (Normal keyboard):
    Col 0    Col 1    Col 2    Col 3    Col 4    Col 5
    -----    -----    -----    -----    -----    -----
Row 0: (ON)    MODE     UP      DOWN     LEFT    RIGHT
Row 1:   A       G       M        S       SHIFT    -
Row 2:   B       H       N        T       DEL      -
Row 3:   C       I       O        U        Y       -
Row 4:   E       K       Q        W       SPACE    -
Row 5:   F       L       R        X       EXE      -
Row 6:   D       J       P        V        Z       -

ON/CLEAR is special - it sets bit 7 of port 5 and can trigger NMI.

The keyboard counter is incremented by the semi-custom chip at $340 and
reset at $300. Bit 12 overflow triggers an NMI when in counter mode.

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, List, Tuple
from enum import IntEnum


class KeyboardLayout(IntEnum):
    """Keyboard layout variants."""
    NORMAL = 0  # Standard Organiser II layout
    ALPHAPOS = 1  # Alpha-positioned variant
    POS200 = 2  # POS 200 variant


# =============================================================================
# KEY MATRIX TABLES
# =============================================================================
# Maps grid coordinates (row, col) to key line and mask values.
# From JAPE's coor2line and coor2mask arrays.

# Row number for each grid position
# -1 indicates ON/CLEAR key (special handling)
COORD_TO_LINE = [
    [-1, 0, 0, 0, 0, 0],  # Row 0: ON/CLEAR, MODE, UP, DOWN, LEFT, RIGHT
    [1, 2, 3, 6, 4, 5],   # Row 1: A-F
    [1, 2, 3, 6, 4, 5],   # Row 2: G-L
    [1, 2, 3, 6, 4, 5],   # Row 3: M-R
    [1, 2, 3, 6, 4, 5],   # Row 4: S-X
    [1, 2, 3, 6, 4, 5],   # Row 5: Y-Z, SHIFT, DEL, SPACE, EXE
]

# Bit mask for each grid position
COORD_TO_MASK = [
    [-1, 0x04, 0x08, 0x10, 0x20, 0x40],
    [0x40, 0x40, 0x40, 0x40, 0x40, 0x40],
    [0x20, 0x20, 0x20, 0x20, 0x20, 0x20],
    [0x10, 0x10, 0x10, 0x10, 0x10, 0x10],
    [0x08, 0x08, 0x08, 0x08, 0x08, 0x08],
    [0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
]


# =============================================================================
# KEY NAME TO MATRIX MAPPING
# =============================================================================
# Maps key names to (line, mask, shift_type) tuples.
# shift_type: 0=no shift on Psion, 1=shift required on Psion, 2=use host shift

# Normal Organiser II keyboard layout
KEY_TO_GRID_NORMAL: Dict[str, Tuple[int, int, int]] = {
    # Special keys
    "ESCAPE": (-1, 0, 2), "ESC": (-1, 0, 2), "ON": (-1, 0, 2), "CLEAR": (-1, 0, 2),
    "F1": (0, 0x04, 2), "MODE": (0, 0x04, 2),
    "UP": (0, 0x08, 2), "ARROWUP": (0, 0x08, 2),
    "DOWN": (0, 0x10, 2), "ARROWDOWN": (0, 0x10, 2),
    "LEFT": (0, 0x20, 2), "ARROWLEFT": (0, 0x20, 2),
    "RIGHT": (0, 0x40, 2), "ARROWRIGHT": (0, 0x40, 2),

    # Letters (uppercase - also accept lowercase)
    "A": (1, 0x40, 0), "B": (2, 0x40, 0), "C": (3, 0x40, 0),
    "D": (6, 0x40, 0), "E": (4, 0x40, 0), "F": (5, 0x40, 0),
    "G": (1, 0x20, 0), "H": (2, 0x20, 0), "I": (3, 0x20, 0),
    "J": (6, 0x20, 0), "K": (4, 0x20, 0), "L": (5, 0x20, 0),
    "M": (1, 0x10, 0), "N": (2, 0x10, 0), "O": (3, 0x10, 0),
    "P": (6, 0x10, 0), "Q": (4, 0x10, 0), "R": (5, 0x10, 0),
    "S": (1, 0x08, 0), "T": (2, 0x08, 0), "U": (3, 0x08, 0),
    "V": (6, 0x08, 0), "W": (4, 0x08, 0), "X": (5, 0x08, 0),
    "Y": (3, 0x04, 0), "Z": (6, 0x04, 0),

    # Shift and special
    "SHIFT": (1, 0x04, 2),
    "DELETE": (2, 0x04, 2), "DEL": (2, 0x04, 2), "BACKSPACE": (2, 0x04, 2),
    " ": (4, 0x04, 2), "SPACE": (4, 0x04, 2), "SPACEBAR": (4, 0x04, 2),
    "ENTER": (5, 0x04, 2), "EXE": (5, 0x04, 2), "RETURN": (5, 0x04, 2),

    # Symbols (shifted letters on Psion)
    "<": (1, 0x40, 1), ">": (2, 0x40, 1), "(": (3, 0x40, 1),
    ")": (6, 0x40, 1), "%": (4, 0x40, 1), "/": (5, 0x40, 1),
    "=": (1, 0x20, 1), "\"": (2, 0x20, 1), "7": (3, 0x20, 1),
    "8": (6, 0x20, 1), "9": (4, 0x20, 1), "*": (5, 0x20, 1),
    ",": (1, 0x10, 1), "$": (2, 0x10, 1), "4": (3, 0x10, 1),
    "5": (6, 0x10, 1), "6": (4, 0x10, 1), "-": (5, 0x10, 1),
    ";": (1, 0x08, 1), ":": (2, 0x08, 1), "1": (3, 0x08, 1),
    "2": (6, 0x08, 1), "3": (4, 0x08, 1), "+": (5, 0x08, 1),
    "0": (3, 0x04, 1), ".": (6, 0x04, 1),
}


@dataclass
class KeyboardState:
    """
    Complete keyboard controller state for snapshotting.
    """
    counter: int = 0  # Keyboard scan counter
    disabled: bool = False  # Keyboard disabled flag


class Keyboard:
    """
    Keyboard matrix controller for Psion Organiser II.

    The keyboard uses a scanning approach:
    1. The keyboard counter determines which matrix lines are read
    2. Port 5 returns the combined state of selected lines
    3. ON/CLEAR is a special key that triggers NMI

    Keyboard counter:
    - Reset by write to $300
    - Increment by write to $340
    - Bit 12 overflow triggers NMI when in counter mode

    Port 5 read ($15):
    - Bits 2-6: Combined key line state (1=not pressed, 0=pressed)
    - Bit 1: Keyboard counter overflow
    - Bit 7: ON/CLEAR pressed

    Example:
        >>> kb = Keyboard()
        >>> kb.key_down("A")
        >>> kb.reset_counter()
        >>> for i in range(7):
        ...     kb.increment_counter()
        ...     port5 = kb.read_port5()
        ...     # Scan row i, check for pressed keys
        >>> kb.key_up("A")
    """

    def __init__(self, layout: KeyboardLayout = KeyboardLayout.NORMAL):
        """
        Initialize keyboard controller.

        Args:
            layout: Keyboard layout variant
        """
        self._layout = layout
        self._state = KeyboardState()

        # Select key mapping based on layout
        self._key_to_grid = KEY_TO_GRID_NORMAL  # Currently only support normal

        # Get shift key position
        shift_info = self._key_to_grid.get("SHIFT", (1, 0x04, 2))
        self._shift_line = shift_info[0]
        self._shift_mask = shift_info[1]

        # Key line states (0xFF = no keys pressed on this line)
        # Separate tracking for grid (on-screen keyboard) and physical keyboard
        self._key_lines_grid = [0xFF] * 8
        self._key_lines_keyboard = [0xFF] * 8

        # ON/CLEAR key state
        self._key_on_grid = False
        self._key_on_keyboard = False

        # Currently pressed keys (key name -> True)
        self._pressed_keys: Dict[str, bool] = {}

        # Callback to get current keyboard status from OS (for shift handling)
        self.get_key_stat: Optional[Callable[[], int]] = None

    @property
    def counter(self) -> int:
        """Current keyboard counter value."""
        return self._state.counter

    def reset_counter(self) -> None:
        """Reset keyboard counter to 0."""
        self._state.counter = 0

    def increment_counter(self) -> None:
        """Increment keyboard counter by 1."""
        self._state.counter += 1

    def counter_has_overflowed(self) -> bool:
        """Check if counter has overflowed (bit 12 set)."""
        return (self._state.counter & 0x1000) != 0

    def is_on_pressed(self) -> bool:
        """Check if ON/CLEAR key is pressed."""
        if self._state.disabled:
            return False
        return self._key_on_grid or self._key_on_keyboard

    def disable(self) -> None:
        """Disable keyboard input."""
        self._state.disabled = True

    def enable(self) -> None:
        """Enable keyboard input."""
        self._state.disabled = False

    def clear(self) -> None:
        """Clear all pressed keys."""
        self._pressed_keys.clear()
        for i in range(8):
            self._key_lines_grid[i] = 0xFF
            self._key_lines_keyboard[i] = 0xFF
        self._key_on_grid = False
        self._key_on_keyboard = False

    def read_port5(self) -> int:
        """
        Read keyboard port 5 value.

        Returns:
            Port 5 value with keyboard state:
            - Bits 2-6: Key line state (inverted, 0=pressed)
            - Bit 1: Counter overflow (VPP charged in hardware)
            - Bit 7: ON/CLEAR pressed
        """
        result = 0x7C  # Bits 2-6 high (no keys pressed)

        if not self._state.disabled:
            # Scan each line selected by counter
            for line in range(7):
                mask = 1 << line
                if (self._state.counter & mask) == 0:
                    # This line is selected (active low)
                    result &= self._key_lines_grid[line] & self._key_lines_keyboard[line]

            # Set bit 7 if ON/CLEAR pressed
            if self._key_on_grid or self._key_on_keyboard:
                result |= 0x80

        # Set bit 1 if counter overflowed
        if self.counter_has_overflowed():
            result |= 0x02

        return result

    # =========================================================================
    # Key Input API
    # =========================================================================

    def key_down(self, key: str) -> None:
        """
        Press a key.

        Args:
            key: Key name (e.g., "A", "ENTER", "MODE", "1", etc.)
        """
        key_upper = key.upper()

        # Handle lowercase letters
        if len(key) == 1 and key.isalpha():
            key_upper = key.upper()

        grid_info = self._key_to_grid.get(key_upper)
        if grid_info is None:
            # Try the original key (for symbols)
            grid_info = self._key_to_grid.get(key)

        if grid_info is None:
            return  # Unknown key

        line, mask, shift_type = grid_info

        if line < 0:
            # ON/CLEAR key
            self._key_on_keyboard = True
        else:
            # Regular key - clear the bit (0 = pressed)
            self._key_lines_keyboard[line] &= (0x7F - mask)

            # Handle shift if needed
            if shift_type == 1:
                # This key requires shift on Psion
                ks = self.get_key_stat() if self.get_key_stat else 0
                if (ks & 0x40) == 0:
                    # Need to auto-press shift
                    self._key_lines_keyboard[self._shift_line] &= (0x7F - self._shift_mask)

        self._pressed_keys[key] = True

    def key_up(self, key: str) -> None:
        """
        Release a key.

        Args:
            key: Key name (e.g., "A", "ENTER", "MODE", etc.)
        """
        key_upper = key.upper()

        # Handle lowercase letters
        if len(key) == 1 and key.isalpha():
            key_upper = key.upper()

        grid_info = self._key_to_grid.get(key_upper)
        if grid_info is None:
            grid_info = self._key_to_grid.get(key)

        if grid_info is None:
            return  # Unknown key

        line, mask, shift_type = grid_info

        if line < 0:
            # ON/CLEAR key
            self._key_on_keyboard = False
        else:
            # Regular key - set the bit (1 = not pressed)
            self._key_lines_keyboard[line] |= (0x80 + mask)

            # Release shift if we auto-pressed it
            if shift_type == 1:
                self._key_lines_keyboard[self._shift_line] |= (0x80 + self._shift_mask)

        if key in self._pressed_keys:
            del self._pressed_keys[key]

    def is_key_down(self, key: str) -> bool:
        """
        Check if a key is currently pressed.

        Args:
            key: Key name (e.g., "A", "ENTER", "MODE", etc.)

        Returns:
            True if key is pressed, False otherwise
        """
        return key in self._pressed_keys or key.upper() in self._pressed_keys

    def tap_key(self, key: str) -> None:
        """
        Simulate a quick key press and release.

        Note: In emulation, this just sets the key state.
        The caller should advance emulation time between press and release.

        Args:
            key: Key name
        """
        self.key_down(key)
        # In real usage, run emulation for some cycles here
        self.key_up(key)

    def type_text(self, text: str) -> List[str]:
        """
        Convert text to sequence of key presses.

        Returns list of key names that should be pressed in sequence
        (with appropriate timing between each).

        Args:
            text: Text to type

        Returns:
            List of key names in order
        """
        result = []
        for char in text:
            char_upper = char.upper()

            # Check if we have a mapping for this character
            if char_upper in self._key_to_grid:
                result.append(char_upper)
            elif char in self._key_to_grid:
                result.append(char)
            elif char == '\n':
                result.append("ENTER")
            # Unknown characters are skipped

        return result

    # =========================================================================
    # Grid Input (for on-screen keyboard simulation)
    # =========================================================================

    def do_grid(self, row: int, col: int, down: bool) -> None:
        """
        Handle on-screen grid keyboard press/release.

        Args:
            row: Grid row (0-5)
            col: Grid column (0-5)
            down: True for press, False for release
        """
        if row == 0 and col == 0:
            # ON/CLEAR key
            self._key_on_grid = down
        else:
            if 0 <= row < len(COORD_TO_LINE) and 0 <= col < len(COORD_TO_LINE[0]):
                line = COORD_TO_LINE[row][col]
                mask = COORD_TO_MASK[row][col]

                if line >= 0:
                    if down:
                        self._key_lines_grid[line] &= (0x7F - mask)
                    else:
                        self._key_lines_grid[line] |= (0x80 + mask)

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def get_snapshot_data(self) -> List[int]:
        """Get keyboard state for snapshot."""
        result = [
            self._state.counter & 0xFF,
            (self._state.counter >> 8) & 0xFF,
            1 if self._state.disabled else 0,
            1 if self._key_on_grid else 0,
            1 if self._key_on_keyboard else 0,
        ]
        result.extend(self._key_lines_grid)
        result.extend(self._key_lines_keyboard)
        return result

    def apply_snapshot_data(self, data: List[int], offset: int = 0) -> int:
        """Restore keyboard state from snapshot."""
        self._state.counter = data[offset] | (data[offset + 1] << 8)
        self._state.disabled = data[offset + 2] != 0
        self._key_on_grid = data[offset + 3] != 0
        self._key_on_keyboard = data[offset + 4] != 0

        pos = offset + 5
        for i in range(8):
            self._key_lines_grid[i] = data[pos + i]
        pos += 8
        for i in range(8):
            self._key_lines_keyboard[i] = data[pos + i]
        pos += 8

        return pos - offset
