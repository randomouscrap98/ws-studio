#!/usr/bin/env python3
"""Differential GB-vs-WSC engine oracle.

Builds a project ROM with the pinned, pre-WSC GB Studio engine, runs it in a
Game Boy libretro core next to the WSC gamerom, and compares engine RAM by the
engine's own ``game_time`` tick rather than by emulator frame.

The intended differences (screen width, off-screen actor activation and the
scene's random-driven actor) live in wsc/oracle/*.json. Every RAM address is
resolved from the build's own symbols and every struct offset is compiled by
the toolchain that built that side, with a tiny offsetof probe.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC_DIR = HERE.parent
ROOT = WSC_DIR.parent
BUILD = WSC_DIR / "build"
ORACLE_DIR = WSC_DIR / "oracle"

# Last GBVM revision before the WSC work began (C03 changed vm.c/vm.h), from
# the vendored appData/engine/gbvm history. This is GB Studio 4.3.2's engine.
GB_ENGINE_REV = "b242ab79fd8a6aa0fe41d43b51a345685b11f9c3"

# Same GBDK-2020 release as wsc/tools/s2c_check.py (GB Studio 4.3.2's build
# tools hash in buildTools/dependencies.lock matches this archive).
GBDK_URL = (
    "https://github.com/gbdk-2020/gbdk-2020/releases/download/"
    "4.5.0/gbdk-linux64.tar.gz"
)
GBDK_SHA256 = "d7857a5f6d135ee4c249043ca26aad9f2ec8ab5d4106d97720d404114f42605c"

GB_CORE_NAME = "sameboy_libretro.so"
WSC_CORE_NAME = "mednafen_wswan_libretro.so"
WSRUN = BUILD / "wsrun"
GB_CORE = BUILD / GB_CORE_NAME
WSC_CORE = BUILD / WSC_CORE_NAME
WSC_ROM = WSC_DIR / "gamerom" / "gamerom.wsc"
WSC_ELF = WSC_DIR / "gamerom" / "build" / "gamerom.elf"
CLI = ROOT / "out" / "cli" / "gb-studio-cli.js"

# Current-only engine sources that the CLI's local-engine overlay leaves in
# place. The GB oracle must not compile WSC HAL code.
GB_ENGINE_STUBS = (
    "src/core/vm_dispatch.c",
    "src/wsc/bankdata_wsc.c",
    "src/wsc/hal_wsc.c",
    "src/wsc/hal_wsc_bg.c",
    "src/wsc/hal_wsc_spr.c",
    "src/wsc/scroll_wsc.c",
    "src/wsc/stubs_wsc.c",
    "src/wsc/ui_wsc.c",
)

ACTIVE_FLAG = 0x20

# Platform-state symbols compared alongside the player actor fields. Sizes are
# the engine's own types; enums are read as one byte on both sides.
STATE_FIELDS = {
    "plat_vel_x": 2,
    "plat_vel_y": 2,
    "plat_delta_x": 2,
    "plat_delta_y": 2,
    "plat_state": 1,
    "plat_next_state": 1,
    "plat_jump_type": 1,
    "plat_run_stage": 1,
    "plat_grounded": 1,
    "plat_on_slope": 1,
    "plat_slope_y": 1,
    "plat_hold_jump_timer": 1,
    "plat_coyote_timer": 1,
    "plat_jump_buffer_timer": 1,
    "plat_extra_jumps_counter": 1,
    "plat_wall_jump_counter": 1,
    "plat_wall_col": 1,
    "plat_drop_timer": 1,
    "plat_ladder_block_h": 1,
    "plat_ladder_block_v": 1,
    "plat_is_actor_attached": 1,
    "plat_dash_pressed": 1,
    "plat_dash_cooldown_timer": 1,
    "plat_dash_currentframe": 1,
    "plat_tap_timer": 1,
    "plat_anim_dirty": 1,
    "shooter_scroll_speed": 1,
    "shooter_reached_end": 1,
    "shooter_dest": 2,
    "shooter_direction": 1,
    "last_hit_trigger": 1,
    "player_iframes": 1,
}

FIELD_NAMES = ("flags", "pos", "x", "y", "dir", "frame", "animation",
               "move_speed", "collision_group", "size", "count")

# Projectile probe fields. The active list is walked from
# projectiles_active_head; pos/delta_pos add their member offsets to the
# struct base like the actor probe does.
PROJECTILE_FIELD_NAMES = ("pos", "x", "y", "delta_pos", "delta_x",
                          "delta_y", "frame", "def", "next", "size",
                          "life_time", "max")


class OracleError(Exception):
    pass


def run(argv, cwd=None, env=None, what=None):
    what = what or " ".join(str(a) for a in argv)
    try:
        proc = subprocess.run(
            [str(a) for a in argv],
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        raise OracleError("cannot run {}: {}".format(what, exc)) from exc
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.strip().splitlines()[-12:])
        raise OracleError("{} failed (exit {}):\n{}".format(
            what, proc.returncode, tail))
    return proc.stdout


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_gbdk():
    dest = BUILD / "gbdk"
    root = dest / "gbdk"
    if (root / "bin" / "lcc").is_file() and (root / "bin" / "sdcc").is_file():
        return root
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "gbdk-linux64.tar.gz"
    if not archive.is_file():
        print("gbdiff: downloading GBDK 4.5.0", file=sys.stderr)
        tmp = archive.with_suffix(".tmp")
        with urllib.request.urlopen(GBDK_URL) as response, open(tmp, "wb") as out:
            shutil.copyfileobj(response, out)
        os.replace(tmp, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != GBDK_SHA256:
        raise OracleError(
            "GBDK archive hash mismatch: got {}, want {}".format(
                digest, GBDK_SHA256))
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest)
    if not (root / "bin" / "lcc").is_file():
        raise OracleError("GBDK does not contain bin/lcc after extraction")
    return root


def ensure_cli():
    if not CLI.is_file():
        print("gbdiff: building the GB Studio CLI", file=sys.stderr)
        run([WSC_DIR / "export" / "run.sh"], cwd=ROOT,
            what="GB Studio CLI/export bootstrap")
    if not CLI.is_file():
        raise OracleError("GB Studio CLI was not built at {}".format(CLI))
    return CLI


def ensure_wsrun():
    if not WSRUN.is_file():
        run(["make", "-C", WSC_DIR / "tools" / "wsrun"], what="wsrun build")
    if not WSRUN.is_file():
        raise OracleError("wsrun was not built at {}".format(WSRUN))
    return WSRUN


def ensure_gb_core():
    if not GB_CORE.is_file():
        run(["bash", WSC_DIR / "tools" / "wsrun" / "fetch-gb-core.sh"],
            what="SameBoy core fetch/build")
    if not GB_CORE.is_file():
        raise OracleError("GB core was not built at {}".format(GB_CORE))
    # SameBoy looks for boot images in the system directory wsrun provides.
    boot = BUILD / "sameboy" / "BootROMs" / "prebuilt" / "cgb_boot.bin"
    if boot.is_file():
        ensure_dir(BUILD / "wsrun-system")
        shutil.copyfile(boot, BUILD / "wsrun-system" / "cgb_boot.bin")
    return GB_CORE


def ensure_wsc_rom():
    run(["make", "-C", WSC_DIR / "gamerom"], what="WSC gamerom build")
    for path in (WSC_ROM, WSC_ELF, WSC_CORE):
        if not path.is_file():
            raise OracleError("missing WSC artifact {}".format(path))
    return WSC_ROM, WSC_ELF


def write_stub(path, name):
    text = ("/* GB oracle stub: {} is not part of the pinned GB engine. */\n"
            "typedef int gb_oracle_engine_stub;\n".format(name))
    path.write_text(text)


def cli_tmp_dir(config):
    """Short, stable CLI temp/cache root (see prepare_gb_project)."""
    digest = hashlib.sha1(config.get("name", "").encode("utf-8")).hexdigest()[:12]
    return ensure_dir(BUILD / "gb-tmp" / digest)


def prepare_gb_project(config, workdir):
    config_text = json.dumps(config, sort_keys=True)
    stamp = workdir / "build.stamp"
    rom = workdir / "rom.gb"
    noi = workdir / "rom.noi"
    if (rom.is_file() and noi.is_file() and stamp.is_file() and
            stamp.read_text() == GB_ENGINE_REV + "\n" + config_text):
        return rom, noi

    print("gbdiff: building the GB ROM with engine {}".format(
        GB_ENGINE_REV[:12]), file=sys.stderr)
    project = workdir / "project"
    # SDCC builds temporary file names from TMPDIR into a small fixed buffer.
    # A workdir under wsc/build/gb-oracle/<config name> is long enough to
    # overflow it for the longer config names, so keep the CLI's temporary and
    # cache root short and stable per config.
    cli_tmp = cli_tmp_dir(config)
    shutil.rmtree(project, ignore_errors=True)
    shutil.rmtree(cli_tmp / "_gbsbuild", ignore_errors=True)
    ensure_dir(cli_tmp)
    shutil.copytree(ROOT / "appData" / "templates" / "gbs2", project)

    engine = ensure_dir(project / "assets" / "engine")
    try:
        archive = subprocess.check_output(
            ["git", "archive", GB_ENGINE_REV, "appData/engine/gbvm"],
            cwd=str(ROOT))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise OracleError("cannot archive pinned GB engine: {}".format(
            exc)) from exc
    # Feed the archive through tar without a shell (input is bytes, so use a
    # small temporary file).
    archive_file = workdir / "engine.tar"
    archive_file.write_bytes(archive)
    run(["tar", "-x", "-C", engine, "--strip-components=3", "-f",
         archive_file], what="extract pinned GB engine")
    archive_file.unlink()

    for name in GB_ENGINE_STUBS:
        path = engine / name
        ensure_dir(path.parent)
        write_stub(path, name)

    settings_path = project / "project" / "settings.gbsres"
    settings = json.loads(settings_path.read_text())
    settings["startSceneId"] = config["gb"]["startSceneId"]
    settings["startX"] = config["gb"]["startX"]
    settings["startY"] = config["gb"]["startY"]
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    tools = ensure_dir(cli_tmp / "_gbstools")
    gbdk = ensure_gbdk()
    gbdk_link = tools / "gbdk"
    if gbdk_link.is_symlink() or gbdk_link.exists():
        gbdk_link.unlink()
    gbdk_link.symlink_to(gbdk)
    shutil.copyfile(ROOT / "buildTools" / "linux-x64" / "tools_version",
                    tools / "tools_version")

    ensure_cli()
    env = dict(os.environ)
    env.update({
        "TMPDIR": str(cli_tmp),
        "ELECTRON_OVERRIDE_DIST_PATH": str(ROOT / "node_modules" /
                                           "electron" / "dist"),
        "ELECTRON_SKIP_BINARY_DOWNLOAD": "1",
    })
    run(["node", CLI, "--verbose", "make:rom",
         project / "project.gbsproj", rom], cwd=ROOT, env=env,
        what="GB ROM build")

    rom_dir = cli_tmp / "_gbsbuild" / "build" / "rom"
    nois = sorted(rom_dir.glob("*.noi"))
    if len(nois) != 1:
        raise OracleError("expected one .noi in {}, found {}".format(
            rom_dir, len(nois)))
    shutil.copyfile(nois[0], noi)
    maps = sorted(rom_dir.glob("*.map"))
    if maps:
        shutil.copyfile(maps[0], workdir / "rom.map")

    stamp.write_text(GB_ENGINE_REV + "\n" + config_text)
    return rom, noi


def parse_noi(path):
    symbols = {}
    for line in path.read_text(errors="replace").splitlines():
        match = re.match(r"\s*DEF\s+(\S+)\s+0x([0-9A-Fa-f]+)\s*$", line)
        if match:
            symbols[match.group(1)] = int(match.group(2), 16)
    if not symbols:
        raise OracleError("no symbols found in {}".format(path))
    return symbols


def ia16_tool(name):
    toolchain = Path(os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful"))
    path = toolchain / "toolchain" / "gcc-ia16-elf" / "bin" / ("ia16-elf-" + name)
    if not path.is_file():
        raise OracleError("cannot find {} (set WONDERFUL_TOOLCHAIN)".format(path))
    return path


def wsc_symbols(elf_path):
    output = run([ia16_tool("objdump"), "-t", elf_path],
                 what="WSC objdump symbols")
    symbols = {}
    for line in output.splitlines():
        if not line or line.startswith("SYMBOL TABLE") or "\t" not in line:
            continue
        left, right = line.split("\t", 1)
        fields = left.split()
        name_fields = right.split(None, 1)
        if len(fields) < 3 or len(name_fields) != 2:
            continue
        address_text, section = fields[0], fields[-1]
        name = name_fields[1]
        if section.startswith("*"):
            continue
        base = section.rstrip("!&")
        if not (base.startswith(".bss") or base.startswith(".data") or
                base.startswith(".sbss") or base.startswith(".sdata") or
                base.startswith(".srodata") or base.startswith(".snoinit")):
            continue
        try:
            symbols[name] = int(address_text, 16) & 0xFFFF
        except ValueError:
            continue
    if not symbols:
        raise OracleError("no system-RAM symbols found in {}".format(elf_path))
    return symbols


def gb_ram_offset(address, ram_size):
    if 0xC000 <= address < 0xD000:
        return address - 0xC000
    if 0xD000 <= address < 0xE000:
        # SameBoy's CGB WRAM dump is eight 4 KiB banks. GBDK uses the default
        # SVBK value 1, so D000-DFFF is bank 1 in the dump.
        if ram_size >= 0x8000:
            return 0x1000 + (address - 0xD000)
        return address - 0xC000
    raise OracleError("GB symbol address 0x{:04X} is not in WRAM".format(address))


PROBE_SOURCE = """\
#include <stddef.h>
#include "gbs_types.h"
#include "actor.h"
#include "projectiles.h"

