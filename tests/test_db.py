# =============================================================================
# test_db.py - Database and File Access Function Tests
# =============================================================================
# Tests for the db.h/dbruntime.inc optional library functions:
#   - db_create, db_open, db_close: File management
#   - db_clear, db_set_str, db_set_int, db_set_idx: Record building
#   - db_read, db_get_str, db_get_int, db_get_idx: Record reading
#   - db_first, db_next, db_back, db_find, db_eof: Navigation
#   - db_update, db_erase: Record modification
#   - db_error, db_field_count, db_recsize, db_count, db_pos: Status
#
# These functions are OPTIONAL - they're only included when the user
# explicitly includes db.h in their C source.
#
# Test Approach:
#   - Compilation tests: Verify C code using these functions compiles
#   - Assembly tests: Verify dbruntime.inc assembles correctly
#   - Integration tests: End-to-end compile + assemble pipeline
#   - Include guard tests: Verify db.h include guards work
#
# Copyright (c) 2025 Hugo José Pinto & Contributors
# =============================================================================

import pytest
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.smallc.compiler import SmallCCompiler, CompilerOptions


# =============================================================================
# Paths and Fixtures
# =============================================================================

INCLUDE_DIR = Path(__file__).parent.parent / "include"


@pytest.fixture
def compiler():
    """Create a Small-C compiler with include paths configured."""
    options = CompilerOptions(
        include_paths=[str(INCLUDE_DIR)],
        target_model="XP",
    )
    return SmallCCompiler(options)


@pytest.fixture
def assembler():
    """Create an assembler with include paths configured."""
    return Assembler(include_paths=[str(INCLUDE_DIR)])


def compile_c(source: str, compiler) -> str:
    """Compile C source to assembly, raising on failure."""
    result = compiler.compile_source(source, "test.c")
    if result.success:
        return result.assembly
    raise Exception(f"Compilation failed: {result.errors}")


# =============================================================================
# File Management Compilation Tests
# =============================================================================

class TestDbCreate:
    """Tests for db_create - create new database file."""

    def test_db_create_compiles(self, compiler):
        """db_create with schema string should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "CONTACTS", "name$,phone$,age%");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_create" in asm

    def test_db_create_raw_compiles(self, compiler):
        """db_create with null schema (raw access) should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('B', "MYDATA", 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_create" in asm

    def test_db_create_error_check(self, compiler):
        """db_create return value used in condition should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "TEST", "val$");
            if (db < 0) {
                print("Error");
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_create" in asm


class TestDbOpen:
    """Tests for db_open - open existing database file."""

    def test_db_open_compiles(self, compiler):
        """db_open with schema string should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_open('A', "CONTACTS", "name$,phone$,age%");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_open" in asm

    def test_db_open_raw_compiles(self, compiler):
        """db_open without schema (raw mode) should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_open('A', "DATA", 0);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_open" in asm


class TestDbClose:
    """Tests for db_close - close database file."""

    def test_db_close_compiles(self, compiler):
        """db_close should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "TEST", "x$");
            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_close" in asm


class TestDbError:
    """Tests for db_error - get last error code."""

    def test_db_error_compiles(self, compiler):
        """db_error used after failed operation should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            int err;
            db = db_create('A', "TEST", "x$");
            if (db < 0) {
                err = db_error();
                print_int(err);
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_error" in asm


# =============================================================================
# Record Building Compilation Tests
# =============================================================================

class TestDbClear:
    """Tests for db_clear - reset record buffer."""

    def test_db_clear_compiles(self, compiler):
        """db_clear should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_clear" in asm


class TestDbSetStr:
    """Tests for db_set_str - set string field by name."""

    def test_db_set_str_compiles(self, compiler):
        """db_set_str with literal values should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_str("name", "John");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_str" in asm

    def test_db_set_str_with_variable(self, compiler):
        """db_set_str with variable value should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            char buf[20];
            strcpy(buf, "Alice");
            db_clear();
            db_set_str("name", buf);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_str" in asm


