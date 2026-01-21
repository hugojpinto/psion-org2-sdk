; =============================================================================
; optimizer_test.asm - Demonstrates peephole optimizer benefits
; =============================================================================
;
; This assembly program contains patterns that the optimizer can improve.
; Assemble with and without optimization to see the difference:
;
;   With optimization (default):
;     psasm -I include optimizer_test.asm -o /tmp/OPTTEST.ob3
;
;   Without optimization:
;     psasm --no-optimize -I include optimizer_test.asm -o /tmp/OPTTEST.ob3
;
; Expected optimization results:
;   - 2 compare zero (CMPA #0 -> TSTA, CMPB #0 -> TSTB)
;   - 2 push/pull pairs eliminated
;   - 1 redundant load removed
;   - 4 dead code instructions removed
;   - Total: 9 optimizations, ~14 bytes saved
;
; Patterns demonstrated:
;   1. CMPA #0 -> TSTA (saves 1 byte each)
;   2. CMPB #0 -> TSTB (saves 1 byte each)
;   3. PSHA + PULA -> eliminated (saves 2 bytes each pair)
;   4. Redundant loads -> eliminated (saves 2 bytes)
;   5. Dead code after RTS -> eliminated (varies)
;
; Note: The C compiler (pscc) generates SUBD #0 for comparisons, which
; is not optimized. These patterns are more common in hand-written assembly.
; =============================================================================

        INCLUDE "psion.inc"

; -----------------------------------------------------------------------------
; Entry point
; -----------------------------------------------------------------------------
_entry:
        BSR     main
        RTS

; -----------------------------------------------------------------------------
; Pattern 1: CMPA #0 -> TSTA (called 4 times, saves 4 bytes)
; -----------------------------------------------------------------------------
test_cmpa_zero:
        CMPA    #0              ; Optimizer converts to TSTA
        BEQ     is_zero_a
        LDAA    #'N'
        RTS
is_zero_a:
        LDAA    #'Y'
        RTS

; -----------------------------------------------------------------------------
; Pattern 2: CMPB #0 -> TSTB (called 4 times, saves 4 bytes)
; -----------------------------------------------------------------------------
test_cmpb_zero:
        CMPB    #0              ; Optimizer converts to TSTB
        BEQ     is_zero_b
        LDAB    #'N'
        RTS
is_zero_b:
        LDAB    #'Y'
        RTS

; -----------------------------------------------------------------------------
; Pattern 3: Push/Pull elimination (saves 2 bytes each pair)
; -----------------------------------------------------------------------------
test_push_pull:
        ; These push/pull pairs are redundant and get eliminated
        PSHA
        PULA                    ; Eliminated with above PSHA

        PSHB
        PULB                    ; Eliminated with above PSHB

        ; Do some actual work
        LDAA    #$41
        LDAB    #$42
        RTS

; -----------------------------------------------------------------------------
; Pattern 4: Redundant loads (saves 2 bytes)
; -----------------------------------------------------------------------------
test_redundant_load:
        LDAA    #$55
        LDAA    #$55            ; Redundant - eliminated
        RTS

; -----------------------------------------------------------------------------
; Pattern 5: Dead code elimination
; -----------------------------------------------------------------------------
test_dead_code:
        LDAA    #$99
        RTS
        ; Everything below is unreachable (dead code)
        LDAA    #$AA            ; Dead - eliminated
        LDAB    #$BB            ; Dead - eliminated
        NOP                     ; Dead - eliminated
        NOP                     ; Dead - eliminated
next_label:                     ; Label ends dead code region
        NOP                     ; This is reachable via label

; -----------------------------------------------------------------------------
; Main - exercises all patterns
; -----------------------------------------------------------------------------
main:
        ; Test CMPA #0 pattern multiple times
        LDAA    #0
        BSR     test_cmpa_zero  ; Pattern 1
        LDAA    #5
        BSR     test_cmpa_zero  ; Pattern 1
        LDAA    #0
        BSR     test_cmpa_zero  ; Pattern 1
        LDAA    #255
        BSR     test_cmpa_zero  ; Pattern 1

        ; Test CMPB #0 pattern multiple times
        LDAB    #0
        BSR     test_cmpb_zero  ; Pattern 2
        LDAB    #10
        BSR     test_cmpb_zero  ; Pattern 2
        LDAB    #0
        BSR     test_cmpb_zero  ; Pattern 2
        LDAB    #128
        BSR     test_cmpb_zero  ; Pattern 2

        ; Test push/pull elimination
        BSR     test_push_pull  ; Pattern 3

        ; Test redundant load
        BSR     test_redundant_load ; Pattern 4

        ; Test dead code (just calling it)
        BSR     test_dead_code  ; Pattern 5

        ; All tests complete - just return silently
        ; (No visible output - this tests internal optimization patterns)
        RTS

; End of program
