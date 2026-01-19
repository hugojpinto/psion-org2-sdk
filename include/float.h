/*
 * =============================================================================
 * Psion Organiser II Floating Point Library Header
 * =============================================================================
 *
 * This header provides floating point support for Small-C programs on the
 * Psion Organiser II. Since Small-C doesn't support native floating point,
 * we provide a library-based approach using 8-byte FP numbers.
 *
 * USAGE:
 *   #include <psion.h>       // Core functions (display, keyboard, etc.)
 *   #include <float.h>       // Floating point support (this file)
 *
 * The compiler will automatically include the necessary runtime code
 * (float.inc and fpruntime.inc) when float.h is included.
 *
 * EXAMPLE:
 *   void main() {
 *       fp_t angle, result;
 *
 *       cls();
 *       fp_from_str(&angle, "0.5236");  // 30 degrees in radians
 *       fp_sin(&result, &angle);
 *       print("sin(30 deg) = ");
 *       fp_print(&result, 4);
 *       getkey();
 *   }
 *
 * FLOATING POINT FORMAT:
 *   Psion uses a proprietary 8-byte BCD format:
 *   - Byte 0: Exponent (bits 0-6) + Sign (bit 7)
 *   - Bytes 1-7: BCD mantissa (14 decimal digits)
 *   - Precision: ~14 significant decimal digits
 *   - Range: approximately 10^-63 to 10^63
 *
 * ERROR HANDLING:
 *   FP operations may fail (overflow, divide by zero, etc.). After any
 *   FP operation, check fp_error for error status:
 *
 *   fp_div(&result, &a, &b);
 *   if (fp_error == FPE_DIVZERO) {
 *       print("Division by zero!");
 *   }
 *
 * LZ-SPECIFIC FUNCTIONS:
 *   Some functions (fp_asin, fp_acos) are only available on LA/LZ/LZ64.
 *   They are conditionally compiled when using -m LZ or -m LZ64.
 *
 * REFERENCE:
 *   - https://www.jaapsch.net/psion/mcosxp1.htm#float
 *   - https://www.jaapsch.net/psion/mcosxp2.htm#floatarith
 *
 * Author: Hugo José Pinto & Contributors
 * =============================================================================
 */

#ifndef _FLOAT_H
#define _FLOAT_H

/* =============================================================================
 * Floating Point Data Type
 * =============================================================================
 *
 * Since Small-C doesn't support native float/double types, we represent
 * floating point numbers as arrays of 8 bytes (fp_t).
 *
 * IMPORTANT: Always use pointers (&var) when passing fp_t to functions.
 * You CANNOT assign fp_t directly; use fp_zero(), fp_from_int(), etc.
 *
 * Example:
 *   fp_t x, y, result;
 *   fp_from_str(&x, "3.14159");
 *   fp_from_str(&y, "2.0");
 *   fp_mul(&result, &x, &y);  // result = x * y
 */

/* Floating point number - 8 bytes in Psion's BCD format */
typedef char fp_t[8];

/* Size of a floating point number in bytes */
#define FP_SIZE 8

/* =============================================================================
 * Error Handling
 * =============================================================================
 *
 * The global variable fp_error is set by FP operations when errors occur.
 * Always check fp_error after operations that may fail.
 *
 * USAGE:
 *   fp_clear_error();          // Clear before operation (optional)
 *   fp_sqrt(&result, &x);      // Perform operation
 *   if (fp_error) {
 *       // Handle error
 *   }
 */

/*
 * FP error handling uses a global variable _fp_error defined in fpruntime.inc.
 * Use fp_get_error() to read it and fp_clear_error() to reset it.
 * The fp_error macro provides convenient access for checking.
 */
int fp_get_error(void);
#define fp_error fp_get_error()

/*
 * Error codes:
 *   FPE_NONE     (0)   - No error
 *   FPE_RANGE    (247) - Argument out of valid range
 *   FPE_LIST     (249) - Invalid list parameter (LZ stat functions)
 *   FPE_TOSTR    (250) - Number to string conversion error
 *   FPE_DIVZERO  (251) - Division by zero
 *   FPE_TOFLT    (252) - String to number conversion error
 *   FPE_OVERFLOW (253) - Arithmetic overflow
 */
