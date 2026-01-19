; =============================================================================
; SYSVARS.INC - Psion Organiser II System Variable Definitions
; =============================================================================
; This file defines the memory addresses of system variables used by the
; Psion Organiser II operating system. These variables are located in the
; zero page ($40-$FF) and system RAM areas.
;
; Memory Map Overview:
;   $0000-$003F  HD6303 internal registers (I/O, timers, ports)
;   $0040-$00FF  Processor RAM (zero page - fast access)
;   $0100-$03FF  Semi-custom chip I/O (display, keyboard, packs)
;   $0400-$1FFF  System RAM (varies by model)
;   $2000-$7FFF  Extended RAM (banked on LZ models)
;   $8000-$FFFF  ROM (banked on some models)
;
; Reference: Psion Technical Manual
; =============================================================================

; =============================================================================
; HD6303 Internal Registers ($00-$3F)
; =============================================================================
; These are hardware registers in the HD6303 processor itself

; Port 1 Data Direction Register
P1DDR       EQU     $00     ; Port 1 data direction (0=input, 1=output)

; Port 2 Data Direction Register
P2DDR       EQU     $01     ; Port 2 data direction

; Port 1 Data Register
PORT1       EQU     $02     ; Port 1 data

; Port 2 Data Register
PORT2       EQU     $03     ; Port 2 data

; Port 3 Control/Status Register
P3CSR       EQU     $04     ; Port 3 control/status

; Port 3 Data Register
PORT3       EQU     $05     ; Port 3 data

; Port 4 Data Direction Register
P4DDR       EQU     $06     ; Port 4 data direction

; Port 4 Data Register
PORT4       EQU     $07     ; Port 4 data

; Timer Control and Status Register
TCSR        EQU     $08     ; Timer control/status

; Free Running Counter
FRCH        EQU     $09     ; Free running counter high byte
FRCL        EQU     $0A     ; Free running counter low byte

; Output Compare Register
OCRH        EQU     $0B     ; Output compare high byte
OCRL        EQU     $0C     ; Output compare low byte

; Input Capture Register
ICRH        EQU     $0D     ; Input capture high byte
ICRL        EQU     $0E     ; Input capture low byte

; Port 3 Control/Status Register 2
P3CSR2      EQU     $0F     ; Port 3 control/status 2

; Rate and Mode Control Register
RMCR        EQU     $10     ; Rate and mode control

; Transmit/Receive Control Status Register
TRCSR       EQU     $11     ; Serial control/status

; Receive Data Register
RDR         EQU     $12     ; Serial receive data

; Transmit Data Register
TDR         EQU     $13     ; Serial transmit data

; RAM Control Register
RAMCR       EQU     $14     ; RAM control (HD6303X/Y only)

; Port 5 Data Register
PORT5       EQU     $15     ; Port 5 data (HD6303X/Y only)

; Port 6 Data Direction Register
P6DDR       EQU     $16     ; Port 6 data direction (HD6303X/Y only)

; Port 6 Data Register
PORT6       EQU     $17     ; Port 6 data (HD6303X/Y only)

; Port 7 Data Register
PORT7       EQU     $18     ; Port 7 data (HD6303X/Y only)

; Timer Control/Status Register 2
TCSR2       EQU     $1F     ; Timer control/status 2 (HD6303X/Y only)

; Output Compare Register 2
OCR2H       EQU     $21     ; Output compare 2 high byte
OCR2L       EQU     $22     ; Output compare 2 low byte

; =============================================================================
; Zero Page System Variables ($40-$FF)
; =============================================================================
; These are commonly used OS variables in the fast-access zero page area

; Stack and pointer area
UTW_S0      EQU     $40     ; System work area start
UTW_S1      EQU     $41
STESSION    EQU     $42     ; Session pointer (2 bytes)
FESSION     EQU     $44     ; File session pointer (2 bytes)

; Current context pointers
RTB_FL      EQU     $46     ; Runtime block pointer
RTB_PL      EQU     $48     ; Program pointer
RTB_BL      EQU     $4A     ; Block pointer

; -----------------------------------------------------------------------------
; Battery State ($60-$61)
; Reference: https://www.jaapsch.net/psion/sysvars.htm
; -----------------------------------------------------------------------------
RTB_LBAT    EQU     $60     ; Low battery flag (non-zero when low)

; -----------------------------------------------------------------------------
; Display Variables ($62-$70)
; Reference: https://www.jaapsch.net/psion/sysvars.htm
; -----------------------------------------------------------------------------
; These variables track cursor position and display state, essential for
; AI agents to understand screen layout during text editing operations.

