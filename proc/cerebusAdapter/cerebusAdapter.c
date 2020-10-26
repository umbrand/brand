/* cerebusAdapter.c
 * Converts cerebrus generic packets to the UDP stream
 *
 * The goal of this process is to convert UDP information to a Redis stream. The
 * stream has the following format:
 *
 * cerebusAdapter num_samples [string] timestamps [uint32 binary array] samples [int16 binary array] 
 * 
 * It makes use of the redisCommandArgv function, which has the form: (redis_context,  argc, (const char**) argv, argvlen));
 *
 * Here, argc is the number of strings being sent. argv is the content of the string, and argvlen is the string lengths
 * for the strings. Note that Redis is binary safe, so we can store raw binaries nicely if we want.
 *
 * This function sits and blocks on a udp socket. When a new packet arrives it then creates a pointer
 * to the point of the UDP payload that we would expect to be a cerebus packet header. 
 * If it has the right data type, it copies the data from the UDP payload to populate argv.
 * It keeps track of the argvlen prior to submission to Redis.
 *
 * When sufficient samples have been collected (defined in the cerebusAdapter.yaml file) it then
 * writes the collected argv to Redis and then starts again.
 *
 * One thing to keep in mind is that the keys for the stream will always be even numbers, and the
 * corresponding values will be odd. That's why there's so much +1 notation everywhere.
 *
 * David Brandman
 * June 2020
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

// Cerebrus packet definition, adapted from the standard Blackrock library
// https://github.com/neurosuite/libcbsdk. 
typedef struct cerebus_packet_header_t {
    uint32_t time;
    uint16_t chid;
    uint8_t type;
    uint8_t dlen;
} cerebus_packet_header_t;


// List of parameters read from the yaml file, facilitates function definition of initialize_parameters
typedef struct yaml_parameters_t {
    int num_channels;
    int samples_per_redis_stream;
} yaml_parameters_t;

void initialize_redis();
void initialize_signals();
int  initialize_socket();
void initialize_parameters(yaml_parameters_t *p);
void initialize_realtime();
void handler_SIGINT(int exitStatus);
void shutdown_process();
void print_argv(int, char **, size_t *);

char PROCESS[] = "cerebusAdapter";

redisContext *redis_context;

int flag_SIGINT = 0;



int main (int argc_main, char **argv_main) {

    //debugging file output
    FILE *fp = fopen("cerebusAdapter_debug.txt","w");

    initialize_redis();

    initialize_signals();

    // Uncommenting this results in bash fork error since cerebusAdapter uses Redis
    //initialize_realtime();

    int udp_fd = initialize_socket();
    
    
    yaml_parameters_t yaml_parameters = {0};
    initialize_parameters(&yaml_parameters);

    int num_channels             = yaml_parameters.num_channels;
    int samples_per_redis_stream = yaml_parameters.samples_per_redis_stream;


    // argc    : The number of arguments in argv. The calculation is:
    //           int argc = 3 + 2 * 4;
    //           3                  -> xadd cerebusAdapter *
    //           4                  -> timestamps (3 types) and sample array
    //           2 *              -> (key, value) pairs
    // argvlen : The length of the strings in each argument of argv
    
    int argc        = 3 + (2 * 4); // argcount = xadd + key:value for everything else
    size_t *argvlen = malloc(argc * sizeof(size_t));  // arvlen (length of each argv entry)

    // argv : This contains the arguments to be executed by redis. 
    //        the argv has the form:
    //        xadd cerebusAdapter * num_samples [string] timestamps [int32] samples [int16] ... 
    //        We begin by populating the entries manually
    //        Starting at index position [3], we start adding the key data, always of form key [value]
    //        So that the key identifier (i.e. the string) is an odd number and the value is even
    
    // We keep track of the indexes. Each ind_ variable keeps track of where the (key value) begins
     

    int ind_xadd              = 0;                         	// xadd cerebusAdapter *
    int ind_timestamps        = ind_xadd + 3;              	// timestamps [data]
    int ind_current_time      = ind_timestamps + 2;        	// current_time [data]
    int ind_udp_received_time = ind_current_time + 2;      	// udp_received_time [data]
    int ind_samples           = ind_udp_received_time + 2;      // samples [data array] 
    
    //////////////////////////////////////////
    // Now we begin the arduous task of allocating memory. We want to be able to hold
    // data of types strings, int16 and int32, so we need to be careful.

    int len = 16;
    char *argv[argc];

    // allocating memory for xadd cerebus *
    for (int i = 0; i < ind_timestamps; i++) {
        argv[i] = malloc(len);
    }


    // allocating memory for timestamps [data]
    argv[ind_timestamps]     = malloc(len);
    argv[ind_timestamps + 1] = malloc(sizeof(int32_t) * samples_per_redis_stream);
    
    // allocating memory for current_time [data]
    argv[ind_current_time]     = malloc(len);
    argv[ind_current_time + 1] = malloc(sizeof(struct timeval) * samples_per_redis_stream);
    
    // allocating memory for udp_received_time [data]
    argv[ind_udp_received_time]     = malloc(len);
    argv[ind_udp_received_time + 1] = malloc(sizeof(struct timeval) * samples_per_redis_stream);
  

 
    // allocating memory for samples:  [data0 ... dataX]
    argv[ind_samples] = malloc(len);
    argv[ind_samples + 1] = malloc(sizeof(int16_t) * samples_per_redis_stream * num_channels);
    
    //
    //////////////////////////////////////////


    // At this point we start populating argv strings
    // Start by adding xadd cerebusAdapter *
    // And then add the keys for num_samples, timestamps, channel list, and sample array

    argvlen[0] = sprintf(argv[0], "%s", "xadd");
    argvlen[1] = sprintf(argv[1], "%s", "cerebusAdapter");
    argvlen[2] = sprintf(argv[2], "%s", "*");
    
    argvlen[ind_timestamps]        = sprintf(argv[ind_timestamps]  , "%s", "timestamps");
    argvlen[ind_current_time]      = sprintf(argv[ind_current_time]  , "%s", "cerebusAdapter_time");
    argvlen[ind_udp_received_time] = sprintf(argv[ind_udp_received_time]  , "%s", "udp_received_time");
    argvlen[ind_samples]           = sprintf(argv[ind_samples], "%s", "samples");



    // Sending kill causes tmux to close
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    printf("[%s] Entering loop...\n", PROCESS);
    
    // How many samples have we copied for argv?
    int n = 0;

    // We use rcvmsg because we want to know when the kernel received the UDP packet
    // and because we want the socket read to timeout, allowing us to gracefully
    // shutdown with a SIGINT call. Using recvmsg means there's a lot more overhead
    // in actually getting to business, as seen below

    char *buffer = malloc(65535); // max size of conceivable packet
    char msg_control_buffer[2000] = {0};
    

    struct iovec message_iovec = {0};
    message_iovec.iov_base = buffer;
    message_iovec.iov_len  = 65535;

    struct msghdr message_header = {0};
    message_header.msg_name       = NULL;
    message_header.msg_iov        = &message_iovec;
    message_header.msg_iovlen     = 1;
    message_header.msg_control    = msg_control_buffer;
    message_header.msg_controllen = 2000;

    struct timeval current_time;
    struct timeval udp_received_time;
    struct cmsghdr *cmsg_header; // Used for getting the time UDP packet was received
    
    while (1) {

        int udp_packet_size = recvmsg(udp_fd, &message_header, 0);

        if (flag_SIGINT) 
            shutdown_process();

        // The timer has timed out or there was an error with the recvmsg() call
        if (udp_packet_size  <= 0) {
            continue;
        }

        // For convenience, makes it much easier to reason about
        char *udp_packet_payload = (char*) message_header.msg_iov->iov_base;
        
        // These two lines of code get the time the UDP packet was received
        cmsg_header = CMSG_FIRSTHDR(&message_header); 
        memcpy(&udp_received_time, CMSG_DATA(cmsg_header), sizeof(struct timeval));



        // We know that the UDP packet is organized as a series
        // of cerebus packets, so we're going to read them in sequence and decide what to do
        // cb_packet_ind is the index of the start of the cerebus packet we're reading from.
        
        int cb_packet_ind = 0; 
        while (cb_packet_ind <= udp_packet_size) {

            // First check: can we safely read the remaining payload content. We should
            // have at least sizeof(cerebus_packet_header_t) bytes left to read
            // If not something went wrong and we go fetch the next packet

            if (cb_packet_ind + sizeof(cerebus_packet_header_t) > udp_packet_size) {
                break;
            }


            // Create a pointer to the cerebus packet at the current location of the udp payload
            cerebus_packet_header_t *cerebus_packet_header = (cerebus_packet_header_t*) &udp_packet_payload[cb_packet_ind];

            // Now check to see if we're getting a type 6 packet, which should contain our sampled Utah array voltage data
            fprintf(fp,"cerebus_packet_header\ttime: %i,\tdlen: %i,\ttype: %i,\tchid: %i\n",cerebus_packet_header->time,cerebus_packet_header->dlen,cerebus_packet_header->type,cerebus_packet_header->chid);
            if (cerebus_packet_header->type == 6) {
                
                // This gets the current system time
                gettimeofday(&current_time,NULL);

                // Copy the timestamp information into argv
                memcpy(&argv[ind_timestamps        + 1][n * sizeof(int32_t)       ], &cerebus_packet_header->time, sizeof(int32_t));
                memcpy(&argv[ind_current_time      + 1][n * sizeof(struct timeval)], &current_time,                sizeof(struct timeval));
                memcpy(&argv[ind_udp_received_time + 1][n * sizeof(struct timeval)], &udp_received_time,           sizeof(struct timeval));

                // The index where the data starts in the UDP payload
                int cb_data_ind  = cb_packet_ind + sizeof(cerebus_packet_header_t);

                // Copy each payload entry directly to the argv. dlen contains the number of 5 bytes of payload
                for(int i = 0; i < cerebus_packet_header->dlen * 2; i++) {
                    memcpy(&argv[ind_samples + 1][n * sizeof(int16_t) + i], &udp_packet_payload[cb_data_ind + 2*i], sizeof(int16_t));
                }
                n++;
            }

            // Regardless of what type of packet we got, advance to the next cerebus packet start location
            cb_packet_ind = cb_packet_ind + sizeof(cerebus_packet_header_t) + (4 * cerebus_packet_header->dlen);



            // Now, if we are at the point of transfering data to Redis, we will do so.
            // Begin by assigning argvlen for the channel and timestamp data
            // And then write to num_samples the string instructing just hwo much data we have

            if (n == samples_per_redis_stream) {

                argvlen[ind_samples + 1] = sizeof(int16_t) * n * num_channels;

                argvlen[ind_timestamps + 1]        = sizeof(int32_t) * n;
                argvlen[ind_current_time + 1]      = sizeof(struct timeval) * n;
                argvlen[ind_udp_received_time + 1] = sizeof(struct timeval) * n;
                
                /* printf("n = %d\n", n); */
                /* print_argv(argc, argv, argvlen); */
                /* return 0; */

                // Everything we've done is just to get to this one line. Whew!
                freeReplyObject(redisCommandArgv(redis_context,  argc, (const char**) argv, argvlen));

                
                // Since we've pushed our data to Redis, restart the data collection
                n = 0;
            }
        }
    }

    // We should never get here, but we should clean our data anyway.
    for (int i = 0; i < argc; i++) {
        free(argv[i]);
    }
    free(argvlen);
    free(buffer);
    return 0;
}

