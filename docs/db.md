# db.h - Database and File Access Functions

**Part of the Psion Organiser II SDK**

This document describes the optional database and file access functions provided by `db.h` and `dbruntime.inc`. These functions wrap the Psion OS FL$ file services to provide a C-friendly interface for creating, reading, writing, and navigating TAB-delimited record databases with full OPL interoperability.

---

## Overview

The Psion Organiser II's "killer feature" is its built-in record-oriented database. The DIARY, WORLD, NOTEPAD, and all user-created OPL applications are built on this system. The db module exposes this from C using a schema-based API that maps cleanly to OPL's data model.

Records are TAB-delimited ASCII text (max 254 bytes, max 16 fields). Numeric values are stored as decimal text and converted on access. Files created by C are fully readable and writable by OPL programs, and vice versa.

**Code Size Impact:** ~1200-1600 bytes of code plus ~300 bytes of static data buffers

---

## Quick Start

### For C Programmers

```c
#include <psion.h>
#include <db.h>

void main() {
    int db;
    char name[20];
    int age;

    /* Create a contacts database on A: (internal RAM) */
    db = db_create('A', "CONTACTS", "name$,phone$,age%");
    if (db < 0) { print("Error!"); getkey(); return; }

    /* Add a record */
    db_clear();
    db_set_str("name", "Alice");
    db_set_str("phone", "555-1234");
    db_set_int("age", 30);
    db_append();

    /* Read it back */
    db_first();
    if (db_read() == 0) {
        db_get_str("name", name, 20);
        age = db_get_int("age");
        cls();
        print(name);
        print(" age:");
        print_int(age);
    }

    db_close(db);
    getkey();
}
```

### For Assembly Programmers

```asm
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"
        INCLUDE "dbruntime.inc"

        ; Using macros (recommended)
        DB_CREATE 'A', FNAME, SCHEMA
        ; D = handle (0 or -1)

        DB_CLEAR
        DB_SET_IDX 1, VALUE1
        DB_SET_IDX 2, VALUE2
        DB_APPEND
        ; D = DB_OK or error

        DB_FIRST
        DB_READ
        DB_GET_IDX 1, BUFFER, 20
        ; BUFFER now contains field 1

        DB_CLOSE

        ; Using functions directly
        LDD     #SCHEMA         ; schema (arg 3, pushed first)
        PSHB
        PSHA
        LDD     #FNAME          ; name (arg 2)
        PSHB
        PSHA
        LDD     #'A'            ; device (arg 1)
        PSHB
        PSHA
        JSR     _db_create
        INS
        INS
        INS
        INS
        INS
        INS
        ; D = handle (0 or -1)

FNAME:  FCC     "DATA"
        FCB     0
SCHEMA: FCC     "x$,y%"
        FCB     0
VALUE1: FCC     "Hello"
        FCB     0
VALUE2: FCC     "42"
        FCB     0
BUFFER: RMB     20
```

---

## Include Order

The db module must be included after the core runtime:

```c
/* C programs */
#include <psion.h>
#include <db.h>          /* Optional - include if needed */
```

```asm
; Assembly programs
        INCLUDE "psion.inc"
        INCLUDE "runtime.inc"
        INCLUDE "dbruntime.inc"     ; Optional - include if needed
```

The compiler automatically includes `dbruntime.inc` in the generated assembly when `db.h` is detected.

---

## Schema Strings

The schema string defines the record structure: field names and types, comma-separated.

**Format:** `"fieldname$,fieldname$,fieldname%"`

**Type suffixes** (matching OPL conventions):
- `$` = String field
- `%` = Integer field

**Examples:**
```c
/* Named fields */
"name$,phone$,age%"

/* Nameless fields (index-only access) */
"$,$,%"

/* Single field */
"value$"

/* No schema (raw access) - pass 0 */
db_create('A', "DATA", 0);
```

**OPL equivalence:**

| C Schema | OPL Equivalent |
|----------|----------------|
| `"name$,phone$,age%"` | `CREATE "A:CONTACTS", A, name$, phone$, age%` |
| `"item$,qty%"` | `CREATE "A:ITEMS", A, item$, qty%` |

Field names are for C's convenience only and are not stored in the file. Field **order** and **types** must match between C and OPL programs that share data.

---

## File Management Functions

