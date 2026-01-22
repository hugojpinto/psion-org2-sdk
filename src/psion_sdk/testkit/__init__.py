"""
Psion Testing Framework
=======================

An automated testing framework for the Psion Organiser II SDK.
Enables declarative tests that run programs in the emulator with
scripted input sequences and assert on display output, memory state,
and CPU registers.

Quick Start
-----------

Basic test with the @psion_test decorator::

    from psion_sdk.testkit import psion_test, PsionTestContext

    @psion_test(requires_boot=True)
    def test_menu_navigation(ctx: PsionTestContext):
        ctx.press("P").press("EXE")
        ctx.assert_display_contains("PROG")

With model parameterization::

    from psion_sdk.testkit import psion_test, for_models

    @psion_test(requires_boot=True)
    @for_models("XP", "LZ64")
    def test_on_multiple_models(ctx):
        ctx.assert_display_contains("FIND")

With compiled programs::

    from psion_sdk.testkit import psion_test, with_program

    @psion_test(requires_boot=True)
    @with_program("examples/hello.c", slot=0)
    def test_hello_world(ctx):
        ctx.press("P").press("EXE")
        ctx.wait_for("HELLO")
        ctx.press("EXE")
        ctx.assert_display_contains("Hello")

Using sequences for complex workflows::

    from psion_sdk.testkit import (
        psion_test, NavigateToMenu, ProgMenu, Editor
    )

    @psion_test(requires_boot=True)
    def test_create_opl_program(ctx):
        NavigateToMenu.execute(ctx, "PROG")
        ProgMenu.create_new(ctx, "TEST", drive="A:")
        Editor.type_line(ctx, 'PRINT "HI"')
        Editor.translate(ctx)
        ctx.wait_for("TEST")

Granularity Levels
------------------

The framework provides operations at multiple abstraction levels:

Level 1 - Atomic Operations (direct emulator control)::

    ctx.run_cycles(100)          # Execute exact cycles
    ctx.step()                   # Single instruction
    ctx.read_byte(0x2000)        # Memory access

Level 2 - Primitive Actions (no auto-wait)::

    ctx.tap_key("A")             # Press key without waiting

Level 3 - Smart Actions (PRIMARY API, with intelligent waiting)::

    ctx.press("P")               # Press and wait until idle
    ctx.type_text("HELLO")       # Type string
    ctx.wait_for("DONE")         # Wait for text

Level 4 - Compound Actions (multi-step operations)::

    ctx.navigate_menu("PROG")    # Press first letter + EXE
    ctx.enter_text_and_confirm() # Type + EXE

Level 5 - Sequences (reusable workflows)::

    BootSequence.execute(ctx)
    NavigateToMenu.execute(ctx, "PROG")
    ProgMenu.create_new(ctx, "TEST")

Fixtures
--------

For fixture-based tests, register fixtures in your conftest.py::

    # conftest.py
    from psion_sdk.testkit.fixtures import (
        test_config,
        fresh_emulator,
        booted_emulator,
        psion_ctx,
    )

Then use in tests::

    def test_with_fixture(psion_ctx):
        psion_ctx.press("C").press("EXE")
        psion_ctx.assert_display_contains("CALC")

Configuration
-------------

Customize timing and paths via TestConfig::

    from psion_sdk.testkit import TestConfig, set_default_config

    config = TestConfig(
        default_model="LZ64",
        default_timeout_cycles=20_000_000,
    )
    set_default_config(config)

Or via environment variables::

    PSION_TEST_MODEL=LZ64
    PSION_TEST_TIMEOUT=20000000
    PSION_TEST_ROM_PATH=/path/to/roms

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# Core test context
from .context import PsionTestContext

# Configuration
from .config import (
    TestConfig,
    get_default_config,
    set_default_config,
)

# Decorators
from .decorators import (
    psion_test,
    for_models,
    with_program,
    requires_rom,
)

# Sequences (Level 5 operations)
from .sequences import (
    BootSequence,
    NavigateToMenu,
    ProgMenu,
    Editor,
)

# Exceptions
from .exceptions import (
    PsionTestError,
    TestTimeoutError,
    TestAssertionError,
    TestSetupError,
    ProgramBuildError,
    ROMNotAvailableError,
)

# Diagnostics
from .diagnostics import (
    TestDiagnostics,
    ActionLogEntry,
)

# Fixtures (import for registration in conftest.py)
from .fixtures import (
    test_config,
    fresh_emulator,
    booted_emulator,
    psion_ctx,
    unbooted_ctx,
    compiled_program,
    register_fixtures,
    pytest_configure,
    pytest_collection_modifyitems,
)


__all__ = [
    # Core
    "PsionTestContext",
    # Configuration
    "TestConfig",
    "get_default_config",
    "set_default_config",
    # Decorators
    "psion_test",
    "for_models",
    "with_program",
    "requires_rom",
    # Sequences
    "BootSequence",
    "NavigateToMenu",
    "ProgMenu",
    "Editor",
    # Exceptions
    "PsionTestError",
    "TestTimeoutError",
    "TestAssertionError",
    "TestSetupError",
    "ProgramBuildError",
    "ROMNotAvailableError",
    # Diagnostics
    "TestDiagnostics",
    "ActionLogEntry",
    # Fixtures
    "test_config",
    "fresh_emulator",
    "booted_emulator",
    "psion_ctx",
    "unbooted_ctx",
    "compiled_program",
    "register_fixtures",
    "pytest_configure",
    "pytest_collection_modifyitems",
]

__version__ = "1.0.0"
