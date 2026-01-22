; =============================================================================
; CTYPE.INC - Character Classification and Conversion for HD6303 Assembly
; =============================================================================
;
; This file provides character classification constants, macros, and inline
; tests for HD6303 assembly programs on the Psion Organiser II. It is the
; assembly equivalent of ctype.h for C programmers.
;
; USAGE:
;   INCLUDE "psion.inc"     ; Core definitions
;   INCLUDE "ctype.inc"     ; Character classification (this file)
;
; This file provides:
;   1. Character code constants (CHAR_0, CHAR_A, etc.)
;   2. Character range constants (for comparisons)
;   3. Inline test macros (IS_DIGIT, IS_ALPHA, etc.)
;   4. Case conversion macros (TO_UPPER, TO_LOWER)
;
; DESIGN PHILOSOPHY:
;   Assembly programmers often prefer direct comparisons over function calls
;   for performance. These macros expand to efficient inline code, similar
;   to how C macros in ctype.h expand to inline comparisons.
;
; REGISTER CONVENTIONS:
;   - IS_* macros test the value in the A register
;   - Result: Z flag set (BEQ branches) if character IS in class
;   - A register is preserved; only flags are modified
;   - Some macros use B as scratch; document where applicable
;
; ASCII REFERENCE (for documentation):
;   '0'-'9' = $30-$39 (48-57)
;   'A'-'Z' = $41-$5A (65-90)
;   'a'-'z' = $61-$7A (97-122)
;   ' '     = $20 (32)
;   '\t'    = $09 (9)
;   '\n'    = $0A (10)
;   '\r'    = $0D (13)
;
; Author: Hugo José Pinto & Contributors
; Part of the Psion Organiser II SDK
; See: specs/12-standard-library-expansion.md
; =============================================================================

; =============================================================================
; CHARACTER CODE CONSTANTS
; =============================================================================
; These constants provide symbolic names for commonly used character codes.
; Using these instead of raw numbers makes code more readable and maintainable.

; --- Digits ---
CHAR_0          EQU     $30             ; '0' = 48
CHAR_1          EQU     $31             ; '1' = 49
CHAR_2          EQU     $32             ; '2' = 50
CHAR_3          EQU     $33             ; '3' = 51
CHAR_4          EQU     $34             ; '4' = 52
CHAR_5          EQU     $35             ; '5' = 53
CHAR_6          EQU     $36             ; '6' = 54
CHAR_7          EQU     $37             ; '7' = 55
CHAR_8          EQU     $38             ; '8' = 56
CHAR_9          EQU     $39             ; '9' = 57

; --- Letter Constants ---
; NOTE: Individual letter constants (CHAR_A, CHAR_B, etc.) are NOT provided
; because the assembler is case-insensitive, causing CHAR_A and CHAR_a to
; collide. Use character literals instead: 'A', 'B', 'a', 'b', etc.
; For range checks, use UPPER_FIRST/UPPER_LAST and LOWER_FIRST/LOWER_LAST.

; --- Whitespace Characters ---
CHAR_SPACE      EQU     $20             ; Space = 32
CHAR_TAB        EQU     $09             ; Horizontal tab = 9
CHAR_LF         EQU     $0A             ; Line feed (newline) = 10
CHAR_CR         EQU     $0D             ; Carriage return = 13
CHAR_FF         EQU     $0C             ; Form feed = 12
CHAR_VT         EQU     $0B             ; Vertical tab = 11

; --- Special Characters ---
CHAR_NULL       EQU     $00             ; Null terminator = 0
CHAR_BELL       EQU     $07             ; Bell = 7
CHAR_BS         EQU     $08             ; Backspace = 8
CHAR_ESC        EQU     $1B             ; Escape = 27
CHAR_DEL        EQU     $7F             ; Delete = 127

