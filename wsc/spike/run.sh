#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
export WONDERFUL_TOOLCHAIN="${WONDERFUL_TOOLCHAIN:-/opt/wonderful}"

make -C "$repo/wsc/tools/wsrun"
exec python3 "$here/run.py" "$@"
