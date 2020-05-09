
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <redisTools.h>

/* This function just allows someone to call the redisTools.py function from within C
 * It populates two strings : path to redisTools and the path to the yaml file
 * It then runs the command. It's designed to read a single YAML value and return
 * the string YAML value.
 */

int load_YAML_variable_string(char *process, char *value, char *buffer, int n) {

    char bashCommand[1024]         = {0};
    char redisToolsPythonFile[256] = {0};
    char configurationFile[256]    = {0};
    int readLength                 = 0; // How much was read from fread()
    FILE *fp;

    sprintf(redisToolsPythonFile, "%s/lib/redisTools/redisTools.py", ROOT_PATH);
    sprintf(configurationFile, "%s/yaml/%s.yaml", ROOT_PATH, process);

    // Start by populating the command to run, and then run the command
    
    sprintf(bashCommand, "python %s %s --name %s", redisToolsPythonFile, configurationFile, value);

    fp = popen(bashCommand, "r");
    if (fp == NULL) {
        perror("popen() failed on python script to load YAML data.\n");
        return -1;
    }

    if((readLength = fread(buffer, 1, n, fp)) < 0) {
        perror("fread could not read variable from python script.\n");
        return -1;
    }

    return readLength;
}

/* This function just allows someone to call the redisTools.py function from within C
 * It populates two strings : path to redisTools and the path to the yaml file
 * It then runs the command
 */

int initialize_redis_from_YAML(char *process) {

    char bashCommand[1024]         = {0};
    char redisToolsPythonFile[256] = {0};
    char configurationFile[256]    = {0};
    FILE *fp;

    sprintf(redisToolsPythonFile, "%s/lib/redisTools/redisTools.py", ROOT_PATH);
    sprintf(configurationFile, "%s/yaml/%s.yaml", ROOT_PATH, process);

    // Start by populating the command to run, and then run the command
    
    sprintf(bashCommand, "python %s %s", redisToolsPythonFile, configurationFile);

    fp = popen(bashCommand, "r");
    if (fp == NULL) {
        perror("popen() failed on python script to load YAML data.\n");
        return -1;
    }

    return 0;
}

/* Helper function for loading a Redis context */

int load_redis_context(redisContext **redis_context, char *redis_ip, char *redis_port) {

    const char *hostname = redis_ip;
    int port = atoi(redis_port);
    struct timeval timeout = { 1, 500000 }; // 1.5 seconds

    *redis_context = redisConnectWithTimeout(hostname, port, timeout); // Global variable

    if (*redis_context == NULL || (*redis_context)->err) {
        if (*redis_context) {
            printf("Connection error: %s\n", (*redis_context)->errstr);
            redisFree(*redis_context);
        } else {
            printf("Connection error: can't allocate redis context\n");
        }
        exit(1);
    }

    return 0;

}

/* Helper function for reading a String reply from Redis */

int redis_string(redisContext *redis_context, char *command, char *string, int n) {

    redisReply *reply;
    reply = redisCommand(redis_context, command);
    if (reply == NULL || reply->type == REDIS_REPLY_ERROR) {
        return REDIS_REPLY_ERROR;
    }
    if (reply->type == REDIS_REPLY_NIL) {
        return REDIS_REPLY_NIL;
    }

    strncpy(string, reply->str, n);
    freeReplyObject(reply);

    return 0;

}

/* Helper function for reading an Integer reply from Redis */

int redis_int(redisContext *redis_context, char *command, int *value) {

    redisReply *reply;
    reply = redisCommand(redis_context, command);
    if (reply == NULL || reply->type == REDIS_REPLY_ERROR) {
        return REDIS_REPLY_ERROR;
    }
    if (reply->type == REDIS_REPLY_NIL) {
        return REDIS_REPLY_NIL;
    }

    *value = (int) reply->integer;
    freeReplyObject(reply);

    return 0;

}

int redis_succeed(redisContext *redis_context, char *command) {

    freeReplyObject(redisCommand(redis_context, command));
    return 0;
}

