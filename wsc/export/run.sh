#!/usr/bin/env bash
set -euo pipefail

# Build the GB Studio CLI (if needed) and export the gbs2 template's data.
# Output goes to wsc/build/export/ (gitignored). The export is ~1.9 MB of
# files, so it is deliberately not committed.
#
# Usage: wsc/export/run.sh [destination]
#   TEMPLATE=/path/to/project.gbsproj overrides the project.

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
dest="${1:-$repo/wsc/build/export}"
template="${TEMPLATE:-$repo/appData/templates/gbs2/project.gbsproj}"
cli="$repo/out/cli/gb-studio-cli.js"

cd "$repo"

# shellcheck source=ensure-cli.sh
source "$here/../tools/ensure-cli.sh"
ensure_cli "$repo" "$cli"

if [[ ! -f "$template" ]]; then
    echo "error: template not found: $template" >&2
    exit 1
fi

tmp="$repo/wsc/build/cli-tmp"
echo "== exporting $(basename "$template") =="
rm -rf "$dest" "$tmp"
mkdir -p "$dest" "$tmp"
# ELECTRON_OVERRIDE_DIST_PATH stops electron/index.js downloading the Electron
# binary when the CLI imports `app`; no Electron process is ever started.
TMPDIR="$tmp" \
ELECTRON_OVERRIDE_DIST_PATH="$repo/node_modules/electron/dist" \
ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
    node "$cli" --verbose export "$template" "$dest"

file_count="$(find "$dest" -type f | wc -l | tr -d ' ')"
byte_count="$(find "$dest" -type f -printf '%s\n' | awk '{ total += $1 } END { print total + 0 }')"
echo "exported files: $file_count ($byte_count bytes)"
