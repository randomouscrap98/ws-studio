#!/usr/bin/env python3
"""Build and check the C05s libws vblank-interrupt ROM under wsrun."""
import os
import subprocess
import sys
from pathlib import Path

SURVEY_DIR = Path(__file__).resolve().parent
WSC_DIR = SURVEY_DIR.parent
VBLANK_DIR = SURVEY_DIR / "vblank"
BUILD_DIR = WSC_DIR / "build" / "survey" / "vblank"
WSRUN = WSC_DIR / "build" / "wsrun"
CORE = WSC_DIR / "build" / "mednafen_wswan_libretro.so"
FRAMES = 120
TOLERANCE = 2


class CheckError(Exception):
    pass


def tool_path(name):
    override = os.environ.get(name.upper())
    candidates = []
    if override:
        candidates.append(Path(override))
    toolchain = Path(os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful"))
    candidates.append(toolchain / "toolchain" / "gcc-ia16-elf" / "bin"
                      / ("ia16-elf-" + name))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise CheckError("cannot find ia16-elf-{} (set WONDERFUL_TOOLCHAIN)".format(name))


def run_command(argv, what, cwd=None):
    env = dict(os.environ)
    env.setdefault("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        [str(arg) for arg in argv],
        cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        if detail:
            detail = "\n".join(detail.splitlines()[-12:])
        raise CheckError("{} failed:\n{}".format(what, detail))
    return proc.stdout


def ram_symbols(elf, names):
    output = run_command([tool_path("objdump"), "-t", elf], "objdump -t")
    found = {}
    for line in output.splitlines():
        if "\t" not in line or line.startswith("SYMBOL TABLE"):
            continue
        left, right = line.split("\t", 1)
        left_fields = left.split()
        right_fields = right.split(None, 1)
        if len(left_fields) < 3 or len(right_fields) != 2:
            continue
        addr_text, section = left_fields[0], left_fields[-1]
        _size, name = right_fields
        if name not in names:
            continue
        if section.startswith("*"):
            continue
        base = section.rstrip("!&")
        if not (base.startswith(".bss") or base.startswith(".data")
                or base.startswith(".sbss") or base.startswith(".sdata")):
            continue
        try:
            address = int(addr_text, 16) & 0xFFFF
        except ValueError:
            continue
        found.setdefault(name, address)
    missing = [name for name in names if name not in found]
    if missing:
        raise CheckError("symbols not in system RAM: {}".format(", ".join(missing)))
    return found


def main():
    if not WSRUN.is_file():
        raise CheckError("wsrun is missing; run make -C wsc/tools/wsrun")
    if not CORE.is_file():
        raise CheckError("core is missing: {}".format(CORE))

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    run_command(["make", "-C", VBLANK_DIR, "clean", "all"], "make vblank")
    rom = VBLANK_DIR / "vblank.wsc"
    elf = VBLANK_DIR / "build" / "vblank.elf"
    if not rom.is_file() or not elf.is_file():
        raise CheckError("vblank build did not produce {} / {}".format(rom, elf))

    ram_path = BUILD_DIR / "ram.bin"
    run_command([
        WSRUN, "--core", CORE, "--rom", rom,
        "--frames", str(FRAMES), "--ram", ram_path,
    ], "wsrun vblank")
    ram = ram_path.read_bytes()

    symbols = ram_symbols(elf, {"vblank_count", "vblank_last_count", "main_loops"})
    def word(name):
        address = symbols[name]
        return int.from_bytes(ram[address:address + 2], "little")

    count = word("vblank_count")
    last_count = word("vblank_last_count")
    loops = word("main_loops")

    print("frames={} vblank_count={} vblank_last_count={} main_loops={}".format(
        FRAMES, count, last_count, loops))

    if abs(count - FRAMES) > TOLERANCE:
        raise CheckError(
            "vblank handler counted {} frames, expected {} +/- {}".format(
                count, FRAMES, TOLERANCE))
    if count <= 0:
        raise CheckError("vblank handler never ran")
    if loops < FRAMES - TOLERANCE:
        raise CheckError("main loop advanced only {} times".format(loops))

    print("PASS vblank: handler counted {} interrupts across {} frames".format(
        count, FRAMES))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckError as exc:
        print("FAIL vblank: {}".format(exc), file=sys.stderr)
        sys.exit(1)
