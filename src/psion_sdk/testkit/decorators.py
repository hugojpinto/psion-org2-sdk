"""
Psion Testing Framework - Decorators
====================================

Test decorators that configure emulator setup, model parameterization,
and program compilation for test functions.

Available Decorators:
    @psion_test     - Main decorator for Psion emulator tests
    @for_models     - Parameterize test to run on multiple models
    @with_program   - Compile and load a program before the test
    @requires_rom   - Mark test as requiring ROM files

Usage:
    from psion_sdk.testkit import psion_test, for_models, with_program

    @psion_test(requires_boot=True)
    @for_models("XP", "LZ64")
    @with_program("examples/hello.c", slot=0)
    def test_hello_world(ctx: PsionTestContext):
        ctx.press("P").press("EXE")
        ctx.wait_for("HELLO")
        ctx.assert_display_contains("Hello")

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from __future__ import annotations
import functools
import hashlib
import inspect
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, TypeVar, Union

import pytest

from psion_sdk.emulator import Emulator, EmulatorConfig

from .config import TestConfig, get_default_config
from .context import PsionTestContext
from .sequences import BootSequence
from .exceptions import (
    TestSetupError,
    ProgramBuildError,
    ROMNotAvailableError,
)


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def psion_test(
    models: Optional[List[str]] = None,
    requires_rom: bool = True,
    requires_boot: bool = False,
    timeout_cycles: Optional[int] = None,
    opk_files: Optional[List[str]] = None,
    config: Optional[TestConfig] = None,
) -> Callable[[F], F]:
    """
    Decorator for Psion emulator tests.

    This is the primary decorator for writing Psion integration tests.
    It handles:
    - Emulator creation and configuration
    - ROM availability checking
    - Optional boot sequence
    - OPK file loading
    - Test context creation
    - Cleanup after test

    The decorated function receives a PsionTestContext as its first argument.

    Args:
        models: List of models to test on. If None, uses default model.
                If multiple models specified, test runs once per model.
        requires_rom: If True, skip test when ROM not available (default: True)
        requires_boot: If True, boot emulator to main menu before test
        timeout_cycles: Maximum cycles before test fails (overrides config)
        opk_files: OPK files to load before test (paths relative to project)
        config: Custom TestConfig (default: from global default)

    Returns:
        Decorated test function

    Example:
        @psion_test(models=["LZ", "LZ64"], requires_boot=True)
        def test_4line_menu(ctx: PsionTestContext):
            ctx.assert_display_contains("FIND")

        @psion_test(requires_boot=True)
        @with_program("examples/hello.c")
        def test_hello_runs(ctx):
            ctx.press("P").press("EXE")
            ctx.wait_for("HELLO")
    """

    def decorator(func: F) -> F:
        # Get effective config
        test_config = config or get_default_config()

        # Get models to test - check for @for_models decorator first
        test_models = getattr(func, "_psion_models", None) or models or [test_config.default_model]

        @functools.wraps(func)
        def wrapper(*args, _psion_model=None, **kwargs):
            # Get model (may come from parametrization, or use first model as default)
            model = _psion_model or test_models[0]

            # Check ROM availability (but don't use the path - let emulator find correct ROM for model)
            rom_available = test_config.find_rom_path() is not None
            if requires_rom and not rom_available:
                pytest.skip("ROM files not available")
                return

            # Create emulator - let it find the correct ROM for the model
            try:
                emu_config = EmulatorConfig(model=model)
                emulator = Emulator(emu_config)
                emulator.reset()
            except Exception as e:
                raise TestSetupError(
                    f"Failed to create emulator: {e}",
                    phase="create_emulator",
                    model=model,
                    cause=e,
                )

            # Load OPK files if specified
            if opk_files:
                project_root = _find_project_root()
                for i, opk_path in enumerate(opk_files):
                    full_path = project_root / opk_path
                    if not full_path.exists():
                        raise TestSetupError(
                            f"OPK file not found: {opk_path}",
                            phase="load_opk",
                        )
                    try:
                        emulator.load_opk(str(full_path), slot=i)
                    except Exception as e:
                        raise TestSetupError(
                            f"Failed to load OPK {opk_path}: {e}",
                            phase="load_opk",
                            cause=e,
                        )

            # Check for _psion_program (from @with_program decorator)
            program_info = getattr(func, "_psion_program", None)
            if program_info:
                opk_path = _compile_program(
                    program_info["source_path"],
                    program_info.get("build_args", {}),
                    program_info.get("procedure_name"),
                    test_config,
                )
                slot = program_info.get("slot", 0)
                try:
                    emulator.load_opk(str(opk_path), slot=slot)
                except Exception as e:
                    raise TestSetupError(
                        f"Failed to load compiled program: {e}",
                        phase="load_program",
                        cause=e,
                    )

            # Create test context
            ctx = PsionTestContext(emulator, test_config)
            ctx._diagnostics.set_test_name(func.__name__)

            # Boot if required
            if requires_boot:
                try:
                    BootSequence.execute(ctx, verify=True)
                except Exception as e:
                    raise TestSetupError(
                        f"Boot sequence failed: {e}",
                        phase="boot",
                        model=model,
                        cause=e,
                    )

            # Run the actual test
            try:
                return func(ctx, *args, **kwargs)
            finally:
                # Cleanup (if needed)
                pass

        # Mark as requiring ROM for pytest collection
        if requires_rom:
            wrapper = pytest.mark.psion_requires_rom(wrapper)

        # Update signature: hide ctx (we provide it) and add _psion_model if needed
        # This prevents pytest from trying to inject 'ctx' as a fixture
        orig_sig = inspect.signature(func)
        new_params = []
        for name, param in orig_sig.parameters.items():
            # Skip 'ctx' parameter - we provide it, not pytest
            if name == "ctx":
                continue
            new_params.append(param)

        # Add _psion_model parameter for multi-model parametrization
        if len(test_models) > 1:
            new_params.append(
                inspect.Parameter("_psion_model", inspect.Parameter.KEYWORD_ONLY)
            )

        # Set the modified signature
        wrapper.__signature__ = orig_sig.replace(parameters=new_params)

        # Apply parametrization for multiple models
        if len(test_models) > 1:
            wrapper = pytest.mark.parametrize(
                "_psion_model", test_models, ids=lambda m: f"model={m}"
            )(wrapper)

        # Mark as testkit test for easy filtering with pytest -m
        wrapper = pytest.mark.testkit(wrapper)

        return wrapper

    return decorator


def for_models(*models: str) -> Callable[[F], F]:
    """
    Parameterize test to run on multiple models.

    Generates separate test cases for each model. The test will run
    once per model, with the model name appearing in the test ID.

    MUST be used together with @psion_test. The @psion_test decorator
    will detect the _psion_models attribute and handle parametrization.

    Args:
        *models: Model names (CM, XP, LZ, LZ64)

    Returns:
        Decorated test function

    Example:
        @psion_test(requires_boot=True)
        @for_models("CM", "XP", "LZ", "LZ64")
        def test_on_all_models(ctx: PsionTestContext):
            # Test runs 4 times, once per model
            ctx.assert_display_contains("FIND")
    """

    def decorator(func: F) -> F:
        # Store models on function for @psion_test to pick up
        # The @psion_test decorator will handle the actual parametrization
        func._psion_models = list(models)
        return func

    return decorator


def with_program(
    source_path: str,
    *,
    slot: int = 0,
    build_args: Optional[Dict[str, Any]] = None,
    procedure_name: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Build and load a program before the test.

    Compiles C (.c) or assembly (.asm) source to OPK and loads it
    into the emulator before the test runs. Compiled programs are
    cached for performance.

    The decorator stores metadata on the function that @psion_test
    uses to compile and load the program.

    Args:
        source_path: Path to source file (relative to project root)
        slot: Pack slot to load into (0=B:, 1=C:, 2=top)
        build_args: Additional arguments for psbuild (e.g., {"model": "LZ"})
        procedure_name: Override procedure name (default: from filename)

    Returns:
        Decorated test function

    Example:
        @psion_test(requires_boot=True)
        @with_program("examples/hello.c", slot=0)
        def test_hello_runs(ctx: PsionTestContext):
            # hello.c is compiled and loaded into slot B:
            ctx.press("P").press("EXE")  # PROG menu
            ctx.wait_for("HELLO")
    """

    def decorator(func: F) -> F:
        # Store program info on function
        func._psion_program = {
            "source_path": source_path,
            "slot": slot,
            "build_args": build_args or {},
            "procedure_name": procedure_name,
        }
        return func

    return decorator


