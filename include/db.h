/*
 * =============================================================================
 * DB.H - Database and File Access for Psion Organiser II
 * =============================================================================
 *
 * This header provides functions for accessing the Psion's built-in database
 * system from C programs. The Psion's database stores records as TAB-delimited
 * ASCII text, supporting string and integer fields with OPL interoperability.
 *
 * USAGE:
 *   #include <psion.h>       // Core functions (must be first)
 *   #include <db.h>          // Database access (this file)
 *
 * The compiler will automatically include the necessary runtime code
 * (dbruntime.inc) when db.h is included.
 *
 * SCHEMA FORMAT:
 *   The schema string defines field names and types, comma-separated:
 *     "name$,phone$,age%"
 *
 *   Type suffixes (matching OPL conventions):
 *     $  = String field  (OPL: name$)
 *     %  = Integer field (OPL: name%)
 *
 *   You can omit names for index-only access:
 *     "$,$,%"    (3 fields: string, string, integer)
 *
 *   Pass 0 (null pointer) for raw access without schema.
 *
 * OPL INTEROPERABILITY:
 *   Files created by C are fully readable/writable by OPL and vice versa.
 *   The on-pack format is identical: TAB-delimited text records.
 *   Field ORDER and TYPES must match between C and OPL programs.
 *   Field NAMES are for C's convenience only - not stored in the file.
 *
 *   C schema "name$,phone$,age%" is equivalent to OPL:
 *     CREATE "A:CONTACTS", A, name$, phone$, age%
 *
 * EXAMPLE:
 *   void main() {
 *       int db;
 *       char name[20];
 *       int age;
 *
 *       db = db_create('A', "CONTACTS", "name$,phone$,age%");
 *       if (db < 0) { print("Error!"); getkey(); return; }
 *
 *       // Add a record
 *       db_clear();
 *       db_set_str("name", "John");
 *       db_set_str("phone", "555-1234");
 *       db_set_int("age", 42);
 *       db_append();
 *
 *       // Read it back
 *       db_first();
 *       if (db_read() == 0) {
 *           db_get_str("name", name, 20);
 *           age = db_get_int("age");
 *           cls();
 *           print(name);
 *           print(" age:");
 *           print_int(age);
 *       }
 *
 *       db_close(db);
 *       getkey();
 *   }
 *
 * CODE SIZE:
 *   Including dbruntime.inc adds approximately 1200-1600 bytes to your program
 *   plus ~300 bytes of static data buffers. Only include it if you need
 *   database access.
 *
 * ASSEMBLY USAGE:
 *   When using these functions from assembly, include dbruntime.inc:
 *     INCLUDE "psion.inc"
 *     INCLUDE "runtime.inc"
 *     INCLUDE "dbruntime.inc"    ; Include AFTER runtime.inc
 *
 *   See dbruntime.inc header for assembly macros and calling conventions.
 *
 * See: specs/11-database-file-access.md
 *
 * Author: Hugo José Pinto & Contributors
 * Part of the Psion Organiser II SDK
 * =============================================================================
 */

#ifndef _DB_H
#define _DB_H

/* Ensure psion.h is included first for basic types and functions */
#ifndef _PSION_H
#error "Please include <psion.h> before <db.h>"
#endif

/* =============================================================================
 * Configuration Constants
 * =============================================================================
 */

/* Maximum record size in bytes (Psion limit) */
#define DB_MAX_RECORD      254
/* Maximum fields per record */
#define DB_MAX_FIELDS      16
/* Maximum field name length in schema */
#define DB_MAX_FIELDNAME   8

/* =============================================================================
 * Error Codes
 * =============================================================================
 * All functions that return int use DB_OK (0) for success and a positive
 * error code for failure. Use db_error() to retrieve the last error.
 */

