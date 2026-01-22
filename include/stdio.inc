; =============================================================================
; STDIO.INC - Extended String and Formatting Functions for Psion Organiser II
; =============================================================================
;
; This file provides OPTIONAL extended string functions and formatted output.
; Include this file only if you need strrchr, strstr, strncat, or sprintf.
;
; INCLUDE ORDER:
;   INCLUDE "psion.inc"     ; Core definitions (syscalls, sysvars)
;   INCLUDE "runtime.inc"   ; Core C runtime (required)
;   INCLUDE "stdio.inc"     ; This file (optional, include last)
;   INCLUDE "ctype.inc"     ; Character classification (optional, after stdio.inc)
;
; CODE SIZE:
;   Including this file adds approximately 250-300 bytes to your program.
;   Only include it if you actually need these functions.
;
; =============================================================================
; FOR C PROGRAMMERS:
; =============================================================================
;   See stdio.h for C function declarations. The implementations here are
;   called by the C runtime. Functions: strrchr, strstr, strncat, sprintf.
;
; =============================================================================
; FOR ASSEMBLY PROGRAMMERS:
; =============================================================================
;   This file provides both function implementations AND convenience macros.
;
;   FUNCTIONS (call via JSR after pushing args to stack):
;     _strrchr  : Find last occurrence of character in string
;     _strstr   : Find substring in string
;     _strncat  : Bounded string concatenation
;     _sprintf  : Formatted string output
;
;   MACROS (expand inline, simpler to use):
;     STRRCHR   : Call _strrchr with two arguments
;     STRSTR    : Call _strstr with two arguments
;     STRNCAT   : Call _strncat with three arguments
;     SPRINTF1  : Call sprintf with 1 format argument
;     SPRINTF2  : Call sprintf with 2 format arguments
;
;   STACK ARGUMENT ORDER:
;     Arguments are pushed RIGHT-TO-LEFT (C calling convention).
;     First argument ends up at lowest address (highest offset from SP).
;
;   Example using function directly:
;     ; Find last '/' in path string
;     LDD     #'/'            ; Character to find (arg 2)
;     PSHB
;     PSHA
;     LDD     #MY_PATH        ; String to search (arg 1)
;     PSHB
;     PSHA
;     JSR     _strrchr        ; Call function
;     INS                     ; Clean up 4 bytes of args
;     INS
;     INS
;     INS
;     ; D = pointer to last '/' or 0 if not found
;
;   Example using macro:
;     STRRCHR MY_PATH, '/'    ; Much simpler!
;     ; D = result
;
; CALLING CONVENTION:
;   All functions follow the Small-C calling convention:
;   - Arguments on stack (right-to-left push order)
;   - Return value in D register (A:B for 16-bit)
;   - Caller cleans up stack
;   - X register preserved across calls (via PSHX/PULX)
;
; Author: Hugo José Pinto & Contributors
; Part of the Psion Organiser II SDK
; See: specs/12-standard-library-expansion.md
; =============================================================================

; =============================================================================
; ASSEMBLY CONVENIENCE MACROS
; =============================================================================
; These macros simplify calling stdio functions from assembly code.
; They handle the stack setup and cleanup automatically.
;
; IMPORTANT: All macros leave the result in D register.
;            Macros may clobber A, B, and flags.

; -----------------------------------------------------------------------------
; STRRCHR - Find last occurrence of character in string
; -----------------------------------------------------------------------------
; Usage: STRRCHR string_addr, char_value
;
; Input:
;   string_addr - Address of null-terminated string (label or immediate)
;   char_value  - Character to search for (ASCII value or character literal)
;
; Output: D = pointer to last occurrence, or 0 if not found
; Clobbers: A, B, X (X restored after call)
;
; Example:
;   STRRCHR my_path, '/'
;   CPD     #0
;   BEQ     not_found
;   ; D points to last '/'
;
; my_path:  FCC "/usr/bin/prog"
;           FCB 0
; -----------------------------------------------------------------------------
MACRO STRRCHR, string_addr, char_value
    ; Push char_value (arg 2, right-to-left)
    LDD     #\char_value
    PSHB
    PSHA
    ; Push string_addr (arg 1)
    LDD     #\string_addr
    PSHB
    PSHA
    ; Call function
    JSR     _strrchr
    ; Clean up stack (4 bytes)
    INS
    INS
    INS
    INS
    ; Result in D
