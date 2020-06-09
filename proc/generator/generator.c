/* Generator.c
 *
 * The program reads from a binary data format (assuming that it's in row-order) and then
 * spits it out at a constant rate. If the PREMEPT_RT kernel module is installed, then it
 * will take advantage of the the module and make itself pre-emptive scheduling. 
 *
 * The code is partially based on the Brainstick project from 2018. Note that the original
 * code used UDP Corking; I needed it then because I was trying to fit the project on a 
 * PiZero and to broadcast 30Khz data, which was a tougher problem.
 *
 * The program has a timer that goes off. When the timer goes off it throws a signal.
 * The signal then posts to a Semaphore. The main loop waits on that semaphore.
 *
 * To speed things up, the data is read in memory ahead of time. 
 *
 * It turns out that this wasn't fast enough on Python, so I had to port it to C.
 *
 * TODO:
 * 1) Make the state variables available through Redis, so that it can hook into rest.py
 *
 * Some variables to consider:
 *  Enable
 *  UDP port
 *  Datafile to read
 *  Number of channels
 *
 * 2) Figure out what the Blackrock header packets read so that the data can be couched in a header
 * 3) Run some verifications of how fast this actually goes. One way to do that is to
 * write a process on the receiving side that looks at the inter-packet interval and look at the
 * variance. Shouldn't be too hard to do. 
 *
 * David Brandman
 * Version 0.2
 * April 2020
 */


// The alarm tools library just takes care of the structures needed for the alarm and signal
// Nothing too fancy

#include "AlarmTools.h"

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
#include <hiredis.h>
#include <time.h>
#include "redisTools.h"


typedef struct cerebus_packet_t {
    uint32_t time;
    uint16_t chid;
    uint8_t type;
    uint8_t dlen;
    uint16_t data[96];
} cerebus_packet_t;

typedef struct yaml_parameters_t {
    int num_channels;
    int cerebus_packet_size;
    int sampling_frequency;
    int broadcast_rate;
    int ramp_max;

} yaml_parameters_t;



int initialize_broadcast_socket();
void initialize_alarm();
void initialize_realtime();
int initialize_from_file(char **, int);
int initialize_ramp(char **, int);
void initialize_parameters(yaml_parameters_t *);
int initialize_buffer(char **, int);

char PROCESS[] = "generator";

// For corking
int one = 1, zero = 0;

// The seamphore that blocks until the alarm goes off
sem_t sem_timer;

// Redis information
redisContext *c;
redisReply *reply;

int main(int argc, char *argv[])
{
    int fd = initialize_broadcast_socket();

    initialize_alarm();
    
    initialize_realtime();

    yaml_parameters_t yaml_parameters;
    initialize_parameters(&yaml_parameters);

    int num_channels        = yaml_parameters.num_channels;
    int sampling_frequency  = yaml_parameters.sampling_frequency;
    int cerebus_packet_size = yaml_parameters.cerebus_packet_size;
    int broadcast_rate      = yaml_parameters.broadcast_rate;


    char *buffer;
    int nRows = initialize_buffer(&buffer, num_channels);

    
	printf("[%s] Entering loop...\n", PROCESS);

    //Sending kill causes tmux to close
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */

    // sampling_frequency is in microseconds. So we add 1e-6 as scaling to get to seconds
    int num_cerebus_packets_per_signal = broadcast_rate * (0.000001 * sampling_frequency);

    printf("[%s] Broadcasting %d packets per %d microseconds...\n", PROCESS, num_cerebus_packets_per_signal, broadcast_rate);
    

    printf("[%s] Entering generator loop...\n", PROCESS);

    int n = 0;
    int num_cerebus_packets_on_udp_packet = 0;

	while(sem_wait(&sem_timer) == 0) {

		for(int i = 0; i < num_cerebus_packets_per_signal; i++) {

			// Write the data
			write(fd, &buffer[n*cerebus_packet_size], cerebus_packet_size);
            num_cerebus_packets_on_udp_packet++;
            n++;
            n = n % nRows;

			if( (num_cerebus_packets_on_udp_packet+1) * cerebus_packet_size >= 1472) {
				setsockopt(fd, IPPROTO_UDP, UDP_CORK, &zero, sizeof(zero));
				setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one));
                num_cerebus_packets_on_udp_packet = 0;
			}
		}

		// Now that we've sent all of the packets we're going to send, uncork and then cork
		setsockopt(fd, IPPROTO_UDP, UDP_CORK, &zero, sizeof(zero));
		setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one));
        num_cerebus_packets_on_udp_packet = 0;
    }

    free(buffer);
    return 0;
}



/**
 * @brief This is called whenever the alarm is called
 */
static void handlerAlarm(int sig)
{
	sem_post(&sem_timer);
}

