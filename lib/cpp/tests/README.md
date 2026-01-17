# Msgpack C++ Roundtrip Tests

Build:
- `make`

Run (standalone Redis on port 6380):
- `./run_msgpack_roundtrip.sh`

Run Python writer -> C++ reader (standalone Redis on port 6381):
- `./run_msgpack_py_to_cpp.sh`

Notes:
- If the build fails with `msgpack.hpp: No such file or directory`, install msgpack:
  `sudo apt-get install libmsgpack-dev` (or make sure `pkg-config msgpack` works).
- The Python tests expect the `rt` environment (redis + msgpack).
- `run_msgpack_roundtrip.sh` validates C++ -> Python:
  - C++ writes `cpp_msgpack_test` with `_hdr` and `data` packed via msgpack.
  - Python reads `_hdr` and `data` and asserts types/values (ints, list, strings).
- `run_msgpack_py_to_cpp.sh` validates Python -> C++:
  - Python writes `py_msgpack_test` with mixed types (int, float, bool, string,
    list, nested map) plus `_hdr.parents`.
  - C++ reads latest entry and validates each field and `_hdr.parents`.