ENDM

; -----------------------------------------------------------------------------
; STRSTR - Find substring in string
; -----------------------------------------------------------------------------
; Usage: STRSTR haystack_addr, needle_addr
;
; Input:
;   haystack_addr - Address of string to search in
;   needle_addr   - Address of substring to find
;
; Output: D = pointer to first occurrence of needle, or 0 if not found
; Clobbers: A, B, X
;
; Example:
;   STRSTR my_text, my_search
;   CPD     #0
;   BEQ     not_found
;
; my_text:    FCC "Hello World"
;             FCB 0
; my_search:  FCC "World"
;             FCB 0
; -----------------------------------------------------------------------------
MACRO STRSTR, haystack_addr, needle_addr
    ; Push needle_addr (arg 2)
    LDD     #\needle_addr
    PSHB
    PSHA
    ; Push haystack_addr (arg 1)
    LDD     #\haystack_addr
    PSHB
    PSHA
    ; Call function
    JSR     _strstr
    ; Clean up (4 bytes)
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; STRNCAT - Bounded string concatenation
; -----------------------------------------------------------------------------
; Usage: STRNCAT dest_addr, src_addr, max_chars
;
; Input:
;   dest_addr - Address of destination string (must have space)
;   src_addr  - Address of source string to append
;   max_chars - Maximum characters to append (16-bit value)
;
; Output: D = dest_addr
; Clobbers: A, B, X
;
; Note: Unlike strncpy, strncat ALWAYS adds a null terminator.
;       Make sure dest has room for n chars plus the terminator!
;
; Example:
;   ; Append up to 5 chars of suffix to buffer
;   STRNCAT buffer, suffix, 5
;
; buffer:   FCC "Hello"
;           RMB 10        ; Room for more chars
; suffix:   FCC " World!"
;           FCB 0
; -----------------------------------------------------------------------------
MACRO STRNCAT, dest_addr, src_addr, max_chars
    ; Push max_chars (arg 3)
    LDD     #\max_chars
    PSHB
    PSHA
    ; Push src_addr (arg 2)
    LDD     #\src_addr
    PSHB
    PSHA
    ; Push dest_addr (arg 1)
    LDD     #\dest_addr
    PSHB
    PSHA
    ; Call function
    JSR     _strncat
    ; Clean up (6 bytes)
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; SPRINTF1 - Formatted string output with 1 argument
; -----------------------------------------------------------------------------
; Usage: SPRINTF1 buffer_addr, format_addr, arg1
;
; Input:
;   buffer_addr - Address of output buffer (must be large enough)
;   format_addr - Address of format string
;   arg1        - First format argument
;
; Output: D = number of characters written
; Clobbers: A, B, X
;
; Supported formats: %d (signed), %u (unsigned), %x (hex), %c (char), %s (string)
;
; Example:
;   SPRINTF1 buffer, fmt_score, score_value
;
; buffer:     RMB 20
; fmt_score:  FCC "Score: %d"
;             FCB 0
; score_value: FDB 1234
; -----------------------------------------------------------------------------
MACRO SPRINTF1, buffer_addr, format_addr, arg1
    ; Push arg1
    LDD     \arg1
    PSHB
    PSHA
    ; Push format_addr
    LDD     #\format_addr
    PSHB
    PSHA
    ; Push buffer_addr
    LDD     #\buffer_addr
    PSHB
    PSHA
    ; Call sprintf1 wrapper
    JSR     _sprintf1
    ; Clean up (6 bytes: buf + fmt + arg1)
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; SPRINTF2 - Formatted string output with 2 arguments
; -----------------------------------------------------------------------------
; Usage: SPRINTF2 buffer_addr, format_addr, arg1, arg2
;
; Same as SPRINTF1 but with 2 format arguments.
;
; Example:
;   SPRINTF2 buffer, fmt_pos, pos_x, pos_y
;
; buffer:   RMB 20
; fmt_pos:  FCC "X:%d Y:%d"
;           FCB 0
; pos_x:    FDB 10
; pos_y:    FDB 20
; -----------------------------------------------------------------------------
MACRO SPRINTF2, buffer_addr, format_addr, arg1, arg2
    ; Push arg2
    LDD     \arg2
    PSHB
    PSHA
    ; Push arg1
    LDD     \arg1
    PSHB
    PSHA
    ; Push format_addr
    LDD     #\format_addr
    PSHB
    PSHA
    ; Push buffer_addr
    LDD     #\buffer_addr
    PSHB
    PSHA
    ; Call sprintf2 wrapper
    JSR     _sprintf2
    ; Clean up (8 bytes)
    INS
    INS
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; =============================================================================
; STACK LAYOUT REFERENCE
; =============================================================================
; These diagrams show the stack layout after PSHX+TSX in each function.
; Offsets are from X register after TSX.
;
; _strrchr(s, c):
;   Stack: [saved_X 2B][ret 2B][s 2B][c 2B]
;   Offsets: saved_X=0-1, ret=2-3, s=4-5, c=6-7 (low byte at 7)
;
; _strstr(haystack, needle):
;   Stack: [saved_X 2B][ret 2B][haystack 2B][needle 2B]
;   Offsets: saved_X=0-1, ret=2-3, haystack=4-5, needle=6-7
;
; _strncat(dest, src, n):
;   Stack: [saved_X 2B][ret 2B][dest 2B][src 2B][n 2B]
;   Offsets: saved_X=0-1, ret=2-3, dest=4-5, src=6-7, n=8-9
;
; _sprintf(buf, fmt, a1, a2, a3, a4):
;   Stack: [saved_X 2B][ret 2B][buf 2B][fmt 2B][a1 2B][a2 2B][a3 2B][a4 2B]
;   Offsets: saved_X=0-1, ret=2-3, buf=4-5, fmt=6-7, a1=8-9, a2=10-11,
;            a3=12-13, a4=14-15
;
; =============================================================================

