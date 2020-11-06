#include <stdlib.h>
#include <stdio.h>
#include <unistd.h> /* close() */
#include <pthread.h>
#include <fcntl.h> // File control definitions
#include <linux/input.h>
#include <signal.h>
#include "redisTools.h"
#include "hiredis.h"

// List of parameters read from the yaml file, facilitates function definition of initialize_parameters
typedef struct yaml_parameters_t {
	int num_channels;
	int samples_per_redis_stream;
} yaml_parameters_t;


void initialize_redis();
void initialize_signals();
void handler_SIGINT(int exitStatus);
void initialize_parameters(yaml_parameters_t *p);
void shutdown_process();

char PROCESS[] = "cursor_control";
redisReply *reply;
redisContext *redis_context;

int flag_SIGINT = 0;

pthread_t subscriberThread;

int32_t mousePosition[3];

void * mouseSubscriberThread(void * thread_params) {
	while(1) {
	// if (flag_SIGINT) 
	// 	shutdown_process();
		reply = redisCommand(redis_context,
			"XREAD BLOCK 1000000 STREAMS mouseData $");
		// char *string = reply->element[0]->element[1]->element[0]->element[1]->element[1]->str;
		// char *string = reply->element[0]->element[1]->element[0]->element[1]->str;
		mousePosition[0] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[1]->str);
		mousePosition[1] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[3]->str);
		mousePosition[2] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[5]->str);
		
		printf("mouse position: (x = %d, y = %d, w = %d)\n", mousePosition[0],
			mousePosition[1], mousePosition[2]);
	}
}

int main() {
	int rc;

	initialize_redis();
	initialize_signals();

	yaml_parameters_t yaml_parameters = {0};
	initialize_parameters(&yaml_parameters);

	/* Spawn Subcriber thread */
	printf("Starting Subcriber Thread \n");
	rc = pthread_create(&subscriberThread, NULL, mouseSubscriberThread, NULL);
	if(rc)
	{
		printf("Subcriber thread failed to initialize!!\n");
	} else {
		printf("Started thread\n");
	}


	while(1) {
		if (flag_SIGINT) 
			shutdown_process();
		usleep(1000);
	}
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


void initialize_parameters(yaml_parameters_t *p) {

	char num_channels_string[16] = {0};
	char samples_per_redis_stream_string[16] = {0};

	load_YAML_variable_string(PROCESS, "num_channels", num_channels_string,   sizeof(num_channels_string));
	load_YAML_variable_string(PROCESS, "samples_per_redis_stream", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));

	p->num_channels             = atoi(num_channels_string);
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