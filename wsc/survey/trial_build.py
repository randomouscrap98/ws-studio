#!/usr/bin/env python3
"""Trial-compile every GBVM engine .c file for the WonderSwan Color.

Uses the same compiler flags as wsc/vmrom plus wsc/survey/trial_include, a
shim directory that declares the GBDK API and generated-data headers the
engine expects.  Engine files are not modified.  This deliberately reports
failures: a PASS here means "no non-GBDK portability problem was found", not
"this file runs on the WonderSwan".
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SURVEY_DIR = Path(__file__).resolve().parent
WSC_DIR = SURVEY_DIR.parent
ROOT_DIR = WSC_DIR.parent
ENGINE = ROOT_DIR / "appData" / "engine" / "gbvm"
BUILD_DIR = WSC_DIR / "build" / "survey"
OBJ_DIR = BUILD_DIR / "obj"

INCLUDES = [
    "-I" + str(SURVEY_DIR / "trial_include"),
    "-I" + str(WSC_DIR / "host" / "include"),
    "-I" + str(ENGINE / "include"),
]

# Mirror wsc/vmrom/Makefile's CFLAGS (WF_ARCH_CFLAGS expanded), but do not
# link.  GBT_PLAYER selects a TRACK_T for music_manager.h; the GB Studio build
# always selects one of GBT_PLAYER / HUGE_TRACKER.
FLAGS = [
    "-std=gnu11",
    "-Wall",
    "-march=v30mz",
    "-mtune=v30mz",
    "-mregparmcall",
    "-ffreestanding",
    "-mcmodel=medium",
    "-msegelf",
    "-mcs-jump-tables",
    "-ffunction-sections",
    "-fdata-sections",
    "-fno-common",
    "-O2",
    "-fno-builtin",
    "-Wno-unknown-pragmas",
    "-Wno-pointer-sign",
    "-DGBT_PLAYER",
]

CATEGORY_TESTS = [
    ("sdcc-asm", re.compile(
        r"expected .* before '(ld|ldh|ldhl|ret|or|e|and|add|sub|srl|sla|rr|rl|push|pop|scx|next_y|skip)'"
        r"|expected '=', ',', ';', 'asm' or '__attribute__' before"
        r"|stray '#'|invalid suffix"
        r"|unknown type name '(ld|ldh|ldhl|ret|or|e|scx|next_y|skip|preserves)'")),
    ("code/data-pointer", re.compile(
        r"initialization from pointer to non-enclosed address space"
        r"|pointer to non-enclosed address space")),
    ("non-constant-initializer", re.compile(r"initializer element is not constant")),
    ("sizeof-assert", re.compile(r"size of array 'check_")),
    ("compiler-ice", re.compile(r"internal compiler error|unrecognizable insn")),
    ("missing-shim", re.compile(
        r"undeclared|unknown type name|implicit declaration of function")),
    ("type-conflict", re.compile(r"conflicting")),
]


class TrialError(Exception):
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
    raise TrialError("cannot find ia16-elf-{} (set WONDERFUL_TOOLCHAIN)".format(name))


def sources():
    files = [ENGINE / "src" / "main.c"]
    files += sorted((ENGINE / "src" / "core").glob("*.c"))
    files += sorted((ENGINE / "src" / "states").glob("*.c"))
    return files


def classify(errors):
    categories = []
    for line in errors:
        for name, regex in CATEGORY_TESTS:
            if regex.search(line):
                if name not in categories:
                    categories.append(name)
                break
        else:
            if "other" not in categories:
                categories.append("other")
    return categories


def compile_file(cc, path):
    obj = OBJ_DIR / (path.stem + ".o")
    argv = [str(cc)] + FLAGS + INCLUDES
    sysroot_include = Path(os.environ.get("WONDERFUL_TOOLCHAIN", "/opt/wonderful")) \
        / "target" / "wswan" / "medium" / "include"
    if sysroot_include.is_dir():
        argv.append("-isystem")
        argv.append(str(sysroot_include))
    argv += ["-c", "-o", str(obj), str(path)]
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, env=env)
    output = proc.stderr or proc.stdout
    error_lines = [line for line in output.splitlines() if "error:" in line]
    warning_lines = [line for line in output.splitlines() if "warning:" in line]
    return proc.returncode, error_lines, warning_lines, output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsv", type=Path,
                        default=BUILD_DIR / "trial_build.tsv")
    parser.add_argument("--show-output", action="store_true",
                        help="print the compiler output for failing files")
    args = parser.parse_args()

    try:
        cc = tool_path("gcc")
    except TrialError as exc:
        print("FAIL trial-build: {}".format(exc), file=sys.stderr)
        return 2

    OBJ_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    failed = 0
    for path in sources():
        rel = path.relative_to(ROOT_DIR)
        code, errors, warnings, output = compile_file(cc, path)
        categories = classify(errors)
        if code != 0:
            failed += 1
        rows.append((str(rel), code, len(errors), len(warnings), categories, output))
        status = "PASS" if code == 0 else "FAIL"
        if code == 0:
            print("{} {:<48} 0 errors, {} warnings".format(
                status, str(path.stem), len(warnings)))
        else:
            print("{} {:<48} {} errors, {} warnings [{}]".format(
                status, str(path.stem), len(errors), len(warnings),
                ",".join(categories)))
        if args.show_output and code != 0:
            for line in output.splitlines():
                print("    " + line)

    args.tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.tsv.open("w", encoding="utf-8") as handle:
        handle.write("file\texit\terrors\twarnings\tcategories\n")
        for rel, code, nerrors, nwarnings, categories, _out in rows:
            handle.write("{}\t{}\t{}\t{}\t{}\n".format(
                rel, code, nerrors, nwarnings, ",".join(categories)))
    print("\n{} files, {} compiled, {} failed; details in {}".format(
        len(rows), len(rows) - failed, failed, args.tsv))
    # The trial build is expected to have failures; run.sh only gates on the
    # vblank check.
    return 0


if __name__ == "__main__":
    sys.exit(main())
