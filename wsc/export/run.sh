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

if ! command -v node >/dev/null 2>&1; then
    echo "error: node is required" >&2
    exit 1
fi
if ! command -v yarn >/dev/null 2>&1; then
    echo "error: yarn 1.x is required" >&2
    exit 1
fi

# package.json declares yarn@4 (for corepack) and .yarnrc points at a Yarn 1
# binary that is not committed. Use the system Yarn 1.22.22 with the tracked
# v1 lockfile instead. --ignore-scripts skips Electron's binary download and
# any native builds; --pure-lockfile is needed because the fork's package.json
# has entries the committed lockfile does not.
if [[ ! -d node_modules || ! -x node_modules/.bin/webpack ]]; then
    echo "== installing dependencies =="
    SKIP_YARN_COREPACK_CHECK=1 \
    YARN_IGNORE_PATH=1 \
    ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
        yarn install --pure-lockfile --ignore-scripts --non-interactive
fi

needs_build=0
if [[ ! -f "$cli" ]]; then
    needs_build=1
elif [[ -n "$(find "$repo/src" "$repo/package.json" "$repo/yarn.lock" \
        -newer "$cli" -print -quit)" ]]; then
    needs_build=1
fi
if ((needs_build)); then
    echo "== building CLI =="
    # The tsc type check fails on this Node/@types combination, but the CLI
    # bundles fine with webpack. This is the same env the repo's start:cli
    # script uses.
    NO_TYPE_CHECKING=1 npm run make:cli
fi

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
