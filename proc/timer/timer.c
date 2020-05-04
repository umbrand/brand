/* timer.c
 * This function is reorganized based on the timer function from Licorice,
 * downloaded 2020.04.28 from https://github.com/bil/licorice
 * 
 * 
 * Timer sits in a while(1) loop, and waits in a pause() function
 * During initialization, it calibates a timer to go off
 * Once timer goes off, it sends SIGALRM, which bumps it out of pause()
 * and then responds to a series of signals in order
 *
 * SIGNINT: First, the loop checks if the user wants to quit the program
 * SIGCHLD: Next, it checks if any of the children it's keeping track of have died
 * SIGALRM: Finally, it responds to the SIGALRM by checking on the health of the children
 *
 * The state of the signals are monitored using these global variables:
 *   static int sigalrm_recv;
 *   static int sigexit_recv;
 *   static int sigchld_recv;
 *
 * They are incremented when a signal goes off and decremented when 
 * the callback functions have finished running.
 *
 * -----------------------------
 *  Initialization
 * -----------------------------
 *
 * During initialization timer forks itself, sets the new processes settings for CPU
 * utilization etc., and then turns itself into the process. The processes forked
 * by timer are expected to have a defined semaphore behavior, defined below. 
 *
 * Each process is given its own CPU, and has a low "niceness", so that it'll bump
 * other processes during process scheduling.
 *
 *
 * -----------------------------
 * Synchronization patters
 * -----------------------------
 *
 * When timer.c checks its childen, it does the following:
 *
 * 1. Try a trywait() function for the children on semaphoreDown
 * 2. Do work regarding changing timer.c's internal state
 * 3. Send an alarm to each of the children
 * 4. Post to semaphoreUp
 *
 * Each of the children have the following logic:
 *
 * 1. Pause(), waiting for the alarm signal
 * 2. Wait on semaphoreUp
 * 3. Do work
 * 4. Post on semaphoreDown
 *
 * This pattern has the following advantages:
 * 1. timer.c wants to keep track of whether the children have finished their work
 *    by the end of a cycle. If semaphoreDown is 0, then it knows that the child
 *    has not yet finished its cycle, and can react accordingly
 * 2. This pattern ensures there won't be a deadlock.  If SIGALRM wasn't there
 *    then the child could sit and wait and then cause timer to block. 
 *
 * The normal behavior of sem_trywait() is to return EAGAIN if the semaphore is 0. 
 *
 * The original licorice approach was to use shared memory for each child to have
 * access to semaphores. The code was changed so that it now uses named semaphores
 * instead, which scales better with new processes
 *
 * ------------------------------------
 *  IPC
 *  -----------------------------------
 *
 *  The original Licorice code uses shared memory for IPC. While fast, it also means
 *  that the code needed a lot of overhead to ensure that processes had the correct
 *  information at the correc time in the correct order.
 *
 *  The new approach to IPC will be use Redis. 
 *
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
#include "timer.h"


/* Initialization functions */

void initialize_params();
void initialize_state();
void initialize_signals();
void initialize_processes();
void initialize_semaphores();
void initialize_timer();

/* Functions for managing when signals fire */

void handle_exit(int exitStatus);
void dead_child();
void check_children();


/* Handler functions called with signals fire */

void alarm_handler(int signum);
void exit_handler(int signum);
void usr1_handler(int signum);
void usr2_handler(int signum);
void chld_handler(int sig);


/* These global signal variables provide book-keeping for when signals go off in timer
 * When signal happens, they increment. When the callback for the signal function
 * is complete, they decrement
 */

int sigalrm_recv;
int sigexit_recv;
int sigchld_recv;

// This contains information for the SIGALRM timer. It needs to be a global variable
// since it's altered in the handle_exit() function
struct itimerval rtTimer;

// Each process has its own params and state process
// If I want to recv a message from a different process,
// I just import its structure and we're good to go
// The initial params_t will be loaded from a YAML file
// I think this will dissapear when we introduce Redis

timer_params_t timer_params;
timer_state_t timer_state;

