#!/usr/bin/env python3
"""Rewrite GB Studio's exported data C for the WonderSwan Color.

The GB Studio compiler emits SDCC/GBDK data: near ``const`` objects, ``BANKREF``
markers and ``far_ptr_t`` initializers built from ``__bank_`` symbols. On WSC
all scene data must live in far ROM and script references must become full far
pointers into the converter's script banks.

This is a post-processor: it works on kinds of construct in the exported C
(object definitions, extern declarations, far-pointer initializers, bank
markers), not on a list of file names. Output goes to a separate build tree;
the GB Studio export is never modified.

Usage:
    d2c.py --export DIR --out DIR --s2c-header FILE --s2c-source FILE
"""

import argparse
import re
import sys
from pathlib import Path

# File-scope object definitions: const/static const ...
DEFINITION_RE = re.compile(r"^(?P<indent>\s*)(?P<pre>static\s+)?const\s+(?P<rest>.+)$")

# Pointer arrays such as `const metasprite_t * const foo[]` and
# `static const unsigned char* const order1[]`. Both the pointee and the
# pointer array itself have to be far, because the pointee lives in far ROM.
PTR_ARRAY_RE = re.compile(
    r"^(?P<pre>\s*(?:static\s+)?const)\s+(?P<base>.+?)\s*\*\s*const\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\[\s*\]\s*="
)

# `extern const ...` declarations in generated headers must carry the same
# named address space as their definitions.
EXTERN_CONST_RE = re.compile(r"^(?P<indent>\s*)extern\s+const\s+(?P<rest>.+)$")

BANKREF_RE = re.compile(r"^\s*BANKREF\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;?\s*$")
BANKREF_EXTERN_RE = re.compile(
    r"^\s*BANKREF_EXTERN\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;?\s*$"
)
PRAGMA_BANK_RE = re.compile(r"^\s*#pragma\s+bank\b.*$")
BANK_OBJECT_RE = re.compile(
    r"^\s*(?:extern\s+)?const\s+void\s+(?:__at\s*\([^)]*\)\s+)?__bank_\w+\s*;\s*$"
)
MUTE_MASK_RE = re.compile(
    r"^\s*void\s+AT\s*\([^)]*\)\s+__mute_mask_\w+\s*;\s*$"
)

TO_FAR_PTR_RE = re.compile(r"TO_FAR_PTR_T\s*\(\s*([A-Za-z_]\w*)\s*\)")
SCENE_DEF_RE = re.compile(r"^\s*const\s+(?:__far\s+)?struct\s+scene_t\s+([A-Za-z_]\w*)\s*=")
SCRIPT_DEF_RE = re.compile(
    r"^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_BANK\s+(\d+)\s*$", re.M
)
SCRIPT_OFF_RE = re.compile(
    r"^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_OFFSET\s+0x([0-9A-Fa-f]+)\s*$", re.M
)
SCRIPT_SIZE_RE = re.compile(
    r"^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_SIZE\s+0x([0-9A-Fa-f]+)\s*$", re.M
)
BANK_DECL_RE = re.compile(
    r"^extern\s+const\s+uint8_t\s+S2C_FAR\s+(s2c_bank\d+)\s*\[\s*\]\s*;$", re.M
)


class ConvertError(Exception):
    pass


def read_scripts(header_path):
    """Return {script name: (bank, offset, size)} from an s2c header."""
    banks = {}
    offsets = {}
    sizes = {}
    try:
        text = header_path.read_text()
    except OSError as exc:
        raise ConvertError("cannot read {}: {}".format(header_path, exc)) from exc
    for name, value in SCRIPT_DEF_RE.findall(text):
        banks[name] = int(value)
    for name, value in SCRIPT_OFF_RE.findall(text):
        offsets[name] = int(value, 16)
    for name, value in SCRIPT_SIZE_RE.findall(text):
        sizes[name] = int(value, 16)
    scripts = {}
    for upper, bank in banks.items():
        if upper not in offsets or upper not in sizes:
            raise ConvertError("incomplete s2c macros for {}".format(upper))
        scripts[upper.lower()] = (bank, offsets[upper], sizes[upper])
    return scripts