### db_create - Create a New Database File

Creates a new data file on the specified device and associates a schema.

**C Declaration:**
```c
int db_create(char device, char *name, char *schema);
```

**Parameters:**
- `device` - Device letter: `'A'` (internal RAM), `'B'` (pack slot 0), `'C'` (pack slot 1)
- `name` - File name (max 8 characters, uppercase recommended)
- `schema` - Schema string defining fields, or `0` for raw access

**Returns:**
- File handle (`0`) on success
- `-1` on error (use `db_error()` for details)

**Example:**
```c
int db;

db = db_create('A', "CONTACTS", "name$,phone$,age%");
if (db < 0) {
    print("Create failed!");
    print_int(db_error());
    getkey();
    return;
}
```

**Assembly Usage:**
```asm
        ; Using macro
        DB_CREATE 'A', FNAME, SCHEMA
        ; D = 0 (success) or -1 (error)

        ; Using function directly
        LDD     #SCHEMA
        PSHB
        PSHA
        LDD     #FNAME
        PSHB
        PSHA
        LDD     #'A'
        PSHB
        PSHA
        JSR     _db_create
        INS
        INS
        INS
        INS
        INS
        INS
```

---

### db_open - Open an Existing Database File

Opens an existing file and associates a schema for field access.

**C Declaration:**
```c
int db_open(char device, char *name, char *schema);
```

**Parameters:**
- `device` - Device letter: `'A'`, `'B'`, or `'C'`
- `name` - File name to open
- `schema` - Schema string (should match file structure), or `0` for raw access

**Returns:**
- File handle (`0`) on success
- `-1` on error

**Example:**
```c
/* Open an OPL-created file */
int db = db_open('A', "CONTACTS", "name$,phone$,age%");
if (db < 0) {
    print("Not found");
    getkey();
    return;
}
```

You can use different field **names** than the original creator, but the field **order** and **types** must match for correct data access.

**Assembly Usage:**
```asm
        DB_OPEN 'A', FNAME, SCHEMA
        ; D = 0 (success) or -1 (error)
```

---

### db_close - Close the Database File

Closes the file and releases the handle.

**C Declaration:**
```c
void db_close(int handle);
```

**Parameters:**
- `handle` - File handle from `db_create()` or `db_open()`

**Example:**
```c
db_close(db);
```

**Assembly Usage:**
```asm
        DB_CLOSE
```

---

### db_error - Get Last Error Code

Returns the error code from the most recent database operation.

**C Declaration:**
```c
int db_error(void);
```

**Returns:**
- Error code (see Error Codes table below), or `0` if no error

**Example:**
```c
int db = db_create('A', "TEST", "x$");
if (db < 0) {
    int err = db_error();
    print("Error: ");
    print_int(err);
}
```

---

### db_catalog - List Files on a Device

Iterates through files on a device, returning one filename at a time. Use with `first=1` to start enumeration, then `first=0` for subsequent files.

**C Declaration:**
```c
int db_catalog(char device, char *buffer, int maxlen, int first);
```

**Parameters:**
- `device` - Device letter: `'A'` (internal RAM), `'B'` (pack slot 0), `'C'` (pack slot 1)
- `buffer` - Destination buffer for the filename (null-terminated)
- `maxlen` - Maximum bytes to copy (including null terminator)
- `first` - `1` to start from beginning, `0` to get next file

**Returns:**
- Length of filename on success
- `0` when no more files

**Example - List all files on A:**
```c
#include <psion.h>
#include <db.h>

void main() {
    char namebuf[16];
    int len;

    cls();
    print("Files on A:\n");

    /* Get first file */
    len = db_catalog('A', namebuf, 16, 1);

    while (len > 0) {
        print(namebuf);
        print("\n");
        /* Get next file */
        len = db_catalog('A', namebuf, 16, 0);
    }

    getkey();
}
```

**Assembly Usage:**
```asm
        ; List files on device A:
        DB_CATALOG 'A', BUFFER, 16, 1   ; First file
        ; D = length or 0

        ; Get next file
        DB_CATALOG 'A', BUFFER, 16, 0
        ; D = length or 0

BUFFER: RMB     16
```

**Notes:**
- Wraps the FL$CATL system service
- Returns all file types (OPL, data files, etc.)
- Filenames are returned as null-terminated C strings

