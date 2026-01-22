"""
Psion Testing Framework - Pytest Fixtures
==========================================

Pytest fixtures for Psion emulator testing. These fixtures provide
pre-configured emulator instances at various states:

    fresh_emulator   - Reset but not booted
    booted_emulator  - Booted to main menu
    psion_ctx        - Full PsionTestContext with booted emulator
    test_config      - Test configuration (session-scoped)

Usage:
    In your conftest.py, register these fixtures:

        from psion_sdk.testkit.fixtures import register_fixtures
        register_fixtures()

    Then use in tests:

        def test_something(psion_ctx):
            psion_ctx.press("P").press("EXE")
            psion_ctx.assert_display_contains("PROG")

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from __future__ import annotations
from pathlib import Path
from typing import Generator, Optional

import pytest

from psion_sdk.emulator import Emulator, EmulatorConfig

from .config import TestConfig, get_default_config, set_default_config
from .context import PsionTestContext
from .sequences import BootSequence
from .exceptions import ROMNotAvailableError


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """
    Fixture: Test configuration (session-scoped).

    Returns the global test configuration. Override in your conftest.py
    to customize settings:

        @pytest.fixture(scope="session")
        def test_config():
            return TestConfig(
                default_model="LZ64",
                default_timeout_cycles=20_000_000,
            )
    """
    return get_default_config()


@pytest.fixture(scope="function")
def fresh_emulator(request, test_config: TestConfig) -> Generator[Emulator, None, None]:
    """
    Fixture: Fresh emulator instance, reset but not booted.

    Use for low-level tests that don't need the OS running.
    The emulator is created with the default model (or parameterized model).

    Example:
        def test_memory_access(fresh_emulator):
            fresh_emulator.write_byte(0x2000, 0x42)
            assert fresh_emulator.read_byte(0x2000) == 0x42

        @pytest.mark.parametrize("fresh_emulator", ["LZ64"], indirect=True)
        def test_lz_specific(fresh_emulator):
            assert fresh_emulator.model.model_type == "LZ64"
    """
    # Get model from parameterization or use default
    model = getattr(request, "param", None) or test_config.default_model

    # Find ROM
    rom_path = test_config.find_rom_path()
    if rom_path is None:
        pytest.skip("ROM files not available")
        return

    # Create emulator
    emu_config = EmulatorConfig(model=model, rom_path=rom_path)
    emulator = Emulator(emu_config)
    emulator.reset()

    yield emulator

    # Cleanup (nothing specific needed)


@pytest.fixture(scope="function")
def booted_emulator(
    fresh_emulator: Emulator, test_config: TestConfig
) -> Generator[Emulator, None, None]:
    """
    Fixture: Emulator booted to main menu.

    Boots the OS and waits until main menu is displayed.
    Use for tests that interact with the OS.

    Example:
        def test_menu_shows_find(booted_emulator):
            assert "FIND" in booted_emulator.display_text
    """
    # Create a temporary context for booting
    ctx = PsionTestContext(fresh_emulator, test_config)

    # Execute boot sequence
    BootSequence.execute(ctx, verify=True)

    yield fresh_emulator


@pytest.fixture(scope="function")
def psion_ctx(
    booted_emulator: Emulator, test_config: TestConfig
) -> Generator[PsionTestContext, None, None]:
    """
    Fixture: Full PsionTestContext with booted emulator.

    Most integration tests should use this fixture or @psion_test.
    The context provides all testing operations with action logging
    and diagnostic capture.

    Example:
        def test_navigate_to_calc(psion_ctx):
            psion_ctx.press("C").press("EXE")
            psion_ctx.assert_display_contains("CALC")
    """
    ctx = PsionTestContext(booted_emulator, test_config)
    yield ctx


@pytest.fixture(scope="function")
def unbooted_ctx(
    fresh_emulator: Emulator, test_config: TestConfig
) -> Generator[PsionTestContext, None, None]:
    """
    Fixture: PsionTestContext with fresh (not booted) emulator.

    Use for tests that need the test context API but handle
    booting themselves or don't need OS functionality.

    Example:
        def test_boot_sequence(unbooted_ctx):
            BootSequence.execute(unbooted_ctx)
            unbooted_ctx.assert_display_contains("FIND")
    """
    ctx = PsionTestContext(fresh_emulator, test_config)
    yield ctx


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════


def register_fixtures() -> None:
    """
    Register all fixtures with pytest.

    Call this from your conftest.py to make fixtures available:

        # conftest.py
        from psion_sdk.testkit.fixtures import register_fixtures
        register_fixtures()

    Note: This function exists for explicit registration. Fixtures
    can also be imported directly if preferred.
    """
    # Fixtures are auto-discovered by pytest when imported in conftest.py
    # This function is mainly for documentation purposes
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def compiled_program(request, test_config: TestConfig) -> Path:
    """
    Fixture: Compile a program and return OPK path.

    Use via indirect parameterization to compile programs for tests:

        @pytest.mark.parametrize("compiled_program", ["examples/hello.c"], indirect=True)
        def test_with_compiled(compiled_program, fresh_emulator):
            fresh_emulator.load_opk(str(compiled_program))

    The compiled program is cached at module scope for performance.
    """
    from .decorators import _compile_program, _find_project_root

    source_path = request.param
    return _compile_program(source_path, {}, None, test_config)


# ═══════════════════════════════════════════════════════════════════════════════
# PYTEST HOOKS
# ═══════════════════════════════════════════════════════════════════════════════


def pytest_configure(config):
    """
    Configure pytest markers for Psion tests.

    Registers custom markers:
        psion_requires_rom: Test requires ROM files
        psion_slow: Test is slow (>5 seconds)
    """
    config.addinivalue_line(
        "markers", "psion_requires_rom: Test requires ROM files to run"
    )
    config.addinivalue_line("markers", "psion_slow: Test is slow (>5 seconds)")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection for Psion tests.

    Automatically skips tests marked with psion_requires_rom when
    ROM files are not available.
    """
    test_config = get_default_config()
    rom_available = test_config.find_rom_path() is not None

    if not rom_available:
        skip_marker = pytest.mark.skip(reason="ROM files not available")
        for item in items:
            if "psion_requires_rom" in item.keywords:
                item.add_marker(skip_marker)
