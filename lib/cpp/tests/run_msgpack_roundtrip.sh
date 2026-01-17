#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PORT=6380

REDIS_SERVER_BIN="${REDIS_SERVER_BIN:-}"
REDIS_CLI_BIN="${REDIS_CLI_BIN:-}"

if [[ -z "$REDIS_SERVER_BIN" ]]; then
  if [[ -x "$ROOT/bin/redis-server" ]]; then
    REDIS_SERVER_BIN="$ROOT/bin/redis-server"
  else
    REDIS_SERVER_BIN="$(command -v redis-server || true)"
  fi
fi

if [[ -z "$REDIS_CLI_BIN" ]]; then
  if [[ -x "$ROOT/bin/redis-cli" ]]; then
    REDIS_CLI_BIN="$ROOT/bin/redis-cli"
  else
    REDIS_CLI_BIN="$(command -v redis-cli || true)"
  fi
fi

if [[ -z "$REDIS_SERVER_BIN" || -z "$REDIS_CLI_BIN" ]]; then
  echo "redis-server/redis-cli not found. Build brand or install Redis."
  exit 1
fi

if [[ ! -f "./msgpack_roundtrip_writer.bin" ]]; then
  echo "Build the writer first: make"
  exit 1
fi

DATA_DIR="$(mktemp -d)"

cleanup() {
  "$REDIS_CLI_BIN" -p "$PORT" shutdown >/dev/null 2>&1 || true
  rm -rf "$DATA_DIR"
}
trap cleanup EXIT

"$REDIS_SERVER_BIN" --port "$PORT" --save "" --appendonly no --dir "$DATA_DIR" --daemonize yes

./msgpack_roundtrip_writer.bin -n cpp_msgpack_writer -i 127.0.0.1 -p "$PORT"
python msgpack_roundtrip_reader.py
