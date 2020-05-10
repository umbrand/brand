/* UDPApapter.c
 * A small program that listens on broadcasted UDP data and then broadcasts it through Redis
 * The first version of this was written in pure python, but it couldn't keep up so I rewrote
 * it in C.
 *
 * After initialization, the program sits and waits for new UDP packets. When it gets
 * new packets it copies it to a buffer. It subscribes to timer_step from timer.c. 
 * When it gets a new timer_step message, it then copies whatever's on the buffer and then
 * broadcasts it over redis. 
 *
 * Note that the data comes in as an array of int16. 
 * I didn't think it was necessary to make a separate list for each channel, but it's 
 * cleaner to do it that way, although it would require downstream processes to start
 * using locks. This may be an idea for a future version.
 *
 * I think because I'm using a redis callback I need to have a second thread
 * that will sit and listen to the udp packets.
 *
 * David Brandman
 * April 2020
 * Version 0.2
 */



#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <pthread.h> 
#include <sys/socket.h>
#include <arpa/inet.h>
#include "redisTools.h"
#include "hiredis/hiredis.h"
#include "hiredis/async.h"
#include "hiredis/adapters/libevent.h"

void initialize_parameters();
int initialize_socket();
void initialize_state();
void initialize_redis();
void initialize_signals();
void subscribe_callback(redisAsyncContext *c, void *reply, void *privdata);

void *udp_thread(void *vargp);

void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);
char PROCESS[] = "udpAdapter";

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

// There are two contexts used. The first is the async one for the callback when
// a subscribed message arrives. 

redisAsyncContext *redis_async_context; 
redisContext *redis_context;

int main (int argc, char **argv) {

    initialize_parameters();

    initialize_redis();

    initialize_signals();

    initialize_state();

    int pipe_fd[2]; // [1] is for writing, [0] is for reading
    if (pipe(pipe_fd) < 0) {
        printf("[%s] Could not create pipe.\n", PROCESS);
        exit(1);
    }
    
    pthread_mutex_lock(&mutex);

    pthread_t udp_pthread; 
    pthread_create(&udp_pthread, NULL, udp_thread, (void *)&pipe_fd[1]); 


    //unlocked in udp_thread() function
    pthread_mutex_lock(&mutex);
    
    printf("[%s] Done initializing. Launching callback\n",PROCESS);
    struct event_base *base = event_base_new();
    redisLibeventAttach(redis_async_context, base);
    redisAsyncCommand(redis_async_context, subscribe_callback, (void *)&pipe_fd[0], "SUBSCRIBE timer_step");

    pid_t ppid = getppid();
    kill(ppid, SIGUSR2);

    event_base_dispatch(base);
    printf("exiting\n");
    return 0;
}
//------------------------------------
// Callback functions
//------------------------------------
void subscribe_callback(redisAsyncContext *c, void *reply, void *privdata) {

    int *pipe_read_fd = (int*) privdata;
    
    redis_succeed(redis_context, "INCR udpAdapter_working");

    int16_t buffer_int[2096] = {0};
    char buffer_string[20000] = {0};

    redisReply *r = reply;
    if (r == NULL || r->type == REDIS_REPLY_ERROR) 
        return;

    int read_length;
    if (r->type == REDIS_REPLY_ARRAY) {
        if((read_length = read(*pipe_read_fd,buffer_int, 2096)) < 0) {
            printf("[%s] Could not read from pipe\n", PROCESS);
            exit(1);
        }
        
        int index = 0;
        index += sprintf(buffer_string, "PUBLISH udpAdapter_raw ");
        for (int i=0; i < (read_length / sizeof(int16_t)); i++)
           index += sprintf(&buffer_string[index], "%d,", buffer_int[i]);
        
        redis_succeed(redis_context, buffer_string);
    }
    redis_succeed(redis_context, "DECR udpAdapter_working");
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

    redis_succeed(redis_context, "SET udpAdapter_working 0");

    printf("[%s] State initialized.\n", PROCESS);

}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    /* signal(SIGINT, &ignore_exit); */
    signal(SIGUSR1, &handle_exit);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void handle_exit(int exitStatus) {
    printf("[%s] Exiting!\n", PROCESS);
    exit(0);
}

void ignore_exit(int exitStatus) {
    printf("[%s] Terminates through SIGUSR1!\n", PROCESS);
}

int initialize_socket() {

    // Create a UDP socket
   	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP ); 
    if (fd == 0) {
        perror("socket failed"); 
        exit(EXIT_FAILURE); 
    }
    //Set socket permissions so that we can listen to broadcasted packets
    int broadcastPermission = 1;
    if (setsockopt(fd,SOL_SOCKET,SO_BROADCAST, (void *) &broadcastPermission, sizeof(broadcastPermission)) < 0) {
        perror("socket permission failure"); 
        exit(EXIT_FAILURE); 
    }

    char broadcast_port_string[16] = {0};
    if(redis_string(redis_context, "get udpAdapter_broadcast_port", broadcast_port_string, 16)) {
        printf("[%s] Could not get broadcast_port from YAML file.\n", PROCESS);
        exit(1);
    }
    int broadcast_port = atoi(broadcast_port_string);
    printf("[%s] I will be listening on port %d\n", PROCESS, broadcast_port);


    // Now configure the socket
    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    addr.sin_port        = htons(broadcast_port);

     if (bind(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[udpAdapter] socket binding failure\n"); 
        exit(EXIT_FAILURE); 
     }

     printf("[%s] Socket initialized.\n",PROCESS);


     return fd;
} 

void *udp_thread(void *vargp) {
    printf("[%s] Thread initialized.\n", PROCESS);
    int *pipe_write_fd = (int*) vargp;

    int udp_fd = initialize_socket();

    char buffer[256] = {0};

    printf("[%s] Entering UDP listening loop.\n", PROCESS);

    pthread_mutex_unlock(&mutex);
    while (1) {
        ssize_t buffer_length = 0;

        if ((buffer_length = recv(udp_fd, buffer, 256, 0)) < 0) {
            perror("recv");
            exit(1);

        } else {
            if(write(*pipe_write_fd, buffer, buffer_length) < 0) {
                printf("[%s]Could not write to pipe.\n", PROCESS);
                exit(1);
            }
        }
    }
}
