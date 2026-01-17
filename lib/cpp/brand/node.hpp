#ifndef BRAND_NODE_HPP
#define BRAND_NODE_HPP

#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <msgpack.hpp>

// Brand libraries
extern "C" {
#include "../../hiredis/hiredis.h"
#include "../../nxjson/nxjson.h"
#include "../../utilityFunctions/constants.h"
#include "../../utilityFunctions/utilityFunctions.h"
}

namespace brand {

struct Header {
  // C++ member variables matching the Python keys
  int64_t ts;
  int64_t seq;
  std::string producer_gid;
  std::string node;
  std::map<std::string, std::string> parents;

  // This macro enables automatic serialization and deserialization.
  // The names must match the member variables exactly.
  MSGPACK_DEFINE_MAP(ts, seq, producer_gid, node, parents);
};

struct StreamEntry {
  std::string id;
  std::map<std::string, msgpack::type::variant> fields;
};

class BRANDNode {
public:
  BRANDNode();
  virtual ~BRANDNode();

  // Initialize the node with command line arguments
  bool initialize(int argc, char *argv[]);

  // Main run loop
  void run();

  // Virtual work method to be implemented by derived classes
  virtual void work() = 0;

  // Virtual cleanup method for derived classes
  virtual void cleanup() {}

  // Redis stream operations
  void publish(const std::string &stream,
               const std::map<std::string, msgpack::type::variant> &data,
               const std::map<std::string, std::string> &parents = {});

  // Read methods matching Python interface
  std::map<
      std::string,
      std::pair<std::vector<std::string>,
                std::map<std::string, std::vector<msgpack::type::variant>>>>
  read(const std::vector<std::string> &streams, int count = 1,
       int block_ms = 0);
  std::pair<std::vector<std::string>,
            std::map<std::string, std::vector<msgpack::type::variant>>>
  read(const std::string &stream, int count = 1, int block_ms = 0);

  std::vector<StreamEntry> read_latest(const std::string &stream,
                                       int count = 1);

  // Removed read_one/read_n in favor of generic read

  // Additional utility methods matching Python
  void get_latest_id_per_stream(const std::vector<std::string> &streams);
  bool is_shutdown_requested() const { return shutdown_requested_; }
  int64_t get_timestamp() { return getTimestampNs(); }
  int next_seq() { return ++seq_; }

  // Parameter management
  std::vector<std::map<std::string, std::string>>
  getParametersFromSupergraph(bool complete_supergraph = false);

  // Logging
  void log(const std::string &level, const std::string &message);
  void log_info(const std::string &message) { log("INFO", message); }
  void log_error(const std::string &message) { log("ERROR", message); }
  void log_warning(const std::string &message) { log("WARNING", message); }
  void log_debug(const std::string &message) { log("DEBUG", message); }

  // Getters
  const std::string &getName() const { return name_; }
  const std::map<std::string, std::string> &getParameters() const {
    return parameters_;
  }

  // Signal handling
  static void signalHandler(int sig);

protected:
  // Update parameters from supergraph
  void updateParameters();

  // Setup logging (matching Python interface)
  void setup_logging(const std::string &log_level = "INFO");
  void add_redis_logging(const std::string &log_level = "INFO");

  // Connect to Redis
  bool connectToRedis(const std::string &host, int port,
                      const std::string &socket = "");

  // Initialize parameters
  void initializeParameters(const std::string &fallback_params = "");

  // Generate unique sequence number (deprecated, use next_seq)
  int nextSeq() { return ++seq_; }

  // Get current timestamp in nanoseconds
  int64_t getTimestampNs();

  // JSON parsing helpers
  std::map<std::string, std::string>
  parseJsonToMap(const std::string &json_str);
  std::string mapToJson(const std::map<std::string, std::string> &map);

private:
  // Member variables
  std::string name_;
  std::string redis_host_;
  int redis_port_;
  std::string redis_socket_;
  std::string producer_gid_hex_;
  std::string supergraph_id_;
  std::map<std::string, std::string> parameters_;
  std::map<std::string, std::string> cursors_;

  redisContext *redis_context_;
  int seq_;
  bool shutdown_requested_;

  // Static instance for signal handling
  static BRANDNode *instance_;

  // Helper methods
  void terminate(int sig);
  void handle_exception(const std::string &error);
  void handleException(const std::string &error) {
    handle_exception(error);
  } // legacy
  std::string generateUUID();
  void parseArguments(int argc, char *argv[]);
  bool validateParameters();

  // Disable copy constructor and assignment
  BRANDNode(const BRANDNode &) = delete;
  BRANDNode &operator=(const BRANDNode &) = delete;
};

} // namespace brand

#endif // BRAND_NODE_HPP
