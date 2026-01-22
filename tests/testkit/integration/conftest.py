"""
Integration Tests Configuration
===============================

pytest configuration specific to integration tests in this directory.

Integration tests:
- Require ROM files to run (automatically skipped if ROM unavailable)
- Test complete user workflows
- May take longer than unit tests

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from pathlib import Path


def _get_test_rom_path() -> Path | None:
    """
    Get path to test ROMs if available.

    Returns None if no ROM files are found.
    """
    # Check emulator/roms directory first (primary location)
    emulator_rom_dir = Path(__file__).parent.parent.parent.parent / "src" / "psion_sdk" / "emulator" / "roms"
    if emulator_rom_dir.exists():
        for rom in emulator_rom_dir.glob("*.rom"):
            return rom

    # Fall back to thirdparty location
    thirdparty_rom_dir = Path(__file__).parent.parent.parent.parent / "thirdparty" / "jape" / "roms"
    if thirdparty_rom_dir.exists():
        for rom in thirdparty_rom_dir.glob("*.rom"):
            return rom

    return None


def pytest_collection_modifyitems(config, items):
    """
    Mark all integration tests as requiring ROM.

    This automatically applies the requires_rom marker to all tests
    in this directory, so they're skipped when ROM isn't available.
    """
    if _get_test_rom_path() is None:
        skip_marker = pytest.mark.skip(reason="ROM files not available - integration tests skipped")
        for item in items:
            # Only skip tests in this integration directory
            if "integration" in str(item.fspath):
                item.add_marker(skip_marker)
