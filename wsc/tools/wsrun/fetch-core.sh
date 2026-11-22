#!/usr/bin/env bash
# Fetch and build the pinned beetle-wswan libretro core.
set -euo pipefail

# Pinned core commit (https://github.com/libretro/beetle-wswan-libretro).
PINNED_COMMIT=4b01295838ea89e3f1355bbe4cb5cf98aa6108cd
CORE_REPO=https://github.com/libretro/beetle-wswan-libretro.git

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
BUILD="$ROOT/wsc/build"
SRC="$BUILD/beetle-wswan"
DEST="$BUILD/mednafen_wswan_libretro.so"
SRC_SO="$SRC/mednafen_wswan_libretro.so"

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

# make is cheap when everything is up to date, and rebuilds only what changed.
make -C "$SRC" -j"$(nproc)"

if [ ! -f "$DEST" ] || ! cmp -s "$SRC_SO" "$DEST"; then
    cp "$SRC_SO" "$DEST"
fi
