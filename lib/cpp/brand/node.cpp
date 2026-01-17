#include "node.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <random>
#include <signal.h>
#include <time.h>
#include <unistd.h>

namespace brand {

// Static member initialization
BRANDNode *BRANDNode::instance_ = nullptr;

BRANDNode::BRANDNode()
    : name_(),
      redis_host_(),
      redis_port_(6379),
      redis_socket_(),
      producer_gid_hex_(),
      supergraph_id_("0-0"),
      parameters_(),
      cursors_(),
      redis_context_(nullptr),
      seq_(0),
      shutdown_requested_(false) {
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

    // Setup basic console logging first (matching Python)
    setup_logging();

    if (!connectToRedis(redis_host_, redis_port_, redis_socket_)) {
      log_error("Failed to connect to Redis");
      return false;
    }

    // Initialize parameters (will be parsed from command line)
    initializeParameters();

    // Now that we have Redis and parameters, add Redis logging (matching
    // Python)
    std::string log_level =
        parameters_.count("log") ? parameters_["log"] : "INFO";
    add_redis_logging(log_level);

    // Setup signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);

    // Get latest ID for each input stream (matching Python)
    if (parameters_.count("input_streams")) {
      // Parse input stream names from parameters - simplified for now
      std::vector<std::string> input_streams;
      // TODO: Parse JSON input_streams to get actual stream names
      get_latest_id_per_stream(input_streams);
    }

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
    handle_exception(std::string("Initialization failed: ") + e.what());
    return false;
  }
}

void BRANDNode::run() {
  log_info("Starting main run loop");

  while (!shutdown_requested_) {
    try {
      work();
      updateParameters();
    } catch (const std::exception &e) {
      handle_exception(std::string("Error in run loop: ") + e.what());
      break;
    }
  }

  // Perform graceful shutdown outside of signal handler context
  if (shutdown_requested_) {
    terminate(0);
  }
}

void BRANDNode::publish(
    const std::string &stream,
    const std::map<std::string, msgpack::type::variant> &data,
    const std::map<std::string, std::string> &parents) {
  // Check if shutdown is requested (matching Python)
  if (shutdown_requested_) {
    return;
  }

  if (!redis_context_) {
    log_error("Redis context not available for publishing");
    return;
  }

  // Create header (match Python msgpack types)
  std::map<std::string, msgpack::type::variant> header = {
      {"ts", static_cast<int64_t>(get_timestamp())},
      {"seq", static_cast<int64_t>(next_seq())},
      {"producer_gid", producer_gid_hex_},
      {"node", name_}};

  if (!parents.empty()) {
    std::map<msgpack::type::variant, msgpack::type::variant> parents_variant_map;
    for (const auto &pair : parents) {
      parents_variant_map[msgpack::type::variant(pair.first)] =
          msgpack::type::variant(pair.second);
    }
    header["parents"] = parents_variant_map;
  }

  // Build argv for binary-safe publish using msgpack for values
  std::vector<std::string> string_args_storage;
  std::vector<const char *> argv;
  std::vector<size_t> argvlen;
  std::vector<std::unique_ptr<msgpack::sbuffer>> packed_value_buffers;

  // Prevent std::string reallocation from invalidating argv pointers.
  string_args_storage.reserve(5); // XADD, stream, *, _hdr, data
  argv.reserve(7);                // 5 strings + 2 msgpack values
  argvlen.reserve(7);

  auto push_arg = [&](const std::string &s) {
    string_args_storage.push_back(s);
    argv.push_back(string_args_storage.back().c_str());
    argvlen.push_back(string_args_storage.back().size());
  };

  // Command and base arguments
  push_arg("XADD");
  push_arg(stream);
  push_arg("*");

  // Header key/value
  push_arg("_hdr");
  {
    auto header_buffer = std::make_unique<msgpack::sbuffer>();
    // Pack the whole header map directly, similar to Python
    msgpack::pack(*header_buffer, header);
    argv.push_back(header_buffer->data());
    argvlen.push_back(header_buffer->size());
    packed_value_buffers.emplace_back(std::move(header_buffer));
  }

  // Data field: pack entire map once (similar to Python)
  push_arg("data");
  {
    auto data_buffer = std::make_unique<msgpack::sbuffer>();
    msgpack::pack(*data_buffer, data);
    argv.push_back(data_buffer->data());
    argvlen.push_back(data_buffer->size());
    packed_value_buffers.emplace_back(std::move(data_buffer));
  }

  redisReply *reply = (redisReply *)redisCommandArgv(
      redis_context_, (int)argv.size(), argv.data(), argvlen.data());

  if (reply) {
    if (reply->type == REDIS_REPLY_ERROR) {
      log_error("Redis publish error: " + std::string(reply->str));
    }
    freeReplyObject(reply);
  }
}

