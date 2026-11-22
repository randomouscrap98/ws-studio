#!/usr/bin/env python3
"""Build and check the C04s far-data spike ROMs."""
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
WSC_DIR = SPIKE_DIR.parent
BUILD_DIR = WSC_DIR / "build" / "spike"
WSRUN = WSC_DIR / "build" / "wsrun"
CORE = WSC_DIR / "build" / "mednafen_wswan_libretro.so"


class SpikeError(Exception):
    pass


def tool_path(name):
    toolchain = os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    path = (Path(toolchain) / "toolchain" / "gcc-ia16-elf" / "bin"
            / ("ia16-elf-" + name))
    if not path.is_file():
        raise SpikeError("cannot find {}".format(path))
    return path


def run_command(argv, what, cwd=None, stdin=None):
    env = dict(os.environ)
    env.setdefault("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        [str(arg) for arg in argv],
        cwd=str(cwd) if cwd is not None else None,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        detail = detail[-1] if detail else "exit status {}".format(proc.returncode)
        raise SpikeError("{}: {}".format(what, detail))
    return proc.stdout


def build_project(name):
    project = SPIKE_DIR / name
    out_dir = BUILD_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        ["make", "-C", str(project), "clean", "all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    (out_dir / "build.log").write_text(proc.stdout)
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.strip().splitlines()[-8:])
        raise SpikeError("make {} failed:\n{}".format(name, tail))
    rom = project / (name + ".wsc")
    if not rom.is_file():
        raise SpikeError("{} did not produce {}".format(name, rom))
    return rom, project / "build" / (name + ".elf")


def run_rom(name, rom, frames):
    out_dir = BUILD_DIR / name
    ram_path = out_dir / "ram.bin"
    if not WSRUN.is_file():
        raise SpikeError("wsrun is missing; run make -C wsc/tools/wsrun")
    if not CORE.is_file():
        raise SpikeError("core is missing: {}".format(CORE))
    run_command(
        [WSRUN, "--core", CORE, "--rom", rom, "--frames", str(frames),
         "--ram", ram_path],
        "wsrun {}".format(name),
    )
    return ram_path


def symbols(elf):
    output = run_command([tool_path("objdump"), "-t", elf], "objdump -t")
    result = {}
    for line in output.splitlines():
        if "\t" not in line or line.startswith("SYMBOL TABLE"):
            continue
        left, right = line.split("\t", 1)
        left_fields = left.split()
        right_fields = right.split(None, 1)
        if len(left_fields) < 3 or len(right_fields) != 2:
            continue
        try:
            address = int(left_fields[0], 16)
            size = int(right_fields[0], 16)
        except ValueError:
            continue
        result[right_fields[1]] = (address, size, left_fields[-1])
    return result


def read_ram(ram_path, syms, name, size):
    if name not in syms:
        raise SpikeError("symbol {} not found".format(name))
    address, symbol_size, _ = syms[name]
    if symbol_size != size:
        raise SpikeError("{} has size {}, expected {}".format(name, symbol_size, size))
    data = ram_path.read_bytes()
    if address + size > len(data):
        raise SpikeError("{} is outside the RAM dump".format(name))
    return int.from_bytes(data[address:address + size], "little")


def function_body(disassembly, name):
    marker = "<{}>:".format(name)
    start = disassembly.find(marker)
    if start < 0:
        return ""
    end = disassembly.find("\n\n", start)
    return disassembly[start:] if end < 0 else disassembly[start:end]


def decode_type2_vma(address):
    """Decode the segment and low bank nibble stored in a wf-wswantool VMA."""
    logical = address & 0xFFFFF
    return logical >> 4, logical & 0xF, (address >> 16) & 0xF


def section_size(elf, name):
    output = run_command([tool_path("objdump"), "-h", elf], "objdump -h")
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == name:
            return int(fields[2], 16)
    raise SpikeError("section {} not found".format(name))


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, condition, detail=""):
        if condition:
            print("PASS {}".format(name))
            self.passed += 1
        else:
            print("FAIL {}{}".format(name, ": " + detail if detail else ""))
            self.failed += 1


