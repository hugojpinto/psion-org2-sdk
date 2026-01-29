; =============================================================================
; DBRUNTIME.INC - Database and File Access Runtime for Psion Organiser II
; =============================================================================
;
; This file provides the assembly runtime for the database API (db.h).
; It wraps Psion OS FL$ file services to provide a C-friendly database
; interface with schema-based named field access.
;
; INCLUDE ORDER:
;   INCLUDE "psion.inc"         ; Core definitions (syscalls, sysvars)
;   INCLUDE "runtime.inc"       ; Core C runtime (required - provides atoi, itoa, etc.)
;   INCLUDE "dbruntime.inc"     ; This file (optional, include last)
;
; CODE SIZE:
;   Including this file adds approximately 1200-1600 bytes of code plus
;   ~300 bytes of static data buffers to your program.
;
; =============================================================================
; FOR C PROGRAMMERS:
; =============================================================================
;   See db.h for C function declarations. The implementations here are
;   called by the C runtime. All functions follow the Small-C calling
;   convention: arguments on stack (right-to-left), return in D register.
;
; =============================================================================
; FOR ASSEMBLY PROGRAMMERS:
; =============================================================================
;   This file provides both function implementations AND convenience macros.
;
;   FUNCTIONS (call via JSR after pushing args to stack):
;     _db_create    : Create new database file
;     _db_open      : Open existing database file
;     _db_close     : Close database file
;     _db_error     : Get last error code
;     _db_clear     : Clear record buffer
;     _db_set_str   : Set string field by name
;     _db_set_int   : Set integer field by name
;     _db_set_idx   : Set field by index (string)
;     _db_set_int_idx : Set integer field by index
;     _db_append    : Write record to file
;     _db_read      : Read current record
;     _db_get_str   : Get string field by name
;     _db_get_int   : Get integer field by name
;     _db_get_idx   : Get field by index (string)
;     _db_get_int_idx : Get integer field by index
;     _db_field_count : Get field count in current record
;     _db_recsize   : Get current record size
;     _db_first     : Move to first record
;     _db_next      : Move to next record
;     _db_back      : Move to previous record
;     _db_find      : Find record containing string
;     _db_eof       : Check end-of-file
;     _db_count     : Get total record count
;     _db_pos       : Get current record position
;     _db_update    : Replace current record
;     _db_erase     : Delete current record
;
;   MACROS (expand inline, simpler to use from assembly):
;     DB_CREATE device, name_addr, schema_addr
;     DB_OPEN   device, name_addr, schema_addr
;     DB_CLOSE
;     DB_CLEAR
;     DB_SET_IDX index, value_addr
;     DB_APPEND
;     DB_READ
;     DB_GET_IDX index, buffer_addr, maxlen
;     DB_FIRST
;     DB_NEXT
;     DB_BACK
;     DB_EOF
;
;   STACK ARGUMENT ORDER:
;     Arguments are pushed RIGHT-TO-LEFT (C calling convention).
;     First argument ends up at lowest address (highest offset from SP).
;
;   Example using function directly:
;     ; Create a database: db_create('B', "DATA", "$,$,%")
;     LDD     #_my_schema     ; schema (arg 3, pushed first)
;     PSHB
;     PSHA
;     LDD     #_my_filename   ; name (arg 2)
;     PSHB
;     PSHA
;     LDD     #'B'            ; device (arg 1)
;     PSHB
;     PSHA
;     JSR     _db_create
;     INS                     ; Clean up 6 bytes
;     INS
;     INS
;     INS
;     INS
;     INS
;     ; D = handle (0 or -1)
;
; CALLING CONVENTION:
;   All functions follow the Small-C calling convention:
;   - Arguments on stack (right-to-left push order)
;   - Return value in D register (A:B for 16-bit)
;   - Caller cleans up stack
;   - X register preserved across calls (via PSHX/PULX)
;
; PSION OS FILE SERVICES USED:
;   FL_SETP ($35) - Select pack/device for file operations
;   FL_CRET ($28) - Create new data file
;   FL_OPEN ($2F) - Open existing data file
;   FL_WRIT ($37) - Write/append record (X=data, B=length)
;   FL_READ ($31) - Read current record (returns X=data, B=length)
;   FL_NEXT ($2E) - Advance to next record (carry=EOF)
;   FL_BACK ($21) - Move to previous record (carry=BOF)
;   FL_FIND ($2C) - Find record containing string
;   FL_ERAS ($2A) - Erase current record
;   FL_FREC ($2D) - Get record info
;   FL_RSET ($34) - Reset to record position
;   FL_DELN ($29) - Delete file by name
;
; Author: Hugo José Pinto & Contributors
; Part of the Psion Organiser II SDK
; See: specs/11-database-file-access.md
; =============================================================================

; =============================================================================
; CONSTANTS
; =============================================================================

DB_MAX_REC      EQU     254     ; Maximum record size in bytes
DB_MAX_FLDS     EQU     16      ; Maximum fields per record
DB_TAB          EQU     $09     ; TAB delimiter between fields

; Error codes (must match db.h)
DB_OK           EQU     0
DB_E_NFND       EQU     1       ; Not found
DB_E_EXST       EQU     2       ; Already exists
DB_E_FULL       EQU     3       ; Pack/record full
DB_E_IO         EQU     4       ; I/O error
DB_E_INV        EQU     5       ; Invalid parameter
DB_E_NOPN       EQU     6       ; No file open
DB_E_ALRD       EQU     7       ; File already open
DB_E_EOF        EQU     8       ; End of file
DB_E_OVFL       EQU     9       ; Record overflow
DB_E_TYPE       EQU     10      ; Type mismatch
DB_E_FLD        EQU     11      ; Invalid field

; File state flags
DB_FL_OPEN      EQU     $01     ; File is open
DB_FL_SCHEMA    EQU     $02     ; Schema is defined

; =============================================================================
; ASSEMBLY CONVENIENCE MACROS
; =============================================================================
; These macros simplify calling database functions from assembly code.
; They handle the stack setup and cleanup automatically.
;
; IMPORTANT: All macros leave the result in D register.
;            Macros may clobber A, B, and flags.

