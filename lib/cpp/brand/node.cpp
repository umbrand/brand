#include "node.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <random>
#include <signal.h>
#include <unistd.h>

namespace brand {

// Static member initialization
BRANDNode *BRANDNode::instance_ = nullptr;

BRANDNode::BRANDNode()
    : redis_context_(nullptr), redis_port_(6379), seq_(0),
      supergraph_id_("0-0") {
  instance_ = this;
  producer_gid_hex_ = generateUUID();
}

BRANDNode::~BRANDNode() {
  if (redis_context_) {
    redisFree(redis_context_);
    redis_context_ = nullptr;
  }
  instance_ = nullptr;
}

bool BRANDNode::initialize(int argc, char *argv[]) {
  try {
    parseArguments(argc, argv);
    setupLogging();

    if (!connectToRedis(redis_host_, redis_port_, redis_socket_)) {
      log_error("Failed to connect to Redis");
      return false;
    }

    // Initialize parameters (will be parsed from command line)
    initializeParameters();

    // Setup signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);

    // Post initialized status to Redis
    std::map<std::string, std::string> initial_data = {
        {"code", "0"}, {"status", "initialized"}};

    redisReply *reply = (redisReply *)redisCommand(
        redis_context_, "XADD %s * code %s status %s",
        (name_ + "_state").c_str(), "0", "initialized");

    if (reply) {
      freeReplyObject(reply);
    }

    log_info("Node initialized successfully");
    return true;

  } catch (const std::exception &e) {
    handleException(std::string("Initialization failed: ") + e.what());
    return false;
  }
}

void BRANDNode::run() {
  log_info("Starting main run loop");

  while (true) {
    try {
      work();
      updateParameters();
    } catch (const std::exception &e) {
      handleException(std::string("Error in run loop: ") + e.what());
      break;
    }
  }
}

void BRANDNode::publish(const std::string &stream,
                        const std::map<std::string, std::string> &data,
                        const std::map<std::string, std::string> &parents) {
  if (!redis_context_) {
    log_error("Redis context not available for publishing");
    return;
  }

  // Create header
  std::map<std::string, std::string> header = {
      {"ts", std::to_string(getTimestampNs())},
      {"seq", std::to_string(nextSeq())},
      {"producer_gid", producer_gid_hex_},
      {"node", name_}};

  if (!parents.empty()) {
    header["parents"] = mapToJson(parents);
  }

  // Build command
  std::string cmd = "XADD " + stream + " * _hdr " + mapToJson(header);

  for (const auto &pair : data) {
    cmd += " " + pair.first + " " + pair.second;
  }

  redisReply *reply = (redisReply *)redisCommand(redis_context_, cmd.c_str());

  if (reply) {
    if (reply->type == REDIS_REPLY_ERROR) {
      log_error("Redis publish error: " + std::string(reply->str));
    }
    freeReplyObject(reply);
  }
}

StreamEntry *BRANDNode::read_one(const std::string &stream, int block_ms) {
  if (!redis_context_) {
    log_error("Redis context not available for reading");
    return nullptr;
  }

  std::string last_id = cursors_.count(stream) ? cursors_[stream] : "$";

  redisReply *reply = (redisReply *)redisCommand(
      redis_context_, "XREAD BLOCK %d COUNT 1 STREAMS %s %s", block_ms,
      stream.c_str(), last_id.c_str());

  if (!reply || reply->type != REDIS_REPLY_ARRAY || reply->elements == 0) {
    if (reply)
      freeReplyObject(reply);
    return nullptr;
  }

  // Parse the reply
  if (reply->element[0]->type == REDIS_REPLY_ARRAY &&
      reply->element[0]->elements >= 2) {

    redisReply *stream_data = reply->element[0]->element[1];
    if (stream_data->type == REDIS_REPLY_ARRAY && stream_data->elements > 0) {

      redisReply *entry = stream_data->element[0];
      if (entry->type == REDIS_REPLY_ARRAY && entry->elements >= 2) {

        StreamEntry *result = new StreamEntry();
        result->id = entry->element[0]->str;
        cursors_[stream] = result->id;

        // Parse fields
        redisReply *fields = entry->element[1];
        if (fields->type == REDIS_REPLY_ARRAY) {
          for (size_t i = 0; i < fields->elements; i += 2) {
            if (i + 1 < fields->elements) {
              std::string key = fields->element[i]->str;
              std::string value = fields->element[i + 1]->str;
              result->fields[key] = value;
            }
          }
        }

        freeReplyObject(reply);
        return result;
      }
    }
  }

  freeReplyObject(reply);
  return nullptr;
}

std::vector<StreamEntry> BRANDNode::read_latest(const std::string &stream,
                                                int count) {
  std::vector<StreamEntry> result;

  if (!redis_context_) {
    log_error("Redis context not available for reading");
    return result;
  }

  redisReply *reply = (redisReply *)redisCommand(
      redis_context_, "XREVRANGE %s + - COUNT %d", stream.c_str(), count);

  if (!reply || reply->type != REDIS_REPLY_ARRAY) {
    if (reply)
      freeReplyObject(reply);
    return result;
  }

  for (size_t i = 0; i < reply->elements; i++) {
    redisReply *entry = reply->element[i];
    if (entry->type == REDIS_REPLY_ARRAY && entry->elements >= 2) {
      StreamEntry stream_entry;
      stream_entry.id = entry->element[0]->str;

      // Parse fields
      redisReply *fields = entry->element[1];
      if (fields->type == REDIS_REPLY_ARRAY) {
        for (size_t j = 0; j < fields->elements; j += 2) {
          if (j + 1 < fields->elements) {
            std::string key = fields->element[j]->str;
            std::string value = fields->element[j + 1]->str;
            stream_entry.fields[key] = value;
          }
        }
      }

      result.push_back(stream_entry);
    }
  }

  freeReplyObject(reply);
  return result;
}

StreamEntries *BRANDNode::read_n(const std::string &stream, int n,
                                 int block_ms) {
  if (!redis_context_) {
    log_error("Redis context not available for reading");
    return nullptr;
  }

  std::string last_id = cursors_.count(stream) ? cursors_[stream] : "$";

  redisReply *reply;
  if (block_ms >= 0) {
    reply = (redisReply *)redisCommand(
        redis_context_, "XREAD BLOCK %d COUNT %d STREAMS %s %s", block_ms, n,
        stream.c_str(), last_id.c_str());
  } else {
    reply = (redisReply *)redisCommand(redis_context_,
                                       "XREAD COUNT %d STREAMS %s %s", n,
                                       stream.c_str(), last_id.c_str());
  }

  if (!reply || reply->type != REDIS_REPLY_ARRAY || reply->elements == 0) {
    if (reply)
      freeReplyObject(reply);
    return nullptr;
  }

  StreamEntries *result = new StreamEntries();

  // Parse the reply structure
  if (reply->element[0]->type == REDIS_REPLY_ARRAY &&
      reply->element[0]->elements >= 2) {

    redisReply *stream_data = reply->element[0]->element[1];
    if (stream_data->type == REDIS_REPLY_ARRAY) {

      for (size_t i = 0; i < stream_data->elements; i++) {
        redisReply *entry = stream_data->element[i];
        if (entry->type == REDIS_REPLY_ARRAY && entry->elements >= 2) {

          std::string entry_id = entry->element[0]->str;
          result->entry_ids.push_back(entry_id);
          cursors_[stream] = entry_id;

          // Parse fields
          redisReply *fields = entry->element[1];
          if (fields->type == REDIS_REPLY_ARRAY) {
            for (size_t j = 0; j < fields->elements; j += 2) {
              if (j + 1 < fields->elements) {
                std::string key = fields->element[j]->str;
                std::string value = fields->element[j + 1]->str;

                // Handle JSON parsing for _hdr field
                if (key == "_hdr") {
                  auto hdr_map = parseJsonToMap(value);
                  for (const auto &hdr_pair : hdr_map) {
                    result->data[hdr_pair.first].push_back(hdr_pair.second);
                  }
                } else {
                  result->data[key].push_back(value);
                }
              }
            }
          }
        }
      }
    }
  }

  freeReplyObject(reply);
  return result;
}

std::vector<std::map<std::string, std::string>>
BRANDNode::getParametersFromSupergraph(bool complete_supergraph) {
  std::vector<std::map<std::string, std::string>> result;

  if (!redis_context_) {
    log_error("Redis context not available");
    return result;
  }

  redisReply *reply = (redisReply *)redisCommand(
      redis_context_, "XRANGE supergraph_stream (%s +", supergraph_id_.c_str());

  if (!reply || reply->type != REDIS_REPLY_ARRAY || reply->elements == 0) {
    if (reply)
      freeReplyObject(reply);
    return result;
  }

  // Update supergraph_id to the latest entry
  if (reply->elements > 0) {
    redisReply *last_entry = reply->element[reply->elements - 1];
    if (last_entry->type == REDIS_REPLY_ARRAY && last_entry->elements >= 1) {
      supergraph_id_ = last_entry->element[0]->str;
    }
  }

  if (complete_supergraph) {
    // Return raw supergraph data - simplified implementation
    freeReplyObject(reply);
    return result;
  }

  // Parse each entry to extract node parameters
  for (size_t i = 0; i < reply->elements; i++) {
    redisReply *entry = reply->element[i];
    if (entry->type == REDIS_REPLY_ARRAY && entry->elements >= 2) {

      redisReply *fields = entry->element[1];
      std::map<std::string, std::string> node_params;

      if (fields->type == REDIS_REPLY_ARRAY) {
        for (size_t j = 0; j < fields->elements; j += 2) {
          if (j + 1 < fields->elements &&
              strcmp(fields->element[j]->str, "data") == 0) {

            // Parse JSON data to find this node's parameters
            std::string json_data = fields->element[j + 1]->str;
            // Simplified JSON parsing - in production, use proper JSON parsing
            // This is a placeholder for the full JSON parsing logic
            break;
          }
        }
      }

      result.push_back(node_params);
    }
  }

  freeReplyObject(reply);
  return result;
}

void BRANDNode::log(const std::string &level, const std::string &message) {
  // Get current time
  auto now = std::chrono::system_clock::now();
  auto time_t = std::chrono::system_clock::to_time_t(now);
  auto tm = *std::localtime(&time_t);

  // Format timestamp
  std::ostringstream oss;
  oss << std::put_time(&tm, "%H:%M:%S");

  // Console logging
  std::cout << oss.str() << " [" << name_ << "] " << level << ": " << message
            << std::endl;

  // Redis logging
  if (redis_context_) {
    std::map<std::string, std::string> log_data = {
        {"level", level}, {"message", message}, {"timestamp", oss.str()}};

    redisReply *reply = (redisReply *)redisCommand(
        redis_context_, "XADD %s * level %s message %s timestamp %s",
        (name_ + "_log").c_str(), level.c_str(), message.c_str(),
        oss.str().c_str());

    if (reply) {
      freeReplyObject(reply);
    }
  }
}

void BRANDNode::signalHandler(int sig) {
  if (instance_) {
    instance_->terminate(sig);
  }
}

void BRANDNode::updateParameters() {
  // Check for parameter updates from supergraph
  auto new_params = getParametersFromSupergraph();
  if (!new_params.empty() && !new_params.back().empty()) {
    // Update parameters
    for (const auto &param : new_params.back()) {
      parameters_[param.first] = param.second;
    }
    log_debug("Parameters updated from supergraph");
  }
}

void BRANDNode::setupLogging(const std::string &log_level) {
  log_info("Logging setup completed with level: " + log_level);
}

bool BRANDNode::connectToRedis(const std::string &host, int port,
                               const std::string &socket) {
  if (!socket.empty()) {
    redis_context_ = redisConnectUnix(socket.c_str());
    if (redis_context_ && !redis_context_->err) {
      log_info("Redis connection established on socket: " + socket);
      return true;
    }
  } else {
    redis_context_ = redisConnect(host.c_str(), port);
    if (redis_context_ && !redis_context_->err) {
      log_info("Redis connection established on host: " + host +
               ", port: " + std::to_string(port));
      return true;
    }
  }

  if (redis_context_) {
    log_error("Redis connection error: " + std::string(redis_context_->errstr));
    redisFree(redis_context_);
    redis_context_ = nullptr;
  }

  return false;
}

void BRANDNode::initializeParameters(const std::string &fallback_params) {
  if (!fallback_params.empty()) {
    auto fallback_map = parseJsonToMap(fallback_params);
    parameters_ = fallback_map;
  }

  // Try to get parameters from supergraph
  auto node_params = getParametersFromSupergraph();
  if (!node_params.empty() && !node_params.back().empty()) {
    parameters_ = node_params.back();
  }

  // Validate required parameters
  if (!validateParameters()) {
    log_error("Invalid parameters configuration");
    std::exit(1);
  }
}

int64_t BRANDNode::getTimestampNs() {
  auto now = std::chrono::high_resolution_clock::now();
  auto duration = now.time_since_epoch();
  return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
}

std::map<std::string, std::string>
BRANDNode::parseJsonToMap(const std::string &json_str) {
  std::map<std::string, std::string> result;

  if (json_str.empty()) {
    return result;
  }

  // Simple JSON parsing using nxjson
  char *json_copy = strdup(json_str.c_str());
  const nx_json *json = nx_json_parse_utf8(json_copy);

  if (!json) {
    log_error("Failed to parse JSON: " + json_str);
    free(json_copy);
    return result;
  }

  if (json->type == NX_JSON_OBJECT) {
    for (const nx_json *item = json->children.first; item; item = item->next) {
      if (item->key) {
        if (item->type == NX_JSON_STRING && item->text_value) {
          result[item->key] = item->text_value;
        } else if (item->type == NX_JSON_OBJECT) {
          // For objects like input_streams and output_streams, store as JSON
          // string
          result[item->key] = "{}"; // simplified - store empty object
        } else {
          // For other types, convert to string representation
          result[item->key] = ""; // placeholder
        }
      }
    }
  } else {
    log_warning("JSON is not an object, ignoring: " + json_str);
  }

  nx_json_free(json);
  free(json_copy);

  return result;
}

std::string
BRANDNode::mapToJson(const std::map<std::string, std::string> &map) {
  std::ostringstream oss;
  oss << "{";

  bool first = true;
  for (const auto &pair : map) {
    if (!first)
      oss << ",";
    oss << "\"" << pair.first << "\":\"" << pair.second << "\"";
    first = false;
  }

  oss << "}";
  return oss.str();
}

void BRANDNode::terminate(int sig) {
  log_info("Signal " + std::to_string(sig) + " received, exiting");

  cleanup();

  // Post termination status to Redis
  if (redis_context_) {
    redisReply *reply = (redisReply *)redisCommand(
        redis_context_, "XADD %s * code %s status %s",
        (name_ + "_state").c_str(), "0", "done");

    if (reply) {
      freeReplyObject(reply);
    }

    redisFree(redis_context_);
    redis_context_ = nullptr;
  }

  std::exit(0);
}

void BRANDNode::handleException(const std::string &error) {
  log_error(error);
  if (redis_context_) {
    // Log error to Redis
    redisReply *reply = (redisReply *)redisCommand(
        redis_context_, "XADD %s * level ERROR message %s",
        (name_ + "_log").c_str(), error.c_str());

    if (reply) {
      freeReplyObject(reply);
    }
  }
}

std::string BRANDNode::generateUUID() {
  std::random_device rd;
  std::mt19937 gen(rd());
  std::uniform_int_distribution<> dis(0, 15);

  std::string uuid;
  for (int i = 0; i < 32; i++) {
    if (i == 8 || i == 12 || i == 16 || i == 20) {
      uuid += "-";
    }
    uuid += "0123456789abcdef"[dis(gen)];
  }

  return uuid;
}

void BRANDNode::parseArguments(int argc, char *argv[]) {
  // Set defaults (matching Python version)
  name_ = "node";
  redis_host_ = "localhost";
  redis_port_ = 6379;
  redis_socket_ = "";
  std::string fallback_parameters = "";

  // Parse arguments
  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];

