/*
 * Runtime Library Test Suite for Psion Organiser II (4-Line Display)
 * ===================================================================
 *
 * Comprehensive visual tests for all C runtime functions.
 * This version is designed for LZ/LZ64 4-line (20x4) displays.
 * Each test displays its name and PASS/FAIL result.
 * Press any key to advance to the next test.
 *
 * Build:
 *   pscc examples/runtime_test_4line.c -o /tmp/rtest4.asm -I include
 *   psasm -r -I include /tmp/rtest4.asm -o /tmp/RTEST4.ob3
 *   psopk create -o RTEST4.opk /tmp/RTEST4.ob3
 *
 * Note: This program requires an LZ or LZ64 machine with 4-line display.
 *       Running on CM/XP will cause undefined behavior.
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
    /* Line 1: Test name */
    print(name);

    /* Line 2: Result with visual indicator */
    cursor(20);
    if (pass) {
        print("Result: [PASS]");
        passed = passed + 1;
    } else {
        print("Result: ** FAIL **");
        failed = failed + 1;
    }

    /* Line 3: Running totals */
    cursor(40);
    print("Pass:");
    print_int(passed);
    at(50, "Fail:");
    print_int(failed);

    /* Line 4: Prompt */
    cursor(60);
    print("Press any key...");
    getkey();
}

/* Display a section header */
void section(char *title) {
    cls();
    /* Line 1: Section decoration */
    print("====================");

    /* Line 2: Section title */
    cursor(20);
    print(title);

    /* Line 3: Section decoration */
    cursor(40);
    print("====================");

    /* Line 4: Prompt */
    cursor(60);
    print("Press any key...");
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
    show_result("strlen(\"Hello\")", len == 5);

    /* Test 2: Empty string */
    buf1[0] = 0;
    len = strlen(buf1);
    show_result("strlen(\"\")", len == 0);

    /* Test 3: Longer string */
    strcpy(buf1, "Hello, Psion!");
    len = strlen(buf1);
    show_result("strlen(13 chars)", len == 13);
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
    show_result("strcpy buf to buf", ok);

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
    show_result("strcat len=10", len == 10);

    /* Test 2: Verify content */
    result = strcmp(buf1, "HelloWorld");
    show_result("strcat content", result == 0);

    /* Test 3: Concatenate to empty */
    buf1[0] = 0;
    strcat(buf1, "Test");
    result = strcmp(buf1, "Test");
    show_result("strcat to empty", result == 0);
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
    show_result("memset fill 'A'", ok);

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
    show_result("abs(42) = 42", result == 42);

    /* Test 2: Negative number */
    result = abs(-42);
    show_result("abs(-42) = 42", result == 42);

    /* Test 3: Zero */
    result = abs(0);
    show_result("abs(0) = 0", result == 0);

    /* Test 4: Large negative */
    result = abs(-1000);
    show_result("abs(-1000)=1000", result == 1000);
}

void test_min() {
    /* Test 1: First smaller */
    result = min(10, 20);
    show_result("min(10,20)=10", result == 10);

    /* Test 2: Second smaller */
    result = min(30, 15);
    show_result("min(30,15)=15", result == 15);

    /* Test 3: Equal values */
    result = min(25, 25);
    show_result("min(25,25)=25", result == 25);

    /* Test 4: Negative numbers */
    result = min(-5, -10);
    show_result("min(-5,-10)=-10", result == -10);

    /* Test 5: Mixed signs */
    result = min(-5, 5);
    show_result("min(-5,5)=-5", result == -5);
}

void test_max() {
    /* Test 1: Second larger */
    result = max(10, 20);
    show_result("max(10,20)=20", result == 20);

    /* Test 2: First larger */
    result = max(30, 15);
    show_result("max(30,15)=30", result == 30);

    /* Test 3: Equal values */
    result = max(25, 25);
    show_result("max(25,25)=25", result == 25);

    /* Test 4: Negative numbers */
    result = max(-5, -10);
    show_result("max(-5,-10)=-5", result == -5);

    /* Test 5: Mixed signs */
    result = max(-5, 5);
    show_result("max(-5,5)=5", result == 5);
}

/* =========================================================================
 * DISPLAY FUNCTION TESTS
 * ========================================================================= */

void test_display() {
    /* Test 1: cls and 4-line layout */
    cls();
    print("Line 1: Top row");
    cursor(20);
    print("Line 2: Second row");
    cursor(40);
    print("Line 3: Third row");
    cursor(60);
    print("Line 4: Bottom row");
    getkey();

    /* Test 2: print_int across lines */
    cls();
    print("print_int test:");
    cursor(20);
    print("Positive: ");
    print_int(12345);
    cursor(40);
    print("Negative: ");
    print_int(-9876);
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 3: print_uint */
    cls();
    print("print_uint test:");
    cursor(20);
    print("Value: ");
    print_uint(65535);
    cursor(40);
    print("(max 16-bit)");
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 4: print_hex */
    cls();
    print("print_hex test:");
    cursor(20);
    print("0x1234 = ");
    print_hex(0x1234);
    cursor(40);
    print("0xABCD = ");
    print_hex(0xABCD);
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 5: at function with 4 lines */
    cls();
    at(0, "at(0,...)");
    at(20, "at(20,...)");
    at(40, "at(40,...)");
    at(60, "at(60,...)");
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
    print("Keyboard Test");
    cursor(20);
    print("Press any key for");
    cursor(40);
    print("getkey() test...");
    k = getkey();
    cls();
    print("You pressed: ");
    buf1[0] = k;
    buf1[1] = 0;
    at(13, buf1);
    cursor(20);
    print("ASCII code: ");
    print_int(k);
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 2: kbhit when no key pressed */
    flushkb();
    hit = kbhit();
    show_result("kbhit() empty=0", hit == 0);

    /* Test 3: flushkb */
    cls();
    print("flushkb() test");
    cursor(20);
    print("Buffer flushed OK");
    cursor(60);
    print("Press any key...");
    flushkb();
    getkey();
}

