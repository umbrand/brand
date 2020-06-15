
#include <math.h>
#include <stdio.h>
#include <signal.h>
#include <stdlib.h>
#include <semaphore.h> // semaphore
#include "redisTools.h"
#include "hiredis.h"
#include "AlarmTools.h"
#include <unistd.h>
#include <pthread.h> 

void initialize_redis();
void initialize_signals();
void initialize_alarm();
void initialize_realtime();

void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);

void alarm_handler(int signum);

char PROCESS[] = "monitor";

redisContext *redis_context;
redisReply *reply;

// The seamphore that blocks until the alarm goes off
sem_t sem_timer;

int main(int argc, char **argv) {


    initialize_redis();

    initialize_signals();

    initialize_alarm();

    initialize_realtime();
    /* Sending kill causes tmux to close */
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    struct timeval monitor_time;
    printf("[%s] Entering loop...\n", PROCESS);

	while(sem_wait(&sem_timer) == 0) {

        reply = redisCommand(redis_context, "xrevrange cerebusAdapter + - count 1");
        if (reply == NULL || reply->type == REDIS_REPLY_ERROR || reply->type == REDIS_REPLY_NIL) {
            printf("[%s] Error running redis command",PROCESS);
            exit(1);
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

        // This gets the current system time
        gettimeofday(&monitor_time,NULL);

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
    }


    redisFree(redis_context);
    printf("[%s] Shutting down.\n",PROCESS);
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
        printf("error: %s\n", redis_context->errstr);
        exit(1);
    }

    printf("[%s] Redis initialized.\n", PROCESS);
     
}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    /* signal(SIGINT, &ignore_exit); */
    signal(SIGUSR1, &handle_exit);
    signal(SIGALRM, &alarm_handler);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void initialize_alarm(){

    printf("[%s] Initializing alarm...\n", PROCESS);
    
	// Initialize the Semaphore used to indicate new data should be sent
	if (sem_init(&sem_timer, 0, 0) < 0) {
		printf("[%s] Could not initialize Semaphore! Exiting.\n", PROCESS);
		exit(1);
	}

    // We want to specify out rate in microseconds from YAML
    
    char num_microseconds_string[16] = {0};
    load_YAML_variable_string(PROCESS, "timer_period", num_microseconds_string, sizeof(num_microseconds_string));
    int num_microseconds = atoi(num_microseconds_string);

    printf("[%s] Setting the alarm to go off every  %d microseconds...\n", PROCESS, num_microseconds);

	// How many nanoseconds do we wait between reads. Note:  1000 nanoseconds = 1us
	InitializeAlarm(&alarm_handler, 0, num_microseconds * 1000);

}

// Do we want the system to be realtime?  Setting the Scheduler to be real-time, priority 80
void initialize_realtime() {
    printf("[%s] Setting Real-time scheduler!\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 80};
    sched_setscheduler(0, SCHED_FIFO, &sched);
}

//
//------------------------------------
//------------------------------------
// Handler functions
//------------------------------------
//------------------------------------

void alarm_handler(int signum) {
	sem_post(&sem_timer);
}

void handle_exit(int exitStatus) {
    printf("[%s] Exiting!\n", PROCESS);
    exit(0);
}

void ignore_exit(int exitStatus) {
    printf("[%s] Terminates through SIGUSR1!\n", PROCESS);
}
