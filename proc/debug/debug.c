/* debug.c
 *
 * Function designed to test the timer loop, so that we understand how a process works
 *
 * David Brandman, May 2020
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <signal.h>
#include <sys/time.h>
#include <string.h>
#include <stdlib.h>
#include <sys/io.h>
#include <unistd.h>
#include <sched.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <fcntl.h>
#include <errno.h>
#include <stdbool.h>
#include <sys/types.h>
#include <stdint.h>
#include <semaphore.h>
#include <sys/wait.h>
#include <stdatomic.h>
#include <time.h>
#include <stdlib.h>
#include "utilityFunctions.h"
#include "debug.h"


void initialize_params();
void initialize_state();
void initialize_signals();
void initialize_semaphores();


void alarm_handler(int signum);
void exit_handler(int signum);



// Each process has its own params and state process
// If I want to recv a message from a different process,
// I just import its structure and we're good to go
// The initial params_t will be loaded from a YAML file

static debug_params_t debug_params;
static debug_state_t debug_state;

static sem_t *semaphoreUp;
static sem_t *semaphoreDown;


// -------------------------------------------------
// Main 
// -------------------------------------------------

int main(int argc, char* argv[]) {

    initialize_params();

    initialize_state();

    initialize_signals();

    initialize_semaphores();
    
    // Send a signal to say that we're done initializing
    pid_t ppid = getppid();
    kill(ppid, SIGUSR2);

    /* int max = 1000000; */
    /* int semValueUp; */
    /* int semValueDown; */
    /* int i = 0; */

    while(1) {

        /* printf("[debug] before pause .\n"); */

        pause(); // Wait on SIGALRM

        /* printf("[debug] past pause .\n"); */
        
        /* sem_getvalue(semaphoreUp, &semValueUp); */
        /* sem_getvalue(semaphoreDown, &semValueDown); */
        /* printf("[debug] %d %d %d\n", i, semValueUp, semValueDown); */

        sem_wait(semaphoreUp); 

        /* for(int i = 0; i <= max; i++){ */
        /*    if (i == max) printf("%d\n", max); */ 
        /* } */
        /* sem_getvalue(semaphoreUp, &semValueUp); */
        /* sem_getvalue(semaphoreDown, &semValueDown); */
        /* printf("[debug] %d %d %d\n", i++, semValueUp, semValueDown); */

        /* sem_wait(semaphoreUp); */ 
        /* sem_getvalue(semaphoreUp, &semValue); */
        /* printf("[debug]Second: %d %d\n", i, semValue); */

        sem_post(semaphoreDown);
        /* sem_getvalue(semaphoreUp, &semValueUp); */
        /* sem_getvalue(semaphoreDown, &semValueDown); */
        /* printf("[debug] %d %d %d\n", i, semValueUp, semValueDown); */
        /* sem_getvalue(semaphoreUp, &semValue); */
        /* printf("[debug]Post: %d %d\n", i, semValue); */

    }
}

// -------------------------------------------------
// Initialization functions
// -------------------------------------------------

void initialize_params() {

    printf("[debug] Initializing parameters. \n");

    debug_params.parameter = 0;

    printf("[debug] Parameters initialized. \n");
}

void initialize_state() {

    printf("[debug] Initializing state.\n");

    debug_state.state = 0;

    printf("[debug] State initialized.\n");

}

void initialize_signals() {

    printf("[debug] Attempting to initialize signal handles.\n");
    // These are global static variables

    sigset_t exitMask;
    sigemptyset(&exitMask);
    sigaddset(&exitMask, SIGALRM);  
    init_utils(&exit_handler, &exitMask);

    static sigset_t alrmMask;
    sigfillset(&alrmMask);
    set_sighandler(SIGINT,  &exit_handler,  &exitMask);
    set_sighandler(SIGALRM, &alarm_handler, &alrmMask); 


    /* signal(SIGALRM, &alarm_handler); */


    /* signal(SIGINT, &exit_handler); */

    printf("[debug] Signal handlers installed.\n");
}

void initialize_semaphores() {

    printf("[debug] Attempting to initialize semaphores.\n");

    semaphoreUp = sem_open("debug_semaphore_up", 0);
    semaphoreDown = sem_open("debug_semaphore_down", 0);

    if (semaphoreUp == SEM_FAILED) {
        perror("[debug] Failed to open semaphoreUp.");
        exit(1);
    }
    if (semaphoreDown == SEM_FAILED) {
        perror("[debug] Failed to open semaphoreDown.");
        exit(1);
    }
    

    printf("[debug] Semaphores initialized.\n");
}



// -------------------------------------------------
// Signal handlers
// -------------------------------------------------

void alarm_handler(int signum) {
    // Do nothing
}

void exit_handler(int signum) {
    printf("[debug] Exiting program!\n");
    exit(1);
}

