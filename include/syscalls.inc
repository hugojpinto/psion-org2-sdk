; =============================================================================
; SYSCALLS.INC - Psion Organiser II System Call Definitions
; =============================================================================
; This file defines the OS service call numbers for the Psion Organiser II.
; System calls are invoked using the SWI instruction followed by the service
; number as a byte in program memory.
;
; Usage:
;     SWI                 ; Software interrupt instruction
;     FCB     DP_EMIT     ; Service number follows immediately
;
; Or use the OS macro:
;     OS      DP_EMIT     ; Expands to: SWI / FCB DP_EMIT
;
; IMPORTANT: Parameters are passed in registers BEFORE the SWI:
;     - A register: character for DP_EMIT, flags for some services
;     - B register: counts, secondary parameters
;     - X register: addresses, pointers
;
; Reference: https://www.jaapsch.net/psion/mcosintr.htm
;            CM/XP Technical Reference Manual
; =============================================================================

; -----------------------------------------------------------------------------
; Memory Management Services (AL$xxx)
; These services manage the heap/cell allocation system
; -----------------------------------------------------------------------------
AL_FREE     EQU     $00     ; Deallocate memory cell
AL_GRAB     EQU     $01     ; Allocate memory cell
AL_GROW     EQU     $02     ; Expand memory cell
AL_REPL     EQU     $03     ; Resize for part replacement
AL_SHNK     EQU     $04     ; Shrink memory cell
AL_SIZE     EQU     $05     ; Get cell dimensions
AL_ZERO     EQU     $06     ; Clear memory cell contents

; -----------------------------------------------------------------------------
; Battery/System Control Services (BT$xxx)
; Power management and NMI control
; -----------------------------------------------------------------------------
BT_NMDN     EQU     $07     ; Disable NMI (stops real-time clock)
BT_NMEN     EQU     $08     ; Re-enable NMI after BT_NMDN
BT_NOF      EQU     $09     ; Disable NMI (preserves time)
BT_NON      EQU     $0A     ; Re-enable NMI (syncs clock)
BT_PPRG     EQU     $0B     ; Push/pop system variables
BT_SWOF     EQU     $0C     ; Power off the device

; -----------------------------------------------------------------------------
; Buzzer/Sound Services (BZ$xxx)
; Audio output control
; -----------------------------------------------------------------------------
BZ_ALRM     EQU     $0D     ; Trigger alarm sound pattern
BZ_BELL     EQU     $0E     ; Standard beep tone
BZ_TONE     EQU     $0F     ; Custom tone (frequency/duration)

; -----------------------------------------------------------------------------
; Display Services (DP$xxx)
; LCD display control and text output
; -----------------------------------------------------------------------------
DP_EMIT     EQU     $10     ; Output single character to display
DP_PRNT     EQU     $11     ; Print string to display
DP_REST     EQU     $12     ; Restore saved screen state
DP_SAVE     EQU     $13     ; Save current screen state
DP_STAT     EQU     $14     ; Position cursor (set status)
DP_VIEW     EQU     $15     ; Display formatted string
DP_WRDY     EQU     $16     ; Wait for display ready

; -----------------------------------------------------------------------------
; Device Management Services (DV$xxx)
; Device initialization and code loading
; -----------------------------------------------------------------------------
DV_BOOT     EQU     $17     ; Initialize device/system
DV_CLER     EQU     $18     ; Deinitialize/clear devices
DV_LKUP     EQU     $19     ; Language/device lookup
DV_LOAD     EQU     $1A     ; Load code from pack into RAM
DV_VECT     EQU     $1B     ; Execute device vector code

; -----------------------------------------------------------------------------
; Editor Services (ED$xxx)
; Line editing functionality
; -----------------------------------------------------------------------------
ED_EDIT     EQU     $1C     ; Start line editor at beginning
ED_EPOS     EQU     $1D     ; Start line editor at position
ED_VIEW     EQU     $1E     ; Clear display and show string

; -----------------------------------------------------------------------------
; Error Handling Services (ER$xxx)
; Error message lookup and display
; -----------------------------------------------------------------------------
ER_LKUP     EQU     $1F     ; Look up error string by code
ER_MESS     EQU     $20     ; Display error message

; -----------------------------------------------------------------------------
; File Services (FL$xxx)
; File system operations
; -----------------------------------------------------------------------------
FL_BACK     EQU     $21     ; Move backward in file
FL_BCAT     EQU     $22     ; Catalog block files
FL_BDEL     EQU     $23     ; Delete block file
FL_BOPN     EQU     $24     ; Open block file
FL_BSAV     EQU     $25     ; Save block file
FL_CATL     EQU     $26     ; Catalog ordinary files
FL_COPY     EQU     $27     ; Copy file
FL_CRET     EQU     $28     ; Create new file
FL_DELN     EQU     $29     ; Delete file by name
FL_ERAS     EQU     $2A     ; Erase current record
FL_FFND     EQU     $2B     ; Find file by prefix
FL_FIND     EQU     $2C     ; Find substring in file
FL_FREC     EQU     $2D     ; Get current record info
FL_NEXT     EQU     $2E     ; Advance to next record
FL_OPEN     EQU     $2F     ; Open existing file
FL_PARS     EQU     $30     ; Parse/validate filename
FL_READ     EQU     $31     ; Read current record
FL_RECT     EQU     $32     ; Set record type
FL_RENM     EQU     $33     ; Rename file
FL_RSET     EQU     $34     ; Reset to specific record
FL_SETP     EQU     $35     ; Select datapack for operations
FL_SIZE     EQU     $36     ; Get free space on pack
FL_WRIT     EQU     $37     ; Write/append record