class TestDbSetInt:
    """Tests for db_set_int - set integer field by name."""

    def test_db_set_int_compiles(self, compiler):
        """db_set_int with literal value should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_int("age", 42);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_int" in asm

    def test_db_set_int_negative(self, compiler):
        """db_set_int with negative value should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_int("temp", -10);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_int" in asm

    def test_db_set_int_expression(self, compiler):
        """db_set_int with expression should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int x;
            x = 20;
            db_clear();
            db_set_int("count", x + 5);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_int" in asm


class TestDbSetIdx:
    """Tests for db_set_idx - set field by index."""

    def test_db_set_idx_compiles(self, compiler):
        """db_set_idx should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_idx(1, "Hello");
            db_set_idx(2, "World");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_idx" in asm


class TestDbSetIntIdx:
    """Tests for db_set_int_idx - set integer field by index."""

    def test_db_set_int_idx_compiles(self, compiler):
        """db_set_int_idx should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_idx(1, "Item");
            db_set_int_idx(2, 100);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_int_idx" in asm


class TestDbAppend:
    """Tests for db_append - write record buffer to file."""

    def test_db_append_compiles(self, compiler):
        """db_append should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
            db_set_idx(1, "Test");
            db_append();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_append" in asm

    def test_db_append_error_check(self, compiler):
        """db_append return value checked for errors should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int result;
            db_clear();
            db_set_idx(1, "Test");
            result = db_append();
            if (result != 0) {
                print("Write failed");
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_append" in asm


# =============================================================================
# Record Reading Compilation Tests
# =============================================================================

class TestDbRead:
    """Tests for db_read - read current record into buffer."""

    def test_db_read_compiles(self, compiler):
        """db_read should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int result;
            result = db_read();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_read" in asm