// removed read_one in favor of generic read

std::vector<StreamEntry> BRANDNode::read_latest(const std::string &stream,
                                                int count) {
  std::vector<StreamEntry> result;

  // Check if shutdown is requested (matching Python)
  if (shutdown_requested_) {
    return result;
  }

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
      stream_entry.id = std::string(entry->element[0]->str,
                                    entry->element[0]->len);

      // Parse fields
      redisReply *fields = entry->element[1];
      if (fields->type == REDIS_REPLY_ARRAY) {
        for (size_t j = 0; j + 1 < fields->elements; j += 2) {
          std::string key = std::string(fields->element[j]->str,
                                        fields->element[j]->len);
          redisReply *val = fields->element[j + 1];
          if (!val)
            continue;

          if (key == "_hdr" || key == "data") {
            const char *buf = val->str;
            size_t len = val->len;
            try {
              msgpack::object_handle oh = msgpack::unpack(buf, len);
              msgpack::object obj = oh.get();
              msgpack::type::variant v;
              obj.convert(v);
              stream_entry.fields[key] = v;
            } catch (const std::exception &e) {
              log_error("Failed to unpack " + key + ": " + e.what());
            }
          } else {
            msgpack::type::variant v;
            v = std::string(val->str ? std::string(val->str, val->len)
                                     : std::string());
            stream_entry.fields[key] = v;
          }
        }
      }

      result.push_back(stream_entry);
    }
  }

  freeReplyObject(reply);
  return result;
}

// removed read_n in favor of generic read

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
    // Set shutdown flag only; avoid heavy work in signal context
    instance_->shutdown_requested_ = true;
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

void BRANDNode::setup_logging(const std::string &log_level) {
  log_info("Logging setup completed with level: " + log_level);
}

void BRANDNode::add_redis_logging(const std::string &log_level) {
  log_info("Redis logging added with level: " + log_level);
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
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return static_cast<int64_t>(ts.tv_sec) * 1000000000LL + ts.tv_nsec;
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
  shutdown_requested_ = true;

  // Give a brief moment for ongoing operations to complete (matching Python)
  usleep(100000); // 0.1 seconds

  cleanup();

  // Post termination status to Redis (only if connection is still alive)
  if (redis_context_) {
    try {
      redisReply *reply = (redisReply *)redisCommand(
          redis_context_, "XADD %s * code %s status %s",
          (name_ + "_state").c_str(), "0", "done");

      if (reply) {
        freeReplyObject(reply);
      }
    } catch (...) {
      // Don't fail on Redis close errors, just log them
      log_debug("Error closing Redis connection during termination");
    }

    redisFree(redis_context_);
    redis_context_ = nullptr;
  }

  std::exit(0);
}

