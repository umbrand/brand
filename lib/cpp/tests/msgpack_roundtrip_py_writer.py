import msgpack
import redis
import time


def main() -> None:
    r = redis.Redis(host="127.0.0.1", port=6381, decode_responses=False)
    stream = b"py_msgpack_test"

    hdr = {
        "ts": time.time_ns(),
        "seq": 1,
        "producer_gid": "py_writer",
        "node": "py_msgpack_writer",
        "parents": {"py_parent": "0-0"},
    }
    data = {
        "int_val": 123,
        "float_val": 1.25,
        "str_val": "hello",
        "bool_val": True,
        "list_val": [1, 2, 3],
        "map_val": {"a": 1, "b": 2},
    }

    r.xadd(
        stream,
        {
            b"_hdr": msgpack.packb(hdr, use_bin_type=True),
            b"data": msgpack.packb(data, use_bin_type=True),
        },
    )


if __name__ == "__main__":
    main()