//------------------------------------
// Initialization functions
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

    signal(SIGINT, &handler_SIGINT);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

int initialize_socket() {

    // Create a UDP socket
   	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP ); 
    if (fd == 0) {
        perror("[cerebusAdapter] socket failed"); 
        exit(EXIT_FAILURE); 
    }
    int one = 1;
    
    //Set socket permissions so that we can listen to broadcasted packets
    if (setsockopt(fd,SOL_SOCKET,SO_BROADCAST, (void *) &one, sizeof(one)) < 0) {
        perror("[cerebusAdapter] socket permission failure"); 
        exit(EXIT_FAILURE); 
    }

    //Set socket permissions that we get a timestamp from when UDP was received
    if (setsockopt(fd,SOL_SOCKET,SO_TIMESTAMP , (void *) &one, sizeof(one)) < 0) {
        perror("[cerebusAdapter] timestamp failure"); 
        exit(EXIT_FAILURE); 
    }

    // Set timeout for socket, so that we can handle SIGINT cleanly
    struct timeval timeout;      
    timeout.tv_sec = 0;
    timeout.tv_usec = 100000;
    if (setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO , (char *) &timeout, sizeof(timeout)) < 0) {
        perror("[cerebusAdapter] timeout failure"); 
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
    addr.sin_addr.s_addr = htonl(INADDR_ANY); //htonl(INADDR_BROADCAST);
    addr.sin_port        = htons(broadcast_port);

     if (bind(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[cerebusAdapter] socket binding failure\n"); 
        exit(EXIT_FAILURE); 
     }

     printf("[%s] Socket initialized.\n",PROCESS);


     return fd;
} 

void initialize_parameters(yaml_parameters_t *p) {

    char num_channels_string[16] = {0};
    char samples_per_redis_stream_string[16] = {0};

    load_YAML_variable_string(PROCESS, "num_channels", num_channels_string,   sizeof(num_channels_string));
    load_YAML_variable_string(PROCESS, "samples_per_redis_stream", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));

    p->num_channels             = atoi(num_channels_string);
    p->samples_per_redis_stream = atoi(samples_per_redis_stream_string);

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

void shutdown_process() {

    printf("[%s] SIGINT received. Shutting down.\n", PROCESS);

    printf("[%s] Setting scheduler back to baseline.\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 0};
    sched_setscheduler(0, SCHED_OTHER, &sched);

    printf("[%s] Shutting down redis.\n", PROCESS);

    redisFree(redis_context);

    printf("[%s] Exiting.\n", PROCESS);
    
    exit(0);
}

//------------------------------------
// Handler functions
//------------------------------------

void handler_SIGINT(int exitStatus) {
    flag_SIGINT++;
}

//------------------------------------
// Helper function
//------------------------------------

// Quick and dirty function used for debugging purposes
void print_argv(int argc, char **argv, size_t *argvlen) {
    printf("argc = %d\n", argc);

    for (int i = 0; i < 5; i++){
        printf("%02d. (%s) - [%ld]\n", i, argv[i], argvlen[i]);
    }

    for (int i = 5; i < 7; i+=2){
        printf("%02d. (%s) [%ld] - [", i, argv[i], argvlen[i+1]);

        for (int j = 0; j < argvlen[i+1]; j+= sizeof(uint32_t)) {
            printf("%u,",  (uint32_t) argv[i+1][j]);
        }

        printf("]\n");
    }

    for (int i = 7; i < 11; i+=2){
        printf("%02d. (%s) [%ld] - [", i, argv[i], argvlen[i+1]);

        for (int j = 0; j < argvlen[i+1]; j+= sizeof(struct timeval)) {
            struct timeval time;
            memcpy(&time,&argv[i+1][j], sizeof(struct timeval));
            long milliseconds = time.tv_sec * 1000 + time.tv_usec / 1000;
            long microseconds = time.tv_usec % 1000;
            printf("%ld.%03ld,", milliseconds,microseconds);
        }

        printf("]\n");
    }


    for (int i = 11; i < argc; i+=2){
        printf("%02d. (%s) [%ld] - [", i, argv[i], argvlen[i+1]);

        for (int j = 0; j < argvlen[i+1]; j+= sizeof(uint16_t)) {
            printf("%u,",  (uint16_t) argv[i+1][j]);
        }

        printf("]\n");
    }

}

