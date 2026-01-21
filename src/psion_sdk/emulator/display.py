"""
LCD Display Controller for Psion Organiser II Emulator
=======================================================

Ported from JAPE's display.js to Python.

The Psion Organiser II uses an HD44780-compatible LCD controller with:
- 2-line models (CM/XP): 16 columns × 2 rows
- 4-line models (LZ): 20 columns × 4 rows

Display RAM is 128 bytes total, with complex mapping from screen positions
to memory addresses (screen2mem arrays from JAPE).

Character display:
- 5 pixels wide × 8 pixels tall per character
- 256 character codes (0-255)
- Codes 0-7 are User Defined Graphics (UDG)
- Codes 8-31 are control codes (map to blank or special chars)
- Codes 32-255 are printable characters

Copyright (c) 2025 Hugo José Pinto & Contributors
Ported from JAPE by Jaap Scherphuis
"""

from dataclasses import dataclass
from typing import Optional, List

# =============================================================================
# CHARACTER BITMAP DATA
# =============================================================================
# These arrays contain 5x8 pixel bitmaps for 256 characters.
# Each character is 8 bytes (8 rows), with 5 bits per row (LSB = rightmost pixel).
# Extracted from JAPE's display.js char2 and char4 arrays.

# Character set for 2-line models (CM/XP)
CHAR2_BITMAP = bytes([
    0,0,0,0,0,0,0,0,4,4,4,4,0,0,4,0,10,10,10,0,0,0,0,0,10,10,31,10,31,10,10,0,4,15,20,14,5,30,4,0,24,25,2,4,8,19,3,0,12,18,20,8,21,18,13,0,12,4,8,0,0,0,0,0,
    2,4,8,8,8,4,2,0,8,4,2,2,2,4,8,0,0,4,21,14,21,4,0,0,0,4,4,31,4,4,0,0,0,0,0,0,12,4,8,0,0,0,0,31,0,0,0,0,0,0,0,0,0,12,12,0,0,1,2,4,8,16,0,0,
    14,17,19,21,25,17,14,0,4,12,4,4,4,4,14,0,14,17,1,2,4,8,31,0,31,2,4,2,1,17,14,0,2,6,10,18,31,2,2,0,31,16,30,1,1,17,14,0,6,8,16,30,17,17,14,0,31,1,2,4,8,8,8,0,
    14,17,17,14,17,17,14,0,14,17,17,15,1,2,12,0,0,12,12,0,12,12,0,0,0,12,12,0,12,4,8,0,2,4,8,16,8,4,2,0,0,0,31,0,31,0,0,0,8,4,2,1,2,4,8,0,14,17,1,2,4,0,4,0,
    14,17,1,13,21,21,14,0,14,17,17,17,31,17,17,0,30,17,17,30,17,17,30,0,14,17,16,16,16,17,14,0,28,18,17,17,17,18,28,0,31,16,16,30,16,16,31,0,31,16,16,30,16,16,16,0,14,17,16,23,17,17,15,0,
    17,17,17,31,17,17,17,0,14,4,4,4,4,4,14,0,7,2,2,2,2,18,12,0,17,18,20,24,20,18,17,0,16,16,16,16,16,16,31,0,17,27,21,21,17,17,17,0,17,17,25,21,19,17,17,0,14,17,17,17,17,17,14,0,
    30,17,17,30,16,16,16,0,14,17,17,17,21,18,13,0,30,17,17,30,20,18,17,0,15,16,16,14,1,1,30,0,31,4,4,4,4,4,4,0,17,17,17,17,17,17,14,0,17,17,17,17,17,10,4,0,17,17,17,21,21,21,10,0,
    17,17,10,4,10,17,17,0,17,17,17,10,4,4,4,0,31,1,2,4,8,16,31,0,14,8,8,8,8,8,14,0,17,10,31,4,31,4,4,0,14,2,2,2,2,2,14,0,4,10,17,0,0,0,0,0,0,0,0,0,0,0,31,0,
    8,4,2,0,0,0,0,0,0,0,14,1,15,17,15,0,16,16,22,25,17,17,30,0,0,0,14,16,16,17,14,0,1,1,13,19,17,17,15,0,0,0,14,17,31,16,14,0,6,9,8,28,8,8,8,0,0,15,17,17,15,1,14,0,
    16,16,22,25,17,17,17,0,4,0,12,4,4,4,14,0,2,0,6,2,2,18,12,0,16,16,18,20,24,20,18,0,12,4,4,4,4,4,14,0,0,0,26,21,21,17,17,0,0,0,22,25,17,17,17,0,0,0,14,17,17,17,14,0,
    0,0,30,17,30,16,16,0,0,0,13,19,15,1,1,0,0,0,22,25,16,16,16,0,0,0,14,16,14,1,30,0,8,8,28,8,8,9,6,0,0,0,17,17,17,19,13,0,0,0,17,17,17,10,4,0,0,0,17,17,21,21,10,0,
    0,0,17,10,4,10,17,0,0,0,17,17,15,1,14,0,0,0,31,2,4,8,31,0,2,4,4,8,4,4,2,0,4,4,4,4,4,4,4,0,8,4,4,2,4,4,8,0,0,4,2,31,2,4,0,0,0,4,8,31,8,4,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,28,20,28,0,7,4,4,4,0,0,0,0,0,0,0,4,4,4,28,0,0,0,0,0,16,8,4,0,0,0,0,12,12,0,0,0,0,31,1,31,1,2,4,0,0,0,31,1,6,4,8,0,
    0,0,2,4,12,20,4,0,0,0,4,31,17,1,6,0,0,0,0,31,4,4,31,0,0,0,2,31,6,10,18,0,0,0,8,31,9,10,8,0,0,0,0,14,2,2,31,0,0,0,30,2,30,2,30,0,0,0,0,21,21,1,6,0,
    0,0,0,31,0,0,0,0,31,1,5,6,4,4,8,0,1,2,4,12,20,4,4,0,4,31,17,17,1,2,4,0,0,31,4,4,4,4,31,0,2,31,2,6,10,18,2,0,8,31,9,9,9,9,18,0,4,31,4,31,4,4,4,0,
    0,15,9,17,1,2,12,0,8,15,18,2,2,2,4,0,0,31,1,1,1,1,31,0,10,31,10,10,2,4,8,0,0,24,1,25,1,2,28,0,0,31,1,2,4,10,17,0,8,31,9,10,8,8,7,0,0,17,17,9,1,2,12,0,
    0,15,9,21,3,2,12,0,2,28,4,31,4,4,8,0,0,21,21,21,1,2,4,0,14,0,31,4,4,4,8,0,8,8,8,12,10,8,8,0,4,4,31,4,4,8,16,0,0,14,0,0,0,0,31,0,0,31,1,10,4,10,16,0,
    4,31,2,4,14,21,4,0,2,2,2,2,2,4,8,0,0,4,2,17,17,17,17,0,16,16,31,16,16,16,15,0,0,31,1,1,1,2,12,0,0,8,20,2,1,1,0,0,4,31,4,4,21,21,4,0,0,31,1,1,10,4,2,0,
    0,14,0,14,0,14,1,0,0,4,8,16,17,31,1,0,0,1,1,10,4,10,16,0,0,31,8,31,8,8,7,0,8,8,31,9,10,8,8,0,0,14,2,2,2,2,31,0,0,31,1,31,1,1,31,0,14,0,31,1,1,2,4,0,
    18,18,18,18,2,4,8,0,0,4,20,20,21,21,22,0,0,16,16,17,18,20,24,0,0,31,17,17,17,17,31,0,0,31,17,17,1,2,4,0,0,24,0,1,1,2,28,0,4,18,8,0,0,0,0,0,28,20,28,0,0,0,0,0,
    0,0,9,21,18,18,13,0,10,0,14,1,15,17,15,0,0,0,14,17,30,17,30,16,0,0,14,16,12,17,14,0,0,0,17,17,17,19,29,16,0,0,15,20,18,17,14,0,0,0,6,9,17,17,30,16,0,0,15,17,17,17,15,1,
    0,0,7,4,4,20,8,0,0,2,26,2,0,0,0,0,2,0,6,2,2,2,2,2,0,20,8,20,0,0,0,0,0,4,14,20,21,14,4,0,8,8,28,8,28,8,15,0,14,0,22,25,17,17,17,0,10,0,14,17,17,17,14,0,
    0,0,22,25,17,17,30,16,0,0,13,19,17,17,15,1,0,14,17,31,17,17,14,0,0,0,0,11,21,26,0,0,0,0,14,17,17,10,27,0,10,0,17,17,17,19,13,0,31,16,8,4,8,16,31,0,0,0,31,10,10,10,19,0,
    31,0,17,10,4,10,17,0,0,0,17,17,17,17,15,1,0,1,30,4,31,4,4,0,0,0,31,8,15,9,17,0,0,0,31,21,31,17,17,0,0,0,4,0,31,0,4,0,0,0,0,0,0,0,0,0,31,31,31,31,31,31,31,31
])

