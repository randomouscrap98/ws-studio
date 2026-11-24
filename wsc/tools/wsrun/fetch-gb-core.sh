#!/usr/bin/env bash
# Fetch and build the pinned SameBoy Game Boy libretro core.
set -euo pipefail

# Pinned core commit (https://github.com/libretro/SameBoy).
PINNED_COMMIT=aa158a889a48b538a0302873704a34577c8eb67d
CORE_REPO=https://github.com/libretro/SameBoy.git

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
BUILD="$ROOT/wsc/build"
SRC="$BUILD/sameboy"
DEST="$BUILD/sameboy_libretro.so"
SRC_SO="$SRC/libretro/sameboy_libretro.so"

mkdir -p "$BUILD"

if [ ! -d "$SRC/.git" ]; then
    if [ -e "$SRC" ]; then
        echo "error: $SRC exists but is not a git checkout" >&2
        exit 1
    fi
    git clone "$CORE_REPO" "$SRC"
fi

if ! git -C "$SRC" cat-file -e "$PINNED_COMMIT^{commit}" 2>/dev/null; then
    git -C "$SRC" fetch origin
fi

if [ "$(git -C "$SRC" rev-parse HEAD)" != "$PINNED_COMMIT" ]; then
    git -C "$SRC" checkout --detach "$PINNED_COMMIT"
fi

# SameBoy's boot-ROM Makefile rules call hexdump(1), which is not installed in
# the container. The shim implements just the one -e format those rules use.
BIN="$BUILD/gb-bin"
mkdir -p "$BIN"
ln -sf "$SCRIPT_DIR/sameboy-hexdump" "$BIN/hexdump"

# make is cheap when everything is up to date, and rebuilds only what changed.
PATH="$BIN:$PATH" make -C "$SRC/libretro" -j"$(nproc)"

if [ ! -f "$DEST" ] || ! cmp -s "$SRC_SO" "$DEST"; then
    cp "$SRC_SO" "$DEST"
fi
