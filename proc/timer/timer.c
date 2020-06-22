/* Timer.c
 * Code that sends SIGUSR1 to processes that are waiting for it in order to run on a real-time scheduler
 * David Brandman
 * June 2020
 *
 * This function sits waiting for the timer to go off. SIGLARM happens, it then sends SIGUSR1 to all
 * of the processes specified in the yaml file. It finds the pid by calling pgrep
 */


#include <math.h>
#include <stdio.h>
#include <signal.h>
#include <stdlib.h>
#include <semaphore.h> // semaphore
#include <string.h>
#include "redisTools.h"
#include "hiredis.h"
#include "AlarmTools.h"
#include <unistd.h>
#include <pthread.h> 

// Keep track of the process names and pid
typedef struct {

    pid_t pid;
    char name[16];

} timer_target_t;

void initialize_signals();
void initialize_alarm();
void initialize_realtime();
int initialize_timer_targets(timer_target_t **);
void shutdown_module();

void handler_SIGINT(int signum);
void handler_SIGALRM(int signum);

char PROCESS[] = "timer";


int flag_SIGINT = 0;
int flag_SIGALRM = 0;

int main(int argc, char **argv) {

    /* Sending kill causes tmux to close */
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */

    timer_target_t *timer_targets;
    int num_targets = initialize_timer_targets(&timer_targets);



    initialize_signals();
    initialize_realtime();
    initialize_alarm();

    printf("[%s] Entering loop...\n", PROCESS);

    while (1) {

        pause();

        if (flag_SIGINT) {
            shutdown_module();
        }
        if (flag_SIGALRM) {

            for (int i = 0; i < num_targets; i++) {
                kill(timer_targets[i].pid, SIGUSR1); 
            }

            flag_SIGALRM--;
        }
    }

    return 0;

}

//------------------------------------
//------------------------------------
// Initialization functions
//------------------------------------
//------------------------------------

int initialize_timer_targets(timer_target_t **timer_targets) {

    // Load which modules we want from YAML file
    char string[256] = {0};
    load_YAML_variable_string(PROCESS, "modules", string, sizeof(string));
    printf("[%s] I will be sending signals to the following processes: %s\n", PROCESS, string);


    // The yaml file is specified by:
    // value: [proc1, proc2, proc3]
    // And this gets read by the python file as:
    // ['proc1','proc2','proc3']
    // So to count how many modules there are, just count the number of commas
    int num_targets = 1;
    for (int i = 0; string[i]; i++) {
        if (string[i] == ',') {
            num_targets++;
        }
    }
    printf("[%s] There are %d modules\n", PROCESS, num_targets);

    // Load which modules to populate timer_targets
    // Split the strings to get rid of the single quotes

    *timer_targets = malloc(sizeof(timer_target_t) * num_targets);
    char *subString;
    for (int i = 0; i < num_targets; i++) {

        if( i == 0) {
            subString = strtok(string, "'"); // first quote
            subString = strtok(NULL, "'"); // second  quote
        } else {
            subString = strtok(NULL, "'"); // first  quote
            subString = strtok(NULL, "'"); // second  quote
        }

        if (!subString) {
            printf("[%s] ERROR, something went wrong parsing module list from yaml\n", PROCESS);
            exit(1);
        } else {
            strcpy((*timer_targets)[i].name, subString);
            //printf("Timer_targets name: (%s)\n", (*timer_targets)[i].name);
        }
    }

    // Now wait until the modules have been opened to get to work
    

    for (int i = 0; i < num_targets; i++) {

        char buffer[256]      = {0};
        char bashCommand[256] = {0};
        int readLength        = 0; // How much was read from fread()
        FILE *fp;

        sprintf(bashCommand, "pgrep %s", (*timer_targets)[i].name);

        fp = popen(bashCommand, "r");
        if (fp == NULL) {
            printf("[%s] popen() failed to read data.\n", PROCESS);
            exit(1);
        }
        
        while (1) {
            readLength = fread(buffer, 1, 256, fp);
            if (readLength < 0) {
                printf("[%s] Error with reading pgrep from buffer.\n", PROCESS);
                exit(1);
            }
            if (readLength == 0) {
                printf("[%s] Waiting for process (%s)...\n", PROCESS, (*timer_targets)[i].name);
                sleep(1);
            }
            if (readLength > 0) {
                (*timer_targets)[i].pid = atoi(buffer);
                printf("[%s] I found (%s) PID: %d\n", PROCESS, (*timer_targets)[i].name, (*timer_targets)[i].pid);
                break;
            }
        }
       
        fclose(fp);
    }
    return num_targets;

}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    signal(SIGALRM, &handler_SIGALRM);
    signal(SIGINT,  &handler_SIGINT);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void initialize_alarm(){

    printf("[%s] Initializing alarm...\n", PROCESS);
    
    // We want to specify out rate in microseconds from YAML
    
    char num_microseconds_string[16] = {0};
    load_YAML_variable_string(PROCESS, "timer_period", num_microseconds_string, sizeof(num_microseconds_string));
    int num_microseconds = atoi(num_microseconds_string);

    printf("[%s] Setting the alarm to go off every  %d microseconds...\n", PROCESS, num_microseconds);

    static struct itimerval rtTimer;

    rtTimer.it_value.tv_sec = 0;
    rtTimer.it_value.tv_usec = num_microseconds;
    rtTimer.it_interval.tv_sec = 0;
    rtTimer.it_interval.tv_usec = num_microseconds;
    if (setitimer(ITIMER_REAL, &rtTimer, NULL) != 0) {
        printf("[%s] Error setting timer. \n", PROCESS);
        exit(1);
    }

}

// Do we want the system to be realtime?  Setting the Scheduler to be real-time, priority 80
void initialize_realtime() {

    char sched_fifo_string[16] = {0};
    load_YAML_variable_string(PROCESS, "sched_fifo", sched_fifo_string, sizeof(sched_fifo_string));

    if (strcmp(sched_fifo_string, "True") != 0) {
        return;
    }


    printf("[%s] Setting Real-time scheduler!\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 80};
    sched_setscheduler(0, SCHED_FIFO, &sched);
}

void shutdown_module() {

    printf("[%s] SIGINT received. Shutting down.\n", PROCESS);

    printf("[%s] Setting scheduler back to baseline.\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 0};
    sched_setscheduler(0, SCHED_OTHER, &sched);


    printf("[%s] Exiting.\n", PROCESS);
    
    exit(0);
}


//
//------------------------------------
//------------------------------------
// Handler functions
//------------------------------------
//------------------------------------

void handler_SIGALRM(int signum) {
    flag_SIGALRM++;
}

void handler_SIGINT(int exitStatus) {
    flag_SIGINT++;
}
