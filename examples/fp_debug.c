/*
 * =============================================================================
 * Floating Point Debug Test
 * =============================================================================
 *
 * This is a minimal test to debug floating point string conversion.
 * It converts two strings to FP, adds them, and displays each step.
 *
 * Expected output:
 *   Screen 1: "A=3.5" (press key)
 *   Screen 2: "A VALUE:3.5"
 *   Screen 3: "B=2.5" (press key)
 *   Screen 4: "B VALUE:2.5"
 *   Screen 5: "ADDING..."
 *   Screen 6: "RESULT:6.0"
 *
 * Build:
 *   python -m psion_sdk.cli.pscc -m LZ -I include examples/fp_debug.c -o /tmp/fp_debug.asm
 *   python -m psion_sdk.cli.psasm -r -m LZ -I include /tmp/fp_debug.asm -o /tmp/FPDEBUG.ob3
 *   python -m psion_sdk.cli.psopk create -o /tmp/FPDEBUG.opk /tmp/FPDEBUG.ob3
 *
 * Status: WORKING - verified 2026-01-19 (guard byte offset fix)
 *
 * Author: Hugo José Pinto & Contributors
 * =============================================================================
 */

#include <psion.h>
#include <float.h>

fp_t a, b, result;

void main() {
    cls();
    print("A=3.5");
    getkey();

    fp_from_str(&a, "3.5");

    cls();
    print("A VALUE:");
    fp_print(&a, 1);
    getkey();

    cls();
    print("B=2.5");
    getkey();

    fp_from_str(&b, "2.5");

    cls();
    print("B VALUE:");
    fp_print(&b, 1);
    getkey();

    cls();
    print("ADDING...");
    fp_add(&result, &a, &b);
    getkey();

    cls();
    print("RESULT:");
    fp_print(&result, 1);
    getkey();
}