# Character set for 4-line models (LZ) - similar but with some variations
CHAR4_BITMAP = bytes([
    0,0,0,0,0,0,0,0,4,4,4,4,0,0,4,0,10,10,10,0,0,0,0,0,10,10,31,10,31,10,10,0,4,15,20,14,5,30,4,0,24,25,2,4,8,19,3,0,12,18,20,8,21,18,13,0,12,4,8,0,0,0,0,0,
    2,4,8,8,8,4,2,0,8,4,2,2,2,4,8,0,0,4,21,14,21,4,0,0,0,4,4,31,4,4,0,0,0,0,0,0,12,4,8,0,0,0,0,31,0,0,0,0,0,0,0,0,0,12,12,0,0,1,2,4,8,16,0,0,
    14,17,19,21,25,17,14,0,4,12,4,4,4,4,14,0,14,17,1,2,4,8,31,0,31,2,4,2,1,17,14,0,2,6,10,18,31,2,2,0,31,16,30,1,1,17,14,0,6,8,16,30,17,17,14,0,31,1,2,4,8,8,8,0,
    14,17,17,14,17,17,14,0,14,17,17,15,1,2,12,0,0,12,12,0,12,12,0,0,0,12,12,0,12,4,8,0,2,4,8,16,8,4,2,0,0,0,31,0,31,0,0,0,8,4,2,1,2,4,8,0,14,17,1,2,4,0,4,0,
    14,17,1,13,21,21,14,0,14,17,17,17,31,17,17,0,30,17,17,30,17,17,30,0,14,17,16,16,16,17,14,0,28,18,17,17,17,18,28,0,31,16,16,30,16,16,31,0,31,16,16,30,16,16,16,0,14,17,16,23,17,17,15,0,
    17,17,17,31,17,17,17,0,14,4,4,4,4,4,14,0,7,2,2,2,2,18,12,0,17,18,20,24,20,18,17,0,16,16,16,16,16,16,31,0,17,27,21,21,17,17,17,0,17,17,25,21,19,17,17,0,14,17,17,17,17,17,14,0,
    30,17,17,30,16,16,16,0,14,17,17,17,21,18,13,0,30,17,17,30,20,18,17,0,15,16,16,14,1,1,30,0,31,4,4,4,4,4,4,0,17,17,17,17,17,17,14,0,17,17,17,17,17,10,4,0,17,17,17,21,21,21,10,0,
    17,17,10,4,10,17,17,0,17,17,17,10,4,4,4,0,31,1,2,4,8,16,31,0,14,8,8,8,8,8,14,0,0,16,8,4,2,1,0,0,14,2,2,2,2,2,14,0,4,10,17,0,0,0,0,0,0,0,0,0,0,0,31,0,
    8,4,2,0,0,0,0,0,0,0,14,1,15,17,15,0,16,16,22,25,17,17,30,0,0,0,14,16,16,17,14,0,1,1,13,19,17,17,15,0,0,0,14,17,31,16,14,0,6,9,8,28,8,8,8,0,0,15,17,17,15,1,14,0,
    16,16,22,25,17,17,17,0,4,0,12,4,4,4,14,0,2,0,6,2,2,18,12,0,16,16,18,20,24,20,18,0,12,4,4,4,4,4,14,0,0,0,26,21,21,17,17,0,0,0,22,25,17,17,17,0,0,0,14,17,17,17,14,0,
    0,0,30,17,30,16,16,0,0,0,13,19,15,1,1,0,0,0,22,25,16,16,16,0,0,0,14,16,14,1,30,0,8,8,28,8,8,9,6,0,0,0,17,17,17,19,13,0,0,0,17,17,17,10,4,0,0,0,17,17,21,21,10,0,
    0,0,17,10,4,10,17,0,0,0,17,17,15,1,14,0,0,0,31,2,4,8,31,0,2,4,4,8,4,4,2,0,4,4,4,4,4,4,4,0,8,4,4,2,4,4,8,0,0,4,2,31,2,4,0,0,0,4,8,31,8,4,0,0,
    14,17,16,16,17,14,4,0,10,0,17,17,17,19,13,0,2,4,14,17,31,16,14,0,4,10,14,1,15,17,15,0,10,0,14,1,15,17,15,0,8,4,14,1,15,17,15,0,4,0,14,1,15,17,15,0,0,0,14,16,17,14,4,0,
    4,10,14,17,31,16,14,0,10,0,14,17,31,16,14,0,8,4,14,17,31,16,14,0,10,0,12,4,4,4,14,0,4,10,12,4,4,4,14,0,4,2,12,4,4,4,14,0,10,0,14,17,17,31,17,0,4,0,14,17,17,31,17,0,
    4,8,31,16,30,16,31,0,0,0,26,5,30,20,11,0,15,20,20,22,28,20,23,0,4,10,0,14,17,17,14,0,10,0,0,14,17,17,14,0,4,2,0,14,17,17,14,0,4,10,17,17,17,19,13,0,8,4,17,17,17,19,13,0,
    10,0,17,17,15,1,14,0,10,0,14,17,17,17,14,0,10,0,17,17,17,17,14,0,0,0,14,19,21,25,14,0,6,9,8,28,8,30,25,0,14,19,19,21,25,25,14,0,0,0,10,4,10,0,0,0,2,5,4,14,4,8,16,0,
    2,4,14,1,15,17,15,0,4,8,12,4,4,4,14,0,4,8,0,14,17,17,14,0,2,4,17,17,17,19,13,0,5,10,22,25,17,17,17,0,5,10,17,25,21,19,17,0,14,1,15,17,15,0,14,0,14,17,17,17,14,0,14,0,
    4,0,4,8,16,17,14,0,4,14,21,4,4,4,0,0,0,4,4,4,21,14,4,0,18,20,8,22,9,2,7,0,18,20,10,22,10,15,2,0,4,0,0,4,4,4,4,0,0,5,10,20,10,5,0,0,0,20,10,5,10,20,0,0,
    14,16,14,1,17,14,4,0,0,14,16,14,1,14,4,0,14,0,14,16,23,17,14,0,14,0,15,17,15,1,14,0,4,0,14,4,4,4,14,0,2,4,14,17,17,31,17,0,4,10,14,17,17,31,17,0,8,4,14,17,17,31,17,0,
    14,17,23,21,23,17,14,0,0,0,0,12,4,4,14,0,31,9,8,8,8,8,28,0,0,0,4,10,17,17,31,0,0,0,4,10,17,17,17,0,0,31,0,14,0,31,0,0,17,10,31,4,31,4,4,0,0,31,10,10,10,10,10,0,
    14,4,14,21,14,4,14,0,4,21,21,21,21,14,4,0,0,0,0,13,18,18,13,0,0,0,10,10,4,10,4,0,0,14,8,4,10,18,12,0,0,0,14,16,28,16,14,0,5,10,14,1,15,17,15,0,5,10,14,17,17,31,17,0,
    4,6,8,8,4,2,4,0,0,0,22,9,9,9,1,0,0,0,6,9,31,18,12,0,0,0,18,20,24,20,18,0,0,0,16,8,4,10,17,0,8,12,16,12,16,12,2,0,0,0,7,12,18,12,0,0,0,0,14,16,12,2,6,0,
    0,0,14,4,4,4,2,0,0,0,18,9,9,5,6,0,4,10,31,16,30,16,31,0,10,0,31,16,30,16,31,0,4,2,31,16,30,16,31,0,0,0,4,21,21,14,4,0,2,4,14,4,4,4,14,0,4,10,14,4,4,4,14,0,
    10,0,14,4,4,4,14,0,0,0,27,17,17,21,10,0,4,8,0,13,18,18,13,0,2,4,14,16,28,16,14,0,2,4,22,9,9,9,1,0,2,4,27,17,17,21,10,0,8,4,14,4,4,4,14,0,28,20,28,0,0,0,0,0,
    2,4,14,17,17,17,14,0,0,0,14,17,30,17,30,16,4,10,14,17,17,17,14,0,8,4,14,17,17,17,14,0,5,10,0,14,17,17,14,0,5,10,14,17,17,17,14,0,0,0,17,17,19,29,16,16,0,12,18,18,28,16,16,16,
    0,0,7,4,4,20,8,0,0,2,26,2,0,0,0,0,4,10,17,17,17,17,14,0,8,4,17,17,17,17,14,0,0,4,14,20,21,14,4,0,2,4,17,17,10,4,4,0,2,4,17,17,15,1,14,0,2,4,17,17,17,17,14,0,
    28,8,14,9,14,8,28,0,4,4,31,4,4,0,31,0,0,14,17,31,17,17,14,0,0,0,0,11,21,26,0,0,0,0,14,17,17,10,27,0,21,10,21,10,21,10,21,10,31,16,8,4,8,16,31,0,0,0,31,10,10,10,19,0,
    16,8,24,10,22,15,2,0,0,10,27,31,14,14,4,0,0,4,14,31,14,4,0,0,4,14,14,27,27,4,14,0,4,14,31,31,21,4,14,0,0,0,4,0,31,0,4,0,0,0,0,0,0,0,0,0,31,31,31,31,31,31,31,31
])

