; =============================================================================
; HELLO.ASM - Hello World for Psion Organiser II
; =============================================================================
; This is a minimal "Hello World" program that demonstrates:
;   - Program structure for Psion machine code
;   - Using system calls (SWI) to interact with the OS
;   - Displaying text on the LCD
;   - Waiting for a keypress before exiting
;
; To assemble:
;   psasm -o hello.ob3 hello.asm
;
; To run on Psion:
;   Transfer hello.ob3 to device and run from top-level menu
;
; Reference: https://www.jaapsch.net/psion/
; =============================================================================

        INCLUDE "psion.inc"     ; Include SDK definitions

; =============================================================================
; Program Origin
; =============================================================================
; All Psion procedures load at $2100 (standard code load address)
        ORG     $2100

; =============================================================================
; Main Entry Point
; =============================================================================
; The Psion OS calls the procedure at its load address.
; We must RTS when done to return control to the OS.

START:
        ; ---------------------------------------------------------------------
        ; Step 1: Clear the display
        ; ---------------------------------------------------------------------
        ; The UT_CDSP system call clears the screen and optionally displays
        ; an inline string. Here we just clear it.

        CLRSCR                  ; Use macro to clear display

        ; ---------------------------------------------------------------------
        ; Step 2: Display our message
        ; ---------------------------------------------------------------------
        ; The DP_PRNT system call displays a null-terminated string.
        ; We load X with the address of our string and call the service.

        PRINT   MESSAGE         ; Use PRINT macro (loads X, calls DP_PRNT)

        ; ---------------------------------------------------------------------
        ; Step 3: Wait for a keypress
        ; ---------------------------------------------------------------------
        ; The KB_GETK system call waits for a key and returns the keycode
        ; in accumulator A. We don't care about the actual key here.

        GETKEY                  ; Use macro (calls KB_GETK via SWI)

        ; ---------------------------------------------------------------------
        ; Step 4: Return to OS
        ; ---------------------------------------------------------------------
        ; RTS returns control to the operating system.
        ; The display will be restored to the top-level menu.

        RTS                     ; Done - return to OS

; =============================================================================
; Data Section
; =============================================================================
; Strings and constants. The FCC directive creates ASCII bytes,
; and FCB 0 adds the null terminator required by DP_PRNT.

MESSAGE:
        FCC     "Hello, Psion!"
        FCB     0               ; Null terminator

; =============================================================================
; End of Program
; =============================================================================
; The assembler calculates the program size from START to here.
; This information is encoded in the OB3 header.
; =============================================================================
