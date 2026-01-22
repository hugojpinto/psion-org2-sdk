# Testkit - Automated Testing Framework

**Part of the Psion Organiser II SDK**

This document describes the testkit framework for writing integration tests that run programs in the Psion emulator with scripted input sequences and assertions on display output.

---

## Overview

The testkit framework enables you to:

- **Boot the emulator** and navigate menus programmatically
- **Run programs** and verify their output
- **Assert on display content**, cursor position, memory, and CPU registers
- **Capture screenshots** on test failure for debugging
- **Parameterize tests** across different Psion models (CM, XP, LZ, LZ64)

The framework integrates with pytest and provides multiple levels of abstraction, from low-level cycle control to high-level workflows.

---

## Quick Start

### Basic Test

```python
from psion_sdk.testkit import psion_test, PsionTestContext

@psion_test(requires_boot=True)
def test_main_menu_visible(ctx: PsionTestContext):
    """Verify the main menu appears after boot."""
    ctx.assert_display_contains("FIND")
    ctx.assert_display_contains("CALC")
```

### Navigate and Interact

```python
from psion_sdk.testkit import psion_test, PsionTestContext

@psion_test(requires_boot=True)
def test_calculator_addition(ctx: PsionTestContext):
    """Test basic calculator addition."""
    # Navigate to CALC menu
    ctx.navigate_menu("CALC")

    # Type calculation and press EXE
    ctx.type_text("2+3")
    ctx.press("EXE")
    ctx.wait_until_idle()

    # Verify result
    ctx.assert_display_contains("5")
```

### Test Multiple Models

```python
from psion_sdk.testkit import psion_test, for_models, PsionTestContext

@psion_test(requires_boot=True)
@for_models("XP", "LZ64")
def test_boot_on_multiple_models(ctx: PsionTestContext):
    """Test runs once on XP and once on LZ64."""
    ctx.assert_display_contains("FIND")
```

---

## Installation & Setup

The testkit framework is part of the Psion SDK. No additional installation needed.

### Requirements

- Python 3.10+
- pytest 7.0+
- ROM files in `src/psion_sdk/emulator/roms/`

### Project Structure

```
src/psion_sdk/testkit/       # The testkit framework library
├── __init__.py
├── config.py                # Test configuration
├── context.py               # PsionTestContext
├── decorators.py            # @psion_test, @for_models, etc.
├── diagnostics.py           # Failure diagnostics
├── exceptions.py            # Test exceptions
├── fixtures.py              # pytest fixtures
└── sequences.py             # Reusable test sequences

tests/testkit/               # Tests using the framework
└── integration/
    ├── test_boot.py
    ├── test_calculator.py
    ├── test_menu_navigation.py
    └── test_stdlib.py
```

### Running Tests

Testkit tests are marked with `@pytest.mark.testkit` and are **excluded by default** to keep the fast unit test workflow. Use these commands:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run unit tests only (default, fast ~14 seconds)
pytest

# Run testkit integration tests only
pytest -m testkit

# Run ALL tests (unit + testkit)
pytest -m ""

# Run specific testkit test
pytest tests/testkit/integration/test_boot.py -v

# Run testkit tests for specific model
pytest -m testkit -k "LZ64"
```

### pytest Markers

| Command | Description |
|---------|-------------|
| `pytest` | Unit tests only (default) |
| `pytest -m testkit` | Testkit tests only |
| `pytest -m "not testkit"` | Unit tests only (explicit) |
| `pytest -m ""` | All tests |

---

## Core Concepts

### The @psion_test Decorator

The `@psion_test` decorator transforms a test function to:
1. Create and configure an emulator instance
2. Optionally boot to the main menu
3. Provide a `PsionTestContext` as the first argument
4. Capture diagnostics on failure
5. Automatically mark the test with `@pytest.mark.testkit`

```python
@psion_test(
    requires_boot=True,      # Boot to main menu before test
    requires_rom=True,       # Skip if ROM not available (default)
    timeout_cycles=10_000_000,  # Max cycles before timeout
)
def test_example(ctx: PsionTestContext):
    pass
