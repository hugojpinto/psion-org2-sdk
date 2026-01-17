; =============================================================================
; BITTEST.ASM - HD6303-Specific Bit Operations Demo
; =============================================================================
; This program demonstrates HD6303-specific instructions that are not
; available on the standard 6800/6801:
;   - AIM (AND Immediate with Memory)
;   - OIM (OR Immediate with Memory)
;   - EIM (XOR Immediate with Memory)
;   - TIM (Test Immediate with Memory)
;   - XGDX (Exchange D and X)
;
; These instructions provide efficient bit manipulation without
; needing to load/modify/store register values.
;
; To assemble:
;   psasm -o bittest.ob3 bittest.asm
;
; Reference: https://www.jaapsch.net/psion/
; =============================================================================

        INCLUDE "psion.inc"

        ORG     $2100

; =============================================================================
; Constants and Work Areas
; =============================================================================

; We use zero-page temp areas for demonstration
FLAGS           EQU     UTW_T0  ; Our flags byte
TEMP            EQU     UTW_T1  ; Temporary storage

; Flag bit definitions
FLAG_READY      EQU     $01     ; Bit 0: Ready flag
FLAG_BUSY       EQU     $02     ; Bit 1: Busy flag
FLAG_ERROR      EQU     $04     ; Bit 2: Error flag
FLAG_DONE       EQU     $08     ; Bit 3: Done flag

; =============================================================================
; Main Entry Point
; =============================================================================

START:
        ; Clear display and show title
        CLRSCR
        PRINT   MSG_TITLE

        ; Wait for key to start
        GETKEY

        ; ---------------------------------------------------------------------
        ; Initialize flags to zero
        ; ---------------------------------------------------------------------
        CLRA
        STAA    FLAGS

        ; ---------------------------------------------------------------------
        ; Demo 1: OIM - Set bits (OR Immediate with Memory)
        ; ---------------------------------------------------------------------
        ; OIM allows setting specific bits in memory without affecting others
        ; This is equivalent to: LDAA FLAGS; ORAA #mask; STAA FLAGS

        CLRSCR
        PRINT   MSG_SET

        ; Set READY flag using OIM
        OIM     #FLAG_READY,FLAGS       ; FLAGS |= FLAG_READY

        ; Set BUSY flag using OIM
        OIM     #FLAG_BUSY,FLAGS        ; FLAGS |= FLAG_BUSY

        ; Show result (should be $03)
        BSR     SHOW_FLAGS
        GETKEY

        ; ---------------------------------------------------------------------
        ; Demo 2: AIM - Clear bits (AND Immediate with Memory)
        ; ---------------------------------------------------------------------
        ; AIM clears specific bits by ANDing with inverted mask
        ; This is equivalent to: LDAA FLAGS; ANDA #mask; STAA FLAGS

        CLRSCR
        PRINT   MSG_CLEAR

        ; Clear BUSY flag using AIM (AND with ~FLAG_BUSY = $FD)
        AIM     #~FLAG_BUSY,FLAGS       ; FLAGS &= ~FLAG_BUSY

        ; Show result (should be $01)
        BSR     SHOW_FLAGS
        GETKEY

        ; ---------------------------------------------------------------------
        ; Demo 3: EIM - Toggle bits (XOR Immediate with Memory)
        ; ---------------------------------------------------------------------
        ; EIM toggles specific bits
        ; This is equivalent to: LDAA FLAGS; EORA #mask; STAA FLAGS

        CLRSCR
        PRINT   MSG_TOGGLE

        ; Toggle ERROR and DONE flags
        EIM     #FLAG_ERROR|FLAG_DONE,FLAGS   ; FLAGS ^= (ERROR|DONE)

        ; Show result (should be $0D: READY + ERROR + DONE)
        BSR     SHOW_FLAGS
        GETKEY

        ; Toggle again to clear them
        EIM     #FLAG_ERROR|FLAG_DONE,FLAGS

        ; Show result (should be $01: just READY)
        BSR     SHOW_FLAGS
        GETKEY

        ; ---------------------------------------------------------------------
        ; Demo 4: TIM - Test bits (Test Immediate with Memory)
        ; ---------------------------------------------------------------------
        ; TIM tests bits and sets Z flag without modifying memory
        ; Useful for conditional branching based on bit states

        CLRSCR
        PRINT   MSG_TEST

        ; Set ERROR flag for testing
        OIM     #FLAG_ERROR,FLAGS

        ; Test if ERROR flag is set
        TIM     #FLAG_ERROR,FLAGS       ; Test ERROR bit
        BEQ     NOT_ERROR               ; Branch if zero (not set)

        ; ERROR is set
        PRINT   MSG_ERR_SET
        BRA     TEST_DONE

