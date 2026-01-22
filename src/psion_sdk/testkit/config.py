"""
Psion Testing Framework - Configuration
=======================================

Test configuration management including timing defaults, paths,
and model settings. Configuration can come from:
- Default values (defined here)
- Pytest configuration
- Environment variables

Key timing values are in CPU cycles (approximately 920 KHz on real hardware):
- 50,000 cycles ≈ 54ms (key hold time)
- 150,000 cycles ≈ 163ms (inter-key delay)
- 5,000,000 cycles ≈ 5.4s (boot time)
- 10,000,000 cycles ≈ 10.9s (timeout)

Copyright (c) 2025-2026 Hugo José Pinto & Contributors
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import os


@dataclass
class TestConfig:
    """
    Configuration for Psion test execution.

    All timing values are in CPU cycles. The HD6303 runs at approximately
    920 kHz, so:
    - 1,000 cycles ≈ 1ms
    - 100,000 cycles ≈ 100ms
    - 1,000,000 cycles ≈ 1 second

    Attributes:
        default_hold_cycles: How long to hold a key (default: 50,000 ≈ 54ms)
        default_delay_cycles: Delay between keystrokes (default: 150,000 ≈ 163ms)
        default_timeout_cycles: Maximum wait time (default: 10,000,000 ≈ 10.9s)
        default_poll_interval: How often to check display (default: 10,000 ≈ 11ms)
        default_idle_threshold: Cycles in idle loop to consider "idle" (default: 1,000)
        boot_cycles: Initial boot cycles (default: 5,000,000 ≈ 5.4s)
        post_boot_cycles: Cycles after language selection (default: 2,000,000 ≈ 2.2s)
        boot_language_key: Key to press for English selection (default: "EXE")
        capture_screenshots_on_failure: Save screenshot when test fails (default: True)
        screenshot_format: Format for screenshots (image, image_lcd, text)
        max_action_log_size: Maximum actions to keep in log (default: 100)
        rom_search_paths: Where to look for ROM files
        screenshot_output_dir: Where to save failure screenshots
        compiled_programs_cache: Where to cache compiled programs
        default_model: Default emulator model (default: "XP")
        default_models_for_tests: Models for @for_models without arguments
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # TIMING DEFAULTS (all in CPU cycles)
    # ═══════════════════════════════════════════════════════════════════════════

    # Key press timing
    default_hold_cycles: int = 100_000  # ~109ms - how long to hold a key down
    default_delay_cycles: int = 150_000  # ~163ms - between consecutive keypresses

    # Wait operation timing
    default_timeout_cycles: int = 10_000_000  # ~10.9s - max wait for operations
    default_poll_interval: int = 10_000  # ~11ms - how often to check conditions
    default_idle_threshold: int = 1_000  # cycles in same PC region = idle

    # Boot sequence timing
    boot_cycles: int = 5_000_000  # ~5.4s - initial ROM boot
    post_boot_cycles: int = 2_000_000  # ~2.2s - after language selection
    boot_language_key: str = "EXE"  # Press for English (first option)

    # ═══════════════════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════

    capture_screenshots_on_failure: bool = True  # Save screenshot on assertion fail
    screenshot_format: str = "image_lcd"  # "image", "image_lcd", or "text"
    max_action_log_size: int = 100  # Keep last N actions for failure report

    # ═══════════════════════════════════════════════════════════════════════════
    # PATHS
    # ═══════════════════════════════════════════════════════════════════════════

    # ROM search paths (relative to project root, searched in order)
    rom_search_paths: List[Path] = field(
        default_factory=lambda: [
            Path("src/psion_sdk/emulator/roms"),
            Path("thirdparty/jape/roms"),
        ]
    )

    # Output paths
    screenshot_output_dir: Path = field(
        default_factory=lambda: Path("/tmp/psion_test_screenshots")
    )
    compiled_programs_cache: Path = field(
        default_factory=lambda: Path("/tmp/psion_test_programs")
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # MODEL DEFAULTS
    # ═══════════════════════════════════════════════════════════════════════════

    default_model: str = "XP"  # Default model for tests without explicit model
    default_models_for_tests: List[str] = field(
        default_factory=lambda: ["XP", "LZ64"]  # 2-line + 4-line coverage
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTORY METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def from_env(cls) -> "TestConfig":
        """
        Create TestConfig from environment variables.

        Environment variables (all optional):
            PSION_TEST_MODEL: Default model (e.g., "XP", "LZ64")
            PSION_TEST_TIMEOUT: Timeout cycles (integer)
            PSION_TEST_ROM_PATH: Additional ROM search path
            PSION_TEST_SCREENSHOT_DIR: Screenshot output directory
            PSION_TEST_SCREENSHOT_FORMAT: Screenshot format

        Returns:
            TestConfig with values from environment variables
        """
        config = cls()

        # Model override
        if model := os.environ.get("PSION_TEST_MODEL"):
            config.default_model = model

        # Timeout override
        if timeout := os.environ.get("PSION_TEST_TIMEOUT"):
            try:
                config.default_timeout_cycles = int(timeout)
            except ValueError:
                pass  # Ignore invalid values

        # Additional ROM path
        if rom_path := os.environ.get("PSION_TEST_ROM_PATH"):
            config.rom_search_paths.insert(0, Path(rom_path))

        # Screenshot directory
        if screenshot_dir := os.environ.get("PSION_TEST_SCREENSHOT_DIR"):
            config.screenshot_output_dir = Path(screenshot_dir)

        # Screenshot format
        if screenshot_format := os.environ.get("PSION_TEST_SCREENSHOT_FORMAT"):
            if screenshot_format in ("image", "image_lcd", "text"):
                config.screenshot_format = screenshot_format

        return config

    @classmethod
    def from_pytest_config(cls, pytest_config) -> "TestConfig":
        """
        Create TestConfig from pytest configuration.

        Reads from pytest.ini or pyproject.toml [tool.pytest.ini_options]:
            psion_model = "XP"
            psion_timeout = 10000000
            psion_rom_path = "path/to/roms"
            psion_screenshot_dir = "path/to/screenshots"

        Args:
            pytest_config: Pytest Config object

        Returns:
            TestConfig with values from pytest configuration
        """
        config = cls()

        # Read from pytest configuration (if available)
        if hasattr(pytest_config, "getini"):
            if model := pytest_config.getini("psion_model"):
                config.default_model = model

            if timeout := pytest_config.getini("psion_timeout"):
                try:
                    config.default_timeout_cycles = int(timeout)
                except ValueError:
                    pass

            if rom_path := pytest_config.getini("psion_rom_path"):
                config.rom_search_paths.insert(0, Path(rom_path))

            if screenshot_dir := pytest_config.getini("psion_screenshot_dir"):
                config.screenshot_output_dir = Path(screenshot_dir)

        return config

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def find_rom_path(self, project_root: Path = None) -> Optional[Path]:
        """
        Find the first available ROM file.

        Searches rom_search_paths in order, looking for any .rom file.

        Args:
            project_root: Project root directory (for relative paths)

        Returns:
            Path to first ROM file found, or None if not found
        """
        if project_root is None:
            # Try to find project root by looking for pyproject.toml
            current = Path.cwd()
            while current != current.parent:
                if (current / "pyproject.toml").exists():
                    project_root = current
                    break
                current = current.parent
            else:
                project_root = Path.cwd()

        for search_path in self.rom_search_paths:
            full_path = project_root / search_path
            if full_path.exists():
                for rom in full_path.glob("*.rom"):
                    return rom

        return None

    def ensure_screenshot_dir(self) -> Path:
        """
        Ensure screenshot output directory exists.

        Creates the directory if it doesn't exist.

        Returns:
            Path to screenshot directory
        """
        self.screenshot_output_dir.mkdir(parents=True, exist_ok=True)
        return self.screenshot_output_dir

    def ensure_cache_dir(self) -> Path:
        """
        Ensure compiled programs cache directory exists.

        Creates the directory if it doesn't exist.

        Returns:
            Path to cache directory
        """
        self.compiled_programs_cache.mkdir(parents=True, exist_ok=True)
        return self.compiled_programs_cache

    def get_display_dimensions(self, model: str) -> tuple:
        """
        Get display dimensions for a model.

        Args:
            model: Model name (CM, XP, LZ, LZ64)

        Returns:
            Tuple of (rows, cols) for the display
        """
        if model in ("LZ", "LZ64"):
            return (4, 20)
        else:
            return (2, 16)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT CONFIGURATION INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Global default configuration (can be overridden in tests)
_default_config: Optional[TestConfig] = None


def get_default_config() -> TestConfig:
    """
    Get the default test configuration.

    Creates from environment variables on first access.
    Can be overridden by calling set_default_config().

    Returns:
        Default TestConfig instance
    """
    global _default_config
    if _default_config is None:
        _default_config = TestConfig.from_env()
    return _default_config


def set_default_config(config: TestConfig) -> None:
    """
    Set the default test configuration.

    Use this in conftest.py to customize configuration for all tests.

    Args:
        config: Configuration to use as default
    """
    global _default_config
    _default_config = config
