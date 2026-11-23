#!/usr/bin/env python3
"""Generate the portable GBVM interpreter dispatcher and test bytecode macros.

Reads the instruction table (script_cmds[]), the handler prototypes and the
assembler macros in vm.i.  Writes:

  appData/engine/gbvm/src/core/vm_dispatch.c   (host VM_STEP dispatcher)
  wsc/vmtest/vm_bytecode.h                     (C equivalents of vm.i macros)

Every handler declared in engine/gbvm/include/vm*.h is parsed and checked
against script_cmds[] and vm.i.  The dispatcher emits all of them for the
WonderSwan build.  The host build only links the core vm.h handlers, so the
engine handler cases are compiled under __ia16__.  Handlers for hardware the
WSC does not have (SGB, SIO/link, GB Printer, RTC) and the UI/dialogue set
stay "unimplemented opcode"; see EXCLUDED_HEADERS.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "appData" / "engine" / "gbvm"
INCLUDE = ENGINE / "include"
DISPATCH = ENGINE / "src" / "core" / "vm_dispatch.c"
BYTECODE = ROOT / "wsc" / "vmtest" / "vm_bytecode.h"

HOST_EXCLUDED = {"vm_call_native", "vm_asm"}

# Explicit exclusion list: opcodes handled by these headers stay
# "unimplemented opcode".  SGB, SIO/link, GB Printer and RTC have no WSC
# hardware; vm_ui is the next porting chunk.
EXCLUDED_HEADERS = {
    "vm_gbprinter.h": "GB Printer",
    "vm_rtc.h": "RTC",
    "vm_sgb.h": "SGB",
    "vm_sio.h": "SIO/link",
    "vm_ui.h": "UI/dialogue (next chunk)",
}

# Pointer operands that are (bank, C data) pairs, not script bytecode.  They
# are resolved through the converter's vm_far_data[] table (C09 list).
FAR_DATA_PARAMS = {
    "vm_actor_emote": {"emote_tiles"},
    "vm_actor_set_spritesheet": {"spritesheet"},
    "vm_actor_replace_tile": {"tileset"},
    "vm_replace_tile": {"tileset"},
    "vm_replace_tile_xy": {"tileset"},
    "vm_load_tileset": {"background"},
    "vm_music_play": {"track"},
    "vm_sfx_play": {"offset"},
    "vm_projectile_load_type": {"projectile_def"},
}

ONE_BYTE_TYPES = {"UBYTE", "UINT8", "INT8", "BYTE"}
SIGNED_ONE_BYTE = {"INT8", "BYTE"}
TWO_BYTE_SIGNED = {"INT16"}
TWO_BYTE_UNSIGNED = {"UWORD", "UINT16"}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def parse_script_cmds(path):
    """Return [(opcode, handler-or-None, args_len), ...]."""
    entries = []
    found = False
    for line in path.read_text().splitlines():
        if "const SCRIPT_CMD script_cmds[]" in line:
            found = True
            continue
        if not found:
            continue
        if re.match(r"\s*\};\s*$", line):
            break
        m = re.match(
            r"\s*\{\s*([A-Za-z_]\w*)\s*,\s*BANK\(\w+\)\s*,\s*(\d+)\s*\}", line
        )
        if m:
            entries.append((len(entries) + 1, m.group(1), int(m.group(2))))
            continue
        if re.match(r"\s*\{\s*0\s*,\s*0\s*,\s*0\s*\}", line):
            entries.append((len(entries) + 1, None, 0))
    return entries


def parse_prototypes(text):
    """Map function name -> parameter list text."""
    text = strip_comments(text)
    pattern = re.compile(
        r"([A-Za-z_][A-Za-z0-9_ \t*]*?)\b(vm_[a-z0-9_]+)\s*\(([^;{}]*?)\)"
        r"\s*(?:OLDCALL|NONBANKED|BANKED|NAKED|PRESERVES_REGS\([^)]*\)|\s)*;",
        re.S,
    )
    protos = {}
    for m in pattern.finditer(text):
        protos[m.group(2)] = m.group(3).strip()
    return protos


def parse_vm_i(path):
    """Return (op constants, macros, opcode -> [(name, byte_sizes)])."""
    text = strip_comments(path.read_text())
    consts = {}
    for m in re.finditer(r"^\s*(OP_[A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text, re.M):
        consts[m.group(1)] = int(m.group(2), 0)

    macros = []
    for m in re.finditer(
        r"^[ \t]*\.macro[ \t]+([A-Za-z0-9_.]+)[ \t]*,?[ \t]*(.*)$", text, re.M
    ):
        name = m.group(1)
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        end = re.search(r"^[ \t]*\.endm", text[m.end():], re.M)
        body = text[m.end(): m.end() + end.start()] if end else ""
        macros.append((name, params, body))

    by_opcode = {}
    for name, params, body in macros:
        terms, byte_sizes, only_db = [], [], True
        for line in body.splitlines():
            s = line.strip()
            if not s or s.startswith(";"):
                continue
            if s.startswith(".db"):
                line_terms = [t.strip() for t in s[3:].split(",") if t.strip()]
                terms.extend(line_terms)
                byte_sizes.extend([1] * len(line_terms))
            elif s.startswith(".dw"):
                line_terms = [t.strip() for t in s[3:].split(",") if t.strip()]
                terms.extend(line_terms)
                byte_sizes.extend([2] * len(line_terms))
                only_db = False
            else:
                only_db = False
        if not terms or terms[0] not in consts:
            continue
        opcode = consts[terms[0]]
        by_opcode.setdefault(opcode, []).append(
            (name, opcode, byte_sizes[1:], terms[1:], params, only_db)
        )
    return consts, macros, by_opcode


def split_params(text):
    if text.strip() in ("", "void"):
        return []
    return [p.strip() for p in re.split(r",", text) if p.strip()]


def param_info(param, enums):
    """Return (name, kind, size) for one C parameter declaration."""
    m = re.match(r"(.*?)([A-Za-z_]\w*)\s*$", param, re.S)
    if not m:
        return param.strip(), "u16", 2
    type_part, name = m.group(1).strip(), m.group(2)
    if "*" in type_part:
        return name, "ptr", 2
    base = re.sub(r"\b(const|volatile)\b", "", type_part)
    base = base.split()[0] if base.split() else ""
    if base in ONE_BYTE_TYPES:
        return name, "i8" if base in SIGNED_ONE_BYTE else "u8", 1
    if base in TWO_BYTE_SIGNED:
        return name, "i16", 2
    if base in TWO_BYTE_UNSIGNED:
        return name, "u16", 2
    if base in enums:
        return name, "u8", 1
    return name, "u16", 2


def enum_names(text):
    text = strip_comments(text)
    return {
        m.group(2)
        for m in re.finditer(
            r"typedef\s+enum[^{]*\{(.*?)\}\s*(\w+)\s*;", text, re.S
        )
    }


def parameter_sizes(params, enums):
    """Sizes (and kinds) of the operands after THIS, dummies removed."""
    infos = [param_info(p, enums) for p in params]
    this_index = next(
        (i for i, p in enumerate(params) if re.search(r"\bTHIS\b", p)), None
    )
    if this_index is None:
        return [], []
    operands = [
        (p, info)
        for p, info in zip(params[this_index + 1:], infos[this_index + 1:])
        if not info[0].startswith("dummy")
    ]
    return [p for p, _ in operands], [info for _, info in operands]


def all_header_text():
    return "\n".join(p.read_text() for p in sorted(INCLUDE.glob("*.h")))


def load():
    entries = parse_script_cmds(ENGINE / "src" / "core" / "vm_instructions.c")
    header_text = all_header_text()
    protos = {}
    handler_header = {}
    for path in sorted(INCLUDE.glob("*.h")):
        for name, params in parse_prototypes(path.read_text()).items():
            protos[name] = params
            handler_header[name] = path.name
    vmh_protos = parse_prototypes((INCLUDE / "vm.h").read_text())
    core_handlers = set(vmh_protos) - HOST_EXCLUDED
    consts, macros, vm_i = parse_vm_i(INCLUDE / "vm.i")
    enums = enum_names(header_text)
    return (entries, protos, core_handlers, handler_header, consts, macros,
            vm_i, enums)


def validate(entries, protos, vm_i, enums):
    args_mismatches = 0
    vm_i_mismatches = 0

    def size_of(info):
        name, kind, size = info
        return size

    for opcode, handler, args_len in entries:
        if handler is None:
            continue
        proto = protos.get(handler)
        if proto is None:
            print(
                f"missing prototype for {handler} (opcode 0x{opcode:02X})",
                file=sys.stderr,
            )
            args_mismatches += 1
            continue
        params, infos = parameter_sizes(split_params(proto), enums)
        sizes = [size_of(i) for i in infos]
        if sum(sizes) != args_len:
            print(
                f"args_len mismatch opcode 0x{opcode:02X} {handler}: "
                f"prototype {sum(sizes)} bytes, table {args_len}",
                file=sys.stderr,
            )
            args_mismatches += 1
        reversed_sizes = list(reversed(sizes))
        for name, _opcode, byte_sizes, _terms, _params, _only_db in vm_i.get(opcode, []):
            if sum(reversed_sizes) != sum(byte_sizes):
                print(
                    f"vm.i mismatch opcode 0x{opcode:02X} {handler}: "
                    f"prototype {sum(reversed_sizes)} bytes, {name} "
                    f"{sum(byte_sizes)} bytes",
                    file=sys.stderr,
                )
                vm_i_mismatches += 1
    return args_mismatches, vm_i_mismatches


def fetch_code(infos):
    lines = []
    for name, kind, _size in reversed(infos):
        if kind == "ptr":
            lines.append(f"    UWORD a_{name}_off = vm_fetch16(&p);")
        elif kind == "u8":
            lines.append(f"    UBYTE a_{name} = vm_fetch8(&p);")
        elif kind == "i8":
            lines.append(f"    INT8 a_{name} = (INT8)vm_fetch8(&p);")
        elif kind == "i16":
            lines.append(f"    INT16 a_{name} = (INT16)vm_fetch16(&p);")
        else:
            lines.append(f"    UWORD a_{name} = vm_fetch16(&p);")
    return lines


def generate_dispatch(entries, protos, core_handlers, handler_header, enums):
    engine_headers = sorted({
        handler_header[handler]
        for _opcode, handler, _args_len in entries
        if handler is not None
        and handler in protos
        and handler not in core_handlers
        and handler not in HOST_EXCLUDED
        and handler_header.get(handler) not in EXCLUDED_HEADERS
    })

    out = [
        "/* Generated by wsc/tools/gen_dispatch.py. Do not edit. */",
        "/* Portable GBVM instruction dispatcher for the host and WonderSwan. */",
        "#if !(defined(__SDCC) && defined(NINTENDO))",
        "",
        "#if !defined(__ia16__)",
        "#include <stdio.h>",
        "#endif",
        "",
        '#include "vm.h"',
    ]
    if engine_headers:
        out.append("")
        out.append("#if defined(__ia16__) && defined(GBVM_ENGINE_HANDLERS)")
        for header in engine_headers:
            out.append(f'#include "{header}"')
        out.append("#endif")
    out.extend([
        "",
        "UBYTE vm_last_unimplemented_opcode;",
        "",
        "static UWORD vm_fetch16(const UBYTE VM_FAR **p) {",
        "    UWORD value = (UWORD)((*p)[0] << 8) | (*p)[1];",
        "    *p += 2;",
        "    return value;",
        "}",
        "",
        "static UBYTE vm_fetch8(const UBYTE VM_FAR **p) {",
        "    return *(*p)++;",
        "}",
        "",
        "UBYTE vm_dispatch_step(SCRIPT_CTX *CTX) {",
        "    UBYTE op = *CTX->PC;",
        "    if (op == 0) {",
        "        return 0;",
        "    }",
        "    switch (op) {",
    ])

    for opcode, handler, _args_len in entries:
        if handler is None or handler in HOST_EXCLUDED:
            continue
        header = handler_header.get(handler)
        if header in EXCLUDED_HEADERS:
            continue
        if handler not in protos:
            continue
        wrapped = handler not in core_handlers
        params = split_params(protos[handler])
        operands, infos = parameter_sizes(params, enums)
        far_data_params = FAR_DATA_PARAMS.get(handler, set())
        infos = [
            (name, "ptr" if name in far_data_params else kind, size)
            for name, kind, size in infos
        ]
        far_names = {
            info[0]
            for p, info in zip(operands, infos)
            if info[1] == "ptr" and "VM_FAR" in p
        }
        before_this = []
        this_index = next(
            (i for i, p in enumerate(params) if re.search(r"\bTHIS\b", p)), None
        )
        has_this = this_index is not None
        if has_this:
            before_this = ["0"] * this_index
        bank_name = next(
            (info[0] for info in infos if info[0] == "bank" and info[1] == "u8"),
            None,
        )
        bank_expr = f"a_{bank_name}" if bank_name else "CTX->bank"

        if wrapped:
            out.append("#if defined(__ia16__) && defined(GBVM_ENGINE_HANDLERS)")
        out.append(f"      case 0x{opcode:02X}: {{ /* {handler} */")
        out.append("        const UBYTE VM_FAR *p = CTX->PC + 1;")
        out.extend(fetch_code(infos))
        for name, kind, _size in infos:
            if kind != "ptr":
                continue
            if handler == "vm_invoke" and name == "fn":
                continue
            if name in far_data_params:
                out.append(
                    f"        const void VM_FAR *a_{name} = "
                    f"vm_far_data_ptr(0, a_{name}_off);"
                )
                continue
            qualifier = " VM_FAR" if name in far_names else ""
            out.append(
                f"        UBYTE{qualifier} *a_{name} = "
                f"(UBYTE{qualifier} *)(vm_bank_base({bank_expr}) "
                f"+ a_{name}_off);"
            )
        out.append("        CTX->PC = p;")
        call_args = list(before_this) + (["CTX"] if has_this else [])
        for name, kind, _size in infos:
            if kind == "ptr" and handler == "vm_invoke" and name == "fn":
                call_args.append(f"vm_native_token(a_{name}_off)")
            else:
                call_args.append(f"a_{name}")
        out.append(f"        {handler}({', '.join(call_args)});")
        out.append("        return 1;")
        out.append("      }")
        if wrapped:
            out.append("#endif")

    out.extend(
        [
            "      default:",
            "#if !defined(__ia16__)",
            '        fprintf(stderr, "vm: unimplemented opcode 0x%02X\\n", op);',
            "#endif",
            "        vm_last_unimplemented_opcode = op;",
            "        return 0;",
            "    }",
            "}",
            "",
            "#endif",
            "",
        ]
    )
    return "\n".join(out)


def c_term(term):
    if term.startswith("#>"):
        return f"(UBYTE)(({term[2:].strip()}) >> 8)"
    if term.startswith("#<"):
        return f"(UBYTE)({term[2:].strip()})"
    if term.startswith("#"):
        return f"(UBYTE)({term[1:].strip()})"
    return f"(UBYTE)({term.strip()})"


def generate_bytecode_header(consts, vm_i):
    out = [
        "/* Generated by wsc/tools/gen_dispatch.py from vm.i. Do not edit. */",
        "#ifndef WS_VM_BYTECODE_H",
        "#define WS_VM_BYTECODE_H",
        "",
        "#include <gbdk/platform.h>",
        "",
    ]
    for name in sorted(consts):
        out.append(f"#define {name} 0x{consts[name]:02X}")
    out.append("")

    seen = set()
    for opcode in sorted(vm_i):
        for name, op_const, _byte_sizes, terms, params, only_db in vm_i[opcode]:
            if not only_db or name in seen or name.startswith("."):
                continue
            seen.add(name)
            body_terms = [c_term(t) for t in terms]
            expansion = ", ".join([f"0x{op_const:02X}"] + body_terms)
            if params:
                out.append(f"#define {name}({', '.join(params)}) {expansion}")
            else:
                out.append(f"#define {name} {expansion}")
    out.extend(["", "#endif", ""])
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if generated files are stale"
    )
    args = parser.parse_args(argv)

    (entries, protos, core_handlers, handler_header, consts, macros, vm_i,
     enums) = load()
    args_bad, vm_i_bad = validate(entries, protos, vm_i, enums)

    dispatch = generate_dispatch(entries, protos, core_handlers, handler_header,
                                 enums)
    bytecode = generate_bytecode_header(consts, vm_i)

    if args.check:
        stale = []
        for path, content in ((DISPATCH, dispatch), (BYTECODE, bytecode)):
            current = path.read_text() if path.exists() else ""
            if current != content:
                stale.append(str(path))
        if stale:
            print("stale generated file: " + ", ".join(stale), file=sys.stderr)
            return 1
    else:
        DISPATCH.parent.mkdir(parents=True, exist_ok=True)
        BYTECODE.parent.mkdir(parents=True, exist_ok=True)
        DISPATCH.write_text(dispatch)
        BYTECODE.write_text(bytecode)

    print(
        f"{len(entries)} opcodes, {args_bad} args_len mismatches, "
        f"{vm_i_bad} vm.i mismatches"
    )
    return 0 if args_bad == 0 and vm_i_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
