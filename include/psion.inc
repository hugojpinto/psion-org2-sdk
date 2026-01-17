; =============================================================================
; PSION.INC - Main Include File for Psion Organiser II Development
; =============================================================================
; This is the main include file for developing HD6303 assembly programs
; targeting the Psion Organiser II. It includes all standard definitions
; for system calls, system variables, and provides useful macros.
;
; Usage:
;     INCLUDE "psion.inc"
;
; This file includes:
;   - syscalls.inc  : OS service call numbers
;   - sysvars.inc   : System variable addresses
;   - Common macros for Psion development
;
; Target Model Support:
;   Use .MODEL directive or -m CLI flag to specify target machine:
;
;     .MODEL XP         ; Target XP (2x16 display) - default
;     .MODEL LZ         ; Target LZ (4x20 display)
;
;   This defines the following symbols:
;     __PSION_CM__, __PSION_XP__, __PSION_LA__, __PSION_LZ__, __PSION_LZ64__
;     __PSION_2LINE__ or __PSION_4LINE__
;     DISP_ROWS, DISP_COLS
;
;   Conditional assembly example:
;     #IFDEF __PSION_4LINE__
;         LDAA #4           ; 4-line display
;     #ELSE
;         LDAA #2           ; 2-line display
;     #ENDIF
;
; Example Program:
;     INCLUDE "psion.inc"
;
;     ORG $2100           ; Standard code load address
;
;     start:
;         SYSCALL DP_EMIT ; Use macro to emit character in A
;         RTS
;
; Reference: https://www.jaapsch.net/psion/
; =============================================================================

; Include system call definitions
    INCLUDE "syscalls.inc"

; Include system variable definitions
    INCLUDE "sysvars.inc"

; =============================================================================
; Standard Program Header
; =============================================================================
; Psion procedures typically start with a header identifying the program.
; The OS uses this header to catalog and manage programs.

; File type identifiers for OB3 format
FTYPE_PROC  EQU     $83     ; Procedure (machine code or OPL)
FTYPE_DATA  EQU     $81     ; Data file
FTYPE_DIARY EQU     $82     ; Diary file

; =============================================================================
; Useful Macros
; =============================================================================

; -----------------------------------------------------------------------------
; PRINT - Display a string at current cursor position
; Usage: PRINT msg
;        msg:  FCB len
;              FCC "Hello"
; Input: Address of LBC string (length byte + chars)
; Note: B = length, X = pointer to characters
; -----------------------------------------------------------------------------
MACRO PRINT, addr
    LDX     #\addr
    LDAB    0,X         ; Get length
    INX                 ; Point to characters
    SWI
    FCB     DP_PRNT
ENDM

; -----------------------------------------------------------------------------
; EMIT - Output single character to display
; Usage: EMIT 'A'       ; Emit literal character
;        EMIT char_var  ; Emit value at address
; Input: Character value in A register
; -----------------------------------------------------------------------------
MACRO EMIT, char
    LDAA    #\char
    SWI
    FCB     DP_EMIT
ENDM

; -----------------------------------------------------------------------------
; GETKEY - Wait for and get a keypress
; Usage: GETKEY
; Output: Key code in B register
; -----------------------------------------------------------------------------
MACRO GETKEY
    SWI
    FCB     KB_GETK
ENDM

; -----------------------------------------------------------------------------
; BEEP - Sound a short beep
; Usage: BEEP
; -----------------------------------------------------------------------------
MACRO BEEP
    SWI
    FCB     BZ_BELL
ENDM

; -----------------------------------------------------------------------------
; PAUSE - Wait for specified number of ticks (1 tick = ~1/32 second)
; Usage: PAUSE 32       ; Wait about 1 second
; Input: Number of ticks in D (A:B)
; -----------------------------------------------------------------------------
MACRO PAUSE, ticks
    LDD     #\ticks
    SWI
    FCB     TM_WAIT
ENDM

; -----------------------------------------------------------------------------
; CURSOR - Position cursor on display
; Usage: CURSOR 0, 5    ; Row 0, column 5
; Input: Row (0-1), Column (0-15)
; Position = row * 16 + col
; -----------------------------------------------------------------------------
MACRO CURSOR, row, col
    LDAA    #(\row*16+\col)     ; Position in A register
    CLRB                        ; Status in B (cursor off)
    SWI
    FCB     DP_STAT
ENDM

; -----------------------------------------------------------------------------
; CLRSCR - Clear screen using DP_EMIT with $0C control character
; Usage: CLRSCR
; -----------------------------------------------------------------------------
MACRO CLRSCR
    LDAA    #$0C        ; Clear display control character
    SWI
    FCB     DP_EMIT
ENDM

; -----------------------------------------------------------------------------
; POWEROFF - Turn off the Psion
; Usage: POWEROFF
; -----------------------------------------------------------------------------
MACRO POWEROFF
    SWI
    FCB     BT_SWOF
ENDM

