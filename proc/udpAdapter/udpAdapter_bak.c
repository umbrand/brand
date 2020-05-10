/* UDPApapter.c
 * A small program that listens on broadcasted UDP data and then pushes it to a Redis server
 * It turns out that creating a Python program wasn't consistent enough so I had to port this
 * over to C. 
 *
 * The program first creates a connection with Redis, and then sits in a while loop waiting
 * for new UDP packets. After receiving them it pushes it to a list. Note that the data
 * comes in as an array of int16. This first version just converts the int16 to a string
 * and then uses lpush to get that whole array for a timestamp to the database.
 * I didn't think it was necessary to make a separate list for each channel, but it's 
 * cleaner to do it that way, although it would require downstream processes to start
 * using locks. This may be an idea for a future version.
 *
 * TODO:
 * 1) Make the back-end Redis compatabile so that it can be used with a rest.py front-end
 *
 * David Brandman
 * April 2020
 * Version 1.0
 */


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <hiredis.h>
#include <signal.h>
#include <sys/time.h>
#include <time.h>
#include <errno.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <time.h>


#define BUFFER_SIZE 20000
#define REDIS_FIELD "rawData"
#define NUM_CHANNELS 48

void getTimeString(char *buffer);

int initializeSocket();
void initializeRedis(redisContext *c, const char *hostname, int port);

int main(int argc, char **argv) {

    int fd = initializeSocket();

    const char *hostname = "127.0.0.1";
    int port = 6379;

    redisContext *c;
    /* initializeRedis(c, hostname, port); */
    redisReply *reply;

    struct timeval timeout = { 1, 500000 }; // 1.5 seconds

    c = redisConnectWithTimeout(hostname, port, timeout);
    if (c == NULL || c->err) {
        if (c) {
            printf("Connection error: %s\n", c->errstr);
            redisFree(c);
        } else {
            printf("Connection error: can't allocate redis context\n");
        }
        exit(1);
    }

    char buffer[BUFFER_SIZE] = {0};

    char timeStringBuffer[80] = {0};

    printf("In while loop...\n");
    while (1)
    {
        ssize_t bufferLength = 0;

        if ((bufferLength = recv(fd, buffer, BUFFER_SIZE, 0)) < 0) {
            perror("recv");
            exit(1);
        }
        else {

            uint16_t *bufferPointer = (uint16_t *) buffer;

            // Assume that we have n being a multiple of the number of channels
            int nRows = (bufferLength / 2) / NUM_CHANNELS;

            for (int i = 0; i < nRows; i++) {

                char bufferString[2096] = {0};

                getTimeString(timeStringBuffer);
                /* printf("%s\n", timeStringBuffer); */

                /* strcpy(bufferString, timeStringBuffer); */
                sprintf(bufferString, "%s,", timeStringBuffer);
                int index = strlen(bufferString);
                
                // Convert the numbers to one string
                for (int j=0; j < NUM_CHANNELS; j++) {
                    index += sprintf(&bufferString[index], "%d ", bufferPointer[i*NUM_CHANNELS + j]);
                }
                index--; // Don't copy the last space introduced in the sprintf

                // Now inform redis
                freeReplyObject(redisCommand(c, "lpush %s %b", REDIS_FIELD, bufferString, (size_t) index));
                freeReplyObject(redisCommand(c, "publish %s %b", REDIS_FIELD, bufferString, (size_t) index));

                // and cut ond data
                freeReplyObject(redisCommand(c, "ltrim %s 0 1999", REDIS_FIELD));
            }



            /* for (int i=0; i < n; i++) */
            /*    index += sprintf(&bufferString[index], " %d", bufferPointer[i]); */


            /* reply = redisCommand(c,"lpush abc %s", bufferString); //b", bufferString, (size_t) index); */
            /* reply = redisCommand(c,"lpush abc %b", bufferString, (size_t) index); */
            /* freeReplyObject(reply); */

        }


    }
    return 0;
}


void initializeRedis(redisContext *c, const char *hostname, int port) {

    struct timeval timeout = { 1, 500000 }; // 1.5 seconds

    c = redisConnectWithTimeout(hostname, port, timeout);
    if (c == NULL || c->err) {
        if (c) {
            printf("Connection error: %s\n", c->errstr);
            redisFree(c);
        } else {
            printf("Connection error: can't allocate redis context\n");
        }
        exit(1);
    }

}

void getTimeString(char *buffer) {
    time_t rawtime;
    struct tm *info;
    struct timeval tv;

    gettimeofday(&tv, NULL);

    time(&rawtime);
    info = localtime(&rawtime);
    strftime(buffer,80,"%Y-%m-%d %H:%M:%S", info);
    sprintf(&buffer[19], ".%03ld", tv.tv_usec / 1000);

}

int initializeSocket() {

    // Create a socket
   	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP ); 
    if (fd == 0) {
        perror("socket failed"); 
        exit(EXIT_FAILURE); 
    }
    //Set socket permissions
    int broadcastPermission = 1;
    if (setsockopt(fd,SOL_SOCKET,SO_BROADCAST, (void *) &broadcastPermission, sizeof(broadcastPermission)) < 0) {
        perror("socket permission failure"); 
        exit(EXIT_FAILURE); 
    }


    // Now configure the socket
    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    addr.sin_port        = htons(53000);

     if (bind(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0)
     {
        perror("socket binding failure"); 
        exit(EXIT_FAILURE); 
     }

     return fd;
} 

