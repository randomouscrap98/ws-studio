#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
export WONDERFUL_TOOLCHAIN="${WONDERFUL_TOOLCHAIN:-/opt/wonderful}"
source "$WONDERFUL_TOOLCHAIN/bin/wf-env"

make -C "$repo/wsc/tools/wsrun"

echo "== GBVM engine hardware inventory =="
python3 "$here/inventory.py"

echo
echo "== Trial build of every engine .c =="
python3 "$here/trial_build.py"

echo
echo "== libws vblank interrupt under wsrun =="
python3 "$here/vblank_check.py"
