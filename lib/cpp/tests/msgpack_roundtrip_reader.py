import sys

try:
    import msgpack
    import redis
except Exception as exc:
    print(f"Import error: {exc}")
    print("Make sure you are in the 'rt' environment with redis/msgpack installed.")
    sys.exit(1)


def main():
    r = redis.Redis(host="127.0.0.1", port=6380, decode_responses=False)
    stream = b"cpp_msgpack_test"

    entries = r.xrevrange(stream, count=1)
    if not entries:
        print("No entries found on cpp_msgpack_test")
        sys.exit(1)

    entry_id, fields = entries[0]
    hdr = msgpack.unpackb(fields[b"_hdr"], raw=False)
    data = msgpack.unpackb(fields[b"data"], raw=False)

    print("entry_id:", entry_id.decode())
    print("_hdr:", hdr)
    print("data:", data)

    assert hdr["node"]
    assert "parents" in hdr
    assert data["values"] == [10, 20, 30]
    assert data["counter"] == 42
    assert data["label"] == "cpp_msgpack_test"


if __name__ == "__main__":
    main()
