# stdio.h - Extended String and Formatting Functions

**Part of the Psion Organiser II SDK**

This document describes the optional extended string functions and formatted output capabilities provided by `stdio.h` and `stdio.inc`.

---

## Overview

The stdio module provides additional string manipulation and formatting functions beyond the core runtime. These are **optional** - include them only when needed to minimize code size.

**Code Size Impact:** ~300-350 bytes when included

---

## Quick Start

### For C Programmers

```c
#include <psion.h>
#include <stdio.h>

void main() {
    char buf[32];
    char *ext;

    /* Format a string */
    sprintf1(buf, "Score: %d", 42);
    print(buf);

    /* Find file extension */
    ext = strrchr("readme.txt", '.');
    if (ext) {
        print(ext);  /* prints ".txt" */
    }

    getkey();
}
```

### For Assembly Programmers

```asm
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"
        INCLUDE "stdio.inc"

        ; Using macros (recommended)
        STRRCHR MY_PATH, '/'
        ; D = pointer to last '/' or 0

        ; Using functions directly
        LDD     #'/'
        PSHB
        PSHA
        LDD     #MY_PATH
        PSHB
        PSHA
        JSR     _strrchr
        INS
        INS
        INS
        INS
        ; D = result
```

---

## Include Order

The stdio module must be included after the core runtime:

```c
/* C programs */
#include <psion.h>
#include <stdio.h>      /* Optional - include if needed */
```

```asm
; Assembly programs
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"
        INCLUDE "stdio.inc"     ; Optional - include if needed
```

---

## Functions

### strrchr - Find Last Occurrence of Character

Searches a string for the **last** occurrence of a character.

**C Declaration:**
```c
char *strrchr(char *s, int c);
```

**Parameters:**
- `s` - Pointer to null-terminated string to search
- `c` - Character to find (only low byte is used)

**Returns:**
- Pointer to last occurrence of `c` in `s`
- `0` (NULL) if character not found

**Example - Extract filename from path:**
```c
char *path = "/home/user/file.txt";
char *filename;

filename = strrchr(path, '/');
if (filename) {
    filename++;  /* Skip the '/' */
    print(filename);  /* prints "file.txt" */
}
```

**Example - Get file extension:**
```c
char *file = "document.txt";
char *ext;

ext = strrchr(file, '.');
if (ext) {
    print(ext);  /* prints ".txt" */
} else {
    print("No extension");
}
```

**Assembly Usage:**
```asm
        ; Using macro
        STRRCHR path_string, '/'
        CPD     #0
        BEQ     not_found
        ; D = pointer to last '/'

        ; Using function directly
        LDD     #'/'            ; Character to find
        PSHB
        PSHA
        LDD     #path_string    ; String to search
        PSHB
        PSHA
        JSR     _strrchr
        INS
        INS
        INS
        INS
        ; D = result (pointer or 0)
```

---

### strstr - Find Substring

Finds the first occurrence of a substring within a string.

**C Declaration:**
```c
char *strstr(char *haystack, char *needle);
```

**Parameters:**
- `haystack` - String to search in
- `needle` - Substring to find

**Returns:**
- Pointer to first occurrence of `needle` in `haystack`
- `0` (NULL) if substring not found
- If `needle` is empty, returns `haystack`

**Example - Search for keyword:**
```c
char *text = "Hello World";
char *found;

found = strstr(text, "World");
if (found) {
    print("Found: ");
    print(found);  /* prints "World" */
}
```

**Example - Check for substring:**
```c
char *email = "user@example.com";

if (strstr(email, "@")) {
    print("Valid email format");
} else {
    print("Missing @ symbol");
}
```

**Assembly Usage:**
```asm
        ; Using macro
        STRSTR haystack, needle
        CPD     #0
        BEQ     not_found
        ; D = pointer to match

        ; Using function directly
        LDD     #needle_str     ; Substring to find
        PSHB
        PSHA
        LDD     #haystack_str   ; String to search
        PSHB
        PSHA
        JSR     _strstr
        INS
        INS
        INS
        INS
```

---

### strncat - Bounded String Concatenation

Appends at most `n` characters from source to destination, plus a null terminator.

**C Declaration:**
```c
char *strncat(char *dest, char *src, int n);
```

**Parameters:**
- `dest` - Destination string (must have sufficient space)
- `src` - Source string to append
- `n` - Maximum characters to append (excluding null terminator)

**Returns:**
- Pointer to `dest`

**Important:** Unlike `strncpy`, `strncat` **always** adds a null terminator. Ensure `dest` has room for `strlen(dest) + n + 1` characters.

**Example - Safe concatenation:**
```c
char buf[20];

strcpy(buf, "Hello");
strncat(buf, " World!", 3);  /* Appends " Wo" */
print(buf);  /* prints "Hello Wo" */
```

**Example - Building a path:**
```c
char path[32];

strcpy(path, "/home/");
strncat(path, username, 8);  /* Max 8 chars of username */
strncat(path, "/", 1);
strncat(path, filename, 12);
```

**Assembly Usage:**
```asm
        ; Using macro
        STRNCAT dest_buf, src_str, 5
        ; D = dest_buf

        ; Using function directly
        LDD     #5              ; Max chars to append
        PSHB
        PSHA
        LDD     #src_str        ; Source string
        PSHB
        PSHA
        LDD     #dest_buf       ; Destination
        PSHB
        PSHA
        JSR     _strncat
        INS
        INS
        INS
        INS
        INS
        INS
```

---

### sprintf - Formatted String Output