; =============================================================================
; FUNCTION IMPLEMENTATIONS
; =============================================================================

; -----------------------------------------------------------------------------
; _strrchr - Find last occurrence of character in string
; -----------------------------------------------------------------------------
; Searches string s for the LAST occurrence of character c.
;
; Input:  Stack: s (pointer to string), c (character to find)
;         After PSHX+TSX: s at 4,X, c at 6,X (low byte at 7,X)
; Output: D = pointer to last occurrence, or 0 (NULL) if not found
;
; Algorithm:
;   1. Initialize "found" pointer to NULL
;   2. Scan string from start to end
;   3. Each time c is found, update "found" pointer
;   4. Return final "found" pointer (last occurrence)
;
; Code size: ~35 bytes
; -----------------------------------------------------------------------------
_strrchr:
        PSHX                    ; Save caller's frame pointer
        TSX
        LDX     4,X             ; X = string pointer
        STX     _strrchr_str    ; Save for scanning

        TSX
        LDAB    7,X             ; B = character to find (low byte)
        STAB    _strrchr_char

        ; Initialize "found" pointer to NULL
        LDD     #0
        STD     _strrchr_found

        ; Scan through string
        LDX     _strrchr_str

_strrchr_loop:
        LDAA    0,X             ; A = current character

        ; Check if this is the character we're looking for
        CMPA    _strrchr_char
        BNE     _strrchr_not_match
        ; Found a match - save this position
        STX     _strrchr_found

_strrchr_not_match:
        ; Check if we've reached null terminator
        TSTA
        BEQ     _strrchr_done   ; End of string

        INX                     ; Advance to next character
        BRA     _strrchr_loop

_strrchr_done:
        ; Return the last found position (or NULL if never found)
        LDD     _strrchr_found
        PULX                    ; Restore caller's frame pointer
        RTS

; --- Local storage for _strrchr ---
_strrchr_str:   RMB     2       ; Original string pointer
_strrchr_char:  RMB     1       ; Character to find
_strrchr_found: RMB     2       ; Pointer to last occurrence (or NULL)

