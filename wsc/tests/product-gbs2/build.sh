#!/usr/bin/env bash
# Build the product ROM for a gbs2 test project whose title "New Game" branch
# starts Sample Town. The variant only changes project data; the product build
# itself knows nothing about the scene.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wsc="$(cd "$here/../.." && pwd)"
repo="$(cd "$wsc/.." && pwd)"
state="$wsc/build/product/tests/product-gbs2"
project="$state/project"

rm -rf "$project"
mkdir -p "$state"
cp -a "$repo/appData/templates/gbs2" "$project"

python3 - "$project" <<'PY'
import json
import sys
from pathlib import Path

project = Path(sys.argv[1])
scenes = project / "project" / "scenes"


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# Sample Town's scene id from the project itself.
sample_id = None
for path in scenes.rglob("scene.gbsres"):
    data = load(path)
    if data.get("symbol") == "scene_sample_town":
        sample_id = data["id"]
        break
if sample_id is None:
    raise SystemExit("scene_sample_town not found")

# Point the title's New Game switch at Sample Town at tile (10, 10).
title = scenes / "ui" / "title_screen" / "scene.gbsres"
data = load(title)


def rewrite(node):
    changed = False
    if isinstance(node, dict):
        if (node.get("command") == "EVENT_SWITCH_SCENE" and
                node.get("args", {}).get("sceneId") ==
                "896aee79-9b53-4ac1-b41f-b1ddf96da7ff"):
            node["args"]["sceneId"] = sample_id
            node["args"]["x"] = {"type": "number", "value": 10}
            node["args"]["y"] = {"type": "number", "value": 10}
            changed = True
        for value in node.values():
            changed = rewrite(value) or changed
    elif isinstance(node, list):
        for value in node:
            changed = rewrite(value) or changed
    return changed


if not rewrite(data):
    raise SystemExit("title New Game scene switch not found")
title.write_text(json.dumps(data, indent=2) + "\n")
PY

"$wsc/tools/build_product.sh" \
    "$project/project.gbsproj" "$state/output.wsc" "$state"

python3 - "$state/build/product.elf" "$state/ram.json" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

elf, ram_out = sys.argv[1:]
toolchain = os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
nm = Path(toolchain) / "toolchain" / "gcc-ia16-elf" / "bin" / "ia16-elf-nm"
output = subprocess.check_output([str(nm), elf], text=True)
symbols = {}
for line in output.splitlines():
    fields = line.split()
    if len(fields) >= 3:
        symbols[fields[-1]] = int(fields[0], 16)
value = symbols["scene_sample_town"]
linear = value & 0xFFFFF
pointer = ((linear >> 4) << 16) | (linear & 0x0F)
checks = [
    {"symbol": "current_scene", "offset": 2, "size": 4,
     "equals": "0x{:08x}".format(pointer)},
    {"symbol": "actors", "offset": 2, "size": 2, "equals": 2560},
    {"symbol": "actors", "offset": 4, "size": 2, "equals": 2560},
]
Path(ram_out).write_text(json.dumps(checks, indent=2) + "\n")
PY