Writes formatted data to a string buffer. Multiple variants are provided based on argument count.

**C Declarations:**
```c
int sprintf0(char *buf, char *fmt);
int sprintf1(char *buf, char *fmt, int a1);
int sprintf2(char *buf, char *fmt, int a1, int a2);
int sprintf3(char *buf, char *fmt, int a1, int a2, int a3);
```

**Parameters:**
- `buf` - Destination buffer (must be large enough for output)
- `fmt` - Format string
- `a1`, `a2`, `a3` - Arguments matching format specifiers

**Returns:**
- Number of characters written (excluding null terminator)

**Supported Format Specifiers:**

| Specifier | Description | Example |
|-----------|-------------|---------|
| `%d` | Signed decimal integer | `-42`, `123` |
| `%u` | Unsigned decimal integer | `42`, `65535` |
| `%x` | Hexadecimal (lowercase) | `2a`, `ffff` |
| `%c` | Single character | `A`, `5` |
| `%s` | String | `hello` |
| `%%` | Literal percent sign | `%` |

**Example - Basic formatting:**
```c
char buf[32];

sprintf1(buf, "Value: %d", 42);
print(buf);  /* prints "Value: 42" */

sprintf2(buf, "%d + %d", 10, 20);
print(buf);  /* prints "10 + 20" */
```

**Example - Multiple types:**
```c
char buf[40];
int score = 1500;
char grade = 'A';

sprintf2(buf, "Score: %d Grade: %c", score, grade);
print(buf);  /* prints "Score: 1500 Grade: A" */
```

**Example - Hexadecimal:**
```c
char buf[16];
int addr = 0x1234;

sprintf1(buf, "Addr: %x", addr);
print(buf);  /* prints "Addr: 1234" */
```

**Buffer Size Guidelines:**
- `%d` needs up to 7 characters (`-32768` plus null)
- `%u` needs up to 6 characters (`65535` plus null)
- `%x` needs up to 5 characters (`ffff` plus null)
- `%s` needs length of string plus null
- Always allocate extra space for safety

**Assembly Usage:**
```asm
        ; Using macro (for 1 argument)
        SPRINTF1 buffer, format, value

        ; Using function directly
        ; Push args RIGHT-TO-LEFT: a4, a3, a2, a1, fmt, buf
        LDD     #0              ; a4 (unused)
        PSHB
        PSHA
        LDD     #0              ; a3 (unused)
        PSHB
        PSHA
        LDD     #0              ; a2 (unused)
        PSHB
        PSHA
        LDD     my_value        ; a1
        PSHB
        PSHA
        LDD     #format_str     ; fmt
        PSHB
        PSHA
        LDD     #buffer         ; buf
        PSHB
        PSHA
        JSR     _sprintf
        ; Clean up 12 bytes
        LDX     #12
clean:  INS
        DEX
        BNE     clean
```

---

## Assembly Macros Reference

The following macros are available for assembly programmers:

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `STRRCHR` | string, char | Find last occurrence of char |
| `STRSTR` | haystack, needle | Find substring |
| `STRNCAT` | dest, src, n | Bounded concatenation |
| `SPRINTF1` | buf, fmt, a1 | Format with 1 argument |
| `SPRINTF2` | buf, fmt, a1, a2 | Format with 2 arguments |

All macros:
- Leave result in D register
- May clobber A, B, and flags
- Handle stack cleanup automatically

---

## Stack Layout Reference

For assembly programmers calling functions directly:

**strrchr(s, c):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [s        2B] offset 4-5
  [c        2B] offset 6-7 (char in low byte at 7)
```

**strstr(haystack, needle):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [haystack 2B] offset 4-5
  [needle   2B] offset 6-7
```

**strncat(dest, src, n):**
```
Stack after PSHX+TSX:
  [saved_X 2B] offset 0-1
  [ret addr 2B] offset 2-3
  [dest    2B] offset 4-5
  [src     2B] offset 6-7
  [n       2B] offset 8-9
```

**sprintf(buf, fmt, a1, a2, a3, a4):**
```
Stack after PSHX+TSX:
  [saved_X 2B] offset 0-1
  [ret addr 2B] offset 2-3
  [buf     2B] offset 4-5
  [fmt     2B] offset 6-7
  [a1      2B] offset 8-9
  [a2      2B] offset 10-11
  [a3      2B] offset 12-13
  [a4      2B] offset 14-15
```

---

## Limitations

1. **sprintf argument limit:** Maximum 4 format arguments (use multiple calls if needed)
2. **No width specifiers:** `%5d`, `%-5d`, `%05d` are not supported
3. **No precision:** `%.2f` is not supported
4. **No floating point:** Use `fp_print()` from float.h instead
5. **Buffer overflow:** No bounds checking - ensure buffers are large enough

---

## Code Size

| Function | Approximate Size |
|----------|-----------------|
| strrchr | ~35 bytes |
| strstr | ~70 bytes |
| strncat | ~55 bytes |
| sprintf (core) | ~150 bytes |
| sprintf wrappers | ~100 bytes |
| **Total** | **~350 bytes** |

---

## See Also

- [small-c-prog.md](small-c-prog.md) - Small-C Programming Manual (comprehensive guide)
- [stdlib.md](stdlib.md) - Core string functions and character classification
- [cli-tools.md](cli-tools.md) - CLI Tools Manual (psbuild, pscc, psasm, psopk, pslink, psdisasm)
- `include/stdio.h` - C header file
- `include/stdio.inc` - Assembly implementation