; =============================================================================
; Display Mode Macros (LZ/LZ64 only)
; =============================================================================
; These macros control the dual display mode on 4-line machines.
; On LZ, you can run in 2-line compatibility mode (canvas border shown)
; or native 4-line mode.
;
; IMPORTANT: These services are only available on LA/LZ/LZ64 models.
; Calling them on CM/XP will cause undefined behavior.
; =============================================================================

; Display mode constants
MODE_2LINE  EQU     0       ; 2-line compatibility mode (16x2)
MODE_4LINE  EQU     1       ; Native 4-line mode (20x4)

; -----------------------------------------------------------------------------
; SETMODE - Set display mode (LZ only)
; Usage: SETMODE MODE_2LINE  ; Switch to 2-line compatibility mode
;        SETMODE MODE_4LINE  ; Switch to native 4-line mode
; Note: Only available on LA/LZ/LZ64 models
; -----------------------------------------------------------------------------
MACRO SETMODE, mode
    LDAA    #\mode
    SWI
    FCB     DP_MSET
ENDM

; -----------------------------------------------------------------------------
; GETMODE - Get current display mode (LZ only)
; Usage: GETMODE
; Output: A = 0 (2-line mode) or 1 (4-line mode)
; Note: Only available on LA/LZ/LZ64 models
; -----------------------------------------------------------------------------
MACRO GETMODE
    SWI
    FCB     DP_GMOD
ENDM

; -----------------------------------------------------------------------------
; PUSHMODE - Save current display mode (LZ only)
; Usage: PUSHMODE
;        ... do something in different mode ...
;        POPMODE
; Note: Only available on LA/LZ/LZ64 models
; -----------------------------------------------------------------------------
MACRO PUSHMODE
    SWI
    FCB     DP_MPSH
ENDM

; -----------------------------------------------------------------------------
; POPMODE - Restore saved display mode (LZ only)
; Usage: POPMODE
; Note: Only available on LA/LZ/LZ64 models
; -----------------------------------------------------------------------------
MACRO POPMODE
    SWI
    FCB     DP_MPOP
ENDM

; =============================================================================
; Register Save/Restore Macros
; =============================================================================

; -----------------------------------------------------------------------------
; PUSHALL - Save all registers to stack
; Saves: A, B, X in that order
; -----------------------------------------------------------------------------
MACRO PUSHALL
    PSHA
    PSHB
    PSHX
ENDM

; -----------------------------------------------------------------------------
; PULLALL - Restore all registers from stack
; Restores: X, B, A (reverse order)
; -----------------------------------------------------------------------------
MACRO PULLALL
    PULX
    PULB
    PULA
ENDM

; =============================================================================
; 16-bit Operations
; =============================================================================

; -----------------------------------------------------------------------------
; LDDA - Load D register with immediate value
; Usage: LDDA $1234
; -----------------------------------------------------------------------------
MACRO LDDA, value
    LDD     #\value
ENDM

; -----------------------------------------------------------------------------
; STDA - Store D register to memory
; Usage: STDA buffer
; -----------------------------------------------------------------------------
MACRO STDA, addr
    STD     \addr
ENDM

; =============================================================================
; String Constants
; =============================================================================
; Strings in Psion format are typically null-terminated (C-style) or
; prefixed with a length byte (Pascal-style/LBC).

; LBC (Leading Byte Count) string definition macro
; Usage: LBCSTR "Hello"
; Produces: FCB 5, "Hello"
MACRO LBCSTR, text
    FCB     \text_len
    FCC     "\text"
ENDM

; =============================================================================
; Common Subroutine Entry/Exit
; =============================================================================

; Standard subroutine prologue - save registers
MACRO SUBENTER
    PSHX
    PSHB
    PSHA
ENDM

; Standard subroutine epilogue - restore registers
MACRO SUBEXIT
    PULA
    PULB
    PULX
    RTS
ENDM

; =============================================================================
; Conditional Compilation Helpers
; =============================================================================

; Define to target specific models
; #DEFINE TARGET_CM     ; For CM models
; #DEFINE TARGET_XP     ; For XP models
; #DEFINE TARGET_LZ     ; For LZ/LZ64 models

; Define for debug builds
; #DEFINE DEBUG         ; Enable debug features

; =============================================================================
; Error Codes (commonly returned by OS services)
; =============================================================================

ERR_NONE    EQU     $00     ; No error
ERR_BREAK   EQU     $01     ; User pressed ON/CLEAR
ERR_EOF     EQU     $02     ; End of file reached
ERR_FULL    EQU     $03     ; Pack/memory full
ERR_NAME    EQU     $04     ; Invalid filename
ERR_NFND    EQU     $05     ; File not found
ERR_EXIST   EQU     $06     ; File already exists
ERR_SYNTAX  EQU     $07     ; Syntax error
ERR_IOERR   EQU     $08     ; I/O error
ERR_BATT    EQU     $09     ; Battery low

; =============================================================================
; Version Information
; =============================================================================

PSION_INC_VER   EQU     $0100   ; Version 1.0 of this include file

; =============================================================================
; End of psion.inc
; =============================================================================