DPB_CPOS    EQU     $62     ; Current cursor position
                            ; Range: 0-31 for 2-line displays (CM/XP)
                            ;        0-79 for 4-line displays (LZ/LZ64)
                            ; Formula: position = (row * columns) + column
                            ;   2-line: position = (row * 16) + column
                            ;   4-line: position = (row * 20) + column

DPB_CUST    EQU     $63     ; Cursor state flags (as passed to DP$STAT)
                            ; Bit 7: cursor visibility (1=on, 0=off)
                            ; Bit 0: cursor style (1=line/underline, 0=block)
                            ; Other bits reserved

DPB_VLIN    EQU     $64     ; Scrolling line position / menu item
                            ; VIEW: line being scrolled (0-1 or 0-3)
                            ; MENU: current menu item number

DPB_VSIZ    EQU     $65     ; Scrolling text size / menu count
                            ; VIEW: number of characters to scroll
                            ; MENU: total number of menu items

DPB_VDIR    EQU     $66     ; Scroll direction
                            ; 0 = paused
                            ; 1 = right
                            ; 2 = left

DPB_SPOS    EQU     $67     ; Saved cursor position (by DP$SAVE)
DPB_SCUS    EQU     $68     ; Saved cursor state (by DP$SAVE)

DPW_SPED    EQU     $69     ; Horizontal scroll speed (2 bytes, 50ms units)
                            ; Default: 4 (200ms between scroll steps)

DPW_DELY    EQU     $6B     ; Vertical scroll delay (2 bytes, 50ms units)
                            ; Default: 10 (500ms pause between scrolls)

DPW_REDY    EQU     $6D     ; Display ready countdown (2 bytes, 50ms units)
                            ; Decremented every 50ms until zero

DPA_VADD    EQU     $6F     ; VIEW string address (2 bytes)
                            ; Address of string being scrolled by DP$VIEW

; -----------------------------------------------------------------------------
; Keyboard Variables ($71-$7B)
; Reference: https://www.jaapsch.net/psion/sysvars.htm
; -----------------------------------------------------------------------------
KBW_TDEL    EQU     $71     ; Keyboard interrupt timing (2 bytes)
                            ; Default: $B3DD for 0.05 second interval
KBB_BACK    EQU     $73     ; Keyboard buffer back index
KBB_NKYS    EQU     $74     ; Number of keys in buffer
KBB_SAST    EQU     $75     ; Shift key state
KBB_WAIT    EQU     $76     ; Unget key (pushed back by KB$UGET)
KBB_SKEY    EQU     $77     ; Last key pressed
KBB_FLGS    EQU     $78     ; Keyboard flags (auto-repeat, etc.)
KBW_REP1    EQU     $79     ; First repeat delay (2 bytes)
KBB_STAT    EQU     $7B     ; Keyboard status (shift/caps lock state)

; Temporary work areas (can be used by user programs)
; These are typically safe to use within your own code
UTW_T0      EQU     $80     ; Temp work byte 0
UTW_T1      EQU     $81     ; Temp work byte 1
UTW_T2      EQU     $82     ; Temp work byte 2
UTW_T3      EQU     $83     ; Temp work byte 3
UTW_W0      EQU     $84     ; Temp work word 0 (2 bytes)
UTW_W1      EQU     $86     ; Temp work word 1 (2 bytes)
UTW_W2      EQU     $88     ; Temp work word 2 (2 bytes)

; String buffer pointer
STR_BUF     EQU     $90     ; String buffer pointer (2 bytes)

; Math/float work area
MTH_ACC     EQU     $A0     ; Math accumulator (8 bytes)
MTH_OPR     EQU     $A8     ; Math operand (8 bytes)
MTH_TMP     EQU     $B0     ; Math temp (8 bytes)

; Menu/editor state
MNU_ITEM    EQU     $C0     ; Current menu item
MNU_CNT     EQU     $C1     ; Menu item count
EDT_POS     EQU     $C2     ; Editor cursor position (2 bytes)
EDT_LEN     EQU     $C4     ; Editor string length

; Device vectors
DEV_VEC0    EQU     $D0     ; Device vector 0 (2 bytes)
DEV_VEC1    EQU     $D2     ; Device vector 1 (2 bytes)
DEV_VEC2    EQU     $D4     ; Device vector 2 (2 bytes)

; OS work area end
UTW_END     EQU     $FF     ; End of zero page work area

; =============================================================================
; Semi-Custom Chip I/O ($100-$3FF)
; =============================================================================
; Control registers for the Psion's custom hardware