---

## Record Building Functions

Records are built in an internal buffer before writing. This matches OPL's model where you assign to fields, then call APPEND.

**Workflow:**
1. `db_clear()` - Reset the record buffer
2. `db_set_xxx()` - Set each field value (in ascending order)
3. `db_append()` - Write the record to the file

### db_clear - Clear the Record Buffer

Resets the record buffer for building a new record. Must be called before setting field values.

**C Declaration:**
```c
void db_clear(void);
```

**Example:**
```c
db_clear();
db_set_str("name", "Alice");
db_set_int("age", 30);
db_append();
```

**Assembly Usage:**
```asm
        DB_CLEAR
```

---

### db_set_str - Set a String Field by Name

Sets a field's value in the record buffer by looking up the field name in the schema.

**C Declaration:**
```c
int db_set_str(char *name, char *value);
```

**Parameters:**
- `name` - Field name (as defined in schema, e.g., `"name"`)
- `value` - String value (null-terminated)

**Returns:**
- `0` on success
- `11` if field name not found in schema

**Example:**
```c
db_clear();
db_set_str("name", "Alice");
db_set_str("phone", "555-1234");
db_append();
```

Fields must be set in ascending order (field 1, then 2, then 3, etc.).

---

### db_set_int - Set an Integer Field by Name

Sets an integer field's value. The integer is converted to ASCII decimal text for storage.

**C Declaration:**
```c
int db_set_int(char *name, int value);
```

**Parameters:**
- `name` - Field name (should be a `%` type field in schema)
- `value` - Integer value (-32768 to 32767)

**Returns:**
- `0` on success
- `11` if field name not found

**Example:**
```c
db_clear();
db_set_str("name", "Widget");
db_set_int("qty", 100);
db_set_int("price", -5);
db_append();
```

---

### db_set_idx - Set a Field by Index

Sets a field by its 1-based position. Always stores as raw string. Use this for raw access or when schema is not defined.

**C Declaration:**
```c
int db_set_idx(int index, char *value);
```

**Parameters:**
- `index` - Field index (1-based, matching OPL convention)
- `value` - String value (null-terminated)

**Returns:**
- `0` on success
- `11` if index out of range (< 1 or > 16)

**Example:**
```c
db_clear();
db_set_idx(1, "Alice");
db_set_idx(2, "555-1234");
db_set_idx(3, "30");
db_append();
```

**Assembly Usage:**
```asm
        DB_CLEAR
        DB_SET_IDX 1, VALUE1
        DB_SET_IDX 2, VALUE2
        DB_APPEND
```

---

### db_set_int_idx - Set an Integer Field by Index

Like `db_set_idx` but converts the integer to a string first.

**C Declaration:**
```c
int db_set_int_idx(int index, int value);
```

**Parameters:**
- `index` - Field index (1-based)
- `value` - Integer value

**Returns:**
- `0` on success
- `11` if index out of range

**Example:**
```c
db_clear();
db_set_idx(1, "Widget");
db_set_int_idx(2, 100);
db_append();
```

---

### db_append - Append Record Buffer to File

Writes the current record buffer as a new record at the end of the file.

**C Declaration:**
```c
int db_append(void);
```

**Returns:**
- `0` on success
- Error code on failure (pack full, I/O error, etc.)

**Example:**
```c
db_clear();
db_set_str("name", "Alice");
db_set_int("age", 30);
int result = db_append();
if (result != 0) {
    print("Write failed");
}
```

**Assembly Usage:**
```asm
        DB_APPEND
        ; D = 0 (success) or error code
```

---

## Record Reading Functions

Use navigation functions to position at a record, then call `db_read()` to load it into the buffer, then use `db_get_xxx()` to extract field values.

**Workflow:**
1. `db_first()` or `db_next()` - Position at a record
2. `db_read()` - Load record into buffer
3. `db_get_xxx()` - Extract field values

### db_read - Read Current Record into Buffer

Reads the record at the current position into the internal buffer. Use `db_get_xxx()` functions to access individual field values afterward.

**C Declaration:**
```c
int db_read(void);
```

**Returns:**
- `0` on success
- `8` if no current record (EOF)

**Example:**
```c
db_first();
if (db_read() == 0) {
    /* Record loaded, extract fields */
    char name[20];
    db_get_str("name", name, 20);
    print(name);
}
```