; -----------------------------------------------------------------------------
; _strstr - Find substring in string
; -----------------------------------------------------------------------------
; Finds the first occurrence of needle in haystack.
;
; Input:  Stack: haystack (pointer), needle (pointer)
;         After PSHX+TSX: haystack at 4,X, needle at 6,X
; Output: D = pointer to first occurrence of needle, or 0 (NULL) if not found
;
; Algorithm:
;   1. If needle is empty, return haystack
;   2. For each position in haystack:
;      a. Try to match all of needle starting at this position
;      b. If full match found, return this position
;      c. If no match, advance to next position in haystack
;   3. If end of haystack reached without match, return NULL
;
; Code size: ~70 bytes
; -----------------------------------------------------------------------------
_strstr:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Get parameters
        LDD     4,X             ; haystack
        STD     _strstr_hay
        LDD     6,X             ; needle
        STD     _strstr_ndl

        ; Check if needle is empty - if so, return haystack
        LDX     _strstr_ndl
        TST     0,X             ; Check first char of needle
        BNE     _strstr_search  ; Not empty, do search

        ; Needle is empty, return haystack
        LDD     _strstr_hay
        PULX
        RTS

_strstr_search:
        ; Outer loop: try each starting position in haystack
        LDX     _strstr_hay

_strstr_outer:
        ; Check if we've reached end of haystack
        TST     0,X             ; Check current haystack char
        BEQ     _strstr_not_found  ; End of haystack, not found

        ; Save current haystack position as potential match start
        STX     _strstr_pos

        ; Inner loop: try to match needle at this position
        ; Reset needle pointer
        LDD     _strstr_ndl
        STD     _strstr_np      ; Needle pointer for inner loop

_strstr_inner:
        ; Get current needle character
        LDX     _strstr_np
        LDAB    0,X             ; B = needle char
        BEQ     _strstr_matched ; End of needle = full match!

        ; Get corresponding haystack character
        LDX     _strstr_pos
        LDAA    0,X             ; A = haystack char at match position

        ; Check if haystack ended
        TSTA
        BEQ     _strstr_not_found  ; Haystack ended before needle matched

        ; Compare characters
        CBA                     ; Compare A (haystack) with B (needle)
        BNE     _strstr_next_pos   ; Mismatch, try next position

        ; Characters match, advance both pointers
        LDX     _strstr_np
        INX
        STX     _strstr_np
        LDX     _strstr_pos
        INX
        STX     _strstr_pos

        BRA     _strstr_inner

_strstr_next_pos:
        ; No match at this position, try next
        LDX     _strstr_hay
        INX
        STX     _strstr_hay
        BRA     _strstr_outer

_strstr_matched:
        ; Return the starting position of the match
        LDD     _strstr_hay
        PULX
        RTS

_strstr_not_found:
        LDD     #0              ; Return NULL
        PULX
        RTS

; --- Local storage for _strstr ---
_strstr_hay:    RMB     2       ; Current haystack scan position
_strstr_ndl:    RMB     2       ; Original needle pointer
_strstr_pos:    RMB     2       ; Current match position in haystack
_strstr_np:     RMB     2       ; Current position in needle during match

; -----------------------------------------------------------------------------
; _strncat - Concatenate strings with length limit
; -----------------------------------------------------------------------------
; Appends at most n characters from src to dest, plus null terminator.
;
; Input:  Stack: dest (pointer), src (pointer), n (count)
;         After PSHX+TSX: dest at 4,X, src at 6,X, n at 8,X
; Output: D = dest pointer
;
; Algorithm:
;   1. Find end of dest (where null terminator is)
;   2. Copy at most n characters from src to end of dest
;   3. Add null terminator
;
; Unlike strncpy, strncat ALWAYS adds a null terminator.
;
; Code size: ~55 bytes
; -----------------------------------------------------------------------------
_strncat:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Save dest for return value
        LDD     4,X             ; dest
        STD     _strncat_ret

        ; Copy parameters
        LDD     4,X             ; dest
        STD     _strncat_dst
        LDD     6,X             ; src
        STD     _strncat_src
        LDD     8,X             ; n
        STD     _strncat_n

        ; Find end of dest string
        LDX     _strncat_dst
_strncat_find_end:
        TST     0,X
        BEQ     _strncat_found_end
        INX
        BRA     _strncat_find_end

