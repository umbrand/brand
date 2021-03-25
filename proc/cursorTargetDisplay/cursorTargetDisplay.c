/* cursorTargetDisplay.c
*   takes in location information from behaviorFSM system and displays it.
*   may need to run on a system separately from the primary data intake 
*/

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
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
    int screen_size[2];
    char cursor_file[255];
} yaml_parameters_t;


void initialize_redis();
void initialize_signals();
void handler_SIGINT(int exitStatus);
void initialize_parameters(yaml_parameters_t *p);
void shutdown_process();

char PROCESS[] = "cursorTargetDisplay";
redisReply *cursor_reply;
redisReply *target_reply;
redisContext *redis_context;

int flag_SIGINT = 0;

pthread_t subscriberThreadCursor;

int cursorPosition[3];   // [X Y state]
int targetPosition[5];  // [X Y W H state]
int *stringConv;


/*
void * subscriberThread(void * thread_params) {
    while(1) {
        //if (flag_SIGINT) 
         //   shutdown_process();
        cursor_reply = redisCommand(redis_context,"XREAD BLOCK 1 STREAMS cursorData $"); 
        if (cursor_reply->elements == 1) {
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
            cursorPosition[0] = *stringConv; 
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //X
            cursorPosition[1] = *stringConv;
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //X
            cursorPosition[2] = *stringConv;
        }

        target_reply = redisCommand(redis_context,"XREAD BLOCK 1 STREAMS targetData $");
        if (target_reply->elements == 1){
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
            targetPosition[0] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //X
            targetPosition[1] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //X
            targetPosition[2] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[7]->str); //X
            targetPosition[3] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[9]->str); //X
            targetPosition[4] = *stringConv;

        }
        
        //printf("cursor position: (x = %d, y = %d, state = %u)\n", cursorPosition[0],
        //    cursorPosition[1], cursorPosition[2]);
        //printf("target position: (x = %d, y = %d, w = %d, h = %d, state = %u)\n", targetPosition[0],
            //targetPosition[1], targetPosition[2], targetPosition[3], targetPosition[4]);
            //if (cursorPosition[0] >= 0){
                //posNeg = cursorPosition[0];
            //}else{
                //printf("%i\n",posNeg);
            //}
    }
}

*/


