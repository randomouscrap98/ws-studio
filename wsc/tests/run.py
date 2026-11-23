#!/usr/bin/env python3
"""Build and run ws-studio WonderSwan Color tests.

Each test lives in wsc/tests/<name>/test.json. See README.md in this directory.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
WSC_DIR = TESTS_DIR.parent
BUILD_TESTS_DIR = WSC_DIR / "build" / "tests"
WSRUN = WSC_DIR / "build" / "wsrun"
CORE = WSC_DIR / "build" / "mednafen_wswan_libretro.so"

# Values must match BOOT_SCENE_* in wsc/gamerom/src/test_scenes.h.
BOOT_SCENES = {
    "logo": 0,
    "town": 1,
    "town-walk": 2,
    "c13": 3,
    "c14": 4,
    "c15-instant": 5,
    "c15-speed": 6,
    "c15-var": 7,
    "c16-choice": 8,
    "c17-edge": 9,
    "c18-big": 10,
    "c18-blank": 11,
}

# Sections that wf-wswantool places in IRAM, which is what wsrun's system-RAM
# dump contains. Far data (SRAM), ROM and absolute symbols are not dumped.
IRAM_SECTION_PREFIXES = (
    ".bss",
    ".data",
    ".sbss",
    ".sdata",
    ".srodata",
    ".snoinit",
)


class TestError(Exception):
    pass


def tool_path(name):
    """Find an ia16 toolchain binary."""
    override = os.environ.get(name.upper())
    candidates = []
    if override:
        candidates.append(Path(override))
    toolchain = os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful")
    candidates.append(
        Path(toolchain) / "toolchain" / "gcc-ia16-elf" / "bin" / ("ia16-elf-" + name)
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise TestError("cannot find ia16-elf-{} (set WONDERFUL_TOOLCHAIN)".format(name))


OBJDUMP = None


def run_command(argv, cwd=None, what="command"):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    try:
        proc = subprocess.run(
            [str(arg) for arg in argv],
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except OSError as exc:
        raise TestError("cannot run {}: {}".format(what, exc)) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        if detail:
            detail = detail.splitlines()[-1]
            raise TestError("{} failed: {}".format(what, detail))
        raise TestError("{} failed with exit status {}".format(what, proc.returncode))
    return proc.stdout


def elf_symbol(elf_path, symbol):
    """Return (offset, size) for a symbol in wsrun's RAM dump."""
    global OBJDUMP
    if OBJDUMP is None:
        OBJDUMP = tool_path("objdump")
    output = run_command([OBJDUMP, "-t", elf_path], what="objdump")
    entries = []
    for line in output.splitlines():
        if not line or line.startswith("SYMBOL TABLE") or line.startswith("In archive"):
            continue
        # ADDR FLAGS SECTION<TAB>SIZE NAME
        if "\t" not in line:
            continue
        left, right = line.split("\t", 1)
        left_fields = left.split()
        right_fields = right.split(None, 1)
        if len(left_fields) < 3 or len(right_fields) != 2:
            continue
        addr_text = left_fields[0]
        section = left_fields[-1]
        size_text, name = right_fields
        if name != symbol:
            continue
        if section.startswith("*"):
            raise TestError(
                "symbol {} is {} (not in system RAM)".format(symbol, section)
            )
        base = section.rstrip("!&")
        if not any(base.startswith(prefix) for prefix in IRAM_SECTION_PREFIXES):
            raise TestError(
                "symbol {} is in section {}, which is not in the system RAM dump".format(
                    symbol, section
                )
            )
        try:
            address = int(addr_text, 16)
            size = int(size_text, 16)
        except ValueError as exc:
            raise TestError("cannot parse objdump line for {}: {}".format(symbol, line)) from exc
        entries.append((address, size, section))

    if not entries:
        raise TestError("symbol {} not found in {}".format(symbol, elf_path))
    if len(entries) > 1:
        raise TestError("symbol {} appears more than once in {}".format(symbol, elf_path))

    address, size, _section = entries[0]
    # IRAM symbols are allocated as flat offsets from 0; the dump starts there.
    return address & 0xFFFF, size