; -----------------------------------------------------------------------------
; Math/Floating Point Services (FN$xxx)
; Trigonometric and mathematical functions
; -----------------------------------------------------------------------------
FN_ATAN     EQU     $38     ; Arctangent
FN_COS      EQU     $39     ; Cosine
FN_EXP      EQU     $3A     ; Exponential (e^x)
FN_LN       EQU     $3B     ; Natural logarithm
FN_LOG      EQU     $3C     ; Logarithm base 10
FN_POWR     EQU     $3D     ; Power (x^y)
FN_RND      EQU     $3E     ; Random number 0-1
FN_SIN      EQU     $3F     ; Sine
FN_SQRT     EQU     $40     ; Square root
FN_TAN      EQU     $41     ; Tangent

; -----------------------------------------------------------------------------
; Interpreter Services (IT$xxx)
; Table-driven interpreter support
; -----------------------------------------------------------------------------
IT_GVAL     EQU     $42     ; Get byte parameter from table
IT_RADD     EQU     $43     ; Get variable address
IT_STRT     EQU     $44     ; Start interpreter execution
IT_TADD     EQU     $45     ; Get word parameter from table

; -----------------------------------------------------------------------------
; Keyboard Services (KB$xxx)
; Keyboard input and control
; -----------------------------------------------------------------------------
KB_BREK     EQU     $46     ; Test ON/CLEAR key pressed
KB_FLSH     EQU     $47     ; Flush keyboard buffer
KB_GETK     EQU     $48     ; Wait for and get keypress
KB_INIT     EQU     $49     ; Initialize keyboard system
KB_STAT     EQU     $4A     ; Set keyboard state/mode
KB_TEST     EQU     $4B     ; Test if key available in buffer
KB_UGET     EQU     $4C     ; Push key back to buffer (unget)

; -----------------------------------------------------------------------------
; Language Services (LG$xxx)
; OPL text block management
; -----------------------------------------------------------------------------
LG_NEWP     EQU     $4D     ; Create new OPL text block
LG_RLED     EQU     $4E     ; Run/List/Edit/Delete program

; -----------------------------------------------------------------------------
; Translation Services (LN$xxx)
; OPL program translation
; -----------------------------------------------------------------------------
LN_STRT     EQU     $4F     ; Launch OPL translator

; -----------------------------------------------------------------------------
; Menu Services (MN$xxx)
; Menu display and selection
; -----------------------------------------------------------------------------
MN_DISP     EQU     $50     ; Display menu and get selection

; -----------------------------------------------------------------------------
; Math Conversion Services (MT$xxx)
; Number format conversions
; -----------------------------------------------------------------------------
MT_BTOF     EQU     $51     ; String to floating point
MT_FADD     EQU     $52     ; Add two floats
MT_FBDC     EQU     $53     ; Float to fixed decimal string
MT_FBEX     EQU     $54     ; Float to exponential string
MT_FBGN     EQU     $55     ; Float to general format string
MT_FBIN     EQU     $56     ; Float to integer
MT_FDIV     EQU     $57     ; Divide floats
MT_FMUL     EQU     $58     ; Multiply floats
MT_FNGT     EQU     $59     ; Negate float
MT_FSUB     EQU     $5A     ; Subtract floats

; -----------------------------------------------------------------------------
; Pack Services (PK$xxx)
; Low-level datapack access
; -----------------------------------------------------------------------------
PK_PKOF     EQU     $5B     ; Turn off pack hardware
PK_QADD     EQU     $5C     ; Query current pack address
PK_RBYT     EQU     $5D     ; Read single byte from pack
PK_READ     EQU     $5E     ; Read multiple bytes from pack
PK_RWRD     EQU     $5F     ; Read word from pack
PK_SADD     EQU     $60     ; Set pack address
PK_SAVE     EQU     $61     ; Write bytes to pack
PK_SETP     EQU     $62     ; Select pack slot (A, B, C)
PK_SKIP     EQU     $63     ; Advance pack address

; -----------------------------------------------------------------------------
; Runtime Services (RM$xxx)
; Program execution
; -----------------------------------------------------------------------------
RM_RUNP     EQU     $64     ; Execute OPL program

; -----------------------------------------------------------------------------
; Top-Level Menu Services (TL$xxx)
; Main menu management
; -----------------------------------------------------------------------------
TL_ADDI     EQU     $65     ; Add item to top menu
TL_CPYX     EQU     $66     ; Copy function
TL_DELI     EQU     $67     ; Delete menu item
TL_XXMD     EQU     $68     ; Filename prompt dialog