; -----------------------------------------------------------------------------
; DB_CREATE - Create a new database file
; -----------------------------------------------------------------------------
; Usage: DB_CREATE device_char, name_addr, schema_addr
;   device_char = 'A', 'B', or 'C'
;   name_addr   = address of null-terminated filename
;   schema_addr = address of schema string (or #0 for raw)
; Output: D = handle (0 or -1)
; -----------------------------------------------------------------------------
MACRO DB_CREATE, device_char, name_addr, schema_addr
    LDD     #\schema_addr
    PSHB
    PSHA
    LDD     #\name_addr
    PSHB
    PSHA
    LDD     #\device_char
    PSHB
    PSHA
    JSR     _db_create
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; DB_OPEN - Open an existing database file
; -----------------------------------------------------------------------------
; Usage: DB_OPEN device_char, name_addr, schema_addr
; Output: D = handle (0 or -1)
; -----------------------------------------------------------------------------
MACRO DB_OPEN, device_char, name_addr, schema_addr
    LDD     #\schema_addr
    PSHB
    PSHA
    LDD     #\name_addr
    PSHB
    PSHA
    LDD     #\device_char
    PSHB
    PSHA
    JSR     _db_open
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; DB_CLOSE - Close the database file
; -----------------------------------------------------------------------------
; Usage: DB_CLOSE
; -----------------------------------------------------------------------------
MACRO DB_CLOSE
    LDD     #0
    PSHB
    PSHA
    JSR     _db_close
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; DB_CLEAR - Clear the record buffer
; -----------------------------------------------------------------------------
; Usage: DB_CLEAR
; -----------------------------------------------------------------------------
MACRO DB_CLEAR
    JSR     _db_clear
ENDM

; -----------------------------------------------------------------------------
; DB_SET_IDX - Set a field by index
; -----------------------------------------------------------------------------
; Usage: DB_SET_IDX index, value_addr
;   index      = field index (1-based, immediate value)
;   value_addr = address of null-terminated string value
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
MACRO DB_SET_IDX, index, value_addr
    LDD     #\value_addr
    PSHB
    PSHA
    LDD     #\index
    PSHB
    PSHA
    JSR     _db_set_idx
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; DB_APPEND - Append the record buffer to file
; -----------------------------------------------------------------------------
; Usage: DB_APPEND
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
MACRO DB_APPEND
    JSR     _db_append
ENDM

; -----------------------------------------------------------------------------
; DB_READ - Read current record into buffer
; -----------------------------------------------------------------------------
; Usage: DB_READ
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
MACRO DB_READ
    JSR     _db_read
ENDM

; -----------------------------------------------------------------------------
; DB_GET_IDX - Get a field by index as string
; -----------------------------------------------------------------------------
; Usage: DB_GET_IDX index, buffer_addr, maxlen
;   index       = field index (1-based)
;   buffer_addr = address of destination buffer
;   maxlen      = maximum bytes including null terminator
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
MACRO DB_GET_IDX, index, buffer_addr, maxlen
    LDD     #\maxlen
    PSHB
    PSHA
    LDD     #\buffer_addr
    PSHB
    PSHA
    LDD     #\index
    PSHB
    PSHA
    JSR     _db_get_idx
    INS
    INS
    INS
    INS
    INS
    INS
ENDM

; -----------------------------------------------------------------------------
; DB_FIRST - Move to first record
; -----------------------------------------------------------------------------
MACRO DB_FIRST
    JSR     _db_first
ENDM

; -----------------------------------------------------------------------------
; DB_NEXT - Move to next record
; -----------------------------------------------------------------------------
MACRO DB_NEXT
    JSR     _db_next
ENDM

; -----------------------------------------------------------------------------
; DB_BACK - Move to previous record
; -----------------------------------------------------------------------------
MACRO DB_BACK
    JSR     _db_back
ENDM

; -----------------------------------------------------------------------------
; DB_EOF - Check end-of-file flag
; -----------------------------------------------------------------------------
; Output: D = 1 if EOF, 0 otherwise
MACRO DB_EOF
    JSR     _db_eof
ENDM

; =============================================================================
; C API ENTRY POINTS (jump table)
; =============================================================================
; The Small-C code generator emits calls with single underscore prefixes
; (e.g., JSR _db_create). These jump to the double-underscore implementations.
; This indirection allows the jump table to be at the start of the file,
; providing a stable entry point regardless of implementation changes.
; =============================================================================

_db_create:     JMP     __db_create
_db_open:       JMP     __db_open
_db_close:      JMP     __db_close
_db_error:      JMP     __db_error
_db_clear:      JMP     __db_clear
_db_set_str:    JMP     __db_set_str
_db_set_int:    JMP     __db_set_int
_db_set_idx:    JMP     __db_set_idx
_db_set_int_idx: JMP    __db_set_int_idx
_db_append:     JMP     __db_append
_db_read:       JMP     __db_read
_db_get_str:    JMP     __db_get_str
_db_get_int:    JMP     __db_get_int
_db_get_idx:    JMP     __db_get_idx
_db_get_int_idx: JMP    __db_get_int_idx
_db_field_count: JMP    __db_field_count
_db_recsize:    JMP     __db_recsize
_db_first:      JMP     __db_first
_db_next:       JMP     __db_next
_db_back:       JMP     __db_back
_db_find:       JMP     __db_find
_db_eof:        JMP     __db_eof
_db_count:      JMP     __db_count
_db_pos:        JMP     __db_pos
_db_update:     JMP     __db_update
_db_erase:      JMP     __db_erase

; =============================================================================
; STACK LAYOUT REFERENCE
; =============================================================================
; These diagrams show the stack layout after PSHX+TSX in each function.
; Offsets are from X register after TSX.
;
; _db_create(device, name, schema):
;   Stack: [saved_X 2B][ret 2B][device 2B][name 2B][schema 2B]
;   Offsets: X+0=saved_X, X+2=ret, X+4=device(low byte at X+5),
;            X+6=name, X+8=schema
;
; _db_open(device, name, schema):
;   Same layout as _db_create
;
; _db_close(handle):
;   Stack: [saved_X 2B][ret 2B][handle 2B]
;   Offsets: X+4=handle
;
; _db_set_str(name, value):
;   Stack: [saved_X 2B][ret 2B][name 2B][value 2B]
;   Offsets: X+4=name, X+6=value
;
; _db_set_int(name, value):
;   Stack: [saved_X 2B][ret 2B][name 2B][value 2B]
;   Offsets: X+4=name, X+6=value
;
; _db_set_idx(index, value):
;   Stack: [saved_X 2B][ret 2B][index 2B][value 2B]
;   Offsets: X+4=index(low at X+5), X+6=value
;
; _db_set_int_idx(index, value):
;   Stack: [saved_X 2B][ret 2B][index 2B][value 2B]
;   Offsets: X+4=index, X+6=value
;
; _db_get_str(name, buffer, maxlen):
;   Stack: [saved_X 2B][ret 2B][name 2B][buffer 2B][maxlen 2B]
;   Offsets: X+4=name, X+6=buffer, X+8=maxlen
;
; _db_get_idx(index, buffer, maxlen):
;   Stack: [saved_X 2B][ret 2B][index 2B][buffer 2B][maxlen 2B]
;   Offsets: X+4=index, X+6=buffer, X+8=maxlen
;
; _db_find(pattern):
;   Stack: [saved_X 2B][ret 2B][pattern 2B]
;   Offsets: X+4=pattern
;
; =============================================================================

; =============================================================================
; INTERNAL STATE (static data)
; =============================================================================

; --- File state ---
_db_flags:      RMB     1       ; State flags (DB_FL_OPEN, DB_FL_SCHEMA)
_db_device:     RMB     1       ; Device letter ('A', 'B', 'C')
_db_schema_ptr: RMB     2       ; Pointer to schema string (in program data)
_db_fld_cnt:    RMB     1       ; Number of fields defined in schema
_db_last_err:   RMB     1       ; Last error code (DB_OK..DB_E_FLD)
_db_eof_flg:    RMB     1       ; EOF flag (0=not EOF, 1=EOF)
_db_rec_pos:    RMB     2       ; Current record position (1-based, 0=none)

; --- Record buffer (shared for building and reading) ---
_db_rec_buf:    RMB     DB_MAX_REC  ; 254-byte record buffer
_db_rec_len:    RMB     1       ; Current record length (0-254)

; --- Record building state ---
_db_bld_pos:    RMB     1       ; Write position in record buffer during build
_db_bld_fcnt:   RMB     1       ; Fields written so far during build

; --- Record reading/parsing state ---
; After db_read, these arrays hold the offset and length of each field
; within _db_rec_buf. Used by db_get_idx to extract fields.
_db_fld_off:    RMB     DB_MAX_FLDS ; Byte offset of each field (0-253)
_db_fld_len:    RMB     DB_MAX_FLDS ; Length of each field (0-253)
_db_rd_fcnt:    RMB     1       ; Number of fields parsed from last read

; --- LBC filename buffer ---
; Used to build LBC (Leading Byte Count) strings for FL$ services.
; Format: [length_byte][chars...] (no null terminator needed by OS)
; Maximum: 1 (length) + 8 (filename) = 9 bytes
_db_lbc_buf:    RMB     10      ; LBC filename buffer

; --- Temporary integer conversion buffer ---
; Used by db_set_int / db_set_int_idx to convert int to string.
; Holds the result of itoa (max "-32768\0" = 7 bytes).
_db_int_buf:    RMB     8       ; Integer-to-string conversion buffer

; --- Field lookup temporaries ---
_db_fld_tmp:    RMB     2       ; Temporary for field lookup
_db_fld_idx:    RMB     1       ; Field index result from lookup

; =============================================================================
; HELPER SUBROUTINES (internal, not called from C)
; =============================================================================

; -----------------------------------------------------------------------------
; __db_set_err - Set the last error code and return it in D
; -----------------------------------------------------------------------------
; Input:  B = error code
; Output: D = error code (A=0, B=error), _db_last_err set
; Clobbers: A
; -----------------------------------------------------------------------------
__db_set_err:
        STAB    _db_last_err
        CLRA                    ; D = 0:error_code (sign-extended)
        RTS

; -----------------------------------------------------------------------------
; __db_chk_open - Check if a file is open
; -----------------------------------------------------------------------------
; Output: Carry clear = file is open, Carry set = not open
;         If not open, _db_last_err is set to DB_E_NOPN
; Clobbers: A, B
; -----------------------------------------------------------------------------
__db_chk_open:
        LDAA    _db_flags
        BITA    #DB_FL_OPEN
        BNE     __db_chk_open_ok
        ; Not open
        LDAB    #DB_E_NOPN
        BSR     __db_set_err
        SEC                     ; Set carry = error
        RTS
__db_chk_open_ok:
        CLC                     ; Clear carry = OK
        RTS

; -----------------------------------------------------------------------------
; __db_make_lbc - Build LBC filename string from null-terminated name
; -----------------------------------------------------------------------------
; Builds an LBC (Leading Byte Count) string in _db_lbc_buf from a
; null-terminated filename. The LBC format is: [length][chars...]
;
; Input:  X = pointer to null-terminated filename
; Output: _db_lbc_buf contains the LBC string
;         X = address of _db_lbc_buf (for passing to FL$ services)
;         B = length of filename
; Clobbers: A, B
; -----------------------------------------------------------------------------
__db_make_lbc:
        STX     _db_mlbc_src    ; Save source pointer

        ; Count length of source string
        CLRB                    ; B = length counter
__db_mlbc_cnt:
        LDAA    0,X
        BEQ     __db_mlbc_copy  ; Reached null terminator
        INX
        INCB
        CMPB    #8              ; Max 8 chars
        BLO     __db_mlbc_cnt

__db_mlbc_copy:
        ; B = length, store as first byte of LBC
        STAB    _db_lbc_buf

        ; Copy chars from source to _db_lbc_buf+1
        LDX     _db_mlbc_src
        STAB    _db_mlbc_len    ; Save length
        LDAB    #0              ; Offset counter
__db_mlbc_cp:
        CMPB    _db_mlbc_len
        BEQ     __db_mlbc_done
        LDAA    0,X             ; Get source char
        INX
        PSHX                    ; Save source
        LDX     #_db_lbc_buf
        INCB                    ; Offset + 1 (skip length byte)
        ABX
        STAA    0,X             ; Store in LBC buffer
        DECB                    ; Restore offset counter
        INCB                    ; Advance offset
        PULX                    ; Restore source
        BRA     __db_mlbc_cp

__db_mlbc_done:
        LDAB    _db_mlbc_len
        LDX     #_db_lbc_buf    ; Return buffer address in X
        RTS

; --- Temporaries for __db_make_lbc ---
_db_mlbc_src:   RMB     2       ; Source string pointer
_db_mlbc_len:   RMB     1       ; String length

; -----------------------------------------------------------------------------
; __db_sel_dev - Select device/pack for FL$ operations
; -----------------------------------------------------------------------------
; Calls FL_SETP to select the pack corresponding to the device letter.
;
; Input:  B = device letter ('A', 'B', 'C')
; Output: Carry clear = success, Carry set = error
; Clobbers: A, B
; -----------------------------------------------------------------------------
__db_sel_dev:
        ; Convert device letter to pack index: 'A'=0, 'B'=1, 'C'=2
        SUBB    #'A'            ; B = 0, 1, or 2
        SWI
        FCB     FL_SETP         ; Select pack
        RTS                     ; Carry flag from FL_SETP

; -----------------------------------------------------------------------------
; __db_find_field - Find a field by name in the schema string
; -----------------------------------------------------------------------------
; Walks the schema string (e.g., "name$,phone$,age%") to find the field
; whose name matches the given search name. Returns the 1-based field
; index and the field type character.
;
; Schema format: field definitions separated by commas.
;   Each field: [name_chars...][type_suffix]
;   type_suffix: '$' (string), '%' (integer)
;   Example: "name$,phone$,age%" -> field 1="name"($), 2="phone"($), 3="age"(%)
;
; Input:  X = pointer to search name (null-terminated)
;         _db_schema_ptr = pointer to schema string
; Output: B = field index (1-based), or 0 if not found
;         A = type character ('$', '%'), or 0 if not found
;         _db_fld_idx = field index (same as B)
; Clobbers: A, B, X
; -----------------------------------------------------------------------------
__db_find_field:
        STX     _dbff_search    ; Save search name pointer

        ; Check if schema exists
        LDD     _db_schema_ptr
        BNE     __dbff_start
        ; No schema - return not found
        CLRB
        CLRA
        STAB    _db_fld_idx
        RTS

__dbff_start:
        LDX     _db_schema_ptr
        STX     _dbff_pos       ; Current position in schema
        LDAB    #1
        STAB    _dbff_fidx      ; Start at field 1

__dbff_field:
        ; Mark start of current field name
        LDX     _dbff_pos
        STX     _dbff_name_start

        ; Scan to type suffix or comma or end
__dbff_scan:
        LDX     _dbff_pos
        LDAA    0,X
        BEQ     __dbff_not_found ; End of schema string

        ; Check for type suffix characters
        CMPA    #'$'
        BEQ     __dbff_found_type
        CMPA    #'%'
        BEQ     __dbff_found_type

        ; Not a type suffix, advance
        INX
        STX     _dbff_pos
        BRA     __dbff_scan

__dbff_found_type:
        ; A = type character ('$' or '%')
        STAA    _dbff_type

        ; Calculate field name length: pos - name_start
        LDD     _dbff_pos
        SUBD    _dbff_name_start
        STD     _dbff_nlen      ; Name length (16-bit, but always < 9)

        ; If name length is 0, this is a nameless field (e.g., "$,$,%")
        ; - skip comparison, not a match for named lookup
        TSTB
        BEQ     __dbff_next_field

        ; Compare search name with this field name
        ; search name is at _dbff_search (null-terminated)
        ; field name is at _dbff_name_start, length in _dbff_nlen low byte
        LDX     _dbff_search
        STX     _dbff_cmp_s     ; Search pointer
        LDX     _dbff_name_start
        STX     _dbff_cmp_f     ; Field pointer
        LDAB    _dbff_nlen+1    ; B = name length (low byte)
        STAB    _dbff_cmp_cnt   ; Compare counter

__dbff_cmp_loop:
        TST     _dbff_cmp_cnt
        BEQ     __dbff_cmp_end_check ; All name chars compared

        LDX     _dbff_cmp_s
        LDAA    0,X             ; A = search char
        BEQ     __dbff_next_field ; Search name shorter -> no match

        LDX     _dbff_cmp_f
        LDAB    0,X             ; B = field char

        CBA                     ; Compare A and B
        BNE     __dbff_next_field ; Mismatch

        ; Characters match, advance
        LDX     _dbff_cmp_s
        INX
        STX     _dbff_cmp_s
        LDX     _dbff_cmp_f
        INX
        STX     _dbff_cmp_f
        DEC     _dbff_cmp_cnt
        BRA     __dbff_cmp_loop

__dbff_cmp_end_check:
        ; All field name chars matched. Check that search name is also
        ; at its end (null terminator), otherwise "na" would match "name".
        LDX     _dbff_cmp_s
        TST     0,X
        BNE     __dbff_next_field ; Search name longer -> no match

        ; MATCH FOUND!
        LDAB    _dbff_fidx      ; B = field index (1-based)
        STAB    _db_fld_idx
        LDAA    _dbff_type      ; A = type character
        RTS

__dbff_next_field:
        ; Advance past the type suffix
        LDX     _dbff_pos
        INX                     ; Skip type suffix character
        STX     _dbff_pos

        ; Check for comma separator
        LDAA    0,X
        CMPA    #','
        BNE     __dbff_chk_end
        INX                     ; Skip comma
        STX     _dbff_pos

__dbff_chk_end:
        ; Check for end of schema
        LDX     _dbff_pos
        TST     0,X
        BEQ     __dbff_not_found

        INC     _dbff_fidx      ; Next field index
        BRA     __dbff_field

__dbff_not_found:
        CLRB                    ; B = 0 (not found)
        CLRA                    ; A = 0
        CLR     _db_fld_idx
        RTS

; --- Temporaries for __db_find_field ---
_dbff_search:   RMB     2       ; Search name pointer
_dbff_pos:      RMB     2       ; Current position in schema
_dbff_name_start: RMB   2       ; Start of current field name
_dbff_fidx:     RMB     1       ; Current field index (1-based)
_dbff_type:     RMB     1       ; Type character found
_dbff_nlen:     RMB     2       ; Field name length (16-bit)
_dbff_cmp_s:    RMB     2       ; Search compare pointer
_dbff_cmp_f:    RMB     2       ; Field compare pointer
_dbff_cmp_cnt:  RMB     1       ; Compare counter

; -----------------------------------------------------------------------------
; __db_count_schema - Count fields in schema string
; -----------------------------------------------------------------------------
; Input:  X = pointer to schema string (or 0 for none)
; Output: B = field count (0 if no schema)
; Clobbers: A, B
; -----------------------------------------------------------------------------
__db_count_schema:
        ; If X is null (0), return 0
        CPX     #0
        BNE     __dbcs_count
        CLRB
        RTS

__dbcs_count:
        CLRB                    ; B = field counter
__dbcs_loop:
        LDAA    0,X
        BEQ     __dbcs_done     ; End of string

        ; Check for type suffix (marks end of a field definition)
        CMPA    #'$'
        BEQ     __dbcs_found
        CMPA    #'%'
        BEQ     __dbcs_found

        INX
        BRA     __dbcs_loop

__dbcs_found:
        INCB                    ; Found a field
        INX                     ; Skip type suffix
        LDAA    0,X
        CMPA    #','
        BNE     __dbcs_chk_end
        INX                     ; Skip comma
__dbcs_chk_end:
        TST     0,X
        BNE     __dbcs_loop     ; More fields
__dbcs_done:
        RTS

; -----------------------------------------------------------------------------
; __db_parse_rec - Parse TAB-delimited record into field offsets
; -----------------------------------------------------------------------------
; Parses the data in _db_rec_buf (length in _db_rec_len) to find the
; start offset and length of each TAB-separated field.
;
; Input:  _db_rec_buf = record data, _db_rec_len = record length
; Output: _db_fld_off[] = byte offset of each field in _db_rec_buf
;         _db_fld_len[] = length of each field
;         _db_rd_fcnt = number of fields found
; Clobbers: A, B, X
; -----------------------------------------------------------------------------
__db_parse_rec:
        CLR     _db_rd_fcnt     ; Reset field count
        LDAB    _db_rec_len
        BEQ     __dbpr_done     ; Empty record -> 0 fields

        ; Initialize: first field starts at offset 0
        CLRA
        STAA    _db_fld_off     ; Field 0 offset = 0
        CLR     _dbpr_fidx      ; Current field index
        CLR     _dbpr_fstart    ; Current field start offset

        ; Walk through the record buffer
        LDX     #_db_rec_buf
        CLRB                    ; B = current byte offset

__dbpr_loop:
        CMPB    _db_rec_len
        BHS     __dbpr_last     ; Past end of record

        LDAA    0,X             ; A = current byte
        CMPA    #DB_TAB
        BEQ     __dbpr_tab

        ; Regular character, advance
        INX
        INCB
        BRA     __dbpr_loop

__dbpr_tab:
        ; Found TAB delimiter - close current field
        ; Field length = current_offset - field_start
        PSHB                    ; Save current offset
        SUBB    _dbpr_fstart    ; B = field length
        PSHX                    ; Save scan pointer

        ; Store field length in _db_fld_len[fidx]
        LDAA    _dbpr_fidx
        LDX     #_db_fld_len
        ABX                     ; Not right - we need fidx as index
        PULX                    ; Restore X (scan pointer)
        ; Redo: use fidx to index into _db_fld_len
        PSHX
        LDAA    _dbpr_fidx
        LDX     #_db_fld_len
        STAB    A,X             ; _db_fld_len[fidx] = field_length
        PULX                    ; Restore scan pointer

        PULB                    ; Restore current offset

        ; Advance to next field
        INC     _dbpr_fidx
        INX                     ; Skip TAB
        INCB                    ; Next offset

        ; Check field limit
        LDAA    _dbpr_fidx
        CMPA    #DB_MAX_FLDS
        BHS     __dbpr_last     ; Too many fields

        ; Store start of next field
        STAB    _dbpr_fstart
        PSHX
        LDX     #_db_fld_off
        STAB    A,X             ; _db_fld_off[fidx] = offset
        PULX

        BRA     __dbpr_loop

__dbpr_last:
        ; Close the last field (no trailing TAB)
        ; Length = rec_len - field_start
        LDAB    _db_rec_len
        SUBB    _dbpr_fstart
        LDAA    _dbpr_fidx
        PSHX
        LDX     #_db_fld_len
        STAB    A,X             ; _db_fld_len[fidx] = last field length
        PULX

        ; Field count = fidx + 1
        LDAB    _dbpr_fidx
        INCB
        STAB    _db_rd_fcnt

__dbpr_done:
        RTS

; --- Temporaries for __db_parse_rec ---
_dbpr_fidx:     RMB     1       ; Current field index during parse
_dbpr_fstart:   RMB     1       ; Start offset of current field

; =============================================================================
; FILE MANAGEMENT FUNCTIONS
; =============================================================================

; -----------------------------------------------------------------------------
; __db_create - Create a new database file
; -----------------------------------------------------------------------------
; C: int db_create(char device, char *name, char *schema)
;
; Input:  Stack: device (X+5 low byte), name (X+6), schema (X+8)
; Output: D = 0 (handle) on success, -1 on error
; -----------------------------------------------------------------------------
__db_create:
        PSHX
        TSX

        ; Check if a file is already open
        LDAA    _db_flags
        BITA    #DB_FL_OPEN
        BEQ     __dbc_proceed
        ; File already open
        LDAB    #DB_E_ALRD
        JSR     __db_set_err
        LDD     #-1
        PULX
        RTS

__dbc_proceed:
        ; Save device letter
        LDAB    5,X             ; B = device letter (low byte of arg 1)
        STAB    _db_device

        ; Save schema pointer
        LDD     8,X             ; D = schema pointer
        STD     _db_schema_ptr

        ; Count schema fields
        LDX     _db_schema_ptr
        JSR     __db_count_schema
        STAB    _db_fld_cnt     ; B = field count

        ; Select device
        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbc_err_io

        ; Build LBC filename
        TSX
        LDX     6,X             ; X = name pointer
        JSR     __db_make_lbc   ; X = _db_lbc_buf, B = length

        ; Call FL_CRET to create the file
        ; FL_CRET: B = record type, X = LBC filename
        ; For data files, record type is typically 0 or the default
        CLRB                    ; B = 0 (standard data file record type)
        SWI
        FCB     FL_CRET
        BCS     __dbc_err_io

        ; Success: mark file as open
        LDAB    #DB_FL_OPEN
        ; Check if schema was provided (non-null)
        LDD     _db_schema_ptr
        BEQ     __dbc_no_schema
        LDAB    #DB_FL_OPEN+DB_FL_SCHEMA
__dbc_no_schema:
        STAB    _db_flags

        ; Clear error, EOF flag, and record position
        CLR     _db_last_err
        CLR     _db_eof_flg
        LDD     #0
        STD     _db_rec_pos

        ; Return handle = 0
        LDD     #0
        PULX
        RTS

__dbc_err_io:
        LDAB    #DB_E_IO
        JSR     __db_set_err
        LDD     #-1
        PULX
        RTS

; -----------------------------------------------------------------------------
; __db_open - Open an existing database file
; -----------------------------------------------------------------------------
; C: int db_open(char device, char *name, char *schema)
;
; Input:  Stack: device (X+5 low byte), name (X+6), schema (X+8)
; Output: D = 0 (handle) on success, -1 on error
; -----------------------------------------------------------------------------
__db_open:
        PSHX
        TSX

        ; Check if a file is already open
        LDAA    _db_flags
        BITA    #DB_FL_OPEN
        BEQ     __dbo_proceed
        ; File already open
        LDAB    #DB_E_ALRD
        JSR     __db_set_err
        LDD     #-1
        PULX
        RTS

__dbo_proceed:
        ; Save device letter
        LDAB    5,X             ; B = device letter
        STAB    _db_device

        ; Save schema pointer
        LDD     8,X             ; D = schema pointer
        STD     _db_schema_ptr

        ; Count schema fields
        LDX     _db_schema_ptr
        JSR     __db_count_schema
        STAB    _db_fld_cnt

        ; Select device
        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbo_err_io

        ; Build LBC filename
        TSX
        LDX     6,X             ; X = name pointer
        JSR     __db_make_lbc

        ; Call FL_OPEN to open the file
        ; FL_OPEN: X = LBC filename
        SWI
        FCB     FL_OPEN
        BCS     __dbo_err_nfnd

        ; Success: mark file as open
        LDAB    #DB_FL_OPEN
        LDD     _db_schema_ptr
        BEQ     __dbo_no_schema
        LDAB    #DB_FL_OPEN+DB_FL_SCHEMA
__dbo_no_schema:
        STAB    _db_flags

        ; Clear error, EOF, position
        CLR     _db_last_err
        CLR     _db_eof_flg
        LDD     #0
        STD     _db_rec_pos

        ; Return handle = 0
        LDD     #0
        PULX
        RTS

__dbo_err_nfnd:
        LDAB    #DB_E_NFND
        JSR     __db_set_err
        LDD     #-1
        PULX
        RTS

__dbo_err_io:
        LDAB    #DB_E_IO
        JSR     __db_set_err
        LDD     #-1
        PULX
        RTS

; -----------------------------------------------------------------------------
; __db_close - Close the database file
; -----------------------------------------------------------------------------
; C: void db_close(int handle)
;
; Input:  Stack: handle (X+4) - ignored for now (single file)
; Output: None
; -----------------------------------------------------------------------------
__db_close:
        ; Simply clear state flags to mark file as closed.
        ; The Psion OS does not require an explicit close for data files;
        ; FL$ services operate statelessly on the current pack.
        CLR     _db_flags
        CLR     _db_last_err
        CLR     _db_eof_flg
        LDD     #0
        STD     _db_rec_pos
        STD     _db_schema_ptr
        RTS

; -----------------------------------------------------------------------------
; __db_error - Get last error code
; -----------------------------------------------------------------------------
; C: int db_error(void)
;
; Output: D = last error code
; -----------------------------------------------------------------------------
__db_error:
        CLRA
        LDAB    _db_last_err
        RTS

; =============================================================================
; RECORD BUILDING FUNCTIONS
; =============================================================================

; -----------------------------------------------------------------------------
; __db_clear - Clear the record buffer for building a new record
; -----------------------------------------------------------------------------
; C: void db_clear(void)
;
; Resets the record buffer position and field counter.
; Must be called before db_set_xxx() / db_append().
; -----------------------------------------------------------------------------
__db_clear:
        CLR     _db_bld_pos     ; Reset write position to 0
        CLR     _db_bld_fcnt    ; Reset field counter to 0
        CLR     _db_rec_len     ; Reset record length
        CLR     _db_last_err
        RTS

; -----------------------------------------------------------------------------
; __db_set_idx - Set a field by index (string value)
; -----------------------------------------------------------------------------
; C: int db_set_idx(int index, char *value)
;
; Appends the field value to the record buffer at the given index position.
; If index > fields_written + 1, intermediate empty fields are inserted.
; Fields are stored TAB-delimited in the buffer.
;
; Input:  Stack: index (X+4, 1-based), value (X+6, null-terminated string)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_set_idx:
        PSHX
        TSX

        ; Get arguments
        LDD     4,X             ; D = index
        STD     _dbsi_index
        LDD     6,X             ; D = value pointer
        STD     _dbsi_value

        ; Validate index (must be 1..DB_MAX_FLDS)
        LDD     _dbsi_index
        TSTB
        BEQ     __dbsi_err_field ; Index 0 is invalid
        CMPB    #DB_MAX_FLDS
        BHI     __dbsi_err_field ; Index > 16 is invalid

        ; Fill any skipped fields with empty strings (TABs)
        ; If index > bld_fcnt + 1, we need to insert empty fields
__dbsi_fill:
        LDAB    _db_bld_fcnt
        INCB                    ; B = next expected field index
        LDAA    _dbsi_index+1   ; A = target index (low byte)
        CBA                     ; Compare next expected with target
        BEQ     __dbsi_write    ; Target == next expected, write normally
        BHI     __dbsi_err_field ; Target < next expected (can't go back)

        ; Need to insert an empty field (just a TAB or start)
        ; If bld_fcnt > 0, write a TAB separator first
        TST     _db_bld_fcnt
        BEQ     __dbsi_fill_inc ; First field, no TAB needed
        ; Write TAB
        LDAB    _db_bld_pos
        CMPB    #DB_MAX_REC-1
        BHS     __dbsi_err_ovfl ; Buffer overflow
        LDX     #_db_rec_buf
        ABX
        LDAA    #DB_TAB
        STAA    0,X
        INC     _db_bld_pos

__dbsi_fill_inc:
        INC     _db_bld_fcnt    ; Count the empty field
        BRA     __dbsi_fill     ; Check again

__dbsi_write:
        ; Write TAB separator if this isn't the first field
        TST     _db_bld_fcnt
        BEQ     __dbsi_copy_val ; First field, no TAB

        ; Write TAB before this field
        LDAB    _db_bld_pos
        CMPB    #DB_MAX_REC-1
        BHS     __dbsi_err_ovfl
        LDX     #_db_rec_buf
        ABX
        LDAA    #DB_TAB
        STAA    0,X
        INC     _db_bld_pos

__dbsi_copy_val:
        ; Copy value string into record buffer
        LDX     _dbsi_value     ; X = source string
__dbsi_copy:
        LDAA    0,X             ; A = source char
        BEQ     __dbsi_done     ; Null terminator -> done

        ; Check buffer space
        LDAB    _db_bld_pos
        CMPB    #DB_MAX_REC-1
        BHS     __dbsi_err_ovfl

        ; Store character
        PSHX                    ; Save source pointer
        LDX     #_db_rec_buf
        ABX
        STAA    0,X
        PULX                    ; Restore source pointer

        INC     _db_bld_pos
        INX                     ; Next source char
        BRA     __dbsi_copy

__dbsi_done:
        ; Update record length and field count
        LDAB    _db_bld_pos
        STAB    _db_rec_len
        INC     _db_bld_fcnt
        CLR     _db_last_err

        LDD     #DB_OK
        PULX
        RTS

__dbsi_err_field:
        LDAB    #DB_E_FLD
        JSR     __db_set_err
        PULX
        RTS

__dbsi_err_ovfl:
        LDAB    #DB_E_OVFL
        JSR     __db_set_err
        PULX
        RTS

; --- Temporaries for __db_set_idx ---
_dbsi_index:    RMB     2       ; Target field index
_dbsi_value:    RMB     2       ; Value string pointer

; -----------------------------------------------------------------------------
; __db_set_str - Set a string field by name
; -----------------------------------------------------------------------------
; C: int db_set_str(char *name, char *value)
;
; Looks up the field name in the schema, then calls db_set_idx.
;
; Input:  Stack: name (X+4), value (X+6)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_set_str:
        PSHX
        TSX

        ; Look up field name in schema
        LDX     4,X             ; X = field name pointer
        JSR     __db_find_field ; B = field index, A = type
        TSTB
        BEQ     __dbss_err      ; Not found

        ; Push arguments for db_set_idx: index, value
        CLRA                    ; A = 0 (high byte of index)
        ; D = 0:field_index
        PSHB
        PSHA                    ; Push index

        TSX
        LDD     8,X             ; value (original X+6, but we pushed 2 bytes + PSHX)
        ; Actually, we need to re-calculate. Stack now has:
        ;   [our index 2B][saved_X 2B][ret 2B][name 2B][value 2B]
        ; After TSX: X+0=index, X+2=saved_X, X+4=ret, X+6=name, X+8=value
        LDD     8,X             ; D = value pointer
        PSHB
        PSHA                    ; Push value

        ; Now call __db_set_idx with index and value on stack
        ; But __db_set_idx expects PSHX+TSX format...
        ; Instead, let's call the internal logic directly.
        ; Clean up and use a simpler approach:
        PULX                    ; Pop value into X (dummy, we'll redo)
        PULX                    ; Pop index into X (dummy)

        ; Simpler approach: save field index, then set up proper call
        LDAB    _db_fld_idx     ; B = field index (saved by __db_find_field)
        STAB    _dbss_fidx

        ; Get value pointer from original stack
        TSX
        LDD     6,X             ; D = value pointer (original arg 2)
        STD     _dbss_val

        ; Push args for _db_set_idx (right-to-left): value, index
        LDD     _dbss_val
        PSHB
        PSHA                    ; Push value
        CLRA
        LDAB    _dbss_fidx
        PSHB
        PSHA                    ; Push index
        JSR     _db_set_idx
        ; Clean up 4 bytes
        INS
        INS
        INS
        INS
        ; D = result from db_set_idx

        PULX
        RTS

__dbss_err:
        LDAB    #DB_E_FLD
        JSR     __db_set_err
        PULX
        RTS

; --- Temporaries for __db_set_str ---
_dbss_fidx:     RMB     1       ; Field index found
_dbss_val:      RMB     2       ; Value pointer

; -----------------------------------------------------------------------------
; __db_set_int - Set an integer field by name
; -----------------------------------------------------------------------------
; C: int db_set_int(char *name, int value)
;
; Looks up the field name, converts integer to string, then sets the field.
;
; Input:  Stack: name (X+4), value (X+6)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_set_int:
        PSHX
        TSX

        ; Look up field name
        LDX     4,X             ; X = name pointer
        JSR     __db_find_field
        TSTB
        BEQ     __dbsn_err      ; Not found

        ; Save field index
        STAB    _dbsn_fidx

        ; Convert integer to string
        ; itoa(value, _db_int_buf) -> we need to push args for _itoa
        TSX
        LDD     6,X             ; D = integer value
        PSHB
        PSHA                    ; Push value (arg 1 for _itoa)
        LDD     #_db_int_buf
        PSHB
        PSHA                    ; Push buffer (arg 2 for _itoa)
        ; _itoa expects: n at X+4, s at X+6 (after PSHX+TSX)
        ; But we pushed in wrong order for C convention (right-to-left)
        ; _itoa(n, s): push s first, then n
        ; Let me redo: _itoa is defined as _itoa(n, s)
        ; C calling: push s (arg 2) first, then n (arg 1)
        INS                     ; Clean up wrong pushes
        INS
        INS
        INS

        ; Redo properly: push s first (right-to-left), then n
        TSX
        LDD     #_db_int_buf    ; s = buffer
        PSHB
        PSHA
        LDD     6,X             ; n = integer value (from original args)
        PSHB
        PSHA
        JSR     _itoa           ; Convert to string
        INS
        INS
        INS
        INS

        ; Now set the field using the converted string
        LDD     #_db_int_buf
        PSHB
        PSHA                    ; Push value (string)
        CLRA
        LDAB    _dbsn_fidx
        PSHB
        PSHA                    ; Push index
        JSR     _db_set_idx
        INS
        INS
        INS
        INS
        ; D = result

        PULX
        RTS

__dbsn_err:
        LDAB    #DB_E_FLD
        JSR     __db_set_err
        PULX
        RTS

; --- Temporaries for __db_set_int ---
_dbsn_fidx:     RMB     1       ; Field index found

; -----------------------------------------------------------------------------
; __db_set_int_idx - Set an integer field by index
; -----------------------------------------------------------------------------
; C: int db_set_int_idx(int index, int value)
;
; Input:  Stack: index (X+4), value (X+6)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_set_int_idx:
        PSHX
        TSX

        ; Save index
        LDD     4,X
        STD     _dbsii_idx

        ; Convert integer to string: itoa(value, _db_int_buf)
        LDD     #_db_int_buf    ; s = buffer (arg 2, push first)
        PSHB
        PSHA
        TSX
        LDD     8,X             ; value (original X+6, now X+8 due to pushes)
        PSHB
        PSHA                    ; n = value (arg 1)
        JSR     _itoa
        INS
        INS
        INS
        INS

        ; Call db_set_idx(index, _db_int_buf)
        LDD     #_db_int_buf    ; value string (arg 2, push first)
        PSHB
        PSHA
        LDD     _dbsii_idx      ; index (arg 1)
        PSHB
        PSHA
        JSR     _db_set_idx
        INS
        INS
        INS
        INS
        ; D = result

        PULX
        RTS

; --- Temporaries ---
_dbsii_idx:     RMB     2       ; Saved index

; -----------------------------------------------------------------------------
; __db_append - Append record buffer to file
; -----------------------------------------------------------------------------
; C: int db_append(void)
;
; Writes the current record buffer to the file as a new record.
; The record must have been built using db_clear/db_set_xxx.
;
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_append:
        ; Check file is open
        JSR     __db_chk_open
        BCS     __dba_ret       ; Error already set

        ; Select the correct device
        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dba_err_io

        ; Write record: FL_WRIT expects X = data, B = length
        LDX     #_db_rec_buf
        LDAB    _db_rec_len
        BEQ     __dba_err_inv   ; Can't write empty record
        SWI
        FCB     FL_WRIT
        BCS     __dba_err_io

        ; Success
        CLR     _db_last_err
        LDD     #DB_OK
__dba_ret:
        RTS

__dba_err_io:
        LDAB    #DB_E_IO
        JMP     __db_set_err

__dba_err_inv:
        LDAB    #DB_E_INV
        JMP     __db_set_err

; =============================================================================
; RECORD READING FUNCTIONS
; =============================================================================

; -----------------------------------------------------------------------------
; __db_read - Read current record into buffer
; -----------------------------------------------------------------------------
; C: int db_read(void)
;
; Reads the record at the current file position into _db_rec_buf,
; then parses it to populate field offset/length tables.
;
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_read:
        ; Check file is open
        JSR     __db_chk_open
        BCS     __dbr_ret

        ; Select device
        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbr_err_io

        ; Read record: FL_READ returns X = data pointer, B = length
        SWI
        FCB     FL_READ
        BCS     __dbr_err_eof

        ; B = record length, X = pointer to record data in OS buffer
        ; Copy to our buffer
        STAB    _db_rec_len
        STX     _dbr_src        ; Save OS data pointer

        ; Copy B bytes from X to _db_rec_buf
        CLRA                    ; A = copy counter
__dbr_copy:
        CMPA    _db_rec_len
        BEQ     __dbr_parse     ; All bytes copied

        LDX     _dbr_src
        LDAB    0,X             ; Read from OS buffer
        INX
        STX     _dbr_src

        LDX     #_db_rec_buf
        PSHA
        TAB                     ; Use A as offset... but ABX needs B
        ; Redo: A = counter, need to index _db_rec_buf[A]
        PULA
        PSHX
        LDX     #_db_rec_buf
        PSHB                    ; Save original B (the data byte)
        TAB                     ; B = counter (from A)
        ABX                     ; X = _db_rec_buf + counter
        PULB                    ; Restore data byte
        STAB    0,X             ; Store in our buffer
        PULX                    ; Restore X (not needed but cleanup)

        INCA                    ; Next byte
        BRA     __dbr_copy

__dbr_parse:
        ; Parse the record to find field boundaries
        JSR     __db_parse_rec

        CLR     _db_last_err
        CLR     _db_eof_flg
        LDD     #DB_OK
__dbr_ret:
        RTS

__dbr_err_eof:
        LDAB    #1
        STAB    _db_eof_flg
        LDAB    #DB_E_EOF
        JMP     __db_set_err

__dbr_err_io:
        LDAB    #DB_E_IO
        JMP     __db_set_err

; --- Temporaries for __db_read ---
_dbr_src:       RMB     2       ; Source pointer from FL_READ

; -----------------------------------------------------------------------------
; __db_get_idx - Get a field by index as string
; -----------------------------------------------------------------------------
; C: int db_get_idx(int index, char *buffer, int maxlen)
;
; Copies the field value from the parsed record into the user's buffer.
;
; Input:  Stack: index (X+4, 1-based), buffer (X+6), maxlen (X+8)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_get_idx:
        PSHX
        TSX

        ; Get arguments
        LDAB    5,X             ; B = index (low byte, 1-based)
        BEQ     __dbgi_err_fld  ; Index 0 is invalid
        DECB                    ; Convert to 0-based
        CMPB    _db_rd_fcnt
        BHS     __dbgi_err_fld  ; Index >= field count

        ; Get field offset and length from parsed tables
        STAB    _dbgi_fidx      ; Save 0-based index
        LDX     #_db_fld_off
        ABX
        LDAA    0,X             ; A = field offset in rec_buf
        STAA    _dbgi_off

        LDAB    _dbgi_fidx
        LDX     #_db_fld_len
        ABX
        LDAA    0,X             ; A = field length
        STAA    _dbgi_len

        ; Get destination buffer and maxlen
        TSX
        LDD     6,X             ; D = buffer pointer
        STD     _dbgi_dst
        LDAB    9,X             ; B = maxlen (low byte)
        STAB    _dbgi_max

        ; Copy field value to user buffer
        ; Source: _db_rec_buf + _dbgi_off, length: _dbgi_len
        ; Dest: _dbgi_dst, max: _dbgi_max - 1 (leave room for null)
        LDX     #_db_rec_buf
        LDAB    _dbgi_off
        ABX                     ; X = source start
        STX     _dbgi_src

        CLRA                    ; A = copy counter
        LDAB    _dbgi_max
        BEQ     __dbgi_term     ; maxlen = 0, just terminate
        DECB                    ; B = max chars to copy (maxlen - 1)
        STAB    _dbgi_max

__dbgi_copy:
        CMPA    _dbgi_len
        BHS     __dbgi_term     ; Copied all field chars
        CMPA    _dbgi_max
        BHS     __dbgi_term     ; Reached max

        LDX     _dbgi_src
        LDAB    0,X             ; B = source char
        INX
        STX     _dbgi_src

        LDX     _dbgi_dst
        STAB    0,X             ; Store in dest
        INX
        STX     _dbgi_dst

        INCA
        BRA     __dbgi_copy

__dbgi_term:
        ; Null-terminate the destination
        LDX     _dbgi_dst
        CLR     0,X

        CLR     _db_last_err
        LDD     #DB_OK
        PULX
        RTS

__dbgi_err_fld:
        LDAB    #DB_E_FLD
        JSR     __db_set_err
        PULX
        RTS

; --- Temporaries for __db_get_idx ---
_dbgi_fidx:     RMB     1       ; 0-based field index
_dbgi_off:      RMB     1       ; Field offset in rec_buf
_dbgi_len:      RMB     1       ; Field length
_dbgi_dst:      RMB     2       ; Destination buffer pointer
_dbgi_src:      RMB     2       ; Source pointer
_dbgi_max:      RMB     1       ; Max chars to copy

; -----------------------------------------------------------------------------
; __db_get_str - Get a string field by name
; -----------------------------------------------------------------------------
; C: int db_get_str(char *name, char *buffer, int maxlen)
;
; Input:  Stack: name (X+4), buffer (X+6), maxlen (X+8)
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_get_str:
        PSHX
        TSX

        ; Look up field name
        LDX     4,X             ; X = name pointer
        JSR     __db_find_field
        TSTB
        BEQ     __dbgs_err      ; Not found

        ; Call db_get_idx(index, buffer, maxlen)
        STAB    _dbgs_fidx      ; Save field index

        ; Push args right-to-left: maxlen, buffer, index
        TSX
        LDD     8,X             ; maxlen
        PSHB
        PSHA
        LDD     6,X             ; buffer
        PSHB
        PSHA
        CLRA
        LDAB    _dbgs_fidx
        PSHB
        PSHA                    ; index
        JSR     _db_get_idx
        INS
        INS
        INS
        INS
        INS
        INS
        ; D = result

        PULX
        RTS

__dbgs_err:
        LDAB    #DB_E_FLD
        JSR     __db_set_err
        PULX
        RTS

; --- Temporaries ---
_dbgs_fidx:     RMB     1

; -----------------------------------------------------------------------------
; __db_get_int - Get an integer field by name
; -----------------------------------------------------------------------------
; C: int db_get_int(char *name)
;
; Input:  Stack: name (X+4)
; Output: D = integer value (0 if not found or conversion fails)
; -----------------------------------------------------------------------------
__db_get_int:
        PSHX
        TSX

        ; Look up field name
        LDX     4,X             ; X = name pointer
        JSR     __db_find_field
        TSTB
        BEQ     __dbgn_zero     ; Not found, return 0

        ; Get field as string into temp buffer, then convert with atoi
        ; Call db_get_idx(index, _db_int_buf, 8)
        LDD     #8              ; maxlen
        PSHB
        PSHA
        LDD     #_db_int_buf    ; buffer
        PSHB
        PSHA
        LDAB    _db_fld_idx     ; index (from find_field)
        CLRA
        PSHB
        PSHA
        JSR     _db_get_idx
        INS
        INS
        INS
        INS
        INS
        INS

        ; Check if get_idx succeeded
        TSTB
        BNE     __dbgn_zero     ; Error

        ; Convert string to integer: atoi(_db_int_buf)
        LDD     #_db_int_buf
        PSHB
        PSHA
        JSR     _atoi
        INS
        INS
        ; D = integer value

        PULX
        RTS

__dbgn_zero:
        LDD     #0
        PULX
        RTS

; -----------------------------------------------------------------------------
; __db_get_int_idx - Get an integer field by index
; -----------------------------------------------------------------------------
; C: int db_get_int_idx(int index)
;
; Input:  Stack: index (X+4, 1-based)
; Output: D = integer value (0 if error)
; -----------------------------------------------------------------------------
__db_get_int_idx:
        PSHX
        TSX

        ; Get field as string into temp buffer
        LDD     #8              ; maxlen
        PSHB
        PSHA
        LDD     #_db_int_buf    ; buffer
        PSHB
        PSHA
        LDD     4,X             ; index (from original args, now at X+4)
        PSHB
        PSHA
        JSR     _db_get_idx
        INS
        INS
        INS
        INS
        INS
        INS

        ; Check if get_idx succeeded
        TSTB
        BNE     __dbgii_zero

        ; Convert string to integer
        LDD     #_db_int_buf
        PSHB
        PSHA
        JSR     _atoi
        INS
        INS
        ; D = integer value

        PULX
        RTS

__dbgii_zero:
        LDD     #0
        PULX
        RTS

; -----------------------------------------------------------------------------
; __db_field_count - Get number of fields in current record
; -----------------------------------------------------------------------------
; C: int db_field_count(void)
;
; Output: D = field count from last db_read, or 0
; -----------------------------------------------------------------------------
__db_field_count:
        CLRA
        LDAB    _db_rd_fcnt
        RTS

; -----------------------------------------------------------------------------
; __db_recsize - Get current record size
; -----------------------------------------------------------------------------
; C: int db_recsize(void)
;
; Output: D = record size in bytes, or 0
; -----------------------------------------------------------------------------
__db_recsize:
        CLRA
        LDAB    _db_rec_len
        RTS

; =============================================================================
; NAVIGATION FUNCTIONS
; =============================================================================

; -----------------------------------------------------------------------------
; __db_first - Move to first record
; -----------------------------------------------------------------------------
; C: int db_first(void)
;
; Resets to the beginning of the file (first record).
; On the Psion, this is done by calling FL_RSET to reset file position.
;
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_first:
        JSR     __db_chk_open
        BCS     __dbfst_ret

        ; Select device
        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbfst_err

        ; FL_RSET resets file position to the beginning
        SWI
        FCB     FL_RSET
        BCS     __dbfst_err

        CLR     _db_eof_flg
        CLR     _db_last_err
        LDD     #1
        STD     _db_rec_pos     ; Position 1

        LDD     #DB_OK
__dbfst_ret:
        RTS

__dbfst_err:
        LDAB    #DB_E_EOF
        JMP     __db_set_err

; -----------------------------------------------------------------------------
; __db_next - Move to next record
; -----------------------------------------------------------------------------
; C: int db_next(void)
;
; Output: D = DB_OK or DB_ERR_EOF
; -----------------------------------------------------------------------------
__db_next:
        JSR     __db_chk_open
        BCS     __dbnx_ret

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbnx_err

        ; FL_NEXT advances to next record; carry set = EOF
        SWI
        FCB     FL_NEXT
        BCS     __dbnx_eof

        ; Increment position
        LDD     _db_rec_pos
        ADDD    #1
        STD     _db_rec_pos

        CLR     _db_eof_flg
        CLR     _db_last_err
        LDD     #DB_OK
__dbnx_ret:
        RTS

__dbnx_eof:
        LDAB    #1
        STAB    _db_eof_flg
        LDAB    #DB_E_EOF
        JMP     __db_set_err

__dbnx_err:
        LDAB    #DB_E_IO
        JMP     __db_set_err

; -----------------------------------------------------------------------------
; __db_back - Move to previous record
; -----------------------------------------------------------------------------
; C: int db_back(void)
;
; Output: D = DB_OK or DB_ERR_EOF (at beginning)
; -----------------------------------------------------------------------------
__db_back:
        JSR     __db_chk_open
        BCS     __dbbk_ret

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbbk_err

        ; FL_BACK moves to previous record; carry set = at beginning
        SWI
        FCB     FL_BACK
        BCS     __dbbk_bof

        ; Decrement position
        LDD     _db_rec_pos
        SUBD    #1
        BCC     __dbbk_store    ; Don't go below 0
        LDD     #1              ; Clamp to 1
__dbbk_store:
        STD     _db_rec_pos

        CLR     _db_eof_flg
        CLR     _db_last_err
        LDD     #DB_OK
__dbbk_ret:
        RTS

__dbbk_bof:
        LDAB    #DB_E_EOF
        JMP     __db_set_err

__dbbk_err:
        LDAB    #DB_E_IO
        JMP     __db_set_err

; -----------------------------------------------------------------------------
; __db_find - Find record containing string
; -----------------------------------------------------------------------------
; C: int db_find(char *pattern)
;
; Input:  Stack: pattern (X+4, null-terminated search string)
; Output: D = DB_OK if found, DB_ERR_NOT_FOUND if not
; -----------------------------------------------------------------------------
__db_find:
        PSHX
        TSX

        JSR     __db_chk_open
        BCS     __dbfn_ret

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbfn_err_io

        ; Build LBC search string from pattern
        TSX
        LDX     4,X             ; X = pattern string
        JSR     __db_make_lbc   ; X = _db_lbc_buf

        ; FL_FIND: X = LBC search string, searches from current position
        SWI
        FCB     FL_FIND
        BCS     __dbfn_nf

        CLR     _db_eof_flg
        CLR     _db_last_err
        LDD     #DB_OK
__dbfn_ret:
        PULX
        RTS

__dbfn_nf:
        LDAB    #DB_E_NFND
        JSR     __db_set_err
        PULX
        RTS

__dbfn_err_io:
        LDAB    #DB_E_IO
        JSR     __db_set_err
        PULX
        RTS

; -----------------------------------------------------------------------------
; __db_eof - Check if at end of file
; -----------------------------------------------------------------------------
; C: int db_eof(void)
;
; Output: D = 1 if at EOF, 0 otherwise
; -----------------------------------------------------------------------------
__db_eof:
        CLRA
        LDAB    _db_eof_flg
        RTS

; -----------------------------------------------------------------------------
; __db_pos - Get current record position
; -----------------------------------------------------------------------------
; C: int db_pos(void)
;
; Output: D = current record number (1-based), or 0 if not positioned
; -----------------------------------------------------------------------------
__db_pos:
        LDD     _db_rec_pos
        RTS

; -----------------------------------------------------------------------------
; __db_count - Get total record count
; -----------------------------------------------------------------------------
; C: int db_count(void)
;
; Counts records by iterating through the file. Restores original position
; afterward. This is an expensive operation - use sparingly.
;
; Output: D = record count, or 0 if not open
; -----------------------------------------------------------------------------
__db_count:
        JSR     __db_chk_open
        BCS     __dbcnt_zero

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbcnt_zero

        ; Save current position
        LDD     _db_rec_pos
        STD     _dbcnt_saved

        ; Reset to beginning
        SWI
        FCB     FL_RSET
        BCS     __dbcnt_zero

        ; Count records by calling FL_NEXT until EOF
        LDD     #0
        STD     _dbcnt_count

__dbcnt_loop:
        ; Try to read a record (FL_READ to check if there's data)
        SWI
        FCB     FL_READ
        BCS     __dbcnt_done    ; No more records

        ; Increment count
        LDD     _dbcnt_count
        ADDD    #1
        STD     _dbcnt_count

        ; Move to next
        SWI
        FCB     FL_NEXT
        BCC     __dbcnt_loop    ; More records

__dbcnt_done:
        ; Restore position by resetting and advancing
        SWI
        FCB     FL_RSET         ; Reset to beginning

        ; Return count
        LDD     _dbcnt_count
        RTS

__dbcnt_zero:
        LDD     #0
        RTS

; --- Temporaries for __db_count ---
_dbcnt_count:   RMB     2       ; Running count
_dbcnt_saved:   RMB     2       ; Saved position

; =============================================================================
; RECORD MODIFICATION FUNCTIONS
; =============================================================================

; -----------------------------------------------------------------------------
; __db_update - Replace current record with buffer contents
; -----------------------------------------------------------------------------
; C: int db_update(void)
;
; Erases the current record and writes the buffer as a replacement.
; This is a simplified update: erase + append. The position may change
; since the new record is appended at the end.
;
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_update:
        JSR     __db_chk_open
        BCS     __dbup_ret

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dbup_err

        ; Erase current record
        SWI
        FCB     FL_ERAS
        BCS     __dbup_err

        ; Write new record (append)
        LDX     #_db_rec_buf
        LDAB    _db_rec_len
        BEQ     __dbup_err      ; Empty record
        SWI
        FCB     FL_WRIT
        BCS     __dbup_err

        CLR     _db_last_err
        LDD     #DB_OK
__dbup_ret:
        RTS

__dbup_err:
        LDAB    #DB_E_IO
        JMP     __db_set_err

; -----------------------------------------------------------------------------
; __db_erase - Delete current record
; -----------------------------------------------------------------------------
; C: int db_erase(void)
;
; Erases the record at the current file position. After erasure, the
; position advances to the next record (or EOF if last).
;
; Output: D = DB_OK or error code
; -----------------------------------------------------------------------------
__db_erase:
        JSR     __db_chk_open
        BCS     __dber_ret

        LDAB    _db_device
        JSR     __db_sel_dev
        BCS     __dber_err

        SWI
        FCB     FL_ERAS
        BCS     __dber_err

        CLR     _db_last_err
        LDD     #DB_OK
__dber_ret:
        RTS

__dber_err:
        LDAB    #DB_E_IO
        JMP     __db_set_err

; =============================================================================
; End of DBRUNTIME.INC
; =============================================================================
