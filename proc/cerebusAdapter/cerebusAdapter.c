/* cerebusAdapter.c
 * Converts cerebrus generic packets to the UDP stream
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
// https://github.com/neurosuite/libcbsdk. Note initial definition does not include
// the int16_t data[96] component. I added that for convenience

typedef struct cerebus_packet_t {
    uint32_t time;
    uint16_t chid;
    uint8_t type;
    uint8_t dlen;
    int16_t data[96];
} cerebus_packet_t;

// List of parameters read from the yaml file, facilitates function definition of initialize_parameters
typedef struct yaml_parameters_t {
    int num_channels;
    int samples_per_redis_stream;
} yaml_parameters_t;

void initialize_redis();
void initialize_signals();
int initialize_socket();
void initialize_parameters(yaml_parameters_t *p);
void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);

char PROCESS[] = "cerebusAdapter";

redisContext *redis_context;



int main (int argc_main, char **argv_main) {

    initialize_redis();

    initialize_signals();

    int udp_fd = initialize_socket();

    yaml_parameters_t yaml_parameters = {0};
    initialize_parameters(&yaml_parameters);

    int num_channels             = yaml_parameters.num_channels;
    int samples_per_redis_stream = yaml_parameters.samples_per_redis_stream;


    //////////////////////////////////////////////

    // max_samples : we expect to send samples_per_redis_stream entries per xadd command
    //               however, if we have dropped packets we can run into problems where
    //               we could potentially write more than the samples_per_redis_stream
    //               value. Just in case, we will add a buffer to prevent overflows. We will
    //               never receive more than 7 cerebus packets per UDP packet

    int max_samples  = samples_per_redis_stream + 7;


    // argc    : The number of arguments in argv. The calculation is:
    //           int argc = 3 + 2 * (2 + num_channels);
    //           3 -> xadd cerebusAdapter *
    //           (2 + num_channels) -> num_samples , timestamps, channels
    //           2 * ()             -> (key, value) pairs
    // argvlen : The length of the strings in each argument of argv
    
    int argc        = 3 + 2 * (2 + num_channels);
    size_t *argvlen = malloc(argc * sizeof(size_t));


    // argv : This contains the number of arguments to be executed by redis. 
    //        the argv has the form:
    //        xadd cerebusAdapter * num_samples [string] timestamps [int32] chan0 [int16] chan1 [int16] ...
    //        We begin by populating the entries manually
    //        Starting at index position [3], we start adding the key data, always of form key [value]
    //        So that the key identifier (i.e. the string) is an odd number and the value is even
    
    // We keep track of the indexes. Each ind_ variable keeps track of where the (key value) begins
     

    int ind_xadd        = 0;                   // xadd cerebusAdapter *
    int ind_num_samples = ind_xadd + 3;        // num_samples string
    int ind_timestamps  = ind_num_samples + 2; // timestamps [data]
    int ind_samples     = ind_timestamps + 2;  // chan0 [data] chan1 [data] ...


    //////////////////////////////////////////
    // Now we begin the arduous task of allocating memory. We want to be able to hold
    // data of types strings, int16 and int32, so we need to be careful.
    // 
    //

    int len = 16;
    char *argv[argc];

    // allocating memory for xadd cerebus *
    for (int i = 0; i < ind_num_samples; i++) {
        argv[i] = malloc(len);
    }

    // allocating memory for num_samples string
    argv[ind_num_samples]     = malloc(len);
    argv[ind_num_samples + 1] = malloc(len);

    // allocating memory for timestamps [data]
    argv[ind_timestamps]     = malloc(len);
    argv[ind_timestamps + 1] = malloc(sizeof(int32_t) * max_samples);
    
    // allocating memory for chan0 [data] chan1 [data] ...
    for(int i = 0; i < num_channels; i++) {
        argv[ind_samples + 2*i] = malloc(len);
        argv[ind_samples + 2*i + 1] = malloc(sizeof(int16_t) * max_samples);
    }
    //////////////////////////////////////////


    // At this point we start populating argv
    // Start by adding xadd cerebusAdapter *
    // And then add the keys for num_samples, timestamps, and all of the channels

    argvlen[0] = (size_t) strcpy(argv[0],  "xadd");
    argvlen[1] = (size_t) strcpy(argv[1],  "cerebusAdapter");
    argvlen[2] = (size_t) strcpy(argv[2],  "*");
    
    argvlen[ind_num_samples] = (size_t) strcpy(argv[ind_num_samples] , "num_samples");
    argvlen[ind_timestamps]  = (size_t) strcpy(argv[ind_timestamps]  , "timestamps");

    for (int i = 0; i < num_channels; i++) {
        argvlen[ind_samples + 2*i] = (size_t) sprintf(argv[ind_samples + 2*i], "chan%01d", i);
    }


    // Sending kill causes tmux to close
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    // we will copy the UDP packet buffer directly into an array of cerebus_packet_t arrays
    // n -> keep track of how many cerebus_packets we have copied

    cerebus_packet_t cerebus_packets[7] = {0};
    int n = 0;

    printf("[%s] Entering loop...\n", PROCESS);

    while (1) {

        int read_bytes = recv(udp_fd, cerebus_packets, sizeof(cerebus_packets), 0); 

        // Check to see if something went wrong. TODO: Add more checks
        if (read_bytes <= 0 || read_bytes % sizeof(cerebus_packets) != 0) {
            continue;
        }



        // We expect that the data will arrive as a series of cerebus packets concatenated in a UDP packet
        // Let's first compute how many cerebus_packets_t we've received

        int num_cerebus_packets = read_bytes / sizeof(cerebus_packet_t);



        // Now for each of the cerebrus packets, copy the samples from the cerebus_packet_t data field.
        // We want to set up the argv immediately. The +1 offset is for the data associated with a key
        // Since we're storing all voltage data as int16, and the timestamps as int32, we need to be careful
        // argv has dimensions [keys][samples]. So that means...
        // ind_samples + j*2 + 1 : start at ind_samples, and then jump to index corresponding to value for key j*2
        // n * sizeof(in16_t) : we're expecting data of size int16_t, so offset based on how many samples we have

        for (int i = 0; i < num_cerebus_packets; i++) {
            for(int j = 0; j < num_channels; j++) {

                memcpy(&argv[ind_samples + j*2 + 1][n * sizeof(int16_t)], &cerebus_packets[i].data[j], sizeof(int16_t));
                memcpy(&argv[ind_timestamps + 1][n * sizeof(int32_t)]   , &cerebus_packets[i].data   , sizeof(int32_t));
            }
            n++;
        }


        // Now, if we are at the point of transfering data to Redis, we will do so.
        // Begin by assigning argvlen for the channel and timestamp data
        // And then write to num_samples the string instructing just hwo much data we have

        if (n >= samples_per_redis_stream) {

            for (int i = 0; i < num_channels; i++) {
                argvlen[ind_samples + i*2 + 1] = sizeof(int16_t) * n;
            }

            argvlen[ind_timestamps + 1] = sizeof(int32_t) * n;
            argvlen[ind_samples + 1]    = sprintf(argv[ind_samples+1], "%d", n);
            
            // Everything we've done is just to get to this one line. Whew!
            freeReplyObject(redisCommandArgv(redis_context,  argc, (const char**) &argv, argvlen));
            
            n = 0;
        }
    }
    for (int i = 0; i < argc; i++) {
        free(argv[i]);
    }
    free(argvlen);
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
        printf("error: %s\n", redis_context->errstr);
        exit(1);
    }

    printf("[%s] Redis initialized.\n", PROCESS);
     
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
        perror("[cerebusAdapter] socket failed"); 
        exit(EXIT_FAILURE); 
    }
    //Set socket permissions so that we can listen to broadcasted packets
    int broadcastPermission = 1;
    if (setsockopt(fd,SOL_SOCKET,SO_BROADCAST, (void *) &broadcastPermission, sizeof(broadcastPermission)) < 0) {
        perror("[cerebusAdapter] socket permission failure"); 
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
    load_YAML_variable_string(PROCESS, "num_channels", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));

    p->num_channels             = atoi(num_channels_string);
    p->samples_per_redis_stream = atoi(samples_per_redis_stream_string);

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