**Assembly Usage:**
```asm
        DB_READ
        ; D = 0 (success) or error code
```

---

### db_get_str - Get a String Field by Name

Retrieves a field's value from the loaded record as a null-terminated string.

**C Declaration:**
```c
int db_get_str(char *name, char *buffer, int maxlen);
```

**Parameters:**
- `name` - Field name (as defined in schema)
- `buffer` - Destination buffer for the value
- `maxlen` - Maximum bytes to copy (including null terminator)

**Returns:**
- `0` on success
- `11` if field name not found

**Example:**
```c
char name[20];
char phone[16];

db_read();
db_get_str("name", name, 20);
db_get_str("phone", phone, 16);

cls();
print(name);
print(" ");
print(phone);
```

---

### db_get_int - Get an Integer Field by Name

Retrieves and converts a field to an integer. The field's stored text is parsed as a decimal number (handles leading minus and whitespace).

**C Declaration:**
```c
int db_get_int(char *name);
```

**Parameters:**
- `name` - Field name (should be a `%` type field in schema)

**Returns:**
- Integer value, or `0` if field not found or not numeric

**Example:**
```c
int age = db_get_int("age");
int qty = db_get_int("qty");
int total = qty * db_get_int("price");
```

---

### db_get_idx - Get a Field by Index

Retrieves any field as a raw string by its 1-based position.

**C Declaration:**
```c
int db_get_idx(int index, char *buffer, int maxlen);
```

**Parameters:**
- `index` - Field index (1-based)
- `buffer` - Destination buffer
- `maxlen` - Maximum bytes (including null terminator)

**Returns:**
- `0` on success
- `11` if index invalid

**Example:**
```c
char buf[30];
db_read();
db_get_idx(1, buf, 30);    /* Get first field */
print(buf);
```

**Assembly Usage:**
```asm
        DB_READ
        DB_GET_IDX 1, BUFFER, 20
        ; BUFFER now contains field 1 as null-terminated string
```

---

### db_get_int_idx - Get an Integer Field by Index

Retrieves and converts a field by index.

**C Declaration:**
```c
int db_get_int_idx(int index);
```

**Parameters:**
- `index` - Field index (1-based)

**Returns:**
- Integer value, or `0` if conversion fails

**Example:**
```c
int val = db_get_int_idx(3);    /* Get third field as integer */
```

---

### db_field_count - Get Number of Fields in Current Record

Returns the number of TAB-delimited fields in the most recently read record.

**C Declaration:**
```c
int db_field_count(void);
```

**Returns:**
- Field count, or `0` if no record loaded

**Example:**
```c
db_read();
int n = db_field_count();
print("Fields: ");
print_int(n);
```

---

### db_recsize - Get Current Record Size

Returns the total size of the current record in bytes, including delimiters.

**C Declaration:**
```c
int db_recsize(void);
```

**Returns:**
- Size in bytes, or `0` if no record loaded

---

## Navigation Functions

These move the file position pointer. After navigation, call `db_read()` to load the record at the new position.

### db_first - Move to First Record

Positions at the first record in the file.

**C Declaration:**
```c
int db_first(void);
```

**Returns:**
- `0` on success
- `8` if file is empty

**Example:**
```c
db_first();
db_read();
/* Now working with the first record */
```

**Assembly Usage:**
```asm
        DB_FIRST
```

---

### db_next - Move to Next Record

Advances to the next record.

**C Declaration:**
```c
int db_next(void);
```

**Returns:**
- `0` on success
- `8` if at end of file

**Example - iterate all records:**
```c
db_first();
while (!db_eof()) {
    if (db_read() == 0) {
        char name[20];
        db_get_str("name", name, 20);
        print(name);
    }
    db_next();
}
```

**Assembly Usage:**
```asm
        DB_NEXT
```

---

### db_back - Move to Previous Record

Moves to the previous record.

**C Declaration:**
```c
int db_back(void);
```

**Returns:**
- `0` on success
- `8` if at beginning of file

**Assembly Usage:**
```asm
        DB_BACK
```

---

### db_find - Find Record Containing String

Searches from the current position for a record containing the specified text. If found, that record becomes the current position.

**C Declaration:**
```c
int db_find(char *pattern);
```

