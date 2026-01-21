/*
 * struct_demo.c - Struct Support Demonstration
 * =============================================
 *
 * This example demonstrates the struct support in Small-C for the
 * Psion Organiser II. It shows:
 *
 *   - Struct definition with different field types
 *   - Member access with . (dot) operator
 *   - Pointer member access with -> (arrow) operator
 *   - Nested structs
 *   - sizeof() with structs
 *   - struct_copy() for copying struct values
 *
 * Build for LZ (4-line display):
 *   python -m psion_sdk.cli.pscc -m LZ -I include examples/struct_demo.c -o /tmp/struct_demo.asm
 *   python -m psion_sdk.cli.psasm -r -m LZ -I include /tmp/struct_demo.asm -o /tmp/STRUCT.ob3
 *   python -m psion_sdk.cli.psopk create -o STRUCT.opk /tmp/STRUCT.ob3
 *
 * Build for XP (2-line display):
 *   python -m psion_sdk.cli.pscc -I include examples/struct_demo.c -o /tmp/struct_demo.asm
 *   python -m psion_sdk.cli.psasm -r -I include /tmp/struct_demo.asm -o /tmp/STRUCT.ob3
 *   python -m psion_sdk.cli.psopk create -o STRUCT.opk /tmp/STRUCT.ob3
 */

#include <psion.h>

/* Define a simple 2D point structure */
struct Point {
    int x;
    int y;
};

/* Define a rectangle using two points */
struct Rect {
    struct Point topLeft;
    struct Point bottomRight;
};

void main() {
    struct Point p1, p2;
    struct Point *pp;
    struct Rect r;
    int area;
    int w, h;

    /* Initialize point using dot operator */
    p1.x = 10;
    p1.y = 20;

    /* Copy struct using struct_copy */
    struct_copy(&p2, &p1, sizeof(struct Point));

    /* Modify copy */
    p2.x = 50;
    p2.y = 60;

    /* Use pointer to access struct */
    pp = &p1;
    pp->x = 15;  /* Modify via pointer */

    /* Display point values */
    print("Point p1:");
    print_int(p1.x);
    putchar(',');
    print_int(p1.y);
    cursor(20);  /* Move to line 1 (LZ: 20 cols/line) */

    print("Point p2:");
    print_int(p2.x);
    putchar(',');
    print_int(p2.y);

    getkey();
    cls();

    /* Work with nested struct */
    r.topLeft.x = 0;
    r.topLeft.y = 0;
    r.bottomRight.x = 100;
    r.bottomRight.y = 50;

    /* Calculate rectangle dimensions */
    w = r.bottomRight.x - r.topLeft.x;
    h = r.bottomRight.y - r.topLeft.y;

    /* Display rectangle info */
    print("Rect size:");
    print_int(w);
    putchar('x');
    print_int(h);
    cursor(20);  /* Move to line 1 */

    /* Show struct sizes */
    print("sizeof Point=");
    print_int(sizeof(struct Point));
    print(" Rect=");
    print_int(sizeof(struct Rect));

    getkey();
}