def read_bank_symbols(header_path):
    try:
        text = header_path.read_text()
    except OSError as exc:
        raise ConvertError("cannot read {}: {}".format(header_path, exc)) from exc
    return sorted(set(BANK_DECL_RE.findall(text)), key=lambda n: int(n[8:]))


def far_data_def(line):
    """Turn one file-scope const definition into far ROM data."""
    match = PTR_ARRAY_RE.match(line)
    if match:
        head = "{pre} __far {base} * const __far {name}[] =".format(
            **match.groupdict()
        )
        return head + line[match.end():]

    match = DEFINITION_RE.match(line)
    if not match:
        return line
    rest = match.group("rest")
    # Leave declarations such as `const void __at(...) __bank_x;` to the
    # bank-marker rule and anything that is not a definition alone.
    if "__bank_" in rest or rest.startswith("void "):
        return line
    if "=" not in rest and "[" not in rest:
        return line
    if "__far" in rest.split("=", 1)[0]:
        return line
    return "{indent}{pre}const __far {rest}".format(
        indent=match.group("indent"), pre=match.group("pre") or "",
        rest=match.group("rest"))


def far_data_extern(line):
    match = EXTERN_CONST_RE.match(line)
    if not match:
        return line
    rest = match.group("rest")
    if "__bank_" in rest or rest.startswith("void "):
        return line
    if "__far" in rest:
        return line
    return "{indent}extern const __far {rest}".format(
        indent=match.group("indent"), rest=match.group("rest"))


def process_source(text, scripts, is_header):
    """Rewrite one generated C source or header. Returns (text, scene names)."""
    scenes = []
    out = []
    for line in text.splitlines():
        if BANKREF_RE.match(line) or BANKREF_EXTERN_RE.match(line):
            continue
        if (PRAGMA_BANK_RE.match(line) or BANK_OBJECT_RE.match(line)
                or MUTE_MASK_RE.match(line)):
            continue

        def script_ptr(match):
            name = match.group(1)
            if name not in scripts:
                return match.group(0)
            bank, offset, _size = scripts[name]
            return (
                "{{ .bank = {bank}, .ptr = (const void __far *)"
                "(s2c_bank{bank} + 0x{offset:04X}) }}"
            ).format(bank=bank, offset=offset)

        line = TO_FAR_PTR_RE.sub(script_ptr, line)
        # The compiler emits `{ NULL, NULL }` for an empty cgb_tileset.
        # A far_ptr_t's first member is the bank byte, so the pointer NULL
        # must not be used as its initializer.
        line = line.replace("{ NULL, NULL }", "{ 0, NULL }")

        if not is_header:
            scene = SCENE_DEF_RE.match(line)
            if scene:
                scenes.append(scene.group(1))
            line = far_data_def(line)
        else:
            line = far_data_extern(line)
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), scenes


def write_build_include(out_dir, s2c_header_name, scripts, bank_symbols, scenes):
    include = out_dir / "include"
    include.mkdir(parents=True, exist_ok=True)

    lines = [
        "/* Generated by wsc/tools/d2c.py. Do not edit. */",
        "#ifndef D2C_SCRIPTS_H",
        "#define D2C_SCRIPTS_H",
        "",
        '#include "{}"'.format(s2c_header_name),
        "",
    ]
    for name in sorted(scripts):
        bank, offset, _size = scripts[name]
        lines.append(
            "#define S2C_FPTR_{name} {{ .bank = {bank}, .ptr = "
            "(const void __far *)(s2c_bank{bank} + 0x{offset:04X}) }}".format(
                name=name, bank=bank, offset=offset
            )
        )
    lines.extend(["", "#endif", ""])
    (include / "d2c_scripts.h").write_text("\n".join(lines))

    manifest = [
        "/* Generated by wsc/tools/d2c.py. Do not edit. */",
        "#ifndef D2C_MANIFEST_H",
        "#define D2C_MANIFEST_H",
        "",
        "#include \"gbs_types.h\"",
        "",
        "/* Script banks are numbered from 1; slot 0 in a bank table means",
        " * \"no script\" and is never one of these entries. */",
        "#define D2C_BANK_COUNT {}".format(len(bank_symbols)),
        "#define D2C_BANK_LIST {}".format(", ".join(bank_symbols)),
        "#define D2C_SCENE_COUNT {}".format(len(scenes)),
    ]
    for scene in scenes:
        manifest.append("extern const __far struct scene_t {};".format(scene))
    manifest.append("#define D2C_SCENE_LIST {}".format(
        ", ".join("&" + scene for scene in scenes)
    ))
    manifest.extend(["", "#endif", ""])
    (include / "d2c_manifest.h").write_text("\n".join(manifest))