**Parameters:**
- `pattern` - Text to search for (null-terminated)

**Returns:**
- `0` if found
- `1` if not found

**Example:**
```c
db_first();
if (db_find("Alice") == 0) {
    db_read();
    char phone[16];
    db_get_str("phone", phone, 16);
    print("Found: ");
    print(phone);
} else {
    print("Not found");
}
```

---

### db_eof - Check if at End of File

**C Declaration:**
```c
int db_eof(void);
```

**Returns:**
- `1` if at EOF (past last record)
- `0` otherwise

**Example - loop through all records:**
```c
int count = 0;
db_first();
while (!db_eof()) {
    db_read();
    count = count + 1;
    db_next();
}
print_int(count);
```

**Assembly Usage:**
```asm
        DB_EOF
        TSTB
        BNE     at_end
```

---

### db_count - Get Total Record Count

Counts all records in the file. This iterates through the entire file, so use sparingly on large files.

**C Declaration:**
```c
int db_count(void);
```

**Returns:**
- Number of records, or `0` if file is empty or not open

**Example:**
```c
int n = db_count();
print("Total: ");
print_int(n);
```

---

### db_pos - Get Current Record Position

Returns the 1-based position of the current record.

**C Declaration:**
```c
int db_pos(void);
```

**Returns:**
- Current record number (1-based), or `0` if not positioned

---

## Record Modification Functions

### db_update - Replace Current Record

Replaces the record at the current position with the contents of the record buffer (built via `db_clear()`/`db_set_xxx()`). Equivalent to OPL `UPDATE`.

Implementation: erases old record and writes new one. Position may change since the new record is appended at the end.

**C Declaration:**
```c
int db_update(void);
```

**Returns:**
- `0` on success
- Error code on failure

**Example:**
```c
/* Find and update Alice's age */
db_first();
if (db_find("Alice") == 0) {
    db_read();
    char name[20];
    char phone[16];

    /* Read existing values */
    db_get_str("name", name, 20);
    db_get_str("phone", phone, 16);

    /* Rebuild with new age */
    db_clear();
    db_set_str("name", name);
    db_set_str("phone", phone);
    db_set_int("age", 31);
    db_update();
}
```

---

### db_erase - Delete Current Record

Removes the record at the current position. After erasure, the position advances to the next record (or EOF if last). Equivalent to OPL `ERASE`.

**C Declaration:**
```c
int db_erase(void);
```

**Returns:**
- `0` on success
- Error code on failure

**Example:**
```c
/* Find and delete a specific record */
db_first();
if (db_find("Charlie") == 0) {
    db_erase();
    print("Deleted");
}

/* Delete all records */
db_first();
while (!db_eof()) {
    db_erase();
}
```

---

## Error Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | `DB_OK` | Success |
| 1 | `DB_ERR_NOT_FOUND` | File or record not found |
| 2 | `DB_ERR_EXISTS` | File already exists |
| 3 | `DB_ERR_FULL` | Pack full or record too large |
| 4 | `DB_ERR_IO` | I/O or pack error |
| 5 | `DB_ERR_INVALID` | Invalid parameter |
| 6 | `DB_ERR_NOT_OPEN` | No file is open |
| 7 | `DB_ERR_ALREADY` | A file is already open |
| 8 | `DB_ERR_EOF` | End of file / no current record |
| 9 | `DB_ERR_OVERFLOW` | Record buffer overflow (> 254 bytes) |
| 10 | `DB_ERR_TYPE` | Type mismatch in schema |
| 11 | `DB_ERR_FIELD` | Invalid field index or name not found |

---

## OPL Interoperability

Files created by the C database API are fully readable and writable by OPL, and vice versa. The on-pack format is identical: TAB-delimited text records.

**Creating in C, reading in OPL:**
```c
/* C code */
db_create('A', "CONTACTS", "name$,phone$,age%");
db_clear();
db_set_str("name", "Alice");
db_set_str("phone", "555-1234");
db_set_int("age", 30);
db_append();
db_close(0);
```

```
REM OPL code (reads the same file)
OPEN "A:CONTACTS", A, name$, phone$, age%
FIRST
  PRINT A.name$, A.phone$, A.age%
CLOSE
```

