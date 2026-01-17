#include "brand/node.hpp"

class MsgpackWriterNode : public brand::BRANDNode {
public:
  void work() override {}
};

int main(int argc, char *argv[]) {
  MsgpackWriterNode node;
  if (!node.initialize(argc, argv)) {
    return 1;
  }

  std::map<std::string, msgpack::type::variant> data;
  data["counter"] = static_cast<int64_t>(42);
  std::vector<msgpack::type::variant> values_variant_vec;
  for (int64_t val : std::vector<int64_t>{10, 20, 30}) {
    values_variant_vec.push_back(val);
  }
  data["values"] = values_variant_vec;
  data["gain"] = 0.5;
  data["label"] = std::string("cpp_msgpack_test");

  std::map<std::string, std::string> parents = {{"parent_node", "0-0"}};
  node.publish("cpp_msgpack_test", data, parents);

  return 0;
}
