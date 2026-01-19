; =============================================================================
; FLOAT.INC - Psion Organiser II Floating Point Support
; =============================================================================
;
; This file provides constants, system variables, and macros for floating
; point operations on the Psion Organiser II. Include this file in assembly
; programs that need floating point arithmetic or mathematical functions.
;
; The Psion OS provides built-in floating point support via system calls.
; Floating point numbers are stored in 8 bytes using a proprietary BCD
; (Binary Coded Decimal) format with approximately 14 decimal digits of
; precision.
;
; FLOATING POINT FORMAT (8 bytes):
;   Byte 0:      Exponent + Sign (bit 7 = sign, bits 0-6 = exponent, bias 64)
;   Bytes 1-7:   BCD Mantissa (14 decimal digits, packed 2 per byte)
;
; IMPORTANT CONCEPTS:
;   - The FP functions use TWO different memory areas:
;     1. FP Accumulator ($C5-$CD): Used by MT$xxx arithmetic functions
;     2. Runtime Stack (RTA_SP at $A5-$A6): Used by FN$xxx trig functions
;   - The runtime stack is NOT the CPU stack (SP). It's a separate stack
;     used by the OPL interpreter for FP operations.
;   - Always ensure 60 bytes available below RTA_SP for scratch space.
;
; USAGE:
;   INCLUDE "psion.inc"     ; Core definitions (includes syscalls.inc)
;   INCLUDE "float.inc"     ; Floating point support (this file)
;   INCLUDE "fpruntime.inc" ; Optional: C runtime FP functions
;
; EXAMPLE - Calculate sqrt(2):
;   ; Convert string "2.0" to FP at my_val
;   LDX     #str_two
;   LDD     #my_val
;   SWI
;   FCB     MT_BTOF
;
;   ; Push onto runtime stack
;   LDX     #my_val
;   JSR     __fp_push_rts       ; From fpruntime.inc
;
;   ; Call square root
;   SWI
;   FCB     FN_SQRT
;
;   ; Pop result
;   LDX     #my_result
;   JSR     __fp_pop_rts
;
; Reference: https://www.jaapsch.net/psion/mcosxp1.htm#float
;            https://www.jaapsch.net/psion/mcosxp2.htm#floatarith
;
; Author: Hugo José Pinto & Contributors
; =============================================================================

; =============================================================================
; Floating Point Size Constants
; =============================================================================

FP_SIZE         EQU     8       ; Size of a floating point number in bytes
FP_ACC_SIZE     EQU     9       ; Size of the FP accumulator (extra byte internal)

; =============================================================================
; Floating Point System Variables
; =============================================================================
; These memory locations are used by the OS for floating point operations.
; NOTE: Some overlap with sysvars.inc but are grouped here for FP clarity.

; -----------------------------------------------------------------------------
; Runtime Stack Pointer (for FN$xxx functions)
; -----------------------------------------------------------------------------
; The FN$ trig/math functions operate on a separate "runtime stack" used by
; the OPL interpreter. This is NOT the CPU stack (SP register).
;
; To use FN$ functions from machine code:
;   1. Push 8-byte FP number onto this stack (decrement RTA_SP by 8, copy data)
;   2. Call the function (SWI + FCB FN_xxx)
;   3. Result replaces input on stack (some functions push additional values)
;   4. Pop result (copy data, increment RTA_SP by 8)

RTA_SP          EQU     $A5     ; Runtime stack pointer (2 bytes: $A5-$A6)
                                ; Points to top of runtime stack (grows down)
                                ; MUST have 60+ bytes available below for scratch

; -----------------------------------------------------------------------------
; Floating Point Accumulator (for MT$xxx functions)
; -----------------------------------------------------------------------------
; The MT$ arithmetic functions (add, sub, mul, div) use the FP accumulator.
; The accumulator is 9 bytes, though FP numbers are 8 bytes.
;
; For binary operations (add, sub, mul, div):
;   - First operand in FP_ACC (copy 8 bytes to $C5)
;   - Second operand in FP_OPR (copy 8 bytes to $CD)
;   - Result appears in FP_ACC
;
; For MT_BTOF (string to FP):
;   - X = string address, D = destination address for result
;
; For MT_FBxx (FP to string):
;   - FP number must be in accumulator first
;   - A = max string length, B = decimal places, X = output buffer
;   - Result: B = actual string length

