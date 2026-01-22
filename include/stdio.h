/*
 * =============================================================================
 * STDIO.H - Extended String and Formatting Functions for Psion Organiser II
 * =============================================================================
 *
 * This header provides extended string functions and formatted output that
 * are not part of the core runtime. These functions are OPTIONAL - include
 * this header only if you need them.
 *
 * USAGE:
 *   #include <psion.h>
 *   #include <stdio.h>
 *
 * ASSEMBLY USAGE:
 *   When using these functions, you must also include stdio.inc in your
 *   assembly source (the compiler will do this automatically if you include
 *   stdio.h in your C source):
 *
 *     INCLUDE "psion.inc"
 *     INCLUDE "runtime.inc"
 *     INCLUDE "stdio.inc"    ; Include AFTER runtime.inc
 *
 * CODE SIZE:
 *   Including stdio.inc adds approximately 200-300 bytes to your program.
 *   Only include it if you actually need these functions.
 *
 * FUNCTIONS PROVIDED:
 *   - strrchr : Find last occurrence of character in string
 *   - strstr  : Find substring in string
 *   - strncat : Bounded string concatenation
 *   - sprintf : Formatted string output (simplified version)
 *
 * NOTE ON SPRINTF:
 *   The sprintf implementation is simplified for the Psion platform:
 *   - Supports %d, %u, %x, %c, %s, %% format specifiers
 *   - Supports width specifiers (e.g., %5d)
 *   - Does NOT support precision, floating point, or long modifiers
 *   - Maximum of 4 format arguments (due to Small-C limitations)
 *
 * Author: Hugo José Pinto & Contributors
 * Part of the Psion Organiser II SDK
 * See: specs/12-standard-library-expansion.md
 * =============================================================================
 */

#ifndef _STDIO_H
#define _STDIO_H

/* Ensure psion.h is included first for basic types */
#ifndef _PSION_H
#error "Please include <psion.h> before <stdio.h>"
#endif

/* =============================================================================
 * Extended String Functions
 * =============================================================================
 */

/*
 * strrchr - Locate last occurrence of character in string
 *
 * Searches the string s for the last occurrence of character c.
 * Unlike strchr which finds the first occurrence, strrchr finds the last.
 *
 * Parameters:
 *   s - String to search
 *   c - Character to find
 *
 * Returns:
 *   Pointer to last occurrence of c in s, or NULL (0) if not found
 *
 * Examples:
 *   strrchr("hello", 'l')   -> pointer to second 'l'
 *   strrchr("hello", 'x')   -> 0 (NULL)
 *   strrchr("/a/b/c", '/')  -> pointer to last '/'
 *
 * Common use: Finding file extension
 *   char *ext = strrchr(filename, '.');
 *   if (ext) { // ext points to ".txt" in "file.txt" }
 */
char *strrchr(char *s, int c);

/*
 * strstr - Locate substring in string
 *
 * Finds the first occurrence of the substring needle in the string haystack.
 * The search does not include the terminating null characters.
 *
 * Parameters:
 *   haystack - String to search in
 *   needle   - Substring to find
 *
 * Returns:
 *   Pointer to first occurrence of needle in haystack, or NULL if not found
 *   If needle is an empty string, returns haystack
 *
 * Examples:
 *   strstr("Hello World", "World") -> pointer to "World"
 *   strstr("Hello World", "xyz")   -> 0 (NULL)
 *   strstr("ABCABC", "BC")         -> pointer to first "BC"
 *
 * Note: Search is case-sensitive. For case-insensitive search,
 * convert both strings to same case first using toupper/tolower.
 */
char *strstr(char *haystack, char *needle);

/*
 * strncat - Concatenate strings with length limit
 *
 * Appends at most n characters from src to the end of dest, then adds
 * a null terminator. Unlike strncpy, strncat ALWAYS null-terminates.
 *
 * Parameters:
 *   dest - Destination string (must have enough space for result)
 *   src  - Source string to append
 *   n    - Maximum characters to append from src
 *
 * Returns:
 *   Pointer to dest
 *
 * Buffer requirement: dest must have room for strlen(dest) + min(n, strlen(src)) + 1
 *
 * Examples:
 *   char buf[20] = "Hello";
 *   strncat(buf, " World", 3);  // buf = "Hello Wo"
 *   strncat(buf, "!", 10);      // buf = "Hello Wo!"
 *
 * Note: The n parameter limits characters copied from src, not total dest length.
 * To limit total dest size, use: strncat(dest, src, maxlen - strlen(dest) - 1)
 */
char *strncat(char *dest, char *src, int n);

/* =============================================================================
 * Formatted Output
 * =============================================================================
 */

/*
 * sprintf - Formatted output to string buffer
 *
 * Writes formatted data to a string buffer. This is a simplified version
 * optimized for the Psion platform with limited format specifier support.
 *
 * SUPPORTED FORMAT SPECIFIERS:
 *   %d  - Signed decimal integer
 *   %u  - Unsigned decimal integer
 *   %x  - Unsigned hexadecimal (lowercase)
 *   %c  - Single character
 *   %s  - Null-terminated string
 *   %%  - Literal percent sign
 *
 * WIDTH SPECIFIERS:
 *   %5d   - Right-align in 5-character field (space-padded)
 *   %-5d  - Left-align in 5-character field
 *   %05d  - Right-align with zero padding
 *
 * NOT SUPPORTED (to minimize code size):
 *   %f, %e, %g  - Floating point (use fp_print instead)
 *   %p          - Pointer
 *   %ld, %lx    - Long integers
 *   %.Nd        - Precision specifiers
 *
 * Parameters:
 *   buf  - Destination buffer (must be large enough for result)
 *   fmt  - Format string
 *   ...  - Arguments matching format specifiers (max 4 arguments)
 *
 * Returns:
 *   Number of characters written (excluding null terminator)
 *
 * Examples:
 *   char buf[32];
 *   sprintf(buf, "Score: %d", 42);         // "Score: 42"
 *   sprintf(buf, "Hex: %x", 255);          // "Hex: ff"
 *   sprintf(buf, "Name: %s", "Bob");       // "Name: Bob"
 *   sprintf(buf, "%d + %d = %d", 1, 2, 3); // "1 + 2 = 3"
 *
 * IMPORTANT: Due to Small-C limitations, a maximum of 4 format arguments
 * are supported. Additional arguments will be ignored.
 *
 * Buffer size: Ensure buf is large enough. No bounds checking is performed.
 * As a rule of thumb, allocate at least strlen(fmt) + 10*num_args bytes.
 */
int sprintf(char *buf, char *fmt, int a1, int a2, int a3, int a4);

/*
 * sprintf0, sprintf1, sprintf2, sprintf3 - Fixed-argument sprintf variants
 *
 * These are convenience wrappers when you know the exact number of arguments.
 * They generate slightly smaller code than the full sprintf.
 *
 * Examples:
 *   sprintf0(buf, "Hello");                // No arguments
 *   sprintf1(buf, "Value: %d", 42);        // One argument
 *   sprintf2(buf, "%d + %d", 1, 2);        // Two arguments
 */
int sprintf0(char *buf, char *fmt);
int sprintf1(char *buf, char *fmt, int a1);
int sprintf2(char *buf, char *fmt, int a1, int a2);
int sprintf3(char *buf, char *fmt, int a1, int a2, int a3);

#endif /* _STDIO_H */
