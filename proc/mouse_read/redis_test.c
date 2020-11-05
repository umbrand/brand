#include <stdlib.h>
#include <stdio.h>
#include <unistd.h> /* close() */
#include <pthread.h>
#include <fcntl.h> // File control definitions
#include <linux/input.h>
#include <signal.h>
#include "redisTools.h"
#include "hiredis.h"

#define MOUSE_RELATIVE 1
#define MOUSE_ABSOLUTE 2

// List of parameters read from the yaml file, facilitates function definition of initialize_parameters
typedef struct yaml_parameters_t {
	int num_channels;
	int samples_per_redis_stream;
} yaml_parameters_t;


void initialize_redis();
void initialize_signals();
void handler_SIGINT(int exitStatus);
void initialize_parameters(yaml_parameters_t *p);

char PROCESS[] = "redis_test";
redisReply *reply;
redisContext *redis_context;

int flag_SIGINT = 0;

int32_t mouseData[6];  // (change in) X, Y, and wheel position (0-2) and 
// value of left, middle, and right button press (3-5)
int mouse_fd = -1;  // file descriptor for the mouse input
// mutex for mouseData
pthread_mutex_t mouseDataMutex = PTHREAD_MUTEX_INITIALIZER;

int main() {
	initialize_redis();
	initialize_signals();

	yaml_parameters_t yaml_parameters = {0};
	initialize_parameters(&yaml_parameters);

	mouse_fd = fopen("/dev/input/by-id/usb-Razer_Razer_Viper-event-mouse", "r");
	// Mouse Initialization
	if (mouse_fd < 0) {
		printf("Error opening mouse. Status code %d.\n", mouse_fd);
		return 1;
	}

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
		if(ev.type == EV_REL)  // mouse movements
			{
				switch(ev.code) {
				case REL_X :  // change in X position
					mouseData[0] += ev.value;
					break;
				case REL_Y :  // change in Y position
					mouseData[1] += ev.value;
					break;
				case REL_WHEEL :  // change in wheel position
					mouseData[2] += ev.value;
					break;
				}
			}
		else if(ev.type == EV_KEY)  // button presses
			{
				switch(ev.code) {
				case BTN_LEFT :
					mouseData[3] = ev.value;
					break;
				case BTN_MIDDLE :
					mouseData[4] = ev.value;
					break;
				case BTN_RIGHT :
					mouseData[5] = ev.value;
					break;
				}
			}
		pthread_mutex_unlock(&mouseDataMutex);
	}
	freeReplyObject(redisCommand(redis_context,
		"XADD mouseData * x %d y %d wheel %d",
		mouseData[0], mouseData[1], mouseData[2]));
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

//------------------------------------
// Handler functions
//------------------------------------

void handler_SIGINT(int exitStatus) {
	flag_SIGINT++;
}


void initialize_parameters(yaml_parameters_t *p) {

	char num_channels_string[16] = {0};
	char samples_per_redis_stream_string[16] = {0};

	load_YAML_variable_string(PROCESS, "num_channels", num_channels_string,   sizeof(num_channels_string));
	load_YAML_variable_string(PROCESS, "samples_per_redis_stream", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));

	p->num_channels             = atoi(num_channels_string);
	p->samples_per_redis_stream = atoi(samples_per_redis_stream_string);

}