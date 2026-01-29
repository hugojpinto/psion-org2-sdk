# Psion Organiser II SDK

A complete cross-development toolchain for the Psion Organiser II, featuring a Small-C compiler, HD6303 assembler, cycle-accurate emulator, and serial transfer utilities.

## Features

- **psbuild** - Unified build tool (C/asm → OPK in one command)
- **pscc** - Small-C compiler targeting HD6303
- **psasm** - HD6303 macro assembler with self-relocating code support
- **psopk** - OPK pack file builder
- **pslink** - Serial transfer via Comms Link (send, receive, flash)
- **Emulator** - Cycle-accurate HD6303 emulator with LCD display
- **MCP Server** - AI assistant integration for the emulator

## Installation

```bash
# Clone the repository
git clone https://github.com/hugojpinto/psion-org2-sdk.git
cd psion-org2-sdk

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .
```

## Quick Start

### 1. Write a C Program

Create a file called `hello.c`:

```c
#include <psion.h>

void main() {
    cls();
    print("Hello, Psion!");
    getkey();
}
```

### 2. Build with psbuild

```bash
# Build directly from C to OPK (one command)
psbuild hello.c -o HELLO.opk
```

That's it! `psbuild` automatically:
- Finds the SDK include directory
- Compiles C → assembly → object code → pack file
- Enables relocatable code (required for C programs)

For more control, you can use the individual tools:

```bash
# Manual pipeline: pscc → psasm → psopk
pscc -I include hello.c -o hello.asm
psasm -r -I include hello.asm -o HELLO.ob3
psopk create -o HELLO.opk HELLO.ob3
```

### Transfer to Device

```bash
# List available serial ports
pslink ports

# Send to Psion (run COMMS > RECEIVE on device first)
pslink send HELLO.opk

# Or flash directly to datapak (COMMS > BOOT on device)
pslink flash HELLO.opk
```

### Or Run in the Emulator

```python
from psion_sdk.emulator import Emulator, EmulatorConfig

emu = Emulator(EmulatorConfig(model="LZ64"))
emu.load_opk("HELLO.opk", slot=0)
emu.reset()
emu.run(5_000_000)  # Boot
emu.tap_key("EXE")  # Select language
emu.run(2_000_000)
print(emu.display_text)
```

## CLI Tools

### psbuild - Unified Build Tool (Recommended)

```bash
psbuild hello.c -o HELLO.opk           # Build C program to OPK
psbuild hello.asm -o HELLO.opk         # Build assembly program to OPK
psbuild -m LZ hello.c -o HELLO.opk     # Target 4-line display
psbuild -v hello.c                     # Verbose output (shows each stage)
psbuild -k hello.c                     # Keep intermediate files (.asm, .ob3)
psbuild --version                      # Show version
```

**Key flags:**
- `-m MODEL` - Target model: CM, XP, LZ, LZ64, PORTABLE
- `-v` - Verbose output showing each build stage
- `-k` - Keep intermediate files for debugging
- `-r` - Enable relocatable code for assembly (always on for C)

The SDK include directory is found automatically. For C sources, `-r` (relocatable) is always enabled.

### pscc - Small-C Compiler

```bash
pscc -I include hello.c -o hello.asm       # Compile C to assembly
pscc -m LZ -I include hello.c -o hello.asm # Target 4-line display
pscc --version                             # Show version
```

**Key flags:**
- `-I include` - **Required.** Path to SDK header files (psion.h)
- `-m MODEL` - Target model: CM, XP, LZ, LZ64, PORTABLE

**Supported C features:**
- `int` (16-bit), `char` (8-bit) types
- Pointers and arrays
- Control flow: `if/else`, `while`, `for`, `do-while`, `switch`
- Functions with parameters and local variables
- `#define` and `#include` preprocessor

### psasm - HD6303 Assembler

```bash
psasm -r -I include hello.asm -o hello.ob3    # Assemble C-generated code
psasm -I include hello.asm -o hello.ob3       # Assemble hand-written assembly
psasm -r -m LZ -I include hello.asm           # Target 4-line display
psasm -l hello.lst -I include hello.asm       # Generate listing
psasm --version                               # Show version
```

**Key flags:**
- `-I include` - **Required.** Path to SDK header files (runtime.inc, psion.inc, etc.)
- `-r` - Generate self-relocating code (required for C programs)
- `-m MODEL` - Target model: CM, XP, LZ, LZ64, PORTABLE

### psopk - OPK Pack Builder

