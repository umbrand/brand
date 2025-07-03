#ifndef BRAND_NODE_HPP
#define BRAND_NODE_HPP

#include <chrono>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

// Brand libraries
extern "C" {
#include "../../hiredis/hiredis.h"
#include "../../nxjson/nxjson.h"
#include "../../utilityFunctions/constants.h"
#include "../../utilityFunctions/utilityFunctions.h"
}

namespace brand {

struct StreamEntry {
  std::string id;
  std::map<std::string, std::string> fields;
};

struct StreamEntries {
  std::vector<std::string> entry_ids;
  std::map<std::string, std::vector<std::string>> data;
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
               const std::map<std::string, std::string> &data,
               const std::map<std::string, std::string> &parents = {});

  StreamEntry *read_one(const std::string &stream, int block_ms = 0);

  std::vector<StreamEntry> read_latest(const std::string &stream,
                                       int count = 1);

  StreamEntries *read_n(const std::string &stream, int n = 1000,
                        int block_ms = -1);

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

  // Setup logging
  void setupLogging(const std::string &log_level = "INFO");

  // Connect to Redis
  bool connectToRedis(const std::string &host, int port,
                      const std::string &socket = "");

  // Initialize parameters
  void initializeParameters(const std::string &fallback_params = "");

  // Generate unique sequence number
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

  // Static instance for signal handling
  static BRANDNode *instance_;

  // Helper methods
  void terminate(int sig);
  void handleException(const std::string &error);
  std::string generateUUID();
  void parseArguments(int argc, char *argv[]);
  bool validateParameters();

  // Disable copy constructor and assignment
  BRANDNode(const BRANDNode &) = delete;
  BRANDNode &operator=(const BRANDNode &) = delete;
};

} // namespace brand

#endif // BRAND_NODE_HPP
