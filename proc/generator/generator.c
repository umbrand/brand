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


int initialize_broadcast_socket();
void initialize_alarm();
void initialize_realtime();
int initialize_from_file(int16_t **, int);
int initialize_ramp(int16_t **, int);
int initialize_num_channels();
int initialize_buffer(int16_t **, int);
void readYAML();

char PROCESS[] = "generator";

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

    int num_channels = initialize_num_channels();

    int16_t *buffer;
    int nRows = initialize_buffer(&buffer, num_channels);

    
	printf("[%s] Entering loop...\n", PROCESS);
    int index = 0;

    /* Sending kill causes tmux to close */
    pid_t ppid = getppid();
    kill(ppid, SIGUSR2);

	while(sem_wait(&sem_timer) == 0) {

        int startInd = (index % nRows) * num_channels;

        if (send(fd, &buffer[startInd], num_channels * sizeof(int16_t), 0) < 0) {
            perror("sendto");
            exit(1);
        }
        index++;
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

    if (connect(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("[generator] connect error");
        exit(EXIT_FAILURE);
    }

    return fd;
}

void initialize_alarm(){

    printf("[%s] Initializing alarm...\n", PROCESS);
    //
	// Initialize the Semaphore used to indicate new data should be sent
	if (sem_init(&sem_timer, 0, 0) < 0) {
		printf("Could not initialize Semaphore! Exiting.\n");
		exit(1);
	}

    // We want to specify out rate in milliseconds from YAML
    
    char num_milliseconds_string[16] = {0};
    load_YAML_variable_string(PROCESS, "broadcast_rate", num_milliseconds_string, sizeof(num_milliseconds_string));
    int num_milliseconds = atoi(num_milliseconds_string);
    printf("[%s] Setting the broadcast rate to %d milliseconds...\n", PROCESS, num_milliseconds);

	// How many nanoseconds do we wait between reads. Note:  1000000 nanoseconds = 1ms
	InitializeAlarm(handlerAlarm, 0, num_milliseconds * 1000000);

}

// Do we want the system to be realtime?  Setting the Scheduler to be real-time, priority 80
void initialize_realtime() {
    printf("[%s] Setting Real-time scheduler!\n", PROCESS);
    const struct sched_param sched= {.sched_priority = 80};
    sched_setscheduler(0, SCHED_FIFO, &sched);
}

int initialize_from_file(int16_t  **buffer, int numChannels) {


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

int initialize_ramp(int16_t  **buffer, int numChannels) {

    printf("[%s] Initializing ramp function...\n", PROCESS);

    int maxValue = 2000;

    int nRows = maxValue * numChannels * sizeof(int16_t);
    *buffer =  (int16_t *) malloc(nRows);

    int index = 0;
    for (int i = 0; i < maxValue; i++) {
        for (int j = 0; j < numChannels; j++) {
            (*buffer)[index] = i;
            index++;
        }
    }

    return maxValue;

}

int initialize_num_channels() {

    char num_channels_string[16] = {0};
    load_YAML_variable_string(PROCESS, "num_channels", num_channels_string, sizeof(num_channels_string));

    return atoi(num_channels_string);

}
int initialize_buffer(int16_t **buffer, int numChannels) {

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

            /* if(item->type == NX_JSON_OBJECT) { */
            /*     printf("I AM AN OBJECT\n"); */
            /* } */

            // Get the name of this variable
            /* sprintf(nameBuffer, "%s", nx_json_get(variable, "name")->text_value); */ 
            /* sprintf(stringList[i], "%s", nameString); */

            /* int l = strlen(nameString) + 1; */

            /* sprintf(redisBuffer, "%s %s", item->key, valueBuffer); */
            /* printf("LINE: %s\n", redisBuffer); */

            /* switch (value->type) { */
            /*     case NX_JSON_INTEGER : sprintf(valueBuffer, "%lld", value->int_value ); break; */
            /*     case NX_JSON_BOOL    : sprintf(valueBuffer, "%lld", value->int_value ); break; */
            /*     case NX_JSON_STRING  : sprintf(valueBuffer, "%s",   value->text_value); break; */
            /*     case NX_JSON_DOUBLE  : sprintf(valueBuffer, "%f",   value->dbl_value ); break; */
            /* } */

            /* sprintf(stringList[i], "%s %s", nameBuffer, valueBuffer); */

/* static void HandlerInt(int sig) */
/* { */
/* 	fprintf("Interrupt called... Freeing memory!"); */
/* 	Display("Exiting Writer!"); */
/* 	exit(1); */
/* } */

/* THIS CODE TOOK ME AN ENTIRE DAY TO GET TO WORK, AND NOW ITS NO LONGER NEEDED */
/* void readYAML(){ */
/*     //begin by reading the YAML file and convert it to JSON */
/*     //The popen() command is used to run a one line python script that converts YAML to JSON */
/*     //The libraries for JSON are more robust than those for YAML for C */

/*     FILE *fp; */
/* 	char *jsonBuffer = malloc(4096); */

/*     fp = popen("python -c \"import sys, yaml, json; f=open('generator.yaml','r'); print(json.dumps(yaml.safe_load(f)))\"", "r"); */
/*     if (fp == NULL) { */
/*         perror("Failed to convert YAML to JSON.\n" ); */
/*         exit(1); */
/*     } */
/*     fread (jsonBuffer, 1, 4096, fp); */

/*     // Now I have a jsonBuffer containing JSON. I am going to parse it for useful information */
/*     // This is based on the nxjson library which I chose because the API was so simple and I found it intuitive */
/*     // So you get the pointer to the JSON buffer and then ask how many variables there are */
/*     // You go through each variable and cover it to a string */
/*     // Then you write the string and name to Redis */
/*     //https://bitbucket.org/yarosla/nxjson/src/default/ */

/*     printf("Trying to parse JSON buffer...\n"); */
/*     const nx_json* json = nx_json_parse_utf8(jsonBuffer); */
/*     if (json->type != NX_JSON_ARRAY) { */
/*         printf("Something went wrong parsing the Json array. Barfing.\n"); */
/*         exit(1); */
/*     } */

/*     int numVariables = json->length; */
/*     char *nameList[numVariables]; */
/*     char *valueList[numVariables]; */
    
/*     printf("Found %d variables in the JSON buffer...\n", numVariables); */
/*     for (int i = 0; i < numVariables; i++) { */

/*         // Find the name of the variable, create memory and then copy the value */
/*         const nx_json* variable = nx_json_item(json, i); */
/*         const char *nameString = nx_json_get(variable, "name")->text_value; */ 
/*         nameList[i] = malloc(strlen(nameString)); */
/*         strcpy(nameList[i], nameString); */

/*         // Find the value of the variable, create memory and then copy the value. TODO: Do this better */
/*         const nx_json* value = nx_json_get(variable, "value"); */
/*         valueList[i] = malloc(256); */

/*         switch (value->type) { */
/*             case NX_JSON_INTEGER : sprintf(valueList[i], "%lld",  value->int_value ); break; */
/*             case NX_JSON_BOOL    : sprintf(valueList[i], "%lld",  value->int_value ); break; */
/*             case NX_JSON_STRING  : sprintf(valueList[i], "%s",    value->text_value); break; */
/*             case NX_JSON_DOUBLE  : sprintf(valueList[i], "%f",    value->dbl_value ); break; */
/*         } */
/*     } */

/*     // At this point I have an array of strings, which contain the information that will be */
/*     // used to initialize Redis. Now I need to find out Redis IP and port */
        
/*     char *redisIP; */
/*     char *redisPort; */

/*     for (int i = 0; i < numVariables; i++) { */

/*         if (strcmp(nameList[i], "redisIP") == 0) { */
/*             redisIP = valueList[i]; */
/*         } */
/*         if (strcmp(nameList[i], "redisPort") == 0) { */
/*             redisPort = valueList[i]; */
/*         } */
/*     } */
/*     printf("From Json, I have redis ip: %s, port: %s\n", redisIP, redisPort); */

/*     //Now I connect to the server with this IP and port information */

/*     const char *hostname = redisIP; */
/*     int port = atoi(redisPort); */
/*     struct timeval timeout = { 1, 500000 }; // 1.5 seconds */

/*     c = redisConnectWithTimeout(hostname, port, timeout); // Global variable */
/*     if (c == NULL || c->err) { */
/*         if (c) { */
/*             printf("Connection error: %s\n", c->errstr); */
/*             redisFree(c); */
/*         } else { */
/*             printf("Connection error: can't allocate redis context\n"); */
/*         } */
/*         exit(1); */
/*     } */

/*     // Having initialized Redis connection, I will add each of the varibles */


/*     for (int i = 0; i < numVariables; i++) { */
/*         freeReplyObject(redisCommand(c, "set %s %s", nameList[i], valueList[i])); */
/*     } */

/*     /1* printf("Redis Initialization Complete!\n"); *1/ */
        
/*     for (int i = 0; i < numVariables; i++) { */
/*         free(nameList[i]); */
/*         free(valueList[i]); */
/*     } */

/*     nx_json_free(json); */
/*     free(jsonBuffer); */

/* } */