_strncat_found_end:
        ; X now points to null terminator in dest
        STX     _strncat_dst    ; Update dest pointer to end

_strncat_copy:
        ; Check if n == 0
        LDD     _strncat_n
        TSTB
        BNE     _strncat_do_copy
        TSTA
        BEQ     _strncat_terminate  ; n == 0, add terminator

_strncat_do_copy:
        ; Decrement n
        SUBD    #1
        STD     _strncat_n

        ; Get character from src
        LDX     _strncat_src
        LDAB    0,X             ; B = *src
        BEQ     _strncat_terminate  ; src ended, add terminator

        ; Store to dest
        LDX     _strncat_dst
        STAB    0,X

        ; Advance pointers
        LDX     _strncat_src
        INX
        STX     _strncat_src
        LDX     _strncat_dst
        INX
        STX     _strncat_dst

        BRA     _strncat_copy

_strncat_terminate:
        ; Add null terminator
        LDX     _strncat_dst
        CLR     0,X

        ; Return original dest
        LDD     _strncat_ret
        PULX
        RTS

; --- Local storage for _strncat ---
_strncat_ret:   RMB     2       ; Return value (original dest)
_strncat_dst:   RMB     2       ; Working dest pointer
_strncat_src:   RMB     2       ; Working src pointer
_strncat_n:     RMB     2       ; Remaining count

; -----------------------------------------------------------------------------
; _sprintf - Formatted string output
; -----------------------------------------------------------------------------
; Writes formatted data to a string buffer. Simplified version for Psion.
;
; Input:  Stack: buf (pointer), fmt (pointer), a1, a2, a3, a4 (args)
;         After PSHX+TSX: buf at 4,X, fmt at 6,X, args at 8,X..14,X
; Output: D = number of characters written
;
; Supported formats: %d, %u, %x, %c, %s, %%
; Width specifiers: %5d, %-5d, %05d
;
; Due to Small-C limitations, only 4 arguments are supported.
;
; Code size: ~150 bytes
; -----------------------------------------------------------------------------
_sprintf:
        PSHX                    ; Save caller's frame pointer
        TSX

        ; Initialize
        LDD     4,X             ; buf
        STD     _sprintf_buf
        STD     _sprintf_ptr    ; Current write position
        LDD     6,X             ; fmt
        STD     _sprintf_fmt
        LDD     8,X             ; First arg
        STD     _sprintf_args
        LDD     10,X            ; Second arg
        STD     _sprintf_args+2
        LDD     12,X            ; Third arg
        STD     _sprintf_args+4
        LDD     14,X            ; Fourth arg
        STD     _sprintf_args+6

        ; Argument index (0-3)
        CLR     _sprintf_argidx

        ; Character count
        LDD     #0
        STD     _sprintf_count

_sprintf_loop:
        ; Get next format character
        LDX     _sprintf_fmt
        LDAB    0,X             ; B = format char
        BEQ     _sprintf_done   ; End of format string

        INX
        STX     _sprintf_fmt    ; Advance format pointer

        ; Check for %
        CMPB    #'%'
        BEQ     _sprintf_format

        ; Regular character - output directly
        BSR     _sprintf_putc
        BRA     _sprintf_loop

_sprintf_format:
        ; Handle format specifier
        ; Get next character
        LDX     _sprintf_fmt
        LDAB    0,X
        BEQ     _sprintf_done   ; Unexpected end

        INX
        STX     _sprintf_fmt

        ; Check for %% (literal percent)
        CMPB    #'%'
        BNE     _sprintf_not_pct
        LDAB    #'%'
        BSR     _sprintf_putc
        BRA     _sprintf_loop

_sprintf_not_pct:
        ; Parse width and flags (simplified - just check for digits)
        CLR     _sprintf_width
        CLR     _sprintf_flags

        ; Check for '-' (left align)
        CMPB    #'-'
        BNE     _sprintf_chk_zero
        LDAA    #1
        STAA    _sprintf_flags  ; Flag 1 = left align
        LDX     _sprintf_fmt
        LDAB    0,X
        INX
        STX     _sprintf_fmt