# =============================================================================
# SCREEN TO MEMORY MAPPING
# =============================================================================
# Maps screen positions (left-to-right, top-to-bottom) to display RAM addresses.
# The HD44780 LCD controller has a complex memory layout.

# 2-line display (16x2) memory mapping
SCREEN2MEM_2LINE = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,  # Row 0
    64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79  # Row 1
]

# 4-line display (20x4) memory mapping
# This is more complex due to the HD44780's internal DDRAM layout
SCREEN2MEM_4LINE = [
    0, 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 30, 31,  # Row 0
    64, 65, 66, 67, 72, 73, 74, 75, 76, 77, 78, 79, 88, 89, 90, 91, 92, 93, 94, 95,  # Row 1
    4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22, 23, 32, 33, 34, 35, 36, 37, 38, 39,  # Row 2
    68, 69, 70, 71, 80, 81, 82, 83, 84, 85, 86, 87, 96, 97, 98, 99, 100, 101, 102, 103  # Row 3
]


@dataclass
class DisplayState:
    """
    Complete display controller state for snapshotting.

    All fields are ported from JAPE's display.js internal variables.
    """
    num_lines: int = 2  # 2 or 4
    cursor_pos: int = 0  # Current cursor position in DDRAM
    scr_ptr: int = 0  # Screen memory pointer
    udg_ptr: int = 0  # UDG (User Defined Graphics) pointer
    cursor_state: bool = True  # Cursor enabled
    cursor_ul: bool = False  # Underline cursor
    cursor_fl: bool = False  # Flashing cursor
    cursor_timer: bool = False  # Current flash state
    addr_incr: bool = False  # Auto-increment mode
    is_on: bool = False  # Display powered on
    ptr_to_screen: bool = True  # True=data goes to screen, False=to UDG
    contrast: int = 5  # Contrast level (0-10)


