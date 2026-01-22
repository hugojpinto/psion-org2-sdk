#include <psion.h>
#include <ctype.h>
#include <stdio.h>

char g_buf[32];
int g_passed;
int g_failed;

void show_result(char *name, int pass) {
    print(name);
    print(": ");
    if (pass) {
        print("OK");
        g_passed = g_passed + 1;
    } else {
        print("FAIL");
        g_failed = g_failed + 1;
    }
}

void wait_key(void) {
    cursor(60);
    print("[KEY]");
    getkey();
    cls();
}

void test_ctype(void) {
    int pass;

    cls();
    print("CTYPE TESTS");
    cursor(20);

    /* Test isdigit */
    pass = isdigit('0') && isdigit('5') && isdigit('9');
    pass = pass && !isdigit('A') && !isdigit(' ');
    show_result("isdigit", pass);

    cursor(40);

    /* Test isupper/islower */
    pass = isupper('A') && isupper('Z') && !isupper('a');
    pass = pass && islower('a') && islower('z') && !islower('A');
    show_result("upper/low", pass);

    cursor(60);

    /* Test isalpha */
    pass = isalpha('A') && isalpha('z') && !isalpha('5');
    show_result("isalpha", pass);

    wait_key();

    cls();
    print("CTYPE TESTS 2");
    cursor(20);

    /* Test isalnum */
    pass = isalnum('A') && isalnum('5') && !isalnum(' ');
    show_result("isalnum", pass);

    cursor(40);

    /* Test case conversion */
    pass = (toupper('a') == 'A') && (toupper('z') == 'Z');
    pass = pass && (tolower('A') == 'a') && (tolower('Z') == 'z');
    show_result("case conv", pass);

    wait_key();
}

void test_runtime(void) {
    int n;
    int pass;
    char *p;

    cls();
    print("ATOI TESTS");
    cursor(20);

    n = atoi("123");
    pass = (n == 123);
    show_result("atoi 123", pass);

    cursor(40);

    n = atoi("-456");
    pass = (n == -456);
    show_result("atoi -456", pass);

    wait_key();

    cls();
    print("ITOA TESTS");
    cursor(20);

    itoa(123, g_buf);
    pass = (g_buf[0] == '1' && g_buf[1] == '2' && g_buf[2] == '3');
    show_result("itoa 123", pass);

    cursor(40);

    itoa(0, g_buf);
    pass = (g_buf[0] == '0' && g_buf[1] == 0);
    show_result("itoa 0", pass);

    wait_key();

    cls();
    print("STRCHR TEST");
    cursor(20);

    p = strchr("Hello", 'l');
    pass = (p != 0) && (*p == 'l');
    show_result("strchr l", pass);

    cursor(40);

    p = strchr("Hello", 'x');
    pass = (p == 0);
    show_result("strchr x", pass);

    wait_key();
}

void test_stdio(void) {
    char *p;
    int pass;

    cls();
    print("STRRCHR TEST");
    cursor(20);

    p = strrchr("/a/b/c", '/');
    pass = (p != 0) && (*(p+1) == 'c');
    show_result("strrchr /", pass);

    cursor(40);

    p = strrchr("file.txt", '.');
    pass = (p != 0) && (p[1] == 't');
    show_result("strrchr .", pass);

    wait_key();

    cls();
    print("STRSTR TEST");
    cursor(20);

    p = strstr("Hello World", "World");
    pass = (p != 0) && (p[0] == 'W');
    show_result("strstr fnd", pass);

    cursor(40);

    p = strstr("Hello", "XYZ");
    pass = (p == 0);
    show_result("strstr nf", pass);

    wait_key();

    cls();
    print("SPRINTF TEST");
    cursor(20);

    sprintf1(g_buf, "%d", 42);
    pass = (g_buf[0] == '4' && g_buf[1] == '2');
    show_result("sprintf d", pass);

    wait_key();
}

void main(void) {
    g_passed = 0;
    g_failed = 0;

    cls();
    print("STDLIB TEST v1.0");
    cursor(20);
    print("Press any key...");
    getkey();

    test_ctype();
    test_runtime();
    test_stdio();

    cls();
    print("=== SUMMARY ===");
    cursor(20);
    print("Passed: ");
    print_int(g_passed);
    cursor(40);
    print("Failed: ");
    print_int(g_failed);
    cursor(60);
    if (g_failed == 0) {
        print("ALL OK!");
    } else {
        print("SOME FAIL");
    }

    getkey();
}