/* Success */
#define DB_OK              0
/* File or record not found */
#define DB_ERR_NOT_FOUND   1
/* File already exists */
#define DB_ERR_EXISTS      2
/* Pack full or record too large */
#define DB_ERR_FULL        3
/* I/O or pack error */
#define DB_ERR_IO          4
/* Invalid parameter */
#define DB_ERR_INVALID     5
/* No file is open */
#define DB_ERR_NOT_OPEN    6
/* A file is already open */
#define DB_ERR_ALREADY     7
/* End of file / no current record */
#define DB_ERR_EOF         8
/* Record buffer overflow (>254 bytes) */
#define DB_ERR_OVERFLOW    9
/* Type mismatch in schema */
#define DB_ERR_TYPE        10
/* Invalid field index or name not found */
#define DB_ERR_FIELD       11

/* =============================================================================
 * Field Type Constants (match OPL suffixes)
 * =============================================================================
 */

/* String field (OPL: name$) */
#define DB_STRING          '$'
/* Integer field (OPL: name%) */
#define DB_INT             '%'

/* =============================================================================
 * Handle Type
 * =============================================================================
 * File handle returned by db_create/db_open. Currently supports a single
 * open file (handle 0). Returns DB_INVALID on error.
 */

/* Invalid handle (error indicator) */
#define DB_INVALID         (-1)

/* =============================================================================
 * File Management Functions
 * =============================================================================
 */

/*
 * db_create - Create a new database file
 *
 * Creates a new data file on the specified device and associates a schema.
 * The schema defines field names and types for named access. The file must
 * not already exist. After creation, the file is open and positioned at the
 * start (empty - no records yet).
 *
 * Parameters:
 *   device  - Device letter: 'A' (internal), 'B' (slot B), 'C' (slot C)
 *   name    - File name (max 8 chars, uppercase recommended)
 *   schema  - Schema string defining fields (see header for format),
 *             or 0 for raw access (index-only, no type checking)
 *
 * Returns:
 *   File handle (0) on success, or DB_INVALID (-1) on error.
 *   Use db_error() to get the specific error code.
 *
 * Example (mirrors OPL: CREATE "A:CONTACTS", A, name$, phone$, age%):
 *   int db = db_create('A', "CONTACTS", "name$,phone$,age%");
 *
 * After creation, OPL can read the file:
 *   OPEN "A:CONTACTS", B, n$, p$, a%
 */
int db_create(char device, char *name, char *schema);

/*
 * db_open - Open an existing database file
 *
 * Opens an existing file and associates a schema. The schema defines how
 * fields are interpreted - it should match the structure used when the file
 * was created (same field order and types).
 *
 * Parameters:
 *   device  - Device letter: 'A', 'B', or 'C'
 *   name    - File name to open
 *   schema  - Schema string (should match file structure),
 *             or 0 for raw access (index-only)
 *
 * Returns:
 *   File handle (0) on success, or DB_INVALID (-1) on error.
 *
 * Example (mirrors OPL: OPEN "A:CONTACTS", A, name$, phone$, age%):
 *   int db = db_open('A', "CONTACTS", "name$,phone$,age%");
 *
 * NOTE: You can use different field NAMES than the original creator,
 * but the field ORDER and TYPES must match for correct data access.
 */
int db_open(char device, char *name, char *schema);

/*
 * db_close - Close the open database file
 *
 * Closes the file and releases the handle.
 *
 * Parameters:
 *   handle - File handle from db_create() or db_open()
 */
void db_close(int handle);

/*
 * db_error - Get last error code
 *
 * Returns the error code from the most recent database operation.
 * Useful for diagnosing failures after db_create/db_open return DB_INVALID.
 *
 * Returns:
 *   Error code (DB_ERR_xxx) or DB_OK if no error.
 */
int db_error(void);

/* =============================================================================
 * Record Building Functions
 * =============================================================================
 * Records are built in a buffer before writing. This matches OPL's model
 * where you assign to fields, then call APPEND.
 *
 * Fields MUST be set in order (field 1, then 2, then 3, etc.) or by
 * ascending index. Skipped fields are filled with empty strings.
 *
 * Workflow:
 *   1. db_clear()           - Reset the record buffer
 *   2. db_set_xxx(...)      - Set each field value
 *   3. db_append()          - Write the record to the file
 */

