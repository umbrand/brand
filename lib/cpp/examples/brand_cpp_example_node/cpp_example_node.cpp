// C++ example node that publishes msgpack data to Redis Streams.
// Msgpack is used under the hood for the "_hdr" header and "data" payload.
#include <unistd.h>

#include "brand/msgpack_helpers.hpp"
#include "brand/node.hpp"

class CppExampleNode : public brand::BRANDNode {
public:
  void work() override {
    // Build the payload using helper setters (like Python dict usage).
    brand::MsgpackBuilder builder;
    builder.set("counter", static_cast<int64_t>(counter_++));
    builder.set_list("values", std::vector<int64_t>{1, 2, 3, 4});
    builder.set("message", "hello from C++ example node");

    // Parent node metadata is stored in the header (_hdr.parents).
    std::map<std::string, std::string> parents = {{"example_parent", "0-0"}};
    publish("cpp_example_node", builder.data(), parents);

    // Example read-back: read the latest entry and inspect fields via helpers.
    auto entries = read_latest("cpp_example_node", 1);
    if (!entries.empty()) {
      auto it = entries[0].fields.find("data");
      if (it != entries[0].fields.end()) {
        brand::MsgpackView view(it->second);
        int64_t last_counter = 0;
        if (view.get_int64("counter", &last_counter)) {
          log_debug("Last counter: " + std::to_string(last_counter));
        }
      }
    }

    usleep(100000); // 100 ms
  }

private:
  int64_t counter_ = 0;
};

int main(int argc, char *argv[]) {
  CppExampleNode node;
  if (!node.initialize(argc, argv)) {
    return 1;
  }

  node.run();
  return 0;
}
