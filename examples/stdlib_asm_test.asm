; =============================================================================
; stdlib_asm_test.asm - Assembly Standard Library Test for Psion Organiser II
; =============================================================================
;
; This program tests the assembly-level standard library support:
;   - ctype.inc : Character classification macros (IS_DIGIT, TO_UPPER, etc.)
;   - stdio.inc : String function macros (STRRCHR, STRSTR, etc.)
;
; PURPOSE:
;   Validates that assembly programmers can use the stdlib functions via
;   the provided macros in ctype.inc and stdio.inc.
;
; BUILD:
;   psbuild -m LZ stdlib_asm_test.asm -o ASMTEST.opk
;
; Author: Hugo José Pinto & Contributors
; Part of the Psion Organiser II SDK
; =============================================================================

        INCLUDE "psion.inc"         ; Core definitions
        INCLUDE "runtime.inc"       ; C runtime (provides string functions)
        INCLUDE "stdio.inc"         ; Extended string functions with macros
        INCLUDE "ctype.inc"         ; Character classification macros

        ORG     $2100

; =============================================================================
; Entry Point
; =============================================================================

start:
        ; Initialize test counter
        CLR     pass_count
        CLR     fail_count

        ; Show title
        CLRSCR
        LDX     #title_msg
        LDAB    #17
        SWI
        FCB     DP_PRNT

        PAUSE   64                  ; Wait 2 seconds

; -----------------------------------------------------------------------------
; TEST 1: Character Constants
; -----------------------------------------------------------------------------
test_constants:
        CLRSCR
        LDX     #const_msg
        LDAB    #14
        SWI
        FCB     DP_PRNT

        ; Test that CHAR_0 = $30 (48)
        LDAA    #CHAR_0
        CMPA    #$30
        BNE     const_fail
        ; Test that CHAR_A = $41 (65)
        LDAA    #CHAR_A
        CMPA    #$41
        BNE     const_fail
        ; Test that CHAR_a = $61 (97)
        LDAA    #CHAR_a
        CMPA    #$61
        BNE     const_fail
        ; Test CASE_OFFSET = 32
        LDAA    #CASE_OFFSET
        CMPA    #$20
        BNE     const_fail

        BSR     show_pass
        BRA     test_toupper

const_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; TEST 2: TO_UPPER macro
; -----------------------------------------------------------------------------
test_toupper:
        CURSOR  1, 0                ; Row 1, col 0

        LDX     #toupper_msg
        LDAB    #9
        SWI
        FCB     DP_PRNT

        ; Test: 'a' -> 'A'
        LDAA    #'a'
        TO_UPPER
        CMPA    #'A'
        BNE     toupper_fail

        ; Test: 'z' -> 'Z'
        LDAA    #'z'
        TO_UPPER
        CMPA    #'Z'
        BNE     toupper_fail

        ; Test: 'A' unchanged
        LDAA    #'A'
        TO_UPPER
        CMPA    #'A'
        BNE     toupper_fail

        ; Test: '5' unchanged
        LDAA    #'5'
        TO_UPPER
        CMPA    #'5'
        BNE     toupper_fail

        BSR     show_pass
        BRA     test_tolower

toupper_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; TEST 3: TO_LOWER macro
; -----------------------------------------------------------------------------
test_tolower:
        CURSOR  2, 0                ; Row 2, col 0

        LDX     #tolower_msg
        LDAB    #9
        SWI
        FCB     DP_PRNT

        ; Test: 'A' -> 'a'
        LDAA    #'A'
        TO_LOWER
        CMPA    #'a'
        BNE     tolower_fail

        ; Test: 'Z' -> 'z'
        LDAA    #'Z'
        TO_LOWER
        CMPA    #'z'
        BNE     tolower_fail

        ; Test: 'a' unchanged
        LDAA    #'a'
        TO_LOWER
        CMPA    #'a'
        BNE     tolower_fail

        BSR     show_pass
        BRA     test_digit_conv

tolower_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; TEST 4: CHAR_TO_DIGIT and DIGIT_TO_CHAR
; -----------------------------------------------------------------------------
test_digit_conv:
        CURSOR  3, 0                ; Row 3, col 0

        LDX     #digit_msg
        LDAB    #11
        SWI
        FCB     DP_PRNT

        ; Test: '5' -> 5
        LDAA    #'5'
        CHAR_TO_DIGIT
        CMPA    #5
        BNE     digit_fail

        ; Test: 7 -> '7'
        LDAA    #7
        DIGIT_TO_CHAR
        CMPA    #'7'
        BNE     digit_fail

        BSR     show_pass
        BRA     wait_section1

digit_fail:
        BSR     show_fail

wait_section1:
        GETKEY
        ; Fall through to next section