#define FPE_NONE      0
#define FPE_RANGE   247
#define FPE_LIST    249
#define FPE_TOSTR   250
#define FPE_DIVZERO 251
#define FPE_TOFLT   252
#define FPE_OVERFLOW 253

/*
 * fp_clear_error - Clear the FP error flag
 *
 * Call this before operations if you want to ensure fp_error
 * reflects only errors from subsequent operations.
 */
void fp_clear_error(void);

/* =============================================================================
 * Initialization and Conversion Functions
 * =============================================================================
 */

/*
 * fp_zero - Set FP number to zero
 *
 * Parameters:
 *   dest - Pointer to FP storage to clear
 *
 * Example:
 *   fp_t x;
 *   fp_zero(&x);  // x = 0.0
 */
void fp_zero(fp_t *dest);

/*
 * fp_from_int - Convert integer to FP
 *
 * Parameters:
 *   dest - Pointer to FP storage for result
 *   n    - 16-bit signed integer to convert
 *
 * Example:
 *   fp_t x;
 *   fp_from_int(&x, 42);  // x = 42.0
 *   fp_from_int(&x, -100); // x = -100.0
 */
void fp_from_int(fp_t *dest, int n);

/*
 * fp_from_str - Convert string to FP
 *
 * Converts an ASCII string representing a number to FP format.
 * Supports signs, decimal points, and exponential notation.
 *
 * Parameters:
 *   dest - Pointer to FP storage for result
 *   s    - Null-terminated string (e.g., "3.14159", "-2.5E10")
 *
 * Errors:
 *   Sets fp_error to FPE_TOFLT if conversion fails
 *
 * Example:
 *   fp_t pi;
 *   fp_from_str(&pi, "3.14159265358979");
 */
void fp_from_str(fp_t *dest, char *s);

/*
 * fp_to_int - Convert FP to integer (truncated)
 *
 * Converts FP number to 16-bit signed integer by truncating
 * towards zero. Values outside -32768 to 32767 may overflow.
 *
 * Parameters:
 *   src - Pointer to FP number to convert
 *
 * Returns:
 *   Integer value (truncated towards zero)
 *
 * Example:
 *   fp_t x;
 *   int n;
 *   fp_from_str(&x, "3.7");
 *   n = fp_to_int(&x);  // n = 3
 */
int fp_to_int(fp_t *src);

/*
 * fp_to_str - Convert FP to string
 *
 * Converts FP number to null-terminated ASCII string.
 * Uses general format (automatic selection of fixed or scientific).
 *
 * Parameters:
 *   buf    - Output buffer (should be >= 20 characters)
 *   src    - Pointer to FP number to convert
 *   places - Decimal places (0-14, or negative for auto)
 *
 * Errors:
 *   Sets fp_error to FPE_TOSTR on conversion error
 *
 * Example:
 *   fp_t x;
 *   char buf[24];
 *   fp_from_str(&x, "123.456789");
 *   fp_to_str(buf, &x, 4);  // buf = "123.4568"
 */
void fp_to_str(char *buf, fp_t *src, int places);

/* =============================================================================
 * Arithmetic Functions
 * =============================================================================
 *
 * All arithmetic functions follow the pattern:
 *   fp_op(result, operand1, operand2)
 * where result = operand1 op operand2
 *
 * NOTE: result can be the same variable as an operand:
 *   fp_add(&x, &x, &y);  // x = x + y  (valid)
 */

/*
 * fp_add - Add two FP numbers
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   a, b   - Pointers to operands
 *
 * Errors:
 *   Sets fp_error to FPE_OVERFLOW on overflow
 *
 * Example:
 *   fp_add(&sum, &x, &y);  // sum = x + y
 */
void fp_add(fp_t *result, fp_t *a, fp_t *b);

/*
 * fp_sub - Subtract two FP numbers
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   a, b   - Pointers to operands
 *
 * Errors:
 *   Sets fp_error to FPE_OVERFLOW on overflow
 *
 * Example:
 *   fp_sub(&diff, &x, &y);  // diff = x - y
 */
void fp_sub(fp_t *result, fp_t *a, fp_t *b);

/*
 * fp_mul - Multiply two FP numbers
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   a, b   - Pointers to operands
 *
 * Errors:
 *   Sets fp_error to FPE_OVERFLOW on overflow
 *
 * Example:
 *   fp_mul(&prod, &x, &y);  // prod = x * y
 */