**Creating in OPL, reading in C:**
```
REM OPL code
CREATE "A:ITEMS", A, item$, qty%
A.item$ = "Widget"
A.qty% = 100
APPEND
CLOSE
```

```c
/* C code (reads the same file) */
db_open('A', "ITEMS", "item$,qty%");
db_first();
db_read();

char item[20];
db_get_str("item", item, 20);
int qty = db_get_int("qty");
```

**Rules for interoperability:**
- Field **order** must match between C and OPL
- Field **types** must match between C and OPL
- Field **names** are independent (only used locally for lookup)
- Maximum 254 bytes per record, maximum 16 fields

---

## Assembly Macros Reference

The following macros are available for assembly programmers:

| Macro | Arguments | Description |
|-------|-----------|-------------|
| `DB_CREATE` | device, name, schema | Create new database file |
| `DB_OPEN` | device, name, schema | Open existing database file |
| `DB_CLOSE` | - | Close database file |
| `DB_CATALOG` | device, buffer, maxlen, first | List files on device |
| `DB_CLEAR` | - | Clear record buffer |
| `DB_SET_IDX` | index, value | Set field by index (string) |
| `DB_APPEND` | - | Append record buffer to file |
| `DB_READ` | - | Read current record into buffer |
| `DB_GET_IDX` | index, buffer, maxlen | Get field by index as string |
| `DB_FIRST` | - | Move to first record |
| `DB_NEXT` | - | Move to next record |
| `DB_BACK` | - | Move to previous record |
| `DB_EOF` | - | Check end-of-file flag |

All macros:
- Leave result in D register
- May clobber A, B, and flags
- Handle stack cleanup automatically

---

## Stack Layout Reference

For assembly programmers calling functions directly:

**db_create(device, name, schema):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [device   2B] offset 4-5 (char in low byte at 5)
  [name     2B] offset 6-7
  [schema   2B] offset 8-9
```

**db_open(device, name, schema):**
```
Same layout as db_create
```

**db_close(handle):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [handle   2B] offset 4-5
```

**db_set_str(name, value):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [name     2B] offset 4-5
  [value    2B] offset 6-7
```

**db_set_int(name, value):**
```
Same layout as db_set_str
```

**db_set_idx(index, value):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [index    2B] offset 4-5 (int in low byte at 5)
  [value    2B] offset 6-7
```

**db_get_str(name, buffer, maxlen):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [name     2B] offset 4-5
  [buffer   2B] offset 6-7
  [maxlen   2B] offset 8-9
```

**db_get_idx(index, buffer, maxlen):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [index    2B] offset 4-5
  [buffer   2B] offset 6-7
  [maxlen   2B] offset 8-9
```

**db_find(pattern):**
```
Stack after PSHX+TSX:
  [saved_X  2B] offset 0-1
  [ret addr 2B] offset 2-3
  [pattern  2B] offset 4-5
```

---

## Complete Example

This example demonstrates a full database lifecycle: create, populate, search, update, delete, and iterate.

```c
#include <psion.h>
#include <db.h>

void main() {
    int db;
    char name[20];
    char phone[16];
    int age;

    /* Step 1: Create database */
    db = db_create('A', "CONTACTS", "name$,phone$,age%");
    if (db < 0) { print("Error!"); getkey(); return; }

    /* Step 2: Add records */
    db_clear();
    db_set_str("name", "Alice");
    db_set_str("phone", "555-0001");
    db_set_int("age", 30);
    db_append();

    db_clear();
    db_set_str("name", "Bob");
    db_set_str("phone", "555-0002");
    db_set_int("age", 25);
    db_append();

    db_clear();
    db_set_str("name", "Charlie");
    db_set_str("phone", "555-0003");
    db_set_int("age", 35);
    db_append();

    /* Step 3: Iterate all records */
    db_first();
    while (!db_eof()) {
        if (db_read() == 0) {
            db_get_str("name", name, 20);
            age = db_get_int("age");
            cls();
            print(name);
            print(" age:");
            print_int(age);
            getkey();
        }
        db_next();
    }

    /* Step 4: Find a specific record */
    db_first();
    if (db_find("Bob") == 0) {
        db_read();
        db_get_str("phone", phone, 16);
        cls();
        print("Bob: ");
        print(phone);
        getkey();
    }

    /* Step 5: Update a record */
    db_first();
    if (db_find("Alice") == 0) {
        db_read();
        db_get_str("name", name, 20);
        db_get_str("phone", phone, 16);

        db_clear();
        db_set_str("name", name);
        db_set_str("phone", phone);
        db_set_int("age", 31);
        db_update();
    }

    /* Step 6: Delete a record */
    db_first();
    if (db_find("Charlie") == 0) {
        db_erase();
    }

    /* Clean up */
    db_close(db);

    cls();
    print("Done!");
    getkey();
}
```

