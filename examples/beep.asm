; =============================================================================
; BEEP.ASM - Beep Pattern Demo for Psion Organiser II
; =============================================================================
; This program demonstrates:
;   - Using the buzzer system calls
;   - Timing delays with TM_WAIT
;   - Loop structures with counter
;   - Using stack to preserve registers
;
; To assemble:
;   psasm -o beep.ob3 beep.asm
;
; Reference: https://www.jaapsch.net/psion/
; =============================================================================

        INCLUDE "psion.inc"

        ORG     $2100

; =============================================================================
; Constants
; =============================================================================

BEEP_COUNT      EQU     5       ; Number of beeps
DELAY_TICKS     EQU     16      ; Delay between beeps (~0.5 second)

; =============================================================================
; Main Entry Point
; =============================================================================

START:
        ; Initialize beep counter
        LDAB    #BEEP_COUNT     ; B = loop counter

BEEP_LOOP:
        ; Sound the beep
        BEEP                    ; Use macro for BZ_BELL

        ; Delay between beeps
        PSHB                    ; Save counter
        LDD     #DELAY_TICKS    ; Load delay time
        LDAA    #TM_WAIT        ; Timer wait service
        SWI                     ; Call OS
        PULB                    ; Restore counter

        ; Decrement and loop
        DECB                    ; B = B - 1
        BNE     BEEP_LOOP       ; Loop if not zero

        ; Done
        RTS

; =============================================================================
; End of Program
; =============================================================================