```

### PsionTestContext

The context object provides all testing operations:

| Category | Methods |
|----------|---------|
| **Display** | `display`, `display_text`, `cursor`, `cursor_visible` |
| **Actions** | `press()`, `type_text()`, `wait_for()`, `wait_until_idle()` |
| **Navigation** | `navigate_menu()`, `go_up()`, `go_down()`, `go_left()`, `go_right()` |
| **Assertions** | `assert_display_contains()`, `assert_display_line()`, `assert_memory()` |
| **Low-level** | `run_cycles()`, `step()`, `read_byte()`, `write_byte()` |

All action methods return `self` for fluent chaining:

```python
ctx.press("P").press("EXE").wait_for("New")
```

---

## Granularity Levels

The framework provides operations at multiple levels of abstraction:

### Level 1: Atomic Operations

Direct emulator control with cycle-exact precision.

```python
ctx.run_cycles(100)           # Execute exactly 100 cycles
ctx.step()                    # Execute one instruction
ctx.read_byte(0x2000)         # Read memory
ctx.write_byte(0x2000, 0x42)  # Write memory
```

### Level 2: Primitive Actions

Single UI interactions without automatic waiting.

```python
ctx.tap_key("A", hold_cycles=50000)  # Press key, don't wait
```

### Level 3: Smart Actions (Recommended)

Single UI interactions with intelligent waiting. **Use these for most tests.**

```python
ctx.press("P")                   # Press and wait until idle
ctx.press("EXE", wait="none")    # Press without waiting
ctx.press("Y", wait="text:OK")   # Press and wait for text

ctx.type_text("HELLO")           # Type string
ctx.wait_for("DONE")             # Wait for text to appear
ctx.wait_until_idle()            # Wait for CPU idle
```

### Level 4: Compound Actions

Multi-step operations with semantic meaning.

```python
ctx.navigate_menu("PROG")        # Press P + EXE
ctx.enter_text_and_confirm("42") # Type + EXE
ctx.go_down(3)                   # Press DOWN 3 times
```

### Level 5: Sequences

Reusable workflows for common scenarios.

```python
from psion_sdk.testkit import BootSequence, NavigateToMenu, ProgMenu, Editor

# Boot sequence
BootSequence.execute(ctx)

# Navigate to menu
NavigateToMenu.execute(ctx, "PROG")

# PROG menu operations
ProgMenu.create_new(ctx, "TEST", drive="A:")
ProgMenu.run_translated(ctx, "HELLO")

# Editor operations
Editor.type_line(ctx, 'PRINT "HI"')
Editor.translate(ctx)
```

---

## Assertions

All assertions capture diagnostics and screenshots on failure.

### Display Assertions

```python
# Check if text appears anywhere
ctx.assert_display_contains("FIND")
ctx.assert_display_not_contains("ERROR")

# Check specific line
ctx.assert_display_line(0, "FIND", exact=False)  # Line contains "FIND"
ctx.assert_display_line(1, "CALC PROG ERASE", exact=True)  # Exact match

# Regex matching
ctx.assert_display_matches(r"\d+")  # Contains digits
```

### Cursor Assertions

```python
ctx.assert_cursor_at(0, 5)        # Row 0, column 5
ctx.assert_cursor_visible(True)   # Cursor is visible
```

### Memory Assertions

```python
ctx.assert_memory_byte(0x2000, 0x42)       # Single byte
ctx.assert_memory_word(0x2000, 0x1234)     # 16-bit word
ctx.assert_memory(0x2000, b'\x42\x00')     # Multiple bytes
```

### Register Assertions

```python
ctx.assert_register("a", 0x42)    # A register
ctx.assert_register("d", 0x1234)  # D register (A:B)
ctx.assert_flag("z", True)        # Zero flag
```

---

## Model Parameterization

### Using @for_models

Run the same test on multiple Psion models:

```python
@psion_test(requires_boot=True)
@for_models("CM", "XP", "LZ", "LZ64")
def test_all_models(ctx: PsionTestContext):
    ctx.assert_display_contains("FIND")
```

### Model-Specific Logic

```python
@psion_test(requires_boot=True)
@for_models("XP", "LZ64")
def test_display_size(ctx: PsionTestContext):
    if ctx.model == "LZ64":
        assert len(ctx.display) == 4  # 4-line display
    else:
        assert len(ctx.display) == 2  # 2-line display
