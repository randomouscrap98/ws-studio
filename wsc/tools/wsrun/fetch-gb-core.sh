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

# SameBoy emulates Game Boy key contact bounce by default. Bounce holds a
# released key for a pseudo-randomised number of frames, so an input edge can
# reach the emulated program one or more game ticks late. wsrun applies the
# input script per retro_run, so that would make the GB and WSC input phases
# differ (the WSC core has no bounce). The differential oracle needs input
# changes on an exact tick, so disable bounce in the libretro frontend. This
# is a local test-harness patch on top of the pinned commit above; it does not
# change emulation timing or anything except key readback.
LIBRETRO_C="$SRC/libretro/libretro.c"
if ! grep -q 'GB_set_emulate_joypad_bouncing' "$LIBRETRO_C"; then
    python3 - "$LIBRETRO_C" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
old = """        init_for_current_model(i);
        GB_load_rom_from_buffer(&gameboy[i], content_data, content_size);
    }"""
new = """        init_for_current_model(i);
        GB_load_rom_from_buffer(&gameboy[i], content_data, content_size);
        GB_set_emulate_joypad_bouncing(&gameboy[i], false);
    }"""
if text.count(old) != 2:
    raise SystemExit("fetch-gb-core: expected 2 load sites in libretro.c")
path.write_text(text.replace(old, new))
PY
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
