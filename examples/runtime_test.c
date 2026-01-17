/*
 * Runtime Library Test Suite for Psion Organiser II
 * =================================================
 *
 * Comprehensive visual tests for all C runtime functions.
 * Each test displays its name and PASS/FAIL result.
 * Press any key to advance to the next test.
 *
 * Build:
 *   pscc examples/runtime_test.c -o /tmp/runtime_test.asm -I include
 *   psasm -r -I include /tmp/runtime_test.asm -o /tmp/RTEST.ob3
 *   psopk create -o RTEST.opk /tmp/RTEST.ob3
 */

#include <psion.h>

/* Test buffers and variables */
char buf1[24];
char buf2[24];
char buf3[24];
char timebuf[8];

int passed;
int failed;
int result;
int a;
int b;

/* Display test result and wait for keypress */
void show_result(char *name, int pass) {
    cls();
    print(name);
    cursor(16);
    if (pass) {
        print("PASS");
        passed = passed + 1;
    } else {
        print("** FAIL **");
        failed = failed + 1;
    }
    getkey();
}

/* Display a section header */
void section(char *title) {
    cls();
    print("-- ");
    at(3, title);
    cursor(16);
    print("Press any key");
    getkey();
}

/* =========================================================================
 * STRING FUNCTION TESTS
 * ========================================================================= */

void test_strlen() {
    int len;

    /* Test 1: Normal string */
    strcpy(buf1, "Hello");
    len = strlen(buf1);
    show_result("strlen basic", len == 5);

    /* Test 2: Empty string */
    buf1[0] = 0;
    len = strlen(buf1);
    show_result("strlen empty", len == 0);

    /* Test 3: Longer string */
    strcpy(buf1, "Hello, Psion!");
    len = strlen(buf1);
    show_result("strlen long", len == 13);
}

void test_strcpy() {
    int ok;

    /* Test 1: Basic copy */
    strcpy(buf1, "Test");
    ok = (buf1[0] == 'T') && (buf1[4] == 0);
    show_result("strcpy basic", ok);

    /* Test 2: Copy to different buffer */
    strcpy(buf2, buf1);
    ok = (buf2[0] == 'T') && (buf2[3] == 't');
    show_result("strcpy buf2buf", ok);

    /* Test 3: Empty string */
    buf1[0] = 0;
    strcpy(buf2, buf1);
    show_result("strcpy empty", buf2[0] == 0);
}

void test_strcmp() {
    /* Test 1: Equal strings */
    strcpy(buf1, "ABC");
    strcpy(buf2, "ABC");
    result = strcmp(buf1, buf2);
    show_result("strcmp equal", result == 0);

    /* Test 2: First less than second */
    strcpy(buf1, "ABC");
    strcpy(buf2, "ABD");
    result = strcmp(buf1, buf2);
    show_result("strcmp less", result < 0);

    /* Test 3: First greater than second */
    strcpy(buf1, "ABD");
    strcpy(buf2, "ABC");
    result = strcmp(buf1, buf2);
    show_result("strcmp greater", result > 0);

    /* Test 4: Different lengths */
    strcpy(buf1, "AB");
    strcpy(buf2, "ABC");
    result = strcmp(buf1, buf2);
    show_result("strcmp shorter", result < 0);
}

void test_strcat() {
    int len;

    /* Test 1: Basic concatenation */
    strcpy(buf1, "Hello");
    strcat(buf1, "World");
    len = strlen(buf1);
    show_result("strcat basic", len == 10);

    /* Test 2: Verify content */
    result = strcmp(buf1, "HelloWorld");
    show_result("strcat verify", result == 0);

    /* Test 3: Concatenate to empty */
    buf1[0] = 0;
    strcat(buf1, "Test");
    result = strcmp(buf1, "Test");
    show_result("strcat empty", result == 0);
}

/* =========================================================================
 * MEMORY FUNCTION TESTS
 * ========================================================================= */

void test_memset() {
    int ok;
    int i;

    /* Test 1: Fill with value */
    memset(buf1, 65, 5);  /* Fill with 'A' */
    buf1[5] = 0;
    ok = (buf1[0] == 65) && (buf1[4] == 65);
    show_result("memset fill", ok);

    /* Test 2: Fill with zero */
    strcpy(buf1, "XXXXX");
    memset(buf1, 0, 3);
    ok = (buf1[0] == 0) && (buf1[3] == 'X');
    show_result("memset zero", ok);
}

