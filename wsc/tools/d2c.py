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


def convert(export_dir, out_dir, s2c_header, s2c_source):
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
    write_build_include(out_dir, s2c_header.name, scripts, bank_symbols, sorted(scenes))
    stubs = write_stubs(out_dir, s2c_source)
    return len(scenes), len(scripts), len(stubs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", required=True, help="GB Studio export directory")
    parser.add_argument("--out", required=True, help="WSC build tree to write")
    parser.add_argument("--s2c-header", required=True, help="s2c generated header")
    parser.add_argument("--s2c-source", required=True, help="s2c generated source")
    args = parser.parse_args(argv)

    try:
        scenes, scripts, stubs = convert(
            args.export, args.out, Path(args.s2c_header), Path(args.s2c_source)
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
