# stdlib - Core String and Character Functions

**Part of the Psion Organiser II SDK**

This document describes the core string manipulation, conversion, and character classification functions provided by the SDK runtime.

---

## Overview

The SDK provides two sets of core functions:

1. **ctype.h** - Character classification and conversion macros (zero runtime overhead)
2. **Core runtime** - String and number conversion functions (always available)

These functions are part of the core runtime and do not add extra code size when included.

---

## Quick Start

### Character Classification (ctype.h)

```c
#include <psion.h>
#include <ctype.h>

void main() {
    char c;

    c = getkey();

    if (isdigit(c)) {
        print("Digit!");
    } else if (isalpha(c)) {
        print("Letter: ");
        putchar(toupper(c));
    } else if (isspace(c)) {
        print("Whitespace");
    }

    getkey();
}
```

### String and Number Conversion

```c
#include <psion.h>

void main() {
    char buf[16];
    char *found;
    int n;

    /* String to integer */
    n = atoi("  -123");  /* n = -123 */

    /* Integer to string */
    itoa(n, buf);
    print(buf);  /* prints "-123" */

    /* Find character in string */
    found = strchr("Hello", 'l');
    if (found) {
        print(found);  /* prints "llo" */
    }

    getkey();
}
```

---

## Include Order

```c
/* C programs */
#include <psion.h>
#include <ctype.h>      /* Optional - character classification */
```

```asm
; Assembly programs
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"   ; Core functions always available
```

---

## Character Classification (ctype.h)

All ctype functions are implemented as **macros** that expand to inline comparisons. This means:
- **Zero code size overhead** - no functions are linked
- **Arguments are evaluated once** - safe with side effects like `toupper(getkey())`
- **Efficient HD6303 code** - compiles to simple compare instructions

### Classification Macros

| Macro | True For | ASCII Range |
|-------|----------|-------------|
| `isdigit(c)` | Decimal digits | '0'-'9' (48-57) |
| `isupper(c)` | Uppercase letters | 'A'-'Z' (65-90) |
| `islower(c)` | Lowercase letters | 'a'-'z' (97-122) |
| `isalpha(c)` | Any letter | 'A'-'Z' or 'a'-'z' |
| `isalnum(c)` | Letter or digit | 'A'-'Z', 'a'-'z', '0'-'9' |
| `isspace(c)` | Whitespace | space, tab, newline, etc. |
| `isxdigit(c)` | Hex digit | '0'-'9', 'A'-'F', 'a'-'f' |
| `isprint(c)` | Printable (incl. space) | 32-126 |
| `isgraph(c)` | Printable (excl. space) | 33-126 |
| `ispunct(c)` | Punctuation | Printable, non-alphanumeric |
| `iscntrl(c)` | Control character | 0-31, 127 |
| `isascii(c)` | Valid ASCII | 0-127 |

### Conversion Macros

| Macro | Description |
|-------|-------------|
| `toupper(c)` | Convert lowercase to uppercase |
| `tolower(c)` | Convert uppercase to lowercase |
| `toascii(c)` | Mask to 7-bit ASCII (c & 0x7F) |

### isdigit - Test for Decimal Digit

Returns non-zero if `c` is a digit character '0' through '9'.

```c
char c = getkey();
if (isdigit(c)) {
    int value = c - '0';  /* Convert '5' to 5 */
    print_int(value);
}
```

### isupper / islower - Test for Letter Case

```c
char c = getkey();
if (isupper(c)) {
    print("Uppercase");
} else if (islower(c)) {
    print("Lowercase");
}
```

### isalpha / isalnum - Test for Letters

```c
/* Check if valid identifier start character */
if (isalpha(c) || c == '_') {
    print("Valid identifier start");
}

/* Check if valid identifier character */
if (isalnum(c) || c == '_') {
    print("Valid identifier char");
}
```

### isspace - Test for Whitespace

Returns non-zero for: space (`' '`), tab (`'\t'`), newline (`'\n'`), carriage return (`'\r'`), form feed (`'\f'`), vertical tab (`'\v'`).

```c
/* Skip leading whitespace */
char *s = "  Hello";
while (isspace(*s)) {
    s++;
}
print(s);  /* prints "Hello" */
```

### isxdigit - Test for Hexadecimal Digit

```c
/* Validate hex string */
char *hex = "1A2F";
char *p = hex;
while (isxdigit(*p)) {
    p++;
}
if (*p == 0) {
    print("Valid hex");
}
```

### isprint / isgraph - Test for Printable

```c
/* isprint includes space, isgraph excludes it */
char c = ' ';
if (isprint(c)) print("Printable");     /* True */
if (isgraph(c)) print("Has graphic");   /* False (space has no graphic) */

c = 'A';
if (isprint(c)) print("Printable");     /* True */
if (isgraph(c)) print("Has graphic");   /* True */
```