---

## Limitations

1. **Single open file:** Only one database file can be open at a time (handle 0). Close one before opening another.
2. **Record size limit:** Maximum 254 bytes per record including TAB delimiters.
3. **Field limit:** Maximum 16 fields per record.
4. **Field name limit:** Maximum 8 characters per field name in the schema.
5. **No float support:** Float fields are not yet supported. Use string representation and manual conversion.
6. **Ascending field order:** When building records, fields must be set in ascending index order (1, 2, 3...).
7. **No buffer overflow checking:** Ensure destination buffers are large enough for field values.
8. **db_update position change:** After `db_update()`, the record position may change because the implementation erases and re-appends.

---

## Code Size

| Component | Approximate Size |
|-----------|-----------------|
| Jump table (26 entries) | ~78 bytes |
| Helper subroutines | ~350 bytes |
| File management functions | ~200 bytes |
| Record building functions | ~300 bytes |
| Record reading functions | ~250 bytes |
| Navigation functions | ~200 bytes |
| Modification functions | ~100 bytes |
| Static data buffers | ~300 bytes |
| **Total** | **~1800 bytes** |

---

## Function Summary

### File Management

| Function | Description | Returns |
|----------|-------------|---------|
| `db_create(dev, name, schema)` | Create new file | Handle or -1 |
| `db_open(dev, name, schema)` | Open existing file | Handle or -1 |
| `db_close(handle)` | Close file | - |
| `db_error()` | Get last error code | Error code |
| `db_catalog(dev, buf, max, first)` | List files on device | Length or 0 |

### Record Building

| Function | Description | Returns |
|----------|-------------|---------|
| `db_clear()` | Reset record buffer | - |
| `db_set_str(name, value)` | Set string field by name | 0 or error |
| `db_set_int(name, value)` | Set integer field by name | 0 or error |
| `db_set_idx(index, value)` | Set field by index (string) | 0 or error |
| `db_set_int_idx(index, value)` | Set integer field by index | 0 or error |
| `db_append()` | Write record to file | 0 or error |

### Record Reading

| Function | Description | Returns |
|----------|-------------|---------|
| `db_read()` | Load current record | 0 or error |
| `db_get_str(name, buf, max)` | Get string field by name | 0 or error |
| `db_get_int(name)` | Get integer field by name | Integer value |
| `db_get_idx(idx, buf, max)` | Get field by index | 0 or error |
| `db_get_int_idx(index)` | Get integer field by index | Integer value |
| `db_field_count()` | Fields in current record | Count |
| `db_recsize()` | Current record size | Bytes |

### Navigation

| Function | Description | Returns |
|----------|-------------|---------|
| `db_first()` | Move to first record | 0 or error |
| `db_next()` | Move to next record | 0 or error |
| `db_back()` | Move to previous record | 0 or error |
| `db_find(pattern)` | Find record with text | 0 or 1 |
| `db_eof()` | Check end-of-file | 1 or 0 |
| `db_count()` | Total record count | Count |
| `db_pos()` | Current position | 1-based |

### Modification

| Function | Description | Returns |
|----------|-------------|---------|
| `db_update()` | Replace current record | 0 or error |
| `db_erase()` | Delete current record | 0 or error |

---

## See Also

- [small-c-prog.md](small-c-prog.md) - Small-C Programming Manual (comprehensive guide)
- [stdlib.md](stdlib.md) - Core string functions and character classification
- [stdio.md](stdio.md) - Extended string functions (strrchr, strstr, strncat, sprintf)
- [cli-tools.md](cli-tools.md) - CLI Tools Manual (psbuild, pscc, psasm, psopk, pslink, psdisasm)
- `include/db.h` - C header file
- `include/dbruntime.inc` - Assembly implementation
- `examples/db_contacts.c` - Complete example program
