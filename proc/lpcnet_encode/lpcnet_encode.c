/* lpcnet_encode.c
 *
 * The goal of this function is to take a sound file (pcm) and encode it into the lpcnet vocoder
 * output. It's designed to run in real-time. There's certainly a role for pre-computing the 
 * vocoder values, but this is an excercise in the whole closed-loop system.
 *
 * David Brandman May 2020
*/

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <math.h>
#include <stdio.h>
#include <signal.h>
#include "arch.h"
#include "lpcnet.h"
#include "freq.h"
#include "redisTools.h"
#include "hiredis.h"

void initialize_redis();
void initialize_signals();
int initialize_buffer(int16_t  **buffer);

void handle_exit(int exitStatus);
void ignore_exit(int exitStatus);
char PROCESS[] = "lpcnet_encode";

redisContext *redis_context;


// LPCNET_COMPRESSED_SIZE -> lpcnet.h. = 8
// Number of bytes in a compressed packet
// LPCNET_PACKET_SAMPLES -> lpcnet.h = 4*160
// Number of audio samples in a packet


int main(int argc, char **argv) {


    initialize_redis();

    initialize_signals();

    // The buffer contains a pointer to the s16le pcm formatted sound file
    int16_t *buffer;
    int num_packets = initialize_buffer(&buffer);

    // State initialization for LPCnet
    LPCNetEncState *net = lpcnet_encoder_create();

    printf("[%s] Initiating For loop. Running for %d seconds...\n",PROCESS, (40*num_packets/1000));

    /* Sending kill causes tmux to close */
    pid_t ppid = getppid();
    kill(ppid, SIGUSR2);

    for (int i = 0; i < num_packets; i++) {

        // Block until we have a timer input
        redis_succeed(redis_context, "xread block 0 streams timer $");

        unsigned char output_buffer[LPCNET_COMPRESSED_SIZE] = {0};
        int buffer_index = i * LPCNET_PACKET_SAMPLES;
        lpcnet_encode(net, &buffer[buffer_index], output_buffer);

        // Convert the encoded value to a string

        int index = 0;
        char buffer_string[64] = {0};

        index += sprintf(buffer_string, "XADD lpcnet_encode * sound_compressed ");
        for (int j=0; j < LPCNET_COMPRESSED_SIZE; j++)
           index += sprintf(&buffer_string[index], "%x", output_buffer[j]);

        // Push the string to Redis
        
        printf("%d %s\n",i, buffer_string);
        redis_succeed(redis_context, buffer_string);
    }
    printf("[%s] Loop is finished. Freeing memory...\n",PROCESS);
    lpcnet_encoder_destroy(net);
    redisFree(redis_context);
    free(buffer);
    printf("[%s] Shutting down.\n",PROCESS);
    return 0;

}

//------------------------------------
//------------------------------------
// Initialization functions
//------------------------------------
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

int initialize_buffer(int16_t  **buffer) {

    char filename[16] = {0};
    load_YAML_variable_string(PROCESS, "filename", filename, sizeof(filename));

    printf("[%s] Finding the file %s to load into memory...\n", PROCESS, filename);
    FILE *dataFILE;
    if ((dataFILE = fopen(filename, "rb")) == NULL) {
        perror("Fopen: ");
        exit(1);
    }
    
    // First, how big is this file? Go to end and then rewind
    fseek(dataFILE, 0L, SEEK_END);
    int dataSize = ftell(dataFILE);
    rewind(dataFILE);

    printf("[%s] File size: %d bytes\n",PROCESS, dataSize);

    int num_packets = dataSize / LPCNET_PACKET_SAMPLES / sizeof(uint16_t);

    // Now load the file in memory. This will get automatically released when the program
    // closes since it's not being malloced in a subprocess or daemon. Whew!
	*buffer =  malloc(dataSize * sizeof(uint16_t));
    int readLength;
    if ( (readLength = fread(*buffer, 1, dataSize, dataFILE)) < 0) {
        printf("[%s] Could not read file. Aborting.\n", PROCESS);
        exit(1);
    }

    // Now that the data is in memory we're done
    fclose(dataFILE);
    return num_packets;
}
//
//------------------------------------
//------------------------------------
// Handler functions
//------------------------------------
//------------------------------------

void handle_exit(int exitStatus) {
    printf("[%s] Exiting!\n", PROCESS);
    exit(0);
}