### toupper / tolower - Case Conversion

Returns the converted character, or the original if no conversion applies.

```c
char c = 'h';
putchar(toupper(c));  /* prints 'H' */

c = '5';
putchar(toupper(c));  /* prints '5' (unchanged) */

/* Convert string to uppercase */
char *s = buf;
while (*s) {
    *s = toupper(*s);
    s++;
}
```

### toascii - Mask to 7-bit

Clears the high bit, ensuring the result is in range 0-127.

```c
char c = 0xC1;        /* High bit set */
c = toascii(c);       /* c = 0x41 = 'A' */
```

---

## String Functions

### atoi - String to Integer

Converts a string to an integer, skipping leading whitespace and handling optional sign.

**C Declaration:**
```c
int atoi(char *s);
```

**Parameters:**
- `s` - Pointer to null-terminated string

**Returns:**
- Integer value parsed from string
- 0 if string contains no valid digits

**Behavior:**
1. Skips leading whitespace (space, tab)
2. Handles optional '+' or '-' sign
3. Converts consecutive digits
4. Stops at first non-digit character

**Examples:**
```c
int n;

n = atoi("42");       /* n = 42 */
n = atoi("  -123");   /* n = -123 */
n = atoi("+456");     /* n = 456 */
n = atoi("12abc");    /* n = 12 (stops at 'a') */
n = atoi("abc");      /* n = 0 (no digits) */
n = atoi("");         /* n = 0 */
```

**Assembly Usage:**
```asm
        ; atoi("123")
        LDD     #str_123        ; Pointer to string
        PSHB
        PSHA
        JSR     _atoi
        INS
        INS
        ; D = 123
```

---

### itoa - Integer to String

Converts an integer to its string representation.

**C Declaration:**
```c
char *itoa(int n, char *buf);
```

**Parameters:**
- `n` - Integer to convert
- `buf` - Destination buffer (must be at least 7 bytes for "-32768\0")

**Returns:**
- Pointer to `buf`

**Examples:**
```c
char buf[8];

itoa(42, buf);        /* buf = "42" */
itoa(-123, buf);      /* buf = "-123" */
itoa(0, buf);         /* buf = "0" */
itoa(-32768, buf);    /* buf = "-32768" */
```

**Buffer Size:**
- Maximum output: "-32768" (7 characters including null)
- Always allocate at least 7 bytes

**Assembly Usage:**
```asm
        ; itoa(n, buf)
        LDD     #buffer         ; buf pointer
        PSHB
        PSHA
        LDD     value           ; n
        PSHB
        PSHA
        JSR     _itoa
        INS
        INS
        INS
        INS
        ; D = pointer to buffer
```

---

### strchr - Find Character in String

Searches a string for the **first** occurrence of a character.

**C Declaration:**
```c
char *strchr(char *s, int c);
```

**Parameters:**
- `s` - Pointer to null-terminated string
- `c` - Character to find (only low byte used)

**Returns:**
- Pointer to first occurrence of `c` in `s`
- `0` (NULL) if character not found

**Note:** If searching for the null terminator (`'\0'`), returns pointer to the end of string.

**Examples:**
```c
char *s = "Hello World";
char *found;

found = strchr(s, 'o');
if (found) {
    print(found);  /* prints "o World" */
}

found = strchr(s, 'x');
if (!found) {
    print("Not found");
}

/* Find null terminator */
found = strchr(s, '\0');
/* found points to the terminating null */
```

**Assembly Usage:**
```asm
        ; strchr(s, c)
        LDD     #'/'            ; Character to find
        PSHB
        PSHA
        LDD     #path_str       ; String to search
        PSHB
        PSHA
        JSR     _strchr
        INS
        INS
        INS
        INS
        ; D = pointer or 0
        CPD     #0
        BEQ     not_found
```

**See Also:** `strrchr` in stdio.h finds the **last** occurrence.

---

### strncpy - Bounded String Copy

Copies at most `n` characters from source to destination.

**C Declaration:**
```c
char *strncpy(char *dest, char *src, int n);
```

**Parameters:**
- `dest` - Destination buffer
- `src` - Source string
- `n` - Maximum characters to copy

**Returns:**
- Pointer to `dest`

**Important Behavior:**
- If `src` is shorter than `n`, `dest` is padded with null characters
- If `src` is `n` or more characters, `dest` is **NOT** null-terminated
- Always manually null-terminate if needed: `dest[n-1] = '\0';`

**Examples:**
```c
char buf[10];

/* Normal copy - fits with null */
strncpy(buf, "Hello", 10);
/* buf = "Hello\0\0\0\0\0" (null-padded) */

/* Truncated copy - no null terminator! */
strncpy(buf, "Hello World", 5);
/* buf = "Hello" (NO null terminator) */
buf[5] = '\0';  /* Must add manually! */

/* Safe pattern */
strncpy(buf, src, sizeof(buf) - 1);
buf[sizeof(buf) - 1] = '\0';
```