_sprintf_chk_zero:
        ; Check for '0' (zero pad)
        CMPB    #'0'
        BNE     _sprintf_chk_width
        LDAA    _sprintf_flags
        ORAA    #2              ; Flag 2 = zero pad
        STAA    _sprintf_flags
        LDX     _sprintf_fmt
        LDAB    0,X
        INX
        STX     _sprintf_fmt

_sprintf_chk_width:
        ; Check for width digits
        CMPB    #'1'
        BLO     _sprintf_specifier
        CMPB    #'9'
        BHI     _sprintf_specifier
        ; It's a digit - parse width (single digit for simplicity)
        SUBB    #'0'
        STAB    _sprintf_width
        LDX     _sprintf_fmt
        LDAB    0,X
        INX
        STX     _sprintf_fmt

_sprintf_specifier:
        ; B contains the format specifier
        ; Get next argument
        LDAA    _sprintf_argidx
        CMPA    #4
        BHS     _sprintf_loop   ; No more args

        ; Calculate argument address: _sprintf_args + argidx*2
        PSHB                    ; Save format specifier (in B)
        ASLA                    ; argidx * 2 (result in A)
        TAB                     ; Move offset to B for ABX
        LDX     #_sprintf_args
        ABX                     ; X = _sprintf_args + offset
        LDD     0,X             ; D = argument value
        STD     _sprintf_arg    ; Save current argument
        PULB                    ; Restore format specifier

        INC     _sprintf_argidx ; Next argument

        ; Dispatch on specifier
        CMPB    #'d'
        BEQ     _sprintf_int
        CMPB    #'u'
        BEQ     _sprintf_uint
        CMPB    #'x'
        BEQ     _sprintf_hex
        CMPB    #'c'
        BEQ     _sprintf_char
        CMPB    #'s'
        BEQ     _sprintf_string
        ; Unknown specifier - skip
        BRA     _sprintf_loop

_sprintf_int:
        ; Signed decimal
        LDD     _sprintf_arg
        LDX     #_sprintf_tmp
        JSR     _itoa_internal  ; Convert to string
        BRA     _sprintf_output_str

_sprintf_uint:
        ; Unsigned decimal - use same as signed for simplicity
        ; (proper unsigned would need separate routine)
        LDD     _sprintf_arg
        BPL     _sprintf_int    ; If positive, same as signed
        ; Handle negative as large positive... actually just use signed
        BRA     _sprintf_int

_sprintf_hex:
        ; Hexadecimal
        LDD     _sprintf_arg
        BSR     _sprintf_tohex
        BRA     _sprintf_output_str

_sprintf_char:
        ; Single character
        LDAB    _sprintf_arg+1  ; Low byte of argument
        BSR     _sprintf_putc
        BRA     _sprintf_loop

_sprintf_string:
        ; String pointer
        LDX     _sprintf_arg    ; X = string pointer
_sprintf_str_loop:
        LDAB    0,X
        BEQ     _sprintf_loop   ; End of string
        PSHX
        BSR     _sprintf_putc
        PULX
        INX
        BRA     _sprintf_str_loop

_sprintf_output_str:
        ; Output string from _sprintf_tmp with width/padding
        ; For simplicity, just output without padding for now
        LDX     #_sprintf_tmp
_sprintf_out_loop:
        LDAB    0,X
        BEQ     _sprintf_loop
        PSHX
        BSR     _sprintf_putc
        PULX
        INX
        BRA     _sprintf_out_loop

_sprintf_done:
        ; Add null terminator
        LDX     _sprintf_ptr
        CLR     0,X

        ; Return character count
        LDD     _sprintf_count
        PULX
        RTS

; --- Helper: Output one character ---
_sprintf_putc:
        ; B = character to output
        LDX     _sprintf_ptr
        STAB    0,X
        INX
        STX     _sprintf_ptr
        ; Increment count
        LDD     _sprintf_count
        ADDD    #1
        STD     _sprintf_count
        RTS

