/* monitor.c
 * David Brandman
 * June 2020
 *
 * The goal of this function is to assess latency and jitter of the pathway going from UDP packets
 * to Redis.
 *
 * It sits on a timer waiting for signals from timer.c. When a signal is received, it then 
 * records the current timestamp off the CPU, and the cerebus packet timestamp that is most
 * recent in the system. 
 *
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

void initialize_redis();
void initialize_signals();
void initialize_alarm();
void initialize_realtime();
void shutdown();

void handler_SIGINT(int signum);
void handler_SIGALRM(int signum);

char PROCESS[] = "monitor";

redisContext *redis_context;
redisReply *reply;

// The seamphore that blocks until the alarm goes off
/* sem_t sem_timer; */

// Let's try mutexes now
/* pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER; */

int flag_SIGINT = 0;
int flag_SIGALRM = 0;

int main(int argc, char **argv) {

    initialize_redis();

    initialize_signals();

    /* Sending kill causes tmux to close */
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    struct timeval monitor_time;


    printf("[%s] Entering loop...\n", PROCESS);

    while (1) {

        pause();

        if (flag_SIGINT) {
            shutdown();
        }
        if (flag_SIGALRM) {

            // This gets the current system time
            gettimeofday(&monitor_time,NULL);

            // There is an issue with hiredis accessing streams. It appears
            // that if the stream doesn't exist, it doesn't inform you
            // in a nice way. So we first check if the stream exists.
            reply = redisCommand(redis_context, "exists cerebusAdapter");
            if (reply == NULL || reply-> type != REDIS_REPLY_INTEGER) {
                printf("[%s] There is a problem with checking redis.\n", PROCESS);
                exit(1);
            }
            // If the stream doesn't exist, it will have reply->integer == 0
            if (reply -> integer == 0 ) {
                continue;
            }
            freeReplyObject(reply);

            // If we've come this far the stream exists
            reply = redisCommand(redis_context, "xrevrange cerebusAdapter + - count 1");
            if (reply == NULL || reply->type != REDIS_REPLY_ARRAY) { //|| reply->len == 0) {
                continue;
            }
            
            // The xrevrange value is rather nested
            // 1. [0] The stream we're getting data from
            // 2. [1] The data content from the stream
            // 3. [1] The string containing the number of samples

            int num_samples = atoi(reply->element[0]->element[1]->element[1]->str);

            // 3. [3] The timestamps binary data
            uint32_t  *timestamps = (uint32_t *) reply->element[0]->element[1]->element[3]->str;

            // pointer to last timestamp
            uint32_t *last_timestamp = &timestamps[num_samples-1];


            // Now get this into Redis!
            char redis_string[256] = {0};
            char monitor_time_string[256] = {0};
            char cb_timestamp_string[256] = {0};

            sprintf(monitor_time_string, "%ld", monitor_time.tv_sec   * 1000000L + monitor_time.tv_usec);
            sprintf(cb_timestamp_string, "%u", *last_timestamp);

            sprintf(redis_string, "xadd monitor * monitor_time %s cerebus_timestamp %s", 
                    monitor_time_string, 
                    cb_timestamp_string);
            redis_succeed(redis_context, redis_string);

            // Free memory
            freeReplyObject(reply);
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

void initialize_redis() {

    printf("[%s] Initializing Redis...\n", PROCESS);

    char redis_ip[16]       = {0};
    char redis_port[16]     = {0};

    load_YAML_variable_string(PROCESS, "redis_ip",   redis_ip,   sizeof(redis_ip));
    load_YAML_variable_string(PROCESS, "redis_port", redis_port, sizeof(redis_port));

    printf("[%s] From YAML, I have redis ip: %s, port: %s\n", PROCESS, redis_ip, redis_port);

    printf("[%s] Trying to connect to redis.\n", PROCESS);

    redis_context = redisConnect(redis_ip, atoi(redis_port));
    if (redis_context->err) {
        printf("[%s] Redis connection error: %s\n", PROCESS, redis_context->errstr);
        exit(1);
    }

    printf("[%s] Redis initialized.\n", PROCESS);
     
}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    signal(SIGALRM, &handler_SIGALRM);
    signal(SIGINT,  &handler_SIGINT);
    signal(SIGUSR1, &handler_SIGALRM);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void shutdown() {

    printf("[%s] SIGINT received. Shutting down.\n", PROCESS);

    printf("[%s] Setting scheduler back to baseline.\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 0};
    sched_setscheduler(0, SCHED_OTHER, &sched);

    printf("[%s] Shutting down redis.\n", PROCESS);

    redisFree(redis_context);

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
    /* pthread_mutex_unlock(&mutex); */
	/* sem_post(&sem_timer); */
}

void handler_SIGINT(int exitStatus) {
    flag_SIGINT++;
}