def copy_transform(export_data, out_data, scripts, is_header):
    scenes = []
    for path in sorted(export_data.rglob("*")):
        if path.suffix not in (".c", ".h"):
            continue
        rel = path.relative_to(export_data)
        dest = out_data / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = path.read_text()
        except OSError as exc:
            raise ConvertError("cannot read {}: {}".format(path, exc)) from exc
        text, found = process_source(text, scripts, is_header)
        if not is_header:
            header = '#include "d2c_scripts.h"\n'
            if header not in text:
                text = header + text
            scenes.extend(found)
        dest.write_text(text)
    return scenes


def transform_huge_headers(export_include, out_include):
    """Make the hUGE data pointer members far in the copied WSC headers."""
    for name in ("hUGEDriver.h", "hUGEDriverRoutines.h"):
        src = export_include / name
        if not src.is_file():
            continue
        text = src.read_text()
        text = text.replace(
            "const unsigned char * subpattern;",
            "const unsigned char __far * subpattern;",
        )
        text = text.replace(
            "const unsigned char * order_cnt;",
            "const unsigned char __far * order_cnt;",
        )
        text = text.replace(
            "const unsigned char ** order1, ** order2, ** order3, ** order4;",
            "const unsigned char __far * const __far * order1,\n"
            "    * const __far * order2, * const __far * order3,\n"
            "    * const __far * order4;",
        )
        text = text.replace(
            "const hUGEDutyInstr_t * duty_instruments;",
            "const hUGEDutyInstr_t __far * duty_instruments;",
        )
        text = text.replace(
            "const hUGEWaveInstr_t * wave_instruments;",
            "const hUGEWaveInstr_t __far * wave_instruments;",
        )
        text = text.replace(
            "const hUGENoiseInstr_t * noise_instruments;",
            "const hUGENoiseInstr_t __far * noise_instruments;",
        )
        text = text.replace(
            "const hUGERoutine_t ** routines;",
            "const hUGERoutine_t __far * routines;",
        )
        text = text.replace(
            "const unsigned char * waves;",
            "const unsigned char __far * waves;",
        )
        text = text.replace(
            "static const hUGERoutine_t routines[]",
            "static const __far hUGERoutine_t routines[]",
        )
        (out_include / name).write_text(text)


def parse_constants(include_dir):
    """Read NAME = VALUE lines from the exported .i files."""
    values = {}
    for path in sorted(include_dir.rglob("*.i")):
        try:
            text = path.read_text()
        except OSError as exc:
            raise ConvertError("cannot read {}: {}".format(path, exc)) from exc
        for line in text.splitlines():
            m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(-?0x[0-9A-Fa-f]+|-?\d+)\s*$", line)
            if m:
                values[m.group(1)] = int(m.group(2), 0)
    return values


def eval_value(token, constants):
    token = token.strip()
    if token.startswith("."):
        token = token[1:]
    if token in constants:
        return constants[token]
    try:
        return int(token, 0)
    except ValueError:
        return 0


