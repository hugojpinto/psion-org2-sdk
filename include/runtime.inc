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

_strlen:        JMP     __strlen        ; char *s -> int length
_memcpy:        JMP     __memcpy        ; void *dest, void *src, int n -> void *dest
_memset:        JMP     __memset        ; void *dest, int c, int n -> void *dest

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
; Uses KB_TEST ($4B): returns key in B, carry set if key available
; -----------------------------------------------------------------------------
_testkey:
        SWI
        FCB     $4B         ; KB_TEST
        BCC     _testkey_none
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
; End of Runtime Library
; =============================================================================