def parse_equals(value):
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise TestError("cannot read {}: {}".format(path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise TestError("invalid JSON in {}: {}".format(path, exc)) from exc


def save_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def resolve(path):
    path = Path(path)
    if path.is_absolute():
        return path
    return WSC_DIR / path


def build_test(spec):
    target = spec.get("build")
    if not target:
        return
    path = resolve(target)
    if path.is_dir():
        run_command(["make", "-C", path], what="build ({})".format(target))
    else:
        run_command(["make", "-C", WSC_DIR, target], what="build ({})".format(target))


def run_wsrun(test_dir, out_dir, spec):
    if not WSRUN.is_file():
        raise TestError("wsrun is missing; run make -C wsc/tools/wsrun")

    rom = resolve(spec["rom"])
    if not rom.is_file():
        raise TestError("ROM {} does not exist after build".format(rom))
    frames = spec["frames"]
    if not isinstance(frames, int) or frames < 0:
        raise TestError("frames must be a non-negative integer")

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "frame.rgb"
    png_path = out_dir / "frame.png"
    ram_path = out_dir / "ram.bin"

    argv = [
        WSRUN,
        "--core",
        CORE,
        "--rom",
        rom,
        "--frames",
        str(frames),
        "--png",
        png_path,
        "--raw",
        raw_path,
        "--ram",
        ram_path,
    ]

    boot = spec.get("boot")
    if boot is not None:
        if boot not in BOOT_SCENES:
            raise TestError("unknown boot scene {!r}".format(boot))
        argv.extend(["--boot-id", str(BOOT_SCENES[boot])])

    marker = spec.get("marker")
    if marker is not None:
        if not isinstance(marker, dict):
            raise TestError("marker must be an object")
        symbol = marker.get("symbol")
        size = marker.get("size")
        if not isinstance(symbol, str) or not symbol:
            raise TestError("marker is missing a symbol")
        if size not in (1, 2, 4):
            raise TestError("marker size must be 1, 2 or 4")
        if "equals" not in marker:
            raise TestError("marker is missing equals")
        try:
            value = parse_equals(marker["equals"])
        except (TypeError, ValueError):
            raise TestError("invalid marker equals value {!r}".format(
                marker["equals"]))
        elf_path = resolve(spec["elf"])
        if not elf_path.is_file():
            raise TestError("ELF {} does not exist after build".format(elf_path))
        address, _size = elf_symbol(elf_path, symbol)
        argv.extend(["--marker", "{}:{}:{}".format(address, size, value)])
        timeout = marker.get("timeout")
        if timeout is not None:
            if type(timeout) is not int or timeout <= 0:
                raise TestError("marker timeout must be a positive integer")
            argv.extend(["--marker-timeout", str(timeout)])
    input_name = spec.get("input")
    if input_name:
        input_path = Path(input_name)
        if not input_path.is_absolute():
            input_path = test_dir / input_path
        if not input_path.is_file():
            raise TestError("input file {} does not exist".format(input_path))
        argv.extend(["--input", input_path])

    output = run_command(argv, what="wsrun ({})".format(test_dir.name))
    match = re.search(r"width=(\d+) height=(\d+)", output)
    if not match:
        raise TestError("wsrun did not report frame dimensions")
    return raw_path, ram_path, int(match.group(1)), int(match.group(2))


def read_bytes(path, what):
    try:
        return path.read_bytes()
    except OSError as exc:
        raise TestError("cannot read {}: {}".format(what, exc)) from exc


def check_frame(raw_path, spec):
    digest = hashlib.sha256(read_bytes(raw_path, "wsrun frame")).hexdigest()
    expected = spec.get("frame_sha256")
    if expected is None:
        return
    expected = str(expected).lower()
    if digest != expected:
        raise TestError(
            "frame hash {} does not match {}".format(digest, expected)
        )


def compare_frames(actual_path, reference_path, precision, width):
    actual = read_bytes(actual_path, "wsrun frame")
    reference = read_bytes(reference_path, "reference frame")

    if precision not in ("exact", "4bit"):
        raise TestError(
            "reference precision must be 'exact' or '4bit', not {!r}".format(
                precision
            )
        )
    if len(actual) != len(reference):
        raise TestError(
            "reference frame is {} bytes, wsrun frame is {} bytes".format(
                len(reference), len(actual)
            )
        )

    first = None
    for offset, (got, want) in enumerate(zip(actual, reference)):
        if precision == "4bit":
            if (got >> 4) != (want >> 4):
                first = offset
                break
        elif got != want:
            first = offset
            break
    if first is None:
        return

    pixel = first // 3
    x = pixel % width if width else 0
    y = pixel // width if width else 0
    if first + 3 <= len(actual):
        got = tuple(actual[first:first + 3])
        want = tuple(reference[first:first + 3])
        detail = "wsrun {} != reference {}".format(got, want)
    else:
        detail = "wsrun 0x{:02X} != reference 0x{:02X}".format(
            actual[first], reference[first]
        )
    raise TestError(
        "reference mismatch at pixel ({}, {}): {}".format(x, y, detail)
    )


def run_reference(test_dir, out_dir, spec, raw_path, width):
    ref_spec = spec.get("reference")
    if ref_spec is None:
        return
    if isinstance(ref_spec, str):
        ref_spec = {"script": ref_spec}
    if not isinstance(ref_spec, dict):
        raise TestError("reference must be a script path or an object")

    script = ref_spec.get("script")
    if not isinstance(script, str) or not script:
        raise TestError("reference is missing a script")
    script_path = resolve(script)
    if not script_path.is_file():
        raise TestError("reference script {} does not exist".format(script_path))

    args = ref_spec.get("args", [])
    if not isinstance(args, list):
        raise TestError("reference args must be a list")
    reference_path = out_dir / "reference.rgb"
    argv = [sys.executable, script_path]
    argv.extend(str(arg) for arg in args)
    argv.extend(["--out", reference_path])
    run_command(argv, what="reference ({})".format(test_dir.name))
    compare_frames(
        raw_path,
        reference_path,
        ref_spec.get("precision", "exact"),
        width,
    )


def check_ram(ram_path, elf_path, spec):
    checks = spec.get("ram") or []
    if not checks:
        return
    ram = read_bytes(ram_path, "RAM dump")
    if not elf_path.is_file():
        raise TestError("ELF {} does not exist after build".format(elf_path))

    problems = []
    for check in checks:
        symbol = check.get("symbol")
        size = check.get("size")
        if not isinstance(symbol, str) or not symbol:
            problems.append("ram check without a symbol name")
            continue
        if size not in (1, 2, 4):
            problems.append("{}: size must be 1, 2 or 4".format(symbol))
            continue
        if "equals" not in check:
            problems.append("{}: missing equals value".format(symbol))
            continue
        extra = check.get("offset", 0)
        if type(extra) is not int or extra < 0:
            problems.append("{}: offset must be a non-negative integer".format(symbol))
            continue
        tolerance = check.get("tolerance", 0)
        if type(tolerance) is not int or tolerance < 0:
            problems.append(
                "{}: tolerance must be a non-negative integer".format(symbol)
            )
            continue
        try:
            expected = parse_equals(check["equals"])
        except (TypeError, ValueError):
            problems.append("{}: invalid equals value {!r}".format(symbol, check["equals"]))
            continue
        try:
            base, _ = elf_symbol(elf_path, symbol)
        except TestError as exc:
            problems.append(str(exc))
            continue
        address = base + extra
        if address + size > len(ram):
            problems.append(
                "{}+0x{:X} at 0x{:04X} is outside the {}-byte RAM dump".format(
                    symbol, extra, address, len(ram)
                )
            )
            continue
        actual = int.from_bytes(ram[address : address + size], "little")
        if abs(actual - expected) > tolerance:
            suffix = " (+/- {})".format(tolerance) if tolerance else ""
            problems.append(
                "{}+0x{:X} at RAM 0x{:04X} is 0x{:0{}X}, expected 0x{:0{}X}{}".format(
                    symbol, extra, address, actual, size * 2, expected, size * 2,
                    suffix,
                )
            )

    if problems:
        raise TestError("; ".join(problems))


def run_test(test_json, update_golden):
    spec = load_json(test_json)
    test_dir = test_json.parent
    name = test_dir.name
    out_dir = BUILD_TESTS_DIR / name

    for key in ("rom", "elf", "frames"):
        if key not in spec:
            raise TestError("test.json is missing {}".format(key))

    build_test(spec)
    raw_path, ram_path, width, _height = run_wsrun(test_dir, out_dir, spec)
    run_reference(test_dir, out_dir, spec, raw_path, width)

    if update_golden:
        digest = hashlib.sha256(read_bytes(raw_path, "wsrun frame")).hexdigest()
        spec["frame_sha256"] = digest
        save_json(test_json, spec)
    else:
        check_frame(raw_path, spec)

    if "ram" in spec:
        ram_spec = spec["ram"]
        if isinstance(ram_spec, str):
            # A generated oracle may write the checks after the build step.
            ram_spec = load_json(resolve(ram_spec))
            if not isinstance(ram_spec, list):
                raise TestError("RAM check file must contain a JSON list")
            spec = dict(spec)
            spec["ram"] = ram_spec
        check_ram(ram_path, resolve(spec["elf"]), spec)


def collect_tests(arguments):
    paths = []
    if arguments:
        for argument in arguments:
            matches = glob.glob(argument)
            if not matches:
                matches = [argument]
            for match in matches:
                path = Path(match)
                if path.is_dir():
                    path = path / "test.json"
                if not path.is_file():
                    raise TestError("{} is not a test directory".format(match))
                paths.append(path.resolve())
    else:
        paths = [
            path.resolve()
            for path in sorted(TESTS_DIR.glob("*/test.json"))
            if not path.parent.name.startswith("_")
        ]

    if not paths:
        raise TestError("no tests found")
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Run ws-studio WSC tests",
    )
    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="write the current frame hash into test.json instead of comparing",
    )
    parser.add_argument(
        "--expect-fail",
        action="store_true",
        help="exit 0 only if every listed test fails",
    )
    parser.add_argument("tests", nargs="*", help="test directories (default: all)")
    args = parser.parse_args()

    try:
        test_paths = collect_tests(args.tests)
    except TestError as exc:
        print("FAIL: {}".format(exc), file=sys.stderr)
        return 2

    results = []
    for test_json in test_paths:
        name = test_json.parent.name
        try:
            run_test(test_json, args.update_golden)
        except TestError as exc:
            print("FAIL {}: {}".format(name, exc))
            results.append(False)
        else:
            print("PASS {}".format(name))
            results.append(True)

    passed = results.count(True)
    failed = len(results) - passed
    print("{} passed, {} failed".format(passed, failed))

    if args.expect_fail:
        return 0 if failed == len(results) else 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
