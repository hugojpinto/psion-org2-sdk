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
 * FLOATING POINT SUPPORT:
 *   For floating point operations (sin, cos, sqrt, etc.), include float.h:
 *     #include <psion.h>
 *     #include <float.h>
 *
 *   Floating point functions are kept separate to avoid code bloat when
 *   not needed. See float.h for documentation and examples.
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

/*
 * udg_define - Define a User Defined Graphic character
 *
 * Defines a custom 5x8 pixel character that can be displayed
 * using putchar(0) through putchar(7). The Psion Organiser II
 * supports 8 UDGs (characters 0-7) which are stored in the
 * HD44780 LCD controller's CGRAM (Character Generator RAM).
 *
 * Parameters:
 *   char_num - Character number (0-7)
 *   data     - Pointer to 8 bytes of bitmap data
 *              Each byte defines one row (top to bottom)
 *              Bits 0-4 are the pixels (bit 4 = left, bit 0 = right)
 *
 * Bitmap Format:
 *   Each UDG is 5 pixels wide by 8 pixels tall.
 *   Each of the 8 bytes represents one row, from top to bottom.
 *   Within each byte, bits 4-0 represent pixels left-to-right.
 *   Bits 7-5 are unused and should be 0.
 *
 *   Example pattern for a star:
 *     Row 0: 0x04 = 00100 = ..X..
 *     Row 1: 0x04 = 00100 = ..X..
 *     Row 2: 0x1F = 11111 = XXXXX
 *     Row 3: 0x0E = 01110 = .XXX.
 *     Row 4: 0x0E = 01110 = .XXX.
 *     Row 5: 0x15 = 10101 = X.X.X
 *     Row 6: 0x04 = 00100 = ..X..
 *     Row 7: 0x00 = 00000 = .....
 *
 * Implementation Notes:
 *   This function disables interrupts (using SEI) while writing to the
 *   LCD's CGRAM to prevent interrupt handlers from corrupting the writes.
 *   On real hardware, the Psion OS may update the display in interrupt
 *   handlers which could interleave with CGRAM writes and cause corruption.
 *
 * Example:
 *   char smiley[8] = {0x00, 0x0A, 0x00, 0x11, 0x0E, 0x00, 0x00, 0x00};
 *   udg_define(0, smiley);
 *   putchar(0);  // Display the smiley
 *
 * Note: The OS may redefine UDGs for its own use (clock, icons, etc.)
 * so you should define your UDGs after returning from any OS menu
 * interaction that might have overwritten them.
 */
void udg_define(int char_num, char *data);

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