/*
 * db_clear - Clear the record buffer
 *
 * Resets the record buffer for building a new record.
 * Must be called before setting field values.
 */
void db_clear(void);

/*
 * db_set_str - Set a string field by name
 *
 * Sets a field's value in the record buffer. The field must be defined
 * in the schema. Fields must be set in ascending order (by field index).
 *
 * Parameters:
 *   name  - Field name (as defined in schema, e.g., "name")
 *   value - String value (null-terminated)
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if name not found.
 *
 * Example (equivalent to OPL: A.name$ = "John"):
 *   db_set_str("name", "John");
 */
int db_set_str(char *name, char *value);

/*
 * db_set_int - Set an integer field by name
 *
 * Sets an integer field's value. The integer is converted to ASCII
 * decimal text for storage (e.g., 42 becomes "42", -7 becomes "-7").
 *
 * Parameters:
 *   name  - Field name (should be a '%' type field in schema)
 *   value - Integer value (-32768 to 32767)
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if name not found.
 *
 * Example (equivalent to OPL: A.age% = 42):
 *   db_set_int("age", 42);
 */
int db_set_int(char *name, int value);

/*
 * db_set_idx - Set a field by index (as string)
 *
 * Sets a field by its 1-based position. Always stores as raw string.
 * Use this for raw access or when schema is not defined.
 *
 * Parameters:
 *   index - Field index (1-based, matching OPL convention)
 *   value - String value (null-terminated)
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if index out of range (>16 or <1).
 *
 * Example:
 *   db_set_idx(1, "John");      // Set first field
 *   db_set_idx(2, "555-1234");  // Set second field
 */
int db_set_idx(int index, char *value);

/*
 * db_set_int_idx - Set an integer field by index
 *
 * Like db_set_idx but converts the integer to a string first.
 *
 * Parameters:
 *   index - Field index (1-based)
 *   value - Integer value
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if index out of range.
 */
int db_set_int_idx(int index, int value);

/*
 * db_append - Append record buffer to file
 *
 * Writes the current record buffer as a new record at the end of the file.
 * The record must have been built using db_clear() + db_set_xxx() calls.
 *
 * Returns:
 *   DB_OK on success, error code otherwise.
 */
int db_append(void);

/* =============================================================================
 * Record Reading Functions
 * =============================================================================
 * Use navigation functions (db_first, db_next, etc.) to position at a
 * record, then call db_read() to load it into the buffer, then use
 * db_get_xxx() to extract field values.
 *
 * Workflow:
 *   1. db_first() or db_next() - Position at a record
 *   2. db_read()               - Load record into buffer
 *   3. db_get_xxx(...)         - Extract field values
 */

/*
 * db_read - Read current record into buffer
 *
 * Reads the record at the current position into the internal buffer.
 * Use db_get_xxx() functions to access individual field values.
 *
 * Returns:
 *   DB_OK on success, DB_ERR_EOF if no current record.
 */
int db_read(void);

/*
 * db_get_str - Get a string field by name
 *
 * Retrieves a field's value from the loaded record as a string.
 * A record must be loaded first via db_read().
 *
 * Parameters:
 *   name   - Field name (as defined in schema)
 *   buffer - Destination buffer for the value
 *   maxlen - Maximum bytes to copy (including null terminator)
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if name not found.
 *
 * Example (equivalent to OPL: n$ = A.name$):
 *   char name[20];
 *   db_get_str("name", name, 20);
 */
int db_get_str(char *name, char *buffer, int maxlen);

/*
 * db_get_int - Get an integer field by name
 *
 * Retrieves and converts a field to an integer. The field's stored text
 * is parsed as a decimal number (handles leading minus and whitespace).
 *
 * Parameters:
 *   name - Field name (should be a '%' type field in schema)
 *
 * Returns:
 *   Integer value, or 0 if field not found or not numeric.
 *
 * Example (equivalent to OPL: a% = A.age%):
 *   int age = db_get_int("age");
 */