```bash
psopk create -o app.opk file.ob3       # Create pack from OB3
psopk list app.opk                     # List pack contents
psopk info app.opk                     # Show detailed info
psopk validate app.opk                 # Validate format
```

### pslink - Serial Transfer

```bash
pslink ports                           # List serial ports
pslink send file.opk                   # Send file to Psion
pslink receive                         # Receive file from Psion
pslink flash file.opk                  # Flash to datapak via BOOT
pslink --version                       # Show version
```

## Target Models

| Model | Display | Flag |
|-------|---------|------|
| CM | 16x2 (2-line) | `-m CM` |
| XP | 16x2 (2-line) | `-m XP` (default) |
| LZ | 20x4 (4-line) | `-m LZ` |
| LZ64 | 20x4 (4-line) | `-m LZ64` |

Programs built for 2-line displays run on all models. Programs built for 4-line displays (`-m LZ`) include a prefix that gracefully exits on 2-line machines.

## Emulator

The SDK includes a cycle-accurate HD6303 emulator that boots real Psion ROMs.

```python
from psion_sdk.emulator import Emulator, EmulatorConfig

# Create emulator (CM, XP, LZ, or LZ64)
emu = Emulator(EmulatorConfig(model="LZ64"))

# Load pack into slot (0=B:, 1=C:, 2=top slot)
emu.load_opk("game.opk", slot=0)

# Boot and navigate
emu.reset()
emu.run(5_000_000)
emu.tap_key("EXE")  # Select English
emu.run(2_000_000)

# Read display
print(emu.display_lines)

# Navigate menus
emu.tap_key("RIGHT")
emu.run(200_000)

# Take screenshot
img = emu.display.render_image_lcd(scale=4)
```

### MCP Server (AI Integration)

The emulator can be controlled via MCP (Model Context Protocol) for integration with AI assistants like Claude.

```json
{
  "mcpServers": {
    "psion-emulator": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "psion_sdk.emulator.mcp.server"]
    }
  }
}
```

## Project Structure

```
psion-org2-sdk/
├── src/psion_sdk/
│   ├── cli/           # Command-line tools (pscc, psasm, psopk, pslink)
│   ├── smallc/        # Small-C compiler
│   ├── assembler/     # HD6303 assembler
│   ├── opk/           # OPK file format handling
│   ├── comms/         # Serial communication
│   └── emulator/      # HD6303 emulator + MCP server
├── include/           # C and assembly headers
│   ├── psion.h        # C runtime header
│   ├── runtime.inc    # Assembly runtime library
│   └── syscalls.inc   # System call definitions
├── examples/          # Example programs
├── docs/              # Documentation
└── tests/             # Test suite
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [CLI Tools Manual](docs/cli-tools.md) | Complete reference for psbuild, pscc, psasm, psopk, pslink, psdisasm |
| [Small-C Programming](docs/small-c-prog.md) | Small-C language guide, types, structs, external OPL calls |
| [Assembly Programming](docs/asm-prog.md) | HD6303 assembly reference, instruction set, system calls |
| [Core Library (stdlib)](docs/stdlib.md) | String functions, character classification (ctype.h) |
| [Extended Library (stdio)](docs/stdio.md) | sprintf, strrchr, strstr, strncat |
| [Database Library (db)](docs/db.md) | Database file access, record CRUD, OPL interoperability |
| [Testkit Framework](docs/testkit.md) | Automated testing framework for emulator-based integration tests |

## Example Programs

### Assembly (hello.asm)

```asm
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

        ORG     $2000

START:  JSR     RT_CLS          ; Clear screen
        LDX     #MESSAGE
        JSR     RT_PRINT        ; Print string
        JSR     RT_GETKEY       ; Wait for key
        RTS

MESSAGE:
        FCC     "Hello, World!"
        FCB     0
```

### C (hello.c)

```c
#include <psion.h>

int main() {
    cls();

    int count = 0;
    while (1) {
        at(0, 0);
        print("Count: ");
        printint(count);

        int key = getkey();
        if (key == KEY_ON)
            break;
        count++;
    }

    return 0;
}
```

## References

- [Jaap's Psion Page](https://www.jaapsch.net/psion/) - Comprehensive Psion documentation
- [HD6303 Instruction Set](https://www.jaapsch.net/psion/mcmnemal.htm) - CPU reference

## License

MIT License - Copyright (c) 2026 Hugo José Pinto

See [LICENSE](LICENSE) for details.