    if (arg == "-n" || arg == "--nickname") {
      if (i + 1 < argc) {
        name_ = argv[++i];
      } else {
        log_error("Error: -n/--nickname requires a value");
        std::exit(1);
      }
    } else if (arg == "-i" || arg == "--redis_host") {
      if (i + 1 < argc) {
        redis_host_ = argv[++i];
      } else {
        log_error("Error: -i/--redis_host requires a value");
        std::exit(1);
      }
    } else if (arg == "-p" || arg == "--redis_port") {
      if (i + 1 < argc) {
        redis_port_ = std::atoi(argv[++i]);
      } else {
        log_error("Error: -p/--redis_port requires a value");
        std::exit(1);
      }
    } else if (arg == "-s" || arg == "--redis_socket") {
      if (i + 1 < argc) {
        redis_socket_ = argv[++i];
      } else {
        log_error("Error: -s/--redis_socket requires a value");
        std::exit(1);
      }
    } else if (arg == "--parameters") {
      if (i + 1 < argc) {
        fallback_parameters = argv[++i];
      } else {
        log_error("Error: --parameters requires a value");
        std::exit(1);
      }
    } else {
      log_error("Unknown argument: " + arg);
      std::exit(1);
    }
  }

  // Track which arguments were actually provided
  bool nickname_provided = false;
  bool redis_host_provided = false;
  bool redis_port_provided = false;

  // Re-parse to track what was provided (simple approach)
  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    if (arg == "-n" || arg == "--nickname") {
      nickname_provided = true;
    } else if (arg == "-i" || arg == "--redis_host") {
      redis_host_provided = true;
    } else if (arg == "-p" || arg == "--redis_port") {
      redis_port_provided = true;
    }
  }

  // Check minimum required arguments (matching Python validation)
  int provided_args = 0;
  if (nickname_provided)
    provided_args++;
  if (redis_host_provided)
    provided_args++;
  if (redis_port_provided)
    provided_args++;

  if (provided_args < 2) {
    log_error("Arguments passed: " + std::to_string(provided_args));
    log_error("Please check the arguments passed. At least nickname and "
              "redis_host are typically required.");
    std::exit(1);
  }

  // Store fallback parameters for later use in initializeParameters
  if (!fallback_parameters.empty()) {
    auto param_map = parseJsonToMap(fallback_parameters);
    parameters_.insert(param_map.begin(), param_map.end());
  }
}

bool BRANDNode::validateParameters() {
  // Check for required streams
  if (parameters_.count("input_streams") == 0 ||
      parameters_.count("output_streams") == 0) {
    log_warning("No input or output streams defined in node parameters - using "
                "defaults");
    // Set default empty streams
    parameters_["input_streams"] = "{}";
    parameters_["output_streams"] = "{}";
  }

  return true;
}

} // namespace brand
