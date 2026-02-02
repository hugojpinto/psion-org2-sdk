# Psion SDK CLI Tools Manual

**Psion Organiser II SDK**

This manual provides comprehensive documentation for all command-line tools in the Psion SDK. These tools form a complete development pipeline for creating, building, and deploying programs to the Psion Organiser II.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [psbuild - Unified Build Tool](#3-psbuild---unified-build-tool)
4. [pscc - Small-C Compiler](#4-pscc---small-c-compiler)
5. [psasm - HD6303 Assembler](#5-psasm---hd6303-assembler)
6. [psopk - OPK Pack Builder](#6-psopk---opk-pack-builder)
7. [pslink - Serial Transfer Tool](#7-pslink---serial-transfer-tool)
8. [psdisasm - Disassembler](#8-psdisasm---disassembler)
9. [Exit Codes](#9-exit-codes)
10. [Environment Setup](#10-environment-setup)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

The Psion SDK provides six command-line tools that work together to build and deploy programs for the Psion Organiser II:

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `psbuild` | Unified build tool | `.c` or `.asm` | `.opk` |
| `pscc` | Small-C compiler | `.c` | `.asm` |
| `psasm` | HD6303 assembler | `.asm` | `.ob3` |
| `psopk` | OPK pack builder | `.ob3` | `.opk` |
| `pslink` | Serial transfer | `.opk` | Device |
| `psdisasm` | Disassembler | `.bin`/`.ob3` | `.asm` |

### Toolchain Pipeline

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         Development Pipeline                              │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   psbuild (recommended): Single command for complete builds               │
│   ════════════════════════════════════════════════════════                │
│                                                                           │
│   ┌─────────────┐                                              ┌─────────┐│
│   │   .c file   │─────────────── psbuild ─────────────────────▶│  .opk   ││
│   │  (Small-C)  │     (auto: pscc → psasm → psopk)             │ (Pack)  ││
│   └─────────────┘                                              └─────────┘│
│                                                                           │
│   Manual pipeline: Fine-grained control                                   │
│   ══════════════════════════════════════                                  │
│                                                                           │
│   ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌─────────┐            │
│   │   .c    │────▶│  .asm    │────▶│  .ob3   │────▶│  .opk   │            │
│   │ (source)│pscc │(assembly)│psasm│(object) │psopk│ (pack)  │            │
│   └─────────┘     └──────────┘     └─────────┘     └─────────┘            │
│                                                                           │
│   Assembly-only pipeline:                                                 │
│   ═══════════════════════                                                 │
│                                                                           │
│   ┌──────────┐     ┌─────────┐     ┌─────────┐                            │
│   │  .asm    │────▶│  .ob3   │────▶│  .opk   │                            │
│   │(assembly)│psasm│(object) │psopk│ (pack)  │                            │
│   └──────────┘     └─────────┘     └─────────┘                            │
│                                                                           │
│   Transfer to device:                                                     │
│   ══════════════════                                                      │
│                                                                           │
│   ┌─────────┐               ┌──────────────┐                              │
│   │  .opk   │───── pslink ─▶│ Psion Device │                              │
│   │ (pack)  │   send/flash  │              │                              │
│   └─────────┘               └──────────────┘                              │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Quick Start

### Prerequisites

```bash
# Create and activate virtual environment (first time)
python3 -m venv .venv
source .venv/bin/activate

# Install SDK in development mode (first time)
pip install -e .
```

**Important:** Always activate the virtual environment before using any tools:

```bash
source .venv/bin/activate
```

### Build Your First Program

**Using psbuild (recommended):**

```bash
# Build C program
psbuild hello.c -o HELLO.opk

# Build assembly program
psbuild hello.asm -o HELLO.opk

# Build for LZ/LZ64 (4-line display)
psbuild -m LZ hello.c -o HELLO.opk
```

**Using manual pipeline:**

```bash
# C program: compile → assemble → package
pscc -I include hello.c -o /tmp/hello.asm
psasm -r -I include /tmp/hello.asm -o /tmp/HELLO.ob3
psopk create -o HELLO.opk /tmp/HELLO.ob3

# Assembly program: assemble → package
psasm -I include hello.asm -o /tmp/HELLO.ob3
psopk create -o HELLO.opk /tmp/HELLO.ob3
```

### Transfer to Device

```bash
# Flash directly to pack (recommended)
pslink flash HELLO.opk

# Or send via COMMS > RECEIVE
pslink send HELLO.opk
```

---

## 3. psbuild - Unified Build Tool

The `psbuild` tool combines the entire toolchain into a single command, automatically detecting source type and running the appropriate pipeline. It supports both single-file and multi-file builds.

### Synopsis

```
psbuild [OPTIONS] INPUT_FILES...
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output OPK file (default: INPUT.opk in current directory) |
| `-m, --model MODEL` | Target model: CM, XP, LA, LZ, LZ64, PORTABLE (default: XP) |
| `-I, --include PATH` | Add include search path (can be repeated) |
| `-r, --relocatable` | Generate self-relocating code (assembly only; always enabled for C) |
| `-k, --keep` | Keep intermediate files (.asm, .ob3) |
| `-g, --debug FILE` | Generate debug symbol file (.dbg) for source-level debugging |
| `-O, --optimize` | Enable peephole optimization (default: enabled) |
| `--no-optimize` | Disable peephole optimization |
| `-v, --verbose` | Show detailed progress for each build stage |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Source Type Detection

`psbuild` automatically detects the source type from the file extension:

| Extension | Source Type | Pipeline |
|-----------|-------------|----------|
| `.c` | Small-C | pscc → psasm (with -r) → psopk |
| `.asm`, `.s` | Assembly | psasm → psopk |

### Include Path Resolution

`psbuild` automatically finds the SDK's include directory. The search order is:

1. Directories specified with `-I` (in order given)
2. Source file's parent directory
3. SDK's `include/` directory (auto-detected)

This means `#include <psion.h>` and `INCLUDE "runtime.inc"` work without specifying `-I include`.

### Examples

```bash
# Basic C build
psbuild hello.c -o HELLO.opk

# C with verbose output
psbuild -v hello.c -o HELLO.opk

# C for LZ/LZ64 target
psbuild -m LZ hello.c -o HELLO.opk

# Assembly with relocation
psbuild -r hello.asm -o HELLO.opk

# Keep intermediate files for debugging
psbuild -k hello.c -o HELLO.opk
# Creates: HELLO.opk, hello.asm, HELLO.ob3

# Custom output location
psbuild hello.c -o /path/to/output/MYPROG.opk

# Multiple include paths
psbuild -I ./mylibs -I ./vendor hello.c -o HELLO.opk

# Disable optimization (for debugging)
psbuild --no-optimize hello.c -o HELLO.opk
```

### Multi-File Builds

`psbuild` supports building from multiple source files, enabling modular code organization:

```bash
# Multiple C files
psbuild main.c utils.c math.c -o MYAPP.opk

# C with assembly helpers
psbuild main.c fast_routines.asm -o MYAPP.opk

# Verbose multi-file build
psbuild -v main.c helpers.c -o MYAPP.opk
```

#### How Multi-File Linking Works

1. **File Classification**: Input files are sorted by type (.c vs .asm)
2. **Main Detection**: For C files, `psbuild` identifies which one contains `main()`
3. **Library Compilation**: Non-main C files are compiled in "library mode":
   - No entry point generated
   - No runtime includes (provided by main file)
4. **Assembly Merge**: All assembly is concatenated in order:
   - Library files first (from non-main C files)
   - User assembly files
   - Main file last (with entry point and runtime)
5. **Final Build**: Merged assembly is assembled and packaged

#### Cross-File References

Use `extern` in C files to reference functions/variables from other files:

```c
/* main.c */
extern int helper_func(int x);  /* From utils.c */
extern int counter;              /* From state.c */

void main() { /* ... */ }
```

```c
/* utils.c */
int helper_func(int x) {
    return x * 2;
}
```

**Requirements:**
- Exactly one C file must contain `main()`
- Assembly routines must follow C calling convention (args at 4,X, 6,X, etc.)
- Assembly labels must use underscore prefix (`_funcname` for `funcname()`)

#### Cross-File Type Checking

When building multi-file C projects, `psbuild` validates that `extern` declarations match their actual definitions. This catches type mismatches at compile time rather than causing mysterious runtime crashes.

**Checked Mismatches:**
- Function return type mismatch
- Function parameter count mismatch
- Function parameter type mismatch
- Variable type mismatch

**Example Error:**

```c
/* main.c */
extern int helper(int x);  /* Expects int parameter */

/* helper.c */
int helper(char *s) { ... }  /* Actual: char* parameter */
```

```
$ psbuild main.c helper.c -o MYAPP.opk
Error: extern 'helper' parameter type mismatch
  main.c:2: extern declares parameter 1 as 'int'
  helper.c:2: definition has parameter 1 as 'char *'
```

**Array/Pointer Decay:**

Unsized arrays (`extern char buffer[];`) correctly match both pointer declarations (`char *buffer`) and sized array definitions (`char buffer[16]`), following standard C semantics.

### Procedure Name Derivation

The procedure name in the OPK is derived from the output filename:

- Converted to uppercase
- Non-alphanumeric characters removed
- Truncated to 8 characters
- Must start with a letter

| Output File | Procedure Name |
|-------------|----------------|
| `HELLO.opk` | `HELLO` |
| `my_prog.opk` | `MYPROG` |
| `test123.opk` | `TEST123` |
| `very_long_name.opk` | `VERYLONG` |

### Key Behaviors

- **C sources**: Always enables `-r` (relocatable) because C programs require self-relocation
- **Assembly sources**: `-r` is optional; add if your code uses internal symbol references
- **Temp files**: Uses temporary directory for intermediate files; cleaned up on success
- **SDK includes**: Auto-detected; no need for explicit `-I include`

---

## 4. pscc - Small-C Compiler

The `pscc` tool compiles Small-C source code to HD6303 assembly language.

### Synopsis

```
pscc [OPTIONS] INPUT_FILE
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output assembly file (default: input.asm) |
| `-I, --include PATH` | Add include search path (can be repeated) |
| `-E, --preprocess-only` | Preprocess only, output to stdout |
| `--ast` | Print AST and exit (for debugging) |
| `-m, --model MODEL` | Target model: CM, XP, LA, LZ, LZ64, PORTABLE |
| `-v, --verbose` | Verbose output |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Examples

```bash
# Basic compilation
pscc hello.c -o hello.asm

# With include path
pscc -I include hello.c -o hello.asm

# For LZ target
pscc -m LZ -I include hello.c -o hello.asm

# Verbose output
pscc -v hello.c

# Preprocess only (view expanded source)
pscc -E hello.c

# Debug AST
pscc --ast hello.c
```

### Target Model Macros

The compiler defines these macros based on the target model:

| Macro | When Defined |
|-------|--------------|
| `__PSION__` | Always |
| `__PSION_CM__` | `-m CM` |
| `__PSION_XP__` | `-m XP` (default) |
| `__PSION_LZ__` | `-m LZ` |
| `__PSION_LZ64__` | `-m LZ64` |
| `__PSION_2LINE__` | CM, XP, LA targets |
| `__PSION_4LINE__` | LZ, LZ64 targets |
| `DISP_ROWS` | 2 or 4 |
| `DISP_COLS` | 16 or 20 |

### Supported C Features

- `int` (16-bit), `char` (8-bit) types
- Pointers and single-dimensional arrays
- Structs with `.` and `->` member access
- `if/else`, `while`, `for`, `do-while`, `switch`
- Functions with parameters and local variables
- `#define` and `#include` preprocessor
- `typedef` for type aliases
- External OPL procedure calls
- Constant folding and 8-bit char arithmetic optimization

---

## 5. psasm - HD6303 Assembler

The `psasm` tool assembles HD6303 source code to Psion OB3 object format.

### Synopsis

```
psasm [OPTIONS] INPUT_FILE
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output OB3 file (default: input.ob3) |
| `-l, --listing FILE` | Generate listing file |
| `-s, --symbols FILE` | Generate symbol file |
| `-g, --debug FILE` | Generate debug symbol file (.dbg) for source-level debugging |
| `-b, --binary FILE` | Generate raw binary (machine code only) |
| `-p, --proc FILE` | Generate procedure (OPL wrapper, no OB3 header) |
| `-I, --include PATH` | Add include search path (can be repeated) |
| `-D, --define SYM=VAL` | Define symbol (can be repeated) |
| `-r, --relocatable` | Generate self-relocating code |
| `-m, --model MODEL` | Target model: CM, XP, LA, LZ, LZ64, PORTABLE |
| `-O, --optimize` | Enable peephole optimization (default) |
| `--no-optimize` | Disable peephole optimization |
| `-v, --verbose` | Verbose output |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Output Formats

The `-o`, `-b`, and `-p` options are mutually exclusive:

| Option | Format | Description |
|--------|--------|-------------|
| `-o file.ob3` | OB3 | Full header + procedure (default, for psopk) |
| `-b file.bin` | Binary | Raw machine code, no OPL wrapper |
| `-p file.proc` | Procedure | OPL wrapper without OB3 header |

### Examples

```bash
# Basic assembly
psasm hello.asm -o hello.ob3

# With include path
psasm -I include hello.asm -o hello.ob3

# Generate relocatable code (required for C programs)
psasm -r -I include hello.asm -o hello.ob3

# For LZ target (adds STOP+SIN prefix)
psasm -r -m LZ -I include hello.asm -o hello.ob3

# With listing file
psasm -l hello.lst -I include hello.asm -o hello.ob3

# Define symbols
psasm -D DEBUG=1 -D VERSION=$0100 hello.asm -o hello.ob3

# Raw binary output
psasm -b code.bin hello.asm

# Disable optimization
psasm --no-optimize hello.asm -o hello.ob3

# Verbose output
psasm -v hello.asm -o hello.ob3
```

### Self-Relocation (-r Flag)

The `-r` flag generates self-relocating code:

- Creates a position-independent stub (~93 bytes)
- Tracks all absolute address references
- Creates a fixup table listing addresses to patch
- Code patches itself at runtime

**When to use `-r`:**
- All C-compiled programs (required)
- Assembly with `JSR`/`JMP` to internal labels
- Programs referencing data addresses with `LDX #label`

**When NOT to use `-r`:**
- Simple assembly using only relative branches
- Programs calling only system services (fixed ROM addresses)

### Debug Symbol Generation (-g Flag)

The `-g` flag generates a debug symbol file (`.dbg`) containing:

- **Symbol addresses**: Labels, EQU constants, and their memory locations
- **Source mappings**: Machine address to source file/line relationships
- **Relocation info**: Whether addresses are absolute or relocatable

**Debug File Format:**

```
# Psion SDK Debug Symbols
VERSION 1.0
TARGET XP
ORIGIN $2100
RELOCATABLE false

[SYMBOLS]
START $2100 CODE hello.asm:5
LOOP $2105 CODE hello.asm:8
COUNTER $0080 EQU hello.asm:3

[SOURCE_MAP]
$2100 hello.asm:5 [start]
$2101 hello.asm:6 [start]
$2105 hello.asm:8 [loop]
```

**RELOCATABLE Field:**
- `false`: Addresses are absolute (non-relocatable code)
- `true`: Addresses are offsets from ORIGIN (relocatable code)

For relocatable code, add ORIGIN to each address to get the runtime address after relocation.

**Examples:**

```bash
# Generate debug file alongside OB3
psasm -g hello.dbg hello.asm -o hello.ob3

# Debug file for relocatable code
psasm -r -g hello.dbg hello.asm -o hello.ob3

# With psbuild
psbuild -g HELLO.dbg hello.c -o HELLO.opk
```

### Optimizations

The assembler applies safe optimizations by default:

| Pattern | Optimization | Savings |
|---------|--------------|---------|
| `CMPA #0` | → `TSTA` | 1 byte |
| `CMPB #0` | → `TSTB` | 1 byte |
| `PSHA` + `PULA` | Eliminated | 2 bytes |
| `PSHB` + `PULB` | Eliminated | 2 bytes |
| `PSHX` + `PULX` | Eliminated | 4 bytes |
| Redundant loads | Second load removed | varies |
| Consecutive `TSX` | Keep only last | 1 byte |
| Dead code after JMP/RTS/BRA | Removed | varies |

---

## 6. psopk - OPK Pack Builder

The `psopk` tool creates, inspects, and extracts Psion pack image files.

### Synopsis

```
psopk COMMAND [OPTIONS] [ARGS]...
```

### Commands

| Command | Description |
|---------|-------------|
| `create` | Create new OPK from OB3 files |
| `list` | List contents of OPK file |
| `info` | Show detailed pack information |
| `extract` | Extract files from OPK |
| `validate` | Validate OPK file format |

### create Command

```
psopk create [OPTIONS] INPUT_FILES...
```

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output OPK file (required) |
| `-s, --size SIZE` | Pack size in KB: 8, 16, 32, 64, 128 (default: 32) |
| `-t, --type TYPE` | Pack type: datapak, rampak, flashpak (default: datapak) |
| `-v, --verbose` | Verbose output |

**Examples:**

```bash
# Create pack from single OB3
psopk create -o HELLO.opk hello.ob3

# Create larger pack
psopk create -o TOOLS.opk -s 64 tool1.ob3 tool2.ob3 tool3.ob3

# Create rampak image
psopk create -o DATA.opk -t rampak -s 16 program.ob3

# Verbose output
psopk create -v -o HELLO.opk hello.ob3
```

### list Command

```
psopk list [OPTIONS] OPK_FILE
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show more details |

**Example:**

```bash
psopk list mypack.opk
# Output:
# Name       Type         Size
# ----------------------------------
# HELLO      Procedure    256 bytes
# UTILS      Procedure    1024 bytes
```

### info Command

```
psopk info OPK_FILE
```

Shows detailed pack information including type, size, timestamp, checksum, and space usage.

**Example:**

```bash
psopk info mypack.opk
# Output:
# Pack Information: mypack.opk
# ========================================
# Pack Type:   Datapak (Simple)
# Size:        32 KB
# Created:     2026-01-22
# Checksum:    0x1234
#
# Contents:
#   Procedures:  2
#   Data Files:  0
#   Total:       2 records
#
# Space Usage:
#   Used:        1280 bytes (4%)
#   Free:        31488 bytes (96%)
```

### extract Command

```
psopk extract [OPTIONS] OPK_FILE
```

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory (default: current) |
| `-n, --name NAME` | Extract only this procedure |
| `-v, --verbose` | Verbose output |

**Examples:**

```bash
# Extract all procedures
psopk extract -o ./output/ mypack.opk

# Extract specific procedure
psopk extract -n HELLO mypack.opk
```

### validate Command

```
psopk validate [OPTIONS] OPK_FILE
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show validation details |

Validates magic number, length, header checksum, and record structure.

**Example:**

```bash
psopk validate mypack.opk
# Output: Validation PASSED: mypack.opk
```

---

## 7. pslink - Serial Transfer Tool

The `pslink` tool transfers files between PC and Psion Organiser II via serial connection.

### Synopsis

```
pslink [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option | Description |
|--------|-------------|
| `-p, --port DEVICE` | Serial port (auto-detect if not specified) |
| `-b, --baud RATE` | Baud rate: 300, 1200, 2400, 4800, 9600 (default: 9600) |
| `-v, --verbose` | Enable verbose output |
| `--timeout SECS` | Connection timeout (default: 30) |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Commands

| Command | Description |
|---------|-------------|
| `ports` | List available serial ports |
| `list` | List files on Psion pack |
| `send` | Send file to Psion |
| `receive` | Receive file from Psion |
| `flash` | Flash OPK directly to pack |

### ports Command

```
pslink ports [--detailed]
```

Lists available serial ports and attempts to auto-detect USB-serial adapters.

**Example:**

```bash
pslink ports
# Available serial ports:
# /dev/tty.usbserial-110    FTDI USB Serial
#
# Suggested port for Psion: /dev/tty.usbserial-110
```

### list Command

```
pslink list [DEVICE]
```

Lists files on a Psion pack. DEVICE defaults to `B:`.

| Device | Description |
|--------|-------------|
| `A:` | Internal memory |
| `B:` | Pack slot B (default) |
| `C:` | Pack slot C |

**Prerequisites:** Start COMMS > TRANSMIT on the Psion.

**Example:**

```bash
pslink list B:
# Files on B:
# ----------------------------------------
#   HELLO
#   UTILS
# ----------------------------------------
# 2 file(s)
```

### send Command

```
pslink send [OPTIONS] FILE
```

| Option | Description |
|--------|-------------|
| `-n, --name NAME` | Filename for Psion (default: derived from file) |
| `--opl` | Send as OPL file (default) |
| `--odb` | Send as data file |

**Workflow:**

1. Run `pslink send` on PC
2. On Psion: COMMS > RECEIVE > enter filename

**Example:**

```bash
pslink send program.opl
# Connecting to Psion on /dev/tty.usbserial-110...
#
# ============================================================
# Ready to serve: PROGRAM (1234 bytes)
#
# On Psion: COMMS > RECEIVE > enter "PROGRAM.OPL"
# ============================================================
#
# Waiting for Psion...
# [==================================================] 100%
# Transfer complete!
```

### receive Command

```
pslink receive [OPTIONS] [OUTPUT]
```

| Option | Description |
|--------|-------------|
| `-s, --simple` | Single-connection mode (skip existence check) |
| `-r, --raw` | Save raw data without line ending conversion |

**Workflow:**

1. Run `pslink receive` on PC
2. On Psion: COMMS > SEND > select file

**Example:**

```bash
pslink receive myfile.opl
# On Psion: COMMS > SEND > select file to send
#
# Waiting for Psion...
# Received: MYFILE (1234 bytes)
# Saved to: myfile.opl
```

### flash Command

```
pslink flash [OPTIONS] FILE
```

| Option | Description |
|--------|-------------|
| `-y, --no-prompt` | Skip pack insertion prompt |

Flashes an OPK pack image directly to a datapak/rampack using the BOOT protocol.

**Workflow:**

1. Run `pslink flash` on PC
2. On Psion: COMMS > BOOT > press EXE
3. Wait for "Making a pack" message
4. Insert empty pack in slot C when prompted
5. Transfer completes

**Example:**

```bash
pslink flash program.opk
# Connecting to Psion on /dev/tty.usbserial-110...
# OPK file: program.opk (32768 bytes, pack image: 32762 bytes)
#
# ============================================================
# On Psion: COMMS > BOOT > press EXE (name can be empty)
# ============================================================
#
# Waiting for Psion to enter BOOT mode...
# Phase 1: Uploading bootloader...
# [==================================================] 100%
#
# ============================================================
# Insert empty datapak/rampack in slot C on the Psion
# ============================================================
# Press Enter to continue...
#
# Phase 2: Sending pack data...
# [==================================================] 100%
#
# Transfer complete! Pack is ready to use.
```

---

## 8. psdisasm - Disassembler

The `psdisasm` tool disassembles HD6303 machine code or OPL QCode bytecode.

### Synopsis

```
psdisasm [OPTIONS] INPUT_FILE
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output file (default: stdout) |
| `-a, --address ADDR` | Base address (hex with 0x or $, or decimal) |
| `-c, --count N` | Maximum instructions to disassemble |
| `-q, --qcode` | Disassemble as OPL QCode bytecode |
| `--call-opl` | Format for _call_opl buffer (implies --qcode) |
| `--hex` | Include hex dump before disassembly |
| `--no-bytes` | Omit raw bytes from output |
| `--symbols` | Include Psion system symbol annotations (default) |
| `--no-symbols` | Disable symbol annotations |
| `-v, --verbose` | Verbose output |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Examples

```bash
# Disassemble machine code
psdisasm firmware.bin

# With base address
psdisasm code.bin --address 0x8000

# Or using $ prefix
psdisasm code.bin -a '$8000'

# Limit output
psdisasm code.bin --count 20

# Output to file
psdisasm code.bin -o listing.asm

# Include hex dump
psdisasm code.bin --hex

# Compact output (no raw bytes)
psdisasm code.bin --no-bytes

# Disable symbol annotations
psdisasm code.bin --no-symbols

# Disassemble QCode
psdisasm qcode.bin --qcode

# Analyze _call_opl buffer
psdisasm buffer.bin --call-opl
```

### Output Format

**Default format (HD6303):**

```asm
; Disassembly of code.bin
; Size: 256 bytes
; Base address: $8000
; Mode: HD6303

$8000: BD 12 34  JSR $1234  ; DP_EMIT
$8003: 86 41     LDAA #$41
$8005: 39        RTS
```

**Compact format (--no-bytes):**

```asm
$8000: JSR $1234  ; DP_EMIT
$8003: LDAA #$41
$8005: RTS
```

### System Symbol Annotations

When `--symbols` is enabled (default), known Psion system addresses are annotated:

| Address | Symbol | Description |
|---------|--------|-------------|
| $0010 | DP_EMIT | Display character |
| $0048 | KB_GETK | Wait for key |
| $006C | TM_WAIT | Timer wait |
| ... | ... | ... |

---

## 9. Exit Codes

All tools use consistent exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Build/transfer/operation error |
| 2 | Invalid arguments or file not found |

---

## 10. Environment Setup

### Virtual Environment

The SDK requires a Python virtual environment:

```bash
# Create (first time only)
python3 -m venv .venv

# Activate (required every session)
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install (first time only)
pip install -e .
```

### Serial Port Permissions (Linux)

On Linux, add your user to the `dialout` group:

```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

### Hardware Connection

For serial transfers:

1. Connect USB-serial adapter to PC
2. Connect adapter to Psion Comms Link
3. Connect Comms Link to Psion

---

## 11. Troubleshooting

### Build Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid OPK file" | Raw OB3 used | Use `psopk create` to wrap OB3 |
| Program crashes on exit | Missing `-r` flag | Use `-r` with psasm for C programs |
| 4-line not working on LZ | Missing `-m LZ` | Add `-m LZ` to both pscc and psasm |
| Immediate exit on CM/XP | Built for LZ | Build without `-m LZ` |

### Serial Transfer Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No serial port found" | Port not detected | Use `--port` option explicitly |
| "Connection timeout" | Psion not ready | Ensure correct COMMS mode on Psion |
| "Transfer error" | Protocol issue | Check baud rate matches Psion setting |

### Common Issues

**"Command not found":**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Or use python -m syntax
python -m psion_sdk.cli.pscc ...
```

**Include files not found:**
```bash
# Use -I to specify include path
pscc -I include hello.c -o hello.asm

# Or use psbuild (auto-finds includes)
psbuild hello.c -o HELLO.opk
```

**Relocatable code crashes:**
```bash
# Don't use < prefix for internal symbols
JSR     my_func         # Correct - will be relocated
JSR     <my_func        # WRONG - won't be relocated, will crash
```

---

## See Also

- [small-c-prog.md](small-c-prog.md) - Small-C Programming Manual
- [asm-prog.md](asm-prog.md) - Assembly Programming Manual
- [stdlib.md](stdlib.md) - Core string and character functions
- [stdio.md](stdio.md) - Extended string functions

---

*Last updated: February 2026*
