/* nidaq_acquisition.c
 * Transfers data between a USB NI-DAQ system and a Redis Stream.
 * 
 * This was initially designed for behavioral data and control for
 * use with the behavior_FSM code.
 * 
 * For documentation on the NIDAQmx ansi c functions (NIDAQmx.h) refer
 * to https://zone.ni.com/reference/en-XX/help/370471AM-01
 * 
 * 
 * Kevin Bodkin
 */


#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include "redisTools.h"
#include "hiredis.h"
#include <NIDAQmx.h>
#include <time.h>



// List of parameters read from the yaml file, facilitates function definition of initialize_parameters
typedef struct yaml_parameters_t {
    int sample_rate;
    int samples_per_redis_stream;
} yaml_parameters_t;

void initialize_redis();
void initialize_parameters(yaml_parameters_t *);
void initialize_realtime();
void initialize_signals();
void shutdown_process();
void handler_SIGINT(int exitStatus);
void print_argv(int, char **, size_t *);



char PROCESS[] = "nidaq_acquisition";

redisContext *redis_context;

int flag_SIGINT = 0;


#define DAQmxErrChk(functionCall) if( DAQmxFailed(error=(functionCall)) ) goto Error; else

int main(void) {

    initialize_redis();

    initialize_signals();

    int32_t         error=0;
    TaskHandle      positionTaskHandle=0; // xy position
    TaskHandle      rewardTaskHandle=0; // output to the reward circuit
    char            errBuff[2048]={'\0'};
    
    // bring in parameters from the yaml setup file
    yaml_parameters_t yaml_parameters = {0};
    initialize_parameters(&yaml_parameters);
    int32 sampleRate      = yaml_parameters.sample_rate; // what's the sampling rate from the nidaq?
    int32 sampPerRedis    = yaml_parameters.samples_per_redis_stream; // how many samples per Redis stream write?
    int32 *sampPerChanRead;   // output from the nidaq, what is the actual number of samples received?


    // array to keep track of system time
    struct timeval current_time;

    // initialize NIDAQmx tasks
    printf("[%s] Initializing NIDAQ tasks\n", PROCESS);
    DAQmxErrChk (DAQmxCreateTask("xyLocation",&positionTaskHandle)); 
    DAQmxErrChk (DAQmxCreateTask("rewardOutput",&rewardTaskHandle));

    // setup  the task to read the xy values from the NIDAQ along with the sampling clock
    DAQmxErrChk (DAQmxCreateAIVoltageChan (positionTaskHandle, "Dev1/ai0", "X_position", DAQmx_Val_Cfg_Default, -5.0, 5.0, DAQmx_Val_Volts, NULL));
    DAQmxErrChk (DAQmxCreateAIVoltageChan (positionTaskHandle, "Dev2/ai1", "Y_position", DAQmx_Val_Cfg_Default, -5.0, 5.0, DAQmx_Val_Volts, NULL));
    DAQmxCfgSampClkTiming(positionTaskHandle, "", sampleRate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, sampPerRedis);


    // number of arguments etc for calls to redis
    int argc        = 7; // number of arguments: "xadd nidaq_acquisition * timestamps [timestamps] samples [X Y]"
    size_t *argvlen = malloc(argc * sizeof(size_t)); // an array of the length of each argument put into Redis. This initializes the array

    int ind_xadd        = 0;                    // xadd nidaq_acquisition *
    int ind_timestamps  = ind_xadd+3;           // timestamps [timestamps]
    int ind_samples     = ind_timestamps+2;     // samples [X Y] -- putting them in an array together rather than having a separate entry for each
    
    // allocating memory for the actual data being passed

    int len = 16;
    char *argv[argc];

    // xadd nidaq_acquisition *
    for (int i = 0; i < ind_timestamps; i++) {
        argv[i] = malloc(len);
    } 


    // timestamps and sample array
    argv[ind_timestamps] = malloc(len);
    argv[ind_timestamps+1] = malloc(sizeof(struct timeval));
    argv[ind_samples]   = malloc(len);
    double samples[2][sampPerRedis];
    argv[ind_samples+1] = malloc(2 * sampPerRedis * sizeof(double)); // number of samples * two inputs * float64 size

    

    // populating the argv strings
    // start with the "xadd nidaq_acquisition"
    argvlen[0] = sprintf(argv[0], "%s", "xadd"); // write the string "xadd" to the first position in argv, and put the length into argv
    argvlen[1] = sprintf(argv[1], "%s", "nidaq_acquisition"); //same for cerebus adapter
    argvlen[2] = sprintf(argv[2], "%s", "*");

    //and the samples array label

    argvlen[ind_timestamps] = sprintf(argv[ind_timestamps], "%s", "timestamps");
    argvlen[ind_samples] = sprintf(argv[ind_samples], "%s", "samples"); // samples label

    printf("[%s] Entering loop\n", PROCESS);

    // start the nidaq tasks
    DAQmxErrChk (DAQmxStartTask(positionTaskHandle));
    DAQmxErrChk (DAQmxStartTask(rewardTaskHandle));

    // main loop
    while (1) {

        // shutdown if we receive a sigint -- C-c
        if (flag_SIGINT)
            shutdown_process();


        // read from the nidaq board for the AI channels
        DAQmxErrChk (DAQmxReadAnalogF64(positionTaskHandle, sampPerRedis, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, samples, sampPerRedis * 2, *sampPerChanRead, NULL));
        &argv[ind_samples+1] = samples;
        
        // current read the current time into the array
        clock_gettime(CLOCK_MONOTONIC,&current_time);
        memcpy(&argv[ind_timestamps + 1][sizeof(struct timeval)], &current_time, sizeof(struct timeval));

        // send everything to Redis -- let's hope I set this up right!
        freeReplyObject(redisCommandArgv(redis_context, argc, (const char**) argv, argvlen));


    }


    // you're outside the matrix, neo!
    for (int i=0; i < argc; i++) {
        free(argv[i]);
    }
    free(argvlen);
    return 0;



    Error: 
                if( DAQmxFailed(error) )
            DAQmxGetExtendedErrorInfo(errBuff,2048);
        /*********************************************/
        // DAQmx Stop Code
        /*********************************************/
        if( thermocoupleMasterTask!=0 ) {
            DAQmxStopTask(thermocoupleMasterTask);
            DAQmxClearTask(thermocoupleMasterTask);
        }
        if( thermocoupleSlaveTask!=0 ) {
            DAQmxStopTask(thermocoupleSlaveTask);
            DAQmxClearTask(thermocoupleSlaveTask);
        }
        if( digitalSlaveTask!=0 ) {
            DAQmxStopTask(digitalSlaveTask);
            DAQmxClearTask(digitalSlaveTask);
        }
        if( DAQmxFailed(error) )
            printf("DAQmx Error: %s\n",errBuff);
        return 0;

}





// startup the redis connection based on the yaml file
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



// signal handlers -- to deal with the SIGINT signals
void initialize_signals() {

    printf("[%s] Attempting to initialize signal handlers.\n", PROCESS);

    signal(SIGINT, &handler_SIGINT);

    printf("[%s] Signal handlers installed.\n", PROCESS);
}



// get all of the parameters from the yaml file.
void initialize_parameters(yaml_parameters_t *p) {

    // create the strings to pull everything in from the yaml file
    char samples_per_redis_stream_string[16] = {0};
    char sample_rate_string[16] = {0};

    // pull it in from the YAML
    load_YAML_variable_string(PROCESS, "samples_per_redis_stream", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));
    load_YAML_variable_string(PROCESS, "sample_rate", sample_rate_string, sizeof(sample_rate_string));

    // add it into yaml parameters struct
    p->sample_rate             = atoi(sample_rate_string);
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



