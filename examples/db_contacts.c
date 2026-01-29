/*
 * =============================================================================
 * db_contacts.c - Contact Database Example for Psion Organiser II
 * =============================================================================
 *
 * Demonstrates the database API by creating a simple contacts database
 * with name, phone, and age fields. Shows the full lifecycle:
 *   - Creating a database with a schema
 *   - Adding records
 *   - Navigating and reading records
 *   - Finding records by text search
 *   - Updating and erasing records
 *
 * BUILD:
 *   psbuild db_contacts.c -o CONTACTS.opk
 *
 * OPL INTEROPERABILITY:
 *   This file can be read/written by OPL programs that open it with
 *   matching field order and types:
 *     OPEN "A:CONTACTS", A, name$, phone$, age%
 *
 * Author: Hugo José Pinto & Contributors
 * Part of the Psion Organiser II SDK
 * =============================================================================
 */

#include <psion.h>
#include <db.h>

/*
 * Schema string defines the record structure:
 *   - name$  : Contact name (string)
 *   - phone$ : Phone number (string)
 *   - age%   : Age (integer, stored as ASCII decimal)
 *
 * This is equivalent to OPL:
 *   CREATE "A:CONTACTS", A, name$, phone$, age%
 */

void main() {
    int db;
    char name[20];
    char phone[16];
    int age;
    int count;

    cls();
    print("Contact DB Demo");
    getkey();

    /* =========================================================================
     * Step 1: Create the database
     * =========================================================================
     * db_create opens a new file on device A: (internal RAM) with the
     * given schema. Returns 0 on success or -1 on error.
     */
    db = db_create('A', "CONTACTS", "name$,phone$,age%");
    if (db < 0) {
        cls();
        print("Create failed!");
        print_int(db_error());
        getkey();
        return;
    }

    /* =========================================================================
     * Step 2: Add records
     * =========================================================================
     * Records are built in a buffer, then appended to the file.
     * Always call db_clear() before setting fields.
     * Fields can be set by name (db_set_str/db_set_int) or by
     * index (db_set_idx/db_set_int_idx).
     */

    /* Record 1: Set fields by name */
    db_clear();
    db_set_str("name", "Alice");
    db_set_str("phone", "555-0001");
    db_set_int("age", 30);
    db_append();

    /* Record 2: Set fields by name */
    db_clear();
    db_set_str("name", "Bob");
    db_set_str("phone", "555-0002");
    db_set_int("age", 25);
    db_append();

    /* Record 3: Set fields by index (1-based) */
    db_clear();
    db_set_idx(1, "Charlie");
    db_set_idx(2, "555-0003");
    db_set_int_idx(3, 35);
    db_append();

    cls();
    print("3 records added");
    getkey();

    /* =========================================================================
     * Step 3: Read all records
     * =========================================================================
     * Navigate with db_first/db_next, load with db_read, extract
     * field values with db_get_str/db_get_int.
     */
    db_first();
    count = 0;
    while (!db_eof()) {
        if (db_read() == 0) {
            db_get_str("name", name, 20);
            age = db_get_int("age");

            cls();
            print(name);
            print(" age:");
            print_int(age);
            getkey();

            count = count + 1;
        }
        db_next();
    }

    cls();
    print("Read ");
    print_int(count);
    print(" records");
    getkey();

    /* =========================================================================
     * Step 4: Find a record by text search
     * =========================================================================
     * db_find searches from the current position for a record
     * containing the given text anywhere in any field.
     */
    db_first();
    if (db_find("Bob") == 0) {
        db_read();
        db_get_str("phone", phone, 16);
        cls();
        print("Bob's phone:");
        print(phone);
        getkey();
    }

    /* =========================================================================
     * Step 5: Update a record
     * =========================================================================
     * To update: read the record, modify fields in the buffer,
     * then call db_update to replace the current record.
     */
    db_first();
    if (db_find("Alice") == 0) {
        db_read();

        /* Rebuild the record with updated age */
        db_clear();
        db_set_str("name", "Alice");
        db_set_str("phone", "555-0001");
        db_set_int("age", 31);
        db_update();

        cls();
        print("Alice updated");
        getkey();
    }

    /* =========================================================================
     * Step 6: Erase a record
     * =========================================================================
     * db_erase removes the current record. After erasure, the position
     * advances to the next record (or EOF).
     */
    db_first();
    if (db_find("Charlie") == 0) {
        db_erase();
        cls();
        print("Charlie erased");
        getkey();
    }

    /* =========================================================================
     * Step 7: Clean up
     * =========================================================================
     */
    db_close(db);

    cls();
    print("Demo complete!");
    getkey();
}