; --- Common Punctuation ---
CHAR_BANG       EQU     $21             ; '!' = 33
CHAR_DQUOTE     EQU     $22             ; '"' = 34
CHAR_HASH       EQU     $23             ; '#' = 35
CHAR_DOLLAR     EQU     $24             ; '$' = 36
CHAR_PERCENT    EQU     $25             ; '%' = 37
CHAR_AMP        EQU     $26             ; '&' = 38
CHAR_SQUOTE     EQU     $27             ; ''' = 39
CHAR_LPAREN     EQU     $28             ; '(' = 40
CHAR_RPAREN     EQU     $29             ; ')' = 41
CHAR_STAR       EQU     $2A             ; '*' = 42
CHAR_PLUS       EQU     $2B             ; '+' = 43
CHAR_COMMA      EQU     $2C             ; ',' = 44
CHAR_MINUS      EQU     $2D             ; '-' = 45
CHAR_DOT        EQU     $2E             ; '.' = 46
CHAR_SLASH      EQU     $2F             ; '/' = 47
CHAR_COLON      EQU     $3A             ; ':' = 58
CHAR_SEMI       EQU     $3B             ; ';' = 59
CHAR_LT         EQU     $3C             ; '<' = 60
CHAR_EQ         EQU     $3D             ; '=' = 61
CHAR_GT         EQU     $3E             ; '>' = 62
CHAR_QUEST      EQU     $3F             ; '?' = 63
CHAR_AT         EQU     $40             ; '@' = 64
CHAR_LBRACK     EQU     $5B             ; '[' = 91
CHAR_BSLASH     EQU     $5C             ; '\' = 92
CHAR_RBRACK     EQU     $5D             ; ']' = 93
CHAR_CARET      EQU     $5E             ; '^' = 94
CHAR_UNDER      EQU     $5F             ; '_' = 95
CHAR_GRAVE      EQU     $60             ; '`' = 96
CHAR_LBRACE     EQU     $7B             ; '{' = 123
CHAR_PIPE       EQU     $7C             ; '|' = 124
CHAR_RBRACE     EQU     $7D             ; '}' = 125
CHAR_TILDE      EQU     $7E             ; '~' = 126

; =============================================================================
; CHARACTER RANGE CONSTANTS
; =============================================================================
; These define the boundaries of character classes for range comparisons.

; Digit range: '0'-'9'
DIGIT_FIRST     EQU     $30             ; '0'
DIGIT_LAST      EQU     $39             ; '9'

; Uppercase range: 'A'-'Z'
UPPER_FIRST     EQU     $41             ; 'A'
UPPER_LAST      EQU     $5A             ; 'Z'

; Lowercase range: 'a'-'z'
LOWER_FIRST     EQU     $61             ; 'a'
LOWER_LAST      EQU     $7A             ; 'z'

; Hex letter range (additional to digits)
HEX_UPPER_FIRST EQU     $41             ; 'A'
HEX_UPPER_LAST  EQU     $46             ; 'F'
HEX_LOWER_FIRST EQU     $61             ; 'a'
HEX_LOWER_LAST  EQU     $66             ; 'f'

; Printable range (including space)
PRINT_FIRST     EQU     $20             ; Space
PRINT_LAST      EQU     $7E             ; '~'

; Control character ranges
CTRL_FIRST      EQU     $00             ; NUL
CTRL_LAST       EQU     $1F             ; US (Unit Separator)

; ASCII range
ASCII_LAST      EQU     $7F             ; DEL (highest 7-bit ASCII)

; Case conversion offset ('a' - 'A' = 32)
CASE_OFFSET     EQU     $20             ; Add to uppercase to get lowercase

; =============================================================================
; INLINE CHARACTER TEST MACROS
; =============================================================================
; These macros test whether a character (in register A) belongs to a
; particular character class. After the macro, use conditional branches:
;   - BEQ/BNE: Branch if character IS/IS NOT in the class
;
; Design: Each macro sets flags without destroying the A register value.
; The macros use comparison sequences that leave the Z flag correctly set.
;
; IMPORTANT: These macros use local labels with \@ suffix to ensure
; uniqueness when the macro is used multiple times.

; -----------------------------------------------------------------------------
; IS_DIGIT - Test if character is decimal digit '0'-'9'
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if digit, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B (used as scratch)
;
; Algorithm: Check if DIGIT_FIRST <= A <= DIGIT_LAST
;
; Usage:
;   LDAA    some_char
;   IS_DIGIT
;   BEQ     handle_digit  ; Branch if it's a digit
; -----------------------------------------------------------------------------
MACRO IS_DIGIT
    PSHB                        ; Save B
    TAB                         ; B = A (copy char)
    SUBB    #DIGIT_FIRST        ; B = char - '0'
    BLO     .isdig_no\@         ; If < '0', not a digit
    CMPB    #(DIGIT_LAST-DIGIT_FIRST)  ; Compare with range
    BHI     .isdig_no\@         ; If > 9, not a digit
    PULB                        ; Restore B
    CLRA                        ; Set Z=1 (is digit)
    TAB                         ; Preserve the original A by reloading from working copy
    BRA     .isdig_end\@
.isdig_no\@:
    PULB                        ; Restore B
    LDAB    #1                  ; Set Z=0 (not digit) - use B as scratch
    TSTB                        ; B != 0, so Z=0
.isdig_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_UPPER - Test if character is uppercase letter 'A'-'Z'
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if uppercase, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
;
; Usage:
;   LDAA    some_char
;   IS_UPPER
;   BEQ     is_uppercase
; -----------------------------------------------------------------------------
MACRO IS_UPPER
    PSHB
    TAB
    SUBB    #UPPER_FIRST
    BLO     .isup_no\@
    CMPB    #(UPPER_LAST-UPPER_FIRST)
    BHI     .isup_no\@
    PULB
    CLRA
    TAB
    BRA     .isup_end\@
.isup_no\@:
    PULB
    LDAB    #1
    TSTB
.isup_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_LOWER - Test if character is lowercase letter 'a'-'z'
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if lowercase, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
; -----------------------------------------------------------------------------
MACRO IS_LOWER
    PSHB
    TAB
    SUBB    #LOWER_FIRST
    BLO     .islo_no\@
    CMPB    #(LOWER_LAST-LOWER_FIRST)
    BHI     .islo_no\@
    PULB
    CLRA
    TAB
    BRA     .islo_end\@
.islo_no\@:
    PULB
    LDAB    #1
    TSTB
.islo_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_ALPHA - Test if character is alphabetic (A-Z or a-z)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if alpha, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
;
; Algorithm: Check uppercase range first, then lowercase
; -----------------------------------------------------------------------------
MACRO IS_ALPHA
    PSHB
    TAB
    ; Check uppercase 'A'-'Z'
    SUBB    #UPPER_FIRST
    BLO     .isal_try_lower\@
    CMPB    #(UPPER_LAST-UPPER_FIRST)
    BLS     .isal_yes\@          ; Is uppercase letter
.isal_try_lower\@:
    ; Check lowercase 'a'-'z'
    TAB                          ; Reload original
    SUBB    #LOWER_FIRST
    BLO     .isal_no\@
    CMPB    #(LOWER_LAST-LOWER_FIRST)
    BHI     .isal_no\@
.isal_yes\@:
    PULB
    CLRA
    TAB
    BRA     .isal_end\@
.isal_no\@:
    PULB
    LDAB    #1
    TSTB
.isal_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_ALNUM - Test if character is alphanumeric (A-Z, a-z, or 0-9)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if alphanumeric, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
; -----------------------------------------------------------------------------
MACRO IS_ALNUM
    PSHB
    TAB
    ; Check digit '0'-'9'
    SUBB    #DIGIT_FIRST
    BLO     .isalnum_try_alpha\@
    CMPB    #(DIGIT_LAST-DIGIT_FIRST)
    BLS     .isalnum_yes\@
.isalnum_try_alpha\@:
    ; Check uppercase 'A'-'Z'
    TAB
    SUBB    #UPPER_FIRST
    BLO     .isalnum_try_lower\@
    CMPB    #(UPPER_LAST-UPPER_FIRST)
    BLS     .isalnum_yes\@
.isalnum_try_lower\@:
    ; Check lowercase 'a'-'z'
    TAB
    SUBB    #LOWER_FIRST
    BLO     .isalnum_no\@
    CMPB    #(LOWER_LAST-LOWER_FIRST)
    BHI     .isalnum_no\@
.isalnum_yes\@:
    PULB
    CLRA
    TAB
    BRA     .isalnum_end\@
.isalnum_no\@:
    PULB
    LDAB    #1
    TSTB
.isalnum_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_XDIGIT - Test if character is hexadecimal digit (0-9, A-F, a-f)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if hex digit, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
; -----------------------------------------------------------------------------
MACRO IS_XDIGIT
    PSHB
    TAB
    ; Check digit '0'-'9'
    SUBB    #DIGIT_FIRST
    BLO     .isxd_try_upper\@
    CMPB    #(DIGIT_LAST-DIGIT_FIRST)
    BLS     .isxd_yes\@
.isxd_try_upper\@:
    ; Check uppercase 'A'-'F'
    TAB
    SUBB    #HEX_UPPER_FIRST
    BLO     .isxd_try_lower\@
    CMPB    #(HEX_UPPER_LAST-HEX_UPPER_FIRST)
    BLS     .isxd_yes\@
.isxd_try_lower\@:
    ; Check lowercase 'a'-'f'
    TAB
    SUBB    #HEX_LOWER_FIRST
    BLO     .isxd_no\@
    CMPB    #(HEX_LOWER_LAST-HEX_LOWER_FIRST)
    BHI     .isxd_no\@
.isxd_yes\@:
    PULB
    CLRA
    TAB
    BRA     .isxd_end\@
.isxd_no\@:
    PULB
    LDAB    #1
    TSTB
.isxd_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_SPACE - Test if character is whitespace (space, tab, newline, etc.)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if whitespace, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags
;
; Whitespace characters: space ($20), tab ($09), LF ($0A), CR ($0D),
;                        form feed ($0C), vertical tab ($0B)
; -----------------------------------------------------------------------------
MACRO IS_SPACE
    CMPA    #CHAR_SPACE         ; Space
    BEQ     .issp_yes\@
    CMPA    #CHAR_TAB           ; Tab
    BEQ     .issp_yes\@
    CMPA    #CHAR_LF            ; Line feed
    BEQ     .issp_yes\@
    CMPA    #CHAR_CR            ; Carriage return
    BEQ     .issp_yes\@
    CMPA    #CHAR_FF            ; Form feed
    BEQ     .issp_yes\@
    CMPA    #CHAR_VT            ; Vertical tab
    BEQ     .issp_yes\@
    ; Not whitespace - set Z=0
    PSHA
    LDAA    #1
    TSTA                        ; Z=0
    PULA
    BRA     .issp_end\@
.issp_yes\@:
    ; Is whitespace - Z=1 (already set by CMPA)
.issp_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_PRINT - Test if character is printable (space through ~)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if printable, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags, B
;
; Printable: $20 (space) through $7E (~)
; -----------------------------------------------------------------------------
MACRO IS_PRINT
    PSHB
    TAB
    SUBB    #PRINT_FIRST
    BLO     .ispr_no\@
    CMPB    #(PRINT_LAST-PRINT_FIRST)
    BHI     .ispr_no\@
    PULB
    CLRA
    TAB
    BRA     .ispr_end\@
.ispr_no\@:
    PULB
    LDAB    #1
    TSTB
.ispr_end\@:
ENDM

; -----------------------------------------------------------------------------
; IS_CNTRL - Test if character is control character (0-31 or 127)
; -----------------------------------------------------------------------------
; Input:  A = character to test
; Output: Z=1 (BEQ) if control, Z=0 (BNE) if not
; Preserves: A, X
; Clobbers: Flags
; -----------------------------------------------------------------------------
MACRO IS_CNTRL
    CMPA    #CHAR_DEL           ; DEL (127) is also control
    BEQ     .isct_yes\@
    CMPA    #CTRL_LAST          ; Compare with $1F
    BHI     .isct_no\@          ; > $1F means not control (except DEL)
    ; A <= $1F, is control
.isct_yes\@:
    ; Set Z=1 (but we may have arrived via BEQ which already set it)
    BRA     .isct_end\@
.isct_no\@:
    ; Set Z=0
    PSHA
    LDAA    #1
    TSTA
    PULA
.isct_end\@:
ENDM

; =============================================================================
; CASE CONVERSION MACROS
; =============================================================================
; These macros convert characters between uppercase and lowercase.

; -----------------------------------------------------------------------------
; TO_UPPER - Convert lowercase to uppercase
; -----------------------------------------------------------------------------
; Input:  A = character to convert
; Output: A = uppercase version (unchanged if not lowercase)
; Preserves: X
; Clobbers: Flags, B
;
; Algorithm: If 'a' <= A <= 'z', subtract 32
; -----------------------------------------------------------------------------
MACRO TO_UPPER
    PSHB
    TAB
    SUBB    #LOWER_FIRST        ; B = A - 'a'
    BLO     .toup_done\@        ; A < 'a', no conversion
    CMPB    #(LOWER_LAST-LOWER_FIRST)
    BHI     .toup_done\@        ; A > 'z', no conversion
    ; A is lowercase, convert
    SUBA    #CASE_OFFSET        ; A = A - 32
.toup_done\@:
    PULB
ENDM

; -----------------------------------------------------------------------------
; TO_LOWER - Convert uppercase to lowercase
; -----------------------------------------------------------------------------
; Input:  A = character to convert
; Output: A = lowercase version (unchanged if not uppercase)
; Preserves: X
; Clobbers: Flags, B
;
; Algorithm: If 'A' <= A <= 'Z', add 32
; -----------------------------------------------------------------------------
MACRO TO_LOWER
    PSHB
    TAB
    SUBB    #UPPER_FIRST        ; B = A - 'A'
    BLO     .tolo_done\@        ; A < 'A', no conversion
    CMPB    #(UPPER_LAST-UPPER_FIRST)
    BHI     .tolo_done\@        ; A > 'Z', no conversion
    ; A is uppercase, convert
    ADDA    #CASE_OFFSET        ; A = A + 32
.tolo_done\@:
    PULB
ENDM

; -----------------------------------------------------------------------------
; TO_ASCII - Mask character to 7-bit ASCII
; -----------------------------------------------------------------------------
; Input:  A = character to mask
; Output: A = A & $7F (high bit cleared)
; Preserves: X, B
; Clobbers: Flags
; -----------------------------------------------------------------------------
MACRO TO_ASCII
    ANDA    #ASCII_LAST         ; A = A & $7F
ENDM

; =============================================================================
; DIGIT VALUE MACROS
; =============================================================================
; These macros convert between character codes and numeric values.

; -----------------------------------------------------------------------------
; CHAR_TO_DIGIT - Convert ASCII digit '0'-'9' to numeric value 0-9
; -----------------------------------------------------------------------------
; Input:  A = ASCII digit character ('0'-'9')
; Output: A = numeric value (0-9)
;         If not a digit, result is undefined
; Preserves: X, B
; Clobbers: Flags
;
; Usage:
;   LDAA    #'5'
;   CHAR_TO_DIGIT       ; A = 5
; -----------------------------------------------------------------------------
MACRO CHAR_TO_DIGIT
    SUBA    #CHAR_0             ; A = A - '0'
ENDM

; -----------------------------------------------------------------------------
; DIGIT_TO_CHAR - Convert numeric value 0-9 to ASCII digit '0'-'9'
; -----------------------------------------------------------------------------
; Input:  A = numeric value (0-9)
; Output: A = ASCII character ('0'-'9')
;         If value > 9, result is undefined
; Preserves: X, B
; Clobbers: Flags
;
; Usage:
;   LDAA    #5
;   DIGIT_TO_CHAR       ; A = '5' ($35)
; -----------------------------------------------------------------------------
MACRO DIGIT_TO_CHAR
    ADDA    #CHAR_0             ; A = A + '0'
ENDM

; -----------------------------------------------------------------------------
; HEX_TO_CHAR - Convert hex value 0-15 to ASCII hex digit
; -----------------------------------------------------------------------------
; Input:  A = hex value (0-15)
; Output: A = ASCII character ('0'-'9' or 'A'-'F')
;         If value > 15, result is undefined
; Preserves: X, B
; Clobbers: Flags
;
; Usage:
;   LDAA    #12
;   HEX_TO_CHAR         ; A = 'C' ($43)
; -----------------------------------------------------------------------------
MACRO HEX_TO_CHAR
    CMPA    #10
    BLO     .htc_digit\@
    ; A >= 10: 'A' + (A - 10)
    ADDA    #(UPPER_FIRST - 10)     ; UPPER_FIRST='A', avoids CHAR_A/CHAR_a collision
    BRA     .htc_done\@
.htc_digit\@:
    ; A < 10: '0' + A
    ADDA    #CHAR_0
.htc_done\@:
ENDM

; =============================================================================
; UTILITY CONSTANTS FOR COMMON PATTERNS
; =============================================================================
; These provide convenient values for common assembly patterns.

; Newline string (for printing line breaks)
; Use: LDX #NEWLINE_STR; LDAB #1; JSR DP_PRNT
NEWLINE_BYTE    EQU     CHAR_LF         ; Standard newline character

; =============================================================================
; End of ctype.inc
; =============================================================================
