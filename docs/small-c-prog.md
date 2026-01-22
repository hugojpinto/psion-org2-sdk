# Small-C Programming Manual

**Psion Organiser II SDK**

This manual provides a comprehensive guide to programming the Psion Organiser II using Small-C, a subset of the C programming language optimized for 8-bit microprocessors.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Building Programs](#3-building-programs)
4. [Language Reference](#4-language-reference)
5. [Standard Library](#5-standard-library)
6. [Optional Libraries](#6-optional-libraries)
7. [External OPL Procedures](#7-external-opl-procedures)
8. [Target Models](#8-target-models)
9. [Memory and Optimization](#9-memory-and-optimization)
10. [Examples](#10-examples)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Introduction

### 1.1 What is Small-C?

Small-C is a subset of the C programming language designed for 8-bit microprocessors with limited resources. The Psion SDK's Small-C compiler (`pscc`) translates C source code into HD6303 assembly, which is then assembled into executable code for the Psion Organiser II.

### 1.2 Why Small-C?

- **Familiar Syntax**: C-like syntax is easier to learn than assembly
- **Readable Code**: Programs are more maintainable than assembly
- **Portable Design**: Concepts transfer to other C environments
- **Efficient Output**: Generates tight HD6303 machine code
- **Full Hardware Access**: Access all Psion features through library functions

### 1.3 Target Hardware

The Psion Organiser II family includes several models:

| Model | RAM | Display | Notes |
|-------|-----|---------|-------|
| CM | 8KB | 16x2 | Entry model |
| XP | 16-32KB | 16x2 | Extended memory (default target) |
| LZ | 32KB | 20x4 | 4-line display |
| LZ64 | 64KB | 20x4 | Maximum RAM |

### 1.4 Design Philosophy

The SDK prioritizes:
- **Correctness over speed**: The compiler produces correct output first
- **Transparency**: Readable assembly output for debugging
- **Simplicity**: Support a minimal but useful C subset
- **8-bit efficiency**: Generate tight code for the HD6303

---

## 2. Getting Started

### 2.1 Prerequisites

- Python 3.10 or higher
- The Psion SDK installed and configured
- A virtual environment activated

### 2.2 Setup

```bash
# Create virtual environment (first time only)
python3 -m venv .venv

# Activate virtual environment (REQUIRED for every session)
source .venv/bin/activate

# Install in development mode (first time only)
pip install -e .
```

### 2.3 Your First Program

Create a file `hello.c`:

```c
#include <psion.h>

void main() {
    cls();
    print("Hello, Psion!");
    getkey();
}
```

Build it:

```bash
psbuild hello.c -o HELLO.opk
```

Transfer to device:

```bash
python -m psion_sdk.cli.pslink flash HELLO.opk
```

---

## 3. Building Programs

### 3.1 The psbuild Tool (Recommended)

`psbuild` is a unified build tool that handles the complete compilation pipeline in a single command:

```bash
# Build C program (default target: XP)
psbuild myprogram.c -o MYPROGRAM.opk

# Build for LZ/LZ64 (4-line display)
psbuild -m LZ myprogram.c -o MYPROGRAM.opk

# Verbose output (shows each stage)
psbuild -v myprogram.c -o MYPROGRAM.opk

# Keep intermediate files for debugging
psbuild -k myprogram.c -o MYPROGRAM.opk
```

### 3.2 Manual Build Pipeline

For finer control, you can use individual tools:

```bash
# Step 1: Compile C to assembly
python -m psion_sdk.cli.pscc -I include hello.c -o /tmp/hello.asm

# Step 2: Assemble with relocation support (REQUIRED for C programs)
python -m psion_sdk.cli.psasm -r -I include /tmp/hello.asm -o /tmp/HELLO.ob3

# Step 3: Create OPK pack
python -m psion_sdk.cli.psopk create -o HELLO.opk /tmp/HELLO.ob3
```

### 3.3 Build Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   .c file   │────▶│  .asm file  │────▶│  .ob3 file  │────▶│  .opk file  │
│  (Small-C)  │pscc │ (Assembly)  │psasm│  (Object)   │psopk│   (Pack)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 3.4 Important Flags

| Flag | Tool | Description |
|------|------|-------------|
| `-I include` | pscc, psasm | Include path for headers |
| `-m LZ` | pscc, psasm | Target 4-line display (LZ/LZ64) |
| `-r` | psasm | Generate self-relocating code (REQUIRED for C) |
| `-v` | psbuild, pscc | Verbose output |
| `-k` | psbuild | Keep intermediate files |

---

## 4. Language Reference

### 4.1 Data Types

Small-C supports a limited set of data types optimized for 8-bit CPUs:

| Type | Size | Range | Description |
|------|------|-------|-------------|
| `char` | 8 bits | -128 to 127 | Signed character |
| `unsigned char` | 8 bits | 0 to 255 | Unsigned character |
| `int` | 16 bits | -32768 to 32767 | Signed integer |
| `unsigned int` | 16 bits | 0 to 65535 | Unsigned integer |
| Pointers | 16 bits | - | Address of any type |

**Not Supported:**
- `float`, `double` (use the float.h library instead)
- `long`, `long long`
- `short` (use `int` instead)

### 4.2 Variables

#### Global Variables

Declared outside any function, accessible from all functions:

```c
int score;           /* Global integer */
char buffer[32];     /* Global array */
int *ptr;            /* Global pointer */
```

#### Local Variables

Declared inside functions, allocated on the stack:

```c
void example() {
    int x;           /* Local variable */
    char c;

    x = 10;
    c = 'A';
}
```

#### Arrays

Single-dimensional arrays are supported:

```c
char name[16];       /* Array of 16 characters */
int values[10];      /* Array of 10 integers */

/* Array access */
values[0] = 100;
name[5] = 'X';
```

**Note:** Multi-dimensional arrays are NOT supported.

### 4.3 Operators

#### Arithmetic Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Addition | `a + b` |
| `-` | Subtraction | `a - b` |
| `*` | Multiplication | `a * b` |
| `/` | Division | `a / b` |
| `%` | Modulo | `a % b` |

#### Relational Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `a == b` |
| `!=` | Not equal | `a != b` |
| `<` | Less than | `a < b` |
| `>` | Greater than | `a > b` |
| `<=` | Less or equal | `a <= b` |
| `>=` | Greater or equal | `a >= b` |

#### Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `&&` | Logical AND | `a && b` |
| `\|\|` | Logical OR | `a \|\| b` |
| `!` | Logical NOT | `!a` |

#### Bitwise Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `&` | Bitwise AND | `a & b` |
| `\|` | Bitwise OR | `a \| b` |
| `^` | Bitwise XOR | `a ^ b` |
| `~` | Bitwise NOT | `~a` |
| `<<` | Left shift | `a << 2` |
| `>>` | Right shift | `a >> 2` |

#### Assignment Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Assignment | `a = b` |
| `+=` | Add and assign | `a += b` |
| `-=` | Subtract and assign | `a -= b` |
| `*=` | Multiply and assign | `a *= b` |
| `/=` | Divide and assign | `a /= b` |
| `%=` | Modulo and assign | `a %= b` |
| `&=` | AND and assign | `a &= b` |
| `\|=` | OR and assign | `a \|= b` |
| `^=` | XOR and assign | `a ^= b` |
| `<<=` | Left shift and assign | `a <<= 2` |
| `>>=` | Right shift and assign | `a >>= 2` |

#### Increment/Decrement Operators

```c
int x = 5;

x++;    /* Post-increment: use x, then increment */
++x;    /* Pre-increment: increment, then use x */
x--;    /* Post-decrement */
--x;    /* Pre-decrement */
```

#### Pointer Operators

```c
int x = 42;
int *p;

p = &x;     /* Address-of: get address of x */
*p = 100;   /* Dereference: access value at p */
```

### 4.4 Control Flow

#### if/else Statement

```c
if (x > 0) {
    print("Positive");
} else if (x < 0) {
    print("Negative");
} else {
    print("Zero");
}
```

#### while Loop

```c
int i = 0;
while (i < 10) {
    print_int(i);
    i = i + 1;
}
```

#### for Loop

```c
int i;
for (i = 0; i < 10; i++) {
    print_int(i);
}
```

#### do-while Loop

```c
int i = 0;
do {
    print_int(i);
    i++;
} while (i < 10);
```

#### switch Statement

```c
char key = getkey();

switch (key) {
    case 'A':
        print("Option A");
        break;
    case 'B':
        print("Option B");
        break;
    default:
        print("Unknown");
        break;
}
```

#### break and continue

```c
while (1) {
    key = getkey();

    if (key == 'Q') {
        break;      /* Exit the loop */
    }

    if (key == ' ') {
        continue;   /* Skip to next iteration */
    }

    /* Process key */
    putchar(key);
}
```

#### goto (Limited)

```c
void example() {
    /* goto is supported but discouraged */
    goto end;

    print("This is skipped");

end:
    print("At end");
}
```

### 4.5 Functions

#### Function Definition

```c
/* Function with no return value */
void show_message() {
    print("Hello!");
}

/* Function returning an integer */
int add(int a, int b) {
    return a + b;
}

/* Function with char return */
char get_first_char(char *s) {
    return *s;
}
```

#### Function Calls

```c
void main() {
    int sum;

    show_message();
    sum = add(10, 20);
    print_int(sum);
}
```

#### The main Function

Every program must have a `main` function as the entry point:

```c
void main() {
    /* Your program starts here */
}
```

**Note:** Unlike standard C, `main` returns `void` (not `int`). The program exits when `main` returns.

### 4.6 Pointers and Arrays

#### Basic Pointers

```c
int x = 42;
int *p;

p = &x;          /* p points to x */
*p = 100;        /* x is now 100 */
print_int(*p);   /* prints 100 */
```

#### Pointers and Arrays

Arrays decay to pointers when passed to functions:

```c
void print_array(int *arr, int len) {
    int i;
    for (i = 0; i < len; i++) {
        print_int(arr[i]);
    }
}

void main() {
    int data[5];
    data[0] = 10;
    data[1] = 20;
    print_array(data, 2);
}
```

#### String Pointers

```c
char *msg = "Hello";
print(msg);          /* prints "Hello" */

char buffer[20];
strcpy(buffer, msg);
```

### 4.7 Structs

Structs allow grouping related data together.

#### Struct Definition

```c
struct Point {
    int x;
    int y;
};

struct Rectangle {
    struct Point topLeft;
    struct Point bottomRight;
};
```

#### Struct Variables

```c
struct Point p;          /* Local struct */
struct Point *pp;        /* Pointer to struct */
struct Point points[4];  /* Array of structs */
```

#### Member Access

```c
/* Direct access with dot operator */
p.x = 10;
p.y = 20;

/* Pointer access with arrow operator */
pp = &p;
pp->x = 30;

/* Nested struct access */
struct Rectangle rect;
rect.topLeft.x = 0;
rect.bottomRight.y = 100;
```

#### sizeof with Structs

```c
int size = sizeof(struct Point);  /* Returns 4 (2 + 2 bytes) */
```

#### Copying Structs

**Important:** Struct assignment (`a = b`) is NOT supported. Use `struct_copy`:

```c
struct Point a, b;
a.x = 10;
a.y = 20;

/* Copy struct using helper function */
struct_copy(&b, &a, sizeof(struct Point));
```

#### Struct Limitations

- Maximum struct size: 255 bytes
- No struct assignment by value
- No structs as function parameters (use pointers)
- No struct return values (use out-parameters)
- No compound initializers (`{10, 20}`)
- No bit-fields

#### Typedef for Structs

```c
typedef struct {
    int x;
    int y;
} Point;

Point p;      /* No 'struct' keyword needed */
Point *pp;
```

### 4.8 8-Bit Char Arithmetic

When both operands are `char` type, the compiler generates efficient 8-bit HD6303 instructions:

```c
char a, b, c;

c = a + b;    /* Uses 8-bit ADDB */
c = a - b;    /* Uses 8-bit SUBB */
c = a & b;    /* Uses 8-bit ANDB */
c = a | b;    /* Uses 8-bit ORAB */
c = a ^ b;    /* Uses 8-bit EORB */
```

**Type Safety Rules:**
- `char + char` → char result (8-bit)
- `int + int` → int result (16-bit)
- `char + int` → **ERROR** (mixed types not allowed)

```c
char c = 'A';
c = c + ' ';     /* OK: char + char */
c = c + 32;      /* ERROR: char + int (use c + ' ' instead) */
```

**Operations that promote to 16-bit:**
Multiply, divide, modulo, and shifts always use 16-bit operations:

```c
char a, b;
int r;
r = a * b;    /* Promotes to 16-bit */
r = a / b;    /* Promotes to 16-bit */
```

### 4.9 Preprocessor

#### #define - Simple Macros

```c
#define MAX_SIZE 100
#define PI_STR "3.14159"

int buffer[MAX_SIZE];
```

#### #define - Function-like Macros

```c
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define ABS(x) ((x) < 0 ? -(x) : (x))

int bigger = MAX(x, y);
```

#### #include

```c
#include <psion.h>       /* System include path */
#include "myheader.h"    /* Local file */
```

#### Conditional Compilation

```c
#ifdef __PSION_4LINE__
    /* Code for LZ/LZ64 only */
    setmode(MODE_4LINE);
#else
    /* Code for CM/XP */
#endif

#ifndef DEBUG
    /* Release code */
#endif

#if DISP_ROWS == 4
    /* 4-line display code */
#endif
```

#### Predefined Macros

| Macro | Description |
|-------|-------------|
| `__PSION__` | Always defined |
| `__PSION_CM__` | Defined when targeting CM |
| `__PSION_XP__` | Defined when targeting XP (default) |
| `__PSION_LZ__` | Defined when targeting LZ |
| `__PSION_LZ64__` | Defined when targeting LZ64 |
| `__PSION_2LINE__` | Defined for 2-line models |
| `__PSION_4LINE__` | Defined for 4-line models |
| `DISP_ROWS` | Number of display rows (2 or 4) |
| `DISP_COLS` | Number of display columns (16 or 20) |

---

## 5. Standard Library

Include the standard library with:

```c
#include <psion.h>
```

### 5.1 Display Functions

| Function | Description |
|----------|-------------|
| `void cls(void)` | Clear screen |
| `void print(char *s)` | Print string |
| `void putchar(char c)` | Print character |
| `void cursor(int pos)` | Set cursor position |
| `void at(int pos, char *s)` | Print at position |
| `int gcursor(void)` | Get cursor position |
| `void print_int(int n)` | Print signed integer |
| `void print_uint(unsigned int n)` | Print unsigned integer |
| `void print_hex(unsigned int n)` | Print as hexadecimal |

**Cursor Position:** Position 0 is top-left. For 2-line displays: 0-15 (row 0), 16-31 (row 1). For 4-line displays: 0-19 (row 0), 20-39 (row 1), etc.

```c
cls();
cursor(0);
print("Line 1");
cursor(DISP_COLS);    /* Move to second line */
print("Line 2");
```

### 5.2 User Defined Graphics

Create custom 5x8 pixel characters:

```c
void udg_define(int char_num, char *data);
```

```c
/* Define a heart character */
char heart[8] = {
    0x00,  /* .....  */
    0x0A,  /* .X.X.  */
    0x1F,  /* XXXXX  */
    0x1F,  /* XXXXX  */
    0x0E,  /* .XXX.  */
    0x04,  /* ..X..  */
    0x00,  /* .....  */
    0x00   /* .....  */
};

udg_define(0, heart);
putchar(0);  /* Display the heart */
```

### 5.3 Keyboard Functions

| Function | Description |
|----------|-------------|
| `char getkey(void)` | Wait for and return keypress |
| `char testkey(void)` | Test for key (0 if none) |
| `int kbhit(void)` | Check if key available |
| `void flushkb(void)` | Flush keyboard buffer |

```c
char key;

/* Wait for keypress */
key = getkey();

/* Non-blocking check */
key = testkey();
if (key != 0) {
    print("Key pressed!");
}
```

### 5.4 Sound Functions

| Function | Description |
|----------|-------------|
| `void beep(void)` | Standard beep |
| `void alarm(void)` | Alarm sound |
| `void tone(int pitch, int duration)` | Custom tone |

```c
beep();                /* Short beep */
alarm();               /* Alarm sound */
tone(100, 16);         /* Custom tone: pitch 100, 0.5 sec */
```

### 5.5 Time Functions

| Function | Description |
|----------|-------------|
| `void delay(int ticks)` | Pause (1 tick = 1/50 sec = 20ms) |
| `unsigned int getticks(void)` | Get system tick counter |
| `void gettime(char *buf)` | Get time (6 bytes: YY MM DD HH MM SS) |
| `void settime(char *buf)` | Set time |

```c
delay(50);             /* Wait 1 second */
delay(100);            /* Wait 2 seconds */

unsigned int start = getticks();
/* ... do something ... */
unsigned int elapsed = getticks() - start;
```

### 5.6 String Functions

| Function | Description |
|----------|-------------|
| `int strlen(char *s)` | String length |
| `char *strcpy(char *dest, char *src)` | Copy string |
| `int strcmp(char *a, char *b)` | Compare strings |
| `char *strcat(char *dest, char *src)` | Concatenate strings |
| `char *strchr(char *s, int c)` | Find first char |
| `char *strncpy(char *dest, char *src, int n)` | Bounded copy |
| `int strncmp(char *s1, char *s2, int n)` | Bounded compare |

```c
char buf[20];

strcpy(buf, "Hello");
strcat(buf, " World");
print(buf);            /* "Hello World" */

int len = strlen(buf); /* 11 */

if (strcmp(buf, "Hello World") == 0) {
    print("Match!");
}

char *p = strchr(buf, 'W');  /* Points to "World" */
```

### 5.7 Memory Functions

| Function | Description |
|----------|-------------|
| `void *memcpy(void *dest, void *src, int n)` | Copy n bytes |
| `void *memset(void *dest, int c, int n)` | Fill n bytes |
| `int memcmp(void *a, void *b, int n)` | Compare n bytes |
| `void *struct_copy(void *dest, void *src, int size)` | Copy struct |

```c
char buf[100];

memset(buf, 0, 100);        /* Zero the buffer */
memcpy(dest, src, 50);      /* Copy 50 bytes */

if (memcmp(a, b, 10) == 0) {
    print("Equal");
}
```

### 5.8 Number Conversion

| Function | Description |
|----------|-------------|
| `int atoi(char *s)` | String to integer |
| `char *itoa(int n, char *s)` | Integer to string |

```c
int n = atoi("123");       /* n = 123 */
int m = atoi("-456");      /* m = -456 */

char buf[8];
itoa(42, buf);             /* buf = "42" */
print(buf);
```

### 5.9 Utility Functions

| Function | Description |
|----------|-------------|
| `int abs(int n)` | Absolute value |
| `int min(int a, int b)` | Minimum of two |
| `int max(int a, int b)` | Maximum of two |
| `void exit(void)` | Exit program |

---

## 6. Optional Libraries

### 6.1 ctype.h - Character Classification

Zero-cost macros for character testing and conversion:

```c
#include <psion.h>
#include <ctype.h>
```

#### Classification Macros

| Macro | True For |
|-------|----------|
| `isdigit(c)` | '0'-'9' |
| `isupper(c)` | 'A'-'Z' |
| `islower(c)` | 'a'-'z' |
| `isalpha(c)` | Letters |
| `isalnum(c)` | Letters or digits |
| `isspace(c)` | Whitespace |
| `isxdigit(c)` | Hex digits |
| `isprint(c)` | Printable (including space) |
| `isgraph(c)` | Graphic (excluding space) |
| `ispunct(c)` | Punctuation |
| `iscntrl(c)` | Control characters |

#### Conversion Macros

| Macro | Description |
|-------|-------------|
| `toupper(c)` | Convert to uppercase |
| `tolower(c)` | Convert to lowercase |
| `toascii(c)` | Mask to 7-bit ASCII |

```c
char c = getkey();

if (isdigit(c)) {
    int value = c - '0';
} else if (isalpha(c)) {
    c = toupper(c);
    putchar(c);
}
```

### 6.2 stdio.h - Extended String Functions

Additional string functions (adds ~300 bytes):

```c
#include <psion.h>
#include <stdio.h>
```

| Function | Description |
|----------|-------------|
| `char *strrchr(char *s, int c)` | Find last occurrence |
| `char *strstr(char *haystack, char *needle)` | Find substring |
| `char *strncat(char *dest, char *src, int n)` | Bounded concatenate |
| `int sprintf(buf, fmt, a1, a2, a3, a4)` | Formatted output |

#### sprintf Format Specifiers

| Specifier | Description |
|-----------|-------------|
| `%d` | Signed decimal |
| `%u` | Unsigned decimal |
| `%x` | Hexadecimal |
| `%c` | Character |
| `%s` | String |
| `%%` | Literal % |

```c
char buf[32];

sprintf1(buf, "Score: %d", 42);
print(buf);  /* "Score: 42" */

sprintf2(buf, "%d + %d", 10, 20);
print(buf);  /* "10 + 20" */

/* Find file extension */
char *ext = strrchr("file.txt", '.');
if (ext) {
    print(ext);  /* ".txt" */
}

/* Search for substring */
if (strstr(text, "error")) {
    print("Found error!");
}
```

### 6.3 float.h - Floating Point

Library-based floating point support:

```c
#include <psion.h>
#include <float.h>
```

#### Floating Point Type

```c
fp_t x, y, result;  /* 8-byte FP numbers */
```

#### Initialization and Conversion

| Function | Description |
|----------|-------------|
| `void fp_zero(fp_t *dest)` | Set to zero |
| `void fp_from_int(fp_t *dest, int n)` | Integer to FP |
| `void fp_from_str(fp_t *dest, char *s)` | String to FP |
| `int fp_to_int(fp_t *src)` | FP to integer |
| `void fp_to_str(char *buf, fp_t *src, int places)` | FP to string |

#### Arithmetic

| Function | Description |
|----------|-------------|
| `void fp_add(fp_t *result, fp_t *a, fp_t *b)` | Addition |
| `void fp_sub(fp_t *result, fp_t *a, fp_t *b)` | Subtraction |
| `void fp_mul(fp_t *result, fp_t *a, fp_t *b)` | Multiplication |
| `void fp_div(fp_t *result, fp_t *a, fp_t *b)` | Division |
| `void fp_neg(fp_t *n)` | Negate in place |

#### Mathematical Functions

| Function | Description |
|----------|-------------|
| `void fp_sin(fp_t *result, fp_t *angle)` | Sine (radians) |
| `void fp_cos(fp_t *result, fp_t *angle)` | Cosine |
| `void fp_tan(fp_t *result, fp_t *angle)` | Tangent |
| `void fp_atan(fp_t *result, fp_t *x)` | Arctangent |
| `void fp_sqrt(fp_t *result, fp_t *x)` | Square root |
| `void fp_exp(fp_t *result, fp_t *x)` | e^x |
| `void fp_ln(fp_t *result, fp_t *x)` | Natural log |
| `void fp_log(fp_t *result, fp_t *x)` | Log base 10 |
| `void fp_pow(fp_t *result, fp_t *x, fp_t *y)` | x^y |
| `void fp_rnd(fp_t *result)` | Random 0-1 |

#### Comparison and Output

| Function | Description |
|----------|-------------|
| `int fp_cmp(fp_t *a, fp_t *b)` | Compare (-1, 0, 1) |
| `int fp_sign(fp_t *n)` | Sign (-1, 0, 1) |
| `int fp_is_zero(fp_t *n)` | Check if zero |
| `void fp_print(fp_t *n, int places)` | Print to display |
| `void fp_print_sci(fp_t *n, int places)` | Scientific notation |

#### Error Handling

```c
fp_div(&result, &a, &b);
if (fp_error == FPE_DIVZERO) {
    print("Division by zero!");
    fp_clear_error();
}
```

#### Example

```c
#include <psion.h>
#include <float.h>

void main() {
    fp_t x, result;

    cls();

    /* Calculate sqrt(2) */
    fp_from_str(&x, "2.0");
    fp_sqrt(&result, &x);

    print("sqrt(2)=");
    fp_print(&result, 5);  /* 1.41421 */

    getkey();
}
```

---

## 7. External OPL Procedures

Small-C can call OPL procedures that exist on the Psion device.

### 7.1 Declaration Syntax

```c
external void MENU();           /* Void return */
external int GETVAL();          /* Integer return (calls GETVAL%) */
external char GETKEY();         /* Char return (calls GETKEY$) */
external int ADDNUM(int a, int b);  /* With parameters */
```

### 7.2 Return Type Mapping

| C Declaration | OPL Procedure | Notes |
|---------------|---------------|-------|
| `external void FUNC()` | `FUNC` | No return |
| `external int FUNC()` | `FUNC%` | Returns integer |
| `external char FUNC()` | `FUNC$` | Returns first char of string |

### 7.3 Parameters

External procedures support up to 4 integer parameters:

```c
external int COMPUTE(int x, int y, int z);

int result = COMPUTE(10, 20, 30);
```

### 7.4 Example

**C Code:**

```c
#include <psion.h>

external int ADDNUM(int a, int b);

void main() {
    int result;

    cls();
    result = ADDNUM(10, 32);
    print("10 + 32 = ");
    print_int(result);
    getkey();
}
```

**Corresponding OPL (create on Psion):**

```opl
ADDNUM%:(a%,b%)
LOCAL r%
r%=a%+b%
RETURN r%
```

### 7.5 Limitations

- Maximum 4 parameters
- Integer parameters only (`int` or `char`)
- Procedure names max 8 characters (including OPL suffix)
- No string returns (only first character captured)

---

## 8. Target Models

### 8.1 Two-Line Models (CM, XP)

Default target. Programs work on all models:

```bash
psbuild myprogram.c -o MYPROGRAM.opk
```

Display: 16 columns x 2 rows (32 cells total)

### 8.2 Four-Line Models (LZ, LZ64)

Use `-m LZ` flag for native 4-line support:

```bash
psbuild -m LZ myprogram.c -o MYPROGRAM.opk
```

Display: 20 columns x 4 rows (80 cells total)

### 8.3 Cross-Platform Code

Use preprocessor macros for portable code:

```c
void show_status() {
    cls();
    print("Status:");

#ifdef __PSION_4LINE__
    cursor(20);  /* Line 1 on 4-line */
    print("Memory OK");
    cursor(40);  /* Line 2 on 4-line */
    print("Battery OK");
#else
    cursor(16);  /* Line 1 on 2-line */
    print("All OK");
#endif

    getkey();
}
```

### 8.4 Display Mode Functions (LZ Only)

```c
#ifdef __PSION_4LINE__
    setmode(MODE_4LINE);  /* Use full display */
    /* ... */
    setmode(MODE_2LINE);  /* Compatibility mode */

    pushmode();           /* Save current mode */
    setmode(MODE_2LINE);
    /* ... */
    popmode();            /* Restore mode */
#endif
```

---

## 9. Memory and Optimization

### 9.1 Memory Considerations

| Resource | Typical Limit |
|----------|---------------|
| Program size | Depends on pack size (8KB-128KB) |
| Stack | ~256-512 bytes |
| Global variables | Limited by available RAM |

### 9.2 Code Size Tips

1. **Avoid stdio.h** unless needed (~300 bytes)
2. **Avoid float.h** unless needed (significant overhead)
3. **Use char for small values** (8-bit operations are smaller)
4. **Reuse buffers** instead of multiple arrays
5. **Use constants** instead of variables where possible

### 9.3 Self-Relocating Code

C programs are compiled with self-relocating code (`-r` flag) because the Psion loads programs at runtime-determined addresses. This is handled automatically by `psbuild`.

### 9.4 Compiler Optimizations

The compiler performs several optimizations:
- **Constant folding**: `x = 2 + 3` becomes `x = 5`
- **Power-of-2 multiply/divide**: Uses shifts
- **8-bit char arithmetic**: Efficient HD6303 instructions
- **Peephole optimization**: Removes redundant instructions

---

## 10. Examples

### 10.1 Hello World

```c
#include <psion.h>

void main() {
    cls();
    print("Hello, Psion!");
    getkey();
}
```

### 10.2 Counter Program

```c
#include <psion.h>

int count;

void display_count() {
    cls();
    print("Count: ");
    print_int(count);
}

void main() {
    char key;

    count = 0;

    while (1) {
        display_count();
        cursor(DISP_COLS);
        print("+/- or Q");

        key = getkey();

        if (key == '+') {
            count++;
        } else if (key == '-') {
            count--;
        } else if (key == 'Q') {
            break;
        }
    }

    cls();
    print("Goodbye!");
    delay(50);
}
```

### 10.3 Menu System

```c
#include <psion.h>
#include <ctype.h>

void option_a() {
    cls();
    print("Option A");
    getkey();
}

void option_b() {
    cls();
    print("Option B");
    getkey();
}

void main() {
    char key;

    while (1) {
        cls();
        print("A) First");
        cursor(DISP_COLS);
        print("B) Second Q)uit");

        key = getkey();
        key = toupper(key);

        switch (key) {
            case 'A':
                option_a();
                break;
            case 'B':
                option_b();
                break;
            case 'Q':
                cls();
                print("Bye!");
                delay(25);
                return;
        }
    }
}
```

### 10.4 Struct Example

```c
#include <psion.h>

struct Point {
    int x;
    int y;
};

void move_point(struct Point *p, int dx, int dy) {
    p->x = p->x + dx;
    p->y = p->y + dy;
}

void main() {
    struct Point cursor;
    char key;

    cursor.x = 10;
    cursor.y = 10;

    while (1) {
        cls();
        print("X:");
        print_int(cursor.x);
        print(" Y:");
        print_int(cursor.y);

        key = getkey();

        switch (key) {
            case 'U': move_point(&cursor, 0, -1); break;
            case 'D': move_point(&cursor, 0, 1); break;
            case 'L': move_point(&cursor, -1, 0); break;
            case 'R': move_point(&cursor, 1, 0); break;
            case 'Q': return;
        }
    }
}
```

### 10.5 String Processing

```c
#include <psion.h>
#include <stdio.h>
#include <ctype.h>

void to_upper_string(char *s) {
    while (*s) {
        *s = toupper(*s);
        s++;
    }
}

void main() {
    char buf[20];
    char *found;

    cls();

    strcpy(buf, "hello world");
    to_upper_string(buf);
    print(buf);  /* "HELLO WORLD" */

    /* Find substring */
    found = strstr(buf, "WORLD");
    if (found) {
        cursor(DISP_COLS);
        print("Found: ");
        print(found);
    }

    getkey();
}
```

---

## 11. Troubleshooting

### 11.1 Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid OPK file" | Raw OB3 used | Use `psopk create` |
| Program crashes on exit | Missing `-r` flag | Use `-r` with psasm |
| Wrong values | Stack access bug | Check calling convention |
| Garbage output | String not terminated | Add null terminator |
| 4-line not working | Missing `-m LZ` | Add `-m LZ` to both pscc and psasm |
| Immediate exit on CM/XP | Built for LZ | Build without `-m LZ` |

### 11.2 Mixed Type Errors

```c
char c = 'A';
c = c + 32;      /* ERROR: char + int */
c = c + ' ';     /* OK: char + char */
```

### 11.3 Struct Errors

```c
struct Point a, b;
a = b;           /* ERROR: use struct_copy */
struct_copy(&a, &b, sizeof(struct Point));  /* OK */
```

### 11.4 Debugging Tips

1. **Use `-v` flag** for verbose build output
2. **Use `-k` flag** to keep intermediate files
3. **Examine generated assembly** (`.asm` file)
4. **Test in emulator** before real hardware
5. **Add print statements** for tracing

### 11.5 Emulator Testing

Test programs in the SDK emulator before transferring to hardware:

```python
from psion_sdk.emulator import Emulator, EmulatorConfig

emu = Emulator(EmulatorConfig(model="XP"))
emu.load_opk("myprogram.opk", slot=0)
emu.reset()
emu.run(5_000_000)
# ... interact with emulator
```

---

## See Also

- [asm-prog.md](asm-prog.md) - Assembly Programming Manual
- [stdlib.md](stdlib.md) - Core string and character functions
- [stdio.md](stdio.md) - Extended string functions and sprintf
- [cli-tools.md](cli-tools.md) - CLI Tools Manual (psbuild, pscc, psasm, psopk, pslink, psdisasm)
- `include/psion.h` - C library header
- `include/float.h` - Floating point header
- `include/ctype.h` - Character classification header
- `examples/` - Example programs

---

*End of Small-C Programming Manual*
