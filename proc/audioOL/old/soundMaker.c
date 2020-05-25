
// C program to implement one side of FIFO 
// This side reads first, then reads 
#include <stdio.h> 
#include <string.h> 
#include <fcntl.h> 
#include <sys/stat.h> 
#include <sys/types.h> 
#include <unistd.h> 
#include "AlarmTools.h"
#include <stdlib.h>
#include <semaphore.h>
#include "Tictoc.h"
#include <signal.h>
#include <errno.h> //errno

  
// ffmpeg -f alsa -ac 1 -i hw:1 -f s16le -ar 16k -ac 1 - > /tmp/pipe
// Use format alsa, use one channel and use second (hw:1) sound card
// As output, format it to s16le and at 16k and use one channel, then pipe output

static void HandlerAlarm(int sig);
static void HandlerSIGINT(int sig);
static void captureSIGINT();

sem_t newDataSemaphore;

int main() 
{ 
    int fd1; 
    int ms1 = 1000000;
  
    InitializeAlarm(HandlerAlarm, 1, 0);

	if (sem_init(&newDataSemaphore, 0, 100*ms1) < 0) {
		printf("Could not initialize Semaphore! Exiting.\n");
		exit(1);
	}

    captureSIGINT();


    // FIFO file path 
    char * myfifo = "/tmp/soundPipeFIFO"; 
  
    
    char *soundFileName = "/home/david/code/github/LPCNet/wav/Emma.pcm";
    FILE *soundFILE = fopen(soundFileName, "rb");
    if (soundFILE == NULL) {
        perror("Fopen: ");
        exit(1);
    }
    int16_t *soundBuffer = malloc(2000000);
    if (fread (soundBuffer, 1, 2000000, soundFILE) < 0) {
        perror("fread: ");
        exit(1);
    }
  
    printf("[soundPipe] Opening Pipe: %s\n", myfifo);
    if((fd1 = open(myfifo,O_RDWR) < 0)) {
        perror("open FIFO: ");
        exit(1);
    }

    printf("[soundPipe] Pipe open\n");


	while(sem_wait(&newDataSemaphore) == 0) {
        if (write(fd1, myfifo, 10) < 0) {
            perror("write: ");
            exit(1);
        }
        printf("HI\n");
    }

    
    /* int test3; */
   /* if ((test3 = open("/tmp/test3",O_RDWR)) <= 0) { */
		/* printf("Could not initialize Signal: %s", strerror(errno)); */
		/* exit(1); */
   /* } */
    


/*     char str1[160080]; */
/*     int index = 0; */
/*     int l = 0; */
/* 	while(sem_wait(&newDataSemaphore) == 0) { */
/*     /1* while (1) { *1/ */
     

/*         struct timespec tic = Tic(); */
/*         l = read(fd1, str1, 160080); */
/*         struct timespec toc = Toc(&tic); */
/*         printf("(%d) (%d) (%d) Elapsed time: %ld milliseconds\n", index, l, (int)str1[0], (long) (toc.tv_nsec / 1000000)); */

/*         if (write(test3, str1, l) < 0) { */
/*             printf("Could not write to test3: %s", strerror(errno)); */
/*             exit(1); */
/*         } */
        

        /* if (l == 0) { */
        /*     exit(0); */
        /* } */
        /* printf("%s\n", str1); */
        // Print the info
        /* printf("(%d) (%d):", index, l); */ 

        // Print an array
        /* int16_t *lPointer = (int16_t *) &l; */
        /* for (int i = 0; i < l/2; i++){ */
        /*     printf("%d ", lPointer[i]); */
        /* } */
        /* printf("\n"); */


  
        /* index++; */
        // Now open in write mode and write 
        // string taken from user. 
        /* fd1 = open(myfifo,O_WRONLY); */ 
        /* fgets(str2, 80, stdin); */ 
        /* write(fd1, str2, strlen(str2)+1); */ 
        /* close(fd1); */ } 
    /* close(fd1); */ 
    /* return 0; */ 
/* } */ 

static void HandlerAlarm(int sig)
{
	sem_post(&newDataSemaphore);
}

static void HandlerSIGINT(int sig) {
    exit(0);
}
static void captureSIGINT() {

    struct sigaction sa = {0};
    sa.sa_handler 	= HandlerSIGINT;

	if(sigaction(SIGINT, &sa, NULL) == -1)
	{
		printf("Could not initialize Signal: %s", strerror(errno));
		exit(1);
	}

}