; Display control
LCD_CTRL    EQU     $0180   ; LCD control register
LCD_DATA    EQU     $01A0   ; LCD data register

; Power control
PWR_OFF     EQU     $01C0   ; Write here to power off

; Pack control (active low signals)
PACK_CTRL   EQU     $0200   ; Pack control port
PACK_DATA   EQU     $0220   ; Pack data port
PACK_STAT   EQU     $0240   ; Pack status port

; Keyboard matrix
KEY_ROWS    EQU     $0260   ; Keyboard row select
KEY_COLS    EQU     $0280   ; Keyboard column read

; Buzzer control
BUZ_CTRL    EQU     $02C0   ; Buzzer frequency/enable

; =============================================================================
; System RAM Areas ($400+)
; =============================================================================
; These vary by model but define common boundaries

; System RAM start (CM/XP models)
SYS_RAM     EQU     $0400   ; Start of system RAM

; Heap area (managed by AL$ services)
HEAP_BASE   EQU     $0600   ; Heap starts here (approximate)

; Display buffer (typically in system RAM)
DISP_BUF    EQU     $2000   ; Display buffer start (varies)

; User program area (for loaded code)
USER_CODE   EQU     $2100   ; Typical user code load address

; =============================================================================
; LZ-Specific System Variables ($2000+)
; =============================================================================
; These variables are only present on LA/LZ/LZ64 models.
; On CM/XP, these addresses may contain user RAM.
;
; Reference: https://www.jaapsch.net/psion/techlz.htm
; =============================================================================

; -----------------------------------------------------------------------------
; Display State Variables (LZ)
; -----------------------------------------------------------------------------
; These control the dual display mode (2-line compatibility / 4-line native)

DPA_SCRN    EQU     $2090   ; Pointer to active screen buffer (2 bytes)
                            ; Points to either 2-line or 4-line buffer

DPB_NLIN    EQU     $2092   ; Number of display lines (2 or 4)
                            ; Read this to detect current line mode

DPB_WIDE    EQU     $2093   ; Display width (16 or 20 characters)
                            ; 16 for 2-line mode, 20 for 4-line mode

DPB_MODE    EQU     $2184   ; Current display mode flag
                            ; 0 = 2-line mode (CM/XP compatibility)
                            ; 1 = 4-line mode (native LZ)
                            ; Read-only; use DP$MSET to change

; -----------------------------------------------------------------------------
; RAM Banking Variables (LZ64)
; -----------------------------------------------------------------------------
; Bank switching state for extended RAM access

MBB_BANK    EQU     $2186   ; Current RAM bank number (0-3)
MBW_BASE    EQU     $2188   ; Bank window base address (2 bytes)

; =============================================================================
; ROM Entry Points (for reference)
; =============================================================================
; The SWI vector jumps to the OS service dispatcher

SWI_VECTOR  EQU     $FFFA   ; SWI interrupt vector location
RST_VECTOR  EQU     $FFFE   ; Reset vector location
NMI_VECTOR  EQU     $FFFC   ; NMI vector location

; =============================================================================
; Model-Specific Definitions
; =============================================================================
; Uncomment the appropriate section for your target model

; --- CM Model (8KB RAM) ---
; RAM_START   EQU     $2000
; RAM_END     EQU     $4000
; RAM_SIZE    EQU     $2000   ; 8KB

; --- XP Model (16-32KB RAM) ---
; RAM_START   EQU     $2000
; RAM_END     EQU     $6000
; RAM_SIZE    EQU     $4000   ; 16KB base

; --- LZ Model (32-64KB RAM) ---
; RAM_START   EQU     $0400
; RAM_END     EQU     $8000
; RAM_SIZE    EQU     $7C00   ; Up to 32KB direct access

; =============================================================================
; Display Dimensions
; =============================================================================

; CM/XP models (2-line display)
DISP_COLS_2 EQU     16      ; Columns for 2-line display
DISP_ROWS_2 EQU     2       ; Rows for 2-line display

; LA/LZ models (4-line display)
DISP_COLS_4 EQU     20      ; Columns for 4-line display
DISP_ROWS_4 EQU     4       ; Rows for 4-line display

; =============================================================================
; Common Character Codes
; =============================================================================

CHAR_NUL    EQU     $00     ; Null character
CHAR_CR     EQU     $0D     ; Carriage return
CHAR_LF     EQU     $0A     ; Line feed
CHAR_ESC    EQU     $1B     ; Escape
CHAR_SPC    EQU     $20     ; Space
CHAR_DEL    EQU     $7F     ; Delete

; =============================================================================
; End of sysvars.inc
; =============================================================================
