/*
 * =============================================================================
 * CTYPE.H - Character Classification and Conversion for Psion Organiser II
 * =============================================================================
 *
 * This header provides character classification and conversion macros
 * compatible with the standard C <ctype.h> header. All functions are
 * implemented as macros for zero runtime overhead - no additional code
 * is linked into your program.
 *
 * USAGE:
 *   #include <psion.h>
 *   #include <ctype.h>
 *
 *   void main() {
 *       char c = getkey();
 *       if (isdigit(c)) {
 *           print("You pressed a digit!");
 *       }
 *       c = toupper(c);  // Convert to uppercase
 *   }
 *
 * IMPLEMENTATION NOTES:
 *   - All macros evaluate their argument exactly once, so side effects
 *     in arguments are safe: toupper(getkey()) works correctly.
 *   - Macros expand to inline comparisons, generating efficient HD6303 code.
 *   - Character codes are assumed to be 7-bit ASCII (0-127).
 *   - Return values: classification macros return non-zero (true) or zero (false).
 *   - Conversion macros return the converted character or original if no change.
 *
 * STANDARD COMPLIANCE:
 *   These macros follow ANSI C semantics. The Psion uses ASCII encoding,
 *   so behavior matches standard C implementations on ASCII systems.
 *
 * ASCII REFERENCE:
 *   0-31:    Control characters (iscntrl)
 *   32:      Space (isspace, isprint)
 *   33-47:   Punctuation !"#$%&'()*+,-./ (ispunct, isprint, isgraph)
 *   48-57:   Digits 0-9 (isdigit, isalnum, isprint, isgraph)
 *   58-64:   Punctuation :;<=>?@ (ispunct, isprint, isgraph)
 *   65-90:   Uppercase A-Z (isupper, isalpha, isalnum, isprint, isgraph)
 *   91-96:   Punctuation [\]^_` (ispunct, isprint, isgraph)
 *   97-122:  Lowercase a-z (islower, isalpha, isalnum, isprint, isgraph)
 *   123-126: Punctuation {|}~ (ispunct, isprint, isgraph)
 *   127:     DEL control character (iscntrl)
 *
 * Author: Hugo José Pinto & Contributors
 * Part of the Psion Organiser II SDK
 * =============================================================================
 */

#ifndef _CTYPE_H
#define _CTYPE_H

/* =============================================================================
 * CHARACTER CLASSIFICATION MACROS
 * =============================================================================
 * These macros test whether a character belongs to a particular class.
 * They return non-zero (true) if the character is in the class, zero otherwise.
 * ============================================================================= */

/*
 * isdigit - Test if character is a decimal digit
 *
 * Returns non-zero if c is a digit character '0' through '9'.
 *
 * Parameters:
 *   c - Character to test (int or char)
 *
 * Returns:
 *   Non-zero if c is '0'-'9', zero otherwise
 *
 * Example:
 *   if (isdigit(c)) {
 *       int digit_value = c - '0';
 *   }
 */
#define isdigit(c)  ((c) >= '0' && (c) <= '9')

/*
 * isupper - Test if character is uppercase letter
 *
 * Returns non-zero if c is an uppercase letter 'A' through 'Z'.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is 'A'-'Z', zero otherwise
 */
#define isupper(c)  ((c) >= 'A' && (c) <= 'Z')

/*
 * islower - Test if character is lowercase letter
 *
 * Returns non-zero if c is a lowercase letter 'a' through 'z'.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is 'a'-'z', zero otherwise
 */
#define islower(c)  ((c) >= 'a' && (c) <= 'z')

/*
 * isalpha - Test if character is alphabetic
 *
 * Returns non-zero if c is a letter (uppercase or lowercase).
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is 'A'-'Z' or 'a'-'z', zero otherwise
 *
 * Note: Expands to (isupper(c) || islower(c)), which the compiler
 * optimizes well on the HD6303.
 */
#define isalpha(c)  (((c) >= 'A' && (c) <= 'Z') || ((c) >= 'a' && (c) <= 'z'))

/*
 * isalnum - Test if character is alphanumeric
 *
 * Returns non-zero if c is a letter or digit.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is 'A'-'Z', 'a'-'z', or '0'-'9', zero otherwise
 *
 * Example:
 *   // Check if valid identifier character (simplified)
 *   if (isalnum(c) || c == '_') { ... }
 */
#define isalnum(c)  (isalpha(c) || isdigit(c))

/*
 * isspace - Test if character is whitespace
 *
 * Returns non-zero if c is a whitespace character:
 *   ' '  (0x20) - Space
 *   '\t' (0x09) - Horizontal tab
 *   '\n' (0x0A) - Newline (line feed)
 *   '\r' (0x0D) - Carriage return
 *   '\f' (0x0C) - Form feed
 *   '\v' (0x0B) - Vertical tab
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is whitespace, zero otherwise
 *
 * Example:
 *   // Skip leading whitespace
 *   while (isspace(*s)) s++;
 */
