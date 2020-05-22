
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <math.h>
#include <stdio.h>
#include <signal.h>
#include <stdlib.h>

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
char PROCESS[] = "lpcnet_decode";

redisContext *redis_context;
redisReply *reply;


// From the LPCNet code base: these are the default values:
// LPCNET_COMPRESSED_SIZE -> lpcnet.h. = 8
// Number of bytes in a compressed packet
// LPCNET_PACKET_SAMPLES -> lpcnet.h = 4*160
// Number of audio samples in a packet

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

int main(int argc, char **argv) {


    initialize_redis();

    initialize_signals();

    // State initialization for LPCnet
    LPCNetDecState *net = lpcnet_decoder_create();

    /* Sending kill causes tmux to close */
    /* pid_t ppid = getppid(); */
    /* kill(ppid, SIGUSR2); */


    printf("[%s] Entering loop...\n", PROCESS);

    while (1) {

        reply = redisCommand(redis_context, "xread count 1 block 0 streams lpcnet_encode $");
        if (reply == NULL || reply->type == REDIS_REPLY_ERROR || reply->type == REDIS_REPLY_NIL) {
            printf("[%s] Error running redis command",PROCESS);
            exit(1);
        }

        // The xread value is rather nested
        // 1. [0] The stream we're getting data from
        // 2. [1] The data content from the stream
        // 3. [0] The first element of the data content of the stream
        // 4. [1] The data associated with the ID
        // 5. [1] The data associated with the key
        char *string = reply->element[0]->element[1]->element[0]->element[1]->element[1]->str;

        /* unsigned char buf[LPCNET_COMPRESSED_SIZE] = {0}; */

        unsigned long encoded;
        sscanf(string, "%lu", &encoded);

        /* printf("%lu\n",encoded); */

        /* unsigned char buf[LPCNET_COMPRESSED_SIZE]; */
        short pcm[LPCNET_PACKET_SAMPLES];

        /* memcpy(buf, &encoded, LPCNET_COMPRESSED_SIZE); */

        /* lpcnet_decode(net, buf, pcm); */
        lpcnet_decode(net, (unsigned char*) &encoded, pcm);

        fwrite(pcm, sizeof(pcm[0]), LPCNET_PACKET_SAMPLES, stdout);
        


    /*     while (1) { */
    /*         unsigned char buf[LPCNET_COMPRESSED_SIZE]; */
    /*         short pcm[LPCNET_PACKET_SAMPLES]; */
    /*         fread(buf, sizeof(buf[0]), LPCNET_COMPRESSED_SIZE, fin); */
    /*         if (feof(fin)) break; */
    /*         lpcnet_decode(net, buf, pcm); */
    /*         fwrite(pcm, sizeof(pcm[0]), LPCNET_PACKET_SAMPLES, fout); */
    /*     } */
        freeReplyObject(reply);
    }


    lpcnet_decoder_destroy(net);
    redisFree(redis_context);
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
