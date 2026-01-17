# Running C Programs on the Psion Emulator

This guide walks through the complete process of compiling a C program and running it on the Psion Organiser II emulator.

## Prerequisites

```bash
source .venv/bin/activate
```

## Step 1: Write the C Program

Create a C source file using the Psion SDK functions:

```c
/* examples/hello_emulator.c */
#include <psion.h>

void main() {
    cls();
    print("Hello Emulator!");
    cursor(20);
    print("Psion SDK 2026");
    cursor(40);
    print("Running on LZ64!");
    cursor(60);
    print("Press any key...");
    getkey();
}
```

Key points:
- Include `<psion.h>` for SDK functions
- Use `void main()` (Small-C style)
- `cls()` clears the display
- `print()` outputs strings
- `cursor(pos)` sets cursor position (0-19 row 1, 20-39 row 2, etc. on LZ64)
- `getkey()` waits for keypress

## Step 2: Compile C to Assembly

```bash
python -m psion_sdk.cli.pscc -m LZ64 -I include examples/hello_emulator.c -o /tmp/hello_emulator.asm
```

Flags:
- `-m LZ64`: Target model (LZ64 = 4-line display, 64KB RAM)
- `-I include`: Include path for psion.h and runtime

## Step 3: Assemble to OB3 Object

```bash
python -m psion_sdk.cli.psasm -r -m LZ64 -I include /tmp/hello_emulator.asm -o /tmp/HELLO.ob3
```

Flags:
- `-r`: Generate self-relocating code (REQUIRED for C programs)
- `-m LZ64`: Target model (adds STOP+SIN prefix for 4-line mode)
- `-I include`: Include path for runtime.inc

**Important:** The `-r` flag is essential. Without it, absolute addresses won't be patched at load time and the program will crash.

## Step 4: Create OPK Pack

```bash
python -m psion_sdk.cli.psopk create -o /tmp/HELLO.opk /tmp/HELLO.ob3
```

This creates a Psion pack file containing the HELLO procedure.

## Step 5: Run on Emulator

### Python Script Method

```python
from pathlib import Path
from psion_sdk.emulator import Emulator, EmulatorConfig

# Create emulator
emu = Emulator(EmulatorConfig(model="LZ64"))

# Load OPK into slot B:
emu.load_opk(Path("/tmp/HELLO.opk"), slot=1)

# Boot (5M cycles + select English)
emu.reset()
emu.run(5_000_000)
emu.tap_key("EXE", hold_cycles=50000)
emu.run(2_000_000)

# Add HELLO to menu via MODE key
emu.tap_key("MODE", hold_cycles=50000)
emu.run(500_000)

for key in "HELLO":
    emu.tap_key(key, hold_cycles=50000)
    emu.run(200_000)

emu.tap_key("EXE", hold_cycles=50000)  # Confirm name
emu.run(1_000_000)
emu.tap_key("EXE", hold_cycles=50000)  # Select Opl type
emu.run(1_000_000)

# Run HELLO (now first menu item)
emu.tap_key("EXE", hold_cycles=50000)
emu.run(3_000_000)

# Take screenshot
img = emu.display.render_image_lcd(
    scale=6,
    pixel_gap=1,
    char_gap=4,
    bezel=16
)
Path("screenshot.png").write_bytes(img)
```

### Alternative: PROG > RUN Method

On a real Psion or via emulator:
1. Go to **Prog** menu
2. Select **Run** (or **Search** on LZ64)
3. Press **MODE** to switch to **B:** drive
4. Type **HELLO**
5. Press **EXE** to run

## Complete One-Liner

```bash
source .venv/bin/activate && \
python -m psion_sdk.cli.pscc -m LZ64 -I include examples/hello_emulator.c -o /tmp/hello_emulator.asm && \
python -m psion_sdk.cli.psasm -r -m LZ64 -I include /tmp/hello_emulator.asm -o /tmp/HELLO.ob3 && \
python -m psion_sdk.cli.psopk create -o /tmp/HELLO.opk /tmp/HELLO.ob3 && \
echo "Created /tmp/HELLO.opk"
```

## Toolchain Diagram

```
┌──────────────────┐
│ hello_emulator.c │  C source code
└────────┬─────────┘
         │ pscc -m LZ64
         ▼
┌──────────────────┐
│hello_emulator.asm│  HD6303 assembly
└────────┬─────────┘
         │ psasm -r -m LZ64
         ▼
┌──────────────────┐
│   HELLO.ob3      │  OB3 object file
└────────┬─────────┘
         │ psopk create
         ▼
┌──────────────────┐
│   HELLO.opk      │  Psion pack file
└────────┬─────────┘
         │ load_opk(slot=1)
         ▼
┌──────────────────┐
│    Emulator      │  LZ64 running program
│  ┌────────────┐  │
│  │Hello Emul! │  │
│  │Psion SDK   │  │
│  │Running LZ64│  │
│  │Press key...│  │
│  └────────────┘  │
└──────────────────┘
```

## LCD Rendering Options

```python
# Compact rendering
img = emu.display.render_image(scale=4)

# Realistic LCD matrix
img = emu.display.render_image_lcd(
    scale=6,      # Pixel size (6x6 each)
    pixel_gap=1,  # Gap between LCD dots
    char_gap=4,   # Gap between 5x8 characters
    bezel=16      # Border around display
)
```

## Target Models

| Model | Display | RAM | Use Case |
|-------|---------|-----|----------|
| CM    | 16x2    | 8KB | Original compatibility |
| XP    | 16x2    | 32KB | Default, maximum compatibility |
| LZ    | 20x4    | 32KB | 4-line display |
| LZ64  | 20x4    | 64KB | 4-line display, max RAM |

## Troubleshooting

**"MISSING PROC"**: The procedure name or drive is wrong. Make sure:
- OPK is loaded in the correct slot (slot=1 for B:)
- Procedure name matches (case-sensitive on some operations)

**Program crashes**: Ensure you used `-r` flag with psasm.

**Display shows garbage**: Check `cursor()` positions match your target model:
- 2-line (CM/XP): positions 0-15 (row 1), 16-31 (row 2)
- 4-line (LZ/LZ64): positions 0-19 (row 1), 20-39 (row 2), 40-59 (row 3), 60-79 (row 4)