def requires_rom(func: F) -> F:
    """
    Mark test as requiring ROM files.

    Equivalent to @psion_test(requires_rom=True) but can be used
    with other test setups (e.g., fixture-based tests).

    The test will be skipped if ROM files are not available.

    Example:
        @requires_rom
        def test_needs_os(booted_emulator):
            assert "FIND" in booted_emulator.display_text
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        config = get_default_config()
        if config.find_rom_path() is None:
            pytest.skip("ROM files not available")
            return
        return func(*args, **kwargs)

    # Also add pytest marker for filtering
    wrapper = pytest.mark.psion_requires_rom(wrapper)
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _find_project_root() -> Path:
    """
    Find the project root directory.

    Looks for pyproject.toml or setup.py going up from current directory.

    Returns:
        Path to project root
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
            return current
        current = current.parent
    return Path.cwd()


def _compile_program(
    source_path: str,
    build_args: Dict[str, Any],
    procedure_name: Optional[str],
    config: TestConfig,
) -> Path:
    """
    Compile a program to OPK format.

    Uses psbuild CLI to compile C or assembly source. Results are
    cached based on source file hash and build arguments.

    Args:
        source_path: Path to source file (relative to project root)
        build_args: Additional arguments for psbuild
        procedure_name: Override procedure name
        config: Test configuration

    Returns:
        Path to compiled OPK file

    Raises:
        ProgramBuildError: If compilation fails
    """
    project_root = _find_project_root()
    full_source_path = project_root / source_path

    if not full_source_path.exists():
        raise ProgramBuildError(
            f"Source file not found: {source_path}",
            source_path=source_path,
        )

    # Determine output name (this becomes the Psion procedure name)
    # Psion procedure names: max 8 chars, alphanumeric, must start with letter
    if procedure_name:
        output_name = procedure_name.upper()[:8]
    else:
        # Sanitize source filename stem for Psion compatibility
        stem = full_source_path.stem.upper()
        # Remove non-alphanumeric chars and truncate
        output_name = "".join(c for c in stem if c.isalnum())[:8]
        if not output_name or not output_name[0].isalpha():
            output_name = "PROGRAM"

    # Create cache key from source hash + build args + procedure_name
    source_content = full_source_path.read_bytes()
    cache_key_data = source_content + str(build_args).encode() + output_name.encode()
    cache_key = hashlib.md5(cache_key_data).hexdigest()[:12]

    # Check cache - use subdirectory for hash to keep OPK filename clean
    # This preserves the procedure name (derived from OPK filename by psbuild)
    cache_dir = config.ensure_cache_dir()
    cache_subdir = cache_dir / cache_key
    cached_opk = cache_subdir / f"{output_name}.opk"

    if cached_opk.exists():
        return cached_opk

    # Create cache subdirectory
    cache_subdir.mkdir(parents=True, exist_ok=True)

    # Build with psbuild
    cmd = ["psbuild", str(full_source_path), "-o", str(cached_opk)]

    # Add model if specified
    if "model" in build_args:
        cmd.extend(["-m", build_args["model"]])

    # Add relocatable flag if specified
    if build_args.get("relocatable"):
        cmd.append("-r")

    # Add verbose for debugging
    # cmd.append("-v")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=60,
        )

        if result.returncode != 0:
            raise ProgramBuildError(
                f"Build failed for {source_path}",
                source_path=source_path,
                build_command=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )

        if not cached_opk.exists():
            raise ProgramBuildError(
                f"Build succeeded but OPK not created: {cached_opk}",
                source_path=source_path,
                build_command=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
            )

        return cached_opk

    except subprocess.TimeoutExpired:
        raise ProgramBuildError(
            f"Build timed out for {source_path}",
            source_path=source_path,
            build_command=" ".join(cmd),
        )
    except FileNotFoundError:
        raise ProgramBuildError(
            "psbuild not found - is the SDK installed?",
            source_path=source_path,
            build_command=" ".join(cmd),
        )
