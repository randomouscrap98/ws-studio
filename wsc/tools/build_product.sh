#!/usr/bin/env bash
## Build a WonderSwan Color product ROM through the GB Studio CLI.
#
# Usage: wsc/tools/build_product.sh PROJECT.gbsproj OUT.wsc [STATE_DIR]
#
# STATE_DIR holds the ejected export, generated converter output and build
# tree. It defaults to the CLI's per-project directory under wsc/build/.
# Set WONDERFUL_TOOLCHAIN to the Wonderful install (default /opt/wonderful).
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 PROJECT.gbsproj OUT.wsc [STATE_DIR]" >&2
    exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
project="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
destination="$2"
state="${3:-${WSC_PRODUCT_STATE:-}}"
cli="$repo/out/cli/gb-studio-cli.js"

if [[ ! -f "$project" ]]; then
    echo "error: project file not found: $project" >&2
    exit 1
fi
if [[ -n "$state" ]]; then
    state="$(mkdir -p "$state" && cd "$state" && pwd)"
fi

# shellcheck source=ensure-cli.sh
source "$here/ensure-cli.sh"
ensure_cli "$repo" "$cli"

tmp="$repo/wsc/build/cli-tmp"
mkdir -p "$tmp" "$(dirname "$destination")"

# ELECTRON_OVERRIDE_DIST_PATH stops electron/index.js downloading the Electron
# binary when the CLI imports `app`; no Electron process is ever started.
if [[ -n "$state" ]]; then
    WSC_PRODUCT_STATE="$state" \
    TMPDIR="$tmp" \
    ELECTRON_OVERRIDE_DIST_PATH="$repo/node_modules/electron/dist" \
    ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
        node "$cli" make:wsc "$project" "$destination"
else
    TMPDIR="$tmp" \
    ELECTRON_OVERRIDE_DIST_PATH="$repo/node_modules/electron/dist" \
    ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
        node "$cli" make:wsc "$project" "$destination"
fi