const unsigned int probe_offsets[] = {
    offsetof(actor_t, flags),
    offsetof(actor_t, pos),
    offsetof(upoint16_t, x),
    offsetof(upoint16_t, y),
    offsetof(actor_t, dir),
    offsetof(actor_t, frame),
    offsetof(actor_t, animation),
    offsetof(actor_t, move_speed),
    offsetof(actor_t, collision_group),
    sizeof(actor_t),
    MAX_ACTORS,
};

const unsigned int projectile_probe_offsets[] = {
    offsetof(projectile_t, pos),
    offsetof(upoint16_t, x),
    offsetof(upoint16_t, y),
    offsetof(projectile_t, delta_pos),
    offsetof(point16_t, x),
    offsetof(point16_t, y),
    offsetof(projectile_t, frame),
    offsetof(projectile_t, def),
    offsetof(projectile_t, next),
    sizeof(projectile_t),
    offsetof(projectile_t, def) + offsetof(projectile_def_t, life_time),
    MAX_PROJECTILES,
};
"""


def parse_probe_values(text, label, names, pattern, base):
    # Labels are prefixed by "_" in SDCC assembly. Match them at the start of
    # a line so "probe_offsets:" does not also match inside
    # "projectile_probe_offsets:".
    label_match = re.search(r"(?m)^_?" + re.escape(label), text)
    if label_match is None:
        raise OracleError("offset probe has no {} label".format(label))
    values = []
    for line in text[label_match.end():].splitlines()[1:]:
        match = re.search(pattern, line)
        if match:
            values.append(int(match.group(1), base))
        elif values:
            break
    if len(values) < len(names):
        raise OracleError("offset probe produced {} values for {}, expected "
                          "{}".format(len(values), label, len(names)))
    return dict(zip(names, values[:len(names)]))


def parse_probe_asm(path, pattern, base):
    text = path.read_text(errors="replace")
    raw = parse_probe_values(text, "probe_offsets:", FIELD_NAMES, pattern,
                             base)
    pos = raw["pos"]
    raw["x"] += pos
    raw["y"] += pos

    proj = parse_probe_values(text, "projectile_probe_offsets:",
                              PROJECTILE_FIELD_NAMES, pattern, base)
    proj_pos = proj["pos"]
    proj["x"] += proj_pos
    proj["y"] += proj_pos
    delta = proj["delta_pos"]
    proj["delta_x"] += delta
    proj["delta_y"] += delta
    for name, value in proj.items():
        raw["proj_" + name] = value
    return raw


def gb_layout(workdir, gbdk, cli_tmp):
    probe = workdir / "layout_gb.c"
    probe.write_text(PROBE_SOURCE)
    asm = workdir / "layout_gb.asm"
    engine_include = workdir / "project" / "assets" / "engine" / "include"
    data_include = cli_tmp / "_gbsbuild" / "include"
    run([
        gbdk / "bin" / "sdcc", "-msm83", "-S",
        "-D__PORT_sm83", "-D__TARGET_gb", "-DHUGE_TRACKER", "-DCGB",
        "-I" + str(gbdk / "include"),
        "-I" + str(engine_include),
        "-I" + str(data_include),
        "-o", asm, probe,
    ], what="GB offsetof probe")
    return parse_probe_asm(asm, r"\.dw\s+#0x([0-9A-Fa-f]+)", 16)


def wsc_layout(workdir):
    probe = workdir / "layout_wsc.c"
    probe.write_text(PROBE_SOURCE)
    asm = workdir / "layout_wsc.s"
    include_dirs = [
        WSC_DIR / "gamerom" / "include",
        BUILD / "gamerom" / "include",
        ROOT / "appData" / "engine" / "gbvm" / "include",
        WSC_DIR / "host" / "include",
        BUILD / "export" / "include",
        BUILD / "gamerom" / "c18",
        BUILD / "gamerom" / "s2c",
    ]
    argv = [
        ia16_tool("gcc"), "-std=gnu11", "-ffreestanding",
        "-march=v30mz", "-mtune=v30mz", "-mregparmcall",
        "-mcmodel=medium", "-msegelf", "-mcs-jump-tables",
        "-S", "-O2", "-fno-builtin", "-Wno-unknown-pragmas",
        "-Wno-pointer-sign", "-D__WONDERFUL__", "-D__WONDERFUL_WSWAN__",
        "-DHUGE_TRACKER", "-DGBVM_ENGINE_HANDLERS",
    ]
    for path in include_dirs:
        argv.extend(["-I", path])
    argv.extend(["-include", WSC_DIR / "gamerom" / "include" /
                 "gamerom_prelude.h", "-o", asm, probe])
    run(argv, what="WSC offsetof probe")
    return parse_probe_asm(asm, r"\.(?:hword|word)\s+(-?\d+)", 10)


class Trace:
    def __init__(self, path):
        data = path.read_bytes()
        if len(data) < 20 or data[:8] != b"GBOTRACE":
            raise OracleError("{} is not a wsrun tick trace".format(path))
        version, self.tick_width, self.ram_size = struct.unpack(
            "<III", data[8:20])
        if version != 1:
            raise OracleError("unsupported trace version {}".format(version))
        self.records = {}
        offset = 20
        while offset < len(data):
            if offset + 8 > len(data):
                raise OracleError("truncated trace record in {}".format(path))
            tick, size = struct.unpack("<II", data[offset:offset + 8])
            offset += 8
            if offset + size > len(data):
                raise OracleError("truncated trace RAM in {}".format(path))
            self.records[tick] = data[offset:offset + size]
            offset += size
        if not self.records:
            raise OracleError("{} contains no ticks".format(path))

    def read(self, address, size):
        raise NotImplementedError

    def u8(self, address):
        return self.read(address, 1)

    def u16(self, address):
        return self.read(address, 2)


class GBTrace(Trace):
    def __init__(self, path):
        super().__init__(path)

    def read(self, address, size):
        offset = gb_ram_offset(address, self.ram_size)
        if offset + size > self.ram_size:
            raise OracleError("GB address 0x{:04X} leaves the RAM dump".format(
                address))
        value = 0
        for i in range(size):
            value |= self.records[self.current][offset + i] << (8 * i)
        return value


class WSCTrace(Trace):
    def __init__(self, path):
        super().__init__(path)

    def read(self, address, size):
        address &= 0xFFFF
        if address + size > self.ram_size:
            raise OracleError("WSC address 0x{:04X} leaves the RAM dump".format(
                address))
        value = 0
        for i in range(size):
            value |= self.records[self.current][address + i] << (8 * i)
        return value


class Side:
    def __init__(self, name, trace, symbols, layout, prefix):
        self.name = name
        self.trace = trace
        self.symbols = symbols
        self.layout = layout
        self.prefix = prefix

    def set_tick(self, tick):
        self.trace.current = tick

    def symbol(self, name):
        name = self.prefix + name.lstrip("_")
        if name not in self.symbols:
            raise OracleError("{} symbol {} not found".format(self.name, name))
        return self.symbols[name]

    def actor_field(self, index, field):
        base = self.symbol("actors") + index * self.layout["size"]
        return base + self.layout[field]

    def actor(self, index, field):
        return self.trace.read(self.actor_field(index, field),
                               {"x": 2, "y": 2, "dir": 1, "flags": 1,
                                "frame": 1, "animation": 1,
                                "move_speed": 1, "collision_group": 1}[field])

    def player_moving(self):
        return self.trace.u8(self.symbol("player_moving"))

    def state_field(self, name):
        return self.trace.read(self.symbol(name), STATE_FIELDS[name])

    def projectiles(self):
        """Active projectile node addresses, in the engine's list order."""
        head = self.trace.u16(self.symbol("projectiles_active_head"))
        nodes = []
        seen = set()
        while (head and head not in seen and
               len(nodes) < self.layout["proj_max"]):
            seen.add(head)
            nodes.append(head)
            head = self.trace.u16(
                (head + self.layout["proj_next"]) & 0xFFFF)
        return nodes

    def projectile_field(self, node, field):
        size = {"x": 2, "y": 2, "delta_x": 2, "delta_y": 2,
                "frame": 1, "life_time": 1}[field]
        return self.trace.read((node + self.layout["proj_" + field]) & 0xFFFF,
                               size)

    def scroll(self, axis):
        return self.trace.u16(self.symbol("scroll_" + axis))