; -----------------------------------------------------------------------------
; TEST 5: HEX_TO_CHAR macro
; -----------------------------------------------------------------------------
test_hex_char:
        CLRSCR

        LDX     #hexconv_msg
        LDAB    #12
        SWI
        FCB     DP_PRNT

        ; Test: 0 -> '0'
        LDAA    #0
        HEX_TO_CHAR
        CMPA    #'0'
        BNE     hex_fail

        ; Test: 9 -> '9'
        LDAA    #9
        HEX_TO_CHAR
        CMPA    #'9'
        BNE     hex_fail

        ; Test: 10 -> 'A'
        LDAA    #10
        HEX_TO_CHAR
        CMPA    #'A'
        BNE     hex_fail

        ; Test: 15 -> 'F'
        LDAA    #15
        HEX_TO_CHAR
        CMPA    #'F'
        BNE     hex_fail

        BSR     show_pass
        BRA     test_strrchr_asm

hex_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; TEST 6: STRRCHR macro (from stdio.inc)
; -----------------------------------------------------------------------------
test_strrchr_asm:
        CURSOR  1, 0

        LDX     #strrchr_msg
        LDAB    #7
        SWI
        FCB     DP_PRNT

        ; Test: Find last '/' in "/a/b/c"
        STRRCHR path_str, '/'
        ; D should point to the last '/'
        CPD     #0
        BEQ     strrchr_fail

        ; Check that next char is 'c'
        XGDX                        ; X = result pointer
        LDAA    1,X                 ; A = char after '/'
        CMPA    #'c'
        BNE     strrchr_fail

        BSR     show_pass
        BRA     test_strstr_asm

strrchr_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; TEST 7: STRSTR macro (from stdio.inc)
; -----------------------------------------------------------------------------
test_strstr_asm:
        CURSOR  2, 0

        LDX     #strstr_msg
        LDAB    #6
        SWI
        FCB     DP_PRNT

        ; Test: Find "World" in "Hello World"
        STRSTR hello_str, world_str
        CPD     #0
        BEQ     strstr_fail

        ; Check that it points to 'W'
        XGDX
        LDAA    0,X
        CMPA    #'W'
        BNE     strstr_fail

        BSR     show_pass
        BRA     test_summary

strstr_fail:
        BSR     show_fail

; -----------------------------------------------------------------------------
; SUMMARY
; -----------------------------------------------------------------------------
test_summary:
        CURSOR  3, 0

        LDX     #summary_msg
        LDAB    #2
        SWI
        FCB     DP_PRNT

        ; Print pass count
        LDAB    pass_count
        CLRA
        LDX     #num_buf
        SWI
        FCB     $7A                 ; UT_UTOB
        LDX     #num_buf
        SWI
        FCB     DP_PRNT

        ; Print "/"
        LDAA    #'/'
        SWI
        FCB     DP_EMIT

        ; Print total (pass + fail)
        LDAB    pass_count
        ADDB    fail_count
        CLRA
        LDX     #num_buf
        SWI
        FCB     $7A                 ; UT_UTOB
        LDX     #num_buf
        SWI
        FCB     DP_PRNT

        ; Wait for key
        GETKEY
        RTS

; =============================================================================
; HELPER SUBROUTINES
; =============================================================================

; -----------------------------------------------------------------------------
; show_pass - Display "OK" and increment pass counter
; -----------------------------------------------------------------------------
show_pass:
        LDX     #ok_msg
        LDAB    #3
        SWI
        FCB     DP_PRNT
        INC     pass_count
        RTS

; -----------------------------------------------------------------------------
; show_fail - Display "FAIL" and increment fail counter
; -----------------------------------------------------------------------------
show_fail:
        LDX     #fail_msg
        LDAB    #4
        SWI
        FCB     DP_PRNT
        INC     fail_count
        RTS

; =============================================================================
; DATA SECTION
; =============================================================================

; --- Messages ---
title_msg:      FCC "ASM STDLIB TEST"
                FCB $0D, $0A        ; CRLF for spacing
const_msg:      FCC "CONST TEST:   "
toupper_msg:    FCC "TOUPPER: "
tolower_msg:    FCC "TOLOWER: "
digit_msg:      FCC "DIGIT CVT: "
hexconv_msg:    FCC "HEX_TO_CHAR:"
strrchr_msg:    FCC "STRRCHR:"
strstr_msg:     FCC "STRSTR:"
summary_msg:    FCC "P:"
ok_msg:         FCC " OK"
fail_msg:       FCC "FAIL"

; --- Test strings ---
path_str:       FCC "/a/b/c"
                FCB 0

hello_str:      FCC "Hello World"
                FCB 0

world_str:      FCC "World"
                FCB 0

; --- Variables ---
pass_count:     RMB 1
fail_count:     RMB 1
num_buf:        RMB 8

        END
