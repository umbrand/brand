
#include <assert.h>
#include <stdio.h> 
#include <stdlib.h> 
#include <string.h>
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


//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
// Parse command line args (Redis and nickname)
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

void parse_command_line_args(int argc, char **argv, command_line_args_t *p) { 

    int opt;
    int redis_port;
    char redis_host[20];
    char node_stream_name[20];
    char redis_socket[40];

    int nflg = 0, sflg = 0, iflg = 0, pflg = 0, errflg = 0;

    while ((opt = getopt(argc, argv, "n:s:i:p:")) != -1) {
        switch (opt) { 
            case 'n': 
                // missing str check on optarg
                strcpy(node_stream_name, optarg); 
                nflg++;
                break;
            case 's': 
                // missing str check on optarg
                strcpy(redis_socket, optarg); 
                sflg++;
                break;
            case 'i': 
                // missing str check on optarg
                strcpy(redis_host, optarg);
                iflg++; 
                break;
            case 'p': 
                // missing int check on optarg
                redis_port = atoi(optarg); 
                pflg++;
                break;
        }
    }

    // must specify -n
    if (nflg == 0)
    {
        printf("ERROR: -n (nickname) argument not provided. Exiting node process.");
		exit(1);
    }

    if (sflg > 0)
    {
        // if -s is specified, ignore -i, and print warning if -i is also specified (that it is being ignored)
        if (iflg > 0)
        {
           printf("WARNING: Both -s (Redis socket) and -i (host IP) provided, so -i is being ignored."); 
        }
        // initialize redis here with socket
    }
    else if (iflg > 0)
    {
        // if -i is specified without -s, must also specify -p
        if (pflg == 0)
        {
           printf("ERROR: -p (port) argument not provided with -i (host IP). Exiting node process."); 
           exit(1);
        }
        // initialize redis here with ip and port
    }
    // must specify either -s or -i
    else
    {
        printf("ERROR: Neither -s (Redis socket) or -i (host IP) provided. Exiting node process."); 
        exit(1);
    }

    p->redis_port = redis_port;
    strcpy(p->redis_socket, redis_socket);
    strcpy(p->redis_host, redis_host);
    strcpy(p->node_stream_name, node_stream_name);

    /*
    printf("redis host: %s\n", p->redis_host);
    printf("redis port: %d\n", p->redis_port);
    printf("node nickname: %s\n", p->node_stream_name);
    */ 
}


//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
// Working with nxjson
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

// Assert that the object requested is both not NULL and has the correct type
void assert_object(const nx_json *json, nx_json_type json_type) {
    if (json == NULL) {
        printf("JSON structure returned null.\n");
        exit(1);
    } else if (json->type != json_type) {
        printf("The JSON object \"%s\" has type %d and attempted to assert it to type %d\n", json->key, json->type, json_type);
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

//------------------------------------------------------------------
// Read the supergraph and parse it with nx_json library
//------------------------------------------------------------------

const nx_json *get_supergraph_json(redisContext *c, redisReply *reply, char *supergraph_id) {

    //printf("PRE REPLY\n");
    char buffer[512];
    //printf("Supergraph_id: %s\n",supergraph_id);
    sprintf(buffer, "XREVRANGE supergraph_stream + %s COUNT 1", supergraph_id);
    //printf("%s\n", buffer);

    reply = redisCommand(c,buffer);
    if (reply->type == REDIS_REPLY_ERROR) {
        printf("Error: %s\n", reply->str);
        exit(1);
    }

    // This is a valid response, means there's nothing new to see, so we short circuit
    if (reply->type == REDIS_REPLY_NIL || reply->elements == 0)  
        return NULL;

    // Now we get the stream data in string format (should be valid JSON, produced by supervisor.py)
    char *data = reply->element[0]->element[1]->element[1]->str;
    
    // Get the ID corresponding to the SUPERGRAPH and then increment it
    //strcpy(supergraph_id, reply->element[0]->element[0]->str);

    // Now we parse this into JSON, and ensure that it's valid
    const nx_json *json = nx_json_parse_utf8(data);
    assert_object(json, NX_JSON_OBJECT);

    // free Redis reply
    freeReplyObject(reply);

    return json;

}

//----------------------------------------------------------------------
// Get the JSON object corresponding to a particular node's parameter.
//----------------------------------------------------------------------
const nx_json *get_parameter_object(const nx_json *json, const char *node, const char *parameter)
{
    //printf("Loading param %s\n", parameter);
    // The JSON object of the nodes in the supergraph
    const nx_json *object_nodes = nx_json_get(json, "nodes");
    assert_object(object_nodes, NX_JSON_OBJECT);
    //search for the node in the nodes object
    if( strcmp(nx_json_get(object_nodes, node)->key, node) == 0)
    {
        //printf("Found node %s\n", node);
        // The JSON object of the parameters of the node
        const nx_json *node_parameters = nx_json_get(nx_json_get(object_nodes, node),"parameters");
        //printf("# parameters %d\n", node_parameters->children.length);
        //assert_object(node_parameters, NX_JSON_ARRAY);
        //get the parameter from the parameters array
        const nx_json *this_parameter = nx_json_get(node_parameters, parameter);
        if (this_parameter == NULL) {
            printf("parameter %s returned null.\n", parameter);
            exit(1);
        }
        return this_parameter;
    }
    printf("Node %s not found in the supergraph\n", node);
    exit(1);
}

//-------------------------------------------------------------------
//-- Get a parameter that is a string
//-------------------------------------------------------------------

char* get_parameter_string(const nx_json *json, const char *node, const char *parameter) 
{
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    // check if parameter is a string
    if (parameter_object->type == NX_JSON_STRING) 
    {
        //printf("Found parameter %s\n", parameter);
        return(parameter_object->text_value);
    } 
    else 
    {
        printf("Parameter %s does not have the type string\n", parameter);
        exit(1);
    }
    //return(output);
}

//-------------------------------------------------------------------
//-- Get a parameter INT
//-------------------------------------------------------------------
int get_parameter_int(const nx_json *json, const char *node, const char *parameter)
{
    const nx_json *parameter_object = get_parameter_object(json, node, parameter);
    // check if parameter is a int
    if (parameter_object->type == NX_JSON_INTEGER) 
    {
        //printf("Found parameter %s\n", parameter);
        return (int)parameter_object->num.u_value;
    } 
    else 
    {
        printf("Parameter %s does not have the type int\n", parameter);
        exit(1);
    }
}

/*
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
*/

//--------------------------------------------------------------
// Emit node state
//--------------------------------------------------------------

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



