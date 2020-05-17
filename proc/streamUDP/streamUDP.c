/* streamUDP.c
 * A small program that listens on broadcasted UDP data and then streams is to Redis
 *
 * David Brandman
 * May 2020
 * Version 0.1
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
#include "hiredis.h"

void initialize_parameters();
int initialize_socket();
void initialize_state();
void initialize_redis();
void initialize_signals();

void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);
char PROCESS[] = "streamUDP";

redisContext *redis_context;

int main (int argc, char **argv) {

    initialize_parameters();

    initialize_redis();

    initialize_signals();

    initialize_state();

    int udp_fd = initialize_socket();

    /* Sending kill causes tmux to close */
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    while (1) {
        ssize_t bytes_read = 0;
        int16_t buffer_int[256] = {0};
        char buffer_string[4096] = {0};

        if ((bytes_read = recv(udp_fd, buffer_int, 256, 0)) < 0) {
            printf("[%s] Error with recv call.\n", PROCESS);
            exit(1);

        } else {

            int index = 0;
            index += sprintf(buffer_string, "XADD streamUDP * ");
            for (int i=0; i < (bytes_read / sizeof(int16_t)); i++)
               index += sprintf(&buffer_string[index], "chan%d %d ", i, buffer_int[i]);
            buffer_string[index-1]='\0';

            /* index += sprintf(&buffer_string[index-1], '\0'); */
            /* printf("%s\n", buffer_string); */

            redis_succeed(redis_context, buffer_string);

        }
    }


    return 0;
}

/* redis_succeed(redis_context, "INCR streamUDP_working"); */
/* redis_succeed(redis_context, "DECR streamUDP_working"); */
//------------------------------------
// Initialization functions
//------------------------------------

void initialize_parameters() {

    /* printf("[%s] Initializing parameters...\n", PROCESS); */
    /* initialize_redis_from_YAML(PROCESS); */

}

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

void initialize_state() {

    /* printf("[%s] Initializing state.\n", PROCESS); */
    /* printf("[%s] State initialized.\n", PROCESS); */

}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    /* signal(SIGINT, &ignore_exit); */
    signal(SIGUSR1, &handle_exit);

    printf("[%s] Signal handlers installed.\n", PROCESS);
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
    load_YAML_variable_string(PROCESS, "broadcast_port", broadcast_port_string, sizeof(broadcast_port_string));

    int broadcast_port = atoi(broadcast_port_string);
    printf("[%s] I will be listening on port %d\n", PROCESS, broadcast_port);


    // Now configure the socket
    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    addr.sin_port        = htons(broadcast_port);

     if (bind(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[streamUDP] socket binding failure\n"); 
        exit(EXIT_FAILURE); 
     }

     printf("[%s] Socket initialized.\n",PROCESS);


     return fd;
} 
//------------------------------------
// Handler functions
//------------------------------------

void handle_exit(int exitStatus) {
    printf("[%s] Exiting!\n", PROCESS);
    exit(0);
}

void ignore_exit(int exitStatus) {
    printf("[%s] Terminates through SIGUSR1!\n", PROCESS);
}


