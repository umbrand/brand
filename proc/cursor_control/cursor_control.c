/* cursor_control.c
*   takes in location information from behaviorFSM system and displays it.
*   may need to run on a system separately from the primary data intake 
*/

#include <stdlib.h>
#include <stdio.h>
#include <unistd.h> /* close() */
#include <pthread.h>
#include <fcntl.h> // File control definitions
#include <linux/input.h>
#include <signal.h>
#include "redisTools.h"
#include "hiredis.h"
#include <SDL2/SDL.h> 
#include <SDL2/SDL_image.h> 
#include <SDL2/SDL_timer.h> 

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

char PROCESS[] = "cursorControl";
redisReply *reply;
redisContext *redis_context;

int flag_SIGINT = 0;

pthread_t subscriberThread;

int32_t cursorPosition[3];   // [X Y state]
int32_t targetPosition[5];  // [X Y W H state]

void * cursorSubscriberThread(void * thread_params) {
    while(1) {
           if (flag_SIGINT) 
         shutdown_process();
        reply = redisCommand(redis_context,
            "XREAD BLOCK 1000000 STREAMS cursorData $");
    
        cursorPosition[0] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
        cursorPosition[1] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //Y
        // states: off = 0, on = 1
        cursorPosition[2] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //state
        
        printf("cursor position: (x = %d, y = %d, state = %d)\n", cursorPosition[0],
            cursorPosition[1], cursorPosition[2]);
    }
}


void * targetSubscriberThread(void * thread_params) {
    while(1) {
    // if (flag_SIGINT) 
    //     shutdown_process();
        reply = redisCommand(redis_context,
            "XREAD BLOCK 1000000 STREAMS targetData $");

        targetPosition[0] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
        targetPosition[1] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //Y
        targetPosition[2] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //W
        targetPosition[3] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[7]->str); //H
        // states: off = 0, on = 1
        targetPosition[4] += atoi(reply->element[0]->element[1]->element[0]->element[1]->element[9]->str); //state
        
        printf("target position: (x = %d, y = %d, w = %d, h = %d, state = %d)\n", targetPosition[0],
            targetPosition[1], targetPosition[2], targetPosition[3], targetPosition[4]);
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
    rc = pthread_create(&subscriberThread, NULL, cursorSubscriberThread, NULL);
    if(rc)
    {
        printf("Subcriber thread failed to initialize!!\n");
    } else {
        printf("Started thread\n");
    }

    // source: https://www.geeksforgeeks.org/sdl-library-in-c-c-with-examples/
    // returns zero on success else non-zero 
    if (SDL_Init(SDL_INIT_EVERYTHING) != 0) { 
        printf("error initializing SDL: %s\n", SDL_GetError()); 
    } 
    SDL_Window* win = SDL_CreateWindow("GAME", // creates a window 
                                       SDL_WINDOWPOS_CENTERED, 
                                       SDL_WINDOWPOS_CENTERED, 
                                       1920, 1080, SDL_WINDOW_OPENGL); 

    // SDL_SetWindowFullscreen(win, SDL_WINDOW_FULLSCREEN);

    // move cursor to center of the screen
    SDL_WarpMouseInWindow(win, 500, 500);


    // triggers the program that controls 
    // your graphics hardware and sets flags 
    Uint32 render_flags = SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC;

    // creates a renderer to render our images 
    SDL_Renderer* rend = SDL_CreateRenderer(win, -1, render_flags); 

    // creates a surface to load an image into the main memory 
    SDL_Surface* surface; 

    // please provide a path for your image 
    surface = IMG_Load("./yellow_circle.png"); 

    // loads image to our graphics hardware memory. 
    SDL_Texture* tex = SDL_CreateTextureFromSurface(rend, surface); 

    // clears main-memory 
    SDL_FreeSurface(surface); 

    SDL_ShowCursor(SDL_DISABLE);

    // let us control our image position 
    // so that we can move it with our keyboard. 
    SDL_Rect dest; 

    // connects our texture with dest to control position 
    SDL_QueryTexture(tex, NULL, NULL, &dest.w, &dest.h); 

    // adjust height and width of our image box. 
    dest.w /= 6; 
    dest.h /= 6; 

    // sets initial x-position of object 
    dest.x = (1920 - dest.w) / 2; 

    // sets initial y-position of object 
    dest.y = (1080 - dest.h) / 2; 

    // controls annimation loop 
    int close = 0; 

    // annimation loop 
    while (1) { 
        if (flag_SIGINT | close) 
            shutdown_process();

        dest.x = cursorPosition[0] + (1920 - dest.w) / 2;
        dest.y = cursorPosition[1] + (1080 - dest.h) / 2;


        // right boundary 
        if (dest.x + dest.w > 1920) 
            dest.x = 1920 - dest.w; 

        // left boundary 
        if (dest.x < 0) 
            dest.x = 0; 

        // bottom boundary 
        if (dest.y + dest.h > 1080) 
            dest.y = 1080 - dest.h; 

        // upper boundary 
        if (dest.y < 0) 
            dest.y = 0; 

        // clears the screen
        SDL_RenderClear(rend); 
        SDL_RenderCopy(rend, tex, NULL, &dest); 

        // triggers the double buffers 
        // for multiple rendering 
        SDL_RenderPresent(rend); 

        // calculates to 60 fps 
        SDL_Delay(1000 / 60); 
    } 

    // destroy texture 
    SDL_DestroyTexture(tex); 

    // destroy renderer 
    SDL_DestroyRenderer(rend); 

    // destroy window 
    SDL_DestroyWindow(win); 
    return 0; 
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
