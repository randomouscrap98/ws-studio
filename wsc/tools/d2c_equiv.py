#!/usr/bin/env python3
"""Compare the TypeScript d2c port with the Python oracle on every script set.

The sets are the same ones `make -C wsc s2c-equiv` uses. For each project set
this generates the s2c output with the Python converter, then runs both d2c
implementations on the same export and compares every generated file byte for
byte. One deliberately broken s2c header must be rejected by both.

Usage: d2c_equiv.py
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC_DIR = HERE.parent
BUILD = WSC_DIR / "build"
WORK = BUILD / "d2c-equiv"
PY_D2C = HERE / "d2c.py"
TS_D2C = HERE / "d2c-ts.js"
ERROR_HEADER = WSC_DIR / "tests" / "d2c-equiv" / "error_incomplete_header.h"
ERROR_SOURCE = WSC_DIR / "tests" / "d2c-equiv" / "error_source.c"
STATES = "topdown,platform,shmup,pointnclick,adventure"

sys.path.insert(0, str(HERE))
import s2c_equiv  # noqa: E402


def generate_s2c(name, export, files, extra=()):
    out = WORK / name / "s2c"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    s2c_equiv.run(
        [
            sys.executable,
            s2c_equiv.PY_S2C,
            "--include",
            export / "include",
            "--out",
            out,
            "--name",
            "product",
            *extra,
            *files,
        ],
        cwd=s2c_equiv.ROOT,
        what="{} python s2c".format(name),
    )
    return out / "product.h", out / "product.c"


def compare_set(name, export, files, extra=()):
    header, source = generate_s2c(name, export, files, extra)
    differences = []
    file_counts = {}
    for implementation, command in (
        ("py", [sys.executable, PY_D2C]),
        ("ts", ["node", TS_D2C]),
    ):
        out = WORK / name / implementation
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        result = s2c_equiv.run(
            [
                *command,
                "--export",
                export,
                "--out",
                out,
                "--s2c-header",
                header,
                "--s2c-source",
                source,
                "--states",
                STATES,
            ],
            cwd=s2c_equiv.ROOT,
            what="{} {} d2c".format(name, implementation),
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise s2c_equiv.EquivError(
                "{} {} d2c failed (exit {}):\n{}".format(
                    name, implementation, result.returncode, detail
                )
            )
        file_counts[implementation] = len(
            [path for path in out.rglob("*") if path.is_file()]
        )

    py_dir = WORK / name / "py"
    ts_dir = WORK / name / "ts"
    file_count, differences = s2c_equiv.compare_tree(py_dir, ts_dir)
    if file_counts["py"] != file_counts["ts"]:
        differences.append(
            "file count: python {} != TypeScript {}".format(
                file_counts["py"], file_counts["ts"]
            )
        )
    if differences:
        for difference in differences[:20]:
            print("  {}".format(difference), file=sys.stderr)
        print(
            "d2c-equiv: {}: {} inputs, {} files, {} differences".format(
                name, len(files), file_count, len(differences)
            )
        )
        return False
    print(
        "d2c-equiv: {}: {} inputs, {} files, 0 differences".format(
            name, len(files), file_count
        )
    )
    return True


def check_error_input(export):
    outcomes = []
    for implementation, command in (
        ("python", [sys.executable, PY_D2C]),
        ("typescript", ["node", TS_D2C]),
    ):
        out = WORK / "error-input" / implementation
        shutil.rmtree(out, ignore_errors=True)
        result = s2c_equiv.run(
            [
                *command,
                "--export",
                export,
                "--out",
                out,
                "--s2c-header",
                ERROR_HEADER,
                "--s2c-source",
                ERROR_SOURCE,
                "--states",
                STATES,
            ],
            cwd=s2c_equiv.ROOT,
            what="{} error input".format(implementation),
            check=False,
        )
        detail = (result.stderr or result.stdout).strip().lower()
        rejected = result.returncode != 0 and "d2c:" in detail
        outcomes.append((implementation, result.returncode, rejected))
    ok = all(rejected for _, _, rejected in outcomes)
    detail = ", ".join(
        "{} exit {}".format(name, code) for name, code, _ in outcomes
    )
    print(
        "d2c-equiv: error-input: both converters {} ({}); {}".format(
            "reject it" if ok else "DID NOT reject it",
            detail,
            "PASS" if ok else "FAIL",
        )
    )
    return ok


def main():
    try:
        gbs2 = s2c_equiv.ensure_gbs2_export()
        variants = [
            (name, s2c_equiv.ensure_variant_export(name))
            for name in s2c_equiv.variant_names()
        ]
        blank = s2c_equiv.ensure_blank_export()

        ok = True
        ok &= compare_set("gbs2", gbs2, s2c_equiv.scripts(gbs2))
        for name, export in variants:
            ok &= compare_set(
                "variant-" + name,
                export,
                s2c_equiv.scripts(export),
            )
        ok &= compare_set(
            "blank-product",
            blank,
            s2c_equiv.scripts(blank),
        )
        gamerom_files = sorted(
            s2c_equiv.scripts(gbs2)
            + [str(path) for path in s2c_equiv.GAMEROM_SRC.glob("*.s")]
        )
        ok &= compare_set("gamerom-scripts", gbs2, gamerom_files)
        test_files = sorted(
            str(path) for path in s2c_equiv.TEST_SCRIPTS.glob("*.s")
        )
        ok &= compare_set(
            "tests-scripts",
            gbs2,
            test_files,
            extra=["--bank", "s2c_far=2"],
        )
        ok &= check_error_input(gbs2)
        if not ok:
            print("d2c-equiv: FAIL", file=sys.stderr)
            return 1
        print("d2c-equiv: all sets equal")
        return 0
    except s2c_equiv.EquivError as exc:
        print("d2c-equiv: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
