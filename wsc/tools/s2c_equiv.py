#!/usr/bin/env python3
"""Compare the TypeScript s2c port with the Python oracle on every script set.

Runs both converters with the same arguments and compares every generated
file byte for byte, including the census. Exports are built with the normal CLI
export path when they are missing (gbs2, project variants, the blank product
test project). One deliberately broken input must be rejected by both.

Usage: s2c_equiv.py [--jobs N]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC_DIR = HERE.parent
ROOT = WSC_DIR.parent
BUILD = WSC_DIR / "build"
WORK = BUILD / "s2c-equiv"
EXPORT = BUILD / "export"
PY_S2C = HERE / "s2c.py"
TS_S2C = HERE / "s2c-ts.js"
BLANK_TEMPLATE = ROOT / "appData" / "templates" / "blank"
GBS2_TEMPLATE = ROOT / "appData" / "templates" / "gbs2"
ENGINE_INCLUDE = ROOT / "appData" / "engine" / "gbvm" / "include"
GAMEROM_SRC = WSC_DIR / "gamerom" / "src"
TEST_SCRIPTS = WSC_DIR / "tests" / "scripts"
ERROR_SCRIPT = WSC_DIR / "tests" / "s2c-equiv" / "error_unknown_macro.s"


class EquivError(Exception):
    pass


def run(argv, cwd=None, env=None, what=None, check=True):
    what = what or " ".join(str(arg) for arg in argv)
    result = subprocess.run(
        [str(arg) for arg in argv],
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise EquivError(
            "{} failed (exit {}):\n{}".format(
                what, result.returncode, detail
            )
        )
    return result


def export_project(project, destination):
    env = dict(os.environ)
    env["TEMPLATE"] = str(project)
    run(
        [WSC_DIR / "export" / "run.sh", destination],
        cwd=ROOT,
        env=env,
        what="export {}".format(project),
    )


def ensure_gbs2_export():
    ready = EXPORT / "src" / "data" / "scene_sample_town.c"
    if not ready.is_file():
        print("s2c-equiv: exporting gbs2", file=sys.stderr)
        run([WSC_DIR / "export" / "run.sh"], cwd=ROOT, what="gbs2 export")
    if not ready.is_file():
        raise EquivError("gbs2 export did not produce {}".format(ready))
    return EXPORT


def variant_names():
    directory = WSC_DIR / "oracle" / "variants"
    return sorted(path.stem for path in directory.glob("*.json"))


def ensure_variant_export(name):
    """Build a variant's WSC export the same way gbdiff does."""
    sys.path.insert(0, str(HERE))
    import gbdiff  # noqa: E402

    variant = gbdiff.load_variant({"variant": name})
    root = BUILD / "variants" / name
    project = root / "project"
    export = root / "export"
    stamp = root / "export.stamp"
    ready = export / "src" / "data" / "scene_sample_town.c"
    exported = ready.is_file()
    if (
        not exported
        or not stamp.is_file()
        or stamp.read_text().strip() != variant["digest"]
    ):
        print("s2c-equiv: exporting variant {}".format(name), file=sys.stderr)
        shutil.rmtree(project, ignore_errors=True)
        shutil.copytree(GBS2_TEMPLATE, project)
        gbdiff.apply_variant(project / "project", variant)
        root.mkdir(parents=True, exist_ok=True)
        export_project(project / "project.gbsproj", export)
        stamp.write_text(variant["digest"] + "\n")
    if not ready.is_file():
        raise EquivError("variant {} export has no scripts".format(name))
    return export


BLANK_SCENE_ID = "c30b1a9c-5e2f-4c7e-9a41-2f7b6de1c001"


def ensure_blank_export():
    """Recreate wsc/tests/product-blank's project and export it.

    The project is the blank template plus the first default empty scene, as
    in that test's build.sh. Keeping it here avoids running a full ROM build
    just to get the script set.
    """
    import json

    state = WORK / "blank"
    project = state / "project"
    scene = project / "project" / "scenes" / "blank" / "scene.gbsres"
    if not scene.is_file():
        print("s2c-equiv: creating blank test project", file=sys.stderr)
        shutil.rmtree(project, ignore_errors=True)
        state.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BLANK_TEMPLATE, project)
        settings_path = project / "project" / "settings.gbsres"
        settings = json.loads(settings_path.read_text())
        settings["startSceneId"] = BLANK_SCENE_ID
        settings["startX"] = 9
        settings["startY"] = 9
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        scene.parent.mkdir(parents=True, exist_ok=True)
        scene.write_text(
            json.dumps(
                {
                    "_resourceType": "scene",
                    "id": BLANK_SCENE_ID,
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
                },
                indent=2,
            )
            + "\n"
        )
    export = state / "export"
    ready = export / "src" / "data" / "script_engine_init.s"
    if not ready.is_file():
        export_project(project / "project.gbsproj", export)
    if not ready.is_file():
        raise EquivError("blank export did not produce scripts")
    return export


