#include <stdlib.h>
#include <stdio.h>
#include <unistd.h> /* close() */
#include <pthread.h>
#include <fcntl.h> // File control definitions
#include <linux/input.h>
#include <signal.h>
#include <string.h>
#include "redisTools.h"
#include "hiredis.h"

#define MOUSE_RELATIVE 1
#define MOUSE_ABSOLUTE 2

// List of parameters read from the yaml file, facilitates function definition
// of initialize_parameters
typedef struct yaml_parameters_t {
	int samples_per_redis_stream;
} yaml_parameters_t;


void initialize_redis();
void initialize_signals();
void handler_SIGINT(int exitStatus);
void handler_SIGUSR1(int exitStatus);
void initialize_parameters(yaml_parameters_t *p);
void shutdown_process();

char PROCESS[] = "mouse_ac";
redisReply *reply;
redisContext *redis_context;

int flag_SIGINT = 0;
int flag_SIGUSR1 = 0;

int32_t mouseData[2];  // (change in) X, Y position
int mouseMode = 0;
pthread_t listenerThread;
pthread_t publisherThread;

int mouse_fd = -1;  // file descriptor for the mouse input
// mutex for mouseData
pthread_mutex_t mouseDataMutex = PTHREAD_MUTEX_INITIALIZER;

void * mouseListenerThread(void * thread_params) {
	pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, NULL);

	struct input_event ev;  // mouse input event
	int rd = 0;  // read status of mouse

	// wait for mouse input
	while(1) {

		rd = read(mouse_fd, &ev, sizeof(struct input_event));  // wait for input
		if (rd < (int) sizeof(struct input_event)) {
			perror("Mouse: error reading \n");
			exit(1);
		}
		pthread_mutex_lock(&mouseDataMutex);
		
		// What kind of event?
		if(ev.type == EV_REL) {  // mouse movements
			switch(ev.code) {
				case REL_X :  // change in X position
					mouseData[0] += ev.value;
					break;
				case REL_Y :  // change in Y position
					mouseData[1] += ev.value;
					break;
			}
		}
		pthread_mutex_unlock(&mouseDataMutex);
	}
	return 0;
}




int main() {
	int rc;

	initialize_redis();
	initialize_signals();

	// bring in parameters from the yaml setup file
	yaml_parameters_t yaml_parameters = {};
	initialize_parameters(&yaml_parameters);
	int32_t sampPerRedis = yaml_parameters.samples_per_redis_stream;

	// array to keep track of system time
	struct timespec current_time;

	// number of arguments etc for calls to redis
	int argc = 7; // number of arguments: "xadd mouse_ac * timestamps [timestamps] samples [X Y]"
	size_t *argvlen = malloc(argc * sizeof(size_t)); // an array of the length of each argument put into Redis. This initializes the array

	int ind_xadd = 0; // xadd mouse_ac *
	int ind_timestamps = ind_xadd + 3; // timestamps [timestamps]
	int ind_samples = ind_timestamps + 2; // samples [X Y] -- putting them in an array together rather than having a separate entry for each
	
	// allocating memory for the actual data being passed
	int len = 16;
	char *argv[argc];

	// xadd mouse_ac *
	for (int i = 0; i < ind_timestamps; i++) {
		argv[i] = malloc(len);
	} 

	// timestamps and sample array
	argv[ind_timestamps] = malloc(len);
	argv[ind_timestamps+1] = malloc(sizeof(struct timespec));
	argv[ind_samples]   = malloc(len);
	double samples[2 * sampPerRedis];
	argv[ind_samples+1] = malloc(2 * sampPerRedis * sizeof(double)); // number of samples * two inputs * float64 size

	// populating the argv strings
	// start with the "xadd mouse_ac"
	argvlen[0] = sprintf(argv[0], "%s", "xadd"); // write the string "xadd" to the first position in argv, and put the length into argv
	argvlen[1] = sprintf(argv[1], "%s", "mouse_ac"); //same for cerebus adapter
	argvlen[2] = sprintf(argv[2], "%s", "*");

	// and the samples array label
	argvlen[ind_timestamps] = sprintf(argv[ind_timestamps], "%s", "timestamps");
	argvlen[ind_samples] = sprintf(argv[ind_samples], "%s", "samples"); // samples label


	mouse_fd = open("/dev/input/by-id/usb-Razer_Razer_Viper-event-mouse",
		O_RDONLY);
	// Mouse Initialization
	if (mouse_fd < 0) {
		printf("Error opening mouse. Status code %d.\n", mouse_fd);
		return 1;
	}

	/* Spawn Mouse thread */
	printf("Starting Mouse Thread \n");
	rc = pthread_create(&listenerThread, NULL, mouseListenerThread, NULL);
	if(rc) {
		printf("Mouse thread failed to initialize!!\n");
	}


	/* server infinite loop */
	while(1) {
		pause();

		if (flag_SIGINT)
			shutdown_process();

		if (flag_SIGUSR1) {
			// read from the mouse
			samples[0] = mouseData[0];
			samples[1] = mouseData[1];
			*argv[ind_samples + 1] = *samples;

			// read the current time into the array
			clock_gettime(CLOCK_MONOTONIC, &current_time);
			memcpy(&argv[ind_timestamps + 1][sizeof(struct timespec)], &current_time,
				sizeof(struct timespec));

			// send everything to Redis
			freeReplyObject(redisCommandArgv(redis_context, argc, (const char**) argv, argvlen));

			flag_SIGUSR1--;
		}

	}

	return 0;

}


void initialize_redis() {

	printf("[%s] Initializing Redis...\n", PROCESS);

	char redis_ip[16]       = {0};
	char redis_port[16]     = {0};

	load_YAML_variable_string(PROCESS, "redis_ip", redis_ip, sizeof(redis_ip));
	load_YAML_variable_string(PROCESS, "redis_port", redis_port,
		sizeof(redis_port));

	printf("[%s] From YAML, I have redis ip: %s, port: %s\n", PROCESS, redis_ip,
		redis_port);

	printf("[%s] Trying to connect to redis.\n", PROCESS);

	redis_context = redisConnect(redis_ip, atoi(redis_port));
	if (redis_context->err) {
		printf("[%s] Redis connection error: %s\n", PROCESS,
			redis_context->errstr);
		exit(1);
	}

	printf("[%s] Redis initialized.\n", PROCESS);
}

void initialize_signals() {

	printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

	signal(SIGINT, &handler_SIGINT);
	signal(SIGUSR1, &handler_SIGUSR1);

	printf("[%s] Signal handlers installed.\n", PROCESS);
}

//------------------------------------
// Handler functions
//------------------------------------


void initialize_parameters(yaml_parameters_t *p) {
	// create the strings to pull everything in from the yaml file
	char samples_per_redis_stream_string[16] = {0};

	// pull it in from the YAML
	load_YAML_variable_string(PROCESS, "samples_per_redis_stream",
		samples_per_redis_stream_string, 
		sizeof(samples_per_redis_stream_string));

	// add it into yaml parameters struct
	p->samples_per_redis_stream = atoi(samples_per_redis_stream_string);

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

void handler_SIGUSR1(int signum) {
	flag_SIGUSR1++;
}