def parse_engine_init(path, constants):
    """Extract the bootstrap data prefix and the platform globals script."""
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise ConvertError("cannot read {}: {}".format(path, exc)) from exc

    data = {}
    i = 0
    while i < len(lines):
        m = re.match(
            r"^_(start_scene_x|start_scene_y|start_scene_dir|start_scene|"
            r"start_player_move_speed|start_player_anim_tick|ui_fonts)::\s*(.*)$",
            lines[i],
        )
        if not m:
            i += 1
            continue
        name, rest = m.group(1), m.group(2).strip()
        if name == "ui_fonts":
            fonts = []
            j = i + 1
            while j < len(lines):
                fm = re.match(r"\s*IMPORT_FAR_PTR_DATA\s+_(\w+)\s*$", lines[j])
                if fm:
                    fonts.append(fm.group(1))
                    j += 1
                    continue
                if lines[j].strip() and not lines[j].lstrip().startswith(";"):
                    break
                j += 1
            data["ui_fonts"] = fonts
            i = j
            continue
        if not rest and i + 1 < len(lines):
            rest = lines[i + 1].strip()
        if name == "start_scene":
            fm = re.match(r"IMPORT_FAR_PTR_DATA\s+_(\w+)", rest)
            data[name] = fm.group(1) if fm else None
        elif name == "start_scene_dir":
            value = re.sub(r"^\.db\s+", "", rest).strip()
            data[name] = value.lstrip(".")
        else:
            dm = re.match(r"\.d[bw]\s+(-?0x[0-9A-Fa-f]+|-?\d+)", rest)
            data[name] = int(dm.group(1), 0) if dm else 0
        i += 1

    globals_ = []
    last = None
    in_init = False
    for line in lines:
        if line.strip().startswith("_script_engine_init::"):
            in_init = True
            continue
        if not in_init:
            continue
        im = re.match(r"\s*\.R_INT(8|16)\s+(\S+)", line)
        if im:
            last = (int(im.group(1)), eval_value(im.group(2), constants))
            continue
        sm = re.match(
            r"\s*\.R_REF_MEM_SET\s+\.MEM_I(8|16)\s*,\s*_(\w+)", line
        )
        if sm and last is not None:
            size = int(sm.group(1))
            globals_.append((sm.group(2), size, last[1]))
            last = None
    data["globals"] = globals_
    return data


def parse_states(path):
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise ConvertError("cannot read {}: {}".format(path, exc)) from exc
    tables = {"start": [], "update": []}
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("_state_start_fns::"):
            current = "start"
            continue
        if stripped.startswith("_state_update_fns::"):
            current = "update"
            continue
        m = re.match(r"IMPORT_FAR_PTR\s+_(\w+)", stripped)
        if m and current:
            tables[current].append(m.group(1))
    return tables


