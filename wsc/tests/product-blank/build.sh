#!/usr/bin/env bash
# Build a product ROM from the blank template with one default empty scene.
# appData/templates/blank has no scenes and GB Studio's own export refuses it,
# so the test adds the first scene a user would create. The product build
# itself is generic and only reads the exported data.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wsc="$(cd "$here/../.." && pwd)"
repo="$(cd "$wsc/.." && pwd)"
state="$wsc/build/product/tests/product-blank"
project="$state/project"
scene_id="c30b1a9c-5e2f-4c7e-9a41-2f7b6de1c001"

rm -rf "$project"
mkdir -p "$state"
cp -a "$repo/appData/templates/blank" "$project"

python3 - "$project" "$scene_id" <<'PY'
import json
import sys
from pathlib import Path

project = Path(sys.argv[1])
scene_id = sys.argv[2]

settings_path = project / "project" / "settings.gbsres"
settings = json.loads(settings_path.read_text())
settings["startSceneId"] = scene_id
settings["startX"] = 9
settings["startY"] = 9
settings_path.write_text(json.dumps(settings, indent=2) + "\n")

scene_dir = project / "project" / "scenes" / "blank"
scene_dir.mkdir(parents=True, exist_ok=True)
scene = {
    "_resourceType": "scene",
    "id": scene_id,
    "_index": 0,
    "type": "TOPDOWN",
    "name": "Blank",
    "symbol": "scene_blank",
    "x": 0,
    "y": 0,
    "width": 20,
    "height": 18,
    "backgroundId": "1e5f9d6a-bdbc-43e6-8c34-22f5bb5dea05",
    "tilesetId": "",
    "colorModeOverride": "none",
    "paletteIds": [],
    "spritePaletteIds": [],
    "autoFadeSpeed": 1,
    "script": [],
    "playerHit1Script": [],
    "playerHit2Script": [],
    "playerHit3Script": [],
    "collisions": "",
}
(scene_dir / "scene.gbsres").write_text(json.dumps(scene, indent=2) + "\n")
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
value = symbols["scene_blank"]
linear = value & 0xFFFFF
pointer = ((linear >> 4) << 16) | (linear & 0x0F)
checks = [
    {"symbol": "current_scene", "offset": 2, "size": 4,
     "equals": "0x{:08x}".format(pointer)},
    {"symbol": "actors", "offset": 2, "size": 2, "equals": 2304},
    {"symbol": "actors", "offset": 4, "size": 2, "equals": 2304},
]
Path(ram_out).write_text(json.dumps(checks, indent=2) + "\n")
PY