NOT_ERROR:
        PRINT   MSG_ERR_CLR

TEST_DONE:
        GETKEY

        ; ---------------------------------------------------------------------
        ; Demo 5: XGDX - Exchange D and X registers
        ; ---------------------------------------------------------------------
        ; XGDX swaps the contents of D (A:B) and X registers
        ; Useful for quickly moving 16-bit values

        CLRSCR
        PRINT   MSG_XGDX

        ; Load D with $1234
        LDD     #$1234
        ; Load X with $5678
        LDX     #$5678

        ; Exchange D and X
        XGDX                    ; Now D=$5678, X=$1234

        ; Store results to show exchange happened
        STD     UTW_W0          ; Store new D value
        STX     UTW_W1          ; Store new X value

        GETKEY

        ; ---------------------------------------------------------------------
        ; Done - return to OS
        ; ---------------------------------------------------------------------
        CLRSCR
        PRINT   MSG_DONE
        GETKEY

        RTS

; =============================================================================
; SHOW_FLAGS - Display current flags value
; =============================================================================
; Input: FLAGS byte at defined address
; =============================================================================

SHOW_FLAGS:
        PSHA
        PSHB

        ; Display "Flags: $"
        PRINT   MSG_FLAGS

        ; Get flags value
        LDAA    FLAGS

        ; Convert high nibble to hex
        TAB                     ; Save in B
        LSRA                    ; Shift high nibble down
        LSRA
        LSRA
        LSRA
        BSR     NIBBLE_TO_HEX   ; Convert to ASCII
        LDAB    #DP_EMIT
        SWI

        ; Convert low nibble to hex
        TBA                     ; Get original back
        ANDA    #$0F            ; Mask low nibble
        BSR     NIBBLE_TO_HEX
        LDAB    #DP_EMIT
        SWI

        PULB
        PULA
        RTS

; =============================================================================
; NIBBLE_TO_HEX - Convert nibble (0-F) in A to ASCII hex character
; =============================================================================
; Input: A = value 0-15
; Output: A = ASCII '0'-'9' or 'A'-'F'
; =============================================================================

NIBBLE_TO_HEX:
        CMPA    #10
        BLO     DIGIT           ; 0-9
        ADDA    #'A'-10         ; A-F
        RTS
DIGIT:
        ADDA    #'0'
        RTS

; =============================================================================
; Messages
; =============================================================================

MSG_TITLE:      FCC     "HD6303 Bits"
                FCB     0

MSG_SET:        FCC     "OIM Set"
                FCB     0

MSG_CLEAR:      FCC     "AIM Clear"
                FCB     0

MSG_TOGGLE:     FCC     "EIM Toggle"
                FCB     0

MSG_TEST:       FCC     "TIM Test"
                FCB     0

MSG_XGDX:       FCC     "XGDX Swap"
                FCB     0

MSG_FLAGS:      FCC     "Flags: $"
                FCB     0

MSG_ERR_SET:    FCC     "ERR set"
                FCB     0

MSG_ERR_CLR:    FCC     "ERR clear"
                FCB     0

MSG_DONE:       FCC     "Done!"
                FCB     0

; =============================================================================
; End of Program
; =============================================================================
