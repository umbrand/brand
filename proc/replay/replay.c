/* Replay.c
 * David Brandman
 * Version 0.1
 * June 2020
 *
 * The goal of this process is to replay pcap-like data for validation of the other rig modules.
 * This process is designed to read a binary data file, where the contents is the concatenation of
 * the UDP packet payloads coming out of a cerebus.
 *
 * Hence, one potential workflow is as follows:
 * 1. Use wireshark or tcpdump to capture raw packets into a pcap file
 * 2. Strip the pcap file of IP headers, retaining only the UDP payload
 * 3. Concatenate all of the UDP payloads in series, making one large file
 * 4. Load that file into a buffer, and then begin replaying packets
 *
 * replay.c waits for SIGALRM, which by default it manages itself. Upon receiving a 
 * signal it then starts reading from the buffer and interpreting the data as a series
 * of cerebus packets. It will send out a total of sampling_frequency / broadcast_rate
 * packets of type=6 per signal. So, replay.c could potentially send out many more than
 * 30 packets per signal, if there are multiple types beyond type 6. 
 * It uses UDP corking to make the logic much easier to reason about.
 *
 * Note that you can easily yolk replay.c to timer.c, by installing a listener for SIGUSR1
 */



//#include <fcntl.h> // splice()
#include <semaphore.h> // semaphore
#include <errno.h>
#include <string.h>
#include <sched.h> // set_scheduler()
#include <stdlib.h> // rand()
#include <signal.h>
#include <sys/socket.h> 
#include <netinet/in.h> 
#include <netinet/udp.h>
#include <stdio.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include "redisTools.h"


// Originall defined here: 
// https://github.com/dashesy/CereLink/blob/master/cbhwlib/cbhwlib.h

typedef struct cerebus_packet_t {
    uint32_t time;
    uint16_t chid;
    uint8_t type;
    uint8_t dlen;
} cerebus_packet_t;

// Parameters worth loading from replay.yaml
typedef struct yaml_parameters_t {
    int sampling_frequency;
    int broadcast_rate;

} yaml_parameters_t;



int  initialize_broadcast_socket();
void initialize_alarm();
void initialize_realtime();
int  initialize_from_file(char **);
void initialize_parameters(yaml_parameters_t *);
void initialize_signals();
void handler_SIGINT(int signum);
void handler_SIGALRM(int signum);
void shutdown_process();

char PROCESS[] = "replay";

// For corking
int one = 1, zero = 0;

// Keep track of when the signals fire
int flag_SIGINT  = 0;
int flag_SIGALRM = 0;



int main(int argc, char *argv[])
{
    int fd = initialize_broadcast_socket();
    
    initialize_realtime();

    initialize_signals();

    yaml_parameters_t yaml_parameters;
    initialize_parameters(&yaml_parameters);
    int sampling_frequency          = yaml_parameters.sampling_frequency;
    int broadcast_rate              = yaml_parameters.broadcast_rate;
    int cerebus_packets_per_SIGALRM = sampling_frequency / broadcast_rate;

    char *buffer;
    int buffer_size = initialize_from_file(&buffer);



    // N.B. This should be the last thing to be done, to prevent signals 
    // occuring during YAML file reads
    initialize_alarm();


	printf("[%s] Entering loop...\n", PROCESS);
    int buffer_ind = 0;

    while (1) {

        pause();

        if (flag_SIGINT) 
            shutdown_process();

        if (flag_SIGALRM) {

            int num_cb_data_packets = 0;
            int udp_packet_size = 0;

            while(num_cb_data_packets < cerebus_packets_per_SIGALRM ) {

                // The cerebus packet definitions use dlen to mean how many 
                // the number of 4 bytes 
                cerebus_packet_t *cb_packet = (cerebus_packet_t *) &buffer[buffer_ind];
                int cb_packet_size = sizeof(cerebus_packet_t) + (cb_packet->dlen * 4);

                write(fd, &buffer[buffer_ind], cb_packet_size);

                udp_packet_size += cb_packet_size;
                buffer_ind      += cb_packet_size;

                // Prevent index out of bounds problems
                if (buffer_ind >= buffer_size) {
                    buffer_ind = 0;
                }

                // Having read the packet, we then ask if writing the next packet
                // will take us over. If yes, then uncork/cork again.
                cerebus_packet_t *next_cb_packet = (cerebus_packet_t *) &buffer[buffer_ind];
                int next_cb_packet_size = sizeof(cerebus_packet_t) + (next_cb_packet->dlen*4);

                if (udp_packet_size + next_cb_packet_size >= 1472) {
                    setsockopt(fd, IPPROTO_UDP, UDP_CORK, &zero, sizeof(zero));
                    setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one));
                    udp_packet_size = 0;
                }

                if (cb_packet->type == 6) {
                    num_cb_data_packets++;
                }

            }
            
            // Now that we've sent all of the packets we're going to send, uncork and then cork
            setsockopt(fd, IPPROTO_UDP, UDP_CORK, &zero, sizeof(zero));
            setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one));

            flag_SIGALRM--;
        }
    }

    free(buffer);
    return 0;
}