int db_get_int(char *name);

/*
 * db_get_idx - Get a field by index (as string)
 *
 * Retrieves any field as a raw string by position.
 *
 * Parameters:
 *   index  - Field index (1-based)
 *   buffer - Destination buffer
 *   maxlen - Maximum bytes (including null terminator)
 *
 * Returns:
 *   DB_OK on success, DB_ERR_FIELD if index invalid.
 */
int db_get_idx(int index, char *buffer, int maxlen);

/*
 * db_get_int_idx - Get an integer field by index
 *
 * Retrieves and converts a field by index.
 *
 * Parameters:
 *   index - Field index (1-based)
 *
 * Returns:
 *   Integer value, or 0 if conversion fails.
 */
int db_get_int_idx(int index);

/*
 * db_field_count - Get number of fields in current record
 *
 * Returns the number of TAB-delimited fields in the most recently
 * read record (after db_read).
 *
 * Returns:
 *   Field count, or 0 if no record loaded.
 */
int db_field_count(void);

/*
 * db_recsize - Get current record size in bytes
 *
 * Returns the total size of the current record including delimiters.
 *
 * Returns:
 *   Size in bytes, or 0 if no record loaded.
 */
int db_recsize(void);

/* =============================================================================
 * Record Navigation Functions
 * =============================================================================
 * These move the file position pointer. After navigation, call db_read()
 * to load the record at the new position.
 */

/*
 * db_first - Move to first record
 *
 * Positions at the first record in the file.
 *
 * Returns:
 *   DB_OK on success, DB_ERR_EOF if file is empty.
 */
int db_first(void);

/*
 * db_next - Move to next record
 *
 * Advances to the next record.
 *
 * Returns:
 *   DB_OK on success, DB_ERR_EOF if at end of file.
 */
int db_next(void);

/*
 * db_back - Move to previous record
 *
 * Moves to the previous record.
 *
 * Returns:
 *   DB_OK on success, DB_ERR_EOF if at beginning of file.
 */
int db_back(void);

/*
 * db_find - Find record containing string
 *
 * Searches from the current position for a record containing the
 * specified text. If found, that record becomes the current position.
 *
 * Parameters:
 *   pattern - Text to search for (null-terminated)
 *
 * Returns:
 *   DB_OK if found, DB_ERR_NOT_FOUND if not found.
 */
int db_find(char *pattern);

/*
 * db_eof - Check if at end of file
 *
 * Returns:
 *   1 if at EOF (past last record), 0 otherwise.
 */
int db_eof(void);

/*
 * db_count - Get total record count
 *
 * Counts all records in the file. Note: this may iterate through
 * the entire file, so use sparingly on large files.
 *
 * Returns:
 *   Number of records, or 0 if file is empty or not open.
 */
int db_count(void);

/*
 * db_pos - Get current record position
 *
 * Returns the 1-based position of the current record.
 *
 * Returns:
 *   Current record number (1-based), or 0 if not positioned.
 */
int db_pos(void);

/* =============================================================================
 * Record Modification Functions
 * =============================================================================
 */

/*
 * db_update - Replace current record with buffer contents
 *
 * Replaces the record at the current position with the contents of the
 * record buffer (built via db_clear/db_set_xxx). Equivalent to OPL UPDATE.
 *
 * Implementation: erases old record and writes new one. Position may change.
 *
 * Returns:
 *   DB_OK on success, error code otherwise.
 */
int db_update(void);

/*
 * db_erase - Delete current record
 *
 * Removes the record at the current position. After erasure, the file
 * position advances to the next record (or EOF if last).
 * Equivalent to OPL ERASE.
 *
 * Returns:
 *   DB_OK on success, error code otherwise.
 */
int db_erase(void);

#endif /* _DB_H */
