#include <stdlib.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <stdio.h>
#include <unistd.h> /* close() */
#include <string.h> /* memset() */
#include <pthread.h>
#include <sys/time.h>
#include <fcntl.h> // File control definitions
#include <linux/input.h>

#define MOUSE_RELATIVE 1
#define MOUSE_ABSOLUTE 2

///// Globals
int32_t mouseData[6];  // (change in) X, Y, and wheel position (0-2) and 
// value of left, middle, and right button press (3-5)
int mouseMode = 0;  // whether to use relative mode (0) or absolute mode (1)
pthread_t mouseThread;  // thread for reading each mouse event

int mouse_fd = -1;  // file descriptor for the mouse input

// mutex for mouseData
pthread_mutex_t mouseDataMutex = PTHREAD_MUTEX_INITIALIZER;

struct timeval mouseTime;  // ?

void * mouseReaderThread(void *)
{
	pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, NULL);

	struct input_event ev;  // mouse input event
	int rd = 0;  // read status of mouse

	pthread_mutex_lock(&mouseDataMutex);
	gettimeofday(&mouseTime, 0);
	pthread_mutex_unlock(&mouseDataMutex);

	while(1)
	{
		rd = read(mouse_fd, &ev, sizeof(struct input_event));  // wait for input
		if (rd < (int) sizeof(struct input_event)) {
			perror("Mouse: error reading \n");
			exit(1);
		}
		// Which mouse mode?
		if(mouseMode == MOUSE_RELATIVE)  // We mostly use relative mode
		{
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
		}  // if relative mode
		else if(mouseMode == MOUSE_ABSOLUTE)
		{
			pthread_mutex_lock(&mouseDataMutex);
	
			if(ev.type == EV_ABS)
				{
					switch(ev.code) {
					case ABS_X :
						mouseData[0] = ev.value;
						break;
					case ABS_Y :
						mouseData[1] = ev.value;
						break;
					case ABS_MT_TOUCH_MAJOR :
						mouseData[2] = ev.value;
						break;
					case ABS_TOOL_WIDTH :
						mouseData[3] = ev.value;
						break;
					case ABS_MT_POSITION_X :
						mouseData[4] = ev.value;
						break;
					case ABS_MT_POSITION_Y :
						mouseData[5] = ev.value;
						break;
					}
				}
			pthread_mutex_unlock(&mouseDataMutex);
		}  // if absolute mode
	}  // while
}  // mouseReaderThread

int main(int argc, char *argv[]) {
	int rc;  // mouseThread creation status

	// Mouse Initialization
	if ((mouse_fd = open(argv[1], O_RDONLY)) < 0) {
		printf("Error opening mouse \n");
		return 1;
	}

	if(atoi(argv[2]) == 1)
	{
		printf("Entering RELATIVE position mode with mouse device %s\n",
			argv[1]);
		mouseMode= MOUSE_RELATIVE;
	}
	else if(atoi(argv[2]) == 2)
	{
		printf("Entering ABSOLUTE position mode with mouse device %s\n",
			argv[1]);
		mouseMode= MOUSE_ABSOLUTE;
	}

	/* Spawn Mouse thread */
	printf("Starting Mouse Thread \n");
	rc = pthread_create(&mouseThread, NULL, mouseReaderThread, NULL);
	if(rc)
	{
		printf("Mouse thread failed to initialize!!\n");
	}

  /* server infinite loop */
  while(1) {
    usleep(100);
	// then copy mouse data
	//pthread_mutex_lock(&mouseDataMutex);
	printf("M %d %d %d %d %d %d \n", mouseData[0], mouseData[1], mouseData[2],
		mouseData[3], mouseData[4], mouseData[5]);
  }
}