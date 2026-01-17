"""
Display Controller Unit Tests
=============================

Tests for HD44780-compatible LCD display emulation.

The Psion Organiser II uses:
- CM/XP: 2-line x 16-character display
- LZ/LZ64: 4-line x 20-character display

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.emulator import Display, DisplayState


# =============================================================================
# Display Initialization Tests
# =============================================================================

class TestDisplayInit:
    """Test display initialization."""

    def test_2line_display(self):
        """Create 2-line display (CM/XP)."""
        display = Display(2)
        assert display.num_lines == 2
        assert display.num_columns == 16

    def test_4line_display(self):
        """Create 4-line display (LZ/LZ64)."""
        display = Display(4)
        assert display.num_lines == 4
        assert display.num_columns == 20

    def test_default_is_off(self):
        """Display starts in off state."""
        display = Display(2)
        assert display.is_on is False

    def test_switch_on(self):
        """switch_on() turns display on."""
        display = Display(2)
        display.switch_on()
        assert display.is_on is True

    def test_switch_off(self):
        """switch_off() turns display off."""
        display = Display(2)
        display.switch_on()
        display.switch_off()
        assert display.is_on is False


# =============================================================================
# HD44780 Command Tests
# =============================================================================

class TestDisplayCommands:
    """Test HD44780 command handling."""

    @pytest.fixture
    def display(self):
        """Create and initialize 2-line display."""
        d = Display(2)
        d.switch_on()
        # Initialize display (8-bit mode, 2-line)
        d.command(0x38)
        # Display on, cursor off
        d.command(0x0C)
        # Entry mode: increment, no shift
        d.command(0x06)
        return d

    def test_clear_display(self, display):
        """Clear command ($01) clears all characters."""
        # Write some text
        for c in "Hello":
            display.set_data(ord(c))

        # Clear
        display.command(0x01)

        # Display should be blank (spaces)
        text = display.get_text()
        assert text.strip() == ""

    def test_home_command(self, display):
        """Home command ($02) moves cursor to start."""
        # Move cursor to position 5
        display.command(0x80 | 5)

        # Home
        display.command(0x02)

        # Cursor should be at position 0
        assert display._state.cursor_pos == 0

    def test_set_ddram_address(self, display):
        """Set DDRAM address command ($80+addr)."""
        display.command(0x80 | 0x10)  # Position 16
        assert display._state.cursor_pos == 0x10

    def test_line_2_address(self, display):
        """Line 2 starts at address $40."""
        # HD44780 line 2 starts at 0x40
        display.command(0x80 | 0x40)
        assert display._state.cursor_pos == 0x40


# =============================================================================
# Character Data Tests
# =============================================================================

class TestDisplayData:
    """Test character data reading and writing."""

    @pytest.fixture
    def display(self):
        """Create initialized display."""
        d = Display(2)
        d.switch_on()
        d.command(0x38)
        d.command(0x0C)
        d.command(0x06)
        d.command(0x01)  # Clear
        return d

    def test_write_character(self, display):
        """set_data writes character at cursor."""
        display.set_data(ord('A'))

        text = display.get_text()
        assert text[0] == 'A'

    def test_write_string(self, display):
        """Writing multiple characters."""
        for c in "Hello":
            display.set_data(ord(c))

        text = display.get_text()
        assert text.startswith("Hello")

    def test_cursor_auto_increment(self, display):
        """Cursor auto-increments after write."""
        display.set_data(ord('A'))
        display.set_data(ord('B'))

        text = display.get_text()
        assert text[0] == 'A'
        assert text[1] == 'B'

    def test_get_data(self, display):
        """get_data reads character at cursor."""
        display.set_data(ord('X'))
        display.command(0x80 | 0x00)  # Home

        data = display.get_data()
        assert data == ord('X')

    def test_line_2_write(self, display):
        """Writing to line 2."""
        display.command(0x80 | 0x40)  # Line 2
        display.set_data(ord('2'))

        lines = display.get_text_grid()
        assert '2' in lines[1]


# =============================================================================
# Display Output Tests
# =============================================================================

class TestDisplayOutput:
    """Test display output methods."""

    @pytest.fixture
    def display(self):
        """Create initialized display with text."""
        d = Display(2)
        d.switch_on()
        d.command(0x38)
        d.command(0x0C)
        d.command(0x06)
        d.command(0x01)

        # Write "Hello" on line 1
        for c in "Hello":
            d.set_data(ord(c))

        # Write "World" on line 2
        d.command(0x80 | 0x40)
        for c in "World":
            d.set_data(ord(c))

        return d

    def test_get_text(self, display):
        """get_text returns all content as single string."""
        text = display.get_text()
        assert "Hello" in text
        assert "World" in text

    def test_get_text_grid(self, display):
        """get_text_grid returns list of lines."""
        lines = display.get_text_grid()
        assert len(lines) == 2
        assert "Hello" in lines[0]
        assert "World" in lines[1]

    def test_get_pixel_buffer(self, display):
        """get_pixel_buffer returns pixel data."""
        pixels = display.get_pixel_buffer()
        assert isinstance(pixels, bytes)
        assert len(pixels) > 0


# =============================================================================
# 4-Line Display Tests
# =============================================================================

class TestDisplay4Line:
    """Test 4-line display specific behavior."""

    @pytest.fixture
    def display(self):
        """Create 4-line display."""
        d = Display(4)
        d.switch_on()
        d.command(0x38)
        d.command(0x0C)
        d.command(0x06)
        d.command(0x01)
        return d

    def test_4_lines(self, display):
        """4-line display has 4 lines."""
        lines = display.get_text_grid()
        assert len(lines) == 4

    def test_20_columns(self, display):
        """4-line display has 20 columns."""
        lines = display.get_text_grid()
        for line in lines:
            assert len(line) == 20

    def test_line_addresses(self, display):
        """4-line display has correct line addresses."""
        # The 4-line display uses complex memory mapping.
        # From JAPE screen2mem4:
        # Row 0: 0,1,2,3, 8,9,10,11,12,13,14,15, 24,25,26,27,28,29,30,31
        # Row 1: 64,65,66,67, 72,73,74,75,76,77,78,79, 88,89,90,91,92,93,94,95
        # Row 2: 4,5,6,7, 16,17,18,19,20,21,22,23, 32,33,34,35,36,37,38,39
        # Row 3: 68,69,70,71, 80,81,82,83,84,85,86,87, 96,97,98,99,100,101,102,103

        # Write 'A' to row 2 (line 3) - address 4
        display.command(0x80 | 0x04)
        display.set_data(ord('A'))

        lines = display.get_text_grid()
        assert lines[2][0] == 'A'

        # Write 'B' to row 3 (line 4) - address 68 (0x44)
        display.command(0x80 | 0x44)
        display.set_data(ord('B'))

        lines = display.get_text_grid()
        assert lines[3][0] == 'B'


# =============================================================================
# Special Character Tests
# =============================================================================

class TestSpecialCharacters:
    """Test special character handling."""

    @pytest.fixture
    def display(self):
        d = Display(2)
        d.switch_on()
        d.command(0x38)
        d.command(0x0C)
        d.command(0x06)
        d.command(0x01)
        return d

    def test_space_character(self, display):
        """Space character ($20) displays as space."""
        display.set_data(0x20)
        text = display.get_text()
        assert text[0] == ' '

    def test_custom_character_range(self, display):
        """Custom characters $00-$07 are valid."""
        display.set_data(0x00)  # Custom char 0
        # Should not crash


# =============================================================================
# Snapshot Tests
# =============================================================================

class TestDisplaySnapshot:
    """Test display state save/restore."""

    def test_snapshot_roundtrip(self):
        """Snapshot preserves display content."""
        display = Display(2)
        display.switch_on()
        display.command(0x38)
        display.command(0x0C)
        display.command(0x06)
        display.command(0x01)

        for c in "Test":
            display.set_data(ord(c))

        # Save state
        data = display.get_snapshot_data()

        # Modify display
        display.command(0x01)  # Clear

        # Restore
        display.apply_snapshot_data(data)

        text = display.get_text()
        assert "Test" in text


# =============================================================================
# Image Rendering Tests
# =============================================================================

class TestDisplayRendering:
    """Test image rendering functionality."""

    @pytest.fixture
    def display(self):
        d = Display(2)
        d.switch_on()
        d.command(0x38)
        d.command(0x0C)
        d.command(0x06)
        d.command(0x01)
        for c in "Hello World":
            d.set_data(ord(c))
        return d

    def test_render_image_returns_bytes(self, display):
        """render_image returns bytes (PNG data) or None if PIL unavailable."""
        img = display.render_image(scale=1)
        if img is None:
            pytest.skip("PIL not available")
        assert isinstance(img, bytes)
        # Check PNG signature
        assert img[:4] == b'\x89PNG'

    def test_render_image_scale(self, display):
        """render_image respects scale parameter."""
        img1 = display.render_image(scale=1)
        if img1 is None:
            pytest.skip("PIL not available")
        img2 = display.render_image(scale=2)
        # Scaled image should be larger
        assert len(img2) > len(img1)