; -----------------------------------------------------------------------------
; FP Accumulator Structure (9 bytes: $C5-$CD)
; -----------------------------------------------------------------------------
; The accumulator has a guard byte at $C5 for intermediate precision.
; When loading/storing 8-byte user FP values, skip the guard byte.
;
; Layout:
;   $C5:      Guard byte (MTT_AMAN) - set to 0 before operations
;   $C6-$CB:  Mantissa (6 bytes, BCD packed)
;   $CC:      Exponent (MTB_AEXP)
;   $CD:      Sign (MTB_ASGN)
; -----------------------------------------------------------------------------
FP_ACC          EQU     $C5     ; Floating point accumulator start (includes guard)
FP_ACC_MAN      EQU     $C6     ; Accumulator mantissa start (skip guard for 8-byte copy)

; -----------------------------------------------------------------------------
; FP Operator Structure (9 bytes: $CE-$D6)
; -----------------------------------------------------------------------------
; The operator area also has a guard byte. Used as second operand for
; binary operations (add, sub, mul, div).
;
; Layout:
;   $CE:      Guard byte (MTT_OMAN) - set to 0 before operations
;   $CF-$D4:  Mantissa (6 bytes, BCD packed)
;   $D5:      Exponent (MTB_OEXP)
;   $D6:      Sign (MTB_OSGN)
; -----------------------------------------------------------------------------
FP_OPR          EQU     $CE     ; Floating point operator start (includes guard)
FP_OPR_MAN      EQU     $CF     ; Operator mantissa start (skip guard for 8-byte copy)

; Work area addresses (from sysvars.inc, repeated for reference)
; These can be used for temporary FP storage in user code
MTH_TMP         EQU     $B0     ; Math temp area (8 bytes)

; =============================================================================
; Floating Point Service Call Aliases
; =============================================================================
; These provide more intuitive names for FP operations. The actual values
; are the same as in syscalls.inc (FN_xxx, MT_xxx), but prefixed with FP_
; for clarity in FP-heavy code.
;
; NOTE: syscalls.inc must be included first (via psion.inc) for these to work.

; -----------------------------------------------------------------------------
; Trigonometric and Mathematical Functions (use Runtime Stack)
; -----------------------------------------------------------------------------
; These functions operate on the runtime stack (RTA_SP), not the accumulator.
; Input: FP number on top of runtime stack
; Output: Result replaces input on stack (and in FP_ACC)

FP_SIN          EQU     FN_SIN      ; $3F - Sine (radians)
FP_COS          EQU     FN_COS      ; $39 - Cosine (radians)
FP_TAN          EQU     FN_TAN      ; $41 - Tangent (radians)
FP_ATAN         EQU     FN_ATAN     ; $38 - Arctangent
FP_SQRT         EQU     FN_SQRT     ; $40 - Square root
FP_EXP          EQU     FN_EXP      ; $3A - Exponential (e^x)
FP_LN           EQU     FN_LN       ; $3B - Natural logarithm
FP_LOG          EQU     FN_LOG      ; $3C - Logarithm base 10
FP_RND          EQU     FN_RND      ; $3E - Random number 0-1 (PUSHES result)

; FP_POWR is binary: requires TWO numbers on stack
; If X and Y on stack (Y pushed last), computes X^Y
FP_POWR         EQU     FN_POWR     ; $3D - Power (x^y)

; -----------------------------------------------------------------------------
; Arithmetic Functions (use FP Accumulator)
; -----------------------------------------------------------------------------
; These functions operate on the FP accumulator and operator areas.
; Load operands into FP_ACC and FP_OPR before calling.
; Result appears in FP_ACC.

FP_ADD          EQU     MT_FADD     ; $52 - Add: ACC = ACC + OPR
FP_SUB          EQU     MT_FSUB     ; $5A - Subtract: ACC = ACC - OPR
FP_MUL          EQU     MT_FMUL     ; $58 - Multiply: ACC = ACC * OPR
FP_DIV          EQU     MT_FDIV     ; $57 - Divide: ACC = OPR / ACC
                                    ; Note: Division is OPR/ACC, not ACC/OPR!

