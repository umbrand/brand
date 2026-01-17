# C++ Brand Nodes

This directory contains the C++ implementation of Brand nodes. The C++ API
mirrors the Python node API but uses `msgpack::type::variant` for payloads so
data can be read by Python (and other languages) without extra conversions.

## Key Concepts

- `brand::BRANDNode` provides `initialize()`, `run()`, and `publish()`.
- `publish()` writes two msgpack fields into a Redis Stream:
  - `_hdr`: header metadata (timestamp, sequence, node name, parents)
  - `data`: your payload map
- Parent node metadata is passed via the `parents` argument to `publish()`.

## Writing (C++ -> Redis)

```cpp
#include "brand/node.hpp"

class MyNode : public brand::BRANDNode {
public:
  void work() override {
    std::map<std::string, msgpack::type::variant> data;
    data["count"] = static_cast<int64_t>(count_++);

    std::vector<msgpack::type::variant> values;
    for (int64_t v : std::vector<int64_t>{1, 2, 3}) {
      values.push_back(v);
    }
    data["values"] = values;
    data["label"] = std::string("example");

    std::map<std::string, std::string> parents = {{"upstream_node", "0-0"}};
    publish("my_stream", data, parents);
  }

private:
  int64_t count_ = 0;
};
```

Notes:
- Use `std::vector<msgpack::type::variant>` for arrays.
- Use `std::map<std::string, msgpack::type::variant>` for payload maps.
- `publish()` packs msgpack into Redis Streams in a Python-compatible format.

## Reading (Redis -> C++)

`read_latest()` returns `StreamEntry` objects with a `fields` map:

```cpp
auto entries = node.read_latest("my_stream", 1);
if (!entries.empty()) {
  const auto &fields = entries[0].fields;
  auto data_it = fields.find("data");
  if (data_it != fields.end()) {
    // msgpack::type::variant can hold maps or multimaps (implementation detail)
    const auto *data_map =
        boost::get<std::map<msgpack::type::variant, msgpack::type::variant>>(
            &data_it->second);
    const auto *data_multimap =
        boost::get<std::multimap<msgpack::type::variant,
                                 msgpack::type::variant>>(
            &data_it->second);
    // Extract values from the map/multimap as needed.
  }
}
```

Notes:
- Msgpack dictionaries may deserialize to either `map` or `multimap` variants.
- `_hdr` is also msgpack and is available via `fields["_hdr"]`.

## Example Node

See `examples/brand_cpp_msgpack_node/` for a working example node that publishes
msgpack payloads and parent metadata.