int main() {
    int rc; //error value for the thread


    initialize_redis();
    initialize_signals();

    yaml_parameters_t yaml_parameters = {0};
    initialize_parameters(&yaml_parameters);


    int screenSize[2];
    char cursorFile[255] = "./face.tga"; // initialize the name, give it 255 for the PATH_MAX of linux
    screenSize[0] = 1920; // horizontal screen size
    screenSize[1] = 1080; // vertical screen size
    //screenSize = yaml_parameters->*screen_size;
    //cursorFile = yaml_parameters->*cursor_file;


    /* Spawn Subcriber thread */
/*    printf("[%s] Starting Subcriber Threads \n", PROCESS);
    rc = pthread_create(&subscriberThreadCursor, NULL, subscriberThread, NULL);
    if (rc)
    {
        printf("[%s] Subcriber thread failed to initialize!!\n", PROCESS);
    } else {
        printf("[%s] Started thread\n", PROCESS);
    }*/

    // source: https://www.geeksforgeeks.org/sdl-library-in-c-c-with-examples/
    // returns zero on success else non-zero 
    if (SDL_Init(SDL_INIT_EVERYTHING) != 0) { 
        printf("[%s] error initializing SDL: %s\n", PROCESS, SDL_GetError()); 
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
    SDL_Surface* cursor_surface; 
    cursor_surface = IMG_Load(cursorFile); // please provide a path for your image 
    if (!cursor_surface) {
        printf("IMG_Load: %s\n", IMG_GetError());
    }
    //cursor_surface = IMG_Load(cursorFile); // please provide a path for your image 

    // loads image to our graphics hardware memory. 
    SDL_Texture* cursor_tex = SDL_CreateTextureFromSurface(rend, cursor_surface); 

    // clears main-memory 
    SDL_FreeSurface(cursor_surface); 

    SDL_ShowCursor(SDL_DISABLE);

    // let us control our image position 
    // so that we can move it with our keyboard. 
    SDL_Rect cursor_dest;
    SDL_Rect target_rect; 
    target_rect.x = screenSize[0]/2;
    target_rect.y = screenSize[1]/2; 

    // connects our texture with dest to control position 
    SDL_QueryTexture(cursor_tex, NULL, NULL, &cursor_dest.w, &cursor_dest.h); 

    // adjust height and width of our image box. is this hard coded right now?
    cursor_dest.w = 50; 
    cursor_dest.h = 50; 

    // sets initial x-position of object 
    cursor_dest.x = (screenSize[0] - cursor_dest.w) / 2; 

    // sets initial y-position of object 
    cursor_dest.y = (screenSize[1] - cursor_dest.h) / 2; 

    // controls annimation loop 
    int close = 0; 

    // annimation loop 
    while (1) { 
        if (flag_SIGINT | close) 
            shutdown_process();
        

        // get the current data from the redis stream
 
        cursor_reply = redisCommand(redis_context,"XREAD BLOCK 1 STREAMS cursorData $"); 
        if (cursor_reply->elements == 1) {
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
            cursorPosition[0] = *stringConv; 
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //X
            cursorPosition[1] = *stringConv;
            stringConv = (int*)(cursor_reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //X
            cursorPosition[2] = *stringConv;
        }

        target_reply = redisCommand(redis_context,"XREAD BLOCK 1 STREAMS targetData $");
        if (target_reply->elements == 1){
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[1]->str); //X
            targetPosition[0] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[3]->str); //X
            targetPosition[1] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[5]->str); //X
            targetPosition[2] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[7]->str); //X
            targetPosition[3] = *stringConv;
            stringConv = (int*)(target_reply->element[0]->element[1]->element[0]->element[1]->element[9]->str); //X
            targetPosition[4] = *stringConv;

        }

        // update the cursor x and y -- based around the center of the screen
        cursor_dest.x = cursorPosition[0] + (screenSize[0] - cursor_dest.w) / 2;
        cursor_dest.y = cursorPosition[1] + (screenSize[1] - cursor_dest.h) / 2;


        // update the target x,y,w and h -- based around the center of the screen
        target_rect.w = targetPosition[2];
        target_rect.h = targetPosition[3];
        target_rect.x = targetPosition[0] + (screenSize[0] - target_rect.w) / 2; 
        target_rect.y = targetPosition[1] + (screenSize[1] - target_rect.h) / 2; 

        // right boundary 
        if (cursor_dest.x + cursor_dest.w > screenSize[0]) 
            cursor_dest.x = screenSize[0] - cursor_dest.w; 

        // left boundary 
        if (cursor_dest.x < 0) 
            cursor_dest.x = 0; 

        // bottom boundary 
        if (cursor_dest.y + cursor_dest.h > screenSize[1]) 
            cursor_dest.y = screenSize[1]- cursor_dest.h; 

        // upper boundary 
        if (cursor_dest.y < 0) 
            cursor_dest.y = 0; 

        // clears the screen
        SDL_RenderClear(rend); 
       
         
        printf("%i\n",targetPosition[4]);
        // display the target as the desired color, based on the state
        switch (targetPosition[4]){

            case 1: // target on -- red
                SDL_SetRenderDrawColor(rend,255,0,0,255);
                SDL_RenderFillRect(rend, &target_rect); // draw the target rectangle*/
                break;

            case 2: // cursor over target -- green
                SDL_SetRenderDrawColor(rend,0,255,0,255);
                SDL_RenderFillRect(rend, &target_rect); // draw the target rectangle*/
                break;
        }

        SDL_SetRenderDrawColor(rend, 0, 0, 0, 255); // render target rectangle on screen
        SDL_RenderCopy(rend, cursor_tex, NULL, &cursor_dest); // render the cursor

        // triggers the double buffers 
        // for multiple rendering 
        SDL_RenderPresent(rend); 

        // calculates to 60 fps 
        SDL_Delay(1000 / 60); 
    } 


    
    // destroy texture 
    SDL_DestroyTexture(cursor_tex); 

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
    char screen_size_x_string[16] = {0};
    char screen_size_y_string[16] = {0};
    char cursor_file_string[255] = {0}; // filenames are sometimes long. Following PATH_MAX

    load_YAML_variable_string(PROCESS, "num_channels", num_channels_string,   sizeof(num_channels_string));
    load_YAML_variable_string(PROCESS, "samples_per_redis_stream", samples_per_redis_stream_string,   sizeof(samples_per_redis_stream_string));
    load_YAML_variable_string(PROCESS, "screen_size_x", screen_size_x_string,   sizeof(screen_size_x_string));
    load_YAML_variable_string(PROCESS, "screen_size_y", screen_size_y_string,   sizeof(screen_size_y_string));
    load_YAML_variable_string(PROCESS, "cursor_file", cursor_file_string, sizeof(cursor_file_string));

    p->num_channels             = atoi(num_channels_string);
    p->samples_per_redis_stream = atoi(samples_per_redis_stream_string);
    p->screen_size[0] = atoi(screen_size_x_string);
    p->screen_size[1] = atoi(screen_size_y_string);
    (void)strncpy(p->cursor_file, cursor_file_string, 255);

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

