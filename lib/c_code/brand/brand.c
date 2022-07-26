
#include <assert.h>
#include <stdio.h> 
#include <stdlib.h> 
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <signal.h>
#include "brand.h"

// #define REDIS_REPLY_STRING 1
// #define REDIS_REPLY_ARRAY 2
// #define REDIS_REPLY_INTEGER 3
// #define REDIS_REPLY_NIL 4
// #define REDIS_REPLY_STATUS 5
// #define REDIS_REPLY_ERROR 6
// #define REDIS_REPLY_DOUBLE 7
// #define REDIS_REPLY_BOOL 8
// #define REDIS_REPLY_MAP 9
// #define REDIS_REPLY_SET 10
// #define REDIS_REPLY_ATTR 11
// #define REDIS_REPLY_PUSH 12
// #define REDIS_REPLY_BIGNUM 13
// #define REDIS_REPLY_VERB 14

char * getNicknameFromCommandLine(int argc, char **argv) { 

    int opt;
    char *node_stream_name;

    while ((opt = getopt(argc, argv, "n:")) != -1) {

        switch (opt) { 
            case 'n': node_stream_name = optarg;break;
        }
    }

    return node_stream_name; 
}

void free_redis_id(char *id) {
    free(id);
}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
// Working with Redis tools
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

redisContext *connect_to_redis_from_commandline_flags(int argc, char **argv) { 

    int opt;
    int redis_port;
    char *redis_host;
    char *node_stream_name;

    while ((opt = getopt(argc, argv, "n:hs:p:")) != -1) {

        switch (opt) { 
            case 'n': node_stream_name = optarg;break;
            case 'hs' : redis_host = optarg; break;
            case 'p' : redis_port = atoi(optarg); break;
        }
    }


    return redisConnect(redis_host, redis_port); 
}

void free_redis_id(char *id) {
    free(id);
}

void increment_redis_id(char *id) {

    char buffer[512];
    strcpy(buffer, id);
    // Extract the part before the dash

    char *id1 = strtok(buffer, "-");
    char *id2 = strtok(NULL, "-");

    // Increment the id2 part
    int id2_int = atoi(id2);
    id2_int++;

    // Put it back together
    sprintf(id, "%s-%d", id1, id2_int);

}
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
// Working with nxjson
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

// Assert that the object requested is both not NULL and has the correct type
void assert_object(const nx_json *json, nx_json_type json_type) {
    if (json == NULL) {
        printf("Json structure returned null.\n");
        exit(1);
    } else if (json->type != json_type) {
        printf("The key %s has type %d and you are trying to assert it has type %d\n", json->key, json->type, json_type);
        exit(1);
    }
}

void assert_reply_not_null(redisReply *reply) {
    if (reply == NULL || reply->type == REDIS_REPLY_ERROR || reply->type == REDIS_REPLY_NIL) {
        printf("Error running redis command");
        exit(1);
    }
}

//----------------------------------------------------------------------
//----------------------------------------------------------------------

void print_type(nx_json_type json_type)
 {
    switch (json_type) {
        case NX_JSON_NULL:    printf("Type: NULL\n"); break;
        case NX_JSON_OBJECT:  printf("Type: OBJECT\n"); break;
        case NX_JSON_ARRAY:   printf("Type: ARRAY\n"); break;
        case NX_JSON_STRING:  printf("Type: STRING\n"); break;
        case NX_JSON_INTEGER: printf("Type: INTEGER\n"); break;
        case NX_JSON_DOUBLE:  printf("Type: DOUBLE\n"); break;
        case NX_JSON_BOOL:    printf("Type: BOOL\n"); break;
    }
 }


//----------------------------------------------------------------------
//----------------------------------------------------------------------
// Get the JSON object corresponding to a particular node's parameter.
const nx_json *get_parameter_object(const nx_json *json, const char *node, const char *parameter)
{
    // The JSON object of the nodes in the supergraph
    const nx_json *object_nodes = nx_json_get(json, "nodes");
    assert_object(object_nodes, NX_JSON_OBJECT);
    //search for the node in the nodes object
     if( strcmp(nx_json_get(object_nodes, node)->key, node) == 0)
     {
        printf("Found node %s\n", node);
        // The JSON object of the parameters of the node
        const nx_json *node_parameters = nx_json_get(nx_json_get(object_nodes, node),"parameters");
        assert_object(node_parameters, NX_JSON_ARRAY);
        //search for the parameter in the parameters array
        for(int i=0;i<node_parameters->children.length;i++)
        {
            const nx_json *this_parameter = nx_json_item(node_parameters, i);
            const nx_json *this_parameter_name = nx_json_get(this_parameter, "name");
            assert_object(this_parameter_name, NX_JSON_STRING);
            // Is this the parameter we're looking for?
            if (strcmp(this_parameter_name->text_value, parameter) == 0) 
            {
                //printf("Found parameter %s\n", parameter);
                return this_parameter;
            }
        }
     }

    printf("Node %s not found in the supergraph\n", node);
    exit(1);
}

