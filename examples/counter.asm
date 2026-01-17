; =============================================================================
; COUNTER.ASM - Display Counter for Psion Organiser II
; =============================================================================
; This program demonstrates:
;   - Converting numbers to ASCII for display
;   - Direct memory manipulation
;   - Loop with exit condition
;   - Multiple subroutine calls
;   - Using system variables for temporary storage
;
; The program displays numbers 0-99 on screen, incrementing
; when any key is pressed. Press ON/CLEAR to exit.
;
; To assemble:
;   psasm -o counter.ob3 counter.asm
;
; Reference: https://www.jaapsch.net/psion/
; =============================================================================

        INCLUDE "psion.inc"

        ORG     $2100

; =============================================================================
; Constants
; =============================================================================

MAX_COUNT       EQU     100     ; Count 0 to 99
ASCII_ZERO      EQU     '0'     ; ASCII code for '0'

; =============================================================================
; Main Entry Point
; =============================================================================

START:
        CLRA                    ; A = 0 (our counter)
        STAA    UTW_T0          ; Store counter in temp area

MAIN_LOOP:
        ; Display current count
        BSR     SHOW_COUNT

        ; Wait for keypress
        GETKEY                  ; Wait for any key

        ; Check for ON/CLEAR (break)
        LDAA    #KB_BREK        ; Check break key
        SWI
        BCS     EXIT            ; If carry set, exit

        ; Increment counter
        LDAA    UTW_T0          ; Load counter
        INCA                    ; Increment
        CMPA    #MAX_COUNT      ; Check if reached max
        BLO     STORE_COUNT     ; If less, continue
        CLRA                    ; Otherwise wrap to 0

STORE_COUNT:
        STAA    UTW_T0          ; Store new value
        BRA     MAIN_LOOP       ; Continue loop

EXIT:
        RTS                     ; Return to OS

; =============================================================================
; SHOW_COUNT - Display the current counter value
; =============================================================================
; Input: Counter value in UTW_T0
; Uses: A, B, X registers
; =============================================================================

SHOW_COUNT:
        PSHA                    ; Save A
        PSHB                    ; Save B

        ; Clear display
        CLRSCR

        ; Get counter value
        LDAA    UTW_T0

        ; Convert to two ASCII digits
        ; Tens digit = value / 10
        ; Ones digit = value % 10

        CLRB                    ; B will count tens
DIV_LOOP:
        CMPA    #10             ; Is A >= 10?
        BLO     DIV_DONE        ; No, we're done
        SUBA    #10             ; A = A - 10
        INCB                    ; B = B + 1
        BRA     DIV_LOOP

DIV_DONE:
        ; B = tens digit, A = ones digit
        ; Convert to ASCII and display

        PSHA                    ; Save ones digit

        ; Display tens digit
        TBA                     ; A = tens digit
        ADDA    #ASCII_ZERO     ; Convert to ASCII
        LDAB    #DP_EMIT        ; Display character service
        SWI

        ; Display ones digit
        PULA                    ; Restore ones digit
        ADDA    #ASCII_ZERO     ; Convert to ASCII
        LDAB    #DP_EMIT
        SWI

        PULB                    ; Restore B
        PULA                    ; Restore A
        RTS

; =============================================================================
; End of Program
; =============================================================================
