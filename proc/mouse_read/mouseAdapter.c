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

// List of parameters read from the yaml file, facilitates function definition
// of initialize_parameters
typedef struct yaml_parameters_t {
} yaml_parameters_t;


void initialize_redis();
void initialize_signals();
void handler_SIGINT(int exitStatus);
void handler_SIGUSR1(int exitStatus);
void initialize_parameters(yaml_parameters_t *p);
void shutdown_process();

char PROCESS[] = "mouseAdapter";
redisReply *reply;
redisContext *redis_context;

int flag_SIGINT = 0;
int flag_SIGUSR1 = 0;

int32_t mouseData[6];  // (change in) X, Y, and wheel position (0-2) and 
// value of left, middle, and right button press (3-5)
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
		// freeReplyObject(redisCommand(redis_context,
		// 	"XADD mouseData * dx %d dy %d dw %d",
		// 	mouseData[0], mouseData[1], mouseData[2]));
	}
	return 0;
}




int main() {
	int rc;

	initialize_redis();
	initialize_signals();

	yaml_parameters_t yaml_parameters = {};
	initialize_parameters(&yaml_parameters);

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
	if(rc)
	{
		printf("Mouse thread failed to initialize!!\n");
	}


	/* server infinite loop */
	while(1) {
		pause();

		if (flag_SIGINT) 
			shutdown_process();

		if (flag_SIGUSR1) {
			freeReplyObject(redisCommand(redis_context,
				"XADD mouseData * dx %d dy %d dw %d",
				mouseData[0], mouseData[1], mouseData[2]));
			pthread_mutex_lock(&mouseDataMutex);
			mouseData[0] = 0;
			mouseData[1] = 0;
			mouseData[2] = 0;
			pthread_mutex_unlock(&mouseDataMutex);

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