int initialize_broadcast_socket() {

    printf("[%s] Initializing socket...\n", PROCESS);
    
    // Create a socket. I think IPPROTO_UDP is needed for broadcasting
   	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP ); 
    if (fd == 0) {
        perror("[generator] socket failed"); 
        exit(EXIT_FAILURE); 
    }

    //Set Braodcast socket option
    int broadcastPermission = 1;
    if (setsockopt(fd,SOL_SOCKET,SO_BROADCAST , (void *) &broadcastPermission, sizeof(broadcastPermission)) < 0) {
        perror("[generator] socket permission failure"); 
        exit(EXIT_FAILURE); 
    }

    // Load the broadcast port from the YAML file
    char broadcast_port_string[16] = {0};
    load_YAML_variable_string(PROCESS, "broadcast_port", broadcast_port_string, sizeof(broadcast_port_string));
    int broadcast_port = atoi(broadcast_port_string);
    printf("[%s] I will be emitting on port %d\n", PROCESS, broadcast_port);


    // Now configure the socket
    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    addr.sin_port        = htons(broadcast_port);

    // Start corking right away
	setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one)); // CORK

    // I connect here instead of using sentto because it's faster; kernel doesn't need to make
    // the necessary checks because it already has a valid file descriptor for the socket
    if (connect(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[generator] connect error");
        exit(EXIT_FAILURE);
    }

    return fd;
}

void initialize_alarm(){

    printf("[%s] Initializing alarm...\n", PROCESS);

    // We want to specify out rate in microseconds from YAML
    char num_microseconds_string[16] = {0};
    load_YAML_variable_string(PROCESS, "broadcast_rate", num_microseconds_string, sizeof(num_microseconds_string));
    int num_microseconds = atoi(num_microseconds_string);

    printf("[%s] Setting the broadcast rate to %d microseconds...\n", PROCESS, num_microseconds);

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


    struct sched_param sched= {.sched_priority = 80};
    if(sched_setscheduler(0, SCHED_FIFO, &sched) < 0) {
        printf("[%s] ERROR SCHED_FIFO SCHEDULER\n", PROCESS);
    }

}

void initialize_parameters(yaml_parameters_t *p) {

    char string[16];

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "broadcast_rate", string, sizeof(string));
    p->broadcast_rate = atoi(string);

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "sampling_frequency", string, sizeof(string));
    p->sampling_frequency = atoi(string);
}

//---------------------------------------------------------
// Buffer initialization functions
//---------------------------------------------------------


int initialize_from_file(char **buffer) {

    char filename[16] = {0};
    load_YAML_variable_string(PROCESS, "filename", filename, sizeof(filename));

    printf("[%s] Loading file %s to memory...\n", PROCESS, filename);
    FILE *dataFILE;
    if ((dataFILE = fopen(filename, "rb")) == NULL) {
        printf("[%s] Could not open file: %s\n", PROCESS, filename);
        exit(1);
    }
    
    // First, how big is this file? Go to end and then rewind
    fseek(dataFILE, 0L, SEEK_END);
    int dataSize = ftell(dataFILE);
    rewind(dataFILE);

    printf("[%s] File size: %d bytes\n", PROCESS, dataSize);

    // Now load the file in memory. This will get automatically released when the program
    // closes since it's not being malloced in a subprocess or daemon. Whew!
	*buffer =  malloc(dataSize);
    int readLength;
    if ( (readLength = fread(*buffer, 1, dataSize, dataFILE)) < 0) {
        printf("[%s] Could not copy file to buffer.\n", PROCESS);
        exit(1);
    }

    // Now that the data is in memory we're done
    fclose(dataFILE);
    return readLength;
}

void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    signal(SIGINT, &handler_SIGINT);
    signal(SIGALRM, &handler_SIGALRM);
    signal(SIGUSR1, &handler_SIGALRM);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}

void handler_SIGINT(int signum) {
    flag_SIGINT++;
}
void handler_SIGALRM(int signum) {
    flag_SIGALRM++;
}
void shutdown_process() {
    printf("[%s] SIGINT received. Shutting down.\n", PROCESS);

    printf("[%s] Exiting.\n", PROCESS);
    
    exit(0);

}