def write_bootstrap(out_dir, init_data, s2c_header_name, scenes):
    out = out_dir / "bootstrap.c"
    start_scene = init_data.get("start_scene") or "scene_logo"
    if start_scene not in scenes:
        raise ConvertError("start scene {} is not an exported scene".format(start_scene))
    lines = [
        "/* Generated by wsc/tools/d2c.py from script_engine_init.s. Do not edit. */",
        '#include <stdint.h>',
        '#include "gbdk/platform.h"',
        '#include "gbs_types.h"',
        '#include "data/data_bootstrap.h"',
    ]
    for font in init_data.get("ui_fonts", []):
        lines.append('#include "data/{}.h"'.format(font))
    lines.extend([
        "",
        "/* Defaults; the test image overrides the start scene at run time. */",
        "#ifndef BOOT_START_SCENE",
        "#define BOOT_START_SCENE {}".format(start_scene),
        "#endif",
        "#ifndef BOOT_START_X",
        "#define BOOT_START_X {}".format(init_data.get("start_scene_x", 0)),
        "#endif",
        "#ifndef BOOT_START_Y",
        "#define BOOT_START_Y {}".format(init_data.get("start_scene_y", 0)),
        "#endif",
        "#ifndef BOOT_START_DIR",
        "#define BOOT_START_DIR {}".format(init_data.get("start_scene_dir", "DIR_RIGHT")),
        "#endif",
        "",
        "extern const __far struct scene_t BOOT_START_SCENE;",
        "",
        "/* These are not const so a platform can select a start scene at run time",
        " * (the WSC test image writes a boot id into its ROM). */",
        "INT16 start_scene_x = BOOT_START_X;",
        "INT16 start_scene_y = BOOT_START_Y;",
        "direction_e start_scene_dir = BOOT_START_DIR;",
        "far_ptr_t start_scene = {",
        "    .bank = 0,",
        "    .ptr = (const void __far *)&BOOT_START_SCENE",
        "};",
        "const __far UBYTE start_player_move_speed = {};".format(
            init_data.get("start_player_move_speed", 32)
        ),
        "const __far UBYTE start_player_anim_tick = {};".format(
            init_data.get("start_player_anim_tick", 15)
        ),
        "",
        "const __far far_ptr_t ui_fonts[] = {",
    ])
    for font in init_data.get("ui_fonts", []):
        lines.append("    TO_FAR_PTR_T({}),".format(font))
    lines.extend([
        "};",
        "",
        "/* Implemented by the platform's boot table. */",
        "void wsc_boot_select(far_ptr_t *scene, INT16 *x, INT16 *y);",
        "",
        "/* Platform globals assigned by the script_engine_init VM routine. They",
        " * are weak so engine sources that define one keep their definition. */",
    ])
    for name, size, value in init_data.get("globals", []):
        ctype = "WORD" if size == 16 else "UBYTE"
        lines.append("__attribute__((weak)) {} {};".format(ctype, name))
    lines.extend(["", "void bootstrap_init(void) {"])
    for name, size, value in init_data.get("globals", []):
        lines.append("    {} = {};".format(name, value))
    lines.extend([
        "    wsc_boot_select(&start_scene, &start_scene_x, &start_scene_y);",
        "}",
        "",
        "/* VM_LOCK, VM_RAISE(EXCEPTION_RESET, 0): platform globals are set by",
        " * bootstrap_init() instead of the GB script init routine. */",
        "const UBYTE bootstrap_script[] = { 0x25, 0x27, 0x00, 0x01, 0x00 };",
        "",
    ])
    out.write_text("\n".join(lines))

    # The runtime selector assigns these through pointers, so their public
    # declarations cannot stay const.
    header = out_dir / "include" / "data" / "data_bootstrap.h"
    if header.is_file():
        text = header.read_text()
        for decl in (
            "INT16 start_scene_x;",
            "INT16 start_scene_y;",
            "direction_e start_scene_dir;",
            "far_ptr_t start_scene;",
        ):
            for prefix in ("extern const __far ", "extern const "):
                text = text.replace(prefix + decl, "extern " + decl)
        header.write_text(text)


def write_states(out_dir, tables, implemented):
    out = out_dir / "states.c"
    count = len(tables["start"])
    if count != len(tables["update"]):
        raise ConvertError("state start/update tables differ in length")

    def emit_table(kind, names):
        result = ["const state_fn_t state_{}_fns[] = {{".format(kind)]
        for name in names:
            state = name[:-len("_init")] if name.endswith("_init") else (
                name[:-len("_update")] if name.endswith("_update") else name)
            if state in implemented:
                result.append("    {},".format(name))
            else:
                result.append("    state_unavailable,")
        result.append("};")
        return result

    lines = [
        "/* Generated by wsc/tools/d2c.py from states_ptrs.s. Do not edit. */",
        '#include "gbdk/platform.h"',
        '#include "gbs_types.h"',
        '#include "data/scene_types.h"',
        '#include "data_manager.h"',
        '#include "states_caller.h"',
        '#include "states/topdown.h"',
        '#include "states/platform.h"',
        '#include "states/shmup.h"',
        '#include "states/pointnclick.h"',
        "",
        "typedef void (*state_fn_t)(void);",
        "",
        "static void state_unavailable(void) {",
        "}",
        "",
    ]
    lines.extend(emit_table("start", tables["start"]))
    lines.extend(emit_table("update", tables["update"]))
    lines.extend([
        "",
        "void state_init(void) {",
        "    if (scene_type < {}) state_start_fns[scene_type]();".format(count),
        "}",
        "",
        "void state_update(void) {",
        "    if (scene_type < {}) state_update_fns[scene_type]();".format(count),
        "}",
        "",
    ])
    out.write_text("\n".join(lines))