; --- Helper: Convert D to hex string in _sprintf_tmp ---
_sprintf_tohex:
        STD     _sprintf_val
        LDX     #_sprintf_tmp

        ; High byte, high nibble
        LDAA    _sprintf_val
        LSRA
        LSRA
        LSRA
        LSRA
        BSR     _sprintf_hexdig
        STAB    0,X
        INX

        ; High byte, low nibble
        LDAA    _sprintf_val
        ANDA    #$0F
        BSR     _sprintf_hexdig
        STAB    0,X
        INX

        ; Low byte, high nibble
        LDAA    _sprintf_val+1
        LSRA
        LSRA
        LSRA
        LSRA
        BSR     _sprintf_hexdig
        STAB    0,X
        INX

        ; Low byte, low nibble
        LDAA    _sprintf_val+1
        ANDA    #$0F
        BSR     _sprintf_hexdig
        STAB    0,X
        INX

        ; Null terminate
        CLR     0,X
        RTS

; --- Helper: Convert nibble in A to hex digit in B ---
_sprintf_hexdig:
        TAB
        CMPB    #10
        BLO     _sprintf_hexdig_num
        ADDB    #('a'-10)       ; a-f
        RTS
_sprintf_hexdig_num:
        ADDB    #'0'            ; 0-9
        RTS

; --- Internal itoa (simpler version for sprintf) ---
; Input: D = value, X = buffer
; Output: string in buffer
_itoa_internal:
        STX     _itoa_int_buf   ; Save buffer pointer (will be updated)
        STX     _itoa_int_start ; Save original start for reversal
        STD     _itoa_int_val

        ; Handle sign
        CLR     _itoa_int_neg
        TSTA
        BPL     _itoa_int_pos
        COM     _itoa_int_neg
        COMA
        COMB
        ADDD    #1
        STD     _itoa_int_val

_itoa_int_pos:
        ; Handle zero special case
        LDD     _itoa_int_val
        TSTB
        BNE     _itoa_int_loop
        TSTA
        BNE     _itoa_int_loop
        ; Value is 0
        LDX     _itoa_int_buf
        LDAB    #'0'
        STAB    0,X
        INX
        BRA     _itoa_int_sign

_itoa_int_loop:
        LDD     _itoa_int_val
        TSTB
        BNE     _itoa_int_div
        TSTA
        BEQ     _itoa_int_sign

_itoa_int_div:
        LDX     #10
        JSR     __udiv16        ; D = D/10, __div16_rem = D%10
        STD     _itoa_int_val

        LDD     __div16_rem
        ADDB    #'0'
        LDX     _itoa_int_buf
        STAB    0,X
        INX
        STX     _itoa_int_buf

        BRA     _itoa_int_loop

_itoa_int_sign:
        TST     _itoa_int_neg
        BEQ     _itoa_int_term
        LDX     _itoa_int_buf
        LDAB    #'-'
        STAB    0,X
        INX
        STX     _itoa_int_buf

_itoa_int_term:
        ; Null terminate
        LDX     _itoa_int_buf
        CLR     0,X

        ; Reverse string in place
        ; End pointer = current position - 1 (last char before null)
        LDX     _itoa_int_buf
        DEX                     ; Back up one char (to last digit)
        STX     _itoa_int_end

        ; Start pointer = original buffer start (saved at function entry)
        LDX     _itoa_int_start

_itoa_int_rev:
        CPX     _itoa_int_end   ; Compare start with end
        BHS     _itoa_int_done  ; If start >= end, done

        ; Swap characters at start and end
        LDAA    0,X             ; A = *start
        PSHX                    ; Save start pointer
        LDX     _itoa_int_end   ; X = end
        LDAB    0,X             ; B = *end
        STAA    0,X             ; *end = A (former *start)
        PULX                    ; Restore start pointer
        STAB    0,X             ; *start = B (former *end)

        ; Move pointers inward
        INX                     ; start++
        PSHX
        LDX     _itoa_int_end
        DEX                     ; end--
        STX     _itoa_int_end
        PULX

        BRA     _itoa_int_rev

_itoa_int_done:
        RTS

; --- Local storage for _sprintf ---
_sprintf_buf:   RMB     2       ; Original buffer pointer
_sprintf_ptr:   RMB     2       ; Current write position
_sprintf_fmt:   RMB     2       ; Current format position
_sprintf_args:  RMB     8       ; 4 arguments (2 bytes each)
_sprintf_argidx: RMB    1       ; Current argument index
_sprintf_count: RMB     2       ; Character count
_sprintf_arg:   RMB     2       ; Current argument value
_sprintf_width: RMB     1       ; Width specifier
_sprintf_flags: RMB     1       ; Flags (bit 0=left, bit 1=zero)
_sprintf_tmp:   RMB     12      ; Temporary conversion buffer
_sprintf_val:   RMB     2       ; Value being converted