void fp_mul(fp_t *result, fp_t *a, fp_t *b);

/*
 * fp_div - Divide two FP numbers
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   a, b   - Pointers to operands (a / b)
 *
 * Errors:
 *   Sets fp_error to FPE_DIVZERO if b is zero
 *   Sets fp_error to FPE_OVERFLOW on overflow
 *
 * Example:
 *   fp_div(&quot, &x, &y);  // quot = x / y
 */
void fp_div(fp_t *result, fp_t *a, fp_t *b);

/*
 * fp_neg - Negate FP number in place
 *
 * Changes the sign of an FP number (positive becomes negative,
 * negative becomes positive).
 *
 * Parameters:
 *   n - Pointer to FP number to negate (modified in place)
 *
 * Example:
 *   fp_from_str(&x, "3.14");
 *   fp_neg(&x);  // x = -3.14
 */
void fp_neg(fp_t *n);

/* =============================================================================
 * Mathematical Functions
 * =============================================================================
 *
 * Trigonometric functions use RADIANS, not degrees.
 * To convert degrees to radians: radians = degrees * pi / 180
 *
 * Example:
 *   // Calculate sin(30 degrees)
 *   fp_t deg30, result, pi, d180;
 *   fp_from_str(&pi, "3.14159265358979");
 *   fp_from_int(&d180, 180);
 *   fp_from_int(&deg30, 30);
 *   fp_mul(&deg30, &deg30, &pi);   // deg30 * pi
 *   fp_div(&deg30, &deg30, &d180); // / 180 = radians
 *   fp_sin(&result, &deg30);       // result = 0.5
 */

/*
 * fp_sin - Compute sine
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   angle  - Pointer to angle in RADIANS
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE on invalid input
 */
void fp_sin(fp_t *result, fp_t *angle);

/*
 * fp_cos - Compute cosine
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   angle  - Pointer to angle in RADIANS
 */
void fp_cos(fp_t *result, fp_t *angle);

/*
 * fp_tan - Compute tangent
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   angle  - Pointer to angle in RADIANS
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE near odd multiples of pi/2
 */
void fp_tan(fp_t *result, fp_t *angle);

/*
 * fp_atan - Compute arctangent
 *
 * Returns the angle (in radians) whose tangent is x.
 * Result is in range [-pi/2, pi/2].
 *
 * Parameters:
 *   result - Pointer to storage for result (radians)
 *   x      - Pointer to input value
 */
void fp_atan(fp_t *result, fp_t *x);

/*
 * fp_sqrt - Compute square root
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   x      - Pointer to non-negative number
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE if x is negative
 */
void fp_sqrt(fp_t *result, fp_t *x);

/*
 * fp_exp - Compute e^x (exponential function)
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   x      - Pointer to exponent
 *
 * Errors:
 *   Sets fp_error to FPE_OVERFLOW if result too large
 */
void fp_exp(fp_t *result, fp_t *x);

/*
 * fp_ln - Compute natural logarithm (base e)
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   x      - Pointer to positive number
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE if x <= 0
 */
void fp_ln(fp_t *result, fp_t *x);

/*
 * fp_log - Compute logarithm base 10
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   x      - Pointer to positive number
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE if x <= 0
 */
void fp_log(fp_t *result, fp_t *x);

/*
 * fp_pow - Compute x^y (power function)
 *
 * Parameters:
 *   result - Pointer to storage for result
 *   x      - Pointer to base
 *   y      - Pointer to exponent
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE for invalid combinations
 *   (e.g., negative base with non-integer exponent)
 */
void fp_pow(fp_t *result, fp_t *x, fp_t *y);

/*
 * fp_rnd - Generate random number between 0 and 1
 *
 * Returns a pseudo-random FP number in range [0, 1).
 *
 * Parameters:
 *   result - Pointer to storage for result
 *
 * Example:
 *   fp_t r;
 *   fp_rnd(&r);  // r = random value 0 <= r < 1
 */
void fp_rnd(fp_t *result);

/* =============================================================================
 * LZ-Only Functions
 * =============================================================================
 *
 * These functions are ONLY available on LA/LZ/LZ64 models.
 * They are conditionally compiled when targeting 4-line machines.
 *
 * Using these on CM/XP will cause undefined behavior or crash.
 */