def write_stubs(out_dir, s2c_source):
    """Define the engine RAM globals that scripts reach through vm_ram_syms[]."""
    text = s2c_source.read_text()
    names = re.findall(r"^extern uint8_t ([A-Za-z_]\w*)\[\];$", text, re.M)
    seen = set()
    lines = [
        "/* Generated by wsc/tools/d2c.py. Do not edit. */",
        "/* Test-only storage for engine globals named by vm_ram_syms[]. */",
        "#include <stdint.h>",
        "",
    ]
    for name in sorted(names):
        if name in seen:
            continue
        seen.add(name)
        lines.append("uint8_t {}[4];".format(name))
    lines.append("")
    (out_dir / "data_stubs.c").write_text("\n".join(lines))
    return sorted(seen)


def convert(export_dir, out_dir, s2c_header, s2c_source, states=None):
    export_dir = Path(export_dir)
    out_dir = Path(out_dir)
    export_data = export_dir / "src" / "data"
    export_include = export_dir / "include"
    if not export_data.is_dir():
        raise ConvertError("export data directory {} is missing".format(export_data))
    if not s2c_header.is_file():
        raise ConvertError("s2c header {} is missing".format(s2c_header))
    if not s2c_source.is_file():
        raise ConvertError("s2c source {} is missing".format(s2c_source))

    scripts = read_scripts(s2c_header)
    bank_symbols = read_bank_symbols(s2c_header)
    if not bank_symbols:
        raise ConvertError("no s2c bank arrays declared in {}".format(s2c_header))

    out_data = out_dir / "data"
    out_include = out_dir / "include"
    out_include.mkdir(parents=True, exist_ok=True)

    scenes = copy_transform(export_data, out_data, scripts, is_header=False)
    copy_transform(export_include / "data", out_include / "data", scripts,
                   is_header=True)

    transform_huge_headers(export_include, out_include)
    scenes = sorted(scenes)
    write_build_include(out_dir, s2c_header.name, scripts, bank_symbols, scenes)
    stubs = write_stubs(out_dir, s2c_source)

    init_path = export_data / "script_engine_init.s"
    states_path = export_data / "states_ptrs.s"
    if init_path.is_file():
        constants = parse_constants(export_include)
        init_data = parse_engine_init(init_path, constants)
        write_bootstrap(out_dir, init_data, s2c_header.name, set(scenes))
    if states_path.is_file():
        implemented = set((states or "topdown").split(","))
        write_states(out_dir, parse_states(states_path), implemented)
    return len(scenes), len(scripts), len(stubs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", required=True, help="GB Studio export directory")
    parser.add_argument("--out", required=True, help="WSC build tree to write")
    parser.add_argument("--s2c-header", required=True, help="s2c generated header")
    parser.add_argument("--s2c-source", required=True, help="s2c generated source")
    parser.add_argument("--states", default="topdown",
                        help="comma-separated state modules compiled into the ROM")
    args = parser.parse_args(argv)

    try:
        scenes, scripts, stubs = convert(
            args.export, args.out, Path(args.s2c_header), Path(args.s2c_source),
            args.states,
        )
    except ConvertError as exc:
        print("d2c: {}".format(exc), file=sys.stderr)
        return 1
    print(
        "d2c: {} scenes, {} scripts, {} RAM stubs".format(scenes, scripts, stubs)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
