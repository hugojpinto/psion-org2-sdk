/*
 * CATCH - A simple UDG game for Psion Organiser II
 *
 * Catch falling stars with your paddle!
 * Stars move across the top row, then drop down.
 * Use LEFT/RIGHT cursor keys to move paddle.
 *
 * Features User Defined Graphics (UDGs) for custom characters.
 */

#include <psion.h>

/* UDG character codes */
#define STAR   0
#define PADDLE 1

/* Psion key codes */
#define KEY_LEFT  5     /* LEFT cursor key */
#define KEY_RIGHT 6     /* RIGHT cursor key */

/* Game constants */
#define SCREEN_WIDTH 16
#define PADDLE_MIN   0  /* Leftmost paddle position */
#define PADDLE_MAX   15 /* Rightmost paddle position */
#define STAR_MIN     8  /* Star play area (right of score) */
#define STAR_MAX     15 /* Right edge */
#define TOP_ROW      0  /* Line 1 - star row */
#define BOTTOM_ROW   16 /* Line 2 - paddle row */
#define MAX_LIVES    3
#define MOVE_DELAY   6  /* Ticks between star movements */
#define DROP_STEPS   4  /* Star drops after this many moves */

/* UDG bitmap buffers */
char star_data[8];
char paddle_data[8];

/* Game state - all globals to avoid frame pointer corruption */
int score;
int lives;
int paddle_x;
int star_x;
int star_dir;
int star_steps;  /* Steps until star drops */
int game_over;
int seed;
int caught;
int key;

/* Initialize the UDG bitmap data */
void init_graphics() {
    /* Star: a 5-pointed star shape */
    star_data[0] = 0x04;  /* ..*.  */
    star_data[1] = 0x04;  /* ..*.  */
    star_data[2] = 0x1F;  /* ***** */
    star_data[3] = 0x0E;  /* .***. */
    star_data[4] = 0x0E;  /* .***. */
    star_data[5] = 0x15;  /* *.*.* */
    star_data[6] = 0x04;  /* ..*.  */
    star_data[7] = 0x00;  /* ..... */

    /* Paddle: a bucket/cup shape */
    paddle_data[0] = 0x00;  /* ..... */
    paddle_data[1] = 0x11;  /* *...* */
    paddle_data[2] = 0x11;  /* *...* */
    paddle_data[3] = 0x1F;  /* ***** */
    paddle_data[4] = 0x1F;  /* ***** */
    paddle_data[5] = 0x1F;  /* ***** */
    paddle_data[6] = 0x0E;  /* .***. */
    paddle_data[7] = 0x00;  /* ..... */

    /* Define the UDGs */
    udg_define(STAR, star_data);
    udg_define(PADDLE, paddle_data);
}

/* Draw compact score on line 1 */
void draw_score() {
    cursor(0);
    print("S:");
    print_int(score);
    cursor(5);
    print("L:");
    print_int(lives);
}

/* Draw star on top row */
void draw_star() {
    cursor(TOP_ROW + star_x);
    putchar(STAR);
}

/* Clear star from top row */
void clear_star() {
    cursor(TOP_ROW + star_x);
    putchar(' ');
}

/* Draw paddle on bottom row */
void draw_paddle() {
    cursor(BOTTOM_ROW + paddle_x);
    putchar(PADDLE);
}

/* Clear paddle */
void clear_paddle() {
    cursor(BOTTOM_ROW + paddle_x);
    putchar(' ');
}

/* Inline random helpers to avoid frame pointer corruption in function calls */
/* These modify global 'seed' directly */

/* Get next value 0-1 (for direction) */
int rand2() {
    seed = seed + 1;
    if (seed >= 2) {
        seed = 0;
    }
    return seed;
}

/* Get next value 0-3 (for drop timing) */
int rand4() {
    seed = seed + 1;
    if (seed >= 4) {
        seed = 0;
    }
    return seed;
}

/* Handle player input */
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

/* Main game function */
void main() {
    /* Initialize graphics */
    init_graphics();

    /* Initialize random seed */
    seed = getticks();

    /* Initialize game state */
    score = 0;
    lives = MAX_LIVES;
    paddle_x = 10;
    game_over = 0;

    /* Show title */
    cls();
    cursor(0);
    print("** CATCH! **");
    cursor(BOTTOM_ROW);
    print("Press any key");
    getkey();

    /* Main game loop */
    while (game_over == 0) {
        /* Clear and draw screen */
        cls();
        draw_score();
        draw_paddle();

        /* Star starts at random position on top row */
        /* Alternate between starting from left or right side */
        if (rand2() == 0) {
            star_x = STAR_MIN;
            star_dir = 1;  /* Move right */
        } else {
            star_x = STAR_MAX;
            star_dir = -1; /* Move left */
        }

        /* Random steps before drop (2-5) */
        star_steps = 2 + rand4();

        /* Draw initial star */
        draw_star();
        caught = 0;

        /* Star moves across top row */
        while (caught == 0 && game_over == 0) {
            /* Check for input */
            check_input();

            /* Delay between movements */
            delay(MOVE_DELAY);

            /* Decrement steps until drop */
            star_steps = star_steps - 1;

            /* Check if time to drop */
            if (star_steps <= 0) {
                /* Star drops! Check if paddle is there */
                if (paddle_x == star_x) {
                    /* Caught! */
                    caught = 1;
                    score = score + 10;
                    beep();
                } else {
                    /* Missed! */
                    caught = 1;  /* End this round */
                    lives = lives - 1;
                    beep();
                    beep();
                    if (lives <= 0) {
                        game_over = 1;
                    }
                }
                /* Clear star from top row */
                clear_star();
                break;
            }

            /* Clear old star position */
            clear_star();

            /* Move star */
            star_x = star_x + star_dir;

            /* Check bounds - bounce off edges */
            if (star_x < STAR_MIN) {
                star_x = STAR_MIN;
                star_dir = 1;  /* Reverse direction */
            }
            if (star_x > STAR_MAX) {
                star_x = STAR_MAX;
                star_dir = -1; /* Reverse direction */
            }

            /* Draw star at new position */
            draw_star();
        }

        /* Brief pause between rounds */
        if (game_over == 0) {
            draw_score();
            delay(15);
        }
    }

    /* Game over screen */
    flushkb();
    cls();
    cursor(0);
    print("GAME OVER!");
    cursor(BOTTOM_ROW);
    print("Score:");
    print_int(score);
    flushkb();
    getkey();
}
