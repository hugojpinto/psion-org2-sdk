/*
 * CATCH4 - A UDG game for Psion Organiser II LZ/LZ64
 *
 * 4-line version with falling stars!
 * Stars move on row 1, then drop to row 3.
 * Use LEFT/RIGHT cursor keys to move paddle.
 */

#include <psion.h>

/* UDG character codes */
#define STAR   0
#define PADDLE 1

/* Psion key codes */
#define KEY_LEFT  5
#define KEY_RIGHT 6

/* Game constants for 4-line display (20x4) */
#define SCREEN_WIDTH 20
#define PADDLE_MIN   0
#define PADDLE_MAX   19
#define STAR_MIN     10
#define STAR_MAX     19
#define ROW0         0   /* Score row */
#define ROW1         20  /* Star row */
#define ROW3         60  /* Paddle row */
#define MAX_LIVES    3
#define MOVE_DELAY   5
#define DROP_STEPS   4

/* UDG bitmap buffers */
char star_data[8];
char paddle_data[8];

/* Game state - all globals */
int score;
int lives;
int paddle_x;
int star_x;
int star_dir;
int star_steps;
int game_over;
int seed;
int caught;
int key;

/* Initialize UDGs */
void init_graphics() {
    star_data[0] = 0x04;
    star_data[1] = 0x04;
    star_data[2] = 0x1F;
    star_data[3] = 0x0E;
    star_data[4] = 0x0E;
    star_data[5] = 0x15;
    star_data[6] = 0x04;
    star_data[7] = 0x00;

    paddle_data[0] = 0x00;
    paddle_data[1] = 0x11;
    paddle_data[2] = 0x11;
    paddle_data[3] = 0x1F;
    paddle_data[4] = 0x1F;
    paddle_data[5] = 0x1F;
    paddle_data[6] = 0x0E;
    paddle_data[7] = 0x00;

    udg_define(STAR, star_data);
    udg_define(PADDLE, paddle_data);
}

/* Draw score */
void draw_score() {
    cursor(ROW0);
    print("S:");
    print_int(score);
    cursor(ROW0 + 10);
    print("L:");
    print_int(lives);
}

/* Draw star on row 1 */
void draw_star() {
    cursor(ROW1 + star_x);
    putchar(STAR);
}

/* Clear star from row 1 */
void clear_star() {
    cursor(ROW1 + star_x);
    putchar(' ');
}

/* Draw paddle on row 3 */
void draw_paddle() {
    cursor(ROW3 + paddle_x);
    putchar(PADDLE);
}

/* Clear paddle */
void clear_paddle() {
    cursor(ROW3 + paddle_x);
    putchar(' ');
}

/* Random 0-1 */
int rand2() {
    seed = seed + 1;
    if (seed >= 2) {
        seed = 0;
    }
    return seed;
}

/* Random 0-3 */
int rand4() {
    seed = seed + 1;
    if (seed >= 4) {
        seed = 0;
    }
    return seed;
}

/* Handle input */
void check_input() {
    key = testkey();

    if (key == KEY_LEFT) {
        if (paddle_x > PADDLE_MIN) {
            clear_paddle();
            paddle_x = paddle_x - 1;
            draw_paddle();
        }
        flushkb();
    }

    if (key == KEY_RIGHT) {
        if (paddle_x < PADDLE_MAX) {
            clear_paddle();
            paddle_x = paddle_x + 1;
            draw_paddle();
        }
        flushkb();
    }
}

/* Main game */
void main() {
    init_graphics();
    seed = getticks();

    score = 0;
    lives = MAX_LIVES;
    paddle_x = 14;
    game_over = 0;

    /* Title */
    cls();
    cursor(ROW0 + 3);
    print("** CATCH! **");
    cursor(ROW1 + 2);
    print("4-Line Version");
    cursor(ROW3 + 2);
    print("Press any key");
    getkey();

    /* Main loop */
    while (game_over == 0) {
        cls();
        draw_score();
        draw_paddle();

        /* Star starts on row 1 */
        if (rand2() == 0) {
            star_x = STAR_MIN;
            star_dir = 1;
        } else {
            star_x = STAR_MAX;
            star_dir = -1;
        }

        star_steps = 2 + rand4();
        draw_star();
        caught = 0;

        /* Star moves on row 1, then drops */
        while (caught == 0) {
            check_input();
            delay(MOVE_DELAY);

            star_steps = star_steps - 1;

            if (star_steps <= 0) {
                /* Star drops - check catch */
                if (paddle_x == star_x) {
                    caught = 1;
                    score = score + 10;
                    beep();
                } else {
                    caught = 1;
                    lives = lives - 1;
                    beep();
                    beep();
                    if (lives <= 0) {
                        game_over = 1;
                    }
                }
                clear_star();
            } else {
                /* Move star */
                clear_star();
                star_x = star_x + star_dir;

                if (star_x < STAR_MIN) {
                    star_x = STAR_MIN;
                    star_dir = 1;
                }
                if (star_x > STAR_MAX) {
                    star_x = STAR_MAX;
                    star_dir = -1;
                }
                draw_star();
            }
        }

        if (game_over == 0) {
            draw_score();
            delay(10);
        }
    }

    /* Game over */
    flushkb();
    cls();
    cursor(ROW0 + 4);
    print("GAME OVER!");
    cursor(ROW1 + 5);
    print("Score:");
    print_int(score);
    cursor(ROW3 + 2);
    print("Press any key");
    flushkb();
    getkey();
}