void ignore_exit(int exitStatus) {
    printf("[%s] Terminates through SIGUSR1!\n", PROCESS);
}

    /* int mode; */
    /* FILE *fin, *fout; */
    /* if (argc != 4) */
    /* { */
    /*     fprintf(stderr, "usage: lpcnet_demo -encode <input.pcm> <compressed.lpcnet>\n"); */
    /*     fprintf(stderr, "       lpcnet_demo -decode <compressed.lpcnet> <output.pcm>\n"); */
    /*     fprintf(stderr, "       lpcnet_demo -features <input.pcm> <features.f32>\n"); */
    /*     fprintf(stderr, "       lpcnet_demo -synthesis <features.f32> <output.pcm>\n"); */
    /*     return 0; */
    /* } */
    /* if (strcmp(argv[1], "-encode") == 0) mode=MODE_ENCODE; */
    /* else if (strcmp(argv[1], "-decode") == 0) mode=MODE_DECODE; */
    /* else if (strcmp(argv[1], "-features") == 0) mode=MODE_FEATURES; */
    /* else if (strcmp(argv[1], "-synthesis") == 0) mode=MODE_SYNTHESIS; */
    /* else { */
    /*     exit(1); */
    /* } */
    /* fin = fopen(argv[2], "rb"); */
    /* if (fin == NULL) { */
	/* fprintf(stderr, "Can't open %s\n", argv[2]); */
	/* exit(1); */
    /* } */

    /* fout = fopen(argv[3], "wb"); */
    /* if (fout == NULL) { */
	/* fprintf(stderr, "Can't open %s\n", argv[3]); */
	/* exit(1); */
    /* } */

    /* if (mode == MODE_ENCODE) { */
    /*     LPCNetEncState *net; */
    /*     net = lpcnet_encoder_create(); */
    /*     while (1) { */
    /*         unsigned char buf[LPCNET_COMPRESSED_SIZE]; */
    /*         short pcm[LPCNET_PACKET_SAMPLES]; */
    /*         fread(pcm, sizeof(pcm[0]), LPCNET_PACKET_SAMPLES, fin); */
    /*         if (feof(fin)) break; */
    /*         lpcnet_encode(net, pcm, buf); */
    /*         fwrite(buf, 1, LPCNET_COMPRESSED_SIZE, fout); */
    /*     } */
    /*     lpcnet_encoder_destroy(net); */
    /* } else if (mode == MODE_DECODE) { */
    /*     LPCNetDecState *net; */
    /*     net = lpcnet_decoder_create(); */
    /*     while (1) { */
    /*         unsigned char buf[LPCNET_COMPRESSED_SIZE]; */
    /*         short pcm[LPCNET_PACKET_SAMPLES]; */
    /*         fread(buf, sizeof(buf[0]), LPCNET_COMPRESSED_SIZE, fin); */
    /*         if (feof(fin)) break; */
    /*         lpcnet_decode(net, buf, pcm); */
    /*         fwrite(pcm, sizeof(pcm[0]), LPCNET_PACKET_SAMPLES, fout); */
    /*     } */
    /*     lpcnet_decoder_destroy(net); */
    /* } else if (mode == MODE_FEATURES) { */
    /*     LPCNetEncState *net; */
    /*     net = lpcnet_encoder_create(); */
    /*     while (1) { */
    /*         float features[4][NB_TOTAL_FEATURES]; */
    /*         short pcm[LPCNET_PACKET_SAMPLES]; */
    /*         fread(pcm, sizeof(pcm[0]), LPCNET_PACKET_SAMPLES, fin); */
    /*         if (feof(fin)) break; */
    /*         lpcnet_compute_features(net, pcm, features); */
    /*         fwrite(features, sizeof(float), 4*NB_TOTAL_FEATURES, fout); */
    /*     } */
    /*     lpcnet_encoder_destroy(net); */
    /* } else if (mode == MODE_SYNTHESIS) { */
    /*     LPCNetState *net; */
    /*     net = lpcnet_create(); */
    /*     while (1) { */
    /*         float in_features[NB_TOTAL_FEATURES]; */
    /*         float features[NB_FEATURES]; */
    /*         short pcm[LPCNET_FRAME_SIZE]; */
    /*         fread(in_features, sizeof(features[0]), NB_TOTAL_FEATURES, fin); */
    /*         if (feof(fin)) break; */
    /*         RNN_COPY(features, in_features, NB_FEATURES); */
    /*         RNN_CLEAR(&features[18], 18); */
    /*         lpcnet_synthesize(net, features, pcm, LPCNET_FRAME_SIZE); */
    /*         fwrite(pcm, sizeof(pcm[0]), LPCNET_FRAME_SIZE, fout); */
    /*     } */
    /*     lpcnet_destroy(net); */
    /* } else { */
    /*     fprintf(stderr, "unknown action\n"); */
    /* } */
    /* fclose(fin); */
    /* fclose(fout); */
    /* return 0; */