def trace_path(workdir, side):
    return workdir / "{}.trace".format(side)


def build_gb_args(config, rom, workdir, layout, symbols, trace):
    start_x = int(config["gb"]["startX"]) * 256
    start_y = int(config["gb"]["startY"]) * 256
    args = [
        WSRUN, "--core", GB_CORE, "--rom", rom,
        "--frames", str(config.get("frames", 5000)),
        "--marker-timeout", str(config.get("marker_timeout", 1500)),
        "--tick", "{}:1".format(gb_ram_offset(symbols["_game_time"],
                                             0x8000)),
        "--max-ticks", str(config["ticks"]),
        "--trace", trace,
    ]
    player = symbols["_actors"]
    args.extend([
        "--marker", "{}:1:0".format(gb_ram_offset(symbols["_game_time"], 0x8000)),
        "--marker", "{}:2:{}".format(
            gb_ram_offset(player + layout["x"], 0x8000), start_x),
        "--marker", "{}:2:{}".format(
            gb_ram_offset(player + layout["y"], 0x8000), start_y),
    ])
    if config.get("input"):
        args.extend(["--input", config["input"], "--input-tick"])
    return args


def build_wsc_args(config, layout, symbols, trace, pokes=()):
    start_x = int(config["gb"]["startX"]) * 256
    start_y = int(config["gb"]["startY"]) * 256
    marker = config["wsc"]["readySymbol"]
    args = [
        WSRUN, "--core", WSC_CORE, "--rom", WSC_ROM,
        "--boot-id", str(config["wsc"]["bootId"]),
        "--frames", str(config.get("frames", 5000)),
        "--marker-timeout", str(config.get("marker_timeout", 1500)),
        "--tick", "{}:1".format(symbols["game_time"]),
        "--max-ticks", str(config["ticks"]),
        "--trace", trace,
    ]
    for address, width, value in pokes:
        args.extend(["--poke", "{}:{}:{}".format(address, width, value)])
    player = symbols["actors"]
    args.extend([
        "--marker", "{}:1:1".format(symbols[marker]),
        "--marker", "{}:1:0".format(symbols["game_time"]),
        "--marker", "{}:2:{}".format(player + layout["x"], start_x),
        "--marker", "{}:2:{}".format(player + layout["y"], start_y),
    ])
    if config.get("input"):
        args.extend(["--input", config["input"], "--input-tick"])
    return args


