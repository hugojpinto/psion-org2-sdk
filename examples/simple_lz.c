/* Simple LZ test - verifies 4-line display mode works */
#include "psion.h"

void main() {
    int mode;

    cls();
    print("Hello LZ!");

    /* Test getmode - should return 1 on LZ in 4-line mode */
    mode = getmode();

    cursor(20);
    print("Mode: ");
    print_int(mode);

    cursor(40);
    if (mode == MODE_4LINE) {
        print("4-line OK!");
    } else {
        print("2-line mode");
    }

    cursor(60);
    print("Press any key");

    getkey();
}
