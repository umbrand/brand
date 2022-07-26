/* Utilities for working with BRAND in Redis */

#include  <hiredis.h>
#include  "nxjson.h"

//--------------------------------------------------------------
// Connect to Redis from commandline flags
//--------------------------------------------------------------

// Connect to redis based on commandline flags
// We expect the flags -h and -p to be host and the port, respectively

redisContext *connect_to_redis_from_commandline_flags(int argc, char **argv);

//--------------------------------------------------------------
// Increment Redis ID
//--------------------------------------------------------------

void increment_redis_id(char *);
//
//--------------------------------------------------------------
// Tools for working with nxson
//--------------------------------------------------------------

char** get_parameter_string(const nx_json *json, const char *node, const char *parameter, char **output);
char*** get_parameter_list_string(const nx_json *json, const char *node, const char *parameter, char ***output,int *n);
void get_parameter_int(const nx_json *json, const char *node, const char *parameter, int *output);
void get_parameter_float(const nx_json *json, const char *node, const char *parameter, float *output);
void get_parameter_bool(const nx_json *json, const char *node, const char *parameter, bool *output);
const nx_json *get_supergraph_json(redisContext *c, redisReply *reply, char *supergraph_id);

//--------------------------------------------------------------
// Emit a node state
//--------------------------------------------------------------

enum node_state {NODE_STARTED, NODE_READY, NODE_SHUTDOWN, NODE_FATAL_ERROR, NODE_WARNING, NODE_SUPERGRAPH_UPDATE, NODE_INFO};

void emit_status(redisContext *c, const char *node_name, enum node_state state, const char *node_message);
int start_new_redis_instance(char *host, int port);
void stop_new_redis_instance(char *host, int port);