def read_trace(path, cls):
    return cls(path)


def excluded_actor_fields(config):
    result = {}
    for item in config.get("compare", {}).get("excluded", []):
        if item.get("category") == "actor_fields":
            result[int(item["actor"])] = set(item.get("fields", ()))
    return result


def skip_viewport_animation_phase(config):
    """Whether an off-screen activation difference also skips frame/animation.

    Only actors whose activation was ignored because they were outside the GB
    viewport are affected, and only their animation-phase fields; position,
    direction and movement are still compared.
    """
    for item in config.get("compare", {}).get("excluded", []):
        if (item.get("category") == "off_screen_actor_activation" and
                item.get("animationPhase")):
            return True
    return False


def actor_in_gb_view(gb, position_side, index):
    """Whether an actor is inside the GB viewport (the common visible area)."""
    x = position_side.actor(index, "x")
    y = position_side.actor(index, "y")
    if x == 0 and y == 0:
        return False
    left = gb.scroll("x")
    top = gb.scroll("y")
    return (left <= x < left + 160 and top <= y < top + 144)


def compare_traces(config, gb, wsc):
    ticks = sorted(set(gb.trace.records) & set(wsc.trace.records))
    if not ticks:
        raise OracleError("the two traces share no ticks")
    expected = config["ticks"]
    if len(ticks) < expected:
        raise OracleError("only {} of {} ticks were recorded".format(
            len(ticks), expected))
    if ticks[0] != 1 or ticks[-1] != expected:
        raise OracleError("tick sequence is {}..{}, expected 1..{}".format(
            ticks[0], ticks[-1], expected))

    fields = config.get("compare", {})
    player_fields = fields.get("playerFields", (
        "x", "y", "dir", "flags", "frame", "animation", "move_speed"))
    actor_fields = fields.get("actorFields", (
        "x", "y", "dir", "frame", "animation"))
    projectile_fields = fields.get("projectileFields", ())
    skip_actor_fields = excluded_actor_fields(config)
    skip_phase = skip_viewport_animation_phase(config)
    phase_actors = set()
    skipped_phase_values = 0
    actor_count = gb.layout["count"]
    if wsc.layout["count"] != actor_count:
        raise OracleError("actor counts differ: GB {}, WSC {}".format(
            actor_count, wsc.layout["count"]))

    compared = 0
    ignored_activation = 0
    for tick in ticks:
        gb.set_tick(tick)
        wsc.set_tick(tick)

        for field in player_fields:
            if field == "player_moving":
                a, b = gb.player_moving(), wsc.player_moving()
            elif field in STATE_FIELDS:
                a, b = gb.state_field(field), wsc.state_field(field)
            else:
                a, b = gb.actor(0, field), wsc.actor(0, field)
            compared += 1
            if a != b:
                return tick, "player." + field, a, b, compared

        if projectile_fields:
            gb_projectiles = gb.projectiles()
            wsc_projectiles = wsc.projectiles()
            compared += 1
            if len(gb_projectiles) != len(wsc_projectiles):
                return (tick, "projectiles.count", len(gb_projectiles),
                        len(wsc_projectiles), compared)
            for index, (gb_node, wsc_node) in enumerate(zip(
                    gb_projectiles, wsc_projectiles)):
                for field in projectile_fields:
                    a = gb.projectile_field(gb_node, field)
                    b = wsc.projectile_field(wsc_node, field)
                    compared += 1
                    if a != b:
                        return (tick, "projectile[{}].{}".format(index, field),
                                a, b, compared)

        for index in range(1, actor_count):
            gb_active = bool(gb.actor(index, "flags") & ACTIVE_FLAG)
            wsc_active = bool(wsc.actor(index, "flags") & ACTIVE_FLAG)
            if gb_active != wsc_active:
                # Only require equal activation inside the GB viewport; the
                # WSC's wider screen intentionally activates more actors.
                position_side = gb if gb_active else wsc
                if actor_in_gb_view(gb, position_side, index):
                    return (tick, "actor[{}].active".format(index),
                            int(gb_active), int(wsc_active), compared)
                ignored_activation += 1
                if skip_phase:
                    phase_actors.add(index)
                continue
            if not gb_active:
                continue
            for field in actor_fields:
                if field in skip_actor_fields.get(index, ()):
                    continue
                if (skip_phase and index in phase_actors and
                        field in ("frame", "animation")):
                    skipped_phase_values += 1
                    continue
                a, b = gb.actor(index, field), wsc.actor(index, field)
                compared += 1
                if a != b:
                    return (tick, "actor[{}].{}".format(index, field),
                            a, b, compared)

    return None, compared, ignored_activation, sorted(phase_actors), skipped_phase_values


