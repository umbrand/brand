/* debug.c
 *
 * Function designed to test the timer loop, so that we understand how a process works
 *
 * David Brandman, May 2020
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "redisTools.h"
#include "hiredis/hiredis.h"
#include "hiredis/async.h"
#include "hiredis/adapters/libevent.h"

void initialize_parameters();
void initialize_state();
void initialize_redis();
void initialize_signals();
void subscribe_callback(redisAsyncContext *c, void *reply, void *privdata);

void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);
char PROCESS[] = "debug";


// There are two contexts used. The first is the async one for the callback when
// a subscribed message arrives. 

redisAsyncContext *redis_async_context; 
redisContext *redis_context;

int main (int argc, char **argv) {

    initialize_parameters();

    initialize_redis();

    initialize_signals();

    initialize_state();

    struct event_base *base = event_base_new();

    pid_t ppid = getppid();
    kill(ppid, SIGUSR2);
    

    redisLibeventAttach(redis_async_context, base);
    redisAsyncCommand(redis_async_context, subscribe_callback, NULL, "SUBSCRIBE timer_step");

    event_base_dispatch(base);
    return 0;
}
//------------------------------------
// Callback functions
//------------------------------------
void subscribe_callback(redisAsyncContext *c, void *reply, void *privdata) {
    redis_succeed(redis_context, "incr debug_working");

    redisReply *r = reply;
    if (r == NULL || r->type == REDIS_REPLY_ERROR) return;

    if (r->type == REDIS_REPLY_ARRAY) {
        if (r->elements >=2) {

            char a[64] = {0};
            sprintf(a,"%s",r->element[2]->str); // You need these steps otherwise it barfs
            int b = atoi(a);
            printf("%d\n", b);
        }
    }
    redis_succeed(redis_context, "decr debug_working");
}
//------------------------------------
// Initialization functions
//------------------------------------

void initialize_parameters() {

    printf("[%s] Initializing parameters...\n", PROCESS);
    initialize_redis_from_YAML(PROCESS);

}

void initialize_redis() {

    printf("[%s] Initializing Redis...\n", PROCESS);

    char redis_ip[16]       = {0};
    char redis_port[16]     = {0};

    load_YAML_variable_string(PROCESS, "redis_ip",   redis_ip,   sizeof(redis_ip));
    load_YAML_variable_string(PROCESS, "redis_port", redis_port, sizeof(redis_port));

    printf("[%s] From YAML, I have redis ip: %s, port: %s\n", PROCESS, redis_ip, redis_port);

    printf("[%s] Trying to connect to redis.\n", PROCESS);

    redis_async_context = redisAsyncConnect(redis_ip, atoi(redis_port));
    if (redis_async_context->err) {
        printf("error: %s\n", redis_async_context->errstr);
        exit(1);
    }

    redis_context = redisConnect(redis_ip, atoi(redis_port));
    if (redis_context->err) {
        printf("error: %s\n", redis_context->errstr);
        exit(1);
    }

    printf("[%s] Redis initialized.\n", PROCESS);
     
}

void initialize_state() {

    printf("[%s] Initializing state.\n", PROCESS);

    redis_succeed(redis_context, "set debug_working 0");

    printf("[%s] State initialized.\n", PROCESS);

}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    signal(SIGINT, &ignore_exit);
    signal(SIGUSR1, &handle_exit);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void handle_exit(int exitStatus) {
    printf("[%s] Exiting!\n", PROCESS);
    exit(0);
}

void ignore_exit(int exitStatus) {
    /* printf("[%s] Terminates through SIGUSR1!\n", PROCESS); */
}