; Unary operation
FP_NEG          EQU     MT_FNGT     ; $59 - Negate: X = -X (in place at address X)
                                    ; Input: X = address of 8-byte FP number

; -----------------------------------------------------------------------------
; Conversion Functions
; -----------------------------------------------------------------------------

; String to FP (like OPL's VAL function)
; Input: X = string address, D = destination address for FP result
; Output: X = first unconvertible character, result at destination
; Error: 252 if conversion fails
FP_BTOF         EQU     MT_BTOF     ; $51 - ASCII to FP

; FP to String (various formats)
; Input: FP number must be in accumulator (FP_ACC)
;        A = max string length
;        B = decimal places (or negative for auto in FBGN)
;        X = output buffer address
; Output: B = actual string length, string at X (NOT null-terminated)
FP_TOSTR        EQU     MT_FBGN     ; $55 - General format (auto-select)
FP_TODEC        EQU     MT_FBDC     ; $53 - Fixed decimal (e.g., "3.1416")
FP_TOEXP        EQU     MT_FBEX     ; $54 - Exponential (e.g., "3.14E+00")
FP_TOINT        EQU     MT_FBIN     ; $56 - Integer (rounded, no decimal)

; =============================================================================
; LZ-Specific Floating Point Services
; =============================================================================
; These services are ONLY available on LA/LZ/LZ64 models.
; Using them on CM/XP will cause undefined behavior or crash.
;
; Use conditional assembly to include these only for LZ targets:
;   #IFDEF __PSION_4LINE__
;       ... LZ-specific code ...
;   #ENDIF

#IFDEF __PSION_4LINE__

; Additional inverse trig functions (LZ only)
FP_ASIN         EQU     $AC         ; Arcsine - replaces stack top
FP_ACOS         EQU     $AD         ; Arccosine - replaces stack top

; Statistical functions (operate on FP lists)
; Input: Push word containing count, then push list address onto runtime stack
; Output: Result pushed onto stack
FP_SUM          EQU     $89         ; Sum of FP list
FP_MEAN         EQU     $8A         ; Mean (average) of FP list
FP_VAR          EQU     $8B         ; Variance of FP list
FP_STD          EQU     $8C         ; Standard deviation of FP list
FP_MIN          EQU     $8D         ; Minimum of FP list
FP_MAX          EQU     $8E         ; Maximum of FP list

#ENDIF ; __PSION_4LINE__

; =============================================================================
; Error Codes for Floating Point Operations
; =============================================================================
; These error codes may be returned by FP functions. Check carry flag after
; SWI to detect errors, then examine A or B for error code.

FPE_NONE        EQU     0           ; No error
FPE_RANGE       EQU     247         ; Argument out of valid range (e.g., sqrt(-1))
FPE_LIST        EQU     249         ; Invalid list parameter (LZ stat functions)
FPE_TOSTR       EQU     250         ; Number to string conversion error
FPE_DIVZERO     EQU     251         ; Division by zero
FPE_TOFLT       EQU     252         ; String to number conversion error
FPE_OVERFLOW    EQU     253         ; Arithmetic overflow

; =============================================================================
; Floating Point Constants
; =============================================================================
; Common mathematical constants in Psion FP format.
; These can be copied to working memory for use in calculations.
;
; FORMAT: 8 bytes - exponent+sign, then 7 BCD mantissa bytes
;
; To use: Copy 8 bytes to your FP variable, then use in operations
;   LDX     #FP_CONST_PI
;   LDD     #my_pi
;   JSR     __fp_copy8          ; From fpruntime.inc

; Pi = 3.14159265358979...
; Exponent: $41 (65 = bias 64 + 1, so 10^1 range, sign bit 0)
; Mantissa: 31 41 59 26 53 58 97 (BCD for 3.141592653589793)
FP_CONST_PI:
        FCB     $41             ; Exponent + sign (positive, 10^1)
        FCB     $31, $41, $59   ; 3.14159...
        FCB     $26, $53, $58   ; ...265358...
        FCB     $97             ; ...9793

; e = 2.71828182845904...
FP_CONST_E:
        FCB     $41             ; Exponent + sign
        FCB     $27, $18, $28   ; 2.71828...
        FCB     $18, $28, $45   ; ...182845...
        FCB     $90             ; ...904

; Zero = 0.0
FP_CONST_ZERO:
        FCB     $00, $00, $00, $00
        FCB     $00, $00, $00, $00

; One = 1.0
; Exponent: $41 (10^1 range), Mantissa: 10 00 00 00 00 00 00
FP_CONST_ONE:
        FCB     $41             ; Exponent + sign
        FCB     $10, $00, $00   ; 1.0000...
        FCB     $00, $00, $00
        FCB     $00

; =============================================================================
; Floating Point Macros
; =============================================================================
; These macros simplify common FP operations in assembly code.

; -----------------------------------------------------------------------------
; FP_CALL_UNARY - Call a unary FP function (sin, cos, sqrt, etc.)
; -----------------------------------------------------------------------------
; Usage: FP_CALL_UNARY FP_SIN
;
; Assumes: Input FP number already on runtime stack (via __fp_push_rts)
; Result: Replaces input on runtime stack (retrieve via __fp_pop_rts)
;
; Example:
;   LDX     #my_angle
;   JSR     __fp_push_rts       ; Push angle to runtime stack
;   FP_CALL_UNARY FP_SIN        ; Call sine function
;   LDX     #my_result
;   JSR     __fp_pop_rts        ; Pop result
; -----------------------------------------------------------------------------
MACRO FP_CALL_UNARY, service
    SWI
    FCB     \service
ENDM

; -----------------------------------------------------------------------------
; FP_NEGATE - Negate FP number in place
; -----------------------------------------------------------------------------
; Usage: FP_NEGATE addr
;
; Input: addr = address of 8-byte FP number
; Output: Number at addr is negated (sign bit flipped)
;
; Example:
;   FP_NEGATE my_value      ; my_value = -my_value
; -----------------------------------------------------------------------------
MACRO FP_NEGATE, addr
    LDX     #\addr
    SWI
    FCB     MT_FNGT
ENDM

; -----------------------------------------------------------------------------
; FP_STR_TO_FP - Convert ASCII string to floating point
; -----------------------------------------------------------------------------
; Usage: FP_STR_TO_FP str_addr, fp_dest
;
; Input: str_addr = address of ASCII string (e.g., "3.14159")
;        fp_dest = address to store 8-byte FP result
; Output: FP number at fp_dest
; Clobbers: D, X
;
; Example:
;   FP_STR_TO_FP str_pi, my_pi
;   ; my_pi now contains the FP representation of pi
;
; str_pi: FCC "3.14159"
;         FCB 0
; my_pi:  RMB 8
; -----------------------------------------------------------------------------
MACRO FP_STR_TO_FP, str_addr, fp_dest
    LDX     #\str_addr
    LDD     #\fp_dest
    SWI
    FCB     MT_BTOF
ENDM

; -----------------------------------------------------------------------------
; FP_PRINT - Print FP number to display (general format)
; -----------------------------------------------------------------------------
; Usage: FP_PRINT fp_addr, buffer, max_len, decimals
;
; Input: fp_addr = address of 8-byte FP number
;        buffer = address of output string buffer
;        max_len = maximum string length (constant)
;        decimals = decimal places (constant, negative for auto)
; Output: String in buffer, B = actual length
; Clobbers: A, B, X, FP_ACC
;
; NOTE: String is NOT null-terminated. Use B for length.
;
; Example:
;   FP_PRINT my_value, str_buf, 16, 4
;   ; str_buf contains ASCII representation, B = length
; -----------------------------------------------------------------------------
MACRO FP_PRINT, fp_addr, buffer, max_len, decimals
    ; Copy FP number to accumulator
    LDX     #\fp_addr
    JSR     __fp_to_acc
    ; Set up conversion parameters
    LDAA    #\max_len       ; A = max string length
    LDAB    #\decimals      ; B = decimal places
    LDX     #\buffer        ; X = output buffer
    ; Call conversion
    SWI
    FCB     MT_FBGN         ; General format
ENDM

; =============================================================================
; End of float.inc
; =============================================================================
