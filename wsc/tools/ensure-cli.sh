#!/usr/bin/env bash
# Sourced helper: make sure the GB Studio CLI bundle exists and is current.
# Used by wsc/export/run.sh and wsc/tools/build_product.sh.

ensure_cli() {
    local repo=$1
    local cli=$2

    if ! command -v node >/dev/null 2>&1; then
        echo "error: node is required" >&2
        exit 1
    fi
    # package.json declares yarn@4 (for corepack) and .yarnrc points at a Yarn
    # 1 binary that is not committed. Use the system Yarn 1.22.22 with the
    # tracked v1 lockfile instead. --ignore-scripts skips Electron's binary
    # download and any native builds; --pure-lockfile is needed because the
    # fork's package.json has entries the committed lockfile does not.
    if [[ ! -d "$repo/node_modules" || ! -x "$repo/node_modules/.bin/webpack" ]]; then
        if ! command -v yarn >/dev/null 2>&1; then
            echo "error: yarn 1.x is required to install dependencies" >&2
            exit 1
        fi
        echo "== installing dependencies =="
        (cd "$repo" && SKIP_YARN_COREPACK_CHECK=1 \
            YARN_IGNORE_PATH=1 \
            ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
            yarn install --pure-lockfile --ignore-scripts --non-interactive)
    fi

    local needs_build=0
    if [[ ! -f "$cli" ]]; then
        needs_build=1
    elif [[ -n "$(find "$repo/src" "$repo/package.json" "$repo/yarn.lock" \
            -newer "$cli" -print -quit)" ]]; then
        needs_build=1
    fi
    if ((needs_build)); then
        echo "== building CLI =="
        # The tsc type check fails on this Node/@types combination, but the
        # CLI bundles fine with webpack. This is the same env the repo's
        # start:cli script uses.
        (cd "$repo" && NO_TYPE_CHECKING=1 npm run make:cli)
    fi
}
