/*
 * external_return_test.c - Test OPL function return values
 * =============================================================
 *
 * This test program demonstrates calling OPL procedures that return
 * integer values back to C code.
 *
 * SETUP REQUIREMENTS:
 * -------------------
 * Before running this program, you must create the OPL procedures on the Psion:
 *
 * 1. Create GETVAL%: (returns a constant value)
 *    GETVAL%:
 *    RETURN 42
 *
 * 2. Create DOUBLE%: (reads g_input global, returns double)
 *    Note: DOUBLE% would need PEEKW to read from C's memory.
 *    For simplicity, GETVAL% demonstrates the basic return mechanism.
 *
 * BUILD COMMANDS:
 * ---------------
 * source .venv/bin/activate
 * python -m psion_sdk.cli.pscc -m LZ -I include examples/external_return_test.c -o /tmp/extret.asm
 * python -m psion_sdk.cli.psasm -r -m LZ -I include /tmp/extret.asm -o /tmp/EXTRET.ob3
 * python -m psion_sdk.cli.psopk create -o /tmp/EXTRET.opk /tmp/EXTRET.ob3
 *
 * Then load /tmp/EXTRET.opk into the emulator and run it.
 *
 * EXPECTED OUTPUT:
 * ----------------
 * Before call
 * OPL returned: 42
 * Done!
 *
 * Author: Hugo Pinto & Claude
 * Date: 2026-01-20
 */

#include <psion.h>

/*
 * Declare external OPL procedure that returns an integer.
 *
 * NOTE ON NAMING: In OPL, integer-returning procedures have names ending
 * with '%' (e.g., GETVAL%). However, '%' is not valid in C identifiers.
 *
 * WORKAROUND OPTIONS:
 * 1. Create the OPL procedure WITHOUT the '%' suffix:
 *      GETVAL:
 *      RETURN 42
 *    Then call it directly with 'external int':
 *      external int GETVAL();
 *
 * 2. Use the legacy call_opl() function with a string:
 *      int result = call_opl("GETVAL%");
 *    This allows any characters in the procedure name.
 *
 * For this test, we use option 1 - the OPL procedure is named GETVAL (no %).
 */
external int GETVAL();

void main() {
    int result;
    int local_var;

    /* Initialize local variable to verify preservation across call */
    local_var = 100;

    cls();
    print("Before call");

    /* Call OPL procedure and capture return value */
    result = GETVAL();

    /* Verify local variable was preserved */
    if (local_var != 100) {
        print("ERR:local!");
        getkey();
        return;
    }

    /* Display the return value */
    cls();
    print("Result: ");
    print_int(result);

    /* Verify it's the expected value (42 from GETVAL) */
    if (result == 42) {
        at(0, 1);
        print("SUCCESS!");
    } else {
        at(0, 1);
        print("UNEXPECTED");
    }

    getkey();
}
