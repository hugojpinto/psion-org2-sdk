/*
 * =============================================================================
 * Psion Organiser II Small-C Library Header
 * =============================================================================
 *
 * This header provides function declarations for the Psion-specific
 * library functions available to Small-C programs.
 *
 * Functions are organized into categories:
 *   - Display: Screen output and control
 *   - Keyboard: Key input
 *   - Sound: Beep and tone generation
 *   - Time: Timing and delays
 *   - Files: File I/O (limited)
 *   - Memory: Memory operations
 *   - String: String manipulation
 *
 * Usage:
 *   #include <psion.h>
 *
 * Note: These functions wrap Psion system calls via SWI instructions.
 * The actual implementation is in the runtime library (runtime.inc).
 *
 * Author: Hugo José Pinto & Contributors
 * =============================================================================
 */

#ifndef _PSION_H
#define _PSION_H

/* Target identification - always defined */
#define __PSION__ 1

/* =============================================================================
 * Model-Specific Macros
 * =============================================================================
 *
 * These macros are automatically defined by the compiler based on the target
 * model specified via #pragma psion model or the -m CLI flag:
 *
 *   __PSION_CM__    - Defined when targeting CM model (2x16 display)
 *   __PSION_XP__    - Defined when targeting XP model (2x16 display)
 *   __PSION_LA__    - Defined when targeting LA model (4x20 display)
 *   __PSION_LZ__    - Defined when targeting LZ model (4x20 display)
 *   __PSION_LZ64__  - Defined when targeting LZ64 model (4x20 display)
 *
 *   __PSION_2LINE__ - Defined when targeting 2-line display models (CM, XP)
 *   __PSION_4LINE__ - Defined when targeting 4-line display models (LA, LZ, LZ64)
 *
 *   DISP_ROWS       - Number of display rows (2 or 4)
 *   DISP_COLS       - Number of display columns (16 or 20)
 *
 * Example usage:
 *   #pragma psion model LZ
 *
 *   void show_status() {
 *     #ifdef __PSION_4LINE__
 *       print_at(0, 3, "4-line mode");
 *     #else
 *       print_at(0, 1, "2-line");
 *     #endif
 *   }
 *
 * Note: If no model is specified, the default is XP (2x16 display).
 * =============================================================================
 */

/* Display dimensions - defined by compiler based on target model */
#ifndef DISP_ROWS
  #ifdef __PSION_4LINE__
    #define DISP_ROWS 4
    #define DISP_COLS 20
  #else
    #define DISP_ROWS 2
    #define DISP_COLS 16
  #endif
#endif

/* Total display buffer size (cells) */
#define DISP_SIZE (DISP_ROWS * DISP_COLS)

/* =============================================================================
 * Display Functions
 * =============================================================================
 */

/*
 * cls - Clear the display screen
 *
 * Clears all characters from the display and moves the cursor
 * to the home position (top-left).
 */
void cls(void);

/*
 * print - Display a string
 *
 * Prints a null-terminated string at the current cursor position.
 * The string is automatically converted to Psion's LBC format.
 *
 * Parameters:
 *   s - Pointer to null-terminated string
 */
void print(char *s);

/*
 * putchar - Display a single character
 *
 * Outputs one character at the current cursor position and
 * advances the cursor.
 *
 * Parameters:
 *   c - Character to display (ASCII code)
 */
void putchar(char c);

/*
 * cursor - Set cursor position
 *
 * Moves the cursor to the specified position. Position 0 is
 * top-left, positions increase left-to-right, top-to-bottom.
 *
 * For 2x16 display: 0-15 (top row), 16-31 (bottom row)
 * For 4x20 display: 0-19 (row 0), 20-39 (row 1), etc.
 *
 * Parameters:
 *   pos - Cursor position (0-31 for 2x16, 0-79 for 4x20)
 */
void cursor(int pos);

/*
 * at - Print string at specified position
 *
 * Combines cursor() and print() for convenience.
 *
 * Parameters:
 *   pos - Cursor position
 *   s   - String to print
 */
void at(int pos, char *s);

/*
 * gcursor - Get current cursor position
 *
 * Returns:
 *   Current cursor position
 */
