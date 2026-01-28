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
; FLOATING POINT SUPPORT:
;   For floating point operations (sin, cos, sqrt, etc.), also include:
;     INCLUDE "float.inc"      ; FP constants and macros
;     INCLUDE "fpruntime.inc"  ; FP runtime functions (for C-style API)
;
;   FP files are kept separate to avoid code bloat when not needed.
;   See float.inc for documentation and examples.
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

; -----------------------------------------------------------------------------
; LOCATE - Position cursor by column and row
; Usage: LOCATE 5, 2     ; Move to column 5, row 2
; Input: Column (0-based), Row (0-based)
; Computes linear position and calls DP$STAT preserving cursor state
; -----------------------------------------------------------------------------
MACRO LOCATE, col, row
#IFDEF __PSION_4LINE__
    ; 4-line: position = row * 20 + col
    LDAA    #\row
    ; row * 20 = row * 16 + row * 4
    ASLA
    ASLA                    ; A = row * 4
    TAB                     ; B = row * 4
    LDAA    #\row
    ASLA
    ASLA
    ASLA
    ASLA                    ; A = row * 16
    ABA                     ; A = row * 20
    ADDA    #\col           ; A = row * 20 + col
#ELSE
    ; 2-line: position = row * 16 + col
    LDAA    #\row
    ASLA
    ASLA
    ASLA
    ASLA                    ; A = row * 16
    ADDA    #\col           ; A = row * 16 + col
#ENDIF
    LDAB    DPB_CUST        ; Preserve current cursor state
    SWI
    FCB     DP_STAT
ENDM

; -----------------------------------------------------------------------------
; CURSOR_ON - Make cursor visible (block cursor)
; Usage: CURSOR_ON
; Shows block cursor at current position
; -----------------------------------------------------------------------------
MACRO CURSOR_ON
    LDAA    DPB_CPOS        ; Current cursor position
    LDAB    #$80            ; Bit 7 = visible, block cursor
    SWI
    FCB     DP_STAT
ENDM

; -----------------------------------------------------------------------------
; CURSOR_OFF - Hide cursor
; Usage: CURSOR_OFF
; Hides cursor, position preserved
; -----------------------------------------------------------------------------
MACRO CURSOR_OFF
    LDAA    DPB_CPOS        ; Current cursor position
    CLRB                    ; Cursor off
    SWI
    FCB     DP_STAT
ENDM

; -----------------------------------------------------------------------------
; KSTAT - Set keyboard status mode
; Usage: KSTAT 2           ; Set to alpha lowercase
; Modes: 1=alpha upper, 2=alpha lower, 3=numeric upper, 4=numeric lower
; Input: Mode number (1-4)
; -----------------------------------------------------------------------------
MACRO KSTAT, mode
#IF \mode == 1
    LDAB    #$00            ; Alpha uppercase
#ENDIF
#IF \mode == 2
    LDAB    #$20            ; Alpha lowercase
#ENDIF
#IF \mode == 3
    LDAB    #$10            ; Numeric uppercase
#ENDIF
#IF \mode == 4
    LDAB    #$30            ; Numeric lowercase
#ENDIF
    SWI
    FCB     KB_STAT
ENDM

; -----------------------------------------------------------------------------
; RANDOMIZE - Seed PRNG from system timer
; Usage: RANDOMIZE
; Seeds the _rand_seed variable from the system tick counter
; Requires runtime.inc to be included for _getticks and _rand_seed
; -----------------------------------------------------------------------------
MACRO RANDOMIZE
    JSR     _randomize
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
; OPL Interoperability - Calling OPL Procedures from Assembly
; =============================================================================
; These macros allow assembly programs to call external OPL procedures.
; The OPL procedure runs to completion, then execution resumes in your
; assembly code with stack state preserved.
;
; SETUP REQUIREMENT:
;   You MUST call CALL_OPL_SETUP at the very start of your program,
;   BEFORE any stack operations (PSHX, PSHA, etc.)!
;
; USAGE:
;   1. At program start:
;          CALL_OPL_SETUP        ; Initialize OPL call support (FIRST!)
;
;   2. Define your procedure name strings:
;      _myproc:
;          FCC     "azMENU"
;          FCB     0             ; Null terminator required
;
;   3. Call the OPL procedure:
;          CALL_OPL _myproc      ; Call the OPL procedure
;          ; Execution resumes here after OPL returns
;
; COMPLETE EXAMPLE:
;          ORG     $2100
;      start:
;          CALL_OPL_SETUP        ; Initialize (MUST be first!)
;          ; ... your code ...
;          CALL_OPL _menu        ; Call OPL procedure
;          ; ... continues here ...
;          RTS
;
;      _menu:
;          FCC     "azMENU"
;          FCB     0
;
;          INCLUDE "runtime.inc"
;          END
;
; CONSTRAINTS:
;   - Procedure name must be <= 8 characters
;   - Uses default device (A:) for procedure lookup
;   - D register returns 0 after the call (can be ignored)
;
; INTERNALS:
;   These macros use _call_opl_setup_asm and _call_opl_asm from runtime.inc.
;   The implementation uses QCode injection to invoke the OPL interpreter.
;   See runtime.inc for full technical documentation.
; =============================================================================

; -----------------------------------------------------------------------------
; CALL_OPL_SETUP - Initialize OPL call support
; Usage: CALL_OPL_SETUP
; MUST be called at program start, BEFORE any stack operations!
; Clobbers: D, X
; -----------------------------------------------------------------------------
MACRO CALL_OPL_SETUP
    JSR     _call_opl_setup_asm
ENDM

; -----------------------------------------------------------------------------
; CALL_OPL - Call an external OPL procedure
; Usage: CALL_OPL procname_label
; Where procname_label points to a null-terminated procedure name string.
; Clobbers: A, B, X
; Returns: D = 0 (standard USR return value)
;
; Example:
;     CALL_OPL _myproc
;     ; Execution resumes here after OPL procedure returns
;     BRA     next
;
; _myproc:
;     FCC     "azMENU"
;     FCB     0
; -----------------------------------------------------------------------------
MACRO CALL_OPL, procname
    LDD     #\procname
    JSR     _call_opl_asm
ENDM

; =============================================================================
; Version Information
; =============================================================================

PSION_INC_VER   EQU     $0100   ; Version 1.0 of this include file

; =============================================================================
; End of psion.inc
; =============================================================================