**Assembly Usage:**
```asm
        ; strncpy(dest, src, n)
        LDD     #10             ; n
        PSHB
        PSHA
        LDD     #src_str        ; src
        PSHB
        PSHA
        LDD     #dest_buf       ; dest
        PSHB
        PSHA
        JSR     _strncpy
        INS
        INS
        INS
        INS
        INS
        INS
        ; D = dest_buf
```

---

### strncmp - Bounded String Comparison

Compares at most `n` characters of two strings.

**C Declaration:**
```c
int strncmp(char *s1, char *s2, int n);
```

**Parameters:**
- `s1` - First string
- `s2` - Second string
- `n` - Maximum characters to compare

**Returns:**
- `0` if strings are equal (up to `n` characters)
- Negative if `s1` < `s2`
- Positive if `s1` > `s2`

**Examples:**
```c
int result;

/* Equal strings */
result = strncmp("Hello", "Hello", 5);  /* result = 0 */

/* Prefix match */
result = strncmp("Hello", "Help", 3);   /* result = 0 (first 3 match) */
result = strncmp("Hello", "Help", 4);   /* result < 0 ('l' < 'p') */

/* Case sensitive */
result = strncmp("ABC", "abc", 3);      /* result < 0 ('A' < 'a') */
```

**Common Patterns:**
```c
/* Check for command prefix */
if (strncmp(input, "quit", 4) == 0) {
    /* Input starts with "quit" */
}

/* Case-insensitive compare (manual) */
char a[16], b[16];
/* Convert both to same case first */
for (int i = 0; i < 16 && a[i]; i++) a[i] = toupper(a[i]);
for (int i = 0; i < 16 && b[i]; i++) b[i] = toupper(b[i]);
if (strncmp(a, b, 16) == 0) { ... }
```

**Assembly Usage:**
```asm
        ; strncmp(s1, s2, n)
        LDD     #5              ; n
        PSHB
        PSHA
        LDD     #str2           ; s2
        PSHB
        PSHA
        LDD     #str1           ; s1
        PSHB
        PSHA
        JSR     _strncmp
        INS
        INS
        INS
        INS
        INS
        INS
        ; D = comparison result
        TSTB
        BEQ     strings_equal
        BMI     s1_less
        ; else s1 greater
```

---

## Stack Layout Reference

For assembly programmers calling functions directly:

**atoi(s):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [s        2B] offset 4-5
```

**itoa(n, buf):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [n        2B] offset 4-5
  [buf      2B] offset 6-7
```

**strchr(s, c):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [s        2B] offset 4-5
  [c        2B] offset 6-7 (char in low byte at 7)
```

**strncpy(dest, src, n):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [dest     2B] offset 4-5
  [src      2B] offset 6-7
  [n        2B] offset 8-9
```

**strncmp(s1, s2, n):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [s1       2B] offset 4-5
  [s2       2B] offset 6-7
  [n        2B] offset 8-9