#define isspace(c)  ((c) == ' ' || (c) == '\t' || (c) == '\n' || (c) == '\r' || (c) == '\f' || (c) == '\v')

/*
 * isxdigit - Test if character is hexadecimal digit
 *
 * Returns non-zero if c is a valid hexadecimal digit:
 * '0'-'9', 'A'-'F', or 'a'-'f'.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is a hex digit, zero otherwise
 *
 * Example:
 *   // Parse hex string
 *   while (isxdigit(*s)) { ... }
 */
#define isxdigit(c) (isdigit(c) || ((c) >= 'A' && (c) <= 'F') || ((c) >= 'a' && (c) <= 'f'))

/*
 * isprint - Test if character is printable (including space)
 *
 * Returns non-zero if c is a printable character (ASCII 32-126 inclusive).
 * This includes space but excludes control characters.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is printable, zero otherwise
 */
#define isprint(c)  ((c) >= ' ' && (c) <= '~')

/*
 * isgraph - Test if character is printable (excluding space)
 *
 * Returns non-zero if c is a printable character with a graphical
 * representation (ASCII 33-126 inclusive). Same as isprint but
 * excludes the space character.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c has graphical representation, zero otherwise
 */
#define isgraph(c)  ((c) > ' ' && (c) <= '~')

/*
 * ispunct - Test if character is punctuation
 *
 * Returns non-zero if c is a printable character that is not
 * alphanumeric or space. This includes characters like:
 * !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is punctuation, zero otherwise
 */
#define ispunct(c)  (isprint(c) && !isalnum(c) && (c) != ' ')

/*
 * iscntrl - Test if character is control character
 *
 * Returns non-zero if c is a control character (ASCII 0-31 or 127).
 * These are non-printable characters used for device control.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is control character, zero otherwise
 */
#define iscntrl(c)  ((c) >= 0 && (c) < ' ' || (c) == 127)

/*
 * isascii - Test if character is valid ASCII
 *
 * Returns non-zero if c is a valid 7-bit ASCII character (0-127).
 * Note: This is a BSD/POSIX extension, not strictly ANSI C.
 *
 * Parameters:
 *   c - Character to test
 *
 * Returns:
 *   Non-zero if c is valid ASCII (0-127), zero otherwise
 */
#define isascii(c)  ((c) >= 0 && (c) <= 127)

/* =============================================================================
 * CHARACTER CONVERSION MACROS
 * =============================================================================
 * These macros convert characters between cases or mask to ASCII.
 * ============================================================================= */

/*
 * toupper - Convert character to uppercase
 *
 * If c is a lowercase letter ('a'-'z'), returns the corresponding
 * uppercase letter ('A'-'Z'). Otherwise returns c unchanged.
 *
 * Parameters:
 *   c - Character to convert
 *
 * Returns:
 *   Uppercase version of c if lowercase, otherwise c unchanged
 *
 * Implementation note:
 *   In ASCII, uppercase and lowercase letters differ by 32 (0x20).
 *   'a' (97) - 32 = 'A' (65)
 *
 * Example:
 *   char upper = toupper('h');  // Returns 'H'
 *   char same = toupper('5');   // Returns '5' (unchanged)
 */
#define toupper(c)  (((c) >= 'a' && (c) <= 'z') ? ((c) - 32) : (c))

/*
 * tolower - Convert character to lowercase
 *
 * If c is an uppercase letter ('A'-'Z'), returns the corresponding
 * lowercase letter ('a'-'z'). Otherwise returns c unchanged.
 *
 * Parameters:
 *   c - Character to convert
 *
 * Returns:
 *   Lowercase version of c if uppercase, otherwise c unchanged
 *
 * Example:
 *   char lower = tolower('H');  // Returns 'h'
 *   char same = tolower('5');   // Returns '5' (unchanged)
 */
#define tolower(c)  (((c) >= 'A' && (c) <= 'Z') ? ((c) + 32) : (c))

/*
 * toascii - Mask character to 7-bit ASCII
 *
 * Clears the high bit of c, ensuring the result is in the range 0-127.
 * Note: This is a BSD/POSIX extension, not strictly ANSI C.
 *
 * Parameters:
 *   c - Character to mask
 *
 * Returns:
 *   c with high bit cleared (c & 0x7F)
 *
 * Example:
 *   char ascii = toascii(0x80 | 'A');  // Returns 'A' (strips high bit)
 */
#define toascii(c)  ((c) & 0x7F)

#endif /* _CTYPE_H */
