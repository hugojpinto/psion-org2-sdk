/*
 * Hello Emulator - A test program for the Psion SDK toolchain
 *
 * This program demonstrates running compiled C code on the emulator.
 */

#include <psion.h>

void main() {
    cls();
    print("Hello Emulator!");
    cursor(20);
    print("Psion SDK v1.0");
    cursor(40);
    print("Running on LZ64!");
    cursor(60);
    print("Press any key...");
    getkey();
}