void test_memcpy() {
    int ok;

    /* Test 1: Basic copy */
    strcpy(buf1, "Source");
    memset(buf2, 0, 10);
    memcpy(buf2, buf1, 6);
    ok = (buf2[0] == 'S') && (buf2[5] == 'e');
    show_result("memcpy basic", ok);

    /* Test 2: Partial copy */
    strcpy(buf1, "ABCDEFGH");
    memset(buf2, 'X', 10);
    memcpy(buf2, buf1, 3);
    ok = (buf2[0] == 'A') && (buf2[2] == 'C') && (buf2[3] == 'X');
    show_result("memcpy partial", ok);
}

void test_memcmp() {
    /* Test 1: Equal memory */
    strcpy(buf1, "ABCD");
    strcpy(buf2, "ABCD");
    result = memcmp(buf1, buf2, 4);
    show_result("memcmp equal", result == 0);

    /* Test 2: First less */
    strcpy(buf1, "ABCD");
    strcpy(buf2, "ABCE");
    result = memcmp(buf1, buf2, 4);
    show_result("memcmp less", result < 0);

    /* Test 3: First greater */
    strcpy(buf1, "ABCE");
    strcpy(buf2, "ABCD");
    result = memcmp(buf1, buf2, 4);
    show_result("memcmp greater", result > 0);

    /* Test 4: Partial compare (only first 2 bytes) */
    strcpy(buf1, "ABXX");
    strcpy(buf2, "ABYY");
    result = memcmp(buf1, buf2, 2);
    show_result("memcmp partial", result == 0);
}

/* =========================================================================
 * MATH FUNCTION TESTS
 * ========================================================================= */

void test_abs() {
    /* Test 1: Positive number */
    result = abs(42);
    show_result("abs positive", result == 42);

    /* Test 2: Negative number */
    result = abs(-42);
    show_result("abs negative", result == 42);

    /* Test 3: Zero */
    result = abs(0);
    show_result("abs zero", result == 0);

    /* Test 4: Large negative */
    result = abs(-1000);
    show_result("abs -1000", result == 1000);
}

void test_min() {
    /* Test 1: First smaller */
    result = min(10, 20);
    show_result("min(10,20)", result == 10);

    /* Test 2: Second smaller */
    result = min(30, 15);
    show_result("min(30,15)", result == 15);

    /* Test 3: Equal values */
    result = min(25, 25);
    show_result("min equal", result == 25);

    /* Test 4: Negative numbers */
    result = min(-5, -10);
    show_result("min negative", result == -10);

    /* Test 5: Mixed signs */
    result = min(-5, 5);
    show_result("min mixed", result == -5);
}

void test_max() {
    /* Test 1: Second larger */
    result = max(10, 20);
    show_result("max(10,20)", result == 20);

    /* Test 2: First larger */
    result = max(30, 15);
    show_result("max(30,15)", result == 30);

    /* Test 3: Equal values */
    result = max(25, 25);
    show_result("max equal", result == 25);

    /* Test 4: Negative numbers */
    result = max(-5, -10);
    show_result("max negative", result == -5);

    /* Test 5: Mixed signs */
    result = max(-5, 5);
    show_result("max mixed", result == 5);
}

/* =========================================================================
 * DISPLAY FUNCTION TESTS
 * ========================================================================= */

void test_display() {
    /* Test 1: cls and print */
    cls();
    print("Display Test 1");
    cursor(16);
    print("cls+print OK?");
    getkey();

    /* Test 2: cursor positioning */
    cls();
    print("XXXXXXXXXXXXXXXX");
    cursor(4);
    print("Cursor");
    cursor(16);
    print("See 'XXXXCursor'?");
    getkey();

    /* Test 3: at function */
    cls();
    at(0, "Line 1 text");
    at(16, "Line 2 text");
    getkey();

    /* Test 4: print_int positive */
    cls();
    print("print_int: ");
    print_int(12345);
    cursor(16);
    print("Shows 12345?");
    getkey();

    /* Test 5: print_int negative */
    cls();
    print("print_int: ");
    print_int(-9876);
    cursor(16);
    print("Shows -9876?");
    getkey();

    /* Test 6: print_uint */
    cls();
    print("print_uint: ");
    print_uint(65535);
    cursor(16);
    print("Shows 65535?");
    getkey();

    /* Test 7: print_hex */
    cls();
    print("print_hex: ");
    print_hex(0x1234);
    cursor(16);
    print("Shows 1234?");
    getkey();

    /* Test 8: print_hex with letters */
    cls();
    print("print_hex: ");
    print_hex(0xABCD);
    cursor(16);
    print("Shows ABCD?");
    getkey();
}