; --- Local storage for _itoa_internal ---
_itoa_int_buf:  RMB     2       ; Current write position
_itoa_int_start: RMB    2       ; Original buffer start (for reversal)
_itoa_int_end:  RMB     2       ; End pointer (for reversal)
_itoa_int_val:  RMB     2       ; Value being converted
_itoa_int_neg:  RMB     1       ; Negative flag

; -----------------------------------------------------------------------------
; _sprintf0 - sprintf with 0 arguments
; -----------------------------------------------------------------------------
; Push args in reverse order (right-to-left): a4, a3, a2, a1, fmt, buf
_sprintf0:
        PSHX
        TSX
        LDD     #0
        PSHB
        PSHA                    ; a4 = 0
        PSHB
        PSHA                    ; a3 = 0
        PSHB
        PSHA                    ; a2 = 0
        PSHB
        PSHA                    ; a1 = 0
        LDD     6,X             ; fmt
        PSHB
        PSHA
        LDD     4,X             ; buf
        PSHB
        PSHA
        JSR     _sprintf
        ; Clean up 12 bytes (buf, fmt, a1-a4)
        LDX     #12
_sprintf0_clean:
        INS
        DEX
        BNE     _sprintf0_clean
        PULX
        RTS

; -----------------------------------------------------------------------------
; _sprintf1 - sprintf with 1 argument
; -----------------------------------------------------------------------------
; Push args in reverse order (right-to-left): a4, a3, a2, a1, fmt, buf
_sprintf1:
        PSHX
        TSX
        LDD     #0
        PSHB
        PSHA                    ; a4 = 0
        PSHB
        PSHA                    ; a3 = 0
        PSHB
        PSHA                    ; a2 = 0
        LDD     8,X             ; a1
        PSHB
        PSHA
        LDD     6,X             ; fmt
        PSHB
        PSHA
        LDD     4,X             ; buf
        PSHB
        PSHA
        JSR     _sprintf
        LDX     #12
_sprintf1_clean:
        INS
        DEX
        BNE     _sprintf1_clean
        PULX
        RTS

; -----------------------------------------------------------------------------
; _sprintf2 - sprintf with 2 arguments
; -----------------------------------------------------------------------------
; Push args in reverse order (right-to-left): a4, a3, a2, a1, fmt, buf
_sprintf2:
        PSHX
        TSX
        LDD     #0
        PSHB
        PSHA                    ; a4 = 0
        PSHB
        PSHA                    ; a3 = 0
        LDD     10,X            ; a2
        PSHB
        PSHA
        LDD     8,X             ; a1
        PSHB
        PSHA
        LDD     6,X             ; fmt
        PSHB
        PSHA
        LDD     4,X             ; buf
        PSHB
        PSHA
        JSR     _sprintf
        LDX     #12
_sprintf2_clean:
        INS
        DEX
        BNE     _sprintf2_clean
        PULX
        RTS

; -----------------------------------------------------------------------------
; _sprintf3 - sprintf with 3 arguments
; -----------------------------------------------------------------------------
; Push args in reverse order (right-to-left): a4, a3, a2, a1, fmt, buf
_sprintf3:
        PSHX
        TSX
        LDD     #0
        PSHB
        PSHA                    ; a4 = 0
        LDD     12,X            ; a3
        PSHB
        PSHA
        LDD     10,X            ; a2
        PSHB
        PSHA
        LDD     8,X             ; a1
        PSHB
        PSHA
        LDD     6,X             ; fmt
        PSHB
        PSHA
        LDD     4,X             ; buf
        PSHB
        PSHA
        JSR     _sprintf
        LDX     #12
_sprintf3_clean:
        INS
        DEX
        BNE     _sprintf3_clean
        PULX
        RTS

; =============================================================================
; End of STDIO.INC
; =============================================================================