```

---

## Summary Tables

### ctype.h Macros

| Macro | Returns True For | Example |
|-------|------------------|---------|
| `isdigit(c)` | '0'-'9' | `isdigit('5')` → true |
| `isupper(c)` | 'A'-'Z' | `isupper('X')` → true |
| `islower(c)` | 'a'-'z' | `islower('x')` → true |
| `isalpha(c)` | letters | `isalpha('A')` → true |
| `isalnum(c)` | letters, digits | `isalnum('9')` → true |
| `isspace(c)` | whitespace | `isspace(' ')` → true |
| `isxdigit(c)` | hex digits | `isxdigit('F')` → true |
| `isprint(c)` | printable | `isprint(' ')` → true |
| `isgraph(c)` | graphic | `isgraph(' ')` → false |
| `ispunct(c)` | punctuation | `ispunct('!')` → true |
| `iscntrl(c)` | control chars | `iscntrl('\n')` → true |
| `toupper(c)` | uppercase | `toupper('a')` → 'A' |
| `tolower(c)` | lowercase | `tolower('A')` → 'a' |

### Core Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `atoi(s)` | String to int | Parsed integer |
| `itoa(n, buf)` | Int to string | Pointer to buf |
| `strchr(s, c)` | Find first char | Pointer or NULL |
| `strncpy(d, s, n)` | Bounded copy | Pointer to dest |
| `strncmp(s1, s2, n)` | Bounded compare | <0, 0, or >0 |

---

## Assembly Macros Reference

The runtime library provides assembly convenience macros that handle stack setup and cleanup automatically. All macros leave the result in D register and may clobber A, B, X, and flags.

### Display Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `CLS` | - | Clear screen |
| `CURSOR` | position | Set cursor position (0-31 or 0-79) |
| `AT` | row, col | Set cursor by row and column |
| `PRINT` | string | Print null-terminated string |
| `PRINT_INT` | value | Print signed integer |
| `PRINT_UINT` | value | Print unsigned integer |
| `PRINT_HEX` | value | Print as 4 hex digits |
| `PUTCHAR` | char | Output single character |

### Input Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `GETKEY` | - | Wait for keypress, D = key code |
| `TESTKEY` | - | Non-blocking key test (50ms poll), D = key or 0 |
| `KBHIT` | - | Check if key in buffer, D = 1 or 0 |
| `FLUSHKB` | - | Flush keyboard buffer |

### Sound Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `BEEP` | - | Sound a beep |
| `ALARM` | - | Sound alarm pattern |
| `TONE` | pitch, duration | Custom tone (pitch divisor, 1/32 sec) |

### Timing Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `DELAY` | ticks | Wait for ticks (1/32 sec each) |
| `GETTICKS` | - | Get system tick counter, D = count |

### Math Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `ABS` | value | Absolute value, D = \|value\| |
| `MIN` | a, b | Minimum, D = min(a, b) |
| `MAX` | a, b | Maximum, D = max(a, b) |

### String Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `STRLEN` | string | String length, D = length |
| `STRCPY` | dest, src | Copy string, D = dest |
| `STRCMP` | s1, s2 | Compare strings, D = result |
| `STRCAT` | dest, src | Concatenate, D = dest |
| `STRCHR` | string, char | Find char, D = ptr or 0 |
| `STRNCPY` | dest, src, n | Bounded copy, D = dest |
| `STRNCMP` | s1, s2, n | Bounded compare, D = result |

### Memory Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `MEMCPY` | dest, src, n | Copy n bytes, D = dest |
| `MEMSET` | dest, byte, n | Fill n bytes, D = dest |
| `MEMCMP` | a, b, n | Compare n bytes, D = result |

### Conversion Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `ATOI` | string | String to integer, D = value |
| `ITOA` | value, buffer | Integer to string, D = buffer |

### Graphics Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `UDG_DEFINE` | char_num, data | Define UDG character (0-7) |

### System Macros

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `GETTIME` | buffer | Get RTC time (6 BCD bytes) |

### LZ-Only Macros

These macros are for LZ/LZ64 4-line display machines only:

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `SETMODE` | mode | Set display mode (0=2-line, 1=4-line) |
| `GETMODE` | - | Get display mode, D = mode |
| `PUSHMODE` | - | Save current display mode |
| `POPMODE` | - | Restore saved display mode |

---

### Macro Examples

**Display example:**
```asm
        CLS                     ; Clear screen
        CURSOR  0               ; Home position
        PRINT   hello_msg       ; Print string
        AT      1, 5            ; Row 1, column 5
        PRINT_INT score         ; Print integer
        ...
hello_msg:
        FCC     "Hello!"
        FCB     0
score:  FDB     1234
```

**Input example:**
```asm
wait_loop:
        TESTKEY                 ; Check for key (non-blocking)
        TSTB
        BEQ     wait_loop       ; No key, keep waiting
        ; D = key code
        CMPB    #'Q'
        BEQ     quit
```

**String example:**
```asm
        STRCPY  dest, src       ; Copy string
        STRCAT  dest, suffix    ; Append suffix
        STRLEN  dest            ; Get length
        STD     len             ; D = length
        ...
dest:   RMB     32
src:    FCC     "Hello"
        FCB     0
suffix: FCC     " World"
        FCB     0
len:    RMB     2
```

**Memory example:**
```asm
        MEMSET  buffer, 0, 64   ; Clear 64 bytes
        MEMCPY  dest, src, 20   ; Copy 20 bytes
        MEMCMP  a, b, 10        ; Compare 10 bytes
        TSTB
        BEQ     equal           ; D = 0 means equal
```

**Conversion example:**
```asm
        ATOI    num_str         ; Parse "123" -> D = 123
        STD     value
        ; Later...
        ITOA    value, buf      ; Convert back to string
        PRINT   buf             ; Print the string
        ...
num_str: FCC    "123"
         FCB    0
value:   RMB    2
buf:     RMB    8
```

---

## See Also

- [small-c-prog.md](small-c-prog.md) - Small-C Programming Manual (comprehensive guide)
- [stdio.md](stdio.md) - Extended string functions (strrchr, strstr, strncat, sprintf)
- [cli-tools.md](cli-tools.md) - CLI Tools Manual (psbuild, pscc, psasm, psopk, pslink, psdisasm)
- `include/ctype.h` - Character classification header
- `include/runtime.inc` - Core runtime implementation