def scripts(export):
    return sorted(str(path) for path in (export / "src" / "data").glob("*.s"))


def compare_tree(left, right):
    left_files = {
        path.relative_to(left)
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right)
        for path in right.rglob("*")
        if path.is_file()
    }
    differences = []
    for relative in sorted(left_files | right_files):
        if relative not in left_files:
            differences.append("{}: missing from python output".format(relative))
            continue
        if relative not in right_files:
            differences.append("{}: missing from TypeScript output".format(relative))
            continue
        if (left / relative).read_bytes() != (right / relative).read_bytes():
            differences.append("{}: bytes differ".format(relative))
    return len(left_files), differences


def compare_set(name, include, files, extra=(), script_label=None):
    work = WORK / name
    py_dir = work / "py"
    ts_dir = work / "ts"
    shutil.rmtree(py_dir, ignore_errors=True)
    shutil.rmtree(ts_dir, ignore_errors=True)
    py_dir.mkdir(parents=True)
    ts_dir.mkdir(parents=True)
    py_census = py_dir / "census.txt"
    ts_census = ts_dir / "census.txt"

    run(
        [
            sys.executable,
            PY_S2C,
            "--include",
            include,
            "--out",
            py_dir,
            "--census",
            py_census,
            "--name",
            name,
            *extra,
            *files,
        ],
        cwd=ROOT,
        what="{} python s2c".format(name),
    )
    run(
        [
            "node",
            TS_S2C,
            "--include",
            include,
            "--out",
            ts_dir,
            "--census",
            ts_census,
            "--name",
            name,
            *extra,
            *files,
        ],
        cwd=ROOT,
        what="{} TypeScript s2c".format(name),
    )

    file_count, differences = compare_tree(py_dir, ts_dir)
    label = script_label or name
    if differences:
        for difference in differences[:20]:
            print("  {}".format(difference), file=sys.stderr)
        print(
            "s2c-equiv: {}: {} scripts, {} files, {} differences".format(
                label, len(files), file_count, len(differences)
            )
        )
        return False
    print(
        "s2c-equiv: {}: {} scripts, {} files, 0 differences".format(
            label, len(files), file_count
        )
    )
    return True


def check_error_input():
    work = WORK / "error-input"
    if not ERROR_SCRIPT.is_file():
        raise EquivError("missing error input {}".format(ERROR_SCRIPT))
    outcomes = []
    for implementation, command in (
        ("python", [sys.executable, PY_S2C]),
        ("typescript", ["node", TS_S2C]),
    ):
        out_dir = work / implementation
        shutil.rmtree(out_dir, ignore_errors=True)
        result = run(
            [
                *command,
                "--include",
                ENGINE_INCLUDE,
                "--out",
                out_dir,
                "--name",
                "error",
                ERROR_SCRIPT,
            ],
            cwd=ROOT,
            what="{} error input".format(implementation),
            check=False,
        )
        rejected = (
            result.returncode != 0
            and "error" in (result.stderr or result.stdout).lower()
        )
        outcomes.append((implementation, result.returncode, rejected))
    ok = all(rejected for _, _, rejected in outcomes)
    detail = ", ".join(
        "{} exit {}".format(name, code) for name, code, _ in outcomes
    )
    print(
        "s2c-equiv: error-input: both converters {} ({}); {}".format(
            "reject it" if ok else "DID NOT reject it", detail,
            "PASS" if ok else "FAIL",
        )
    )
    return ok


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        gbs2 = ensure_gbs2_export()
        variants = [(name, ensure_variant_export(name)) for name in variant_names()]
        blank = ensure_blank_export()

        ok = True
        ok &= compare_set("gbs2", str(gbs2 / "include"), scripts(gbs2))
        for name, export in variants:
            ok &= compare_set(
                "variant-" + name,
                str(export / "include"),
                scripts(export),
            )
        ok &= compare_set(
            "blank-product",
            str(blank / "include"),
            scripts(blank),
        )
        gamerom_files = sorted(
            scripts(gbs2)
            + [str(path) for path in GAMEROM_SRC.glob("*.s")]
        )
        ok &= compare_set(
            "gamerom-scripts",
            str(gbs2 / "include"),
            gamerom_files,
        )
        test_files = sorted(str(path) for path in TEST_SCRIPTS.glob("*.s"))
        ok &= compare_set(
            "tests-scripts",
            str(ENGINE_INCLUDE),
            test_files,
            extra=["--bank", "s2c_far=2"],
        )
        ok &= check_error_input()
        if not ok:
            print("s2c-equiv: FAIL", file=sys.stderr)
            return 1
        print("s2c-equiv: all sets equal")
        return 0
    except EquivError as exc:
        print("s2c-equiv: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