def check_farwalk(results):
    rom, elf = build_project("farwalk")
    ram = run_rom("farwalk", rom, 10)
    syms = symbols(elf)

    expected = {
        "sum_direct": (2, 120),
        "sum_param": (2, 376),
        "sum_struct": (2, 120),
        "sum_table": (2, 496),
    }
    for name, (size, want) in expected.items():
        got = read_ram(ram, syms, name, size)
        results.check("farwalk." + name, got == want,
                      "got 0x{:X}, want 0x{:X}".format(got, want))

    start_seg = read_ram(ram, syms, "start_seg", 2)
    start_off = read_ram(ram, syms, "start_off", 2)
    end_seg = read_ram(ram, syms, "end_seg", 2)
    end_off = read_ram(ram, syms, "end_off", 2)
    results.check("farwalk.walk_delta",
                  end_seg == start_seg and (end_off - start_off) == 16,
                  "start={:04X}:{:04X} end={:04X}:{:04X}".format(
                      start_seg, start_off, end_seg, end_off))
    tbl_seg = read_ram(ram, syms, "tbl_seg_delta", 2)
    tbl_off = read_ram(ram, syms, "tbl_off_delta", 2)
    results.check("farwalk.table_delta", tbl_seg == 0 and tbl_off == 16,
                  "seg delta 0x{:X}, off delta 0x{:X}".format(tbl_seg, tbl_off))

    section = syms["far_data"][2]
    results.check("farwalk.symbol_in_rom", section.startswith(".farrodata"),
                  "far_data is in {}".format(section))

    stage1 = SPIKE_DIR / "farwalk" / "build" / "farwalk_stage1.elf"
    disassembly = run_command([tool_path("objdump"), "-dr", stage1],
                              "objdump -dr")
    body = function_body(disassembly, "run")
    (BUILD_DIR / "farwalk" / "run.dis").write_text(body)
    results.check("farwalk.codegen.deref",
                  "%ds" in body and "(%bx)" in body,
                  "no DS-relative byte load in run()")
    results.check("farwalk.codegen.increment",
                  re.search(r"lea\s+0x1\(%bx\),%c[ix]", body) is not None,
                  "no 16-bit offset-only increment in run()")


def check_placement(results):
    rom, elf = build_project("placement")
    ram = run_rom("placement", rom, 10)
    syms = symbols(elf)

    for name, want in [("a_first", 0xA1), ("a_last", 0xA2),
                       ("b_first", 0xB1), ("b_last", 0xB2)]:
        got = read_ram(ram, syms, name, 2)
        results.check("placement." + name, got == want,
                      "got 0x{:X}, want 0x{:X}".format(got, want))

    a_seg = read_ram(ram, syms, "a_seg", 2)
    a_off = read_ram(ram, syms, "a_off", 2)
    b_seg = read_ram(ram, syms, "b_seg", 2)
    b_off = read_ram(ram, syms, "b_off", 2)
    results.check("placement.different_segments",
                  a_seg != b_seg and read_ram(ram, syms, "same_segment", 2) == 0,
                  "segments {:04X} and {:04X}".format(a_seg, b_seg))
    results.check("placement.no_boundary_cross",
                  read_ram(ram, syms, "a_crosses", 2) == 0
                  and read_ram(ram, syms, "b_crosses", 2) == 0,
                  "offset+40960 exceeds 0x10000")
    results.check("placement.forced_rom0",
                  read_ram(ram, syms, "forced_seg", 2) == 0x2000,
                  "forced segment is 0x{:04X}, want 0x2000".format(
                      read_ram(ram, syms, "forced_seg", 2)))
    results.check("placement.symbols_in_rom",
                  syms["far_a"][2].startswith(".farrodata")
                  and syms["far_b"][2].startswith(".farrodata")
                  and syms["forced"][2].startswith(".rom0"),
                  "far_a={} far_b={} forced={}".format(
                      syms["far_a"][2], syms["far_b"][2], syms["forced"][2]))

    a_seg2, a_off2, a_nibble = decode_type2_vma(syms["far_a"][0])
    b_seg2, b_off2, b_nibble = decode_type2_vma(syms["far_b"][0])
    print("INFO placement far_a VMA 0x{:08X} seg 0x{:04X} off 0x{:X} "
          "bank nibble 0x{:X}".format(syms["far_a"][0], a_seg2, a_off2, a_nibble))
    print("INFO placement far_b VMA 0x{:08X} seg 0x{:04X} off 0x{:X} "
          "bank nibble 0x{:X}".format(syms["far_b"][0], b_seg2, b_off2, b_nibble))


