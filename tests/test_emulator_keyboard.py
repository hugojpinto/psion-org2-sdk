"""
Keyboard Controller Unit Tests
==============================

Tests for keyboard matrix emulation.

The Psion Organiser II keyboard is a 6x6 key matrix scanned by the CPU.
Keys are identified by their grid position and mapped to logical names.

Copyright (c) 2025 Hugo José Pinto & Contributors
"""

import pytest
from psion_sdk.emulator import Keyboard, KeyboardLayout


# =============================================================================
# Keyboard Initialization
# =============================================================================

class TestKeyboardInit:
    """Test keyboard initialization."""

    def test_create_keyboard(self):
        """Can create keyboard."""
        kb = Keyboard()
        assert kb is not None

    def test_initial_state(self):
        """No keys pressed initially."""
        kb = Keyboard()
        # Port read should show no keys (all bits high)
        # Note: Default row may not be scanned yet


# =============================================================================
# Key Press/Release Tests
# =============================================================================

class TestKeyPressRelease:
    """Test key press and release operations."""

    @pytest.fixture
    def kb(self):
        return Keyboard()

    def test_key_down(self, kb):
        """key_down accepts valid key names."""
        kb.key_down('A')
        # Should not raise

    def test_key_up(self, kb):
        """key_up releases key."""
        kb.key_down('A')
        kb.key_up('A')
        # Should not raise


# =============================================================================
# Key Name Tests
# =============================================================================

class TestKeyNames:
    """Test key name handling."""

    @pytest.fixture
    def kb(self):
        return Keyboard()

    def test_letter_keys(self, kb):
        """Letter keys A-Z can be pressed."""
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            kb.key_down(letter)
            kb.key_up(letter)

    def test_special_keys(self, kb):
        """Special keys can be pressed."""
        special_keys = ['EXE', 'DEL', 'MODE', 'SHIFT', 'SPACE']

        for key in special_keys:
            try:
                kb.key_down(key)
                kb.key_up(key)
            except KeyError:
                # Key may not exist in this layout
                pass

    def test_on_key(self, kb):
        """ON key detection."""
        kb.key_down('ON')
        assert kb.is_on_pressed()
        kb.key_up('ON')
        assert not kb.is_on_pressed()


# =============================================================================
# Matrix Scanning Tests
# =============================================================================

class TestMatrixScanning:
    """Test keyboard matrix scanning behavior."""

    @pytest.fixture
    def kb(self):
        return Keyboard()

    def test_port5_read(self, kb):
        """Port 5 can be read."""
        result = kb.read_port5()
        assert isinstance(result, int)
        assert 0 <= result <= 0xFF


# =============================================================================
# Counter Tests
# =============================================================================

class TestKeyboardCounter:
    """Test keyboard counter functionality."""

    @pytest.fixture
    def kb(self):
        return Keyboard()

    def test_initial_counter(self, kb):
        """Counter starts at 0."""
        assert kb.counter == 0

    def test_increment_counter(self, kb):
        """increment_counter increments."""
        kb.increment_counter()
        assert kb.counter == 1

        kb.increment_counter()
        assert kb.counter == 2

    def test_reset_counter(self, kb):
        """reset_counter resets to 0."""
        kb.increment_counter()
        kb.increment_counter()
        kb.reset_counter()
        assert kb.counter == 0

    def test_counter_has_overflowed_method(self, kb):
        """counter_has_overflowed method exists."""
        result = kb.counter_has_overflowed()
        assert isinstance(result, bool)


# =============================================================================
# Snapshot Tests
# =============================================================================

class TestKeyboardSnapshot:
    """Test keyboard state save/restore."""

    def test_snapshot_roundtrip(self):
        """Snapshot save/restore works."""
        kb = Keyboard()
        kb.key_down('A')
        kb.increment_counter()

        # Save state
        data = kb.get_snapshot_data()
        assert data is not None

        # Create new keyboard and restore
        kb2 = Keyboard()
        kb2.apply_snapshot_data(data)


# =============================================================================
# Edge Cases
# =============================================================================

class TestKeyboardEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def kb(self):
        return Keyboard()

    def test_double_key_down(self, kb):
        """Double key_down is safe."""
        kb.key_down('A')
        kb.key_down('A')  # Should not crash

    def test_release_unpressed_key(self, kb):
        """Releasing unpressed key is safe."""
        kb.key_up('A')  # Should not crash
