/*
 * =============================================================================
 * Floating Point Demo for Psion Organiser II
 * =============================================================================
 *
 * This example demonstrates the use of floating point functions from the
 * Psion SDK float.h library. It performs basic arithmetic and trigonometric
 * calculations to verify the FP implementation.
 *
 * Build for XP (2-line display):
 *   python -m psion_sdk.cli.pscc -I include examples/fp_demo.c -o /tmp/fp_demo.asm
 *   python -m psion_sdk.cli.psasm -r -I include /tmp/fp_demo.asm -o /tmp/FPDEMO.ob3
 *   python -m psion_sdk.cli.psopk create -o FPDEMO.opk /tmp/FPDEMO.ob3
 *
 * Build for LZ (4-line display):
 *   python -m psion_sdk.cli.pscc -m LZ -I include examples/fp_demo.c -o /tmp/fp_demo.asm
 *   python -m psion_sdk.cli.psasm -r -m LZ -I include /tmp/fp_demo.asm -o /tmp/FPDEMO.ob3
 *   python -m psion_sdk.cli.psopk create -o FPDEMO.opk /tmp/FPDEMO.ob3
 *
 * Usage:
 *   Press any key to advance through each demo screen.
 *
 * Author: Hugo José Pinto & Contributors
 * =============================================================================
 */

#include <psion.h>
#include <float.h>

/* String buffer for displaying FP values */
char strbuf[24];

/* FP working variables */
fp_t a, b, result;
fp_t pi, deg30, temp;

/*
 * wait_key - Display prompt and wait for keypress
 */
void wait_key() {
    cursor(DISP_COLS * (DISP_ROWS - 1));  /* Bottom-left */
    print("[Key]");
    getkey();
}

/*
 * Demo 1: Basic Arithmetic
 * Shows addition, subtraction, multiplication, division
 */
void demo_arithmetic() {
    cls();
    print("FP ARITHMETIC");
    delay(25);
    cls();

    /* 3.5 + 2.5 = 6.0 */
    fp_from_str(&a, "3.5");
    fp_from_str(&b, "2.5");
    fp_add(&result, &a, &b);

    cursor(0);
    print("3.5+2.5=");
    fp_print(&result, 1);
    wait_key();

    /* 10.0 - 4.3 = 5.7 */
    cls();
    fp_from_str(&a, "10.0");
    fp_from_str(&b, "4.3");
    fp_sub(&result, &a, &b);

    cursor(0);
    print("10-4.3=");
    fp_print(&result, 1);
    wait_key();

    /* 2.5 * 4.0 = 10.0 */
    cls();
    fp_from_str(&a, "2.5");
    fp_from_str(&b, "4.0");
    fp_mul(&result, &a, &b);

    cursor(0);
    print("2.5*4=");
    fp_print(&result, 1);
    wait_key();

    /* 22.0 / 7.0 = 3.142857... */
    cls();
    fp_from_str(&a, "22.0");
    fp_from_str(&b, "7.0");
    fp_div(&result, &a, &b);

    cursor(0);
    print("22/7=");
    fp_print(&result, 4);
    wait_key();
}

/*
 * Demo 2: Square Root
 * Shows sqrt() function
 */
void demo_sqrt() {
    cls();
    print("SQUARE ROOT");
    delay(25);
    cls();

    /* sqrt(2) = 1.41421... */
    fp_from_str(&a, "2.0");
    fp_sqrt(&result, &a);

    cursor(0);
    print("sqrt(2)=");
    fp_print(&result, 5);
    wait_key();

    /* sqrt(16) = 4 */
    cls();
    fp_from_int(&a, 16);
    fp_sqrt(&result, &a);

    cursor(0);
    print("sqrt(16)=");
    fp_print(&result, 1);
    wait_key();
}

/*
 * Demo 3: Trigonometry
 * Shows sin(), cos(), tan()
 */