/* =============================================================================
 * OPL Interoperability - The 'external' Keyword
 * =============================================================================
 *
 * The 'external' keyword enables Small-C code to call OPL procedures that
 * exist on the Psion device. This is the RECOMMENDED way to call OPL code.
 *
 * SYNTAX
 * ------
 *   external void procedureName();   // For procedures that return nothing
 *   external int procedureName%();   // For procedures that return integers
 *
 * RETURN VALUES
 * -------------
 *   OPL procedure names determine their return type:
 *     - PROC%: returns integer (use 'external int PROC%();')
 *     - PROC:  returns float (NOT SUPPORTED - use void)
 *     - PROC$: returns string (NOT SUPPORTED - use void)
 *
 *   Integer-returning procedures can have their value captured:
 *     external int GETVAL%();
 *     int x = GETVAL%();  // x receives the OPL return value
 *
 *   Note: The '%' suffix IS part of the procedure name in OPL.
 *
 * CONSTRAINTS
 * -----------
 *   - Return type: void or int (float/string not supported)
 *   - Parameters: MUST be empty (use global variables for data exchange)
 *   - Procedure name MUST be <= 8 characters (Psion identifier limit)
 *
 * EXAMPLE - Void Procedure
 * ------------------------
 *   // Declare external OPL procedures at file scope
 *   external void azMENU();
 *   external void azHELP();
 *
 *   void main() {
 *       int score = 100;      // Local variables work normally
 *
 *       azMENU();             // Call looks like a normal C function!
 *
 *       // Execution resumes here after OPL procedure returns
 *       // score is STILL 100! (local variables preserved)
 *       print_int(score);
 *
 *       azHELP();             // Can call multiple external procedures
 *   }
 *
 * EXAMPLE - Integer-Returning Procedure
 * -------------------------------------
 *   // OPL procedure: RANDOM%: RETURN INT(RND*100)
 *   external int RANDOM%();
 *
 *   void main() {
 *       int r = RANDOM%();    // Get random number from OPL!
 *       print("Random: ");
 *       print_int(r);
 *   }
 *
 * HOW IT WORKS
 * ------------
 *   Under the hood, the compiler:
 *   1. Injects setup code at the start of main() (transparent to user)
 *   2. Transforms external calls into QCode injection sequences
 *   3. The OPL interpreter runs the procedure and returns control to C
 *   4. Stack is automatically preserved across the call
 *   5. For int returns, captures the return value from OPL's language stack
 *
 * DATA EXCHANGE
 * -------------
 *   External procedures cannot take parameters. Use global variables
 *   or OPL return values for data exchange between C and OPL:
 *
 *   // Method 1: Use return value (preferred for simple data)
 *   external int GETSCORE%();
 *   int score = GETSCORE%();
 *
 *   // Method 2: Use global variables (for complex data exchange)
 *   int g_score;              // Global variable for data exchange
 *
 *   external void azSCORE();  // OPL procedure reads g_score via PEEKW
 *
 *   void main() {
 *       g_score = 42;         // Set before calling OPL
 *       azSCORE();            // OPL reads g_score via PEEKW/POKEW
 *   }
 *
 * PORTABILITY
 * -----------
 *   This feature is fully portable across all Psion II models:
 *   CM, XP, LA, LZ, LZ64, and P350.
 *
 * Reference: dev_docs/PROCEDURE_CALL_RESEARCH.md
 */

/* =============================================================================
 * Legacy OPL Functions (for advanced users)
 * =============================================================================
 * These functions provide low-level access to OPL procedure calling.
 * For most users, the 'external' keyword above is RECOMMENDED instead.
 */

/*
 * _call_opl_setup - Initialize call_opl support
 *
 * NOTE: When using the 'external' keyword, this is called AUTOMATICALLY
 * by compiler-injected code. You do NOT need to call it manually!
 *
 * For legacy code using call_opl() directly, this function MUST be called
 * as the very first statement in main(), BEFORE any local variables.
 *
 * Example (legacy usage):
 *   void main() {
 *       _call_opl_setup();  // MUST be first, before locals!
 *       int x;              // Locals AFTER setup
 *       call_opl("azMENU"); // Manual call_opl() invocation
 *   }
 */
void _call_opl_setup(void);

/*
 * call_opl - Call an OPL procedure from C code (legacy interface)
 *
 * NOTE: For new code, use the 'external' keyword instead:
 *   external int GETVAL%();
 *   int x = GETVAL%();  // Much cleaner syntax!
 *
 * This function calls an external OPL procedure by name. After the
 * procedure completes, execution resumes at the next statement.
 * LOCAL VARIABLES ARE PRESERVED across the call.
 *
 * Parameters:
 *   name - Name of OPL procedure to call (max 8 characters)
 *          Include '%' suffix for integer-returning procedures
 *
 * Returns:
 *   For integer procedures (name ends with '%'): the return value
 *   For void/float procedures: 0 (default OPL return)
 *
 * REQUIREMENTS:
 *   - _call_opl_setup() MUST be called first in main(), BEFORE locals!
 *   - Maximum procedure name length: 8 characters
 *   - Uses default device (A:) for procedure lookup
 *
 * Example (legacy usage):
 *   void main() {
 *       _call_opl_setup();           // Required - MUST be first!
 *       int score = 42;
 *       call_opl("azMENU");          // Call void procedure
 *       int val = call_opl("GET%");  // Call int-returning procedure
 *       print_int(score);            // score is still 42!
 *       print_int(val);              // val has OPL return value
 *   }
 */
int call_opl(char *name);

#endif /* _PSION_H */