int gcursor(void);

/* =============================================================================
 * Display Mode Functions (LZ/LZ64 only)
 * =============================================================================
 * These functions control the dual display mode on 4-line machines.
 * On LZ, you can run in 2-line compatibility mode (shows a canvas/border)
 * or native 4-line mode.
 *
 * IMPORTANT: These functions are only available on LA/LZ/LZ64 models.
 * Calling them on CM/XP will cause undefined behavior.
 *
 * Use #ifdef __PSION_4LINE__ to conditionally compile these calls.
 */

/* Display mode constants */
#define MODE_2LINE 0
#define MODE_4LINE 1

/*
 * setmode - Set display mode (LZ only)
 *
 * Switches between 2-line compatibility mode and native 4-line mode.
 * In 2-line mode, the display shows a 16x2 character area centered
 * on the screen with a decorative border ("canvas").
 *
 * Parameters:
 *   mode - MODE_2LINE (0) or MODE_4LINE (1)
 *
 * Example:
 *   #ifdef __PSION_4LINE__
 *     setmode(MODE_4LINE);  // Use full 4-line display
 *   #endif
 */
void setmode(int mode);

/*
 * getmode - Get current display mode (LZ only)
 *
 * Returns:
 *   MODE_2LINE (0) if in 2-line compatibility mode
 *   MODE_4LINE (1) if in native 4-line mode
 */
int getmode(void);

/*
 * pushmode - Save current display mode (LZ only)
 *
 * Saves the current display mode to a stack. Use with popmode()
 * to temporarily switch modes and restore.
 *
 * Example:
 *   pushmode();
 *   setmode(MODE_2LINE);  // Temporarily use 2-line mode
 *   // ... do something ...
 *   popmode();            // Restore original mode
 */
void pushmode(void);

/*
 * popmode - Restore saved display mode (LZ only)
 *
 * Restores the display mode saved by a previous pushmode() call.
 */
void popmode(void);

/* =============================================================================
 * Keyboard Functions
 * =============================================================================
 */

/*
 * getkey - Wait for and return a keypress
 *
 * Blocks until a key is pressed, then returns the ASCII code
 * of the key (or special key code for function keys).
 *
 * Returns:
 *   ASCII code of pressed key
 */
char getkey(void);

/*
 * testkey - Test for keypress without blocking
 *
 * Checks if a key is available in the keyboard buffer.
 * Returns immediately without waiting.
 *
 * Returns:
 *   ASCII code of key if pressed, 0 if no key available
 */
char testkey(void);

/*
 * kbhit - Check if key is available
 *
 * Returns non-zero if a key is in the buffer.
 *
 * Returns:
 *   1 if key available, 0 if not
 */
int kbhit(void);

/*
 * flushkb - Flush keyboard buffer
 *
 * Removes all pending keypresses from the keyboard buffer.
 */
void flushkb(void);

/* =============================================================================
 * Sound Functions
 * =============================================================================
 */

/*
 * beep - Generate standard beep
 *
 * Produces the standard Psion beep sound.
 */
void beep(void);

/*
 * alarm - Generate alarm beep
 *
 * Produces a more prominent alarm sound.
 */
void alarm(void);

/*
 * tone - Generate custom tone
 *
 * Produces a tone at specified pitch for specified duration.
 *
 * Parameters:
 *   pitch    - Tone frequency (higher = lower pitch)
 *   duration - Length in 1/32 second units
 */
void tone(int pitch, int duration);

/* =============================================================================
 * Time Functions
 * =============================================================================
 */

/*
 * delay - Pause execution
 *
 * Pauses program execution for the specified number of ticks.
 * One tick is 1/50 second (20ms).
 *
 * Parameters:
 *   ticks - Number of ticks to wait (1 tick = 20ms)
 */
void delay(int ticks);

/*
 * getticks - Get system tick counter
 *
 * Returns the current value of the system tick counter.
 * Useful for timing measurements.
 *
 * Returns:
 *   Current tick count (wraps at 65535)
 */
unsigned int getticks(void);

