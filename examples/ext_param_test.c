/*
 * ext_param_test.c - Test external OPL procedure parameter passing
 *
 * This program tests calling OPL procedures with integer parameters.
 * It demonstrates the new parameter passing feature added to the Small-C
 * compiler for external OPL procedure declarations.
 *
 * Build with:
 *   python -m psion_sdk.cli.pscc -m LZ -I include examples/ext_param_test.c -o /tmp/ext_param_test.asm
 *   python -m psion_sdk.cli.psasm -r -m LZ -I include /tmp/ext_param_test.asm -o /tmp/EXTPARAM.ob3
 *   python -m psion_sdk.cli.psopk create -o EXTPARAM.opk /tmp/EXTPARAM.ob3
 *
 * Corresponding OPL procedures (must be created on Psion):
 *
 *   ADDNUM%:(a%,b%)
 *   LOCAL r%
 *   r%=a%+b%
 *   RETURN r%
 *
 *   SHOWVAL:(v%)
 *   PRINT v%
 */

#include <psion.h>

/* External OPL procedures with parameters */
external int ADDNUM(int a, int b);   /* Calls ADDNUM% with two integer params */
external void SHOWVAL(int v);         /* Calls SHOWVAL with one integer param */

void main() {
    int result;
    int x;
    int y;

    cls();

    /* Initialize test values */
    x = 10;
    y = 32;

    /* Display what we're doing */
    print("Testing params");
    at(0, 1);

    /* Call OPL procedure with two parameters and get return value */
    result = ADDNUM(x, y);

    /* Display result */
    print_int(x);
    putchar('+');
    print_int(y);
    putchar('=');
    print_int(result);

    /* Also test with literal values */
    at(0, 2);
    print("5+7=");
    result = ADDNUM(5, 7);
    print_int(result);

    /* Wait for key */
    at(0, 3);
    print("Press any key");
    getkey();
}
