/*
 * Hello World Example for Psion Organiser II
 * ===========================================
 *
 * This is a simple Small-C program that demonstrates the basic
 * features of the pscc compiler.
 *
 * To compile and run:
 *   $ pscc hello.c -o hello.asm
 *   $ psasm hello.asm -o hello.ob3
 *   $ psopk hello.ob3 -o hello.opk
 *   $ pslink hello.opk  (transfer to device)
 */

#include <psion.h>

/* Global variable to track key presses */
int count;

/*
 * display_count - Show the current count on screen
 *
 * This function demonstrates:
 * - Function definitions
 * - Function calls (cls, cursor, print_int)
 * - Global variable access
 */
void display_count() {
    cls();
    cursor(0);
    print("Count: ");
    print_int(count);
}

/*
 * main - Entry point
 *
 * This function demonstrates:
 * - Local variables
 * - While loops
 * - If/else statements
 * - Comparison operators
 * - Assignment operators
 */
void main() {
    char key;

    /* Initialize count */
    count = 0;

    /* Display welcome message */
    cls();
    print("Hello, Psion!");
    cursor(16);  /* Second line on 2x16 display */
    print("Press +/- or Q");

    /* Wait for initial key press */
    getkey();

    /* Main loop */
    while (1) {
        display_count();
        cursor(16);
        print("+/- to change");

        /* Wait for key */
        key = getkey();

        /* Handle key press */
        if (key == '+') {
            count = count + 1;
        } else if (key == '-') {
            count = count - 1;
        } else if (key == 'Q') {
            /* Exit on Q */
            break;
        }
    }

    /* Goodbye message */
    cls();
    print("Goodbye!");
    delay(50);  /* Wait 1 second */
}