```

### Available Models

| Model | Display | RAM | Notes |
|-------|---------|-----|-------|
| CM | 16x2 | 8KB | Original model |
| XP | 16x2 | 32KB | Extended memory (default) |
| LZ | 20x4 | 32KB | 4-line display |
| LZ64 | 20x4 | 64KB | Maximum RAM |

---

## Testing Compiled Programs

### Using @with_program

Compile and load a C or assembly program before the test:

```python
from psion_sdk.testkit import psion_test, with_program

@psion_test(requires_boot=True)
@with_program("examples/hello.c", slot=0)
def test_hello_world(ctx: PsionTestContext):
    """Test that hello.c displays expected output."""
    # Navigate to PROG menu
    ctx.press("P").press("EXE")
    ctx.wait_for("HELLO")

    # Run the program
    ctx.press("EXE")
    ctx.wait_until_idle()

    # Verify output
    ctx.assert_display_contains("Hello")
```

### Build Arguments

Pass build arguments for model-specific or relocatable builds:

```python
@psion_test(requires_boot=True)
@with_program(
    "examples/test.asm",
    slot=0,
    build_args={"model": "LZ", "relocatable": True},
    procedure_name="TEST"
)
def test_assembly_program(ctx: PsionTestContext):
    ...
```

### Pack Slots

| Slot | Drive | Usage |
|------|-------|-------|
| 0 | B: | First program slot |
| 1 | C: | Second program slot |
| 2 | - | Top slot (ROM packs) |

---

## Wait Strategies

The `press()` method supports different wait strategies:

| Strategy | Syntax | Description |
|----------|--------|-------------|
| **idle** | `wait="idle"` | Wait until CPU enters idle loop (default) |
| **none** | `wait="none"` | Don't wait after keypress |
| **cycles** | `wait="cycles:N"` | Wait exactly N cycles |
| **text** | `wait="text:XXX"` | Wait for text to appear |

```python
ctx.press("P")                      # Default: wait until idle
ctx.press("EXE", wait="none")       # Don't wait
ctx.press("Y", wait="cycles:500000") # Wait 500K cycles
ctx.press("DEL", wait="text:DELETE?") # Wait for confirmation
```

---

## Failure Diagnostics

When a test fails, the framework captures comprehensive diagnostics:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                              PSION TEST FAILURE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Test: test_calculator_addition                                              ║
║  Model: XP                                                                   ║
║  Error: Display does not contain '5'                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  DISPLAY STATE                                                               ║
║  ┌────────────────┐                                                          ║
║  │2+3             │ line 0                                                   ║
║  │                │ line 1                                                   ║
║  └────────────────┘                                                          ║
║  Cursor: row 0, col 3 (visible)                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  RECENT ACTIONS (last 5)                                                     ║
║  [  1] navigate_menu("CALC") → success                                       ║
║  [  2] type_text("2+3") → success                                            ║
║  [  3] press("EXE") → success                                                ║
║  [  4] wait_until_idle() → success                                           ║
║  [  5] assert_display_contains("5") → FAILED                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  SCREENSHOT: /tmp/psion_test_screenshots/test_calculator_addition_*.png      ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Screenshots are saved to `/tmp/psion_test_screenshots/` by default.

---

## Configuration

### TestConfig

Customize timing and paths via TestConfig:

```python
from psion_sdk.testkit import TestConfig, set_default_config

config = TestConfig(
    default_model="LZ64",
    default_timeout_cycles=20_000_000,
    boot_cycles=5_000_000,
    post_boot_cycles=2_000_000,
)
set_default_config(config)
```

### Environment Variables

```bash
export PSION_TEST_MODEL=LZ64
export PSION_TEST_TIMEOUT=20000000
```

### Default Timing Values

| Setting | Default | Description |
|---------|---------|-------------|
| `default_hold_cycles` | 50,000 | Key hold duration |
| `default_delay_cycles` | 150,000 | Inter-key delay |
| `default_timeout_cycles` | 10,000,000 | Max wait time |
| `boot_cycles` | 5,000,000 | Initial boot cycles |
| `post_boot_cycles` | 2,000,000 | After language selection |

---

## Complete Example

```python
"""
Integration test for a custom Psion program.

This test:
1. Boots the emulator
2. Compiles and loads a C program
3. Navigates to and runs the program
4. Verifies the output
"""

from psion_sdk.testkit import (
    psion_test,
    for_models,
    with_program,
    PsionTestContext,
    NavigateToMenu,
)


