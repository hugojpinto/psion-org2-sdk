; =============================================================================
; Small-C Runtime Library for HD6303 (Psion Organiser II)
; =============================================================================
;
; This file provides runtime support functions for Small-C compiled code.
; It includes:
;   - 16-bit arithmetic (multiply, divide, modulo)
;   - Shift operations
;   - Memory operations
;   - String operations
;   - Stack manipulation helpers
;   - Psion OS wrapper functions
;
; Calling Convention:
;   - Arguments passed on stack (right-to-left push order)
;   - Return value in D register (A:B for 16-bit)
;   - Caller cleans up arguments
;   - X register may be used but must be preserved across calls
;
; Stack Frame (after PSHX + TSX):
;   X+0, X+1:  Saved X (frame pointer)
;   X+2, X+3:  Return address
;   X+4, X+5:  First argument (16-bit) or X+5 for 8-bit low byte
;   X+6, X+7:  Second argument
;   ...
;
; Register Usage:
;   A, B, D - Scratch/return value
;   X       - Pointer operations, preserved across calls
;   SP      - Stack pointer
;
; Author: Hugo José Pinto & Contributors
; =============================================================================

; =============================================================================
; C API Compatibility Wrappers
; =============================================================================
; The Small-C code generator emits calls with single underscore prefixes
; (e.g., JSR _strlen), but our internal implementations use double underscores
; (e.g., __strlen). These wrappers provide compatibility.
; =============================================================================

