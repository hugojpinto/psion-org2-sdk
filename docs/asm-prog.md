# Assembly Programming Manual

**Psion Organiser II SDK - HD6303 Assembly Language Reference**

This manual provides a comprehensive guide to programming the Psion Organiser II in HD6303 assembly language using the Psion SDK.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [HD6303 CPU Architecture](#2-hd6303-cpu-architecture)
3. [Program Structure](#3-program-structure)
4. [Assembly Language Syntax](#4-assembly-language-syntax)
5. [Addressing Modes](#5-addressing-modes)
6. [Instruction Set Reference](#6-instruction-set-reference)
7. [Assembler Directives](#7-assembler-directives)
8. [Runtime Library Macros](#8-runtime-library-macros)
9. [System Calls](#9-system-calls)
10. [Memory Layout](#10-memory-layout)
11. [Self-Relocation](#11-self-relocation)
12. [Peephole Optimizer](#12-peephole-optimizer)
13. [Build Process](#13-build-process)
14. [Practical Examples](#14-practical-examples)
15. [Debugging Tips](#15-debugging-tips)
16. [Common Pitfalls](#16-common-pitfalls)

---

## 1. Getting Started

### Your First Assembly Program

Here's a minimal "Hello World" program:

```asm
; hello.asm - Hello World for Psion Organiser II
        INCLUDE "psion.inc"     ; SDK definitions and macros

        ORG     $2100           ; Standard code load address

START:
        CLRSCR                  ; Clear the display
        PRINT   MESSAGE         ; Print our string
        GETKEY                  ; Wait for keypress
        RTS                     ; Return to OS

MESSAGE:
        FCC     "Hello, Psion!"
        FCB     0               ; Null terminator
```

### Building and Running

```bash
# Activate virtual environment
source .venv/bin/activate

# Method 1: Single-command build with psbuild (recommended)
psbuild hello.asm -o HELLO.opk

# Method 2: Manual pipeline
python -m psion_sdk.cli.psasm -I include hello.asm -o /tmp/hello.ob3
python -m psion_sdk.cli.psopk create -o HELLO.opk /tmp/hello.ob3

# Transfer to device
python -m psion_sdk.cli.pslink flash HELLO.opk
```

### Required Include Files

| File | Purpose |
|------|---------|
| `psion.inc` | Main include - macros, constants, includes others |
| `syscalls.inc` | OS system call numbers (129 services) |
| `sysvars.inc` | System variable addresses |
| `runtime.inc` | Runtime library functions and macros (optional) |

Most programs only need `INCLUDE "psion.inc"` which automatically includes the others.

---

## 2. HD6303 CPU Architecture

The Psion Organiser II uses the Hitachi HD6303, an enhanced member of the Motorola 6800 family. It's an 8-bit CPU with 16-bit addressing.

### Registers

| Register | Size | Description |
|----------|------|-------------|
| **A** | 8-bit | Accumulator A - primary arithmetic register |
| **B** | 8-bit | Accumulator B - secondary arithmetic register |
| **D** | 16-bit | Double accumulator (A:B combined, A is high byte) |
| **X** | 16-bit | Index register - pointers and indexed addressing |
| **SP** | 16-bit | Stack pointer - grows downward |
| **PC** | 16-bit | Program counter |
| **CCR** | 8-bit | Condition Code Register (flags) |

### Condition Code Register (CCR)

```
Bit:  7   6   5   4   3   2   1   0
      1   1   H   I   N   Z   V   C
```

| Flag | Name | Set When |
|------|------|----------|
| **C** | Carry | Arithmetic carry/borrow occurred |
| **V** | Overflow | Signed overflow occurred |
| **Z** | Zero | Result is zero |
| **N** | Negative | Result bit 7 is set (negative) |
| **I** | Interrupt | Interrupts disabled (set by SEI) |
| **H** | Half-carry | Carry from bit 3 to bit 4 (for BCD) |

### Register Operations

```asm
; Transfer between registers
        TAB             ; A -> B
        TBA             ; B -> A
        XGDX            ; Exchange D and X (HD6303 extension)

; Combine A and B into D
        LDAA    #$12    ; A = $12
        LDAB    #$34    ; B = $34
                        ; Now D = $1234 (A is high byte)

; Stack pointer manipulation
        TSX             ; SP -> X (X = SP, not SP+1!)
        TXS             ; X -> SP
        INS             ; SP = SP + 1
        DES             ; SP = SP - 1
```

**Important**: `TSX` gives `X = SP` directly, not `X = SP + 1` as some 6800 documentation suggests.

---

## 3. Program Structure

### Basic Program Template

```asm
; =============================================================================
; PROGRAM.ASM - Description of your program
; =============================================================================
; Author: Your Name
; Date: YYYY-MM-DD
; =============================================================================

        INCLUDE "psion.inc"     ; Include SDK definitions

; =============================================================================
; Constants
; =============================================================================
MY_CONST        EQU     100     ; Define constants before code

; =============================================================================
; Program Origin
; =============================================================================
        ORG     $2100           ; Standard load address

; =============================================================================
; Main Entry Point
; =============================================================================
START:
        ; Your code here

        ; Always return to OS when done
        RTS

; =============================================================================
; Subroutines
; =============================================================================
MY_SUBROUTINE:
        ; Subroutine code
        RTS

; =============================================================================
; Data Section
; =============================================================================
MESSAGE:
        FCC     "Hello!"
        FCB     0               ; Null terminator

BUFFER:
        RMB     32              ; Reserve 32 bytes

; =============================================================================
; End of Program
; =============================================================================
```

### Calling Conventions

When writing subroutines, follow these conventions for compatibility with the runtime library:

```asm
; Stack frame after PSHX + TSX:
;   X+0, X+1:  Saved X (caller's frame pointer)
;   X+2, X+3:  Return address
;   X+4, X+5:  First argument (16-bit) or X+5 for 8-bit
;   X+6, X+7:  Second argument
;   ...

; Example: Subroutine with two 16-bit arguments
; int add(int a, int b)
_add:
        PSHX            ; Save caller's frame pointer
        TSX
        LDD     4,X     ; Load first argument (a)
        ADDD    6,X     ; Add second argument (b)
        PULX            ; Restore frame pointer
        RTS             ; Return with result in D
```

**Key conventions:**
- Arguments are pushed right-to-left (first argument at highest address)
- Return value goes in D register
- Caller cleans up the stack after the call
- Preserve X register across calls (using PSHX/PULX)

---

## 4. Assembly Language Syntax

### General Format

```
[label:] [instruction/directive] [operands] [; comment]
```

### Labels

Labels identify memory locations:

```asm
start:      LDAA    #$41        ; Global label
loop:       DECA                ; Another global label
.retry:     BNE     .retry      ; Local label (scoped to enclosing global)
@local:     NOP                 ; Alternative local label syntax
_func:      RTS                 ; Underscore prefix (common for functions)
```

**Label rules:**
- Start with a letter, underscore, or `.`/`@` (for local labels)
- Contain letters, digits, and underscores
- Maximum 31 characters
- Case-sensitive (by default)
- Colon after definition is optional but recommended

### Numbers

| Format | Examples | Description |
|--------|----------|-------------|
| Decimal | `123`, `255` | Default base |
| Hexadecimal | `$7F`, `0x7F`, `$FFFF` | Prefix `$` or `0x` |
| Binary | `%10101010`, `0b11110000` | Prefix `%` or `0b` |
| Octal | `@177`, `0o377` | Prefix `@` or `0o` |
| Character | `'A'`, `'*'` | ASCII value |

### Strings

```asm
; FCC - Form Constant Characters (no terminator)
message:    FCC     "Hello"         ; 5 bytes: H,e,l,l,o

; FCB - Add explicit null terminator
cstring:    FCC     "Hello"
            FCB     0               ; C-style string

; Escape sequences
newline:    FCC     "Line1\nLine2"  ; \n = newline ($0A)
tab:        FCC     "Col1\tCol2"    ; \t = tab ($09)
quote:      FCC     "Say \"Hi\""    ; \" = double quote
```

### Expressions

The assembler evaluates expressions at assembly time:

```asm
; Arithmetic
        LDAA    #10 + 5         ; 15
        LDAB    #$20 - $10      ; $10
        LDX     #TABLE + OFFSET * 2

; Bitwise operations
        LDAA    #$FF & $0F      ; $0F (AND)
        LDAB    #$0F | $F0      ; $FF (OR)
        LDD     #$FF ^ $0F      ; $F0 (XOR)
        LDAA    #~$0F           ; $F0 (NOT)

; Shifts
        LDAA    #1 << 4         ; $10 (shift left)
        LDAB    #$80 >> 4       ; $08 (shift right)

; HIGH/LOW byte extraction
        LDAA    #HIGH(ADDR)     ; High byte of address
        LDAB    #LOW(ADDR)      ; Low byte of address

; Current PC reference
        BRA     *-2             ; Branch to 2 bytes before here
        FDB     $               ; Store current address
```

### Comments

```asm
; Semicolon starts a comment
        LDAA    #0      ; Inline comment
* Asterisk at line start is also a comment (legacy)
```

---

## 5. Addressing Modes

The HD6303 supports these addressing modes:

### Inherent (No Operand)

Instructions that operate on registers implicitly:

```asm
        NOP             ; No operation
        RTS             ; Return from subroutine
        INCA            ; Increment A
        CLRB            ; Clear B
        ASLD            ; Arithmetic shift D left
        MUL             ; A * B -> D
```

### Immediate (#value)

Load a constant value directly:

```asm
        LDAA    #$41            ; Load 8-bit value into A
        LDAB    #100            ; Decimal value
        LDD     #$1234          ; Load 16-bit value into D
        LDX     #BUFFER         ; Load address into X
        CMPA    #'A'            ; Compare with character
```

### Direct (Zero Page)

Access memory in the range $00-$FF with a single-byte address:

```asm
        LDAA    $40             ; Load from address $0040
        STAB    <ZEROPAGE_VAR   ; < forces direct mode
        INC     $80             ; Increment byte at $0080
```

**Note:** Direct mode is 1 byte smaller and faster than extended mode.

### Extended (Full Address)

Access any memory location with a 16-bit address:

```asm
        LDAA    $1234           ; Load from $1234
        STAB    BUFFER          ; Store to BUFFER address
        JMP     >LABEL          ; > forces extended mode
        JSR     SUBROUTINE      ; Call subroutine
```

### Indexed (Offset,X)

Access memory relative to the X register:

```asm
        LDAA    0,X             ; Load byte at address X
        LDAB    5,X             ; Load byte at address X+5
        STD     10,X            ; Store D at address X+10
        INC     0,X             ; Increment byte at X
        CLR     255,X           ; Maximum offset is 255
```

### Relative (Branch Instructions)

PC-relative addressing for branches (-128 to +127 bytes):

```asm
        BEQ     target          ; Branch if equal
        BNE     loop            ; Branch if not equal
        BRA     always          ; Branch always
        BSR     subroutine      ; Branch to subroutine
```

**Automatic Branch Relaxation:** If a branch target is out of range, the assembler automatically converts it to a long branch:

| Original | Relaxed Form | Size Change |
|----------|--------------|-------------|
| `BEQ target` | `BNE skip; JMP target; skip:` | 2 → 5 bytes |
| `BRA target` | `JMP target` | 2 → 3 bytes |
| `BSR target` | `JSR target` | 2 → 3 bytes |

### Forcing Addressing Modes

Use `<` and `>` prefixes to force specific modes:

```asm
        LDAA    <$40            ; Force direct mode (even if label is >$FF)
        JSR     >FUNC           ; Force extended mode (even if address <=$FF)
```

---

## 6. Instruction Set Reference

### Load and Store

| Instruction | Description | Flags Affected |
|-------------|-------------|----------------|
| `LDAA src` | Load A | N, Z, V=0 |
| `LDAB src` | Load B | N, Z, V=0 |
| `LDD src` | Load D (16-bit) | N, Z, V=0 |
| `LDX src` | Load X (16-bit) | N, Z, V=0 |
| `LDS src` | Load SP | N, Z, V=0 |
| `STAA dst` | Store A | N, Z, V=0 |
| `STAB dst` | Store B | N, Z, V=0 |
| `STD dst` | Store D | N, Z, V=0 |
| `STX dst` | Store X | N, Z, V=0 |
| `STS dst` | Store SP | N, Z, V=0 |

### Arithmetic

| Instruction | Description | Flags |
|-------------|-------------|-------|
| `ADDA src` | A = A + src | H, N, Z, V, C |
| `ADDB src` | B = B + src | H, N, Z, V, C |
| `ADDD src` | D = D + src | N, Z, V, C |
| `ADCA src` | A = A + src + C | H, N, Z, V, C |
| `ADCB src` | B = B + src + C | H, N, Z, V, C |
| `SUBA src` | A = A - src | N, Z, V, C |
| `SUBB src` | B = B - src | N, Z, V, C |
| `SUBD src` | D = D - src | N, Z, V, C |
| `SBCA src` | A = A - src - C | N, Z, V, C |
| `SBCB src` | B = B - src - C | N, Z, V, C |
| `INCA` | A = A + 1 | N, Z, V |
| `INCB` | B = B + 1 | N, Z, V |
| `INC dst` | mem = mem + 1 | N, Z, V |
| `INX` | X = X + 1 | Z only |
| `DECA` | A = A - 1 | N, Z, V |
| `DECB` | B = B - 1 | N, Z, V |
| `DEC dst` | mem = mem - 1 | N, Z, V |
| `DEX` | X = X - 1 | Z only |
| `NEGA` | A = -A | N, Z, V, C |
| `NEGB` | B = -B | N, Z, V, C |
| `NEG dst` | mem = -mem | N, Z, V, C |
| `ABA` | A = A + B | H, N, Z, V, C |
| `SBA` | A = A - B | N, Z, V, C |
| `MUL` | D = A * B (unsigned) | C |
| `DAA` | Decimal adjust A | N, Z, V, C |
| `ABX` | X = X + B (unsigned) | None |

### Compare and Test

| Instruction | Description | Flags |
|-------------|-------------|-------|
| `CMPA src` | Compare A with src | N, Z, V, C |
| `CMPB src` | Compare B with src | N, Z, V, C |
| `CPX src` | Compare X with src | N, Z, V, C |
| `CBA` | Compare B with A | N, Z, V, C |
| `TSTA` | Test A (compare with 0) | N, Z, V=0, C=0 |
| `TSTB` | Test B (compare with 0) | N, Z, V=0, C=0 |
| `TST dst` | Test memory | N, Z, V=0, C=0 |

### Logic

| Instruction | Description | Flags |
|-------------|-------------|-------|
| `ANDA src` | A = A AND src | N, Z, V=0 |
| `ANDB src` | B = B AND src | N, Z, V=0 |
| `ORAA src` | A = A OR src | N, Z, V=0 |
| `ORAB src` | B = B OR src | N, Z, V=0 |
| `EORA src` | A = A XOR src | N, Z, V=0 |
| `EORB src` | B = B XOR src | N, Z, V=0 |
| `BITA src` | Test A AND src | N, Z, V=0 |
| `BITB src` | Test B AND src | N, Z, V=0 |
| `COMA` | A = NOT A | N, Z, V=0, C=1 |
| `COMB` | B = NOT B | N, Z, V=0, C=1 |
| `COM dst` | mem = NOT mem | N, Z, V=0, C=1 |
| `CLRA` | A = 0 | N=0, Z=1, V=0, C=0 |
| `CLRB` | B = 0 | N=0, Z=1, V=0, C=0 |
| `CLR dst` | mem = 0 | N=0, Z=1, V=0, C=0 |

### HD6303-Specific Bit Operations

These instructions are unique to the HD6303:

```asm
; AIM - AND Immediate with Memory
        AIM     #$0F, $80       ; mem[$80] = mem[$80] AND $0F
        AIM     #$FE, 5,X       ; mem[X+5] = mem[X+5] AND $FE

; OIM - OR Immediate with Memory
        OIM     #$80, $40       ; mem[$40] = mem[$40] OR $80
        OIM     #$01, 0,X       ; mem[X] = mem[X] OR $01

; EIM - XOR Immediate with Memory
        EIM     #$FF, $50       ; mem[$50] = mem[$50] XOR $FF (toggle all bits)

; TIM - Test Immediate with Memory (doesn't modify memory)
        TIM     #$80, $60       ; Test if bit 7 is set at $60
        BNE     bit_set         ; Branch if (mem[$60] AND $80) != 0
```

### Shift and Rotate

| Instruction | Description | Flags |
|-------------|-------------|-------|
| `ASLA/ASLB` | Arithmetic shift left (×2) | N, Z, V, C |
| `ASL dst` | Shift memory left | N, Z, V, C |
| `ASLD` | Shift D left (16-bit) | N, Z, V, C |
| `ASRA/ASRB` | Arithmetic shift right (÷2 signed) | N, Z, V, C |
| `ASR dst` | Shift memory right (signed) | N, Z, V, C |
| `LSRA/LSRB` | Logical shift right (÷2 unsigned) | N=0, Z, V, C |
| `LSR dst` | Shift memory right (unsigned) | N=0, Z, V, C |
| `LSRD` | Shift D right (16-bit unsigned) | N=0, Z, V, C |
| `ROLA/ROLB` | Rotate left through carry | N, Z, V, C |
| `ROL dst` | Rotate memory left | N, Z, V, C |
| `RORA/RORB` | Rotate right through carry | N, Z, V, C |
| `ROR dst` | Rotate memory right | N, Z, V, C |

```
ASLA/ASL:  C <- [b7...b0] <- 0
ASRA/ASR:  [b7] -> [b7...b0] -> C  (sign preserved)
LSRA/LSR:     0 -> [b7...b0] -> C  (zero fill)
ROLA/ROL:  C <- [b7...b0] <- C     (9-bit rotate)
RORA/ROR:  C -> [b7...b0] -> C     (9-bit rotate)
```

### Branch Instructions

| Instruction | Condition | Description |
|-------------|-----------|-------------|
| `BRA label` | Always | Branch always |
| `BRN label` | Never | Branch never (2-byte NOP) |
| `BEQ label` | Z=1 | Branch if equal (zero) |
| `BNE label` | Z=0 | Branch if not equal |
| `BCS label` | C=1 | Branch if carry set (unsigned lower) |
| `BCC label` | C=0 | Branch if carry clear (unsigned higher/same) |
| `BLO label` | C=1 | Alias for BCS (unsigned lower) |
| `BHS label` | C=0 | Alias for BCC (unsigned higher/same) |
| `BHI label` | C=0 AND Z=0 | Branch if unsigned higher |
| `BLS label` | C=1 OR Z=1 | Branch if unsigned lower/same |
| `BMI label` | N=1 | Branch if minus (negative) |
| `BPL label` | N=0 | Branch if plus (positive) |
| `BVS label` | V=1 | Branch if overflow set |
| `BVC label` | V=0 | Branch if overflow clear |
| `BGE label` | N⊕V=0 | Branch if signed >= |
| `BLT label` | N⊕V=1 | Branch if signed < |
| `BGT label` | Z=0 AND N⊕V=0 | Branch if signed > |
| `BLE label` | Z=1 OR N⊕V=1 | Branch if signed <= |
| `BSR label` | Always | Branch to subroutine |

**Branch range:** -128 to +127 bytes from the instruction following the branch.

### Jump and Call

| Instruction | Description |
|-------------|-------------|
| `JMP dst` | Jump (indexed or extended) |
| `JSR dst` | Jump to subroutine (pushes return address) |
| `RTS` | Return from subroutine |
| `RTI` | Return from interrupt |

### Stack Operations

| Instruction | Description |
|-------------|-------------|
| `PSHA` | Push A onto stack |
| `PSHB` | Push B onto stack |
| `PSHX` | Push X onto stack (2 bytes) |
| `PULA` | Pull A from stack |
| `PULB` | Pull B from stack |
| `PULX` | Pull X from stack |
| `INS` | Increment SP (pop 1 byte) |
| `DES` | Decrement SP (reserve 1 byte) |
| `TSX` | Transfer SP to X |
| `TXS` | Transfer X to SP |

### Register Transfers

| Instruction | Description |
|-------------|-------------|
| `TAB` | A -> B |
| `TBA` | B -> A |
| `TAP` | A -> CCR (flags) |
| `TPA` | CCR -> A |
| `XGDX` | Exchange D and X (HD6303) |

### Flag Control

| Instruction | Description |
|-------------|-------------|
| `CLC` | Clear carry flag |
| `SEC` | Set carry flag |
| `CLV` | Clear overflow flag |
| `SEV` | Set overflow flag |
| `CLI` | Clear interrupt mask (enable IRQ) |
| `SEI` | Set interrupt mask (disable IRQ) |

### Control Instructions

| Instruction | Description |
|-------------|-------------|
| `NOP` | No operation (1 byte, 1 cycle) |
| `SWI` | Software interrupt (system call) |
| `WAI` | Wait for interrupt |
| `SLP` | Sleep (low-power mode, HD6303) |
| `TRAP` | Software trap |

---

## 7. Assembler Directives

### Origin and Location

```asm
        ORG     $2100           ; Set program counter
        * = $8000               ; Alternative ORG syntax
```

### Symbol Definition

```asm
CONST   EQU     $1234           ; Define constant (immutable)
VALUE   =       100             ; Alternative EQU syntax
COUNT   SET     0               ; Define variable (can be reassigned)
COUNT   SET     COUNT+1         ; Reassign SET symbol
```

### Data Definition

```asm
; FCB/DB - Define byte(s)
        FCB     $41, $42, $43   ; Three bytes
        DB      'A', 'B', 'C'   ; Same thing
        BYTE    0               ; Alias

; FCC - Define string (no terminator)
        FCC     "Hello"         ; 5 bytes

; FDB/DW - Define word(s) (16-bit, big-endian)
        FDB     $1234           ; Two bytes: $12, $34
        DW      LABEL           ; Store address
        WORD    $FFFF           ; Alias

; RMB/DS - Reserve bytes (uninitialized)
        RMB     32              ; Reserve 32 bytes
        DS      100             ; Alias
        RESERVE 16              ; Alias

; FILL - Fill with value
        FILL    $FF, 16         ; Fill 16 bytes with $FF

; ALIGN - Align to boundary
        ALIGN   256             ; Align to 256-byte boundary
```

### Code Organization

```asm
; Include source file
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

; Include binary data
        INCBIN  "font.bin"

; End of source (optional)
        END                     ; Marks end of source
        END     START           ; Optionally specify entry point
```

### Conditional Assembly

```asm
; Symbol-based conditions
#IFDEF DEBUG
        PRINT   debug_msg
#ENDIF

#IFNDEF RELEASE
        JSR     _debug_check
#ENDIF

; Expression-based conditions
#IF TARGET == LZ
        ; LZ-specific code
#ELIF TARGET == XP
        ; XP-specific code
#ELSE
        ; Default code
#ENDIF
```

### Macros

```asm
; Simple macro
MACRO SAVE_REGS
        PSHA
        PSHB
        PSHX
ENDM

; Macro with parameters
MACRO PRINT_AT, row, col, msg
        AT      \row, \col
        PRINT   \msg
ENDM

; Usage
        SAVE_REGS
        PRINT_AT 0, 0, hello_msg
```

---

## 8. Runtime Library Macros

The runtime library (`runtime.inc`) provides convenient macros for common operations. Include it with:

```asm
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"
```

### Display Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `CLS` | Clear screen | `CLS` |
| `CURSOR pos` | Set cursor position | `CURSOR 16` |
| `AT row, col` | Position by row/column | `AT 1, 5` |
| `PRINT addr` | Print null-terminated string | `PRINT message` |
| `PRINT_INT val` | Print signed integer | `PRINT_INT score` |
| `PRINT_UINT val` | Print unsigned integer | `PRINT_UINT count` |
| `PRINT_HEX val` | Print as 4 hex digits | `PRINT_HEX address` |
| `PUTCHAR c` | Output single character | `PUTCHAR 'A'` |

### Input Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `GETKEY` | Wait for keypress (D = key) | `GETKEY` |
| `TESTKEY` | Non-blocking key check | `TESTKEY` |
| `KBHIT` | Check if key in buffer | `KBHIT` |
| `FLUSHKB` | Flush keyboard buffer | `FLUSHKB` |

### Sound Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `BEEP` | Sound a beep | `BEEP` |
| `ALARM` | Sound alarm pattern | `ALARM` |
| `TONE pitch, dur` | Custom tone | `TONE 100, 16` |

### Timing Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `DELAY ticks` | Wait (1 tick ≈ 1/32 sec) | `DELAY 32` |
| `GETTICKS` | Get tick counter (D) | `GETTICKS` |

### Math Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `ABS val` | Absolute value | `ABS number` |
| `MIN a, b` | Minimum of two | `MIN score, highscore` |
| `MAX a, b` | Maximum of two | `MAX value, #0` |

### String Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `STRLEN str` | String length (D) | `STRLEN message` |
| `STRCPY dst, src` | Copy string | `STRCPY buffer, input` |
| `STRCMP s1, s2` | Compare strings (D) | `STRCMP name, "TEST"` |
| `STRCAT dst, src` | Concatenate strings | `STRCAT path, filename` |
| `STRCHR str, c` | Find character | `STRCHR line, ','` |
| `STRNCPY dst, src, n` | Bounded copy | `STRNCPY buf, src, 10` |
| `STRNCMP s1, s2, n` | Bounded compare | `STRNCMP a, b, 5` |

### Memory Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `MEMCPY dst, src, n` | Copy n bytes | `MEMCPY dest, src, 100` |
| `MEMSET dst, c, n` | Fill n bytes | `MEMSET buffer, 0, 32` |
| `MEMCMP a, b, n` | Compare n bytes | `MEMCMP buf1, buf2, 16` |

### Conversion Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `ATOI str` | String to integer (D) | `ATOI input` |
| `ITOA val, buf` | Integer to string | `ITOA score, numbuf` |

### Graphics Macros

| Macro | Description | Example |
|-------|-------------|---------|
| `UDG_DEFINE num, data` | Define custom character | `UDG_DEFINE 0, star_gfx` |

### LZ-Only Macros (4-Line Display)

| Macro | Description | Example |
|-------|-------------|---------|
| `SETMODE m` | Set display mode | `SETMODE MODE_4LINE` |
| `GETMODE` | Get display mode (D) | `GETMODE` |
| `PUSHMODE` | Save mode to stack | `PUSHMODE` |
| `POPMODE` | Restore mode | `POPMODE` |

### Example Using Macros

```asm
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

        ORG     $2100

START:
        CLS                     ; Clear screen
        PRINT   greeting        ; "Hello!"
        AT      1, 0            ; Move to line 2
        PRINT   prompt          ; "Press any key"
        GETKEY                  ; Wait for key

        CLS
        PRINT   score_label     ; "Score: "
        PRINT_INT #1234         ; Print 1234

        DELAY   64              ; Wait 2 seconds
        RTS

greeting:
        FCC     "Hello!"
        FCB     0
prompt:
        FCC     "Press any key"
        FCB     0
score_label:
        FCC     "Score: "
        FCB     0
```

---

## 9. System Calls

The Psion OS provides services via the `SWI` instruction. Place the service number in the byte following SWI:

```asm
        LDAA    #'A'            ; Character to print
        SWI
        FCB     $10             ; DP_EMIT service
```

Or use the SDK macros:

```asm
        LDAA    #'A'
        LDAB    #DP_EMIT        ; Load service number
        SWI                     ; FCB follows automatically? No!
```

**Typical pattern with syscall constants:**

```asm
        SWI
        FCB     DP_EMIT         ; DP_EMIT = $10
```

### Common System Calls

#### Display Services

| Service | Code | Input | Output | Description |
|---------|------|-------|--------|-------------|
| DP_EMIT | $10 | A=char | - | Display character |
| DP_PRNT | $11 | X=str, B=len | - | Display string |
| DP_STAT | $14 | A=pos, B=status | - | Set cursor position |
| DP_BELL | $0E | - | - | Sound beep |
| UT_CDSP | $68 | - | - | Clear display |

#### Keyboard Services

| Service | Code | Input | Output | Description |
|---------|------|-------|--------|-------------|
| KB_GETK | $48 | - | B=key | Wait for key |
| KB_TEST | $4B | - | B=key or 0 | Test for key |
| KB_BREK | $49 | A=code | C=break | Test break key |

#### Timer Services

| Service | Code | Input | Output | Description |
|---------|------|-------|--------|-------------|
| TM_WAIT | $6C | D=ticks | - | Wait for ticks |
| TM_TICK | $6D | - | D=count | Get tick count |

#### Utility Services

| Service | Code | Input | Output | Description |
|---------|------|-------|--------|-------------|
| UT_UTOB | $7A | D=value, X=buf | B=len | Unsigned to ASCII |
| UT_BTOU | $78 | X=str | D=value | ASCII to unsigned |

### Example: Manual System Calls

```asm
; Print "HELLO" using DP_PRNT
        LDX     #message
        LDAB    #5              ; Length
        SWI
        FCB     $11             ; DP_PRNT

; Wait for key
        SWI
        FCB     $48             ; KB_GETK
        ; Key code now in B

; Check for ON/CLEAR break
        LDAA    #$49            ; KB_BREK code
        SWI
        BCS     user_break      ; Branch if break pressed

message:
        FCC     "HELLO"
```

---

## 10. Memory Layout

### Psion Memory Map (Typical)

| Address Range | Description |
|---------------|-------------|
| $0000-$00FF | Zero page (fast access) |
| $0000-$001F | HD6303 internal registers |
| $0020-$007F | System variables |
| $0080-$00FF | Work area (temporary storage) |
| $0100-$01FF | Hardware I/O |
| $0180 | LCD control register |
| $0181 | LCD data register |
| $2000-$7FFF | RAM (varies by model) |
| $2100 | Standard code load address |
| $8000-$FFFF | ROM |

### Useful Zero-Page Addresses

```asm
; Temporary work words (from sysvars.inc)
UTW_S0  EQU     $80     ; Temp word 0 (trashed by allocator)
UTW_S1  EQU     $82     ; Temp word 1
UTW_S2  EQU     $84     ; Temp word 2
UTW_S3  EQU     $86     ; Temp word 3
UTW_T0  EQU     $88     ; Temp word (safe to use)
UTW_T1  EQU     $8A     ; Temp word
UTW_T2  EQU     $8C     ; Temp word
UTW_W0  EQU     $90     ; Work word 0
UTW_W1  EQU     $92     ; Work word 1
UTW_W2  EQU     $94     ; Work word 2
```

### Display System Variables

| Address | Name | Description |
|---------|------|-------------|
| $62 | DPB_CPOS | Cursor position (0-31 or 0-79) |
| $63 | DPB_CUST | Cursor state (bit 7=visible) |
| $2184 | DPB_MODE | Display mode (0=2-line, 1=4-line) |
| $2092 | DPB_NLIN | Number of lines (2 or 4) |
| $2093 | DPB_WIDE | Display width (16 or 20) |

---

## 11. Self-Relocation

When code needs to work at any load address (especially for C-compiled programs), use the `-r` flag:

```bash
psasm -r -I include program.asm -o program.ob3
```

### What Self-Relocation Does

1. **Generates a position-independent stub** (~93 bytes) that discovers its runtime address
2. **Tracks all absolute address references** (JSR, JMP, LDX#, etc.)
3. **Creates a fixup table** listing addresses to patch
4. **Patches addresses at runtime** by adding the load offset

### When to Use `-r`

- All C-compiled programs (required)
- Assembly programs with `JSR`/`JMP` to internal labels
- Programs that reference data addresses with `LDX #label`

### When NOT to Use `-r`

- Simple assembly programs using only relative branches (BSR, BRA, BEQ, etc.)
- Programs that only call system services (fixed ROM addresses)
- Code where all jumps are relative or to external (ROM) addresses

### Addressing Mode Impact

In relocatable mode, the assembler **forces extended addressing** for internal symbol references:

```asm
; In relocatable mode:
        JSR     my_func         ; Always BD xx xx (extended, 3 bytes)
        JSR     <$3F            ; Forces direct mode (NOT relocated!)
        JSR     >my_func        ; Explicit extended (will be relocated)
```

**Warning:** Using `<` prefix in relocatable code creates a direct-mode instruction that will NOT be patched. Only use `<` for fixed system addresses.

---

## 12. Assembler Optimizer

The assembler includes a peephole optimizer enabled by default. It applies safe transformations to reduce code size:

### Optimizations Applied

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

### Disabling Optimization

```bash
psasm --no-optimize program.asm -o program.ob3
```

### Patterns NOT Optimized (for safety)

The following are **not** optimized because they have different flag behavior:

| Pattern | Why NOT Optimized |
|---------|-------------------|
| `LDAA #0` → `CLRA` | CLR clears Carry, LD doesn't affect it |
| `ADDA #1` → `INCA` | INC doesn't set Carry, ADD does |
| `SUBA #1` → `DECA` | DEC doesn't set Carry, SUB does |

---

## 13. Build Process

### Using psbuild (Recommended)

Single command to build from source to OPK:

```bash
# Assembly program
psbuild myprogram.asm -o MYPROG.opk

# With verbose output
psbuild -v myprogram.asm -o MYPROG.opk

# Keep intermediate files for debugging
psbuild -k myprogram.asm -o MYPROG.opk

# Target LZ (4-line display)
psbuild -m LZ myprogram.asm -o MYPROG.opk

# Enable relocatable code (for assembly with internal symbol refs)
psbuild -r myprogram.asm -o MYPROG.opk
```

### Manual Pipeline

```bash
# Step 1: Assemble to OB3
psasm -I include myprogram.asm -o /tmp/myprogram.ob3

# With relocation support
psasm -r -I include myprogram.asm -o /tmp/myprogram.ob3

# For LZ target
psasm -r -m LZ -I include myprogram.asm -o /tmp/myprogram.ob3

# Step 2: Create OPK pack
psopk create -o MYPROG.opk /tmp/myprogram.ob3

# Step 3: Transfer to device
pslink send MYPROG.opk

# Or flash directly
pslink flash MYPROG.opk
```

### Output Formats

| Flag | Format | Use Case |
|------|--------|----------|
| `-o file.ob3` | OB3 (default) | For psopk, transfer to Psion |
| `-b file.bin` | Raw binary | Machine code only, no wrapper |
| `-p file.proc` | Procedure | OPL wrapper without OB3 header |
| `-l file.lst` | Listing | Debugging, code review |

### Listing File

Generate a listing file with `-l`:

```bash
psasm -l program.lst -I include program.asm -o program.ob3
```

Example listing output:
```
Psion Assembler - program.asm
=============================

Addr  Code          Line  Source
----  ------------  ----  ------
2100  BD 21 10      1     START:  JSR     init
2103  86 00         2             LDAA    #0
2105  BD 21 20      3             JSR     main
2108  39            4             RTS

Symbol Table
------------
START   = $2100
init    = $2110
main    = $2120
```

---

## 14. Practical Examples

### Example 1: Counter Display

```asm
; counter.asm - Display counting numbers
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

        ORG     $2100

MAX_COUNT       EQU     100

START:
        CLRA
        STAA    count           ; Initialize counter

MAIN_LOOP:
        CLS                     ; Clear display
        PRINT_INT count         ; Show current value
        GETKEY                  ; Wait for key

        ; Check for break
        LDAA    #KB_BREK
        SWI
        BCS     EXIT

        ; Increment counter
        LDAA    count
        INCA
        CMPA    #MAX_COUNT
        BLO     STORE
        CLRA                    ; Wrap to 0

STORE:
        STAA    count
        BRA     MAIN_LOOP

EXIT:
        RTS

count:  RMB     1
```

### Example 2: Beep Pattern

```asm
; beeppattern.asm - Play a rhythm
        INCLUDE "psion.inc"

        ORG     $2100

START:
        LDAB    #5              ; 5 beeps

BEEP_LOOP:
        PSHB                    ; Save counter

        ; Short beep
        SWI
        FCB     $0E             ; BZ_BELL

        ; Short delay
        LDD     #8              ; 1/4 second
        SWI
        FCB     $6C             ; TM_WAIT

        PULB
        DECB
        BNE     BEEP_LOOP

        ; Long final delay
        LDD     #32             ; 1 second
        SWI
        FCB     $6C

        RTS
```

### Example 3: User Defined Graphic

```asm
; udg.asm - Display custom character
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

        ORG     $2100

START:
        CLS

        ; Define a star character as UDG 0
        UDG_DEFINE 0, star_data

        ; Display it
        PUTCHAR 0               ; Display UDG 0
        PUTCHAR ' '
        PUTCHAR 0
        PUTCHAR ' '
        PUTCHAR 0

        GETKEY
        RTS

; UDG bitmap: 5x8 pixels, one byte per row
star_data:
        FCB     %00100          ; ..X..
        FCB     %00100          ; ..X..
        FCB     %11111          ; XXXXX
        FCB     %01110          ; .XXX.
        FCB     %01110          ; .XXX.
        FCB     %10101          ; X.X.X
        FCB     %00100          ; ..X..
        FCB     %00000          ; .....
```

### Example 4: Simple Menu

```asm
; menu.asm - Simple menu system
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"

        ORG     $2100

START:
        CLS
        PRINT   menu_title
        AT      1, 0
        PRINT   menu_opts

WAIT_KEY:
        GETKEY

        CMPB    #'1'
        BEQ     OPTION_1
        CMPB    #'2'
        BEQ     OPTION_2
        CMPB    #'3'
        BEQ     EXIT
        BRA     WAIT_KEY

OPTION_1:
        CLS
        PRINT   msg_opt1
        BEEP
        DELAY   32
        BRA     START

OPTION_2:
        CLS
        PRINT   msg_opt2
        BEEP
        BEEP
        DELAY   32
        BRA     START

EXIT:
        RTS

menu_title:
        FCC     "=== MENU ==="
        FCB     0
menu_opts:
        FCC     "1:Beep 2:2x 3:Exit"
        FCB     0
msg_opt1:
        FCC     "Single Beep!"
        FCB     0
msg_opt2:
        FCC     "Double Beep!"
        FCB     0
```

---

## 15. Debugging Tips

### Using the Emulator MCP

The SDK includes an emulator with MCP (Model Context Protocol) interface for AI-assisted debugging:

```bash
# List emulator sessions
psion-mcp list_sessions

# Create emulator and boot
psion-mcp create_emulator --model LZ
psion-mcp boot_emulator

# Load your program
psion-mcp load_pack --opk_path myprogram.opk

# Set breakpoints
psion-mcp set_breakpoint --address 0x2100

# Step through code
psion-mcp step_with_disasm

# View registers
psion-mcp get_registers

# Read memory
psion-mcp read_memory --address 0x2100 --count 32
```

### Common Debug Techniques

1. **Add visual markers:**
```asm
DEBUG:
        LDAA    #'*'
        SWI
        FCB     $10     ; Print marker
```

2. **Print register values:**
```asm
        ; Print A register value
        PSHA
        PSHB
        TAB             ; A -> B for PRINT_HEX
        CLRA            ; Clear high byte
        PSHB
        PSHA
        JSR     _print_hex
        INS
        INS
        PULB
        PULA
```

3. **Breakpoint with keypress:**
```asm
        ; Wait for key before continuing
        SWI
        FCB     $48     ; KB_GETK
```

### Disassembly

Use `psdisasm` to examine compiled code:

```bash
# Disassemble binary
psdisasm program.bin --address 0x2100

# With hex dump
psdisasm program.bin --hex

# Limit output
psdisasm program.bin --count 20
```

---

## 16. Common Pitfalls

### 1. Forgetting the Null Terminator

```asm
; WRONG - no null terminator
message:
        FCC     "Hello"

; CORRECT
message:
        FCC     "Hello"
        FCB     0
```

### 2. Stack Imbalance

```asm
; WRONG - unbalanced stack
        PSHA
        ; ... code that returns without PULA
        RTS             ; Stack corrupted!

; CORRECT
        PSHA
        ; ... code ...
        PULA
        RTS
```

### 3. Wrong Stack Offsets

```asm
; After PSHX + TSX, offsets are:
;   0,X = saved X (high byte)
;   1,X = saved X (low byte)
;   2,X = return address (high)
;   3,X = return address (low)
;   4,X = first argument (high)
;   5,X = first argument (low)

; WRONG
        PSHX
        TSX
        LDAA    2,X     ; This is return address, not argument!

; CORRECT
        PSHX
        TSX
        LDD     4,X     ; First argument is at offset 4
```

### 4. Modifying X in Indexed Addressing

```asm
; WRONG - X modified between setup and use
        LDX     #buffer
        JSR     some_func       ; This might destroy X!
        LDAA    0,X             ; X may be garbage

; CORRECT - preserve X
        LDX     #buffer
        PSHX
        JSR     some_func
        PULX
        LDAA    0,X             ; X is valid
```

### 5. Branch Out of Range

```asm
; WRONG (but assembler auto-fixes this)
        BEQ     very_far_label  ; More than 127 bytes away

; The assembler automatically relaxes this to:
;       BNE     skip
;       JMP     very_far_label
; skip:
```

### 6. Direct Mode in Relocatable Code

```asm
; WRONG in relocatable code (-r flag)
        JSR     <my_func        ; Direct mode won't be patched!

; CORRECT
        JSR     my_func         ; Assembler uses extended mode
```

### 7. INC/DEC Don't Set Carry

```asm
; WRONG - checking carry after INC
        LDAA    #$FF
        INCA                    ; A becomes 0, but C is NOT set!
        BCS     overflow        ; This branch never taken!

; CORRECT - use ADD for carry detection
        LDAA    #$FF
        ADDA    #1              ; A becomes 0, C IS set
        BCS     overflow        ; This works
```

### 8. TSX Behavior

```asm
; NOTE: TSX gives X = SP directly (not SP+1)
; This is different from some 6800 documentation

        LDAA    #$42
        PSHA                    ; Push $42
        TSX                     ; X = SP (pointing to the $42)
        LDAB    0,X             ; B = $42 (correct!)
```

### 9. XGDX Destroys D

```asm
; WRONG - using D after XGDX without reloading
        LDD     #$1234
        XGDX                    ; D now contains old X value!
        STD     somewhere       ; Storing old X, not $1234!

; CORRECT
        LDD     #$1234
        XGDX                    ; X = $1234, D = old X
        ; If you need the original D value, save it first
```

### 10. Forgetting RTS

```asm
; WRONG - code falls through
my_func:
        LDAA    #0
        ; Missing RTS - will execute whatever follows!

; CORRECT
my_func:
        LDAA    #0
        RTS
```

---

## See Also

- [small-c-prog.md](small-c-prog.md) - Small-C Programming Manual
- [stdlib.md](stdlib.md) - Core string and character functions
- [stdio.md](stdio.md) - Extended string functions and sprintf
- [cli-tools.md](cli-tools.md) - CLI Tools Manual (psbuild, pscc, psasm, psopk, pslink, psdisasm)

---

## References

- [Psion Technical Reference](https://www.jaapsch.net/psion/)
- [HD6303 Instruction Set](https://www.jaapsch.net/psion/mcmnemal.htm)
- [System Calls Reference](https://www.jaapsch.net/psion/mcosxp1.htm)
- [System Variables](https://www.jaapsch.net/psion/sysvars.htm)

---

*Last updated: January 2026*
