"""
Psion Testing Framework - Test Configuration
=============================================

pytest configuration and fixtures for the automated testing framework.
This conftest.py is loaded for all tests under tests/testkit/.

It provides:
- Psion testing framework fixtures registration
- pytest markers for ROM-requiring tests
- Helper fixtures for test programs

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

import pytest
from pathlib import Path

# Import and register Psion testing fixtures
from psion_sdk.testkit.fixtures import (
    test_config,
    fresh_emulator,
    booted_emulator,
    psion_ctx,
    unbooted_ctx,
    compiled_program,
    pytest_configure,
    pytest_collection_modifyitems,
)


# Re-export fixtures so pytest can discover them
__all__ = [
    "test_config",
    "fresh_emulator",
    "booted_emulator",
    "psion_ctx",
    "unbooted_ctx",
    "compiled_program",
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def project_root() -> Path:
    """
    Fixture: Get project root directory.

    Returns the absolute path to the project root (where pyproject.toml is).
    """
    current = Path(__file__).parent.parent.parent
    if (current / "pyproject.toml").exists():
        return current
    # Fallback: go up until we find pyproject.toml
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def examples_dir(project_root: Path) -> Path:
    """
    Fixture: Get examples directory.
    """
    return project_root / "examples"


@pytest.fixture(scope="session")
def test_programs_dir(project_root: Path) -> Path:
    """
    Fixture: Get test programs directory.
    """
    return project_root / "tests" / "testing" / "programs"


# ═══════════════════════════════════════════════════════════════════════════════
# ROM AVAILABILITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════


def get_test_rom_path() -> Path | None:
    """
    Get path to test ROMs if available.

    Returns None if no ROM files are found.
    """
    # Check emulator/roms directory first (primary location)
    emulator_rom_dir = Path(__file__).parent.parent.parent / "src" / "psion_sdk" / "emulator" / "roms"
    if emulator_rom_dir.exists():
        for rom in emulator_rom_dir.glob("*.rom"):
            return rom

    # Fall back to thirdparty location
    thirdparty_rom_dir = Path(__file__).parent.parent.parent / "thirdparty" / "jape" / "roms"
    if thirdparty_rom_dir.exists():
        for rom in thirdparty_rom_dir.glob("*.rom"):
            return rom

    return None


# Skip marker for tests requiring ROM
requires_rom = pytest.mark.skipif(
    get_test_rom_path() is None,
    reason="No ROM files available for testing"
)