/* =========================================================================
 * KEYBOARD FUNCTION TESTS
 * ========================================================================= */

void test_keyboard() {
    char k;
    int hit;

    /* Test 1: getkey */
    cls();
    print("Press any key");
    cursor(16);
    print("for getkey test");
    k = getkey();
    cls();
    print("You pressed: ");
    buf1[0] = k;
    buf1[1] = 0;
    at(13, buf1);
    cursor(16);
    print("Correct? Y/N");
    getkey();

    /* Test 2: kbhit when no key pressed */
    flushkb();
    hit = kbhit();
    show_result("kbhit empty", hit == 0);

    /* Test 3: flushkb */
    cls();
    print("flushkb test");
    cursor(16);
    print("(auto-pass)");
    flushkb();
    getkey();
}

/* =========================================================================
 * SOUND FUNCTION TESTS
 * ========================================================================= */

void test_sound() {
    /* Test 1: alarm */
    cls();
    print("alarm() test");
    cursor(16);
    print("Hear beep?");
    alarm();
    getkey();

    /* Test 2: tone low */
    cls();
    print("tone(50,20)");
    cursor(16);
    print("Low tone?");
    tone(50, 20);
    getkey();

    /* Test 3: tone high */
    cls();
    print("tone(200,20)");
    cursor(16);
    print("High tone?");
    tone(200, 20);
    getkey();

    /* Test 4: tone sequence */
    cls();
    print("Tone sequence");
    cursor(16);
    print("3 notes...");
    tone(100, 10);
    delay(5);
    tone(150, 10);
    delay(5);
    tone(200, 10);
    getkey();
}

/* =========================================================================
 * TIME FUNCTION TESTS
 * ========================================================================= */

void test_time() {
    int t1;
    int t2;

    /* Test 1: delay */
    cls();
    print("delay(50) test");
    cursor(16);
    print("~2.5 sec pause");
    delay(50);
    cls();
    print("Delay done!");
    cursor(16);
    print("Felt ~2.5 sec?");
    getkey();

    /* Test 2: getticks changes */
    cls();
    print("getticks test");
    cursor(16);
    print("Reading...");
    t1 = getticks();
    delay(20);  /* Wait ~1 second */
    t2 = getticks();
    cls();
    print("Ticks changed:");
    cursor(16);
    print_int(t2 - t1);
    at(22, " (~6)");  /* delay uses 32Hz, tick counter runs at ~10Hz */
    getkey();

    /* Test 3: gettime */
    cls();
    print("gettime test");
    cursor(16);
    print("Reading clock...");
    gettime(timebuf);
    cls();
    print("Time: ");
    /* Display hours:minutes */
    print_int(timebuf[3]);  /* Hours */
    at(9, ":");
    if (timebuf[4] < 10) {
        at(10, "0");
        cursor(11);
    } else {
        cursor(10);
    }
    print_int(timebuf[4]);  /* Minutes */
    cursor(16);
    print("Correct time?");
    getkey();
}

/* =========================================================================
 * MAIN TEST RUNNER
 * ========================================================================= */

void main() {
    passed = 0;
    failed = 0;

    /* Welcome screen */
    cls();
    print("Runtime Tests");
    cursor(16);
    print("Press any key");
    getkey();

    /* String function tests */
    section("STRING TESTS");
    test_strlen();
    test_strcpy();
    test_strcmp();
    test_strcat();

    /* Memory function tests */
    section("MEMORY TESTS");
    test_memset();
    test_memcpy();
    test_memcmp();

    /* Math function tests */
    section("MATH TESTS");
    test_abs();
    test_min();
    test_max();

    /* Display function tests */
    section("DISPLAY TESTS");
    test_display();

    /* Keyboard function tests */
    section("KEYBOARD TESTS");
    test_keyboard();

    /* Sound function tests */
    section("SOUND TESTS");
    test_sound();

    /* Time function tests */
    section("TIME TESTS");
    test_time();

    /* Final summary */
    cls();
    print("Tests Complete!");
    cursor(16);
    print("P:");
    print_int(passed);
    at(22, " F:");
    print_int(failed);
    getkey();

    /* Exit message */
    cls();
    if (failed == 0) {
        print("All tests PASS!");
    } else {
        print("Some tests FAIL");
    }
    cursor(16);
    print("Press key exit");
    getkey();

    exit();
}