def run_pair(config, workdir):
    workdir = ensure_dir(workdir)
    ensure_wsrun()
    ensure_gb_core()
    ensure_wsc_rom()

    gbdk = ensure_gbdk()
    rom, noi = prepare_gb_project(config, workdir)
    gb_symbols = parse_noi(noi)
    wsc_syms = wsc_symbols(WSC_ELF)
    gb_lay = gb_layout(workdir, gbdk, cli_tmp_dir(config))
    wsc_lay = wsc_layout(workdir)

    gb_trace = trace_path(workdir, "gb")
    wsc_trace = trace_path(workdir, "wsc")
    print("gbdiff: running GB oracle ROM", file=sys.stderr)
    run(build_gb_args(config, rom, workdir, gb_lay, gb_symbols, gb_trace),
        cwd=ROOT, what="GB oracle run")

    pokes = []
    if config.get("rngSync"):
        # The two platforms seed the LCG differently (GB DIV_REG, WSC vblank
        # count). Copy the GB state into WSC once, after the start marker and
        # before the tick trace: the WSC platform hook uses GBDK's LCG, so the
        # sequences then match. Both seeds are plain 16-bit RAM words.
        seed = gb_symbols.get("___rand_seed")  # GBDK's __rand_seed
        target = wsc_syms.get("rng_state")
        if seed is None or target is None:
            raise OracleError("rngSync needs GB __rand_seed and WSC rng_state")
        gb_start = GBTrace(gb_trace)
        gb_start.current = 1
        pokes.append((target, 2, gb_start.u16(seed)))

    print("gbdiff: running WSC gamerom", file=sys.stderr)
    run(build_wsc_args(config, wsc_lay, wsc_syms, wsc_trace, pokes),
        cwd=ROOT, what="WSC oracle run")

    gb = Side("GB", read_trace(gb_trace, GBTrace), gb_symbols, gb_lay, "_")
    wsc = Side("WSC", read_trace(wsc_trace, WSCTrace), wsc_syms, wsc_lay, "")
    result = compare_traces(config, gb, wsc)
    if result[0] is not None:
        tick, field, a, b, compared = result
        print("DIVERGED tick {} field {}: GB={} (0x{:X}) WSC={} (0x{:X}) "
              "after {} compared values".format(
                  tick, field, a, a, b, b, compared))
        return 1

    _, compared, ignored_activation, phase_actors, skipped_phase = result
    exclusions = config.get("compare", {}).get("excluded", [])
    print("match: {} ticks, {} compared values".format(config["ticks"],
                                                       compared))
    projectile_fields = config["compare"].get("projectileFields", ())
    print("fields: player {}; active actor {}; projectiles {}".format(
        ",".join(config["compare"]["playerFields"]),
        ",".join(config["compare"]["actorFields"]),
        ",".join(projectile_fields) or "not compared"))
    if ignored_activation:
        print("ignored {} off-screen activation differences".format(
            ignored_activation))
    if skipped_phase:
        print("ignored {} viewport-caused animation-phase values for "
              "actor[s] {}".format(
                  skipped_phase, ",".join(str(i) for i in phase_actors)))
    for item in exclusions:
        why = item.get("why", "")
        if item.get("category") == "actor_fields":
            print("excluded actor[{}] {} ({}).".format(
                item["actor"], item.get("name", "fields"), why))
        else:
            print("excluded {} ({}).".format(item["category"], why))
    return 0