void demo_trig() {
    cls();
    print("TRIGONOMETRY");
    delay(25);
    cls();

    /* Calculate sin(30 degrees) = 0.5 */
    /* First convert 30 degrees to radians: 30 * pi / 180 */
    fp_from_str(&pi, FP_STR_PI);
    fp_from_int(&deg30, 30);
    fp_from_int(&temp, 180);

    /* deg30 = 30 * pi / 180 */
    fp_mul(&deg30, &deg30, &pi);
    fp_div(&deg30, &deg30, &temp);

    /* Now deg30 contains 30 degrees in radians */
    fp_sin(&result, &deg30);

    cursor(0);
    print("sin(30)=");
    fp_print(&result, 4);
    wait_key();

    /* cos(30 degrees) = 0.866... */
    cls();
    fp_cos(&result, &deg30);

    cursor(0);
    print("cos(30)=");
    fp_print(&result, 4);
    wait_key();

    /* sin(0) = 0 */
    cls();
    fp_zero(&a);
    fp_sin(&result, &a);

    cursor(0);
    print("sin(0)=");
    fp_print(&result, 4);
    wait_key();

    /* cos(0) = 1 */
    cls();
    fp_cos(&result, &a);

    cursor(0);
    print("cos(0)=");
    fp_print(&result, 4);
    wait_key();
}

/*
 * Demo 4: Logarithms and Exponentials
 */
void demo_log_exp() {
    cls();
    print("LOG & EXP");
    delay(25);
    cls();

    /* e^1 = e = 2.718... */
    fp_from_str(&a, "1.0");
    fp_exp(&result, &a);

    cursor(0);
    print("e^1=");
    fp_print(&result, 4);
    wait_key();

    /* ln(e) = 1 */
    cls();
    fp_from_str(&a, FP_STR_E);  /* a = e */
    fp_ln(&result, &a);

    cursor(0);
    print("ln(e)=");
    fp_print(&result, 4);
    wait_key();

    /* log10(100) = 2 */
    cls();
    fp_from_int(&a, 100);
    fp_log(&result, &a);

    cursor(0);
    print("log(100)=");
    fp_print(&result, 4);
    wait_key();
}

/*
 * Demo 5: Power function
 */
void demo_power() {
    cls();
    print("POWER");
    delay(25);
    cls();

    /* 2^10 = 1024 */
    fp_from_int(&a, 2);
    fp_from_int(&b, 10);
    fp_pow(&result, &a, &b);

    cursor(0);
    print("2^10=");
    fp_print(&result, 0);
    wait_key();

    /* 2^0.5 = sqrt(2) = 1.41421... */
    cls();
    fp_from_int(&a, 2);
    fp_from_str(&b, "0.5");
    fp_pow(&result, &a, &b);

    cursor(0);
    print("2^0.5=");
    fp_print(&result, 5);
    wait_key();
}

/*
 * Demo 6: Random numbers
 */
void demo_random() {
    int i;

    cls();
    print("RANDOM");
    delay(25);
    cls();

    /* Show 4 random numbers */
    for (i = 0; i < 4; i++) {
        fp_rnd(&result);
        cursor(0);
        print("Rnd=");
        fp_print(&result, 6);
        wait_key();
        if (i < 3) cls();
    }
}

/*
 * Demo 7: Error handling
 */
void demo_errors() {
    cls();
    print("ERROR HANDLING");
    delay(25);
    cls();

    /* Division by zero */
    fp_clear_error();
    fp_from_int(&a, 10);
    fp_zero(&b);
    fp_div(&result, &a, &b);

    cursor(0);
    if (fp_error == FPE_DIVZERO) {
        print("10/0=DIV ERR!");
    } else {
        print("10/0=");
        fp_print(&result, 2);
    }
    wait_key();

    /* Square root of negative */
    cls();
    fp_clear_error();
    fp_from_int(&a, -1);
    fp_neg(&a);  /* Make it clearly negative */
    fp_from_str(&a, "-1.0");  /* Ensure negative */
    fp_sqrt(&result, &a);

    cursor(0);
    if (fp_error == FPE_RANGE) {
        print("sqrt(-1)=ERR!");
    } else {
        print("sqrt(-1)=");
        fp_print(&result, 2);
    }
    wait_key();
}

/*
 * Main entry point
 */
void main() {
    cls();
    print("FP DEMO");
    cursor(DISP_COLS);  /* Second line */
    print("Press key...");
    getkey();

    /* Run all demos */
    demo_arithmetic();
    demo_sqrt();
    demo_trig();
    demo_log_exp();
    demo_power();
    demo_random();
    demo_errors();

    /* Done */
    cls();
    print("DEMO COMPLETE");
    getkey();
}