; -----------------------------------------------------------------------------
; Fixed Zero-Page Storage (must be defined before first use)
; -----------------------------------------------------------------------------
; These use the temporary work words in zero page.
; UTW_S0-3 are trashed by allocator calls, but UTW_W0-W2 are safe.
; These MUST be defined here (not later) to avoid forward reference issues
; in the two-pass assembler.
;
_CALL_OPL_TAG   EQU     UTW_W0  ; $84: Tag of our allocated cell
_CALL_OPL_FP    EQU     UTW_T0  ; $80: Saved frame pointer (caller's X register)
_CALL_OPL_REST  EQU     UTW_T2  ; $82: Restore function address (2 bytes, $82-$83)
; NOTE: Resume address is now stored in cell at _COL_RESUME offset, not zero-page

_strlen:        JMP     __strlen        ; char *s -> int length
_memcpy:        JMP     __memcpy        ; void *dest, void *src, int n -> void *dest
_memset:        JMP     __memset        ; void *dest, int c, int n -> void *dest
_struct_copy:   JMP     __memcpy        ; void *dest, void *src, int size -> void *dest
                                        ; Alias for struct copying: struct_copy(&dest, &src, sizeof(T))

; =============================================================================
; 16-bit Signed Multiplication: D = D * X
; =============================================================================
; Input:  D = multiplicand
;         X = multiplier (via stack or register setup)
; Output: D = product (low 16 bits)
; Clobbers: A, B, X
;
; Algorithm: Shift-and-add multiplication
; For 16x16, we compute the low 16 bits of the result
;
__mul16:
        PSHX            ; Save X (multiplier)
        ; D already contains multiplicand
        ; X contains multiplier (passed in X)

        ; Save multiplicand
        PSHB
        PSHA

        ; Initialize result to 0
        LDD     #0
        PSHB
        PSHA            ; Result on stack

        ; Counter in Y position (use memory)
        LDAB    #16     ; 16 bits to process
        PSHB            ; Counter on stack

        ; Stack layout:
        ; SP+0: counter
        ; SP+1: result (high)
        ; SP+2: result (low)
        ; SP+3: multiplicand (high)
        ; SP+4: multiplicand (low)
        ; SP+5: multiplier (high) - original X
        ; SP+6: multiplier (low)

__mul16_loop:
        ; Check counter
        TSX
        LDAB    0,X     ; Counter
        BEQ     __mul16_done

        ; Decrement counter
        DECB
        STAB    0,X

        ; Shift result left
        LDD     1,X     ; Result
        ASLD            ; Shift left
        STD     1,X

        ; Check MSB of multiplier
        LDD     5,X     ; Multiplier
        BPL     __mul16_skip_add

        ; Add multiplicand to result
        LDD     1,X     ; Result
        ADDD    3,X     ; Add multiplicand
        STD     1,X     ; Store result

__mul16_skip_add:
        ; Shift multiplier left
        TSX
        LDD     5,X
        ASLD
        STD     5,X

        BRA     __mul16_loop

__mul16_done:
        ; Get result
        TSX
        LDD     1,X

        ; Clean up stack (7 bytes: counter + result + multiplicand + multiplier)
        INS             ; Counter
        INS
        INS             ; Result
        INS
        INS             ; Multiplicand
        INS
        INS             ; Multiplier

        RTS


; =============================================================================
; 16-bit Signed Division: D = D / X
; =============================================================================
; Input:  D = dividend
;         X = divisor
; Output: D = quotient
;         Remainder available through __div16_rem
; Clobbers: A, B
;
; Algorithm: Restoring division
;
__div16:
        ; Handle signs
        PSHX            ; Save divisor
        PSHB
        PSHA            ; Save dividend

        ; Determine sign of result
        CLR     __div16_sign

        ; Make dividend positive
        TSX
        LDD     0,X
        BPL     __div16_dvd_pos
        COM     __div16_sign
        COMA
        COMB
        ADDD    #1
        STD     0,X

__div16_dvd_pos:
        ; Make divisor positive
        LDD     2,X     ; Divisor
        BPL     __div16_dvr_pos
        COM     __div16_sign
        COMA
        COMB
        ADDD    #1
        STD     2,X

__div16_dvr_pos:
        ; Do unsigned division
        LDD     0,X     ; Dividend
        LDX     2,X     ; Divisor
        BSR     __udiv16

        ; Apply sign to result
        TST     __div16_sign
        BPL     __div16_pos_result
        COMA
        COMB
        ADDD    #1

__div16_pos_result:
        ; Clean up stack
        PULX            ; Dummy pull (was dividend)
        PULX            ; Restore saved X

        RTS

; Storage for sign during division
__div16_sign:
        RMB     1

; Storage for remainder
__div16_rem:
        RMB     2


; =============================================================================
; 16-bit Unsigned Division: D = D / X
; =============================================================================
; Input:  D = dividend
;         X = divisor
; Output: D = quotient
;         __div16_rem = remainder
;
__udiv16:
        PSHX            ; Save divisor

        ; Check for division by zero
        CPX     #0
        BNE     __udiv16_start

        ; Division by zero: return max value
        LDD     #$FFFF
        STD     __div16_rem
        PULX
        RTS

__udiv16_start:
        ; Initialize remainder to 0
        PSHB
        PSHA            ; Save dividend

        LDD     #0
        STD     __div16_rem

        ; Bit counter
        LDAB    #16
        PSHB

        ; Stack: counter (SP+0), dividend (SP+1,2), divisor (SP+3,4)

__udiv16_loop:
        TSX
        LDAB    0,X     ; Counter
        BEQ     __udiv16_done

        DECB
        STAB    0,X

        ; Shift dividend left, MSB into remainder
        LDD     1,X     ; Dividend
        ASLD
        STD     1,X
        ROL     __div16_rem+1
        ROL     __div16_rem

        ; Compare and subtract remainder with divisor
        LDD     __div16_rem
        SUBD    3,X             ; D = remainder - divisor, sets C if borrow
        BCS     __udiv16_loop   ; remainder < divisor, continue (D reloaded in loop)
        ; Subtraction result is valid (remainder >= divisor)
        STD     __div16_rem

        ; Set LSB of quotient
        TSX
        LDD     1,X
        ORAB    #1
        STD     1,X

        BRA     __udiv16_loop

__udiv16_done:
        ; Get quotient
        INS             ; Pop counter
        PULA
        PULB            ; Quotient in D
        PULX            ; Restore divisor
        RTS


; =============================================================================
; 16-bit Modulo: D = D % X
; =============================================================================
; Input:  D = dividend
;         X = divisor
; Output: D = remainder
;
__mod16:
        BSR     __div16
        LDD     __div16_rem
        RTS


; =============================================================================
; 16-bit Left Shift: D = D << B
; =============================================================================
; Input:  D = value to shift
;         B = shift count (in low byte, from stack or previous op)
; Output: D = shifted value
;
__shl16:
        ; Get shift count (assumed in B from caller context)
        PSHB            ; Save count
        PSHA

        TSX
        LDAB    0,X     ; Get count back
        ANDB    #$0F    ; Limit to 0-15

        PULA            ; Get value high byte
        PULB            ; Value low byte - now D = original value

        ; Shift count in memory
        TSX
        STAB    0,X     ; Store count

__shl16_loop:
        TSX
        TST     0,X     ; Check count
        BEQ     __shl16_done
        DEC     0,X
        ASLD            ; Shift D left
        BRA     __shl16_loop

__shl16_done:
        INS             ; Clean up count
        RTS


; =============================================================================
; 16-bit Right Shift (Arithmetic): D = D >> B
; =============================================================================
; Input:  D = value to shift
;         B = shift count
; Output: D = shifted value (sign-extended)
;
__shr16:
        PSHB            ; Save count
        PSHA

        TSX
        LDAB    0,X
        ANDB    #$0F

        PULA
        PULB

        TSX
        STAB    0,X

__shr16_loop:
        TSX
        TST     0,X
        BEQ     __shr16_done
        DEC     0,X
        ASRA            ; Arithmetic shift right (preserves sign)
        RORB
        BRA     __shr16_loop

__shr16_done:
        INS
        RTS


; =============================================================================
; 16-bit Logical Right Shift: D = D >>> B
; =============================================================================
; Input:  D = value to shift
;         B = shift count
; Output: D = shifted value (zero-filled)
;
__lshr16:
        PSHB
        PSHA

        TSX
        LDAB    0,X
        ANDB    #$0F

        PULA
        PULB

        TSX
        STAB    0,X

__lshr16_loop:
        TSX
        TST     0,X
        BEQ     __lshr16_done
        DEC     0,X
        LSRD            ; Logical shift right
        BRA     __lshr16_loop

__lshr16_done:
        INS
        RTS


; =============================================================================
; Memory Copy: memcpy(dest, src, n)
; =============================================================================
; Input:  Stack: dest (2 bytes), src (2 bytes), n (2 bytes)
; Output: D = dest
;
__memcpy:
        PSHX                ; Save caller's frame
        TSX
        ; Stack: [saved_X 2B][ret 2B][dest 2B][src 2B][n 2B]
        ; Offsets: 0-1=saved_X, 2-3=ret, 4-5=dest, 6-7=src, 8-9=n

        ; Save dest for return value
        LDD     4,X         ; dest
        PSHB
        PSHA                ; saved_dest
        ; Stack: [saved_dest 2B][saved_X 2B][ret 2B][dest 2B][src 2B][n 2B]
        ; After TSX: 0-1=saved_dest, 2-3=saved_X, 4-5=ret, 6-7=dest, 8-9=src, 10-11=n

__memcpy_loop:
        TSX
        LDD     10,X        ; n (count)
        TSTB
        BNE     __memcpy_cont
        TSTA
        BEQ     __memcpy_done
__memcpy_cont:
        SUBD    #1
        STD     10,X        ; update n

        ; Load byte from src
        LDX     8,X         ; src pointer
        LDAB    0,X         ; byte from src
        PSHB                ; save byte BEFORE XGDX destroys it!
        INX                 ; src++
        XGDX                ; D = updated src
        TSX
        STD     9,X         ; update src on stack (offset +1 due to pushed byte)

        ; Store byte to dest
        LDX     7,X         ; dest pointer (offset +1 due to pushed byte)
        PULB                ; get byte back
        STAB    0,X         ; store to dest
        INX                 ; dest++
        XGDX                ; D = updated dest
        TSX
        STD     6,X         ; update dest on stack (byte was popped, back to normal)

        BRA     __memcpy_loop

__memcpy_done:
        ; Return original dest
        PULA
        PULB                ; D = saved_dest (return value)
        PULX                ; Restore caller's frame
        RTS


; =============================================================================
; Memory Set: memset(dest, c, n)
; =============================================================================
; Input:  Stack: dest (2 bytes), c (1 byte), n (2 bytes)
; Output: D = dest
;
__memset:
        PSHX                ; Save caller's frame
        TSX
        ; Stack: [saved_X 2B][ret 2B][dest 2B][c 2B][n 2B]
        ; Offsets: 0-1=saved_X, 2-3=ret, 4-5=dest, 6-7=c, 8-9=n

        LDD     4,X         ; dest
        PSHB
        PSHA                ; Save dest for return
        ; Stack: [saved_dest 2B][saved_X 2B][ret 2B][dest 2B][c 2B][n 2B]
        ; After TSX: 0-1=saved_dest, 2-3=saved_X, 4-5=ret, 6-7=dest, 8-9=c, 10-11=n

__memset_loop:
        TSX
        LDD     10,X        ; n (count)
        TSTB
        BNE     __memset_cont
        TSTA
        BEQ     __memset_done
__memset_cont:
        SUBD    #1
        STD     10,X        ; update n
        LDAB    9,X         ; c low byte (c at 8-9, low byte at 9)
        LDX     6,X         ; dest
        STAB    0,X         ; store byte
        INX                 ; dest++
        XGDX                ; D = updated dest
        TSX
        STD     6,X         ; update dest on stack
        BRA     __memset_loop

__memset_done:
        PULA
        PULB                ; D = saved_dest (return value)
        PULX                ; Restore caller's frame
        RTS


; =============================================================================
; String Length: strlen(s)
; =============================================================================
; Input:  Stack: s (pointer to string)
; Output: D = length (not including null terminator)
;
__strlen:
        TSX
        LDX     2,X     ; Get string pointer

        LDD     #0      ; Count

__strlen_loop:
        TST     0,X     ; Check for null
        BEQ     __strlen_done
        INX
        ADDD    #1
        BRA     __strlen_loop

__strlen_done:
        RTS


; =============================================================================
; Psion Library Wrapper Functions
; =============================================================================
; These functions provide a C-callable interface to Psion OS services.
; They follow the Small-C calling convention:
;   - Arguments passed on stack (right-to-left)
;   - Return value in D (A:B)
;   - Caller cleans up stack
; =============================================================================

; -----------------------------------------------------------------------------
; _cls - Clear screen
; Input:  None
; Output: None
; Uses DP_EMIT with $0C control character to clear the display
; -----------------------------------------------------------------------------
_cls:
        LDAA    #$0C            ; Clear display control character
        SWI
        FCB     $10             ; DP_EMIT
        RTS

; -----------------------------------------------------------------------------
; _cursor - Position cursor
; Input:  Stack: position (0-31 for 2-line, 0-79 for 4-line)
; Output: None
; Uses DP_STAT ($14): A = position, B = status (bit7=on, bit0=underline)
; -----------------------------------------------------------------------------
_cursor:
        PSHX                ; Save caller's frame pointer
        TSX
        LDAA    5,X         ; Get position into A register
        CLRB                ; B = 0 (cursor off, block style)
        SWI
        FCB     $14         ; DP_STAT: A = position, B = status
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _print - Print C-style null-terminated string
; Input:  Stack: pointer to null-terminated string
; Output: None
; Uses DP_PRNT ($11): X = string address, B = length
; -----------------------------------------------------------------------------
_print:
        PSHX                ; Save caller's frame pointer
        TSX
        LDX     4,X         ; Get string pointer
        ; Calculate length of C string (count until null)
        PSHX                ; Save string pointer for DP_PRNT
        CLRB                ; Length counter = 0
_print_len:
        TST     0,X         ; Test byte at X
        BEQ     _print_do   ; If null, done counting
        INX                 ; Next char
        INCB                ; Length++
        BRA     _print_len
_print_do:
        PULX                ; Restore string pointer
        ; B = length, X = string start
        SWI
        FCB     $11         ; DP_PRNT
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _getkey - Wait for and get keypress
; Input:  None
; Output: D = key code (in low byte)
; Uses KB_GETK ($48): returns key in B register
; -----------------------------------------------------------------------------
_getkey:
        SWI
        FCB     $48         ; KB_GETK
        ; Key code is returned in B
        CLRA                ; Clear high byte, key in B = D
        RTS

; -----------------------------------------------------------------------------
; _testkey - Test if key is available (non-blocking)
; Input:  None
; Output: D = key code if available, 0 if not
; Uses KB_TEST ($4B): returns key in B (0 if no key)
;
; IMPORTANT: When called with interrupts DISABLED, KB_TEST polls the keyboard
; directly with a 50ms delay, allowing non-blocking key detection even when
; the normal keyboard interrupt handler isn't filling the buffer.
; We use this mode for reliable key detection in game loops.
; -----------------------------------------------------------------------------
_testkey:
        TPA                 ; Get CCR into A
        PSHA                ; Save original CCR
        SEI                 ; Disable interrupts - forces KB_TEST to poll directly
        SWI
        FCB     $4B         ; KB_TEST - polls keyboard with 50ms delay when I=1
        PULA                ; Restore original CCR
        TAP                 ; Put it back
        TSTB                ; Test if key returned (0 = no key)
        BEQ     _testkey_none
        ; Key available in B
        CLRA
        RTS
_testkey_none:
        LDD     #0
        RTS

; -----------------------------------------------------------------------------
; _beep - Sound a beep
; Input:  None
; Output: None
; Uses BZ_BELL ($0E)
; -----------------------------------------------------------------------------
_beep:
        SWI
        FCB     $0E         ; BZ_BELL
        RTS

; -----------------------------------------------------------------------------
; _delay - Wait for specified ticks (1 tick ≈ 1/32 second)
; Input:  Stack: ticks (16-bit)
; Output: None
; Uses TM_WAIT ($6C): D = number of ticks to wait
; -----------------------------------------------------------------------------
_delay:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     4,X         ; Get ticks value - arg at X+4,X+5 after PSHX
        SWI
        FCB     $6C         ; TM_WAIT
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _print_int - Print integer value
; Input:  Stack: integer value (16-bit)
; Output: None
; Uses UT_UTOB ($7A) to convert to string, then DP_PRNT ($11) to display
; UT_UTOB: D = value, X = buffer address
; -----------------------------------------------------------------------------
_print_int:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     4,X         ; Get integer value - arg at X+4,X+5 after PSHX

        ; Check if negative (bit 15 set)
        BPL     _print_int_pos  ; Branch if positive

        ; Negative: print '-' and negate
        PSHA                ; Save A
        PSHB                ; Save B
        LDAA    #'-'
        SWI
        FCB     $10         ; DP_EMIT: print '-'
        PULB                ; Restore B
        PULA                ; Restore A

        ; Negate D: D = 0 - D = (~D) + 1
        COMA                ; Complement A
        COMB                ; Complement B
        ADDD    #1          ; Add 1 to complete two's complement

_print_int_pos:
        ; Use UT_UTOB to convert to decimal string
        ; D = value (now positive), X = buffer address
        LDX     #_print_int_buf
        SWI
        FCB     $7A         ; UT_UTOB

        ; UT_UTOB returns length in B, string at buffer
        ; B = length, now print
        LDX     #_print_int_buf
        SWI
        FCB     $11         ; DP_PRNT
        PULX                ; Restore caller's frame pointer
        RTS

; Buffer for print_int (max 6 digits + sign + null)
_print_int_buf:
        RMB     8

; -----------------------------------------------------------------------------
; _putchar - Output single character
; Input:  Stack: character (in low byte)
; Output: None
; Uses DP_EMIT ($10): A = character to emit
; -----------------------------------------------------------------------------
_putchar:
        PSHX                ; Save caller's frame pointer
        TSX
        LDAA    5,X         ; Get character (low byte) - arg at X+4,X+5 after PSHX
        SWI
        FCB     $10         ; DP_EMIT
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _udg_define - Define a User Defined Graphic character
; Input:  Stack: char_num (0-7), data (pointer to 8 bytes)
;         After PSHX+TSX: char_num at 4,X, data at 6,X
; Output: None
;
; Defines a custom 5x8 character for display using HD44780 CGRAM.
; LCD_CTRL ($0180) receives command, LCD_DATA ($0181) receives data.
;
; CRITICAL TIMING: The HD44780 LCD controller needs ~37-40µs to process each
; command or data write. On real hardware, we must wait for the busy flag
; (bit 7 of status register at $0180) to clear before each write. The emulator
; doesn't enforce this timing, but real hardware does - writing too fast
; causes data corruption (shows as horizontal lines instead of correct pattern).
;
; UDG data format: 8 bytes, one per row (top to bottom).
; Each byte uses bits 0-4 for the 5-pixel width (bit 0 = rightmost pixel).
;
; Reference: Psion LZ Technical Reference, Chapter 6 "UDG Characters"
;            HD44780 Datasheet - Command execution times
; -----------------------------------------------------------------------------
_udg_define:
        PSHX                ; Save caller's frame pointer
        TSX
        ;
        ; Disable interrupts during CGRAM access
        ;
        SEI                 ; Set interrupt mask (disable IRQ)
        ;
        ; Calculate CGRAM address: 0x40 | (char_num << 3)
        ; This sets the write pointer to the start of the UDG bitmap
        ;
        LDAA    5,X         ; Get char_num (low byte, 0-7)
        ANDA    #$07        ; Mask to valid range 0-7
        ASLA                ; char_num << 1
        ASLA                ; char_num << 2
        ASLA                ; char_num << 3
        ORAA    #$40        ; Set CGRAM address command (bit 6)
        ;
        ; Wait for LCD ready, then send CGRAM address command
        ;
        BSR     _udg_wait   ; Wait for busy flag to clear
        STAA    $0180       ; Send command to LCD controller
        ;
        ; Get pointer to bitmap data
        ;
        LDX     6,X         ; X = pointer to data array
        ;
        ; Write 8 bytes of bitmap data, waiting for LCD ready before each
        ;
        LDAB    #8          ; Counter: 8 rows to write
_udg_loop:
        BSR     _udg_wait   ; Wait for busy flag to clear
        LDAA    0,X         ; Get bitmap byte
        STAA    $0181       ; Write to LCD data register (auto-increments CGRAM ptr)
        INX                 ; Next bitmap byte
        DECB                ; Decrement counter
        BNE     _udg_loop   ; Loop until all 8 bytes written
        ;
        ; Restore display RAM pointer mode (set DDRAM address 0)
        ; This ensures subsequent putchar calls write to display, not CGRAM
        ;
        BSR     _udg_wait   ; Wait for busy flag to clear
        LDAA    #$80        ; Set DDRAM address 0 command
        STAA    $0180       ; Send command
        ;
        ; Re-enable interrupts
        ;
        CLI                 ; Clear interrupt mask (enable IRQ)
        ;
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _udg_wait - Wait for HD44780 LCD busy flag to clear
; Input:  None
; Output: None (all registers preserved)
;
; The HD44780 sets bit 7 of the status register while processing a command.
; We poll this bit until it clears, indicating the LCD is ready for the next
; command or data write. Typical wait time is ~37-40µs per operation.
;
; Uses TST instead of LDAA to avoid clobbering the A register - this matches
; the ROM's implementation and is critical for the CGRAM address write.
;
; On the Psion, reading from $0180 returns the LCD status register:
;   Bit 7: Busy flag (1 = busy, 0 = ready)
;   Bits 6-0: Current address counter value
; -----------------------------------------------------------------------------
_udg_wait:
        TST     $0180       ; Test LCD status register (preserves A)
        BMI     _udg_wait   ; Loop if bit 7 (busy) is set
        RTS                 ; Return when LCD is ready


; =============================================================================
; Additional Utility Functions
; =============================================================================

; -----------------------------------------------------------------------------
; _exit - Exit program and return to Psion menu
; Input:  None
; Output: Does not return
; Simply returns from the USR() call that invoked the program
; -----------------------------------------------------------------------------
_exit:
        RTS             ; Return to caller (USR() in OPL or system menu)

; -----------------------------------------------------------------------------
; _abs - Absolute value of integer
; Input:  Stack: n (16-bit signed integer)
; Output: D = |n|
; Computes absolute value using two's complement negation if negative
; -----------------------------------------------------------------------------
_abs:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     4,X         ; Get argument n from stack (at X+4,X+5)
        BPL     _abs_done   ; If positive, already done
        ; Negate D: D = ~D + 1 (two's complement)
        COMA                ; Complement high byte
        COMB                ; Complement low byte
        ADDD    #1          ; Add 1 to complete two's complement
_abs_done:
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _min - Return minimum of two integers
; Input:  Stack: a (16-bit), b (16-bit)
;         First arg (a) at 4,X, second arg (b) at 6,X (after PSHX+TSX)
; Output: D = minimum of a and b
; Uses signed comparison
; IMPORTANT: Branch IMMEDIATELY after SUBD because LDD modifies N,Z,V flags!
; -----------------------------------------------------------------------------
_min:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     6,X         ; Load b (second arg)
        SUBD    4,X         ; D = b - a, sets flags for signed compare
        BGE     _min_use_a  ; If b >= a (b-a >= 0), a is smaller, use a
        ; b < a, return b (the smaller one)
        LDD     6,X         ; Reload b
        BRA     _min_done
_min_use_a:
        LDD     4,X         ; Return a (the smaller one)
_min_done:
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _max - Return maximum of two integers
; Input:  Stack: a (16-bit), b (16-bit)
;         First arg (a) at 4,X, second arg (b) at 6,X (after PSHX+TSX)
; Output: D = maximum of a and b
; Uses signed comparison
; IMPORTANT: Branch IMMEDIATELY after SUBD because LDD modifies N,Z,V flags!
; -----------------------------------------------------------------------------
_max:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     6,X         ; Load b (second arg)
        SUBD    4,X         ; D = b - a, sets flags for signed compare
        BLE     _max_use_a  ; If b <= a (b-a <= 0), a is larger, use a
        ; b > a, return b (the larger one)
        LDD     6,X         ; Reload b
        BRA     _max_done
_max_use_a:
        LDD     4,X         ; Return a (the larger one)
_max_done:
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _strcpy - Copy string
; Input:  Stack: dest (pointer), src (pointer)
;         After TSX: dest at 2,X, src at 4,X
; Output: D = dest pointer
; Copies src to dest including null terminator
; Simple implementation like __strlen - no PSHX
; -----------------------------------------------------------------------------
_strcpy:
        TSX
        ; Stack: [ret 2B][dest 2B][src 2B]
        ; Offsets: 0-1=ret, 2-3=dest, 4-5=src
        ; Save original dest for return, and make working copies
        LDD     2,X         ; dest
        PSHB
        PSHA                ; dest_work
        PSHB
        PSHA                ; dest_ret (original for return)
        LDD     4,X         ; src
        PSHB
        PSHA                ; src_work
        ; Stack: [src_work 2B][dest_ret 2B][dest_work 2B][ret 2B][dest 2B][src 2B]
        ; After TSX: 0-1=src_work, 2-3=dest_ret, 4-5=dest_work
_strcpy_loop:
        ; Load byte from src
        TSX
        LDX     0,X         ; X = src_work
        LDAB    0,X         ; B = *src
        INX                 ; src++
        PSHX                ; save new_src first
        PSHB                ; save byte second
        ; Stack: [byte 1B][new_src 2B][src_work 2B][dest_ret 2B][dest_work 2B][...]
        ; After TSX: 0=byte, 1-2=new_src, 3-4=src_work, 5-6=dest_ret, 7-8=dest_work
        TSX
        LDD     1,X         ; D = new_src
        STD     3,X         ; Update src_work
        LDAB    0,X         ; B = byte (from stack, before loading X)
        LDX     7,X         ; X = dest_work (now X is dest pointer)
        STAB    0,X         ; *dest = byte
        INX                 ; dest++
        PSHX                ; save new_dest
        ; Stack: [new_dest 2B][byte 1B][new_src 2B][src_work 2B][dest_ret 2B][dest_work 2B][...]
        TSX
        LDD     0,X         ; D = new_dest
        STD     9,X         ; Update dest_work (0=new_dest, 1=byte, 3=new_src, 5=src_work, 7=dest_ret, 9=dest_work)
        LDAB    2,X         ; B = byte for null test
        INS                 ; Remove new_dest
        INS
        INS                 ; Remove byte
        INS                 ; Remove new_src
        INS
        ; Stack: [src_work 2B][dest_ret 2B][dest_work 2B][...]
        TSTB                ; Test byte (still in B)
        BNE     _strcpy_loop
        ; Done - return original dest
        PULA
        PULB                ; Remove src_work
        PULA
        PULB                ; D = dest_ret (return value)
        INS                 ; Remove dest_work
        INS
        RTS

; -----------------------------------------------------------------------------
; _strcmp - Compare two strings
; Input:  Stack: a (pointer), b (pointer)
;         First arg (a) at 4,X, second arg (b) at 6,X (after PSHX+TSX)
; Output: D = 0 if equal, <0 if a<b, >0 if a>b
; Compares strings byte by byte until null or difference
; NOTE: XGDX corrupts D, so we must save both bytes before pointer updates
; -----------------------------------------------------------------------------
_strcmp:
        PSHX                ; Save caller's frame pointer
_strcmp_loop:
        ; Stack: [saved_X 2B][ret 2B][arg_a 2B][arg_b 2B]
        ; After TSX: 0-1=saved_X, 2-3=ret, 4-5=arg_a, 6-7=arg_b
        TSX
        LDX     4,X         ; Get pointer to string a
        LDAB    0,X         ; Get byte from a into B
        PSHB                ; Save byte_a
        ; Stack: [byte_a 1B][saved_X 2B][ret 2B][arg_a 2B][arg_b 2B]
        ; After TSX: 0=byte_a, 1-2=saved_X, 3-4=ret, 5-6=arg_a, 7-8=arg_b
        INX                 ; a++
        XGDX                ; D = incremented a pointer
        TSX
        STD     5,X         ; Update arg_a pointer
        LDX     7,X         ; Get pointer to string b
        LDAB    0,X         ; Get byte from b into B
        PSHB                ; Save byte_b
        ; Stack: [byte_b 1B][byte_a 1B][saved_X 2B][ret 2B][arg_a 2B][arg_b 2B]
        ; After TSX: 0=byte_b, 1=byte_a, 2-3=saved_X, 4-5=ret, 6-7=arg_a, 8-9=arg_b
        INX                 ; b++
        XGDX                ; D = incremented b pointer (safe, byte_b was saved)
        TSX
        STD     8,X         ; Update arg_b pointer
        ; Compare the saved bytes
        PULB                ; byte_b into B
        PULA                ; byte_a into A
        ; Now A = byte_a, B = byte_b
        ; Save byte_a for null check (SBA will overwrite A with result)
        PSHA                ; Save byte_a
        SBA                 ; A = byte_a - byte_b
        BNE     _strcmp_diff_pop ; If different, pop saved byte and return difference
        ; Bytes are equal - check if null terminator
        PULA                ; Restore byte_a
        TSTA                ; Test byte_a (if null, we're done)
        BNE     _strcmp_loop ; Continue if not null
        ; Both strings ended equally
        LDD     #0
        PULX                ; Restore caller's frame pointer
        RTS
_strcmp_diff_pop:
        INS                 ; Discard saved byte_a (1 byte)
_strcmp_diff:
        ; A contains byte_a - byte_b
        ; Sign-extend A into D
        TAB                 ; B = A (the difference)
        BPL     _strcmp_pos
        LDAA    #$FF        ; Sign extend negative to high byte
        BRA     _strcmp_ret
_strcmp_pos:
        CLRA                ; Sign extend positive (zero high byte)
_strcmp_ret:
        ; D = sign-extended difference (A:B)
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _strcat - Concatenate strings
; Input:  Stack: dest (pointer), src (pointer)
;         First arg (dest) at 4,X, second arg (src) at 6,X (after PSHX+TSX)
; Output: D = dest pointer
; Appends src to end of dest
; -----------------------------------------------------------------------------
_strcat:
        PSHX                ; Save caller's frame pointer
        TSX
        ; Save original dest for return value
        LDD     4,X         ; dest (first arg)
        PSHB
        PSHA                ; Saved original dest at SP+0,SP+1
        ; Find end of dest (where null terminator is)
_strcat_find_end:
        TSX
        LDX     6,X         ; Get current dest pointer (+2 for saved dest, was at 4,X)
        TST     0,X         ; Check if null
        BEQ     _strcat_copy ; Found end, start copying
        INX                 ; dest++
        XGDX
        TSX
        STD     6,X         ; Update dest pointer (+2 for saved dest, was at 4,X)
        BRA     _strcat_find_end
_strcat_copy:
        ; Now copy src to current dest position
        TSX
        LDX     8,X         ; Get src pointer (+2 for saved dest, was at 6,X)
        LDAB    0,X         ; Get byte from src
        PSHB                ; Save byte
        INX                 ; src++
        XGDX
        TSX
        STD     9,X         ; Update src pointer (+1 for saved byte, +2 for saved dest, was at 6,X)
        ; Store to dest
        LDX     7,X         ; Get dest pointer (+1 for saved byte, +2 for saved dest, was at 4,X)
        PULB                ; Get byte
        STAB    0,X         ; Store to dest
        TSTB                ; Check if null terminator
        BEQ     _strcat_done ; Done if null
        INX                 ; dest++
        XGDX
        TSX
        STD     6,X         ; Update dest pointer (+2 for saved dest, was at 4,X)
        BRA     _strcat_copy
_strcat_done:
        ; Return original dest
        PULA
        PULB                ; D = original dest
        PULX                ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _memcmp - Compare memory blocks
; Input:  Stack: a (pointer), b (pointer), n (count)
;         First arg (a) at 4,X, second (b) at 6,X, third (n) at 8,X (after PSHX+TSX)
; Output: D = 0 if equal, <0 if a<b, >0 if a>b
; Compares n bytes of memory
; NOTE: XGDX corrupts D, so we must save both bytes before pointer updates
; -----------------------------------------------------------------------------
_memcmp:
        PSHX                ; Save caller's frame pointer
_memcmp_loop:
        ; Stack: [saved_X 2B][ret 2B][arg_a 2B][arg_b 2B][n 2B]
        ; After TSX: 0-1=saved_X, 2-3=ret, 4-5=arg_a, 6-7=arg_b, 8-9=n
        TSX
        LDD     8,X         ; Get count n (third arg)
        ; Test if count is zero
        TSTB
        BNE     _memcmp_cont
        TSTA
        BEQ     _memcmp_equal ; n == 0, equal
_memcmp_cont:
        ; Decrement count
        SUBD    #1
        STD     8,X         ; Update count
        ; Get byte from a
        LDX     4,X         ; pointer a
        LDAB    0,X         ; byte_a into B
        PSHB                ; save byte_a
        ; Stack: [byte_a 1B][saved_X 2B][ret 2B][arg_a 2B][arg_b 2B][n 2B]
        ; After TSX: 0=byte_a, 1-2=saved_X, 3-4=ret, 5-6=arg_a, 7-8=arg_b, 9-10=n
        INX
        XGDX                ; D = incremented a pointer
        TSX
        STD     5,X         ; Update a pointer
        ; Get byte from b
        LDX     7,X         ; pointer b
        LDAB    0,X         ; byte_b into B
        PSHB                ; save byte_b
        ; Stack: [byte_b 1B][byte_a 1B][saved_X 2B][ret 2B][arg_a 2B][arg_b 2B][n 2B]
        ; After TSX: 0=byte_b, 1=byte_a, 2-3=saved_X, 4-5=ret, 6-7=arg_a, 8-9=arg_b, 10-11=n
        INX
        XGDX                ; D = incremented b pointer (safe, byte_b was saved)
        TSX
        STD     8,X         ; Update b pointer
        ; Compare bytes: byte_a - byte_b
        PULB                ; byte_b into B
        PULA                ; byte_a into A
        ; Now A = byte_a, B = byte_b
        SBA                 ; A = byte_a - byte_b
        BNE     _memcmp_diff
        BRA     _memcmp_loop
_memcmp_equal:
        LDD     #0
        PULX
        RTS
_memcmp_diff:
        ; A contains difference, sign-extend to D
        TAB                 ; B = A (the difference)
        BPL     _memcmp_pos
        LDAA    #$FF        ; Negative sign extension
        BRA     _memcmp_ret
_memcmp_pos:
        CLRA                ; Positive sign extension
_memcmp_ret:
        PULX
        RTS

; =============================================================================
; STANDARD LIBRARY EXPANSION - Phase 2 Core Functions
; =============================================================================
; These functions were added as part of the Standard Library Expansion
; (see specs/12-standard-library-expansion.md).
;
; Functions in this section:
;   - _atoi    : Convert string to integer
;   - _itoa    : Convert integer to string buffer
;   - _strchr  : Find character in string
;   - _strncpy : Bounded string copy
;   - _strncmp : Bounded string compare
;
; All functions follow the Small-C calling convention:
;   - Arguments on stack (right-to-left push order)
;   - Return value in D register
;   - Caller cleans up stack
;   - X register preserved across calls (via PSHX/PULX)
; =============================================================================

; -----------------------------------------------------------------------------
; _atoi - Convert ASCII string to integer
; -----------------------------------------------------------------------------
; Parses a null-terminated string and converts it to a 16-bit signed integer.
; Leading whitespace (space, tab) is skipped. An optional sign (+/-) may
; precede the digits. Parsing stops at the first non-digit character.
;
; Input:  Stack: s (pointer to null-terminated string)
;         After PSHX+TSX: string pointer at 4,X
; Output: D = integer value (0 if no valid digits found)
;
; Algorithm:
;   1. Skip leading whitespace (space, tab)
;   2. Check for optional sign (+/-)
;   3. Accumulate digits: result = result * 10 + digit
;   4. Apply sign if negative
;
; Multiplication by 10 optimization:
;   Uses x*10 = x*8 + x*2 = (x<<3) + (x<<1) instead of calling __mul16.
;   This is much faster for the common case of decimal parsing.
;
; Examples:
;   "123"   -> 123
;   "-456"  -> -456
;   "  +78" -> 78
;   "12abc" -> 12 (stops at 'a')
;   "xyz"   -> 0  (no digits)
;
; Code size: ~85 bytes
; -----------------------------------------------------------------------------
_atoi:
        PSHX                    ; Save caller's frame pointer
        TSX
        LDX     4,X             ; X = string pointer

        ; --- Skip whitespace ---
_atoi_ws:
        LDAB    0,X
        CMPB    #' '
        BEQ     _atoi_ws_next
        CMPB    #$09            ; Tab
        BNE     _atoi_chk_sign
_atoi_ws_next:
        INX
        BRA     _atoi_ws

        ; --- Check sign ---
_atoi_chk_sign:
        CLR     _atoi_neg
        LDAB    0,X
        CMPB    #'-'
        BNE     _atoi_chk_plus
        COM     _atoi_neg       ; Mark negative
        INX
        BRA     _atoi_begin
_atoi_chk_plus:
        CMPB    #'+'
        BNE     _atoi_begin
        INX

        ; --- Initialize result = 0 ---
_atoi_begin:
        LDD     #0
        STD     _atoi_result

        ; --- Main digit loop ---
_atoi_dloop:
        LDAB    0,X             ; Get character
        SUBB    #'0'            ; Convert to digit (0-9)
        BMI     _atoi_finish    ; < '0' -> done
        CMPB    #9
        BHI     _atoi_finish    ; > '9' -> done

        ; Save digit, multiply result by 10, add digit
        STAB    _atoi_digit     ; Save digit temporarily

        ; result = result * 10
        ; Using x*10 = (x*4 + x)*2 = (x<<2 + x)<<1
        ; Or x*10 = x*8 + x*2 = (x<<3) + (x<<1)
        LDD     _atoi_result
        ASLD                    ; D = result * 2
        STD     _atoi_tmp       ; Save result*2
        ASLD                    ; D = result * 4
        ASLD                    ; D = result * 8
        ADDD    _atoi_tmp       ; D = result*10

        ; Add digit to D
        ADDB    _atoi_digit     ; Add digit to low byte
        ADCA    #0              ; Propagate carry to high byte

        STD     _atoi_result    ; Store new result

        INX                     ; Advance to next character
        BRA     _atoi_dloop

        ; --- Apply sign and return ---
_atoi_finish:
        LDD     _atoi_result
        TST     _atoi_neg       ; Check if negative
        BEQ     _atoi_ret       ; If not negative, return as-is
        ; Negate: D = -D = ~D + 1
        COMA
        COMB
        ADDD    #1
_atoi_ret:
        PULX                    ; Restore caller's frame pointer
        RTS

; --- Local storage for _atoi ---
_atoi_neg:      RMB     1       ; Sign flag: 0=positive, $FF=negative
_atoi_result:   RMB     2       ; Accumulated result
_atoi_tmp:      RMB     2       ; Temporary for multiplication
_atoi_digit:    RMB     1       ; Current digit value

; -----------------------------------------------------------------------------
; _itoa - Convert integer to null-terminated string
; -----------------------------------------------------------------------------
; Converts a 16-bit signed integer to a decimal string representation.
; The string is stored in the provided buffer with a null terminator.
;
; Input:  Stack: n (16-bit signed integer), s (pointer to buffer)
;         After PSHX+TSX: n at 4,X, s at 6,X
; Output: D = pointer to buffer (s)
;
; Buffer size: Caller must provide at least 7 bytes for the buffer:
;   - Sign: 1 byte (optional '-')
;   - Digits: up to 5 bytes (-32768 to 32767)
;   - Null terminator: 1 byte
;
; Algorithm:
;   1. Handle sign (if negative, negate and remember to add '-')
;   2. Extract digits by repeated division by 10 (generates in reverse)
;   3. Reverse the digit string in place
;   4. Add sign if needed
;
; Examples:
;   itoa(123, buf)   -> "123"
;   itoa(-456, buf)  -> "-456"
;   itoa(0, buf)     -> "0"
;   itoa(32767, buf) -> "32767"
;
; Code size: ~95 bytes
; -----------------------------------------------------------------------------
_itoa:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Get parameters
        LDD     4,X             ; D = n (the integer)
        LDX     6,X             ; X = s (buffer pointer)
        STX     _itoa_buf       ; Save buffer start for return value
        STX     _itoa_ptr       ; Working pointer

        ; Check if negative
        CLR     _itoa_neg
        TSTA                    ; Check sign bit (high bit of A)
        BPL     _itoa_pos       ; If positive, skip negation
        COM     _itoa_neg       ; Set negative flag
        ; Negate D: D = -D
        COMA
        COMB
        ADDD    #1

_itoa_pos:
        ; D = absolute value of n
        ; Now extract digits by dividing by 10 repeatedly
        ; Store digits in reverse order, then reverse at end

        ; Special case: if n == 0, just store "0"
        STD     _itoa_val       ; Save value
        TSTB
        BNE     _itoa_digit_loop
        TSTA
        BNE     _itoa_digit_loop
        ; Value is 0
        LDX     _itoa_ptr
        LDAB    #'0'
        STAB    0,X
        INX
        STX     _itoa_ptr
        BRA     _itoa_add_sign

_itoa_digit_loop:
        ; While val > 0: digit = val % 10; val = val / 10
        LDD     _itoa_val
        TSTA
        BNE     _itoa_do_div
        TSTB
        BEQ     _itoa_add_sign  ; val == 0, done extracting digits

_itoa_do_div:
        ; Divide D by 10, get quotient and remainder
        ; We'll use __udiv16 which leaves remainder in __div16_rem
        LDX     #10
        JSR     __udiv16        ; D = D / 10, __div16_rem = D % 10
        STD     _itoa_val       ; Save quotient as new value

        ; Get remainder (the digit)
        LDD     __div16_rem
        ADDB    #'0'            ; Convert 0-9 to '0'-'9'

        ; Store digit at current position
        LDX     _itoa_ptr
        STAB    0,X
        INX
        STX     _itoa_ptr

        BRA     _itoa_digit_loop

_itoa_add_sign:
        ; Add minus sign if negative
        TST     _itoa_neg
        BEQ     _itoa_terminate
        LDX     _itoa_ptr
        LDAB    #'-'
        STAB    0,X
        INX
        STX     _itoa_ptr

_itoa_terminate:
        ; Add null terminator
        LDX     _itoa_ptr
        CLR     0,X

        ; Now reverse the string in place
        ; Start pointer = _itoa_buf
        ; End pointer = _itoa_ptr - 1 (last char before null)
        LDX     _itoa_ptr
        DEX                     ; X points to last char
        STX     _itoa_end

        LDX     _itoa_buf       ; X points to first char
        ; Reverse while start < end

_itoa_rev_loop:
        CPX     _itoa_end       ; Compare start with end
        BHS     _itoa_done      ; If start >= end, done reversing

        ; Swap characters at start (X) and end (_itoa_end)
        LDAB    0,X             ; B = char at start
        PSHX                    ; Save start pointer
        LDX     _itoa_end
        LDAA    0,X             ; A = char at end
        STAB    0,X             ; Store start char at end
        PULX                    ; Restore start pointer
        STAA    0,X             ; Store end char at start

        ; Move pointers inward
        INX                     ; start++
        PSHX
        LDX     _itoa_end
        DEX                     ; end--
        STX     _itoa_end
        PULX

        BRA     _itoa_rev_loop

_itoa_done:
        ; Return buffer pointer
        LDD     _itoa_buf
        PULX                    ; Restore caller's frame pointer
        RTS

; --- Local storage for _itoa ---
_itoa_neg:      RMB     1       ; Sign flag
_itoa_val:      RMB     2       ; Current value being converted
_itoa_buf:      RMB     2       ; Buffer start pointer (for return)
_itoa_ptr:      RMB     2       ; Current write position
_itoa_end:      RMB     2       ; End pointer for reversal

; -----------------------------------------------------------------------------
; _strchr - Find first occurrence of character in string
; -----------------------------------------------------------------------------
; Searches the string s for the first occurrence of character c.
; The null terminator is considered part of the string, so strchr(s, 0)
; returns a pointer to the terminating null.
;
; Input:  Stack: s (pointer to string), c (character to find)
;         After PSHX+TSX: s at 4,X, c at 6,X (low byte at 7,X)
; Output: D = pointer to first occurrence of c, or 0 (NULL) if not found
;
; Examples:
;   strchr("Hello", 'l') -> pointer to first 'l'
;   strchr("Hello", 'x') -> 0 (NULL)
;   strchr("Hello", 0)   -> pointer to null terminator
;
; Code size: ~30 bytes
; -----------------------------------------------------------------------------
_strchr:
        PSHX                    ; Save caller's frame pointer
        TSX
        LDX     4,X             ; X = string pointer
        TSX
        LDAB    7,X             ; B = character to find (low byte of c argument)

        ; Restore X to point to string
        LDX     4,X             ; X = string pointer again

_strchr_loop:
        LDAA    0,X             ; A = current character in string
        CBA                     ; Compare A with B (current char with search char)
        BEQ     _strchr_found   ; Found the character

        ; Check if we've reached null terminator (and didn't find char)
        TSTA
        BEQ     _strchr_not_found  ; Reached end without finding

        INX                     ; Advance to next character
        BRA     _strchr_loop

_strchr_found:
        ; Return pointer to found character
        XGDX                    ; D = X (pointer to found char)
        PULX                    ; Restore caller's frame pointer
        RTS

_strchr_not_found:
        ; Return NULL (0)
        LDD     #0
        PULX                    ; Restore caller's frame pointer
        RTS

; -----------------------------------------------------------------------------
; _strncpy - Copy string with length limit
; -----------------------------------------------------------------------------
; Copies at most n characters from src to dest. If src is shorter than n,
; the remainder of dest is filled with null characters. If src is n or more
; characters long, dest will NOT be null-terminated.
;
; WARNING: Unlike strcpy, strncpy may NOT null-terminate dest if src >= n chars.
; Always ensure dest has space for n characters.
;
; Input:  Stack: dest (pointer), src (pointer), n (count)
;         After PSHX+TSX: dest at 4,X, src at 6,X, n at 8,X
; Output: D = dest pointer
;
; Behavior:
;   - Copy up to n characters from src to dest
;   - If null found in src before n chars, pad dest with nulls up to n
;   - If n chars copied without finding null, dest is NOT null-terminated
;
; Examples:
;   strncpy(buf, "Hi", 5)   -> buf = "Hi\0\0\0" (padded with nulls)
;   strncpy(buf, "Hello", 3) -> buf = "Hel" (NOT null-terminated!)
;
; Code size: ~60 bytes
; -----------------------------------------------------------------------------
_strncpy:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Save dest for return value
        LDD     4,X             ; dest
        STD     _strncpy_ret    ; Save for return

        ; Copy parameters to working storage
        LDD     4,X             ; dest
        STD     _strncpy_dst
        LDD     6,X             ; src
        STD     _strncpy_src
        LDD     8,X             ; n
        STD     _strncpy_n

_strncpy_copy:
        ; Check if n == 0
        LDD     _strncpy_n
        TSTB
        BNE     _strncpy_do_copy
        TSTA
        BEQ     _strncpy_done   ; n == 0, done

_strncpy_do_copy:
        ; Decrement n
        SUBD    #1
        STD     _strncpy_n

        ; Get character from src
        LDX     _strncpy_src
        LDAB    0,X             ; B = *src

        ; Store to dest
        LDX     _strncpy_dst
        STAB    0,X             ; *dest = B

        ; Advance pointers
        LDX     _strncpy_src
        INX
        STX     _strncpy_src
        LDX     _strncpy_dst
        INX
        STX     _strncpy_dst

        ; Check if we just copied a null
        TSTB
        BEQ     _strncpy_pad    ; If null, switch to padding mode
        BRA     _strncpy_copy   ; Continue copying

_strncpy_pad:
        ; Pad remainder with nulls
        LDD     _strncpy_n
        TSTB
        BNE     _strncpy_do_pad
        TSTA
        BEQ     _strncpy_done   ; n == 0, done padding

_strncpy_do_pad:
        ; Decrement n
        LDD     _strncpy_n
        SUBD    #1
        STD     _strncpy_n

        ; Store null to dest
        LDX     _strncpy_dst
        CLR     0,X
        INX
        STX     _strncpy_dst

        BRA     _strncpy_pad

_strncpy_done:
        ; Return original dest
        LDD     _strncpy_ret
        PULX                    ; Restore caller's frame pointer
        RTS

; --- Local storage for _strncpy ---
_strncpy_ret:   RMB     2       ; Return value (original dest)
_strncpy_dst:   RMB     2       ; Working dest pointer
_strncpy_src:   RMB     2       ; Working src pointer
_strncpy_n:     RMB     2       ; Remaining count

; -----------------------------------------------------------------------------
; _strncmp - Compare strings with length limit
; -----------------------------------------------------------------------------
; Compares at most n characters of two strings. Comparison stops when:
;   - A difference is found
;   - A null terminator is reached in either string
;   - n characters have been compared
;
; Input:  Stack: s1 (pointer), s2 (pointer), n (count)
;         After PSHX+TSX: s1 at 4,X, s2 at 6,X, n at 8,X
; Output: D = 0 if equal, <0 if s1<s2, >0 if s1>s2
;
; The comparison is done using unsigned character values (standard C behavior).
;
; Examples:
;   strncmp("abc", "abd", 3) -> negative (c < d)
;   strncmp("abc", "abc", 3) -> 0 (equal)
;   strncmp("abc", "ab", 3)  -> positive (c > null)
;   strncmp("abcd", "abce", 2) -> 0 (only first 2 chars compared)
;
; Code size: ~55 bytes
; -----------------------------------------------------------------------------
_strncmp:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Copy parameters to working storage
        LDD     4,X             ; s1
        STD     _strncmp_s1
        LDD     6,X             ; s2
        STD     _strncmp_s2
        LDD     8,X             ; n
        STD     _strncmp_n

_strncmp_loop:
        ; Check if n == 0
        LDD     _strncmp_n
        TSTB
        BNE     _strncmp_cont
        TSTA
        BEQ     _strncmp_equal  ; n == 0, strings are equal so far

_strncmp_cont:
        ; Decrement n
        SUBD    #1
        STD     _strncmp_n

        ; Get characters from both strings
        LDX     _strncmp_s1
        LDAA    0,X             ; A = *s1
        INX
        STX     _strncmp_s1

        LDX     _strncmp_s2
        LDAB    0,X             ; B = *s2
        INX
        STX     _strncmp_s2

        ; Compare characters
        SBA                     ; A = A - B (*s1 - *s2)
        BNE     _strncmp_diff   ; If different, return the difference

        ; Characters are equal - check if we reached null terminator
        TSTB                    ; Test *s2 (which equals *s1)
        BEQ     _strncmp_equal  ; Both strings ended

        BRA     _strncmp_loop   ; Continue comparing

_strncmp_equal:
        LDD     #0
        PULX                    ; Restore caller's frame pointer
        RTS

_strncmp_diff:
        ; A contains the difference (s1[i] - s2[i])
        ; Sign-extend A to D
        TAB                     ; B = A
        BPL     _strncmp_pos
        LDAA    #$FF            ; Sign-extend negative
        BRA     _strncmp_return
_strncmp_pos:
        CLRA                    ; Sign-extend positive
_strncmp_return:
        ; D = sign-extended difference
        PULX                    ; Restore caller's frame pointer
        RTS

; --- Local storage for _strncmp ---
_strncmp_s1:    RMB     2       ; Working s1 pointer
_strncmp_s2:    RMB     2       ; Working s2 pointer
_strncmp_n:     RMB     2       ; Remaining count

; =============================================================================
; End of Standard Library Expansion - Phase 2
; =============================================================================

; =============================================================================
; ASSEMBLY CONVENIENCE MACROS
; =============================================================================
; These macros simplify calling runtime functions from assembly code.
; They handle the stack setup and cleanup automatically.
;
; IMPORTANT: All macros leave the result in D register.
;            Macros may clobber A, B, X, and flags.
;
; MACRO CATEGORIES:
;   Display:    CLS, CURSOR, AT, PRINT, PRINT_INT, PRINT_UINT, PRINT_HEX, PUTCHAR
;   Input:      GETKEY, TESTKEY, KBHIT, FLUSHKB
;   Sound:      BEEP, ALARM, TONE
;   Timing:     DELAY, GETTICKS
;   Math:       ABS, MIN, MAX
;   String:     STRLEN, STRCPY, STRCMP, STRCAT, STRCHR, STRNCPY, STRNCMP
;   Memory:     MEMCPY, MEMSET, MEMCMP
;   Conversion: ATOI, ITOA
;   Graphics:   UDG_DEFINE
;   System:     GETTIME
;   LZ-only:    SETMODE, GETMODE, PUSHMODE, POPMODE
; =============================================================================

; =============================================================================
; DISPLAY MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; CLS - Clear screen
; -----------------------------------------------------------------------------
; Usage: CLS
; Output: None
; -----------------------------------------------------------------------------
MACRO CLS
    JSR     _cls
ENDM

; -----------------------------------------------------------------------------
; CURSOR - Position cursor
; -----------------------------------------------------------------------------
; Usage: CURSOR position
; Input: position - 0-31 for 2-line, 0-79 for 4-line
; Output: None
; -----------------------------------------------------------------------------
MACRO CURSOR, position
    LDD     #\position
    PSHB
    PSHA
    JSR     _cursor
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; AT - Position cursor by row and column
; -----------------------------------------------------------------------------
; Usage: AT row, col
; Input: row (0-1 or 0-3), col (0-15 or 0-19)
; Output: None
; Note: Uses DISP_COLS (set by assembler based on target model)
;       Position formula: row * DISP_COLS + col
; -----------------------------------------------------------------------------
MACRO AT, row, col
    LDD     #(\row * DISP_COLS + \col)
    PSHB
    PSHA
    JSR     _cursor
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; PRINT - Print null-terminated string
; -----------------------------------------------------------------------------
; Usage: PRINT string_addr
; Input: string_addr - Address of null-terminated string
; Output: None
; -----------------------------------------------------------------------------
MACRO PRINT, string_addr
    LDD     #\string_addr
    PSHB
    PSHA
    JSR     _print
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; PRINT_INT - Print signed integer
; -----------------------------------------------------------------------------
; Usage: PRINT_INT value
; Input: value - 16-bit signed integer (label or immediate)
; Output: None
; -----------------------------------------------------------------------------
MACRO PRINT_INT, value
    LDD     \value
    PSHB
    PSHA
    JSR     _print_int
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; PRINT_UINT - Print unsigned integer
; -----------------------------------------------------------------------------
; Usage: PRINT_UINT value
; Input: value - 16-bit unsigned integer (label or immediate)
; Output: None
; -----------------------------------------------------------------------------
MACRO PRINT_UINT, value
    LDD     \value
    PSHB
    PSHA
    JSR     _print_uint
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; PRINT_HEX - Print integer as 4 hex digits
; -----------------------------------------------------------------------------
; Usage: PRINT_HEX value
; Input: value - 16-bit value (label or immediate)
; Output: None
; -----------------------------------------------------------------------------
MACRO PRINT_HEX, value
    LDD     \value
    PSHB
    PSHA
    JSR     _print_hex
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; PUTCHAR - Output single character
; -----------------------------------------------------------------------------
; Usage: PUTCHAR char_value
; Input: char_value - ASCII character value
; Output: None
; -----------------------------------------------------------------------------
MACRO PUTCHAR, char_value
    LDD     #\char_value
    PSHB
    PSHA
    JSR     _putchar
    INS
    INS
ENDM

; =============================================================================
; INPUT MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; GETKEY - Wait for and get keypress
; -----------------------------------------------------------------------------
; Usage: GETKEY
; Output: D = key code (low byte)
; -----------------------------------------------------------------------------
MACRO GETKEY
    JSR     _getkey
ENDM

; -----------------------------------------------------------------------------
; TESTKEY - Test if key available (non-blocking with 50ms poll)
; -----------------------------------------------------------------------------
; Usage: TESTKEY
; Output: D = key code if available, 0 if not
; -----------------------------------------------------------------------------
MACRO TESTKEY
    JSR     _testkey
ENDM

; -----------------------------------------------------------------------------
; KBHIT - Check if key is in buffer (non-blocking)
; -----------------------------------------------------------------------------
; Usage: KBHIT
; Output: D = 1 if key available, 0 if not
; -----------------------------------------------------------------------------
MACRO KBHIT
    JSR     _kbhit
ENDM

; -----------------------------------------------------------------------------
; FLUSHKB - Flush keyboard buffer
; -----------------------------------------------------------------------------
; Usage: FLUSHKB
; Output: None
; -----------------------------------------------------------------------------
MACRO FLUSHKB
    JSR     _flushkb
ENDM

; =============================================================================
; SOUND MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; BEEP - Sound a beep
; -----------------------------------------------------------------------------
; Usage: BEEP
; Output: None
; -----------------------------------------------------------------------------
MACRO BEEP
    JSR     _beep
ENDM

; -----------------------------------------------------------------------------
; ALARM - Sound alarm pattern
; -----------------------------------------------------------------------------
; Usage: ALARM
; Output: None
; -----------------------------------------------------------------------------
MACRO ALARM
    JSR     _alarm
ENDM

; -----------------------------------------------------------------------------
; TONE - Generate custom tone
; -----------------------------------------------------------------------------
; Usage: TONE pitch, duration
; Input: pitch (higher = lower pitch), duration (1/32 sec units)
; Output: None
; -----------------------------------------------------------------------------
MACRO TONE, pitch, duration
    LDD     #\duration
    PSHB
    PSHA
    LDD     #\pitch
    PSHB
    PSHA
    JSR     _tone
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; TIMING MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; DELAY - Wait for specified ticks (1 tick ≈ 1/32 second)
; -----------------------------------------------------------------------------
; Usage: DELAY ticks
; Input: ticks - Number of 1/32 second ticks to wait
; Output: None
; -----------------------------------------------------------------------------
MACRO DELAY, ticks
    LDD     #\ticks
    PSHB
    PSHA
    JSR     _delay
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; GETTICKS - Get system tick counter
; -----------------------------------------------------------------------------
; Usage: GETTICKS
; Output: D = current tick count
; -----------------------------------------------------------------------------
MACRO GETTICKS
    JSR     _getticks
ENDM

; =============================================================================
; MATH MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; ABS - Absolute value
; -----------------------------------------------------------------------------
; Usage: ABS value
; Input: value - 16-bit signed integer (label or immediate)
; Output: D = |value|
; -----------------------------------------------------------------------------
MACRO ABS, value
    LDD     \value
    PSHB
    PSHA
    JSR     _abs
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; MIN - Minimum of two values
; -----------------------------------------------------------------------------
; Usage: MIN a, b
; Input: a, b - 16-bit signed integers (labels or immediates)
; Output: D = minimum of a and b
; -----------------------------------------------------------------------------
MACRO MIN, a, b
    LDD     \b
    PSHB
    PSHA
    LDD     \a
    PSHB
    PSHA
    JSR     _min
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; MAX - Maximum of two values
; -----------------------------------------------------------------------------
; Usage: MAX a, b
; Input: a, b - 16-bit signed integers (labels or immediates)
; Output: D = maximum of a and b
; -----------------------------------------------------------------------------
MACRO MAX, a, b
    LDD     \b
    PSHB
    PSHA
    LDD     \a
    PSHB
    PSHA
    JSR     _max
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; STRING MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; STRLEN - Get string length
; -----------------------------------------------------------------------------
; Usage: STRLEN string_addr
; Input: string_addr - Address of null-terminated string
; Output: D = length (not including null)
; -----------------------------------------------------------------------------
MACRO STRLEN, string_addr
    LDD     #\string_addr
    PSHB
    PSHA
    JSR     _strlen
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRCPY - Copy string
; -----------------------------------------------------------------------------
; Usage: STRCPY dest_addr, src_addr
; Input: dest_addr, src_addr - String addresses
; Output: D = dest_addr
; -----------------------------------------------------------------------------
MACRO STRCPY, dest_addr, src_addr
    LDD     #\src_addr
    PSHB
    PSHA
    LDD     #\dest_addr
    PSHB
    PSHA
    JSR     _strcpy
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRCMP - Compare strings
; -----------------------------------------------------------------------------
; Usage: STRCMP s1_addr, s2_addr
; Input: s1_addr, s2_addr - String addresses
; Output: D = 0 if equal, <0 if s1<s2, >0 if s1>s2
; -----------------------------------------------------------------------------
MACRO STRCMP, s1_addr, s2_addr
    LDD     #\s2_addr
    PSHB
    PSHA
    LDD     #\s1_addr
    PSHB
    PSHA
    JSR     _strcmp
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRCAT - Concatenate strings
; -----------------------------------------------------------------------------
; Usage: STRCAT dest_addr, src_addr
; Input: dest_addr - Destination (must have room), src_addr - String to append
; Output: D = dest_addr
; -----------------------------------------------------------------------------
MACRO STRCAT, dest_addr, src_addr
    LDD     #\src_addr
    PSHB
    PSHA
    LDD     #\dest_addr
    PSHB
    PSHA
    JSR     _strcat
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRCHR - Find first occurrence of character in string
; -----------------------------------------------------------------------------
; Usage: STRCHR string_addr, char_value
; Input: string_addr - String to search, char_value - Character to find
; Output: D = Pointer to found character, or 0 if not found
; -----------------------------------------------------------------------------
MACRO STRCHR, string_addr, char_value
    LDD     #\char_value
    PSHB
    PSHA
    LDD     #\string_addr
    PSHB
    PSHA
    JSR     _strchr
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRNCPY - Bounded string copy
; -----------------------------------------------------------------------------
; Usage: STRNCPY dest_addr, src_addr, max_chars
; Input: dest_addr, src_addr, max_chars
; Output: D = dest_addr
; WARNING: If src >= max_chars, dest will NOT be null-terminated!
; -----------------------------------------------------------------------------
MACRO STRNCPY, dest_addr, src_addr, max_chars
    LDD     #\max_chars
    PSHB
    PSHA
    LDD     #\src_addr
    PSHB
    PSHA
    LDD     #\dest_addr
    PSHB
    PSHA
    JSR     _strncpy
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRNCMP - Bounded string comparison
; -----------------------------------------------------------------------------
; Usage: STRNCMP s1_addr, s2_addr, max_chars
; Input: s1_addr, s2_addr, max_chars
; Output: D = 0 if equal, <0 if s1<s2, >0 if s1>s2
; -----------------------------------------------------------------------------
MACRO STRNCMP, s1_addr, s2_addr, max_chars
    LDD     #\max_chars
    PSHB
    PSHA
    LDD     #\s2_addr
    PSHB
    PSHA
    LDD     #\s1_addr
    PSHB
    PSHA
    JSR     _strncmp
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; MEMORY MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; MEMCPY - Copy memory block
; -----------------------------------------------------------------------------
; Usage: MEMCPY dest_addr, src_addr, count
; Input: dest_addr, src_addr, count (bytes)
; Output: D = dest_addr
; -----------------------------------------------------------------------------
MACRO MEMCPY, dest_addr, src_addr, count
    LDD     #\count
    PSHB
    PSHA
    LDD     #\src_addr
    PSHB
    PSHA
    LDD     #\dest_addr
    PSHB
    PSHA
    JSR     _memcpy
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; MEMSET - Fill memory block
; -----------------------------------------------------------------------------
; Usage: MEMSET dest_addr, byte_value, count
; Input: dest_addr, byte_value (0-255), count (bytes)
; Output: D = dest_addr
; -----------------------------------------------------------------------------
MACRO MEMSET, dest_addr, byte_value, count
    LDD     #\count
    PSHB
    PSHA
    LDD     #\byte_value
    PSHB
    PSHA
    LDD     #\dest_addr
    PSHB
    PSHA
    JSR     _memset
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; MEMCMP - Compare memory blocks
; -----------------------------------------------------------------------------
; Usage: MEMCMP a_addr, b_addr, count
; Input: a_addr, b_addr, count (bytes)
; Output: D = 0 if equal, <0 if a<b, >0 if a>b
; -----------------------------------------------------------------------------
MACRO MEMCMP, a_addr, b_addr, count
    LDD     #\count
    PSHB
    PSHA
    LDD     #\b_addr
    PSHB
    PSHA
    LDD     #\a_addr
    PSHB
    PSHA
    JSR     _memcmp
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; CONVERSION MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; ATOI - Convert string to integer
; -----------------------------------------------------------------------------
; Usage: ATOI string_addr
; Input: string_addr - Address of null-terminated string
; Output: D = Parsed integer value (0 if no valid digits)
; -----------------------------------------------------------------------------
MACRO ATOI, string_addr
    LDD     #\string_addr
    PSHB
    PSHA
    JSR     _atoi
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; ITOA - Convert integer to string
; -----------------------------------------------------------------------------
; Usage: ITOA value, buffer_addr
; Input: value (label), buffer_addr (min 7 bytes)
; Output: D = Pointer to buffer
; -----------------------------------------------------------------------------
MACRO ITOA, value, buffer_addr
    LDD     #\buffer_addr
    PSHB
    PSHA
    LDD     \value
    PSHB
    PSHA
    JSR     _itoa
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; GRAPHICS MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; UDG_DEFINE - Define User Defined Graphic character
; -----------------------------------------------------------------------------
; Usage: UDG_DEFINE char_num, data_addr
; Input: char_num (0-7), data_addr (pointer to 8 bytes of bitmap data)
; Output: None
; -----------------------------------------------------------------------------
MACRO UDG_DEFINE, char_num, data_addr
    LDD     #\data_addr
    PSHB
    PSHA
    LDD     #\char_num
    PSHB
    PSHA
    JSR     _udg_define
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; SYSTEM MACROS
; =============================================================================

; -----------------------------------------------------------------------------
; GETTIME - Get current time from RTC
; -----------------------------------------------------------------------------
; Usage: GETTIME buffer_addr
; Input: buffer_addr - Pointer to 6-byte buffer for YY MM DD HH MM SS (BCD)
; Output: Time data written to buffer
; -----------------------------------------------------------------------------
MACRO GETTIME, buffer_addr
    LDD     #\buffer_addr
    PSHB
    PSHA
    JSR     _gettime
    INS
    INS
ENDM

; =============================================================================
; LZ-ONLY DISPLAY MODE MACROS
; =============================================================================
; These macros are for LZ/LZ64 4-line display machines only.
; On CM/XP (2-line), these may cause undefined behavior.

; -----------------------------------------------------------------------------
; SETMODE - Set display mode (LZ only)
; -----------------------------------------------------------------------------
; Usage: SETMODE mode
; Input: mode - 0=2-line, 1=4-line
; Output: None
; -----------------------------------------------------------------------------
MACRO SETMODE, mode
    LDD     #\mode
    PSHB
    PSHA
    JSR     _setmode
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; GETMODE - Get current display mode (LZ only)
; -----------------------------------------------------------------------------
; Usage: GETMODE
; Output: D = mode (0=2-line, 1=4-line)
; -----------------------------------------------------------------------------
MACRO GETMODE
    JSR     _getmode
ENDM

; -----------------------------------------------------------------------------
; PUSHMODE - Save current display mode (LZ only)
; -----------------------------------------------------------------------------
; Usage: PUSHMODE
; Output: None
; -----------------------------------------------------------------------------
MACRO PUSHMODE
    JSR     _pushmode
ENDM

; -----------------------------------------------------------------------------
; POPMODE - Restore saved display mode (LZ only)
; -----------------------------------------------------------------------------
; Usage: POPMODE
; Output: None
; -----------------------------------------------------------------------------
MACRO POPMODE
    JSR     _popmode
ENDM

; =============================================================================
; End of Assembly Convenience Macros
; =============================================================================

; -----------------------------------------------------------------------------
; _print_uint - Print unsigned integer
; Input:  Stack: n (16-bit unsigned)
; Output: None
; Uses UT_UTOB to convert to string, then DP_PRNT to display
; (Same as _print_int but without sign handling)
; -----------------------------------------------------------------------------
_print_uint:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     4,X         ; Get integer value
        ; Use UT_UTOB to convert to decimal string
        LDX     #_print_uint_buf
        SWI
        FCB     $7A         ; UT_UTOB: D=value, X=buffer, returns B=length
        ; B = length, print the string
        LDX     #_print_uint_buf
        SWI
        FCB     $11         ; DP_PRNT: X=buffer, B=length
        PULX
        RTS

; Buffer for print_uint (max 5 digits + null for 65535)
_print_uint_buf:
        RMB     8

; -----------------------------------------------------------------------------
; _print_hex - Print integer as 4 hex digits
; Input:  Stack: n (16-bit)
; Output: None
; Converts each nibble to hex ASCII and prints
; -----------------------------------------------------------------------------
_print_hex:
        PSHX                ; Save caller's frame pointer
        TSX
        LDD     4,X         ; Get value
        ; Store value temporarily
        PSHB
        PSHA                ; Value at SP+0,SP+1
        ; Process high byte, high nibble first
        TSX
        LDAA    0,X         ; High byte
        LSRA                ; Shift right 4 times to get high nibble
        LSRA
        LSRA
        LSRA
        BSR     _print_hex_digit
        ; High byte, low nibble
        TSX
        LDAA    0,X
        ANDA    #$0F        ; Mask low nibble
        BSR     _print_hex_digit
        ; Low byte, high nibble
        TSX
        LDAA    1,X
        LSRA
        LSRA
        LSRA
        LSRA
        BSR     _print_hex_digit
        ; Low byte, low nibble
        TSX
        LDAA    1,X
        ANDA    #$0F
        BSR     _print_hex_digit
        ; Clean up
        INS
        INS                 ; Pop saved value
        PULX
        RTS

; Helper: Print single hex digit (value 0-15 in A)
_print_hex_digit:
        CMPA    #10
        BLO     _print_hex_numeric
        ; A >= 10: convert to 'A'-'F'
        ADDA    #('A'-10)   ; A + 55 = 'A' for 10, 'B' for 11, etc.
        BRA     _print_hex_emit
_print_hex_numeric:
        ; A < 10: convert to '0'-'9'
        ADDA    #'0'        ; A + 48
_print_hex_emit:
        SWI
        FCB     $10         ; DP_EMIT: character in A
        RTS

; -----------------------------------------------------------------------------
; _at - Print string at specified position
; Input:  Stack: pos (16-bit), s (pointer)
;         First arg (pos) at 4,X, second arg (s) at 6,X (after PSHX+TSX)
; Output: None
; Equivalent to: cursor(pos); print(s);
; -----------------------------------------------------------------------------
_at:
        PSHX                ; Save caller's frame pointer
        TSX
        ; First, call cursor(pos)
        LDD     4,X         ; pos (first arg)
        PSHB
        PSHA
        JSR     _cursor
        INS
        INS                 ; Clean up cursor arg
        ; Now, call print(s)
        TSX
        LDD     6,X         ; string pointer (second arg)
        PSHB
        PSHA
        JSR     _print
        INS
        INS                 ; Clean up print arg
        PULX
        RTS

; -----------------------------------------------------------------------------
; _kbhit - Check if key is available in buffer (non-blocking)
; Input:  None
; Output: D = 1 if key available, 0 if not
; Uses KB_TEST which returns carry set if key available
; -----------------------------------------------------------------------------
_kbhit:
        SWI
        FCB     $4B         ; KB_TEST: returns C=1 if key in buffer
        BCC     _kbhit_none
        ; Key available
        LDD     #1
        RTS
_kbhit_none:
        LDD     #0
        RTS

; -----------------------------------------------------------------------------
; _flushkb - Flush keyboard buffer
; Input:  None
; Output: None
; Uses KB_FLSH to clear all pending keypresses
; -----------------------------------------------------------------------------
_flushkb:
        SWI
        FCB     $47         ; KB_FLSH
        RTS

; -----------------------------------------------------------------------------
; _alarm - Generate alarm sound
; Input:  None
; Output: None
; Uses BZ_ALRM for alarm sound pattern
; -----------------------------------------------------------------------------
_alarm:
        SWI
        FCB     $0D         ; BZ_ALRM
        RTS

; -----------------------------------------------------------------------------
; _tone - Generate custom tone
; Input:  Stack: pitch (16-bit), duration (16-bit)
;         First arg (pitch) at 4,X, second arg (duration) at 6,X (after PSHX+TSX)
; Output: None
; Uses BZ_TONE: B=pitch (frequency divisor), A=duration (1/32 sec units)
; Note: Psion BZ_TONE uses 8-bit values, we truncate 16-bit args
; -----------------------------------------------------------------------------
_tone:
        PSHX                ; Save caller's frame pointer
        TSX
        LDAB    5,X         ; pitch low byte (first arg, frequency divisor: higher = lower pitch)
        LDAA    7,X         ; duration low byte (second arg, units of 1/32 second)
        SWI
        FCB     $0F         ; BZ_TONE: B=pitch, A=duration
        PULX
        RTS

; -----------------------------------------------------------------------------
; _gettime - Get current time from RTC
; Input:  Stack: buf (pointer to 6-byte buffer for YY MM DD HH MM SS)
; Output: Time data written to buffer
; Uses TM_TGET to read system time
; Note: The format returned is 6 BCD bytes: year, month, day, hour, min, sec
; -----------------------------------------------------------------------------
_gettime:
        PSHX                ; Save caller's frame pointer
        TSX
        LDX     4,X         ; Get buffer pointer
        SWI
        FCB     $6A         ; TM_TGET: X=buffer, writes 6 bytes
        PULX
        RTS

; -----------------------------------------------------------------------------
; _settime - Set current time in RTC
; Input:  Stack: buf (pointer to 6-byte buffer with YY MM DD HH MM SS)
; Output: None
; Note: This requires write access to system time which may be restricted
; The OS doesn't have a direct TM_TSET; this is a placeholder for completeness
; On most Psion models, time is set through the WORLD menu, not programmatically
; -----------------------------------------------------------------------------
_settime:
        ; Time setting is typically done through the WORLD menu
        ; This function is provided for API completeness but may not
        ; have a direct OS equivalent on all models
        ; For now, this is a no-op to avoid system instability
        RTS

; -----------------------------------------------------------------------------
; _gcursor - Get current cursor position
; Input:  None
; Output: D = current cursor position
; Note: The Psion doesn't have a direct "get cursor position" call
; We track position internally or return 0 as placeholder
; This is a limitation of the Psion display system
; -----------------------------------------------------------------------------
_gcursor:
        ; The Psion OS doesn't provide a direct cursor query
        ; Return 0 as a placeholder
        LDD     #0
        RTS

; -----------------------------------------------------------------------------
; _getticks - Get system tick counter
; Input:  None
; Output: D = current tick count
; Reads the system tick counter from known memory location
; Note: This varies by ROM version; using common location
; -----------------------------------------------------------------------------
_getticks:
        ; System tick counter is typically at a fixed location in system RAM
        ; For CM/XP ROM 3.x, the timer tick count is at $2077-$2078
        ; This may vary by model/ROM version
        LDX     #$2077      ; System tick counter address (model dependent)
        LDD     0,X         ; Read tick counter
        RTS

; =============================================================================
; LZ-Specific Display Mode Functions
; =============================================================================
; These functions control display mode on LZ/LZ64 machines.
; On CM/XP, these are no-ops or return default values.
;
; IMPORTANT: These should only be called on 4-line machines (LA/LZ/LZ64).
; Calling on CM/XP will cause undefined behavior in the OS.
; Use #ifdef __PSION_4LINE__ in C code to conditionally compile.
; =============================================================================

; -----------------------------------------------------------------------------
; _setmode - Set display mode (LZ only)
; Input:  Stack: mode (0=2-line, 1=4-line)
; Output: None
; Uses DP_MSET ($82): A = mode
; -----------------------------------------------------------------------------
_setmode:
        PSHX                ; Save caller's frame pointer
        TSX
        LDAA    5,X         ; Get mode (low byte of arg)
        SWI
        FCB     $82         ; DP_MSET
        PULX
        RTS

; -----------------------------------------------------------------------------
; _getmode - Get current display mode (LZ only)
; Input:  None
; Output: D = mode (0=2-line, 1=4-line)
; Reads directly from DPB_MODE system variable ($2184) for reliability.
; Note: DP_GMOD ($84) syscall exists but its register usage is undocumented.
;       Reading the system variable is more reliable across ROM versions.
; -----------------------------------------------------------------------------
_getmode:
        LDX     #$2184      ; DPB_MODE system variable address
        LDAB    0,X         ; Read mode byte (0=2-line, 1=4-line)
        CLRA                ; Clear high byte for 16-bit return
        RTS

; -----------------------------------------------------------------------------
; _pushmode - Save current display mode (LZ only)
; Input:  None
; Output: None
; Uses DP_MPSH ($81)
; -----------------------------------------------------------------------------
_pushmode:
        SWI
        FCB     $81         ; DP_MPSH
        RTS

; -----------------------------------------------------------------------------
; _popmode - Restore saved display mode (LZ only)
; Input:  None
; Output: None
; Uses DP_MPOP ($83)
; -----------------------------------------------------------------------------
_popmode:
        SWI
        FCB     $83         ; DP_MPOP
        RTS

; =============================================================================
; OPL Procedure Call Support (QCode Injection)
; =============================================================================
;
; OVERVIEW
; --------
; This module enables Small-C compiled code to call external OPL procedures.
; It uses "QCode Injection" - a technique discovered through reverse engineering
; the Psion II OPL interpreter in January 2026.
;
; The technique works by:
;   1. Saving the current stack pointer (for later restoration)
;   2. Building a synthetic QCode buffer in RAM
;   3. Pointing the interpreter's program counter (RTA_PC) to our buffer
;   4. Unwinding to USR() entry and returning (interpreter takes over)
;   5. The interpreter executes our buffer, calling the OPL procedure
;   6. After the procedure returns, our buffer triggers USR(restore, saved_SP)
;   7. The restore routine restores SP and jumps to resume point
;   8. C code continues with stack (and locals) intact!
;
; KEY INSIGHT: STACK PRESERVATION VIA QCODE BUFFER
; -------------------------------------------------
; The saved stack pointer is passed as the USR() argument in the QCode buffer.
; When USR(_call_opl_restore, saved_SP) is called:
;   - D register = saved_SP (passed as USR argument!)
;   - _call_opl_restore does XGDX; TXS to restore SP
;   - Then jumps to the resume address (stored in static variable)
;   - Locals are preserved because the original stack is restored!
;
; This elegant solution was suggested by the user: "Could we not use our made
; from scratch 7D buffer to do the pushing and popping of the stack?"
;
; PORTABILITY
; -----------
; The key insight is that RTA_PC ($A9/$AA) is at a STABLE address across ALL
; Psion Organiser II models: CM, XP, LA, LZ, LZ64, and P350.
; Source: https://www.jaapsch.net/psion/sysvars.htm
;
; This makes the technique fully portable across the Psion II family.
;
; SETUP REQUIREMENT
; -----------------
; When using the 'external' keyword in C code, the compiler AUTOMATICALLY
; injects _call_opl_setup() at the start of main(). No manual setup needed!
;
; Example using the external keyword (RECOMMENDED):
;   external void azMENU();  // Declare external OPL procedure
;
;   void main() {
;       // Compiler auto-injects: JSR _call_opl_setup (invisible to user)
;       int score = 0;
;       azMENU();  // Looks like a normal function call!
;       print_int(score);  // score is preserved across the call
;   }
;
; For advanced users calling _call_opl directly (NOT recommended):
;   _call_opl_setup();  // Must be first statement in main()
;   _call_opl("azMENU");  // Manual invocation
;
; This is required because call_opl() needs to unwind the entire C call
; stack to return control to the OPL interpreter.
;
; USE CASES
; ---------
; - Call OPL utility procedures (file I/O, comms, database)
; - Integrate with existing OPL code libraries
; - Build hybrid OPL/C applications (like Martin Reid's adventure framework)
; - Access OPL-only features not available via system calls
;
; REFERENCES
; ----------
; - dev_docs/PROCEDURE_CALL_RESEARCH.md - Full research documentation
; - https://www.jaapsch.net/psion/sysvars.htm - System variables
; - https://www.jaapsch.net/psion/qcodes.htm - QCode reference
;
; =============================================================================

; =============================================================================
; OPL Runtime System Variables (STABLE across all Psion II models)
; =============================================================================
; These addresses are confirmed stable on CM, XP, LA, LZ, LZ64, P350.
; They point to the OPL interpreter's internal state.

RTA_SP          EQU     $A5     ; Language stack pointer (16-bit at $A5/$A6)
                                ; Points to lowest byte of OPL expression stack
                                ; Used for parameter passing and temporaries

RTA_FP          EQU     $A7     ; Frame pointer (16-bit at $A7/$A8)
                                ; Points into header of current procedure frame
                                ; Used for local variable access

RTA_PC          EQU     $A9     ; Program counter (16-bit at $A9/$AA)
                                ; Points to current QCode opcode being executed
                                ; THIS IS THE KEY VARIABLE for QCode injection!

; =============================================================================
; QCode Opcodes Used for Injection
; =============================================================================
; These are the QCode bytes we synthesize in our buffer.

QCO_PROC        EQU     $7D     ; Procedure call opcode
                                ; Format: $7D len name...
                                ; Triggers the full 14-step procedure call sequence
                                ; including FL$BOPN lookup, frame setup, etc.

QCO_PUSHWORD    EQU     $22     ; Push 16-bit integer onto expression stack
                                ; Format: $22 HH LL (BIG-ENDIAN!)
                                ; Note: OPL uses big-endian for QCode integers

QCO_USR         EQU     $9F     ; USR() function opcode
                                ; Pops address and argument from stack
                                ; Calls machine code at address with arg in D

QCO_PUSHBYTE    EQU     $20     ; Push 8-bit integer onto expression stack
                                ; Format: $20 BB (single byte value)
                                ; Used for parameter count in procedure calls

; =============================================================================
; QCODE BUFFER LAYOUT (Stack-Preserving Version)
; =============================================================================
;
; The _call_opl function builds this structure in _call_opl_buf:
;
;   ┌────────────────────────────────────────────────────────────────────┐
;   │ Byte 0:        $20                QCO_PUSHBYTE opcode              │
;   │ Byte 1:        $00                Parameter count (0 for no args)  │
;   │ Byte 2:        $7D                QCO_PROC opcode                  │
;   │ Byte 3:        len                Procedure name length (1-8)      │
;   │ Bytes 4..N+2:  name               Procedure name bytes (no null)   │
;   │ Byte N+3:      $22                QCO_PUSHWORD opcode              │
;   │ Bytes N+4,N+5: HH LL              _call_opl_restore addr (BIG-END) │
;   │ Byte N+6:      $22                QCO_PUSHWORD opcode              │
;   │ Bytes N+7,N+8: SP_H SP_L          Saved SP value (BIG-ENDIAN!)     │
;   │ Byte N+9:      $9F                QCO_USR opcode                   │
;   └────────────────────────────────────────────────────────────────────┘
;
; The key insight: saved_SP is passed as the USR() argument!
; When USR(_call_opl_restore, saved_SP) executes:
;   - D register = saved_SP
;   - _call_opl_restore restores SP from D and jumps to resume
;   - Local variables are preserved!
;
; Example: call_opl("SUB"); with restore at $0ABC and saved_SP=$1FF0 builds:
;
;   Offset: 0   1   2   3   4   5   6   7   8   9  10  11  12  13
;   Bytes:  20  00  7D  03  53  55  42  22  0A  BC  22  1F  F0  9F
;           |cnt|      |   S   U   B  |   |rest|  |  |saved| USR
;           └─0─┘      └─ length ─────┘   └─────┘  └───────┘
;           param                         restore   SP as
;           count                         address   argument
;                                  addr      argument!
;
; =============================================================================
; EXECUTION FLOW (Stack-Preserving Version)
; =============================================================================
;
;   C Code                    OPL Interpreter                Target OPL Proc
;   ─────────────────────────────────────────────────────────────────────────
;
;   int x = 42;
;   call_opl("SUB"); ────────┐
;   print_int(x);            │ 1. Save current SP (resume_SP) to buffer
;   ↑                        │ 2. Calculate resume_addr, store in static
;   │                        │ 3. Build QCode buffer:
;   │                        │      $7D len name  (proc call)
;   │                        │      $22 restore   (push restore func addr)
;   │                        │      $22 saved_SP  (push SP as USR arg!)
;   │                        │      $9F           (USR opcode)
;   │                        │ 4. Set RTA_PC = &_call_opl_buf
;   │                        │ 5. Unwind to _usr_entry_sp, RTS
;   │                        │    (Exits USR entirely - interpreter takes over)
;   │                        ↓
;   │                        Interpreter resumes ──────────────────────┐
;   │                        Fetches $7D from buffer                   │
;   │                        Parses "SUB" name                         │
;   │                        Calls procedure... ───────────────────────┤
;   │                                                                  ↓
;   │                                                  SUB: executes
;   │                                                  (BEEP, PRINT, etc.)
;   │                                                  Hits $7B (return) ─────┐
;   │                                                                         │
;   │                        Buffer continues: ←──────────────────────────────┘
;   │                        $22 → push _call_opl_restore addr
;   │                        $22 → push saved_SP (our captured SP!)
;   │                        $9F → USR(_call_opl_restore, saved_SP)
;   │                        ↓
;   │                   _call_opl_restore:
;   │                        D = saved_SP (the USR argument!)
;   │                        XGDX         ; X = saved_SP
;   │                        TXS          ; SP = X (stack restored!)
;   │                        LDX resume   ; X = resume_addr
;   │                        JMP 0,X      ; Jump to resume point
;   │                        ↓
;   └────────────────────────┘
;   Execution continues at print_int(x)
;   x is STILL 42! (stack was restored to exact state)
;   D = 0 (standard USR return)
;
; WHY THIS WORKS
; --------------
; 1. We capture SP at call_opl() entry (before any stack changes)
; 2. We calculate resume_SP = entry_SP + 4 (skip ret addr + arg)
; 3. We build a QCode buffer that passes resume_SP as USR argument
; 4. We unwind and exit USR entirely (interpreter continues)
; 5. Interpreter runs our buffer: calls proc, then USR(restore, SP)
; 6. _call_opl_restore receives saved_SP in D, restores it, jumps
; 7. We're back exactly where we were, with locals intact!
;
; =============================================================================
;
; =============================================================================

; -----------------------------------------------------------------------------
; _call_opl - Call an OPL procedure from C code (QCode Injection)
; -----------------------------------------------------------------------------
;
; SYNOPSIS
;   int call_opl(char *name);
;
; DESCRIPTION
;   Calls an external OPL procedure by name. When the procedure completes,
;   execution resumes at the statement following the call_opl() call.
;   LOCAL VARIABLES ARE PRESERVED across the call!
;
;   The OPL procedure's return value is captured and returned in D register.
;   For integer-returning procedures (name ends with %), this is the actual
;   return value. For void/float procedures, this is 0.
;
;   The resume address is automatically derived from the return address
;   on the stack, adjusted to skip the argument cleanup code (INS INS).
;
; SETUP REQUIREMENT
;   Programs using call_opl() MUST call _call_opl_setup() as the very
;   first statement in main():
;
;     void main() {
;         _call_opl_setup();  // REQUIRED - must be first!
;         // ... rest of program ...
;     }
;
;   This saves the USR entry stack pointer needed for stack unwinding.
;
; PARAMETERS
;   name_ptr    - Pointer to null-terminated procedure name (max 8 chars)
;                 Example: "azMENU" or "RAND%" (include % for int-returning)
;                 Do NOT include device prefix; uses default device.
;
; STACK LAYOUT (at entry, before prologue)
;   SP points to: [return addr][name_ptr]
;   resume_SP = SP + 4 (after cleanup of ret addr + arg)
;
; RESUME ADDRESS CALCULATION
;   After JSR _call_opl, the compiler emits cleanup code:
;       JSR _call_opl   ; return addr points here ─┐
;       INS             ; ← return addr            │
;       INS             ; cleanup 2 bytes of arg   │
;       <next stmt>     ; ← resume_addr = ret + 2 ─┘
;
;   We add 2 to the return address to skip the INS INS cleanup.
;
; REGISTER USAGE
;   A, B, D, X - All scratch (clobbered)
;   Uses _call_opl_* static variables for state
;
; RETURNS
;   Execution continues at the next statement after call_opl().
;   D register = OPL procedure's return value:
;     - For integer procedures (name ends with %): actual return value
;     - For void/float procedures: 0 (default OPL return)
;   Stack is restored to exact state at call_opl() entry.
;   LOCAL VARIABLES ARE PRESERVED!
;
; EXAMPLE USAGE
;   void game_loop() {
;       int local_score = 42;   // Local variable
;
;       call_opl("azMENU");     // Call void OPL procedure
;
;       // Execution resumes here
;       // local_score is STILL 42! (stack preserved)
;       print_int(local_score);
;
;       // For integer-returning procedures:
;       int rand_val = call_opl("RAND%");  // Get return value!
;       print_int(rand_val);
;   }
;
; HOW IT WORKS
;   1. Capture entry SP; calculate resume_SP = entry_SP + 4
;   2. Calculate resume_addr = return_addr + 2
;   3. Build QCode buffer:
;      - $20 $00 (push param count = 0)
;      - $7D len name (procedure call)
;      - $22 _call_opl_restore (push restore function address)
;      - $22 resume_SP (push saved SP as USR argument!)
;      - $9F (USR opcode)
;   4. Point RTA_PC to buffer
;   5. Unwind to USR entry (LDX _usr_entry_sp; TXS; RTS)
;   6. Interpreter executes buffer: calls proc, then USR(restore, SP)
;   7. _call_opl_restore:
;      a. Capture OPL return value from RTA_SP (language stack)
;      b. Restore CPU SP from saved_SP
;      c. Load return value into D
;      d. Jump to resume_addr
;   8. We're back with locals intact, D = OPL return value!
;
; NOTES
;   - Maximum name length: 8 characters (Psion identifier limit)
;   - Name is NOT null-terminated in buffer (length-prefixed)
;   - RTA_PC ($A9/$AA) is stable across all Psion II models
;   - The clever trick: saved_SP is passed as USR() argument!
;   - OPL return value captured from language stack before SP restore
;
; -----------------------------------------------------------------------------
_call_opl:
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 0: Save caller's frame pointer and set restore function
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; The C calling convention uses X as the frame pointer. We MUST save it
        ; before TSX clobbers it, and restore it in _call_opl_restore so that
        ; the C code can continue accessing local variables after the OPL call.
        ;
        ; Also set the restore function address for this call type (int return).
        ; _call_opl_str will set a different restore function for char returns.
        ;
        STX     _CALL_OPL_FP    ; Save caller's frame pointer to zero-page
        LDD     #_call_opl_restore
        STD     _CALL_OPL_REST  ; Store restore function for int returns
        BRA     _call_opl_common
        ;
; -----------------------------------------------------------------------------
; _call_opl_str - Call OPL procedure returning string (get first char)
; -----------------------------------------------------------------------------
; Same as _call_opl but uses _call_opl_str_restore which reads the first
; character of an OPL string return value instead of converting a float.
;
; Use this for: external char FUNC();
;
; INPUT
;   Same as _call_opl: procedure name pointer on stack
;
; OUTPUT
;   D = first character of the returned string (low byte in B, A=0)
;   For empty string, D = 0
;
; -----------------------------------------------------------------------------
_call_opl_str:
        STX     _CALL_OPL_FP    ; Save caller's frame pointer to zero-page
        LDD     #_call_opl_str_restore
        STD     _CALL_OPL_REST  ; Store restore function for char returns
        ; Fall through to common code
        ;
        BRA     _call_opl_common
        ;
; -----------------------------------------------------------------------------
; _call_opl_param - Call OPL procedure WITH PARAMETERS (returns int)
; -----------------------------------------------------------------------------
; Extended version of _call_opl that supports passing integer parameters to
; OPL procedures. Parameters are pushed onto the OPL language stack via QCode
; $22 (PUSHWORD) opcodes before the procedure call.
;
; Use this for: external void FUNC(int a, int b);
;               external int FUNC(int x);
;
; INPUT
;   Stack layout at entry (pushed by C codegen right-to-left):
;     SP -> [return_addr 2B]
;           [param_count 2B]     <- pushed last before JSR
;           [name_ptr 2B]        <- procedure name string pointer
;           [param_N 2B]         <- last argument (pushed first by C)
;           [param_N-1 2B]
;           ...
;           [param_1 2B]         <- first argument (pushed last by C)
;
; OUTPUT
;   D = return value from OPL procedure (BCD float converted to int)
;   For void procedures, D is garbage (caller ignores)
;
; NOTES
;   - Maximum 4 parameters supported (parser enforces this)
;   - All parameters are 16-bit integers (char is promoted)
;   - OPL expects parameters in ORDER (first param first on language stack)
;   - C pushes right-to-left, so we read from highest offset first
;
; -----------------------------------------------------------------------------
_call_opl_param:
        STX     _CALL_OPL_FP    ; Save caller's frame pointer to zero-page
        LDD     #_call_opl_restore
        STD     _CALL_OPL_REST  ; Store restore function for int returns
        BRA     _call_opl_param_common
        ;
; -----------------------------------------------------------------------------
; _call_opl_str_param - Call OPL procedure WITH PARAMETERS (returns string)
; -----------------------------------------------------------------------------
; Same as _call_opl_param but returns the first character of a string.
;
; Use this for: external char FUNC(int x);
;
; OUTPUT
;   D = first character of returned string (A=0, B=char)
;
; -----------------------------------------------------------------------------
_call_opl_str_param:
        STX     _CALL_OPL_FP    ; Save caller's frame pointer to zero-page
        LDD     #_call_opl_str_restore
        STD     _CALL_OPL_REST  ; Store restore function for char returns
        ; Fall through to param common code
        ;
_call_opl_param_common:
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 1: Capture stack data and store to cell
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; Stack at entry (pushed by C codegen right-to-left):
        ;   SP+0,1: return_addr    (from JSR)
        ;   SP+2,3: param_count    (pushed last by codegen)
        ;   SP+4,5: name_ptr       (pushed second-to-last)
        ;   SP+6,7: param_1        (first arg, pushed LAST by C - lowest offset)
        ;   SP+8,9: param_2        (second arg, pushed earlier)
        ;   ...
        ;   SP+4+2*N: param_N      (last arg, pushed FIRST by C - highest offset)
        ;
        ; We need to save entry_SP early since we need it for parameter access.
        ; We'll use UTW_W1 ($86-$87) as temporary storage for entry_SP.
        ;
        TSX                     ; X = entry_SP (points to return addr)
        STX     UTW_W1          ; Save entry_SP to zero-page for later use
        ;
        ; 1. Read and store param_count to cell
        ;
        LDAB    3,X             ; B = param_count (low byte, max 4)
        PSHB                    ; Save param_count temporarily
        JSR     _call_opl_get_cell ; X = cell base
        PULB                    ; B = param_count
        STAB    _COL_PARAM_CNT,X ; cell.param_count = B
        ;
        ; 2. Read and store name_ptr to cell
        ;
        LDX     UTW_W1          ; X = entry_SP
        LDD     4,X             ; D = name_ptr
        PSHB
        PSHA                    ; Save name_ptr temporarily
        JSR     _call_opl_get_cell ; X = cell base
        PULA
        PULB                    ; D = name_ptr
        STD     _COL_NAME_PTR,X ; cell.name_ptr = D
        ;
        ; 3. Calculate and store resume_addr = return_addr + 2
        ;    (skips the INS INS cleanup after JSR)
        ;
        LDX     UTW_W1          ; X = entry_SP
        LDD     0,X             ; D = return_addr
        ADDD    #2              ; D = resume_addr
        PSHB
        PSHA                    ; Save resume_addr temporarily
        JSR     _call_opl_get_cell ; X = cell base
        PULA
        PULB                    ; D = resume_addr
        STD     _COL_RESUME,X   ; cell.resume = D
        ;
        ; 4. Calculate and store resume_SP = entry_SP + 6 + 2*param_count
        ;    This is where SP will be after cleaning up all pushed items:
        ;    return_addr(2) + param_count(2) + name_ptr(2) + params(2*N)
        ;
        LDD     UTW_W1          ; D = entry_SP
        ADDD    #6              ; D = entry_SP + 6 (base)
        PSHB
        PSHA                    ; Save intermediate result
        JSR     _call_opl_get_cell ; X = cell base
        LDAB    _COL_PARAM_CNT,X ; B = param_count
        ASLB                    ; B = 2 * param_count (max 8)
        CLRA                    ; A = 0, so D = 2*param_count
        TSX                     ; X = current SP
        ADDD    0,X             ; D = (entry_SP+6) + 2*param_count = resume_SP
        INS
        INS                     ; Pop intermediate
        JSR     _call_opl_get_cell ; X = cell base
        STD     _COL_SAVED_SP,X ; cell.saved_sp = resume_SP
        ;
        ; 5. Store caller's frame pointer (was saved at function entry)
        ;
        LDD     _CALL_OPL_FP    ; D = saved frame pointer (from zero-page)
        STD     _COL_FRAME_PTR,X ; cell.frame_ptr = D
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 2: Count procedure name length
        ; ═══════════════════════════════════════════════════════════════════
        ;
        LDX     _COL_NAME_PTR,X ; X = name string pointer
        CLRB                    ; B = length counter
_cop_count_name:
        TST     0,X             ; Test current byte
        BEQ     _cop_count_done ; If null, done
        INX                     ; Next char
        INCB                    ; Increment counter
        CMPB    #8              ; Max 8 chars
        BNE     _cop_count_name
_cop_count_done:
        ;
        ; B = name length (1-8)
        ; Store in cell
        ;
        PSHB                    ; Save length
        JSR     _call_opl_get_cell ; X = cell base
        PULB                    ; B = length
        STAB    _COL_NAMELEN,X  ; cell.namelen = B
        CLR     _COL_IDX,X      ; Initialize buffer index to 0
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 3: Build QCode buffer with parameters
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; Buffer format:
        ;   [$22 param1_hi param1_lo]  ; First parameter (OPL order)
        ;   [$22 param2_hi param2_lo]  ; Second parameter
        ;   ...
        ;   [$20 param_count]          ; Push parameter count
        ;   [$7D namelen name...]      ; QCO_PROC
        ;   [$22 restore_hi restore_lo] ; Push restore function
        ;   [$22 saved_sp_hi saved_sp_lo] ; Push saved SP
        ;   [$9F]                      ; QCO_USR
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3a. Write parameter pushes (if any)
        ; ─────────────────────────────────────────────────────────────────
        ; OPL emits parameters in DECLARATION ORDER (first to last).
        ; Each parameter is: PUSHWORD value, PUSHBYTE 0 (type marker)
        ;
        ; C pushes arguments right-to-left, so on the C stack:
        ;   entry_SP+6: param_1 (first param, pushed LAST by C - lowest offset)
        ;   entry_SP+8: param_2 (second param, pushed earlier)
        ;   ...
        ;   entry_SP+4+2*N: param_N (last param, pushed FIRST by C - highest offset)
        ;
        ; We emit in OPL order (first to last): param1, param2, ..., paramN
        ; So we read from LOWEST offset (param_1 at 6) to HIGHEST offset.
        ;
        ; entry_SP is saved in UTW_W1 from STEP 1.
        ; We use UTW_W2 ($88) to track current parameter offset.
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAB    _COL_PARAM_CNT,X ; B = param_count
        TSTB
        BEQ     _cop_param_done ; Skip if no params
        ;
        ; B = number of params to emit (loop counter)
        ; Starting offset = 6 (param_1 is always at entry_SP+6)
        ; We INCREMENT the offset each iteration to process params in order.
        ;
        LDAA    #6              ; A = 6 = starting offset (param_1)
        STAA    UTW_W2          ; Save current offset to UTW_W2
        ;
_cop_param_loop:
        ;
        ; Emit one parameter: $22 high low
        ; Parameter is at entry_SP + current_offset
        ;
        PSHB                    ; Save loop counter
        ;
        ; Emit $22 (QCO_PUSHWORD)
        ;
        LDAA    #QCO_PUSHWORD   ; A = $22
        BSR     _call_opl_emit  ; Write $22 to buffer
        ;
        ; Load parameter value from entry_SP + offset
        ;
        LDX     UTW_W1          ; X = entry_SP
        LDAB    UTW_W2          ; B = current offset
        ABX                     ; X = entry_SP + offset = &param
        LDD     0,X             ; D = parameter value (high in A, low in B)
        ;
        ; Emit high byte (A), then low byte (B) - BIG ENDIAN for QCode!
        ;
        PSHB                    ; Save low byte
        BSR     _call_opl_emit  ; Write high byte (A)
        PULA                    ; A = low byte (was B)
        BSR     _call_opl_emit  ; Write low byte
        ;
        ; Emit type marker: $20 $00 (PUSHBYTE 0 = integer type)
        ; OPL requires a type marker after each parameter value!
        ;
        LDAA    #QCO_PUSHBYTE   ; A = $20
        BSR     _call_opl_emit  ; Write $20
        CLRA                    ; A = 0 (integer type marker)
        BSR     _call_opl_emit  ; Write $00
        ;
        ; INCREMENT offset by 2 (move to next param at higher address)
        ;
        LDAA    UTW_W2          ; A = current offset
        ADDA    #2              ; A = offset + 2
        STAA    UTW_W2          ; Update offset
        ;
        PULB                    ; B = loop counter
        DECB                    ; Decrement
        BNE     _cop_param_loop ; Continue if more params
        ;
_cop_param_done:
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3b. Write parameter count: $20 count
        ; ─────────────────────────────────────────────────────────────────
        ; OPL uses PUSHBYTE for the parameter count.
        ;
        LDAA    #QCO_PUSHBYTE   ; A = $20
        BSR     _call_opl_emit  ; Write $20
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAA    _COL_PARAM_CNT,X ; A = param_count
        BSR     _call_opl_emit  ; Write count
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3c. Write procedure call: $7D length name...
        ; ─────────────────────────────────────────────────────────────────
        ;
        LDAA    #QCO_PROC       ; A = $7D
        BSR     _call_opl_emit  ; Write $7D
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAA    _COL_NAMELEN,X  ; A = name length
        BSR     _call_opl_emit  ; Write length
        ;
        ; Copy name bytes
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAB    _COL_NAMELEN,X  ; B = byte counter
        LDX     _COL_NAME_PTR,X ; X = name string pointer
_cop_copyname:
        TSTB
        BEQ     _cop_name_done
        LDAA    0,X             ; A = current byte
        INX                     ; Advance source
        PSHX                    ; Save source pointer
        PSHB                    ; Save counter
        BSR     _call_opl_emit  ; Write byte
        PULB                    ; Restore counter
        PULX                    ; Restore source pointer
        DECB
        BRA     _cop_copyname
_cop_name_done:
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3d. Write restore address: $22 addr_hi addr_lo
        ; ─────────────────────────────────────────────────────────────────
        ;
        LDAA    #QCO_PUSHWORD   ; A = $22
        BSR     _call_opl_emit  ; Write $22
        ;
        LDD     _CALL_OPL_REST  ; D = restore function address
        PSHB                    ; Save low byte
        BSR     _call_opl_emit  ; Write high byte (A)
        PULA                    ; A = low byte
        BSR     _call_opl_emit  ; Write low byte
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3e. Write saved SP: $22 sp_hi sp_lo
        ; ─────────────────────────────────────────────────────────────────
        ;
        LDAA    #QCO_PUSHWORD   ; A = $22
        BSR     _call_opl_emit  ; Write $22
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDD     _COL_SAVED_SP,X ; D = saved SP (resume SP)
        PSHB                    ; Save low byte
        BSR     _call_opl_emit  ; Write high byte (A)
        PULA                    ; A = low byte
        BSR     _call_opl_emit  ; Write low byte
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 3f. Write USR opcode: $9F
        ; ─────────────────────────────────────────────────────────────────
        ;
        LDAA    #QCO_USR        ; A = $9F
        BSR     _call_opl_emit  ; Write $9F
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 4: Set RTA_PC and unwind to OPL interpreter
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; Same as _call_opl_common - point interpreter to our buffer and exit.
        ;
        JSR     _call_opl_get_cell ; X = cell base
        XGDX                    ; D = cell base
        ADDD    #_COL_BUF       ; D = buffer address
        SUBD    #1              ; Pre-compensate (interpreter adds 1)
        XGDX                    ; X = adjusted buffer address
        STX     RTA_PC          ; RTA_PC = &buffer - 1
        ;
        ; Unwind stack to USR entry point
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDX     _COL_USR_SP,X   ; X = USR entry SP
        TXS                     ; SP = X (unwind)
        CLRB                    ; B=0 so interpreter doesn't advance RTA_PC
        RTS                     ; Exit to OPL interpreter!
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; After OPL executes our buffer:
        ; 1. It executes param pushes ($22 value)
        ; 2. It pushes param count ($20 N)
        ; 3. It calls the procedure ($7D len name)
        ; 4. It pushes restore addr and saved_SP ($22 values)
        ; 5. It executes USR($9F) which calls _call_opl_restore/str_restore
        ; 6. _call_opl_restore restores SP and jumps to resume_addr
        ; 7. C code continues!
        ; ═══════════════════════════════════════════════════════════════════
        ;
; END of _call_opl_param / _call_opl_str_param
; -----------------------------------------------------------------------------

_call_opl_common:
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 1: Capture SP and arguments from stack
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; At entry, SP points to: [return_addr 2B][name_ptr 2B]
        ; After normal return + cleanup, SP would be at entry_SP + 4.
        ;
        ; Stack state at entry:
        ;   ┌─────────────────────────┐
        ;   │ 0,X - 1,X: return addr  │ ← SP/X points here
        ;   │ 2,X - 3,X: name_ptr     │ (the argument)
        ;   └─────────────────────────┘
        ;
        TSX                     ; X = SP (points to return addr)
        ;
        ; Extract name_ptr first (before we lose X)
        ;
        LDD     2,X             ; D = name_ptr (argument at 2,X)
        PSHB
        PSHA                    ; Save name_ptr on stack
        ;
        ; Calculate resume_addr = return_addr + 2 (skips INS INS cleanup)
        ;
        LDD     0,X             ; D = return address
        ADDD    #2              ; D = return_addr + 2
        PSHB
        PSHA                    ; Save resume_addr on stack
        ;
        ; Calculate resume_SP = entry_SP + 4
        ;
        XGDX                    ; D = entry SP (was in X from TSX)
        ADDD    #4              ; D = resume_SP
        PSHB
        PSHA                    ; Save saved_sp on stack
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 2: Store values to allocated cell
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; Stack now: [saved_sp][resume_addr][name_ptr][ret_addr][orig_name_ptr]
        ;
        JSR     _call_opl_get_cell ; X = cell base
        ;
        PULA
        PULB                    ; D = saved_sp
        STD     _COL_SAVED_SP,X ; Store at offset 2
        ;
        PULA
        PULB                    ; D = resume_addr
        STD     _COL_RESUME,X   ; Store at offset 28
        ;
        PULA
        PULB                    ; D = name_ptr
        STD     _COL_NAME_PTR,X ; Store at offset 0
        ;
        ; Copy frame pointer from zero-page to cell (OPL-safe storage)
        ; We saved it to _CALL_OPL_FP at entry before TSX clobbered it.
        ;
        LDD     _CALL_OPL_FP    ; D = saved frame pointer
        STD     _COL_FRAME_PTR,X ; Store in cell at offset 30
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 3: Count procedure name length
        ; ═══════════════════════════════════════════════════════════════════
        ;
        LDX     _COL_NAME_PTR,X ; X = pointer to name string (from cell)
        CLRB                    ; B = length counter, start at 0
_call_opl_count:
        TST     0,X             ; Test byte at current position
        BEQ     _call_opl_build ; If null terminator, done counting
        INX                     ; Advance to next character
        INCB                    ; Increment length counter
        CMPB    #8              ; Check against Psion's 8-char limit
        BNE     _call_opl_count ; Continue if under limit
        ;
        ; If we reach here, name is exactly 8 chars (or we hit limit)
        ; Fall through to build phase
        ;

_call_opl_build:
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 4: Build QCode buffer
        ; ═══════════════════════════════════════════════════════════════════
        ; We build the buffer byte-by-byte using _call_opl_emit helper.
        ;
        ; At this point: B = name length (1-8)
        ;
        PSHB                    ; Save length on stack
        JSR     _call_opl_get_cell ; X = cell base
        PULB                    ; B = length
        STAB    _COL_NAMELEN,X  ; Save length in cell
        CLR     _COL_IDX,X      ; Initialize buffer write index to 0

        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4a. Write parameter count: $20 $00 (push 0 for no arguments)
        ; ─────────────────────────────────────────────────────────────────
        ; QCO_PROC reads the parameter count from the language stack.
        ; Before calling a procedure with 0 arguments, OPL emits "$20 $00"
        ; to push 0 onto the stack. Without this, QCO_PROC reads garbage
        ; and reports "ARG COUNT ERR".
        ;
        LDAA    #QCO_PUSHBYTE   ; A = $20 (push byte opcode)
        BSR     _call_opl_emit  ; buf[0] = $20
        ;
        CLRA                    ; A = 0 (parameter count for no-arg call)
        BSR     _call_opl_emit  ; buf[1] = $00
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4b. Write procedure call header: $7D + length
        ; ─────────────────────────────────────────────────────────────────
        ;
        LDAA    #QCO_PROC       ; A = $7D (procedure call opcode)
        BSR     _call_opl_emit  ; buf[2] = $7D
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAA    _COL_NAMELEN,X  ; A = name length
        BSR     _call_opl_emit  ; buf[3] = length

        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4c. Write procedure name bytes (without null terminator)
        ; ─────────────────────────────────────────────────────────────────
        ; Loop copies 'namelen' bytes from name string to buffer.
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDAB    _COL_NAMELEN,X  ; B = byte counter
        LDX     _COL_NAME_PTR,X ; X = source pointer (name string)
_call_opl_copyname:
        TSTB                    ; Check if counter is zero
        BEQ     _call_opl_suffix   ; If zero, name copy complete
        LDAA    0,X             ; A = current source byte
        INX                     ; Advance source pointer
        PSHX                    ; Save source pointer (emit clobbers X)
        PSHB                    ; Save counter (emit clobbers B)
        BSR     _call_opl_emit  ; Write byte to buffer
        PULB                    ; Restore counter
        PULX                    ; Restore source pointer
        DECB                    ; Decrement counter
        BRA     _call_opl_copyname ; Continue loop

_call_opl_suffix:
        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4d. Write restore function address: $22 + addr (big-endian)
        ; ─────────────────────────────────────────────────────────────────
        ; This is the function that will receive the saved SP and restore it.
        ; The restore function address was set at entry:
        ;   - _call_opl: uses _call_opl_restore (BCD float to int)
        ;   - _call_opl_str: uses _call_opl_str_restore (string first char)
        ; OPL QCode uses BIG-ENDIAN for 16-bit values!
        ; HD6303 D register: A = high byte, B = low byte
        ;
        LDAA    #QCO_PUSHWORD   ; A = $22 (push word opcode)
        BSR     _call_opl_emit  ; Write $22
        ;
        LDD     _CALL_OPL_REST  ; D = restore function address (from zero-page)
        PSHB                    ; Save low byte (need to write after high)
        BSR     _call_opl_emit  ; Write high byte (A)
        PULA                    ; A = low byte (was B)
        BSR     _call_opl_emit  ; Write low byte

        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4e. Write saved SP as USR argument: $22 + saved_SP (big-endian)
        ; ─────────────────────────────────────────────────────────────────
        ; THIS IS THE KEY TRICK! The saved SP is passed as the USR argument.
        ; When USR(_call_opl_restore, saved_SP) is called:
        ;   - D register = saved_SP
        ;   - _call_opl_restore restores SP from D and jumps to resume
        ;   - Local variables are preserved!
        ;
        LDAA    #QCO_PUSHWORD   ; A = $22 (push word opcode)
        BSR     _call_opl_emit  ; Write $22
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDD     _COL_SAVED_SP,X ; D = saved SP value (resume SP)
        PSHB                    ; Save low byte
        BSR     _call_opl_emit  ; Write high byte (A)
        PULA                    ; A = low byte (was B)
        BSR     _call_opl_emit  ; Write low byte

        ;
        ; ─────────────────────────────────────────────────────────────────
        ; 4f. Write USR opcode: $9F
        ; ─────────────────────────────────────────────────────────────────
        ; This completes the buffer. When the interpreter executes this,
        ; it will call USR(_call_opl_restore, saved_SP)!
        ;
        LDAA    #QCO_USR        ; A = $9F (USR opcode)
        BSR     _call_opl_emit  ; Write $9F

        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 5: Point interpreter to our buffer
        ; ═══════════════════════════════════════════════════════════════════
        ; This is the magic! RTA_PC is the OPL interpreter's program counter.
        ; By setting it to point to our buffer, the interpreter will execute
        ; our synthesized QCode when it resumes.
        ;
        ; RTA_PC is at $A9/$AA - CONFIRMED STABLE across all Psion II models.
        ;
        ; Calculate buffer address: cell_base + _COL_BUF offset
        ;
        JSR     _call_opl_get_cell ; X = cell base
        XGDX                    ; D = cell base
        ADDD    #_COL_BUF       ; D = cell_base + 8 (buffer offset)
        SUBD    #1              ; Pre-compensate: interpreter adds 1 after USR return
        XGDX                    ; X = adjusted buffer address
        STX     RTA_PC          ; RTA_PC = &buffer - 1 (becomes &buffer after +1)

        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 6: Unwind to USR entry and exit
        ; ═══════════════════════════════════════════════════════════════════
        ; We need to exit the current USR() context entirely so the OPL
        ; interpreter takes over. Simply doing RTS would return to our
        ; caller (the C code), which would then continue executing before
        ; the interpreter runs our buffer - causing code to run twice!
        ;
        ; Solution: Restore SP to the saved USR entry point and RTS from
        ; there. This requires _usr_entry_sp to be set at program start.
        ;
        ; The interpreter will then:
        ;   1. Fetch $7D → call the target OPL procedure
        ;   2. Target procedure executes and returns ($7B)
        ;   3. Fetch $22 → push _call_opl_restore address
        ;   4. Fetch $22 → push saved_SP
        ;   5. Fetch $9F → call USR(_call_opl_restore, saved_SP)
        ;   6. _call_opl_restore restores SP and jumps to resume_addr
        ;   7. Back in C code with stack intact!
        ;
        JSR     _call_opl_get_cell ; X = cell base
        LDX     _COL_USR_SP,X   ; X = USR entry stack pointer
        TXS                     ; SP = X (unwind entire C stack)
        CLRB                    ; B=0 so interpreter doesn't advance RTA_PC!
        RTS                     ; Exit USR! Interpreter takes over.

; =============================================================================
; _call_opl_emit - Write byte to buffer at current index
; =============================================================================
;
; Helper subroutine for buffer construction. Writes a single byte to
; the QCode buffer at the current index, then increments the index.
; The buffer is located in the dynamically allocated cell.
;
; INPUT
;   A = byte to write
;
; OUTPUT
;   Byte written to buffer
;   idx incremented in cell
;
; CLOBBERS
;   X (used for address calculation)
;
; PRESERVES
;   A (still contains the byte that was written)
;   B (saved and restored)
;
; NOTES
;   Uses indexed addressing: buf[idx] = A; idx++;
;   Accesses the allocated cell via tag dereference.
;
; -----------------------------------------------------------------------------
_call_opl_emit:
        PSHA                    ; [1] Save A (the byte to write)
        PSHB                    ; [2] Save B (caller's value)
        ;
        ; Stack: [B_saved][A_byte][ret_addr]
        ;
        ; Get cell base
        ;
        JSR     _call_opl_get_cell ; X = cell base
        ;
        ; Load current index and calculate buffer address
        ; Buffer addr = cell_base + _COL_BUF + idx
        ;
        LDAB    _COL_IDX,X      ; B = current index (0-19)
        PSHB                    ; [3] Save index
        ;
        ; Stack: [idx][B_saved][A_byte][ret_addr]
        ;
        ; Increment index in cell now (before we lose X)
        ;
        INC     _COL_IDX,X
        ;
        ; Calculate buffer address
        ;
        XGDX                    ; D = cell base
        ADDD    #_COL_BUF       ; D = buffer start (cell + 8)
        XGDX                    ; X = buffer start
        PULB                    ; B = index
        ABX                     ; X = &buf[idx] (final address)
        ;
        ; Stack: [B_saved][A_byte][ret_addr]
        ;
        ; Retrieve the byte to write from stack and store it
        ; Need to get A from stack position 1 (past B_saved)
        ;
        PSHX                    ; [3] Save buffer address
        TSX                     ; X = SP
        LDAA    3,X             ; A = byte (at offset 3: [bufaddr][B][A])
        PULX                    ; X = buffer address
        STAA    0,X             ; buf[idx] = A
        ;
        ; Restore registers
        ;
        PULB                    ; Restore caller's B
        PULA                    ; Restore A (unchanged, for caller)
        RTS

; =============================================================================
; _call_opl_restore - Restore stack and resume C execution with return value
; =============================================================================
;
; This function is called by the OPL interpreter via USR(_call_opl_restore, SP).
; It receives the saved stack pointer as the USR argument in D register,
; captures the OPL procedure's return value from the language stack,
; restores SP to that value, and jumps to the saved resume address.
;
; INPUT
;   D = saved_SP (the USR argument, passed by our QCode buffer)
;   RTA_SP points to the OPL procedure's return value on language stack
;         (After USR pops its params, the return value is at top of stack)
;
; OUTPUT
;   Does not return normally - jumps to resume address
;   SP is restored to saved value
;   D = OPL procedure's return value (integer, for int-returning functions)
;
; HOW IT WORKS
;   1. D contains the saved SP (passed as USR argument)
;   2. Save saved_SP to temp zero-page (UTW_W1)
;   3. Read OPL return value from RTA_SP (language stack)
;   4. Save OPL return value to temp zero-page (UTW_W2)
;   5. Restore CPU SP from saved_SP
;   6. Load resume address from cell
;   7. Load OPL return value into D
;   8. JMP to resume point
;
; RETURN VALUE MECHANISM
;   When an OPL procedure returns (via QCO_RETURN), its return value is
;   pushed onto the language stack (RTA_SP). Our QCode buffer then executes:
;     $22 restore_addr  → pushes restore function address
;     $22 saved_SP      → pushes saved SP as USR argument
;     $9F               → USR(_call_opl_restore, saved_SP)
;
;   USR pops both values for its call. After that, the OPL return value
;   is sitting right at the top of the language stack!
;
;   Language stack state when we're called:
;     RTA_SP -> [opl_return_value]  (2 bytes, integer)
;
; RESULT
;   Execution resumes at the C statement after call_opl().
;   Local variables are preserved because SP was restored!
;   D contains the OPL procedure's return value for int-returning calls.
;
; NOTES
;   - For integer-returning procedures (name ending with %), D = return value
;   - For void procedures or procedures without explicit RETURN, D = 0
;   - Float and string return values are NOT supported (would need different handling)
;   - Uses UTW_W1 ($86) and UTW_W2 ($88) as scratch during restore
;
; -----------------------------------------------------------------------------
_call_opl_restore:
        ;
        ; D = saved_SP (the USR argument from our QCode buffer!)
        ; RTA_SP points to OPL's return value (after USR popped its params)
        ;
        ; Step 1: Save saved_SP to temp (we need it later after reading RTA_SP)
        ;
        STD     UTW_W1          ; UTW_W1 = saved_SP (temp storage)
        ;
        ; Step 2: Capture OPL return value from language stack BEFORE
        ;         restoring CPU SP. After we restore SP, we lose access to
        ;         OPL's stack context, so we must read it now.
        ;
        ;         For integer-returning procedures (name ending with %),
        ;         OPL pushes a 2-byte integer directly on the language stack.
        ;         We simply read it as a 16-bit value.
        ;
        LDX     RTA_SP          ; X = language stack pointer
        LDD     0,X             ; D = 2-byte integer return value
        STD     UTW_W2          ; Store in temp for later
        ; UTW_W2 now contains the integer return value
        ;
        ; Step 3: Restore CPU stack pointer from saved_SP
        ;
        LDD     UTW_W1          ; D = saved_SP
        XGDX                    ; X = saved_SP
        TXS                     ; SP = X (CPU stack pointer restored!)
        ;
        ; Now SP is exactly where it was after call_opl() cleanup.
        ; Local variables above this point are intact!
        ;
        ; Step 4: Get resume address from cell and push onto stack for RTS
        ;
        ;         We need to restore the frame pointer (X) before jumping, but
        ;         we also need X to read from the cell. Solution: push the resume
        ;         address onto the stack, then restore X, then RTS to jump.
        ;
        LDX     _CALL_OPL_TAG   ; X = tag of our cell
        LDX     0,X             ; X = cell base (dereference tag)
        LDD     _COL_RESUME,X   ; D = resume address from cell
        PSHB                    ; Push resume address onto stack (low byte)
        PSHA                    ; Push resume address onto stack (high byte)
        ;
        ; Step 5: Restore frame pointer, load return value, and jump via RTS
        ;
        ;         The C calling convention uses X as the frame pointer.
        ;         We saved it to the cell at _COL_FRAME_PTR (OPL-safe storage).
        ;         X still points to cell base after the push above.
        ;
        LDX     _COL_FRAME_PTR,X ; X = saved frame pointer from cell
        LDD     UTW_W2          ; D = OPL return value
        RTS                     ; Pop resume address and jump to it!
        ;
        ; Execution continues at the C statement after call_opl().
        ; X is restored to the frame pointer, D contains the return value.
        ;

; =============================================================================
; _call_opl_str_restore - Restore stack and resume with string first char
; =============================================================================
;
; This function is called by the OPL interpreter via USR(_call_opl_str_restore, SP).
; It's the string-return variant of _call_opl_restore.
;
; INPUT
;   D = saved_SP (the USR argument from our QCode buffer)
;   RTA_SP points to the OPL procedure's return value (a string)
;
; OUTPUT
;   Does not return normally - jumps to resume address
;   SP is restored to saved value
;   D = first character of the returned string (or 0 for empty string)
;
; STRING FORMAT ON LANGUAGE STACK
;   OPL strings are stored as: [length_byte][char1][char2]...[charN]
;   - RTA_SP points to the length byte
;   - First character is at RTA_SP + 1
;   - If length is 0, we return 0
;
; -----------------------------------------------------------------------------
_call_opl_str_restore:
        ;
        ; D = saved_SP (the USR argument from our QCode buffer!)
        ; RTA_SP points to OPL's return value (string on language stack)
        ;
        ; Step 1: Save saved_SP to temp (we need it later)
        ;
        STD     UTW_W1          ; UTW_W1 = saved_SP (temp storage)
        ;
        ; Step 2: Read first character of string from language stack
        ;
        ;         String format: [length][char1][char2]...
        ;         If length == 0, return 0
        ;         Otherwise, return char1 (byte at offset 1)
        ;
        LDX     RTA_SP          ; X = pointer to string on language stack
        LDAA    0,X             ; A = length byte
        BEQ     _cosr_empty     ; If length is 0, return 0
        ;
        ; String has at least one character - read it
        ;
        LDAB    1,X             ; B = first character
        CLRA                    ; A = 0 (char is 8-bit, return in low byte)
        BRA     _cosr_store
        ;
_cosr_empty:
        LDD     #0              ; Return 0 for empty string
        ;
_cosr_store:
        STD     UTW_W2          ; Save return value
        ;
        ; Step 3: Restore CPU stack pointer from saved_SP
        ;
        LDD     UTW_W1          ; D = saved_SP
        XGDX                    ; X = saved_SP
        TXS                     ; SP = X (CPU stack pointer restored!)
        ;
        ; Step 4: Get resume address from cell and push onto stack for RTS
        ;
        LDX     _CALL_OPL_TAG   ; X = tag of our cell
        LDX     0,X             ; X = cell base (dereference tag)
        LDD     _COL_RESUME,X   ; D = resume address from cell
        PSHB                    ; Push resume address onto stack (low byte)
        PSHA                    ; Push resume address onto stack (high byte)
        ;
        ; Step 5: Restore frame pointer, load return value, and jump via RTS
        ;
        LDX     _COL_FRAME_PTR,X ; X = saved frame pointer from cell
        LDD     UTW_W2          ; D = first char of string (in low byte B)
        RTS                     ; Pop resume address and jump to it!
        ;

; =============================================================================
; _call_opl_setup - Initialize call_opl support (C calling convention)
; =============================================================================
;
; SYNOPSIS
;   void _call_opl_setup(void);
;
; DESCRIPTION
;   Saves the USR entry stack pointer for later use by call_opl().
;   This is the C-calling-convention version.
;
;   AUTOMATIC INJECTION: When using the 'external' keyword in C code,
;   the compiler AUTOMATICALLY injects a call to this function at the
;   very start of main(), BEFORE any local variables are allocated.
;   Users do NOT need to call this function manually!
;
;   The saved SP is used to unwind the entire C call stack when
;   call_opl() needs to exit the current USR() context.
;
; USAGE (MODERN - RECOMMENDED)
;   The 'external' keyword makes this transparent:
;
;   external void azMENU();  // Compiler will auto-inject setup!
;
;   void main() {
;       // JSR _call_opl_setup is injected HERE by compiler
;       int x;
;       azMENU();  // Works seamlessly
;   }
;
; USAGE (LEGACY - Manual call, not recommended)
;   void main() {
;       _call_opl_setup();  // REQUIRED - must be FIRST, before locals!
;       int x;              // Locals AFTER setup
;       // ... rest of program using call_opl("name") ...
;   }
;
; FOR ASSEMBLY PROGRAMMERS
;   Use _call_opl_setup_asm and _call_opl_asm instead - see below.
;
; WHY IS THIS NEEDED?
;   When call_opl() is invoked from deep in the call stack, it needs
;   to exit the USR() context entirely so the OPL interpreter can
;   execute our QCode buffer. To do this, we need to restore SP to
;   the value that allows RTS to return to OPL.
;
;   If _call_opl_setup() is not called, call_opl() will crash.
;   If called AFTER local variable declarations, stack calculation
;   will be wrong and call_opl() will crash.
;
; STACK ANALYSIS
;   When OPL calls USR(_main, arg):
;     1. OPL interpreter calls machine code at _main
;     2. At _main entry: SP -> [return_addr to OPL interpreter]
;     3. Compiler prologue runs: PSHX (saves caller's X)
;     4. After prologue: SP -> [saved_X][return to OPL]
;     5. main() calls _call_opl_setup()
;     6. At our entry: SP -> [ret to main][saved_X][ret to OPL]
;                              0,X         2,X      4,X
;
;   To properly return to OPL, we need SP pointing to [ret to OPL].
;   That's current_SP + 4 (skip our return + main's saved_X).
;
; CRITICAL CONSTRAINT
;   This calculation assumes main() has NO locals pushed before
;   calling _call_opl_setup(). If there are locals between saved_X
;   and our return address, the calculation will be wrong!
;
;   CORRECT:
;     void main() { _call_opl_setup(); int x; ... }
;
;   WRONG (will crash):
;     void main() { int x; _call_opl_setup(); ... }
;
; NOTES
;   - Must be called before any call_opl() invocation
;   - Must be the first statement in main() (before locals!)
;   - Only needs to be called once per program execution
;
; -----------------------------------------------------------------------------
_call_opl_setup:
        ;
        ; At entry to _call_opl_setup, the stack looks like:
        ;
        ;   ┌─────────────────────────────────┐
        ;   │ SP+0, SP+1: return addr to main │ ← SP points here
        ;   │ SP+2, SP+3: main's saved_X      │ (from PSHX prologue)
        ;   │ SP+4, SP+5: return addr to OPL  │ ← We need SP here!
        ;   └─────────────────────────────────┘
        ;
        ; We want _usr_entry_sp = current_SP + 4
        ; so that TXS + RTS will return directly to OPL.
        ;
        ; STEP 1: Capture USR entry SP (before any stack changes)
        ;
        TSX                     ; X = SP (points to our return addr)
        XGDX                    ; D = current SP
        ADDD    #4              ; D = SP + 4 (skip ret_to_main + saved_X)
        PSHB
        PSHA                    ; Save usr_entry_sp temporarily on stack
        ;
        ; STEP 2: Allocate memory cell using AL$GRAB
        ;
        ; The allocator will find a free cell tag in $2024-$203E range
        ; and allocate the requested memory, returning the tag in X.
        ;
        LDD     #_COL_SIZE      ; D = 28 bytes needed
        SWI                     ; Call AL$GRAB allocator
        FCB     AL_GRAB         ; X = tag of allocated cell
        STX     _CALL_OPL_TAG   ; Save tag to fixed zero-page location
        ;
        ; STEP 3: Store usr_entry_sp in the allocated cell
        ;
        LDX     0,X             ; X = cell base (dereference tag)
        PULA
        PULB                    ; D = usr_entry_sp (from stack)
        STD     _COL_USR_SP,X   ; Store at offset 4 in cell
        ;
        RTS

; =============================================================================
; =============================================================================
;
;                    ASSEMBLY PROGRAMMER INTERFACE
;
; =============================================================================
; =============================================================================
;
; The following routines provide a clean interface for assembly language
; programmers who want to call OPL procedures without using the C compiler.
;
; QUICK START FOR ASSEMBLY PROGRAMMERS
; -------------------------------------
;
; 1. At the VERY START of your program (before ANY stack operations):
;
;        ORG     $2100
;        JSR     _call_opl_setup_asm   ; MUST be first instruction!
;        ; ... rest of your program ...
;
; 2. To call an OPL procedure:
;
;        LDD     #_myproc_name         ; Load address of procedure name
;        JSR     _call_opl_asm         ; Call OPL procedure
;        ; Execution resumes here after OPL returns
;
;    _myproc_name:
;        FCC     "azMENU"              ; Procedure name (max 8 chars)
;        FCB     0                     ; Null terminator
;
; COMPLETE EXAMPLE
; ----------------
;
;        ORG     $2100
;
;    ; ─────────────────────────────────────────────────────────────────────
;    ; Program entry point
;    ; ─────────────────────────────────────────────────────────────────────
;    _main:
;        JSR     _call_opl_setup_asm   ; Initialize OPL call support (FIRST!)
;
;        ; Your program logic here...
;        LDAA    #'H'
;        JSR     _putchar
;
;        ; Call an OPL procedure
;        LDD     #_menu_proc           ; D = pointer to procedure name
;        JSR     _call_opl_asm         ; Call the OPL procedure
;        ; OPL procedure runs, then execution resumes here
;
;        ; Continue after OPL returns...
;        LDAA    #'!'
;        JSR     _putchar
;
;        RTS                           ; Return to OPL interpreter
;
;    ; ─────────────────────────────────────────────────────────────────────
;    ; Procedure name strings
;    ; ─────────────────────────────────────────────────────────────────────
;    _menu_proc:
;        FCC     "azMENU"
;        FCB     0
;
;        INCLUDE "runtime.inc"         ; Include runtime library
;        END
;
; KEY DIFFERENCES FROM C VERSION
; ------------------------------
;
; | Feature          | C Version (_call_opl)      | Asm Version (_call_opl_asm) |
; |------------------|----------------------------|-----------------------------|
; | Name pointer     | Pushed on stack            | Passed in D register        |
; | Stack cleanup    | Requires INS INS after     | No cleanup needed           |
; | Resume address   | Return addr + 2            | Return addr (exact)         |
; | Setup function   | _call_opl_setup (SP+4)     | _call_opl_setup_asm (SP+2)  |
;
; =============================================================================

; =============================================================================
; _call_opl_setup_asm - Initialize OPL call support (assembly version)
; =============================================================================
;
; SYNOPSIS (assembly)
;   JSR     _call_opl_setup_asm
;
; DESCRIPTION
;   Saves the USR entry stack pointer for later use by _call_opl_asm.
;   This is the assembly-language version - simpler stack calculation.
;
;   MUST be called as the VERY FIRST instruction in your program,
;   BEFORE any PSHX, PSHA, PSHB, or other stack-modifying operations!
;
; STACK LAYOUT AT ENTRY
;   When OPL calls USR(addr, arg), the stack looks like:
;     SP -> [return_to_setup][return_to_OPL]
;            0,1              2,3
;
;   We want SP pointing to [return_to_OPL] for unwinding.
;   So we calculate: _usr_entry_sp = current_SP + 2
;
; EXAMPLE
;        ORG     $2100
;    _main:
;        JSR     _call_opl_setup_asm   ; MUST be first!
;        ; ... your program ...
;
; CLOBBERS
;   D, X
;
; -----------------------------------------------------------------------------
_call_opl_setup_asm:
        ;
        ; STEP 1: Capture USR entry SP
        ;
        TSX                     ; X = SP (points to our return addr)
        XGDX                    ; D = current SP
        ADDD    #2              ; D = SP + 2 (skip just our return addr)
        PSHB
        PSHA                    ; Save usr_entry_sp temporarily
        ;
        ; STEP 2: Allocate memory cell
        ;
        LDD     #_COL_SIZE      ; D = 28 bytes needed
        SWI                     ; Call AL$GRAB allocator
        FCB     AL_GRAB         ; X = tag of allocated cell
        STX     _CALL_OPL_TAG   ; Save tag to zero-page
        ;
        ; STEP 3: Store usr_entry_sp in cell
        ;
        LDX     0,X             ; X = cell base (dereference tag)
        PULA
        PULB                    ; D = usr_entry_sp
        STD     _COL_USR_SP,X   ; Store at offset 4 in cell
        ;
        RTS

; =============================================================================
; _call_opl_asm - Call an OPL procedure (assembly version)
; =============================================================================
;
; SYNOPSIS (assembly)
;   LDD     #procedure_name_string
;   JSR     _call_opl_asm
;   ; Execution resumes here after OPL procedure returns
;
; DESCRIPTION
;   Calls an external OPL procedure by name. When the procedure completes,
;   execution resumes at the instruction immediately after the JSR.
;   Stack state and registers are preserved across the call.
;
;   This is the assembly-friendly version that:
;   - Takes the procedure name pointer in D register (not on stack)
;   - Does NOT require any stack cleanup after the call
;   - Resumes at the exact return address (no +2 adjustment)
;
; PARAMETERS
;   D = Pointer to null-terminated procedure name string (max 8 chars)
;
; RETURNS
;   D = 0 (standard USR return value)
;   Execution resumes at the instruction after JSR _call_opl_asm
;
; REQUIREMENTS
;   - _call_opl_setup_asm MUST be called first (at program start)
;   - Procedure name must be <= 8 characters
;   - Uses default device (A:) for procedure lookup
;
; EXAMPLE
;        ; Call the azMENU OPL procedure
;        LDD     #_azMENU_name
;        JSR     _call_opl_asm
;        ; Execution resumes here
;        ; D = 0 (can be ignored)
;        BRA     _continue
;
;    _azMENU_name:
;        FCC     "azMENU"
;        FCB     0
;
;    _continue:
;        ; ... rest of program ...
;
; CLOBBERS
;   A, B, X (all registers may be modified)
;
; STACK EFFECT
;   Net zero - SP is preserved across the call
;
; HOW IT WORKS
;   1. Builds a QCode buffer containing: procedure_call + USR(restore, SP)
;   2. Sets RTA_PC to point to this buffer
;   3. Unwinds stack to USR entry and returns to OPL interpreter
;   4. Interpreter executes our buffer: calls OPL proc, then USR(restore)
;   5. _call_opl_restore receives saved_SP, restores stack, jumps to resume
;   6. Execution continues at the instruction after JSR _call_opl_asm
;
; -----------------------------------------------------------------------------
_call_opl_asm:
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 1: Save name pointer and capture resume information
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; D = name_ptr (passed in D register - assembly convention!)
        ;
        PSHB
        PSHA                    ; Save name_ptr on stack
        ;
        ; Get return address and use it directly as resume address
        ; (no +2 adjustment needed for assembly - no INS cleanup)
        ;
        TSX                     ; X = SP (points past pushed name_ptr)
        LDD     2,X             ; D = return address (at offset 2)
        PSHB
        PSHA                    ; Save resume_addr on stack
        ;
        ; Calculate resume_SP = entry_SP + 2 (just skip our return addr)
        ;
        XGDX                    ; D = SP (at time of name_ptr push)
        ADDD    #4              ; D = entry_SP + 4 (skip name_ptr push + ret addr)
        PSHB
        PSHA                    ; Save saved_sp on stack
        ;
        ; Stack: [saved_sp][resume_addr][name_ptr][ret_addr]
        ;
        ; Store values to cell
        ;
        JSR     _call_opl_get_cell ; X = cell base
        PULA
        PULB                    ; D = saved_sp
        STD     _COL_SAVED_SP,X ; Store at offset 2
        PULA
        PULB                    ; D = resume_addr
        STD     _COL_RESUME,X   ; Store at offset 28
        PULA
        PULB                    ; D = name_ptr
        STD     _COL_NAME_PTR,X ; Store at offset 0

        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 2: Count procedure name length
        ; ═══════════════════════════════════════════════════════════════════
        ;
        LDX     _COL_NAME_PTR,X ; X = pointer to name string (from cell)
        CLRB                    ; B = length counter, start at 0
_call_opl_asm_count:
        TST     0,X             ; Test byte at current position
        BEQ     _call_opl_asm_build ; If null terminator, done counting
        INX                     ; Advance to next character
        INCB                    ; Increment length counter
        CMPB    #8              ; Check against Psion's 8-char limit
        BNE     _call_opl_asm_count ; Continue if under limit

_call_opl_asm_build:
        ;
        ; ═══════════════════════════════════════════════════════════════════
        ; STEP 3-6: Build buffer and unwind (shared with C version)
        ; ═══════════════════════════════════════════════════════════════════
        ;
        ; Jump to the shared build code in _call_opl.
        ; At this point:
        ;   - B = name length (1-8)
        ;   - Cell contains: name_ptr, saved_sp, resume address
        ;
        ; The _call_opl_build code is shared and handles:
        ;   - Building the QCode buffer
        ;   - Setting RTA_PC
        ;   - Unwinding to USR entry
        ;
        JMP     _call_opl_build ; Reuse shared build/unwind code

; =============================================================================
; Dynamic Memory Allocation for OPL Procedure Call Support
; =============================================================================
; These variables are stored in a dynamically allocated memory cell obtained
; via the Psion allocator service (AL$GRAB). This ensures safe RAM allocation
; that doesn't conflict with system usage.
;
; The allocator manages 32 cells with tags at $2000-$203E.
; Cells $2024-$203E (14 cells) are available for applications.
;
; MEMORY CELL LAYOUT (offsets from cell base):
;   +0:  name_ptr   (2B) - Pointer to procedure name string
;   +2:  saved_sp   (2B) - SP value to restore after OPL call
;   +4:  usr_sp     (2B) - USR() entry SP for stack unwinding
;   +6:  namelen    (1B) - Procedure name length (1-8)
;   +7:  idx        (1B) - Buffer write index
;   +8:  buf       (20B) - QCode injection buffer
;   Total: 28 bytes
;
; FIXED ZERO-PAGE STORAGE (these survive stack manipulation):
;   UTW_W0 ($84): Cell TAG returned by AL$GRAB (dereference to get base)
;   UTW_W1 ($86): Resume address (must be accessible after TXS in restore)
;
; WHY UTW_W1 FOR RESUME?
;   _call_opl_restore needs to access resume_addr AFTER restoring SP.
;   At that point, the cell base pointer (via tag dereference) is lost
;   because X was used for TXS. So resume must be at a fixed location.
;
; =============================================================================

; -----------------------------------------------------------------------------
; Cell Layout Offsets
; -----------------------------------------------------------------------------
; The cell stores all data needed for external OPL procedure calls. It must
; survive stack unwinding and OPL execution.
;
; =============================================================================
; PARAMETER LIMIT CONFIGURATION
; =============================================================================
; To increase the maximum number of external OPL parameters:
;
;   1. Change _COL_MAX_PARAMS below (OPL supports up to 16)
;   2. Update MAX_EXTERNAL_PARAMS in src/psion_sdk/smallc/parser.py to match
;   3. The buffer size and cell layout will adjust automatically via EQUs
;
; BUFFER SIZE CALCULATION:
;   Each parameter requires 5 bytes in the QCode buffer:
;     - $22 HH LL  (3 bytes) - PUSHWORD to push the value
;     - $20 $00    (2 bytes) - PUSHBYTE type marker (0 = integer)
;
;   Fixed overhead (19 bytes):
;     - param count:  2 bytes ($20 NN)
;     - proc call:   10 bytes ($7D len name[8] - max 8-char name)
;     - restore addr: 3 bytes ($22 HH LL)
;     - saved SP:     3 bytes ($22 HH LL)
;     - USR opcode:   1 byte  ($9F)
;
;   Formula: buffer_size = (max_params * 5) + 19
;
;   Examples:
;     4 params:  4*5 + 19 =  39 bytes -> use 40
;     8 params:  8*5 + 19 =  59 bytes -> use 64
;    16 params: 16*5 + 19 =  99 bytes -> use 100
;
; MEMORY IMPACT:
;   Cell is allocated via AL$GRAB only when external calls are used.
;   Current config (4 params): 49 bytes per cell
;   With 16 params: would be 113 bytes per cell
;   This is negligible on 32KB machines since only one cell is active at a time.
;
; =============================================================================

; Maximum external OPL parameters supported (OPL allows up to 16)
; >>> CHANGE THIS VALUE TO INCREASE PARAMETER LIMIT <<<
_COL_MAX_PARAMS EQU     4

; Bytes per parameter in QCode buffer (PUSHWORD + type marker)
_COL_BYTES_PER_PARAM    EQU     5       ; $22 HH LL $20 $00

; Fixed overhead in QCode buffer (count + proc + restore + SP + USR)
_COL_BUF_OVERHEAD       EQU     19      ; See calculation above

; Buffer size calculation (with padding for safety)
; For 4 params: 4*5 + 19 = 39, rounded to 40
_COL_BUF_SIZE   EQU     (_COL_MAX_PARAMS * _COL_BYTES_PER_PARAM) + _COL_BUF_OVERHEAD + 1

; Cell field offsets (derived from above constants)
_COL_NAME_PTR   EQU     0       ; Pointer to procedure name string (2B)
_COL_SAVED_SP   EQU     2       ; Saved SP for stack restoration (2B)
_COL_USR_SP     EQU     4       ; USR() entry SP for unwinding (2B)
_COL_NAMELEN    EQU     6       ; Procedure name length 1-8 (1B)
_COL_IDX        EQU     7       ; Buffer write index (1B)
_COL_PARAM_CNT  EQU     8       ; Parameter count for param calls (1B)
_COL_BUF        EQU     9       ; Buffer for synthesized QCode
_COL_RESUME     EQU     _COL_BUF + _COL_BUF_SIZE        ; Resume address (2B)
_COL_FRAME_PTR  EQU     _COL_RESUME + 2                 ; Saved frame pointer (2B)
_COL_SIZE       EQU     _COL_FRAME_PTR + 2              ; Total cell size

; -----------------------------------------------------------------------------
; Compatibility Symbols (point to cell offsets for documentation)
; -----------------------------------------------------------------------------
; These map the old names to cell offsets. Code must load cell base first!
;
_call_opl_name_ptr      EQU     _COL_NAME_PTR
_call_opl_saved_sp      EQU     _COL_SAVED_SP
_usr_entry_sp           EQU     _COL_USR_SP
_call_opl_namelen       EQU     _COL_NAMELEN
_call_opl_idx           EQU     _COL_IDX
_call_opl_buf           EQU     _COL_BUF

; =============================================================================
; _call_opl_get_cell - Get cell base address
; =============================================================================
; Dereferences the cell tag to get the current base address.
; The base address may change if other cells are resized, so always
; call this before accessing cell data.
;
; INPUT:  None
; OUTPUT: X = cell base address
; CLOBBERS: None (X is the output)
;
; -----------------------------------------------------------------------------
_call_opl_get_cell:
        LDX     _CALL_OPL_TAG   ; X = tag (e.g., $2024)
        LDX     0,X             ; X = cell base (dereference tag)
        RTS

; =============================================================================
; _call_opl_cleanup - Free the allocated memory cell
; =============================================================================
; Call this when the program exits to release the allocated memory.
; This is good practice but not strictly required as the Psion reclaims
; all cells when the program terminates.
;
; INPUT:  None
; OUTPUT: Cell is freed
; CLOBBERS: A, B, X (trashed by AL$FREE)
;
; -----------------------------------------------------------------------------
_call_opl_cleanup:
        LDX     _CALL_OPL_TAG   ; X = tag of our cell
        SWI                     ; Call AL$FREE allocator
        FCB     AL_FREE         ; Free the cell
        RTS


; =============================================================================
; Data Section - Runtime buffers
; =============================================================================

; String buffer for _call_opl_restore float-to-int conversion
; Used by MT_FBIN to convert BCD float to string, then parsed to integer
_cor_strbuf:
        RMB     16              ; 16 bytes for integer string (e.g., "-32768" + padding)

; =============================================================================
; End of Runtime Library
; =============================================================================
