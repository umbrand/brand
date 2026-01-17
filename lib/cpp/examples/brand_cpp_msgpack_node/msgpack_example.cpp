// C++ example node that publishes msgpack data to Redis Streams.
// The payload mirrors the Python node style: a msgpack-packed "data" map plus
// an "_hdr" header with timestamps and parent node metadata.
#include <unistd.h>

#include "brand/node.hpp"

class CppExampleNode : public brand::BRANDNode {
public:
  void work() override {
    // Build the payload as a map of msgpack variants (like Python dict).
    std::map<std::string, msgpack::type::variant> data;
    data["counter"] = static_cast<int64_t>(counter_++);
    // Arrays must be stored as a vector<variant> for msgpack compatibility.
    std::vector<msgpack::type::variant> values;
    for (int64_t value : std::vector<int64_t>{1, 2, 3, 4}) {
      values.push_back(value);
    }
    data["values"] = values;
    data["message"] = std::string("hello from C++ example node");

    // Parent node metadata is stored in the header (_hdr.parents).
    std::map<std::string, std::string> parents = {{"example_parent", "0-0"}};
    // Publish to Redis using msgpack for both _hdr and data fields.
    publish("cpp_example_node", data, parents);

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