// For debugging purposes
// TODO: this needs to be made robust according to a YAML configuration
pid_t so_pids[0];
pid_t ch_pids[0];
pid_t si_pids[0];
int NUM_SINKS = 0;
int NUM_MODULES = 0;
int NUM_SOURCES = 1;

static sem_t *semaphoresUp;
static sem_t *semaphoresDown;

// -------------------------------------------------
// Main 
// -------------------------------------------------

int main(int argc, char* argv[]) {

    initialize_params();

    initialize_state();

    initialize_signals();

    initialize_semaphores();

    initialize_processes();

    initialize_timer();
    
    printf("[timer] Done initializations, entering loop.\n");

    while(1) {

        if (sigexit_recv) // Respond to SIGINT. Handles exiting of program
            handle_exit(0);

        if (sigchld_recv) // Respond to SIGCHLD. Handles death of child
            dead_child();

        if (sigalrm_recv) // Respond to SIGALARM. Will fire each timestep
            check_children();

        pause();
    }
}

// -------------------------------------------------
// Initialization functions
// -------------------------------------------------

void initialize_params() {

     // TODO: Load this from the YAML file
     
    timer_params.secreq = 0;
    timer_params.usecreq = 1000;
}

void initialize_state() {


    timer_state.timestep = 0;

}

void initialize_signals() {

    printf("[timer] Attempting to initialize signal handles.\n");

    sigalrm_recv = 0; // How many SIGALRM received
    sigexit_recv = 0; // How many SIGINT  received
    sigchld_recv = 0; // How many SIGCHLD received


    signal(SIGINT, &exit_handler);
    signal(SIGALRM, &alarm_handler);
    signal(SIGUSR1, &usr1_handler);
    signal(SIGUSR2, &usr2_handler);
    signal(SIGCHLD, &chld_handler);

    printf("[timer] Signal handlers installed.\n");
}

void initialize_semaphores() {

    printf("[timer] Attempting to initialize semaphores.\n");

    semaphoresUp   = sem_open("debug_semaphore_up", O_CREAT , 0644, 0); // NB. Starts 0
    semaphoresDown = sem_open("debug_semaphore_down", O_CREAT , 0644, 1); // NB. starts 1

    if (semaphoresUp == SEM_FAILED) {
        perror("[timer] Failed to create semaphore.");
        exit(1);
    }
    if (semaphoresDown == SEM_FAILED) {
        perror("[timer] Failed to create semaphore.");
        exit(1);
    }
    
    printf("[timer] Semaphores initialized.\n");
}

void initialize_processes() {

    printf("[timer] Attempting to initialize processes.\n");

    if ((so_pids[0] = fork()) == -1) {
        die("fork failed \n");
    }

    if (so_pids[0] == 0) { // child process

        char* argv[2] = {"./../debug/debug", NULL}; // file to load

        execvp(argv[0],argv);
        printf("network exec error. %s \n", strerror(errno));
        exit(1);
        //in case execvp fails
    }
    printf("[timer] Waiting for PID to initialize... %d\n", so_pids[0]);
    pause(); // Waiting for SIGUSR2 from the child when it's ready to go
    printf("[timer] PID %d initialized. \n", so_pids[0]);
    printf("[timer] Processes initialized.\n");
}

void initialize_timer() {

    printf("[timer] Attempting to initialize SIGALRM timer.\n");

    rtTimer.it_value.tv_sec     = timer_params.secreq;
    rtTimer.it_value.tv_usec    = timer_params.usecreq;
    rtTimer.it_interval.tv_sec  = timer_params.secreq;
    rtTimer.it_interval.tv_usec = timer_params.usecreq;
    setitimer(ITIMER_REAL, &rtTimer, NULL);

    printf("[timer] SIGALRM Timer initialized.\n");

}

// -------------------------------------------------
// Handler functions
// -------------------------------------------------