//-------------------------------------------------------------------
//-- Get a parameter that is a string
//-------------------------------------------------------------------

// TODO: This function should allocate memory, rather than depending on the user to allocate memory
char** get_parameter_string(const nx_json *json, const char *node, const char *parameter, char **output) 
{
    *output =(char*)malloc(sizeof(char) * 512);
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    const nx_json *parameter_type   = nx_json_get(parameter_object, "type");
    assert_object(parameter_type, NX_JSON_STRING);
    if (strcmp(parameter_type->text_value, "string") == 0) 
    {
        printf("Found parameter %s\n", parameter);
        const nx_json *parameter_value = nx_json_get(parameter_object, "value");
        strcpy(*output, parameter_value->text_value);
    } 
    else 
    {
        printf("Parameter %s does not have the type string\n", parameter);
        exit(1);
    }
    return(output);
}



//-------------------------------------------------------------------
//-- Get a parameter list string
//-------------------------------------------------------------------
// TODO: The memory for output should be defined within this function, and `int n` should be `int &n`, with n
// being the number of elements to return

char*** get_parameter_list_string(const nx_json *json, const char *node, const char *parameter, char ***output, int *n)
{
     const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    const nx_json *parameter_type   = nx_json_get(parameter_object, "type");
    assert_object(parameter_type, NX_JSON_STRING);
    if (strcmp(parameter_type->text_value, "string") == 0) 
    {
        printf("Found parameter %s\n", parameter);
        const nx_json *parameter_value = nx_json_get(parameter_object, "value");
        assert_object(parameter_value, NX_JSON_ARRAY);
        *n = parameter_value->children.length;
        printf(" %s contains  %d elements \n",parameter ,*n);
        //allocate dynamic memory to store 2d array
        *output = (char **)malloc(sizeof(char *) * (*n));
        for (int i = 0; i < *n; i++) 
        {
            (*output)[i] = (char *)malloc(sizeof(char) * 512);
            const nx_json *this_value = nx_json_item(parameter_value,i);
            assert_object(this_value, NX_JSON_STRING);
            printf("%s\n", this_value->text_value);
            strcpy((*output)[i], this_value->text_value);
        }
    } 
    else 
    {
        printf("Parameter %s does not have the type list\n", parameter);
        exit(1);
    }
}

//-------------------------------------------------------------------
//-- Get a parameter INT
//-------------------------------------------------------------------
void get_parameter_int(const nx_json *json, const char *node, const char *parameter, int *output)
{
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    const nx_json *parameter_type   = nx_json_get(parameter_object, "type");
    assert_object(parameter_type, NX_JSON_STRING);
    if (strcmp(parameter_type->text_value, "int") == 0) 
    {
        printf("Found parameter %s\n", parameter);
        const nx_json *parameter_value = nx_json_get(parameter_object, "value");
        assert_object(parameter_value, NX_JSON_INTEGER);
        *output = parameter_value->num.u_value;
    } 
    else 
    {
        printf("Parameter %s does not have the type int\n", parameter);
        exit(1);
    }
}
//-------------------------------------------------------------------
//-- Get a parameter FLOAT
//-------------------------------------------------------------------
void get_parameter_float(const nx_json *json, const char *node, const char *parameter, float *output)
{
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    const nx_json *parameter_type   = nx_json_get(parameter_object, "type");
    assert_object(parameter_type, NX_JSON_STRING);
    if (strcmp(parameter_type->text_value, "float") == 0) 
    {
        printf("Found parameter %s\n", parameter);
        const nx_json *parameter_value = nx_json_get(parameter_object, "value");
        assert_object(parameter_value, NX_JSON_DOUBLE);
        *output = parameter_value->num.dbl_value;
    } 
    else 
    {
        printf("Parameter %s does not have the type float\n", parameter);
        exit(1);
    }
}
//-------------------------------------------------------------------
//-- Get a parameter BOOL
//-------------------------------------------------------------------
void get_parameter_bool(const nx_json *json, const char *node, const char *parameter, bool *output)
{
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    const nx_json *parameter_type   = nx_json_get(parameter_object, "type");
    assert_object(parameter_type, NX_JSON_STRING);
    if (strcmp(parameter_type->text_value, "bool") == 0) 
    {
        printf("Found parameter %s\n", parameter);
        const nx_json *parameter_value = nx_json_get(parameter_object, "value");
        assert_object(parameter_value, NX_JSON_BOOL);
        *output = parameter_value->num.s_value;
    } 
    else 
    {
        printf("Parameter %s does not have the type bool\n", parameter);
        exit(1);
    }
}

