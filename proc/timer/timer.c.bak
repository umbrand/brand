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
 *  information at the correct time in the correct order.
 *
 *  The new approach to IPC will be use Redis. 
 *
 * ------------------------------------
 *  Testing
 *  -----------------------------------
 *
 * This next implentation will work as follows:
 * Sources will sit and subscribe to the timer_step value
 *
 * eval "redis.call('publish','timer_step',redis.call(redis.call('incr','timer_step')); return 0"
 * And then the timer.c function goes through all of the listed functions and checks to see if they
 * have completed their cycle
 *
 * Each process has process_is_working variable, that is 1 if the function is working and 0 if idle
 * Deciding if a process is working or not depends on the is_working variable. This is how
 * timer will know if there's a lag
 * There is no longer a difference between sources and sinks and modules. Just modules
 * The behavior relative to the published data is what is going to distinguish the processes
 *
 * Timer will keep track of the processes spawned in this way:
 * typedef struct child {
     * pid_t child_pid;
     * char[32] name;
     * } 
 * So that it can be more informed as to what is happening if a child dies
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
#include <hiredis.h>
#include "utilityFunctions.h"
#include "timer.h"
#include "redisTools.h"


/* Initialization functions */

void initialize_parameters();
void initialize_redis();
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

typedef struct {

    pid_t pid;
    char name[16];

} timer_child_t;

timer_child_t *timer_child;
int num_children;

// The state of this function -- how many times timer has run

int timer_step;

// Redis information
redisContext *redis_context;
redisReply *reply;


// -------------------------------------------------
// Main 
// -------------------------------------------------

int main(int argc, char* argv[]) {

    initialize_parameters();

    initialize_redis();

    initialize_state();

    initialize_signals();

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

void initialize_parameters() {

    printf("[timer] Load YAML configuration file to Redis...\n");

    initialize_redis_from_YAML("timer");

}

void initialize_redis() {

    printf("[timer] Initializing Redis...\n");

    char redis_ip[16]       = {0};
    char redis_port[16]     = {0};

    load_YAML_variable_string("timer", "redis_ip",   redis_ip,   sizeof(redis_ip));
    load_YAML_variable_string("timer", "redis_port", redis_port, sizeof(redis_port));

    printf("[timer] From YAML, I have redis ip: %s, port: %s\n", redis_ip, redis_port);

    printf("[timer] Trying to connect to redis.\n");

    load_redis_context(&redis_context, redis_ip, redis_port);

    printf("[timer] Redis initialized.\n");
     
}

void initialize_state() {

    timer_step = 0;

}

void initialize_signals() {

    printf("[timer] Attempting to initialize signal handlers.\n");

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


void initialize_processes() {

    printf("[timer] Attempting to initialize processes.\n");
    
    // First, how many timer_modules are there?

    if(redis_int(redis_context, "llen timer_modules", &num_children)) {
        printf("[timer] could not read length of modules.\n");
        exit(1);
    }

    printf("[timer] There are %d modules to initialize.\n", num_children);

    // timer_child keeps a list of the PIDs and names of processes

    timer_child = malloc(num_children * sizeof(timer_child_t));

    // Get the name of the module to be loaded (Redis), and then fork yourself
    // and keep track of the pid of what has been forked.

    for (int i = 0; i < num_children; i++) {


        char child_name[16] = {0};
        char reddis_command[64] = {0};
        sprintf(reddis_command, "lindex timer_modules %d", i);
        redis_string(redis_context, reddis_command, child_name, 16);

        strcpy(timer_child[i].name, child_name);

        char initializeCommand[64] = {0};
        sprintf(initializeCommand, "./%s", child_name);

        printf("[timer] Forking and executing: %s\n", initializeCommand);

        if ((timer_child[i].pid = fork()) == -1) {
            die("[timer] fork failed \n");
        }

        if (timer_child[i].pid == 0) { // child process

            char* argv[2] = {initializeCommand, NULL}; // file to load

            execvp(argv[0],argv);
            /* if (system(initializeCommand)) { */
            printf("[timer] system fail: %s %s \n", initializeCommand, strerror(errno));
            exit(1);
            /* } */
            //in case execvp fails
        }

        printf("[timer] Waiting for SIGUSR2 from [%s]\n", timer_child[i].name);

        pause(); // Waiting for SIGUSR2 from the child when it's ready to go

        printf("[timer] Signal received: [%s] initialized. \n", timer_child[i].name);

    }
    printf("[timer] All processes initialized.\n");
}

void initialize_timer() {

    printf("[timer] Attempting to initialize SIGALRM timer.\n");

    char buffer[16] ={0};
    if(redis_string(redis_context, "get timer_sample_period", buffer, sizeof(buffer))){
        printf("[timer] Could not load timer_sample_period.\n");
        exit(1);
    }

    rtTimer.it_value.tv_sec     = 0;
    rtTimer.it_value.tv_usec    = atoi(buffer);
    rtTimer.it_interval.tv_sec  = 0;
    rtTimer.it_interval.tv_usec = atoi(buffer);
    setitimer(ITIMER_REAL, &rtTimer, NULL);

    printf("[timer] SIGALRM Timer initialized, usec = %d.\n", atoi(buffer));

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

    
    printf("[timer] Killing modules...\n");
    for (int i = 0; i < num_children; i++) {
        if (timer_child[i].pid != -1) {
            printf("[timer] Killing module [%s]: %d\n", timer_child[i].name, timer_child[i].pid);
            kill(timer_child[i].pid, SIGUSR1); // children already receive SIGUSR1
            while (waitpid(timer_child[i].pid, 0, WNOHANG) > 0);
        }
    }

    printf("[timer] Exiting with status: %d\n", exitStatus);
    exit(exitStatus);

}


void dead_child() {
    printf("[timer] Dead child. \n");
    sigchld_recv--;

    // waitpid(-1,...) waits for any small child to change state
    // And then WNOHANG means that it will return immediately

    int saved_errno = errno;
    int dead_pid;
    while ((dead_pid = waitpid((pid_t)(-1), 0, WNOHANG)) == 0);

    for (int i = 0; i < num_children; i++) {
        printf("[timer] Checking child [%s]\n", timer_child[i].name);
        if (timer_child[i].pid == dead_pid) {
            timer_child[i].pid = -1;
            printf("[timer] I have lost child [%s]\n", timer_child[i].name);
        }
    }

    errno = saved_errno;
    die("A child was lost and now I'm quitting. :-/ \n");

}

void check_children() {

    if ((sigalrm_recv > 1)) {
        printf("[timer] Timer missed a tick. Dying.\n");
        handle_exit(1);
    }

    for (int i = 0; i < num_children; i++) {

        char command[64] = {0};
        char is_working[64] = {0};
        sprintf(command, "get %s_working", timer_child[i].name);
        redis_string(redis_context, command, is_working, 64);

        if (atoi(is_working) > 0) {

            printf("Step (%d): [%s] timing violation.\n", timer_step, timer_child[i].name);
        }

    }

    char publish[64] = {0};
    sprintf(publish, "xadd timer * step %d", timer_step);
    redis_succeed(redis_context,publish);

    timer_step++;
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