#ifdef __PSION_4LINE__

/*
 * fp_asin - Compute arcsine (LZ only)
 *
 * Returns the angle (in radians) whose sine is x.
 * Result is in range [-pi/2, pi/2].
 *
 * Parameters:
 *   result - Pointer to storage for result (radians)
 *   x      - Pointer to value in range [-1, 1]
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE if |x| > 1
 */
void fp_asin(fp_t *result, fp_t *x);

/*
 * fp_acos - Compute arccosine (LZ only)
 *
 * Returns the angle (in radians) whose cosine is x.
 * Result is in range [0, pi].
 *
 * Parameters:
 *   result - Pointer to storage for result (radians)
 *   x      - Pointer to value in range [-1, 1]
 *
 * Errors:
 *   Sets fp_error to FPE_RANGE if |x| > 1
 */
void fp_acos(fp_t *result, fp_t *x);

#endif /* __PSION_4LINE__ */

/* =============================================================================
 * Comparison Functions
 * =============================================================================
 */

/*
 * fp_cmp - Compare two FP numbers
 *
 * Parameters:
 *   a, b - Pointers to FP numbers to compare
 *
 * Returns:
 *   -1 if a < b
 *    0 if a == b (approximately)
 *    1 if a > b
 *
 * Example:
 *   if (fp_cmp(&x, &y) > 0) {
 *       print("x is greater");
 *   }
 */
int fp_cmp(fp_t *a, fp_t *b);

/*
 * fp_sign - Get sign of FP number
 *
 * Parameters:
 *   n - Pointer to FP number
 *
 * Returns:
 *   -1 if negative
 *    0 if zero
 *    1 if positive
 */
int fp_sign(fp_t *n);

/*
 * fp_is_zero - Check if FP number is zero
 *
 * Parameters:
 *   n - Pointer to FP number
 *
 * Returns:
 *   1 if n is zero
 *   0 if n is non-zero
 */
int fp_is_zero(fp_t *n);

/* =============================================================================
 * Output Functions
 * =============================================================================
 */

/*
 * fp_print - Print FP number to display
 *
 * Prints the FP number at the current cursor position using
 * general format (automatic fixed or scientific notation).
 *
 * Parameters:
 *   n      - Pointer to FP number to print
 *   places - Number of decimal places (0-14)
 *
 * Example:
 *   fp_t pi;
 *   fp_from_str(&pi, "3.14159");
 *   fp_print(&pi, 4);  // Displays "3.1416"
 */
void fp_print(fp_t *n, int places);

/*
 * fp_print_sci - Print FP number in scientific notation
 *
 * Prints the FP number at the current cursor position using
 * exponential format (e.g., "3.14E+00").
 *
 * Parameters:
 *   n      - Pointer to FP number to print
 *   places - Number of decimal places (0-14)
 *
 * Example:
 *   fp_t x;
 *   fp_from_str(&x, "12345.67");
 *   fp_print_sci(&x, 2);  // Displays "1.23E+04"
 */
void fp_print_sci(fp_t *n, int places);

/* =============================================================================
 * Mathematical Constants (for convenience)
 * =============================================================================
 *
 * To use these, copy them to a local fp_t variable:
 *
 *   fp_t my_pi;
 *   fp_from_str(&my_pi, FP_STR_PI);
 *
 * Or use directly in calculations:
 *   fp_from_str(&temp, FP_STR_PI);
 *   fp_mul(&result, &x, &temp);  // result = x * pi
 */

/* String representations of common constants */
#define FP_STR_PI     "3.14159265358979"   /* Pi */
#define FP_STR_E      "2.71828182845905"   /* e (Euler's number) */
#define FP_STR_LN2    "0.69314718055995"   /* ln(2) */
#define FP_STR_LN10   "2.30258509299405"   /* ln(10) */
#define FP_STR_SQRT2  "1.41421356237310"   /* sqrt(2) */

/* Conversion factors */
#define FP_STR_DEG2RAD "0.01745329251994"  /* pi/180 - degrees to radians */
#define FP_STR_RAD2DEG "57.2957795130823"  /* 180/pi - radians to degrees */

#endif /* _FLOAT_H */
