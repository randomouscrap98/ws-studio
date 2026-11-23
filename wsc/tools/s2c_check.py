#!/usr/bin/env python3
"""Compare s2c.py output with the real sdasgb assembler.

For every exported VM script:
  * assemble the same source with sdasgb -ff (relocation-flagged listing),
  * compare all non-relocated bytes exactly,
  * verify every relocated (pointer/label) byte against the converter's
    bank+offset layout and external placeholder map.

sdasgb comes from the pinned GBDK-2020 4.5.0 Linux release. If it is not
present under wsc/build/gbdk it is downloaded there; the archive SHA-256 is
checked.
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC_DIR = HERE.parent
REPO_DIR = WSC_DIR.parent
SDAS_URL = (
    "https://github.com/gbdk-2020/gbdk-2020/releases/download/"
    "4.5.0/gbdk-linux64.tar.gz"
)
SDAS_SHA256 = "d7857a5f6d135ee4c249043ca26aad9f2ec8ab5d4106d97720d404114f42605c"

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import s2c  # noqa: E402

LISTING_RE = re.compile(r"^\s*([0-9A-Fa-f]{8})(.*?)(?:\s{2,})(\d+)\s+(.*)$")
TOKEN_RE = re.compile(r"([uvpqrsRUSVPQ*`]?)([0-9A-Fa-f]{2})")


class CheckError(Exception):
    pass


def ensure_sdas(path):
    path = Path(path)
    if path.is_file() and path.stat().st_mode & 0o111:
        return path
    dest = WSC_DIR / "build" / "gbdk"
    archive = dest / "gbdk-linux64.tar.gz"
    dest.mkdir(parents=True, exist_ok=True)
    if not archive.is_file():
        print("s2c_check: downloading GBDK 4.5.0 sdas", file=sys.stderr)
        with urllib.request.urlopen(SDAS_URL) as response, open(archive, "wb") as out:
            shutil.copyfileobj(response, out)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != SDAS_SHA256:
        raise CheckError(
            "GDBK archive hash mismatch: got {}, want {}".format(digest, SDAS_SHA256)
        )
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest)
    if not path.is_file():
        raise CheckError("sdas not found after extracting {}".format(archive))
    return path


def _parse_data_field(field):
    clean = re.sub(r"\s+", "", field)
    tokens = TOKEN_RE.findall(clean)
    consumed = ["".join(token) for token in tokens]
    if "".join(consumed) != clean:
        raise CheckError("cannot parse listing data field {!r}".format(field))
    return tokens


CONTINUATION_RE = re.compile(r"^\s+((?:[uvpqrsRUSVPQ*`]?[0-9A-Fa-f]{2}\s*)+)$")


def parse_listing(path):
    data = {}
    next_address = None
    for line in path.read_text(errors="replace").splitlines():
        match = LISTING_RE.match(line)
        if not match:
            cont = CONTINUATION_RE.match(line)
            if cont and next_address is not None:
                for flag, byte_text in _parse_data_field(cont.group(1)):
                    data[next_address] = (int(byte_text, 16), flag)
                    next_address += 1
            continue
        address_text, field, _line_number, _source = match.groups()
        field = field.strip()
        if not field:
            next_address = None
            continue
        address = int(address_text, 16)
        for index, (flag, byte_text) in enumerate(_parse_data_field(field)):
            data[address + index] = (int(byte_text, 16), flag)
        next_address = address + len(_parse_data_field(field))
    return data


def make_lookup(converter, script):
    def lookup(name):
        if name in script.labels:
            return script.offset + script.labels[name]
        if name.startswith("___bank_"):
            base = name[len("___bank_"):]
            target = converter.script_labels.get("_" + base)
            if target is not None:
                return target.bank
        if name in script.consts:
            value = script.consts[name]
            return value if isinstance(value, int) else s2c.eval_expression(value, lookup)
        if name in converter.defs.constants:
            value = converter.defs.constants[name]
            return value if isinstance(value, int) else s2c.eval_expression(value, lookup)
        if name in converter.script_labels:
            return converter.script_labels[name].offset
        kind = converter.symbol_kinds.get(name)
        if kind:
            what, base = kind
            if what == "script_label":
                return converter.script_labels[name].offset
            if what == "script_bank":
                return converter.script_labels["_" + base].bank
            if what == "local_label":
                return script.offset + script.labels[name]
        if name in converter.externals:
            return converter.externals[name][1]
        raise s2c.ExprError("unresolved symbol {!r}".format(name))

    return lookup


def expected_pointer_byte(converter, script, ref):
    if ref.kind == "script":
        # Verify the target through the model's actual label/bank placement.
        by_label = converter.script_labels
        value = None
        for sym in ref.symbols:
            if sym in script.labels:
                value = script.offset + script.labels[sym]
                break
            if sym in by_label:
                value = by_label[sym].offset
                break
            if sym.startswith("___bank_"):
                target = by_label.get("_" + sym[len("___bank_"):])
                if target is not None:
                    value = target.bank
                    break
        if value is None:
            raise CheckError("script pointer {} has no script symbol".format(ref.expr))
    else:
        value = s2c.eval_expression(ref.expr, make_lookup(converter, script))
    if ref.mode == "word":
        return (value >> (8 * ref.byte_index)) & 0xFF
    if ref.mode == "high":
        return (value >> 8) & 0xFF
    return value & 0xFF


def check_script(converter, script, index, sdas, include_dir, work_dir):
    source = work_dir / "{:03d}_{}.s".format(index, s2c.sanitize(script.name).lower())
    source.write_text(script.source)
    rel = work_dir / (source.stem + ".rel")
    list_path = work_dir / (source.stem + ".lst")
    command = [
        str(sdas),
        "-I" + str(include_dir),
        "-g",
        "-l",
        "-ff",
        "-o",
        str(rel),
        str(source),
    ]
    proc = subprocess.run(command, cwd=str(work_dir), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise CheckError(
            "sdas failed for {}: {}".format(
                script.path.name, (proc.stderr or proc.stdout).strip().splitlines()[-1:]
            )
        )
    listing = parse_listing(list_path)
    if not listing:
        raise CheckError("sdas emitted no bytes for {}".format(script.path.name))
    max_pos = max(listing)
    if max_pos + 1 != len(script.data):
        raise CheckError(
            "{}: sdas has {} bytes, converter has {}".format(
                script.path.name, max_pos + 1, len(script.data)
            )
        )
    flagged = {pos for pos, (_byte, flag) in listing.items() if flag}
    refs = set(script.refs)
    if flagged != refs:
        missing = sorted(flagged - refs)[:8]
        extra = sorted(refs - flagged)[:8]
        raise CheckError(
            "{}: relocation set mismatch (sdas-only {}, converter-only {})".format(
                script.path.name, missing, extra
            )
        )
    for pos in range(len(script.data)):
        sdas_byte, flag = listing[pos]
        if flag:
            ref = script.refs[pos]
            want = expected_pointer_byte(converter, script, ref)
            if script.data[pos] != want:
                raise CheckError(
                    "{} @0x{:X}: pointer {} emitted 0x{:02X}, expected 0x{:02X}".format(
                        script.path.name, pos, ref.expr, script.data[pos], want
                    )
                )
        elif script.data[pos] != sdas_byte:
            raise CheckError(
                "{} @0x{:X}: byte 0x{:02X} != sdas 0x{:02X}".format(
                    script.path.name, pos, script.data[pos], sdas_byte
                )
            )
    pointer_operands = sum(
        1 for pos in flagged if pos - 1 not in flagged
    )
    return len(script.data), len(flagged), pointer_operands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", default=str(WSC_DIR / "build" / "export"))
    parser.add_argument("--sdas", default=str(WSC_DIR / "build" / "gbdk" / "gbdk" / "bin" / "sdasgb"))
    parser.add_argument("--keep", action="store_true", help="keep temporary sdas files")
    args = parser.parse_args(argv)

    export = Path(args.export)
    include_dir = export / "include"
    data_dir = export / "src" / "data"
    if not include_dir.is_dir() or not data_dir.is_dir():
        print(
            "s2c_check: export not found; run wsc/export/run.sh first",
            file=sys.stderr,
        )
        return 2
    try:
        sdas = ensure_sdas(args.sdas)
    except (CheckError, OSError, urllib.error.URLError) as exc:
        print("s2c_check: {}".format(exc), file=sys.stderr)
        return 2

    files = sorted(data_dir.glob("*.s"))
    try:
        defs = s2c.Definitions(include_dir)
        converter = s2c.Converter(defs, files)
        converter.run()
    except (s2c.ConversionError, s2c.ExprError) as exc:
        print("s2c_check: converter failed: {}".format(exc), file=sys.stderr)
        return 1

    work = WSC_DIR / "build" / "s2c-check"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    total_bytes = total_pointers = total_operands = 0
    try:
        for index, script in enumerate(converter.scripts):
            nbytes, npointers, noperands = check_script(
                converter, script, index, sdas, include_dir, work
            )
            total_bytes += nbytes
            total_pointers += npointers
            total_operands += noperands
    except (CheckError, s2c.ExprError) as exc:
        print("s2c_check: FAIL: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print(
        "s2c_check: {} scripts, {} bytes, {} pointer operands ({} pointer bytes), "
        "{} banks, {} externals, {} skipped: OK".format(
            len(converter.scripts),
            total_bytes,
            total_operands,
            total_pointers,
            len(converter.banks),
            len(converter.externals),
            len(converter.skipped),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