def check_reach(results, name, count, rom_size, expected_high_nibbles, frames):
    rom, elf = build_project(name)
    actual_size = rom.stat().st_size
    results.check(name + ".rom_size", actual_size == rom_size,
                  "ROM is {} bytes, want {}".format(actual_size, rom_size))
    ram = run_rom(name, rom, frames)
    syms = symbols(elf)

    ok = read_ram(ram, syms, "chunk_ok", 2)
    results.check(name + ".chunks_read", ok == count,
                  "{} of {} chunks read correctly".format(ok, count))

    firsts = read_ram(ram, syms, "firsts_sum", 2)
    lasts = read_ram(ram, syms, "lasts_sum", 2)
    want_firsts = sum(0x80 + i for i in range(count))
    want_lasts = sum(0x7F - i for i in range(count))
    results.check(name + ".markers",
                  firsts == want_firsts and lasts == want_lasts,
                  "firsts=0x{:X}/0x{:X} lasts=0x{:X}/0x{:X}".format(
                      firsts, want_firsts, lasts, want_lasts))

    c0 = read_ram(ram, syms, "bank_c0", 2)
    results.check(name + ".default_c0", (c0 & 0x0F) == 0x0F,
                  "port C0 reads 0x{:02X}, linear bank nibble is not F".format(c0))

    address, size, _ = syms["chunk_segs"]
    data = ram.read_bytes()
    segments = [int.from_bytes(data[address + 2 * i:address + 2 * i + 2], "little")
                for i in range(size // 2)]
    nibbles = sorted((segment >> 12) & 0xF for segment in segments)
    results.check(name + ".distinct_segments",
                  len(set(segments)) == count and nibbles == expected_high_nibbles,
                  "segments={} nibbles={}".format(
                      ["0x{:04X}".format(s) for s in segments], nibbles))
    print("INFO {} segments {}".format(
        name, " ".join("0x{:04X}".format(s) for s in segments)))

    banks = []
    for i in range(count):
        symbol = "chunk{}".format(i)
        if symbol in syms:
            banks.append(decode_type2_vma(syms[symbol][0])[2])
    results.check(name + ".symbol_banks",
                  len(banks) == count and sorted(banks) == expected_high_nibbles,
                  "bank nibbles={}".format(banks))


def compile_array(size):
    source = "typedef unsigned char u8;\nconst u8 __far a[{}];\n".format(size)
    env = dict(os.environ)
    env.setdefault("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        [str(tool_path("gcc")), "-mcmodel=medium", "-msegelf",
         "-mcs-jump-tables", "-ffreestanding", "-x", "c", "-c",
         "-o", "/dev/null", "-"],
        input=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    return proc.returncode, proc.stderr


def check_limits(results):
    rom, elf = build_project("limits")
    ram = run_rom("limits", rom, 120)
    syms = symbols(elf)

    checks = {
        "mismatch_at": (4, 0x10000),
        "wrap_at": (4, 0x10000),
        "seg_before": (2, 0xE000),
        "off_before": (2, 0),
        "seg_after": (2, 0xE000),
        "off_after": (2, 0),
        "first_byte": (2, 0x11),
        "wrapped_index_byte": (2, 0x22),
        "norm_0": (2, 0x11),
        "norm_8000": (2, 0x33),
        "norm_ffff": (2, 0x44),
        "norm_10000": (2, 0x55),
        "norm_end": (2, 0x66),
    }
    for name, (size, want) in checks.items():
        got = read_ram(ram, syms, name, size)
        results.check("limits." + name, got == want,
                      "got 0x{:X}, want 0x{:X}".format(got, want))

    results.check("limits.section_in_rom",
                  syms["big"][2].startswith(".farrodata"),
                  "big is in {}".format(syms["big"][2]))
    big_size = section_size(elf, ".farrodata.big")
    results.check("limits.section_size", big_size == 0x18000,
                  "section size 0x{:X}, want 0x18000".format(big_size))
    big_seg, big_off, big_nibble = decode_type2_vma(syms["big"][0])
    print("INFO limits big VMA 0x{:08X} seg 0x{:04X} off 0x{:X} "
          "bank nibble 0x{:X}".format(syms["big"][0], big_seg, big_off, big_nibble))

    code, stderr = compile_array(32767)
    results.check("limits.c_array_32767", code == 0, stderr.strip())
    code, stderr = compile_array(32768)
    results.check("limits.c_array_32768_rejected",
                  code != 0 and "size of array" in stderr,
                  "exit={} stderr={}".format(code, stderr.strip()))
    code, stderr = compile_array(40000)
    results.check("limits.c_array_40000_rejected",
                  code != 0 and "size of array" in stderr,
                  "exit={} stderr={}".format(code, stderr.strip()))

    macros = run_command(
        [tool_path("gcc"), "-mcmodel=medium", "-msegelf", "-dM", "-E",
         "-x", "c", "/dev/null"],
        "gcc -dM",
    )
    results.check("limits.ptrdiff_max",
                  "#define __PTRDIFF_MAX__ 0x7fff" in macros,
                  "__PTRDIFF_MAX__ is not 0x7fff")


def check_dsclobber(results):
    rom, elf = build_project("dsclobber")
    ram = run_rom("dsclobber", rom, 10)
    syms = symbols(elf)

    before = read_ram(ram, syms, "before", 2)
    after = read_ram(ram, syms, "after", 2)
    results.check("dsclobber.before", before == 0x1111,
                  "got 0x{:X}, want 0x1111".format(before))
    results.check("dsclobber.store_lost", after == 0xAAAA,
                  "after=0x{:X}, want the pre-read 0xAAAA (lost store)".format(after))
    results.check("dsclobber.data_segment",
                  read_ram(ram, syms, "data_seg", 2) != 0,
                  "data_seg is zero")


def main():
    if not WSRUN.is_file():
        print("FAIL wsrun is missing; run make -C wsc/tools/wsrun",
              file=sys.stderr)
        return 2
    results = Results()
    for name, func in [
        ("farwalk", check_farwalk),
        ("placement", check_placement),
        ("reach512", lambda r: check_reach(
            r, "reach512", 8, 512 * 1024, list(range(8, 16)), 60)),
        ("reach2m", lambda r: check_reach(
            r, "reach2m", 12, 2 * 1024 * 1024, list(range(4, 16)), 60)),
        ("limits", check_limits),
        ("dsclobber", check_dsclobber),
    ]:
        try:
            func(results)
        except SpikeError as exc:
            print("FAIL {}: {}".format(name, exc))
            results.failed += 1

    print("{} passed, {} failed".format(results.passed, results.failed))
    if results.failed:
        print("SPIKE FAIL")
        return 1
    print("SPIKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
