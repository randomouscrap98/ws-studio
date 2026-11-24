#!/usr/bin/env bash
#
# ROM capacity check for the WSC gamerom.
#
# Builds the normal image, then a variant with CAPACITY_FILLER=1 (48 KiB of
# called far code plus 150 KiB of far const data) in its own build directory.
# The variant must still link into the configured banks and boot the sample
# town scene exactly like the normal image.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WSC_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
ROOT_DIR=$(cd "${WSC_DIR}/.." && pwd)
GAMEROM_DIR="${WSC_DIR}/gamerom"

BUILD_ROOT="${WSC_DIR}/build/capacity_check"
CAP_BUILD="${BUILD_ROOT}/build"
CAP_ROM="${BUILD_ROOT}/gamerom.wsc"
CAP_ELF="${CAP_BUILD}/gamerom.elf"
CAP_TEST_DIR="${BUILD_ROOT}/test-boot-town"
CAP_RAM="${BUILD_ROOT}/ram_town.json"
CAP_LOG="${BUILD_ROOT}/capacity_usage.log"
NORMAL_LOG="${BUILD_ROOT}/normal_usage.log"

MIN_NORMAL_FREE=65536
MIN_FILLER_CODE=49152
MIN_FILLER_DATA=131072
MIN_FILLER_TOTAL=$((MIN_FILLER_CODE + MIN_FILLER_DATA))

export WONDERFUL_TOOLCHAIN="${WONDERFUL_TOOLCHAIN:-/opt/wonderful}"
NM="${WONDERFUL_TOOLCHAIN}/toolchain/gcc-ia16-elf/bin/ia16-elf-nm"

fail() {
    echo "FAIL capacity_check: $*"
    exit 1
}

usage_table() {
    awk '/^Section / { printing = 1 } printing && /^make:/ { exit } printing { print }' "$1"
}

# Print the table at the end of a usage log and discard make's own chatter.
capture_usage() {
    local log=$1
    local table
    table=$(usage_table "$log")
    if [[ -z "$table" ]]; then
        cat "$log"
        fail "no usage table in ${log}"
    fi
    printf '%s\n' "$table"
}

# The Cartridge ROM row is:
#   Cartridge ROM  0x80000 -> 0xFFFFF  size used used% free free% |...|
rom_field() {
    awk -v field="$2" '$1 == "Cartridge" && $2 == "ROM" { print $field; exit }' "$1"
}

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

echo "== normal gamerom =="
if ! make -C "$GAMEROM_DIR" usage >"$NORMAL_LOG" 2>&1; then
    cat "$NORMAL_LOG"
    fail "normal gamerom build failed"
fi
capture_usage "$NORMAL_LOG"
NORMAL_SIZE=$(rom_field "$NORMAL_LOG" 6)
NORMAL_USED=$(rom_field "$NORMAL_LOG" 7)
NORMAL_FREE=$(rom_field "$NORMAL_LOG" 9)

echo
echo "== capacity variant (CAPACITY_FILLER=1) =="
if ! make -C "$GAMEROM_DIR" CAPACITY_FILLER=1 \
        BUILDDIR="$CAP_BUILD" ROM="$CAP_ROM" usage >"$CAP_LOG" 2>&1; then
    cat "$CAP_LOG"
    fail "capacity variant build failed"
fi
capture_usage "$CAP_LOG"
CAP_SIZE=$(rom_field "$CAP_LOG" 6)
CAP_USED=$(rom_field "$CAP_LOG" 7)
CAP_FREE=$(rom_field "$CAP_LOG" 9)

if [[ ! -f "$CAP_ELF" ]]; then
    fail "capacity ELF ${CAP_ELF} was not produced"
fi
if [[ ! -f "$CAP_ROM" ]]; then
    fail "capacity ROM ${CAP_ROM} was not produced"
fi

FILLER_CODE=$("$NM" -S --radix=d "$CAP_ELF" |
    awk '$4 == "capacity_filler_code" { value = $2 + 0 } END { print value + 0 }')
FILLER_DATA=$("$NM" -S --radix=d "$CAP_ELF" |
    awk '$4 ~ /^capacity_data_[0-9]+$/ { sum += $2 + 0 } END { print sum + 0 }')
if [[ -z "$FILLER_CODE" ]]; then
    FILLER_CODE=0
fi
if [[ -z "$FILLER_DATA" ]]; then
    FILLER_DATA=0
fi
FILLER_TOTAL=$((FILLER_CODE + FILLER_DATA))
FILLER_DELTA=$((CAP_USED - NORMAL_USED))

echo
echo "normal:   ${NORMAL_USED} / ${NORMAL_SIZE} used, ${NORMAL_FREE} free"
echo "capacity: ${CAP_USED} / ${CAP_SIZE} used, ${CAP_FREE} free"
echo "filler:   ${FILLER_CODE} code + ${FILLER_DATA} data = ${FILLER_TOTAL} bytes"
echo "growth:   ${FILLER_DELTA} bytes used versus the normal image"

[[ "$NORMAL_FREE" -ge "$MIN_NORMAL_FREE" ]] ||
    fail "normal image has ${NORMAL_FREE} free, need ${MIN_NORMAL_FREE}"
[[ "$FILLER_CODE" -ge "$MIN_FILLER_CODE" ]] ||
    fail "linked filler code is ${FILLER_CODE} bytes, need ${MIN_FILLER_CODE}"
[[ "$FILLER_DATA" -ge "$MIN_FILLER_DATA" ]] ||
    fail "linked filler data is ${FILLER_DATA} bytes, need ${MIN_FILLER_DATA}"
[[ "$FILLER_DELTA" -ge "$MIN_FILLER_TOTAL" ]] ||
    fail "capacity variant grew by only ${FILLER_DELTA} bytes, need ${MIN_FILLER_TOTAL}"

echo
echo "== capacity variant boot-town =="
make -C "$WSC_DIR/tools/wsrun" >/dev/null
python3 "$WSC_DIR/tools/boot_oracle.py" \
    --ram-out "$CAP_RAM" --elf "$CAP_ELF" \
    --scene scene_sample_town --start-x 400 --start-y 400

mkdir -p "$CAP_TEST_DIR"
python3 - "$WSC_DIR/tests/boot-town/test.json" "$CAP_TEST_DIR/test.json" \
        "$CAP_ROM" "$CAP_ELF" "$CAP_RAM" <<'PY'
import json
import sys

source, destination, rom, elf, ram = sys.argv[1:]
with open(source, "r", encoding="utf-8") as handle:
    spec = json.load(handle)
spec["rom"] = rom
spec["elf"] = elf
spec["ram"] = ram
spec.pop("build", None)
with open(destination, "w", encoding="utf-8") as handle:
    json.dump(spec, handle, indent=2)
    handle.write("\n")
PY

if ! python3 "$WSC_DIR/tests/run.py" "$CAP_TEST_DIR"; then
    fail "boot-town failed on the capacity variant"
fi

echo
echo "PASS capacity_check: normal free ${NORMAL_FREE} bytes, capacity free ${CAP_FREE} bytes, boot-town passed"
