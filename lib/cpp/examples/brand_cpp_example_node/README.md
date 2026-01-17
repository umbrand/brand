# C++ Example Node

Build:
- `make`

If the build fails with `msgpack.hpp: No such file or directory`, install msgpack:
- `sudo apt-get install libmsgpack-dev` (or make sure `pkg-config msgpack` works)

Run (example):
- start supervisor
- `./cpp_example_node.bin -n cpp_example_node -i 127.0.0.1 -p 6379`

The node publishes to the `cpp_example_node` stream with a `_hdr` and `data`
msgpack payload, including a small integer array.