class Display:
    """
    HD44780-compatible LCD display controller.

    The Psion Organiser II uses an HD44780 LCD controller with:
    - 2-line models (CM/XP): 16 columns × 2 rows
    - 4-line models (LZ): 20 columns × 4 rows

    Display RAM:
    - 128 bytes for character data
    - 64 bytes for User Defined Graphics (8 characters × 8 bytes)

    Command interface (HD44780 protocol):
    - Commands sent to $180 (command register)
    - Data sent to $181 (data register)

    Example:
        >>> display = Display(num_lines=4)
        >>> display.switch_on()
        >>> display.command(0x80)  # Set cursor to position 0
        >>> display.set_data(ord('H'))  # Write 'H'
        >>> display.set_data(ord('i'))  # Write 'i'
        >>> print(display.get_text())  # Returns "Hi" + spaces
    """

    # Display RAM size constants
    DISPLAY_RAM_SIZE = 128
    UDG_RAM_SIZE = 64

    def __init__(self, num_lines: int = 2):
        """
        Initialize display controller.

        Args:
            num_lines: Number of display lines (2 or 4)
        """
        if num_lines not in (2, 4):
            raise ValueError(f"num_lines must be 2 or 4, got {num_lines}")

        self._state = DisplayState(num_lines=num_lines)

        # Set dimensions based on model
        self._num_columns = 20 if num_lines == 4 else 16

        # Select character bitmap and screen mapping
        self._char_bitmap = CHAR4_BITMAP if num_lines == 4 else CHAR2_BITMAP
        self._screen2mem = SCREEN2MEM_4LINE if num_lines == 4 else SCREEN2MEM_2LINE

        # Build reverse mapping (memory address -> screen position)
        self._mem2screen: dict[int, int] = {}
        for screen_pos, mem_addr in enumerate(self._screen2mem):
            self._mem2screen[mem_addr] = screen_pos

        # Allocate display RAM (128 bytes) and UDG RAM (64 bytes)
        self._display_data = bytearray(self.DISPLAY_RAM_SIZE)
        self._udg_data = bytearray(self.UDG_RAM_SIZE)

        # Track if display needs refresh (for external rendering)
        self._needs_refresh = True

    @property
    def num_lines(self) -> int:
        """Number of display lines (2 or 4)."""
        return self._state.num_lines

    @property
    def num_columns(self) -> int:
        """Number of display columns (16 or 20)."""
        return self._num_columns

    @property
    def is_on(self) -> bool:
        """True if display is powered on."""
        return self._state.is_on

    @property
    def needs_refresh(self) -> bool:
        """True if display content has changed since last read."""
        return self._needs_refresh

    def switch_on(self) -> None:
        """
        Power on the display.

        Initializes display to default state with spaces in all positions.
        """
        self._state.cursor_pos = 0
        self._state.scr_ptr = 0
        self._state.cursor_state = True
        self._state.cursor_ul = False
        self._state.cursor_fl = False
        self._state.cursor_timer = False
        self._state.addr_incr = False
        self._state.is_on = True
        self._state.ptr_to_screen = True

        # Clear UDG and display RAM
        for i in range(self.UDG_RAM_SIZE):
            self._udg_data[i] = 0
        for i in range(self.DISPLAY_RAM_SIZE):
            self._display_data[i] = 32  # Space character

        self._needs_refresh = True

    def switch_off(self) -> None:
        """Power off the display."""
        self._state.is_on = False
        self._needs_refresh = True

    def reset(self) -> None:
        """Reset display (alias for switch_off)."""
        self.switch_off()

    def command(self, data: int) -> None:
        """
        Process HD44780 LCD command.

        Command encoding (from HD44780 datasheet):
        - 1AAAAAAA: Set DDRAM address to AAAAAAA
        - 01AAAAAA: Set CGRAM address to AAAAAA (UDG data)
        - 001BLHxx: Function set (byte/nibble, lines, height)
        - 0001SDxx: Cursor/display shift
        - 00001EUF: Display on/off control
        - 000001AD: Entry mode set (address auto-increment)
        - 0000001x: Return home
        - 00000001: Clear display

        Args:
            data: 8-bit command byte
        """
        if (data & 0x80) != 0:
            # 1AAAAAAA - Set DDRAM address
            if self._state.ptr_to_screen:
                self._state.cursor_pos = data & 0x7F
                self._state.scr_ptr = data & 0x7F
                if self._state.cursor_state:
                    self._needs_refresh = True
            self._state.ptr_to_screen = True

        elif (data & 0x40) != 0:
            # 01AAAAAA - Set CGRAM address (UDG)
            self._state.udg_ptr = data & 0x3F
            self._state.ptr_to_screen = False

        elif (data & 0x20) != 0:
            # 001BLHxx - Function set
            # Ignored for now (byte mode, line count fixed at init)
            pass

        elif (data & 0x10) != 0:
            # 0001SDxx - Cursor/display shift
            if (data & 0x08) == 0:
                # Cursor move
                if (data & 0x04) != 0:
                    self._state.cursor_pos = (self._state.cursor_pos + 1) & 0x7F
                else:
                    self._state.cursor_pos = (self._state.cursor_pos - 1) & 0x7F
                self._needs_refresh = True
            # Display shift ignored for now

        elif (data & 0x08) != 0:
            # 00001EUF - Display on/off control
            self._state.cursor_state = (data & 0x04) != 0
            self._state.cursor_ul = (data & 0x02) != 0
            self._state.cursor_fl = (data & 0x01) != 0
            self._needs_refresh = True

        elif (data & 0x04) != 0:
            # 000001AD - Entry mode set
            self._state.addr_incr = (data & 0x02) != 0
            # Display auto-increment ignored for now

        elif (data & 0x02) != 0:
            # 0000001x - Return home
            self._state.cursor_pos = 0
            self._needs_refresh = True

        elif (data & 0x01) != 0:
            # 00000001 - Clear display
            for i in range(self.DISPLAY_RAM_SIZE):
                self._display_data[i] = 32  # Space
            self._state.cursor_pos = 0
            self._state.scr_ptr = 0
            self._needs_refresh = True

    def set_data(self, data: int) -> None:
        """
        Write data to display or UDG RAM.

        Where data is written depends on ptr_to_screen flag:
        - True: Write to display RAM at scr_ptr
        - False: Write to UDG RAM at udg_ptr

        Args:
            data: 8-bit data byte
        """
        data = data & 0xFF

        if self._state.ptr_to_screen:
            # Write to display RAM
            self._display_data[self._state.scr_ptr] = data

            # Mark refresh if this position is visible
            if self._state.scr_ptr in self._mem2screen:
                self._needs_refresh = True

            if self._state.addr_incr:
                self._state.scr_ptr += 1
                # Handle wrap at line boundary for 4-line displays
                if self._state.num_lines == 4 and self._state.scr_ptr == 40:
                    self._state.scr_ptr = 64
                self._state.scr_ptr &= 0x7F
        else:
            # Write to UDG RAM
            self._udg_data[self._state.udg_ptr] = data
            self._state.udg_ptr = (self._state.udg_ptr + 1) & 0x3F
            self._needs_refresh = True

    def get_data(self) -> int:
        """
        Read data from display or UDG RAM.

        Returns:
            8-bit data byte from current pointer position
        """
        if self._state.ptr_to_screen:
            result = self._display_data[self._state.scr_ptr]
            self._state.scr_ptr = (self._state.scr_ptr + 1) & 0x7F
        else:
            result = self._udg_data[self._state.udg_ptr]
            self._state.udg_ptr = (self._state.udg_ptr + 1) & 0x3F

        return result

    # =========================================================================
    # Text Access API (for testing and debugging)
    # =========================================================================

    def get_text_grid(self) -> List[str]:
        """
        Get display contents as list of strings (one per line).

        Returns:
            List of strings, one per display line
        """
        if not self._state.is_on:
            return ["" for _ in range(self._state.num_lines)]

        result = []
        pos = 0
        for line in range(self._state.num_lines):
            line_chars = []
            for col in range(self._num_columns):
                addr = self._screen2mem[pos]
                char_code = self._display_data[addr]
                # Convert character code to displayable character
                if 32 <= char_code < 127:
                    line_chars.append(chr(char_code))
                else:
                    line_chars.append(' ')  # Non-printable
                pos += 1
            result.append("".join(line_chars))

        self._needs_refresh = False
        return result

    def get_text(self) -> str:
        """
        Get display contents as single string with newlines.

        Returns:
            Display text with '\\n' separating lines
        """
        return "\n".join(self.get_text_grid())

    def get_char_at(self, row: int, col: int) -> int:
        """
        Get character code at specific screen position.

        Args:
            row: Row number (0-based)
            col: Column number (0-based)

        Returns:
            Character code at position (0-255)
        """
        if not (0 <= row < self._state.num_lines and 0 <= col < self._num_columns):
            raise ValueError(f"Invalid position ({row}, {col})")

        screen_pos = row * self._num_columns + col
        mem_addr = self._screen2mem[screen_pos]
        return self._display_data[mem_addr]

    # =========================================================================
    # Pixel Buffer API (for graphical rendering)
    # =========================================================================

    def get_pixel_buffer(self) -> bytes:
        """
        Get display as pixel buffer.

        Returns:
            Bytes containing pixel data (1 bit per pixel, packed).
            Format: Row-major, MSB first.
            Size: (num_lines * 8) rows × (num_columns * 5 + gaps) columns
        """
        if not self._state.is_on:
            return bytes(self._state.num_lines * 8 * (self._num_columns * 5))

        # Calculate dimensions
        char_width = 5
        char_height = 8
        width = self._num_columns * char_width
        height = self._state.num_lines * char_height

        # Create pixel buffer (1 byte per pixel for simplicity)
        pixels = bytearray(width * height)

        # Render each character
        for line in range(self._state.num_lines):
            for col in range(self._num_columns):
                screen_pos = line * self._num_columns + col
                mem_addr = self._screen2mem[screen_pos]
                char_code = self._display_data[mem_addr]

                # Get character bitmap
                if char_code < 8:
                    # UDG character (0-7)
                    bitmap_offset = char_code * 8
                    char_data = self._udg_data
                else:
                    # Normal character (map 8-31 to 0)
                    bitmap_offset = max((char_code - 32), 0) * 8
                    char_data = self._char_bitmap

                # Render character pixels
                base_x = col * char_width
                base_y = line * char_height

                for row_idx in range(char_height):
                    if bitmap_offset + row_idx < len(char_data):
                        row_data = char_data[bitmap_offset + row_idx]
                    else:
                        row_data = 0

                    for bit_idx in range(char_width):
                        # LSB = rightmost pixel
                        pixel_on = (row_data >> bit_idx) & 1
                        pixel_x = base_x + (char_width - 1 - bit_idx)
                        pixel_y = base_y + row_idx
                        pixels[pixel_y * width + pixel_x] = pixel_on * 255

        self._needs_refresh = False
        return bytes(pixels)

    def render_image(self, scale: int = 2) -> Optional[bytes]:
        """
        Render display as PNG image (requires PIL).

        Args:
            scale: Pixel scale factor (default 2)

        Returns:
            PNG image bytes, or None if PIL not available
        """
        try:
            from PIL import Image
            import io
        except ImportError:
            return None

        # Get pixel buffer
        pixels = self.get_pixel_buffer()

        # Calculate dimensions
        char_width = 5
        char_height = 8
        width = self._num_columns * char_width
        height = self._state.num_lines * char_height

        # Create image
        img = Image.new('L', (width * scale, height * scale), color=180)  # Gray background

        # Fill pixels
        for y in range(height):
            for x in range(width):
                pixel = pixels[y * width + x]
                color = 32 if pixel else 180  # Dark gray for on, light for off
                for sy in range(scale):
                    for sx in range(scale):
                        img.putpixel((x * scale + sx, y * scale + sy), color)

        # Export as PNG
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def render_image_lcd(
        self,
        scale: int = 3,
        pixel_gap: int = 1,
        char_gap: int = 2,
        bezel: int = 8,
        ink_color: tuple = (40, 42, 40),
        paper_color: tuple = (148, 156, 132),
        grid_color: tuple = (136, 144, 120),
        bezel_color: tuple = (180, 180, 175),
    ) -> Optional[bytes]:
        """
        Render display as PNG image with LCD matrix grid visible.

        Creates a realistic LCD display rendering showing the character
        cell boundaries and pixel grid, similar to a real Psion display.

        Args:
            scale: Pixel scale factor (default 3)
            pixel_gap: Gap between pixels within a character (default 1)
            char_gap: Gap between character cells (default 2)
            bezel: Bezel/border size around display (default 8)
            ink_color: RGB tuple for "on" pixels (default dark gray-green)
            paper_color: RGB tuple for LCD background (default LCD green)
            grid_color: RGB tuple for grid lines (default darker LCD green)
            bezel_color: RGB tuple for bezel (default light gray)

        Returns:
            PNG image bytes, or None if PIL not available
        """
        try:
            from PIL import Image, ImageDraw
            import io
        except ImportError:
            return None

        # Character dimensions
        char_width = 5   # pixels per character width
        char_height = 8  # pixels per character height

        # Calculate scaled pixel size (each LCD pixel becomes scale x scale)
        pixel_size = scale

        # Calculate character cell size (including pixel gaps)
        cell_width = char_width * pixel_size + (char_width - 1) * pixel_gap
        cell_height = char_height * pixel_size + (char_height - 1) * pixel_gap

        # Calculate total display size
        display_width = (
            self._num_columns * cell_width +
            (self._num_columns - 1) * char_gap
        )
        display_height = (
            self._state.num_lines * cell_height +
            (self._state.num_lines - 1) * char_gap
        )

        # Total image size with bezel
        img_width = display_width + 2 * bezel
        img_height = display_height + 2 * bezel

        # Create RGB image with bezel color
        img = Image.new('RGB', (img_width, img_height), color=bezel_color)
        draw = ImageDraw.Draw(img)

        # Fill LCD area with grid color (will show through gaps)
        draw.rectangle(
            [bezel, bezel, bezel + display_width - 1, bezel + display_height - 1],
            fill=grid_color
        )

        # Get pixel buffer
        pixels = self.get_pixel_buffer()
        src_width = self._num_columns * char_width

        # Draw each character cell
        for char_row in range(self._state.num_lines):
            for char_col in range(self._num_columns):
                # Calculate cell top-left position
                cell_x = bezel + char_col * (cell_width + char_gap)
                cell_y = bezel + char_row * (cell_height + char_gap)

                # Draw each pixel in the character
                for py in range(char_height):
                    for px in range(char_width):
                        # Get pixel state from buffer
                        src_x = char_col * char_width + px
                        src_y = char_row * char_height + py
                        pixel_on = pixels[src_y * src_width + src_x]

                        # Calculate pixel rectangle position
                        pixel_x = cell_x + px * (pixel_size + pixel_gap)
                        pixel_y = cell_y + py * (pixel_size + pixel_gap)

                        # Draw pixel (ink if on, paper if off)
                        color = ink_color if pixel_on else paper_color
                        draw.rectangle(
                            [pixel_x, pixel_y,
                             pixel_x + pixel_size - 1, pixel_y + pixel_size - 1],
                            fill=color
                        )

        # Export as PNG
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    # =========================================================================
    # Contrast Control
    # =========================================================================

    def increase_contrast(self) -> None:
        """Increase contrast level (max 10)."""
        if self._state.is_on and self._state.contrast < 10:
            self._state.contrast += 1
            self._needs_refresh = True

    def decrease_contrast(self) -> None:
        """Decrease contrast level (min 0)."""
        if self._state.is_on and self._state.contrast > 0:
            self._state.contrast -= 1
            self._needs_refresh = True

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def get_snapshot_data(self) -> List[int]:
        """
        Get complete display state for snapshot.

        Format matches JAPE's getSnapshotData for compatibility.

        Returns:
            List of bytes representing complete display state
        """
        result = [
            self._state.num_lines,
            self._state.cursor_pos,
            self._state.scr_ptr,
            self._state.udg_ptr,
            1 if self._state.cursor_state else 0,
            1 if self._state.cursor_ul else 0,
            1 if self._state.cursor_fl else 0,
            1 if self._state.cursor_timer else 0,
            1 if self._state.addr_incr else 0,
            1 if self._state.is_on else 0,
            1 if self._state.ptr_to_screen else 0,
        ]
        result.extend(self._display_data)
        result.extend(self._udg_data)
        return result

    def apply_snapshot_data(self, data: List[int], offset: int = 0) -> int:
        """
        Restore display state from snapshot.

        Args:
            data: Snapshot data bytes
            offset: Starting offset in data

        Returns:
            Number of bytes consumed
        """
        # Reinitialize with correct line count
        num_lines = data[offset]
        self.__init__(num_lines)

        # Restore state
        self._state.cursor_pos = data[offset + 1]
        self._state.scr_ptr = data[offset + 2]
        self._state.udg_ptr = data[offset + 3]
        self._state.cursor_state = data[offset + 4] != 0
        self._state.cursor_ul = data[offset + 5] != 0
        self._state.cursor_fl = data[offset + 6] != 0
        self._state.cursor_timer = data[offset + 7] != 0
        self._state.addr_incr = data[offset + 8] != 0
        self._state.is_on = data[offset + 9] != 0
        self._state.ptr_to_screen = data[offset + 10] != 0

        # Restore display RAM
        pos = offset + 11
        for i in range(self.DISPLAY_RAM_SIZE):
            self._display_data[i] = data[pos + i]
        pos += self.DISPLAY_RAM_SIZE

        # Restore UDG RAM
        for i in range(self.UDG_RAM_SIZE):
            self._udg_data[i] = data[pos + i]
        pos += self.UDG_RAM_SIZE

        self._needs_refresh = True
        return pos - offset
