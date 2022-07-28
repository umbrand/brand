/* Utilities for working with BRAND in Redis */

#include  <stdbool.h>
#include  <hiredis.h>
#include  "nxjson.h"

//--------------------------------------------------------------
// Parse command line arguments
//--------------------------------------------------------------

typedef struct command_line_args_t {
    int redis_port;
    char redis_host[20];
    char node_stream_name[20];
} command_line_args_t;

void parse_command_line_args(int argc, char **argv, command_line_args_t *p);


//--------------------------------------------------------------
// Tools for working with nxson
//--------------------------------------------------------------

const nx_json *get_supergraph_json(redisContext *c, redisReply *reply, char *supergraph_id);
char* get_parameter_string(const nx_json *json, const char *node, const char *parameter);
//char*** get_parameter_list_string(const nx_json *json, const char *node, const char *parameter, char ***output,int *n);
int get_parameter_int(const nx_json *json, const char *node, const char *parameter);
//void get_parameter_float(const nx_json *json, const char *node, const char *parameter, float *output);
//void get_parameter_bool(const nx_json *json, const char *node, const char *parameter, bool *output);

//--------------------------------------------------------------
// Emit node state
//--------------------------------------------------------------

enum node_state {NODE_STARTED, NODE_READY, NODE_SHUTDOWN, NODE_FATAL_ERROR, NODE_WARNING, NODE_SUPERGRAPH_UPDATE, NODE_INFO};
void emit_status(redisContext *c, const char *node_name, enum node_state state, const char *node_message);