def run_platform_smoke(config, workdir):
    workdir = ensure_dir(workdir)
    ensure_wsrun()
    ensure_gb_core()
    gbdk = ensure_gbdk()
    rom, noi = prepare_gb_project(config, workdir)
    symbols = parse_noi(noi)
    layout = gb_layout(workdir, gbdk, cli_tmp_dir(config))
    trace = trace_path(workdir, "gb")
    run(build_gb_args(config, rom, workdir, layout, symbols, trace),
        cwd=ROOT, what="GB platform smoke run")
    data = GBTrace(trace)
    ys = {}
    positions = {}
    for tick in sorted(data.records):
        data.current = tick
        ys[tick] = data.u16(symbols["_actors"] + layout["y"])
        positions[tick] = (data.u16(symbols["_actors"] + layout["x"]),
                           ys[tick])
    apex = min(ys, key=lambda tick: (ys[tick], tick))
    print("platform GB-only trace: {} ticks, y range {}..{} px, apex tick {} "
          "(y={} px)".format(
              len(ys), min(ys.values()) // 32, max(ys.values()) // 32,
              apex, ys[apex] // 32))
    before = ys.get(apex - 8)
    after = ys.get(apex + 8)
    if before is None or after is None:
        raise OracleError("platform jump is not inside the trace")
    if not (before > ys[apex] < after):
        raise OracleError(
            "no jump-like y arc around tick {}: {} {} {}".format(
                apex, before, ys[apex], after))
    print("platform y arc: tick {}={} -> tick {}={} -> tick {}={} "
          "(subpixels)".format(apex - 8, before, apex, ys[apex], apex + 8,
                               after))
    return 0


def load_config(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise OracleError("cannot read config {}: {}".format(path, exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--platform-smoke", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (ROOT / config_path).resolve()
    config = load_config(config_path)
    if config.get("input"):
        config["input"] = str((config_path.parent / config["input"]).resolve())
    workdir = Path(args.workdir) if args.workdir else (
        BUILD / "gb-oracle" / config["name"])
    try:
        if args.platform_smoke:
            return run_platform_smoke(config, workdir)
        return run_pair(config, workdir)
    except OracleError as exc:
        print("gbdiff: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