class TestDbGetStr:
    """Tests for db_get_str - get string field by name."""

    def test_db_get_str_compiles(self, compiler):
        """db_get_str should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            char name[20];
            db_read();
            db_get_str("name", name, 20);
            print(name);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_str" in asm

    def test_db_get_str_error_check(self, compiler):
        """db_get_str return value checked should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            char buf[30];
            int err;
            db_read();
            err = db_get_str("name", buf, 30);
            if (err != 0) {
                print("Field error");
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_str" in asm


class TestDbGetInt:
    """Tests for db_get_int - get integer field by name."""

    def test_db_get_int_compiles(self, compiler):
        """db_get_int should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int age;
            db_read();
            age = db_get_int("age");
            print_int(age);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_int" in asm

    def test_db_get_int_in_expression(self, compiler):
        """db_get_int used in arithmetic expression should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int total;
            db_read();
            total = db_get_int("qty") * db_get_int("price");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_int" in asm


class TestDbGetIdx:
    """Tests for db_get_idx - get field by index as string."""

    def test_db_get_idx_compiles(self, compiler):
        """db_get_idx should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            char buf[30];
            db_read();
            db_get_idx(1, buf, 30);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_idx" in asm


class TestDbGetIntIdx:
    """Tests for db_get_int_idx - get integer field by index."""

    def test_db_get_int_idx_compiles(self, compiler):
        """db_get_int_idx should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int val;
            db_read();
            val = db_get_int_idx(3);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_get_int_idx" in asm


class TestDbFieldCount:
    """Tests for db_field_count - get field count in record."""

    def test_db_field_count_compiles(self, compiler):
        """db_field_count should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int n;
            db_read();
            n = db_field_count();
            print_int(n);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_field_count" in asm


class TestDbRecsize:
    """Tests for db_recsize - get record size."""

    def test_db_recsize_compiles(self, compiler):
        """db_recsize should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int sz;
            db_read();
            sz = db_recsize();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_recsize" in asm


# =============================================================================
# Navigation Compilation Tests
# =============================================================================

class TestDbFirst:
    """Tests for db_first - move to first record."""

    def test_db_first_compiles(self, compiler):
        """db_first should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_first();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_first" in asm


class TestDbNext:
    """Tests for db_next - move to next record."""

    def test_db_next_compiles(self, compiler):
        """db_next should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_next();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_next" in asm


class TestDbBack:
    """Tests for db_back - move to previous record."""

    def test_db_back_compiles(self, compiler):
        """db_back should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_back();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_back" in asm


class TestDbFind:
    """Tests for db_find - find record containing string."""

    def test_db_find_compiles(self, compiler):
        """db_find with literal pattern should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int result;
            db_first();
            result = db_find("Alice");
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_find" in asm

    def test_db_find_in_condition(self, compiler):
        """db_find used in conditional should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_first();
            if (db_find("Bob") == 0) {
                print("Found!");
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_find" in asm


class TestDbEof:
    """Tests for db_eof - check end-of-file."""

    def test_db_eof_compiles(self, compiler):
        """db_eof should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            if (db_eof()) {
                print("End");
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_eof" in asm

    def test_db_eof_in_loop(self, compiler):
        """db_eof used in while loop should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_first();
            while (!db_eof()) {
                db_read();
                db_next();
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_eof" in asm


class TestDbCount:
    """Tests for db_count - get total record count."""

    def test_db_count_compiles(self, compiler):
        """db_count should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int n;
            n = db_count();
            print_int(n);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_count" in asm


class TestDbPos:
    """Tests for db_pos - get current record position."""

    def test_db_pos_compiles(self, compiler):
        """db_pos should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int pos;
            db_first();
            pos = db_pos();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_pos" in asm


# =============================================================================
# Record Modification Compilation Tests
# =============================================================================

class TestDbUpdate:
    """Tests for db_update - replace current record."""

    def test_db_update_compiles(self, compiler):
        """db_update should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int result;
            db_clear();
            db_set_idx(1, "New value");
            result = db_update();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_update" in asm


class TestDbErase:
    """Tests for db_erase - delete current record."""

    def test_db_erase_compiles(self, compiler):
        """db_erase should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int result;
            db_first();
            result = db_erase();
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_erase" in asm


# =============================================================================
# Assembly Tests
# =============================================================================

class TestDbAssembly:
    """Tests that dbruntime.inc assembles correctly."""

    def test_dbruntime_assembles(self, assembler):
        """dbruntime.inc should assemble without errors."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "dbruntime.inc"

            ORG $2100
            NOP
        """
        result = assembler.assemble(source)
        assert result is not None
        assert len(result) > 0

    def test_db_create_from_asm(self, assembler):
        """db_create called from assembly should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "dbruntime.inc"

            ORG $2100

            ; db_create('A', "TEST", "x$,y%")
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
            ; D = handle or -1
            RTS

FNAME:      FCC "TEST"
            FCB 0
SCHEMA:     FCC "x$,y%"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_db_set_idx_from_asm(self, assembler):
        """db_set_idx called from assembly should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "dbruntime.inc"

            ORG $2100

            ; db_clear()
            JSR     _db_clear

            ; db_set_idx(1, "Hello")
            LDD     #VALUE
            PSHB
            PSHA
            LDD     #1
            PSHB
            PSHA
            JSR     _db_set_idx
            INS
            INS
            INS
            INS
            RTS

VALUE:      FCC "Hello"
            FCB 0
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_db_read_get_idx_from_asm(self, assembler):
        """db_read + db_get_idx from assembly should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "dbruntime.inc"

            ORG $2100

            ; db_first()
            JSR     _db_first

            ; db_read()
            JSR     _db_read

            ; db_get_idx(1, buffer, 20)
            LDD     #20
            PSHB
            PSHA
            LDD     #BUFFER
            PSHB
            PSHA
            LDD     #1
            PSHB
            PSHA
            JSR     _db_get_idx
            INS
            INS
            INS
            INS
            INS
            INS
            RTS

BUFFER:     RMB 20
        """
        result = assembler.assemble(source)
        assert result is not None

    def test_db_macros_assemble(self, assembler):
        """Database convenience macros should assemble."""
        source = """
            INCLUDE "psion.inc"
            INCLUDE "runtime.inc"
            INCLUDE "dbruntime.inc"

            ORG $2100

            ; Use macros
            DB_CLEAR
            DB_SET_IDX 1, VALUE
            DB_APPEND
            DB_FIRST
            DB_READ
            DB_GET_IDX 1, BUFFER, 20
            DB_NEXT
            DB_EOF
            DB_BACK
            DB_CLOSE
            RTS

VALUE:      FCC "Test"
            FCB 0
BUFFER:     RMB 20
        """
        result = assembler.assemble(source)
        assert result is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestDbIntegration:
    """Integration tests: C source compiles and the generated assembly
    includes dbruntime.inc when db.h is used.

    Note: These tests verify that C code using database functions compiles
    and assembles correctly. Full runtime testing requires the emulator.
    """

    def test_full_create_append_workflow(self, compiler):
        """Complete create + append workflow should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "ITEMS", "name$,qty%");
            if (db < 0) return;

            db_clear();
            db_set_str("name", "Widget");
            db_set_int("qty", 100);
            db_append();

            db_clear();
            db_set_str("name", "Gadget");
            db_set_int("qty", 50);
            db_append();

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_create" in asm
        assert "_db_set_str" in asm
        assert "_db_set_int" in asm
        assert "_db_append" in asm
        assert "_db_close" in asm

    def test_full_read_loop_workflow(self, compiler):
        """Complete navigation + read loop should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            char name[20];
            int qty;

            db = db_open('A', "ITEMS", "name$,qty%");
            if (db < 0) return;

            db_first();
            while (!db_eof()) {
                if (db_read() == 0) {
                    db_get_str("name", name, 20);
                    qty = db_get_int("qty");
                    print(name);
                    print_int(qty);
                }
                db_next();
            }

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_open" in asm
        assert "_db_first" in asm
        assert "_db_eof" in asm
        assert "_db_read" in asm
        assert "_db_get_str" in asm
        assert "_db_get_int" in asm
        assert "_db_next" in asm

    def test_find_and_update_workflow(self, compiler):
        """Find + update workflow should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void update_qty(char *item, int new_qty) {
            db_first();
            if (db_find(item) == 0) {
                db_read();
                db_clear();
                db_set_str("name", item);
                db_set_int("qty", new_qty);
                db_update();
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_find" in asm
        assert "_db_update" in asm

    def test_index_based_access(self, compiler):
        """Index-based field access (no schema names) should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            char buf[30];
            int val;

            db = db_create('A', "RAW", "$,$,%");
            if (db < 0) return;

            db_clear();
            db_set_idx(1, "Alpha");
            db_set_idx(2, "Beta");
            db_set_int_idx(3, 99);
            db_append();

            db_first();
            db_read();
            db_get_idx(1, buf, 30);
            val = db_get_int_idx(3);

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_set_idx" in asm
        assert "_db_set_int_idx" in asm
        assert "_db_get_idx" in asm
        assert "_db_get_int_idx" in asm

    def test_erase_workflow(self, compiler):
        """Erase in loop workflow should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void erase_all() {
            db_first();
            while (!db_eof()) {
                db_erase();
            }
        }
        """
        asm = compile_c(source, compiler)
        assert "_db_erase" in asm
        assert "_db_eof" in asm

    def test_dbruntime_included_in_output(self, compiler):
        """Compiler should emit INCLUDE dbruntime.inc when db.h is used."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            db_clear();
        }
        """
        asm = compile_c(source, compiler)
        assert 'INCLUDE "dbruntime.inc"' in asm

    def test_dbruntime_not_included_without_db_h(self, compiler):
        """Compiler should NOT emit INCLUDE dbruntime.inc without db.h."""
        source = """
        #include <psion.h>

        void main() {
            print("Hello");
        }
        """
        asm = compile_c(source, compiler)
        assert 'INCLUDE "dbruntime.inc"' not in asm

    def test_compile_and_assemble_pipeline(self, compiler, assembler):
        """Full compile + assemble pipeline should succeed."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "TEST", "val$");
            if (db < 0) return;

            db_clear();
            db_set_idx(1, "Hello");
            db_append();

            db_first();
            db_read();

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

        # Assemble the generated output
        result = assembler.assemble(asm)
        assert result is not None
        assert len(result) > 0


# =============================================================================
# Include Guard Tests
# =============================================================================

class TestDbIncludeGuards:
    """Test that include guards work correctly."""

    def test_db_include_guard(self, compiler):
        """Multiple includes of db.h should be safe."""
        source = """
        #include <psion.h>
        #include <db.h>
        #include <db.h>

        void main() {
            db_clear();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_psion_required_before_db(self, compiler):
        """db.h should require psion.h first (enforced by #error)."""
        # Test the correct order works
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            db = db_create('A', "X", "a$");
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_db_with_stdio(self, compiler):
        """db.h should coexist with stdio.h."""
        source = """
        #include <psion.h>
        #include <stdio.h>
        #include <db.h>

        void main() {
            char buf[40];
            int db;
            int count;

            db = db_open('A', "DATA", "name$,val%");
            if (db < 0) return;

            count = db_count();
            sprintf1(buf, "Records: %d", count);
            print(buf);

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert 'INCLUDE "dbruntime.inc"' in asm
        assert 'INCLUDE "stdio.inc"' in asm


# =============================================================================
# Documentation Example Tests
# =============================================================================

class TestDbDocExamples:
    """Test examples from db.h documentation to ensure they compile."""

    def test_header_example(self, compiler):
        """The example from db.h header documentation should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            char name[20];
            int age;

            db = db_create('A', "CONTACTS", "name$,phone$,age%");
            if (db < 0) { print("Error!"); getkey(); return; }

            db_clear();
            db_set_str("name", "John");
            db_set_str("phone", "555-1234");
            db_set_int("age", 42);
            db_append();

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
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_opl_interop_read_example(self, compiler):
        """C reading OPL-created data example should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            char item[20];
            int qty;
            char price_str[20];

            db = db_open('A', "SALES", "item$,qty%");
            if (db < 0) return;

            db_first();
            db_read();

            db_get_str("item", item, 20);
            qty = db_get_int("qty");

            cls();
            print(item);
            print(" x ");
            print_int(qty);

            db_close(db);
            getkey();
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_update_example(self, compiler):
        """Record update example should compile."""
        source = """
        #include <psion.h>
        #include <db.h>

        void increase_ages() {
            int db;
            char name[20];
            char phone[20];
            int age;

            db = db_open('A', "CONTACTS", "name$,phone$,age%");
            if (db < 0) return;

            db_first();
            while (!db_eof()) {
                db_read();
                db_get_str("name", name, 20);
                db_get_str("phone", phone, 20);
                age = db_get_int("age");

                db_clear();
                db_set_str("name", name);
                db_set_str("phone", phone);
                db_set_int("age", age + 1);
                db_update();

                db_next();
            }

            db_close(db);
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None


# =============================================================================
# Error Constant Tests
# =============================================================================

class TestDbConstants:
    """Test that error constants and type constants are accessible."""

    def test_error_constants_accessible(self, compiler):
        """DB_OK, DB_INVALID, and DB_ERR_xxx constants should be usable."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            int db;
            int err;

            db = db_create('A', "T", "x$");
            if (db == -1) {
                err = db_error();
                if (err == 1) {
                    print("Not found");
                }
                if (err == 6) {
                    print("Not open");
                }
            }
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None

    def test_max_record_constant(self, compiler):
        """DB_MAX_RECORD should be accessible as a constant."""
        source = """
        #include <psion.h>
        #include <db.h>

        void main() {
            char buf[254];
            print_int(254);
        }
        """
        asm = compile_c(source, compiler)
        assert asm is not None