@psion_test(requires_boot=True)
@for_models("XP", "LZ64")
@with_program("examples/hello.c", slot=0)
def test_hello_world_complete(ctx: PsionTestContext):
    """Test hello.c runs correctly on XP and LZ64."""

    # Navigate to PROG menu
    NavigateToMenu.execute(ctx, "PROG")
    ctx.assert_display_contains("New")

    # Find and select our program
    ctx.wait_for("HELLO")
    ctx.press("EXE")

    # Wait for program to run
    ctx.wait_until_idle()

    # Verify output
    ctx.assert_display_contains("Hello")

    # Press key to exit (program calls getkey())
    ctx.press("EXE")

    # Should return to PROG menu
    ctx.wait_for("PROG")
```

---

## Best Practices

### 1. Use Smart Actions

Prefer Level 3 smart actions over low-level cycle manipulation:

```python
# Good
ctx.press("P").press("EXE")

# Avoid (unless timing-critical)
ctx.tap_key("P", hold_cycles=50000)
ctx.run_cycles(200000)
ctx.tap_key("EXE", hold_cycles=50000)
```

### 2. Wait for Stability

Always wait for the UI to stabilize before assertions:

```python
ctx.press("EXE")
ctx.wait_until_idle()  # Important!
ctx.assert_display_contains("Result")
```

### 3. Use Sequences for Common Workflows

```python
# Good - clear intent, reusable
NavigateToMenu.execute(ctx, "PROG")

# Avoid - repeating boilerplate
ctx.press("P")
ctx.press("EXE")
ctx.wait_until_idle()
```

### 4. Test One Thing Per Test

```python
# Good - focused tests
def test_addition(ctx):
    ...

def test_subtraction(ctx):
    ...

# Avoid - multiple concerns
def test_all_operations(ctx):
    # test addition
    # test subtraction
    # test multiplication
    ...
```

### 5. Handle Model Differences

```python
@psion_test(requires_boot=True)
@for_models("XP", "LZ64")
def test_model_aware(ctx: PsionTestContext):
    # Model-specific assertions
    if ctx.model in ("LZ", "LZ64"):
        # 4-line display has different menu layout
        ctx.assert_display_contains("PROG")
    else:
        # 2-line display
        ctx.assert_display_line(1, "CALC", exact=False)
```

---

## Troubleshooting

### Test Skipped: ROM files not available

Ensure ROM files are in `src/psion_sdk/emulator/roms/`. The emulator automatically selects the correct ROM for each model.

### Boot Sequence Failed

- Increase `boot_cycles` if the OS needs more time to initialize
- Check that the correct ROM is available for the target model
- LZ/LZ64 models may need different timing than XP

### Display Assertion Failed

1. Check the failure report for actual display content
2. Look at the screenshot in `/tmp/psion_test_screenshots/`
3. Add `ctx.wait_until_idle()` before assertions
4. Increase timeout if operations are slow

### Test Timeout

Increase the timeout:

```python
@psion_test(requires_boot=True, timeout_cycles=50_000_000)
def test_slow_operation(ctx):
    ...
```

---

## API Reference

### Decorators

| Decorator | Description |
|-----------|-------------|
| `@psion_test()` | Main test decorator (auto-marks with `@pytest.mark.testkit`) |
| `@for_models(*models)` | Parameterize across models |
| `@with_program(path, slot)` | Compile and load program |
| `@requires_rom` | Skip if ROM unavailable |

### Sequences

| Sequence | Description |
|----------|-------------|
| `BootSequence.execute(ctx)` | Boot to main menu |
| `NavigateToMenu.execute(ctx, menu)` | Navigate to menu item |
| `ProgMenu.create_new(ctx, name)` | Create new procedure |
| `ProgMenu.run_translated(ctx, name)` | Run compiled procedure |
| `Editor.type_line(ctx, code)` | Type OPL code line |
| `Editor.translate(ctx)` | Compile current procedure |

### Fixtures (for pytest)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_config` | session | Test configuration |
| `fresh_emulator` | function | Reset but not booted |
| `booted_emulator` | function | Booted to main menu |
| `psion_ctx` | function | Full PsionTestContext |

---

## See Also

- [Small-C Programming Guide](small-c-prog.md)
- [Assembly Programming Guide](asm-prog.md)
- [CLI Tools Reference](cli-tools.md)
