# C++ Brand Nodes

This directory contains the C++ implementation of Brand nodes. The C++ API
mirrors the Python node API but uses msgpack payloads so data can be read by
Python (and other languages) without extra conversions.
To keep user code clean, use `brand::MsgpackBuilder` and `brand::MsgpackView`
from `brand/msgpack_helpers.hpp`.

Why helpers: msgpack is typed (integers, floats, strings, arrays, maps), and in
C++ those types are represented as `msgpack::type::variant` plus nested map or
multimap structures. The helpers hide those details so node code looks closer
to Python dict usage while still preserving msgpack types.

## Key Concepts

- `brand::BRANDNode` provides `initialize()`, `run()`, and `publish()`.
- `publish()` writes two msgpack fields into a Redis Stream:
  - `_hdr`: header metadata (timestamp, sequence, node name, parents)
  - `data`: your payload map
- Parent node metadata is passed via the `parents` argument to `publish()`.

## Writing (C++ -> Redis)

```cpp
#include "brand/msgpack_helpers.hpp"
#include "brand/node.hpp"

class MyNode : public brand::BRANDNode {
public:
  void work() override {
    brand::MsgpackBuilder builder;
    builder.set("count", static_cast<int64_t>(count_++));
    builder.set_list("values", std::vector<int64_t>{1, 2, 3});
    builder.set("label", "example");

    std::map<std::string, std::string> parents = {{"upstream_node", "0-0"}};
    publish("my_stream", builder.data(), parents);
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

`read_latest()` returns `StreamEntry` objects with a `fields` map. Use
`MsgpackView` to access values without worrying about map vs multimap:

```cpp
auto entries = node.read_latest("my_stream", 1);
  if (!entries.empty()) {
    const auto &fields = entries[0].fields;
    auto data_it = fields.find("data");
    if (data_it != fields.end()) {
      brand::MsgpackView view(data_it->second);
      int64_t count = 0;
      if (view.get_int64("count", &count)) {
        // Use count...
      }
    }
  }
}
```

Notes:
- `_hdr` is msgpack and is available via `fields["_hdr"]`.
- `MsgpackView` handles map vs multimap differences internally.

## Example Node

See `examples/brand_cpp_example_node/` for a working example node that publishes
msgpack payloads and parent metadata.