//------------------------------------------------------------------
// Read the supergraph and parse it with nx_json library
// TODO: Change `model_stream` to `supergraph`
//------------------------------------------------------------------

const nx_json *get_supergraph_json(redisContext *c, redisReply *reply, char *supergraph_id) {

    printf("PRE REPLY\n");
    char buffer[512];
    printf("Supergraph_id: %s\n",supergraph_id);
    sprintf(buffer, "XREVRANGE supergraph_stream + %s COUNT 1", supergraph_id);
    printf("%s\n", buffer);
    //redisAppendCommand(c, buffer);
    //redisGetReply(c, (void **) &reply);
    reply = redisCommand(c,buffer);
    if (reply->type == REDIS_REPLY_ERROR) {
        printf("Error: %s\n", reply->str);
        exit(1);
    }

    // printf("AA: %s\n", reply->str);
    // printf("AA: %zu\n", reply->elements);
    // printf("A: %s\n", reply->element[0]->str);
    // printf("B: %zu\n", reply->element[0]->element[1]->element[1]->len);
    // printf("C: %s\n", reply->element[0]->element[1]->element[1]->str);

    // This is a valid response, means there's nothing new to see, so we short circuit
    if (reply->type == REDIS_REPLY_NIL || reply->elements == 0)  
        return NULL;

    // Now we get the stream data in string format (should be valid JSON, produced by supervisor.py)
    char *data = reply->element[0]->element[1]->element[1]->str;
    // Get the ID corresponding to the SUPERGRAPH and then increment it
    strcpy(supergraph_id, reply->element[0]->element[0]->str);
    // Now we parse this into JSON, and ensure that it's valid
    const nx_json *json = nx_json_parse_utf8(data);
    assert_object(json, NX_JSON_OBJECT);
    return json;

}

void emit_status(redisContext *c, const char *node_name, enum node_state state, const char *node_message) {
    
    /* XADD node_name_status * state STATE string STRING */

    char node_state[256];
    switch (state) {
        case NODE_STARTED    : sprintf(node_state, "state Initialized");    break;
        case NODE_READY      : sprintf(node_state, "state Ready");          break;
        case NODE_SHUTDOWN   : sprintf(node_state, "state Shutdown");       break;
        case NODE_FATAL_ERROR: sprintf(node_state, "state \"Fatal Error: %s\"", node_message);  break;
        case NODE_WARNING    : sprintf(node_state, "state \"Warning: %s\"",     node_message);  break;
        case NODE_INFO       : sprintf(node_state, "state \"Info: %s\"",        node_message);  break;
        default:
            printf("Unknown state %d\n", state);
            break;
                            
    }
    
    char stream[512];
    redisReply *reply;
    sprintf(stream, "XADD %s_state * %s", node_name,node_state);
    printf("%s\n", stream);
    reply = redisCommand(c,stream);
    freeReplyObject(reply);
}

int start_new_redis_instance(char *host, int port)
{
    char *new_redis_command = malloc(sizeof(char) * 512);    
    //char *redis_port_string = malloc(sizeof(char) * 6);
    //sprintf(redis_port_string, "%d", port);
    // can also perform a chmod 777 <path_to_redis.conf>
    strcpy(new_redis_command,"sudo redis-server /etc/redis/redis-test.conf");
    // strcat(new_redis_command,host);
    // strcat(new_redis_command," --port ");
    // strcat(new_redis_command,redis_port_string);
    int redis_conn =  system(new_redis_command);
    if(redis_conn == -1)
    {
        return -1;
    }
    free(new_redis_command);
    return 1;
}

void stop_new_redis_instance(char *host, int port)
{
    char *new_redis_command = malloc(sizeof(char) * 512);    
    char *redis_port_string = malloc(sizeof(char) * 6);
    sprintf(redis_port_string, "%d", port);
    strcpy(new_redis_command,"redis-cli -h ");
    strcat(new_redis_command,host);
    strcat(new_redis_command," -p ");
    strcat(new_redis_command,redis_port_string);
    strcat(new_redis_command," shutdown");
    system(new_redis_command);
    free(new_redis_command); 
    free(redis_port_string);
}