int initialize_broadcast_socket() {

    printf("[%s] Initializing socket...\n", PROCESS);
    //
    // Create a socket. I think IPPROTO_UDP is needed for broadcasting
   	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP ); 
    if (fd == 0) {
        perror("[generator] socket failed"); 
        exit(EXIT_FAILURE); 
    }

    //Set socket permissions
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

    // I connect here instead of using sentto because it's faster; kernel doesn't need to make
    // the necessary checks because it already has a valid file descriptor for the socket


	setsockopt(fd, IPPROTO_UDP, UDP_CORK, &one, sizeof(one)); // CORK


    if (connect(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[generator] connect error");
        exit(EXIT_FAILURE);
    }

    return fd;
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
    load_YAML_variable_string(PROCESS, "broadcast_rate", num_microseconds_string, sizeof(num_microseconds_string));
    int num_microseconds = atoi(num_microseconds_string);

    printf("[%s] Setting the broadcast rate to %d microseconds...\n", PROCESS, num_microseconds);

	// How many nanoseconds do we wait between reads. Note:  1000 nanoseconds = 1us
	InitializeAlarm(handlerAlarm, 0, num_microseconds * 1000);

}

// Do we want the system to be realtime?  Setting the Scheduler to be real-time, priority 80
void initialize_realtime() {
    printf("[%s] Setting Real-time scheduler!\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 80};
    sched_setscheduler(0, SCHED_FIFO, &sched);
}

void initialize_parameters(yaml_parameters_t *p) {

    char string[16];
   
    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "num_channels", string, sizeof(string));
    p->num_channels = atoi(string);

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "sampling_frequency", string, sizeof(string));
    p->sampling_frequency = atoi(string);

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "cerebus_packet_size", string, sizeof(string));
    p->cerebus_packet_size = atoi(string);

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "broadcast_rate", string, sizeof(string));
    p->broadcast_rate = atoi(string);

    memset(string, 0, 16 * sizeof(char));
    load_YAML_variable_string(PROCESS, "ramp_max", string, sizeof(string));
    p->ramp_max = atoi(string);
}

//---------------------------------------------------------
// Buffer initialization functions
//---------------------------------------------------------

int initialize_buffer(char **buffer, int numChannels) {

    char use_ramp_string[16] = {0};
    load_YAML_variable_string(PROCESS, "use_ramp", use_ramp_string, sizeof(use_ramp_string));

    if (strcmp(use_ramp_string, "True") == 0) {
        printf("[%s] Generating data from a ramp.\n", PROCESS);
        return initialize_ramp(buffer, numChannels);
    } else {
        printf("[%s] Generating data from a file.\n", PROCESS);
        return initialize_from_file(buffer, numChannels);
    }

}

int initialize_ramp(char  **buffer, int num_channels) {

    printf("[%s] Initializing ramp function...\n", PROCESS);

    char ramp_max_string[16] = {0};
    load_YAML_variable_string(PROCESS, "ramp_max", ramp_max_string, sizeof(ramp_max_string));
    int ramp_max = atoi(ramp_max_string);
    printf("[%s] Ramp goes from 0 to %d.\n", PROCESS, ramp_max);

    
    *buffer = malloc(sizeof(cerebus_packet_t) * ramp_max);

    for (int i = 0; i < ramp_max; i++) {
        
        cerebus_packet_t cerebus_packet = {0};
        cerebus_packet.time = i;
        for (int j = 0; j < num_channels; j++) {
            cerebus_packet.data[j] = i;
        }
        memcpy(&(*buffer)[i*sizeof(cerebus_packet_t)], &cerebus_packet, sizeof(cerebus_packet_t));
    }

    return ramp_max;

}
int initialize_from_file(char **buffer, int numChannels) {


    char filename[16] = {0};
    load_YAML_variable_string(PROCESS, "filename", filename, sizeof(filename));

    printf("Finding the file %s to load into memory...\n", filename);
    FILE *dataFILE;
    if ((dataFILE = fopen(filename, "rb")) == NULL) {
        perror("Fopen: ");
        exit(1);
    }
    
    // First, how big is this file? Go to end and then rewind
    fseek(dataFILE, 0L, SEEK_END);
    int dataSize = ftell(dataFILE);
    rewind(dataFILE);

    printf("File size: %d bytes\n", dataSize);

    int nRows = dataSize / numChannels;

    // Now load the file in memory. This will get automatically released when the program
    // closes since it's not being malloced in a subprocess or daemon. Whew!
	*buffer =  malloc(dataSize);
    int readLength;
    if ( (readLength = fread(*buffer, 1, dataSize, dataFILE)) < 0) {
        printf("[%s] Could not read file. Aborting.\n", PROCESS);
        exit(1);
    }

    // Now that the data is in memory we're done
    fclose(dataFILE);
    return nRows;
}


    /* int nRows = maxValue * numChannels * sizeof(int16_t); */
    /* *buffer =  (int16_t *) malloc(nRows); */

    /* int index = 0; */
    /* for (int i = 0; i < maxValue; i++) { */
    /*     for (int j = 0; j < numChannels; j++) { */
    /*         (*buffer)[index] = i; */
    /*         index++; */
    /*     } */
    /* } */