/* =========================================================================
 * SOUND FUNCTION TESTS
 * ========================================================================= */

void test_sound() {
    /* Test 1: alarm */
    cls();
    print("Sound Test: alarm()");
    cursor(20);
    print("Playing alarm...");
    cursor(60);
    print("Press any key...");
    alarm();
    getkey();

    /* Test 2: tone low */
    cls();
    print("tone(50, 20)");
    cursor(20);
    print("Low frequency tone");
    cursor(60);
    print("Press any key...");
    tone(50, 20);
    getkey();

    /* Test 3: tone high */
    cls();
    print("tone(200, 20)");
    cursor(20);
    print("High frequency tone");
    cursor(60);
    print("Press any key...");
    tone(200, 20);
    getkey();

    /* Test 4: tone sequence */
    cls();
    print("Tone Sequence");
    cursor(20);
    print("Playing 3 notes...");
    cursor(40);
    print("Low -> Mid -> High");
    tone(100, 10);
    delay(5);
    tone(150, 10);
    delay(5);
    tone(200, 10);
    cursor(60);
    print("Press any key...");
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
    cursor(20);
    print("Waiting ~2.5 sec...");
    delay(50);
    cursor(40);
    print("Delay complete!");
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 2: getticks changes */
    cls();
    print("getticks() test");
    cursor(20);
    print("Measuring ticks...");
    t1 = getticks();
    delay(20);  /* Wait ~1 second */
    t2 = getticks();
    cursor(40);
    print("Elapsed: ");
    print_int(t2 - t1);
    at(55, "ticks");
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test 3: gettime */
    cls();
    print("gettime() test");
    cursor(20);
    print("Current time:");
    gettime(timebuf);
    cursor(40);
    /* Display hours:minutes:seconds */
    print_int(timebuf[3]);  /* Hours */
    putchar(':');
    if (timebuf[4] < 10) putchar('0');
    print_int(timebuf[4]);  /* Minutes */
    putchar(':');
    if (timebuf[5] < 10) putchar('0');
    print_int(timebuf[5]);  /* Seconds */
    cursor(60);
    print("Press any key...");
    getkey();
}

/* =========================================================================
 * DISPLAY MODE TEST (LZ specific)
 * ========================================================================= */

void test_displaymode() {
    int mode;

    /* Show current mode */
    cls();
    print("Display Mode Test");
    cursor(20);
    print("Current mode: ");
    mode = getmode();
    print_int(mode);
    if (mode == 1) {
        at(35, "(4-line)");
    } else {
        at(35, "(2-line)");
    }
    cursor(60);
    print("Press any key...");
    getkey();

    /* Test pushmode/popmode */
    cls();
    print("pushmode/popmode test");
    cursor(20);
    print("Saving current mode");
    pushmode();
    cursor(40);
    print("Mode saved to stack");
    cursor(60);
    print("Press any key...");
    getkey();

    cls();
    print("Restoring mode...");
    popmode();
    /* Note: popmode() may trigger clock display on Psion OS, so clear screen */
    cls();
    print("Mode restored!");
    cursor(40);
    mode = getmode();
    print("Mode is now: ");
    print_int(mode);
    cursor(60);
    print("Press any key...");
    getkey();
}

/* =========================================================================
 * MAIN TEST RUNNER
 * ========================================================================= */

void main() {
    passed = 0;
    failed = 0;

    /* Ensure 4-line mode.
     * Note: When built with -m LZ, the STOP+SIN prefix in the OB3 file
     * tells the LZ OS to stay in 4-line mode automatically. This setmode()
     * call is kept for PORTABLE builds where manual mode switching is needed.
     * It's harmless when the prefix is present.
     */
    setmode(MODE_4LINE);

    /* Welcome screen */
    cls();
    print("Runtime Test Suite");
    cursor(20);
    print("4-Line Display Ver.");
    cursor(40);
    print("For LZ/LZ64 only");
    cursor(60);
    print("Press any key...");
    getkey();

    /* Display mode tests (LZ specific) */
    section("DISPLAY MODE TEST");
    test_displaymode();

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

    /* Final summary - use all 4 lines */
    cls();
    print("====================");
    cursor(20);
    print("  TESTS COMPLETE!");
    cursor(40);
    print("Pass: ");
    print_int(passed);
    at(50, "Fail: ");
    print_int(failed);
    cursor(60);
    if (failed == 0) {
        print("All tests PASSED!");
    } else {
        print("Some tests FAILED");
    }
    getkey();

    /* Exit message */
    cls();
    print("Runtime Test Suite");
    cursor(20);
    print("4-Line Version");
    cursor(40);
    print("Exiting...");
    cursor(60);
    print("Press any key...");
    getkey();

    exit();
}