/*
 * gettime - Get current time
 *
 * Retrieves the current time from the real-time clock.
 *
 * Parameters:
 *   buf - Buffer to receive time (6 bytes: YY MM DD HH MM SS)
 */
void gettime(char *buf);

/*
 * settime - Set current time
 *
 * Sets the real-time clock.
 *
 * Parameters:
 *   buf - Time to set (6 bytes: YY MM DD HH MM SS)
 */
void settime(char *buf);

/* =============================================================================
 * Number Output Functions
 * =============================================================================
 */

/*
 * print_int - Print integer value
 *
 * Prints a signed 16-bit integer as decimal digits.
 *
 * Parameters:
 *   n - Integer to print (-32768 to 32767)
 */
void print_int(int n);

/*
 * print_uint - Print unsigned integer
 *
 * Prints an unsigned 16-bit integer as decimal digits.
 *
 * Parameters:
 *   n - Unsigned integer to print (0 to 65535)
 */
void print_uint(unsigned int n);

/*
 * print_hex - Print integer as hexadecimal
 *
 * Prints a 16-bit value as 4 hex digits.
 *
 * Parameters:
 *   n - Value to print
 */
void print_hex(unsigned int n);

/* =============================================================================
 * String Functions
 * =============================================================================
 */

/*
 * strlen - Get string length
 *
 * Parameters:
 *   s - Pointer to null-terminated string
 *
 * Returns:
 *   Length of string (not including null terminator)
 */
int strlen(char *s);

/*
 * strcpy - Copy string
 *
 * Copies source string to destination buffer including null terminator.
 *
 * Parameters:
 *   dest - Destination buffer
 *   src  - Source string
 *
 * Returns:
 *   Pointer to dest
 */
char *strcpy(char *dest, char *src);

/*
 * strcmp - Compare strings
 *
 * Compares two strings lexicographically.
 *
 * Parameters:
 *   a - First string
 *   b - Second string
 *
 * Returns:
 *   0 if equal, <0 if a<b, >0 if a>b
 */
int strcmp(char *a, char *b);

/*
 * strcat - Concatenate strings
 *
 * Appends src to the end of dest.
 *
 * Parameters:
 *   dest - Destination buffer (must have room)
 *   src  - String to append
 *
 * Returns:
 *   Pointer to dest
 */
char *strcat(char *dest, char *src);

/* =============================================================================
 * Memory Functions
 * =============================================================================
 */

/*
 * memcpy - Copy memory block
 *
 * Copies n bytes from src to dest.
 *
 * Parameters:
 *   dest - Destination buffer
 *   src  - Source buffer
 *   n    - Number of bytes to copy
 *
 * Returns:
 *   Pointer to dest
 */
void *memcpy(void *dest, void *src, int n);

/*
 * memset - Fill memory
 *
 * Sets n bytes of dest to value c.
 *
 * Parameters:
 *   dest - Destination buffer
 *   c    - Fill value (byte)
 *   n    - Number of bytes to fill
 *
 * Returns:
 *   Pointer to dest
 */
void *memset(void *dest, int c, int n);

/*
 * memcmp - Compare memory
 *
 * Compares n bytes of memory.
 *
 * Parameters:
 *   a - First buffer
 *   b - Second buffer
 *   n - Number of bytes to compare
 *
 * Returns:
 *   0 if equal, <0 if a<b, >0 if a>b
 */
int memcmp(void *a, void *b, int n);

/* =============================================================================
 * Utility Functions
 * =============================================================================
 */

/*
 * abs - Absolute value
 *
 * Parameters:
 *   n - Integer value
 *
 * Returns:
 *   Absolute value of n
 */
int abs(int n);

/*
 * min - Minimum of two values
 *
 * Parameters:
 *   a, b - Values to compare
 *
 * Returns:
 *   Smaller of a and b
 */
int min(int a, int b);

/*
 * max - Maximum of two values
 *
 * Parameters:
 *   a, b - Values to compare
 *
 * Returns:
 *   Larger of a and b
 */
int max(int a, int b);

/*
 * exit - Exit program
 *
 * Terminates the program and returns to the Psion menu.
 */
void exit(void);

#endif /* _PSION_H */