void BRANDNode::handle_exception(const std::string &error) {
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

void BRANDNode::get_latest_id_per_stream(
    const std::vector<std::string> &streams) {
  for (const auto &stream : streams) {
    try {
      // Get latest ID for stream using XINFO STREAM
      redisReply *reply = (redisReply *)redisCommand(
          redis_context_, "XINFO STREAM %s", stream.c_str());

      if (reply && reply->type == REDIS_REPLY_ARRAY) {
        // Parse XINFO response to get last-generated-id
        for (size_t i = 0; i < reply->elements; i += 2) {
          if (i + 1 < reply->elements &&
              strcmp(reply->element[i]->str, "last-generated-id") == 0) {
            cursors_[stream] = reply->element[i + 1]->str;
            break;
          }
        }
      }

      if (reply) {
        freeReplyObject(reply);
      }
    } catch (...) {
      log_warning("Error getting latest ID for stream " + stream);
      cursors_[stream] = "0-0";
    }
  }
}

// Overloaded read method for multiple streams (matching Python interface)
std::map<std::string,
         std::pair<std::vector<std::string>,
                   std::map<std::string, std::vector<msgpack::type::variant>>>>
BRANDNode::read(const std::vector<std::string> &streams, int count,
                int block_ms) {
  std::map<
      std::string,
      std::pair<std::vector<std::string>,
                std::map<std::string, std::vector<msgpack::type::variant>>>>
      result;

  // Initialize result with empty structures
  for (const auto &s : streams) {
    result[s] = std::make_pair(
        std::vector<std::string>(),
        std::map<std::string, std::vector<msgpack::type::variant>>());
  }

  // Check if shutdown is requested
  if (shutdown_requested_) {
    return result;
  }

  if (!redis_context_) {
    log_error("Redis context not available for reading");
    return result;
  }

  // Build XREAD command for all streams at once
  std::ostringstream cmd;
  cmd << "XREAD BLOCK " << block_ms << " COUNT " << count << " STREAMS";
  for (const auto &s : streams) {
    cmd << " " << s;
  }
  for (const auto &s : streams) {
    auto it = cursors_.find(s);
    cmd << " " << (it != cursors_.end() ? it->second : std::string("$"));
  }

  redisReply *reply =
      (redisReply *)redisCommand(redis_context_, cmd.str().c_str());
  if (!reply || reply->type != REDIS_REPLY_ARRAY || reply->elements == 0) {
    if (reply)
      freeReplyObject(reply);
    return result;
  }

  // Parse reply: array of [stream, [ [id, [k,v ...]], ... ]]
  for (size_t i = 0; i < reply->elements; ++i) {
    redisReply *stream_arr = reply->element[i];
    if (!stream_arr || stream_arr->type != REDIS_REPLY_ARRAY ||
        stream_arr->elements < 2)
      continue;

    std::string stream_name = std::string(stream_arr->element[0]->str,
                                          stream_arr->element[0]->len);
    redisReply *entries = stream_arr->element[1];
    if (!entries || entries->type != REDIS_REPLY_ARRAY)
      continue;

    auto &entry_ids = result[stream_name].first;
    auto &data_map = result[stream_name].second;

    for (size_t e = 0; e < entries->elements; ++e) {
      redisReply *entry = entries->element[e];
      if (!entry || entry->type != REDIS_REPLY_ARRAY || entry->elements < 2)
        continue;

      std::string entry_id =
          std::string(entry->element[0]->str, entry->element[0]->len);
      entry_ids.push_back(entry_id);
      cursors_[stream_name] = entry_id; // advance cursor

      redisReply *fields = entry->element[1];
      if (!fields || fields->type != REDIS_REPLY_ARRAY)
        continue;

      // Iterate field pairs
      for (size_t j = 0; j + 1 < fields->elements; j += 2) {
        std::string key = std::string(fields->element[j]->str,
                                      fields->element[j]->len);
        redisReply *val = fields->element[j + 1];
        if (!val)
          continue;

        if (key == "_hdr") {
          const char *buf = val->str;
          size_t len = val->len;
          try {
            msgpack::object_handle oh = msgpack::unpack(buf, len);
            msgpack::object obj = oh.get();
            msgpack::type::variant v;
            obj.convert(v);
            data_map["_hdr"].push_back(v);
          } catch (const std::exception &e) {
            log_error(std::string("Failed to unpack _hdr: ") + e.what());
          }
        } else if (key == "data") {
          const char *buf = val->str;
          size_t len = val->len;
          try {
            msgpack::object_handle oh = msgpack::unpack(buf, len);
            msgpack::object obj = oh.get();
            if (obj.type == msgpack::type::MAP) {
              for (uint32_t m = 0; m < obj.via.map.size; ++m) {
                const msgpack::object_kv &kv = obj.via.map.ptr[m];
                std::string dkey;
                kv.key.convert(dkey);
                msgpack::type::variant v;
                kv.val.convert(v);
                data_map[dkey].push_back(v);
              }
            } else {
              // If 'data' is not a map, store whole object as variant
              msgpack::type::variant v;
              obj.convert(v);
              data_map["data"].push_back(v);
            }
          } catch (const std::exception &e) {
            log_error(std::string("Failed to unpack data: ") + e.what());
          }
        } else {
          // Fallback: store raw string value
          msgpack::type::variant v;
          v = std::string(val->str ? std::string(val->str, val->len)
                                   : std::string());
          data_map[key].push_back(v);
        }
      }
    }
  }

  freeReplyObject(reply);
  return result;
}

// Overloaded read method for single stream (matching Python interface)
std::pair<std::vector<std::string>,
          std::map<std::string, std::vector<msgpack::type::variant>>>
BRANDNode::read(const std::string &stream, int count, int block_ms) {
  auto multi = read(std::vector<std::string>{stream}, count, block_ms);
  auto it = multi.find(stream);
  if (it != multi.end()) {
    return it->second;
  }
  return std::make_pair(
      std::vector<std::string>(),
      std::map<std::string, std::vector<msgpack::type::variant>>());
}

} // namespace brand