void handle_exit(int exitStatus) {

    printf("[timer] Shutting down timer.\n");

    // Begin by shutting down the timer
    rtTimer.it_value.tv_sec     = 0;
    rtTimer.it_value.tv_usec    = 0;
    rtTimer.it_interval.tv_sec  = 0;
    rtTimer.it_interval.tv_usec = 0;
    setitimer(ITIMER_REAL, &rtTimer, NULL);

    printf("[timer] Killing sinks...\n");
    for (int ex_i = 0; ex_i < NUM_SINKS; ex_i++) {
        if (si_pids[ex_i] != -1) {
            printf("Killing sink: %d\n", si_pids[ex_i]);
            kill(si_pids[ex_i], SIGUSR1); // children already receive SIGUSR1
            while (waitpid(si_pids[ex_i], 0, WNOHANG) > 0);
        }
    }

    printf("[timer] Killing modules...\n");
    for (int ex_i = 0; ex_i < NUM_MODULES; ex_i++) {
        if (ch_pids[ex_i] != -1) {
            printf("Killing module: %d\n", ch_pids[ex_i]);
            kill(ch_pids[ex_i], SIGUSR1); // children already receive SIGUSR1
            while (waitpid(ch_pids[ex_i], 0, WNOHANG) > 0);
        }
    }

    printf("[timer] Killing sources...\n");
    for (int ex_i = 0; ex_i < NUM_SOURCES; ex_i++) {
        if (so_pids[ex_i] != -1) {
            printf("Killing source: %d\n", so_pids[ex_i]);
            kill(so_pids[ex_i], SIGUSR1); // children already receive SIGUSR1
          while (waitpid(so_pids[ex_i], 0, WNOHANG) > 0);
        }
    }

    sem_unlink("/debug_semaphore_up");
    sem_unlink("/debug_semaphore_down");

    printf("[timer] Exiting with status: %d\n", exitStatus);
    exit(exitStatus);

}
//TODO: Implement this logic
void dead_child() {
    printf("[timer] Dead child. \n");
    sigchld_recv--;

}

// TODO: Differentiate between sinks, sources, and modules
void check_children() {

    /* printf("Checking children %d\n", timer_state.timestep); */

    if ((sigalrm_recv > 1))
        die("[timer] Timer missed a tick. Dying.");

    timer_state.timestep++;
    /* int semValueUp = -1; */
    /* int semValueDown = -1; */

    for (int al_i = 0; al_i < NUM_SOURCES; al_i++) {

        /* sem_getvalue(semaphoresUp, &semValueUp); */
        /* printf("[timer] PreTryWait %d %d\n", semValueUp, semValueDown); */
        /* sem_getvalue(semaphoresDown, &semValueDown); */
        /* printf("[timer] PreTryWait %d %d\n", semValueUp, semValueDown); */

        if (sem_trywait(semaphoresDown)) {
            printf("Sink timing violation on ms: %d from non_source number %d \n", timer_state.timestep, al_i);
        }

        /* sem_getvalue(semaphoresUp, &semValueUp); */
        /* sem_getvalue(semaphoresDown, &semValueDown); */
        /* printf("[timer] PostTryWait %d %d\n", semValueUp, semValueDown); */
    }

    /* for (int al_i = 0; al_i < NUM_SOURCES; al_i++)  { */
    /*     printf("Trying sem_wait child %d\n", al_i); */
    /*     sem_wait(semaphoresUp[al_i]); */
    /* } */


    for (int al_i = 0; al_i < NUM_SOURCES; al_i++) 
        kill(so_pids[al_i], SIGALRM);

    // This is where manipulations of shared memory will go

    for (int al_i = 0; al_i < NUM_SOURCES; al_i++) {
        sem_post(semaphoresUp);
    }
    

    

    sigalrm_recv--;


}
// -------------------------------------------------
// Signal handlers
// -------------------------------------------------

// Handle SIGALRM on millisecond
void alarm_handler(int signum) {
    sigalrm_recv++;
}

void exit_handler(int signum) {
    sigexit_recv++;
}

void usr1_handler(int signum) {
  //do nothing, this sig is just used for communication
}

void usr2_handler(int signum) {
  //do nothing, this sig is just used for communication
}

void chld_handler(int sig) {
    sigchld_recv++;
}