; -----------------------------------------------------------------------------
; Time Services (TM$xxx)
; Real-time clock access
; -----------------------------------------------------------------------------
TM_DAYV     EQU     $69     ; Calculate day of week
TM_TGET     EQU     $6A     ; Get current system time
TM_UPDT     EQU     $6B     ; Add offset to time value
TM_WAIT     EQU     $6C     ; Wait for specified ticks

; -----------------------------------------------------------------------------
; Utility Services (UT$xxx)
; General-purpose utilities
; -----------------------------------------------------------------------------
UT_CPYB     EQU     $6D     ; Copy buffer/block
UT_DDSP     EQU     $6E     ; Formatted display output
UT_DISP     EQU     $6F     ; Inline display string
UT_ENTR     EQU     $70     ; Call subroutine with parameters
UT_FILL     EQU     $71     ; Fill buffer with value
UT_ICPB     EQU     $72     ; Case-insensitive string compare
UT_ISBF     EQU     $73     ; Search for substring in buffer
UT_LEAV     EQU     $74     ; Exit routine/restore state
UT_SDIV     EQU     $75     ; Signed 16-bit division
UT_SMUL     EQU     $76     ; Signed 16-bit multiplication
UT_SPLT     EQU     $77     ; Split string into fields
UT_UDIV     EQU     $78     ; Unsigned 16-bit division
UT_UMUL     EQU     $79     ; Unsigned 16-bit multiplication
UT_UTOB     EQU     $7A     ; Unsigned integer to decimal string
UT_XCAT     EQU     $7B     ; Extended catalog (by type)
UT_XTOB     EQU     $7C     ; Integer to hexadecimal string
UT_YSNO     EQU     $7D     ; Yes/No prompt dialog
UT_CDSP     EQU     $7E     ; Clear display and show string (v2.5+)

; -----------------------------------------------------------------------------
; Extended Services (v2.7+)
; Language and menu extensions
; -----------------------------------------------------------------------------
TL_RSTR     EQU     $7F     ; Restore menu entries
TL_LSET     EQU     $80     ; Select menu language

; =============================================================================
; LZ-Specific System Services ($81+)
; =============================================================================
; These services are only available on LA/LZ/LZ64 models.
; Calling them on CM/XP will cause undefined behavior.
;
; Reference: https://www.jaapsch.net/psion/techlz.htm
; =============================================================================

; -----------------------------------------------------------------------------
; Display Mode Services (LZ only)
; -----------------------------------------------------------------------------
; The LZ has dual display mode support - it can emulate a 2-line display
; (CM/XP compatibility mode) or use its native 4-line display.
;
; When running CM/XP software, the LZ displays a "canvas" border around
; the 2x16 character area. Programs can switch modes using DP$MSET.
; -----------------------------------------------------------------------------

DP_MPSH     EQU     $81     ; Push current display mode to stack
                            ; Saves mode for later restoration

DP_MSET     EQU     $82     ; Set display mode (2-line or 4-line)
                            ; Input: A = 0 for 2-line mode
                            ;        A = 1 for 4-line mode
                            ; The OS switches screen buffers and adjusts
                            ; all display services accordingly.
                            ; In 2-line mode, display is centered with border.

DP_MPOP     EQU     $83     ; Pop/restore saved display mode from stack
                            ; Restores mode saved by DP_MPSH

; -----------------------------------------------------------------------------
; Additional LZ Display Services
; -----------------------------------------------------------------------------
DP_GMOD     EQU     $84     ; Get current display mode
                            ; Output: A = 0 (2-line) or 1 (4-line)

; -----------------------------------------------------------------------------
; LZ Extended File Services
; -----------------------------------------------------------------------------
FL_SECD     EQU     $85     ; Sector direct access
FL_SECT     EQU     $86     ; Sector read/write

; -----------------------------------------------------------------------------
; LZ Memory Banking Services
; -----------------------------------------------------------------------------
; LZ/LZ64 support extended RAM via banking. These services manage
; the RAM bank switching mechanism.
; -----------------------------------------------------------------------------
MB_BANK     EQU     $87     ; Select RAM bank
                            ; Input: A = bank number (0-3)
MB_SAVE     EQU     $88     ; Save to banked RAM
MB_LOAD     EQU     $89     ; Load from banked RAM

; =============================================================================
; OS Macro (standard Psion assembler convention)
; =============================================================================
; Convenience macro for invoking system calls.
; Usage: OS DP_EMIT
; Expands to: SWI
;             FCB DP_EMIT
;
; Example - display character 'A':
;     LDAA    #$41        ; Character in A register
;     OS      DP_EMIT     ; Call display service
;
; Example - wait for keypress:
;     OS      KB_GETK     ; Returns key in B register
; =============================================================================
MACRO OS, service
    SWI
    FCB     \service
ENDM

; =============================================================================
; End of syscalls.inc
; =============================================================================
