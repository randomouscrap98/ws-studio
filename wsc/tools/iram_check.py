#!/usr/bin/env python3
"""Check where the WSC_UPPER_RAM buffers landed.

The WSC colour IRAM is 64 KiB, but only 0xC000..0xFDFF is free for engine
state: 0x4000..0xBFFF is the C18 tile area and 0xFE00..0xFFFF is the
hardware palette area.  This script parses the final ELF (section headers
and symbols, standard library only) and fails if the section produced by
WSC_UPPER_RAM, or any symbol in it, leaves that range.

Run it after wf-wswantool has built the final ELF.
"""
import argparse
import struct
import sys
from pathlib import Path

SHT_SYMTAB = 2
SHN_UNDEF = 0
SHN_ABS = 0xFFF1
SHN_COMMON = 0xFFF2
SHN_XINDEX = 0xFFFF

TILE_RANGE = (0x4000, 0xBFFF)
PALETTE_RANGE = (0xFE00, 0xFFFF)
UPPER_RANGE = (0xC000, 0xFDFF)


class CheckError(Exception):
    pass


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def c_string(data, offset):
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", "replace")


class Elf:
    def __init__(self, path):
        data = Path(path).read_bytes()
        if data[:4] != b"\x7fELF":
            raise CheckError("{} is not an ELF file".format(path))
        if data[4] != 1 or data[5] != 1:
            raise CheckError("{} is not a 32-bit little-endian ELF".format(path))

        self.shnum = u16(data, 48)
        self.shstrndx = u16(data, 50)
        shoff = u32(data, 32)
        shentsize = u16(data, 46)
        if self.shnum == 0 or self.shstrndx == 0xFFFF:
            raise CheckError("extended ELF section numbering is not supported")

        self.sections = []
        for index in range(self.shnum):
            base = shoff + index * shentsize
            if base + 40 > len(data):
                raise CheckError("truncated section header {}".format(index))
            (
                name,
                sh_type,
                _flags,
                addr,
                offset,
                size,
                link,
                _info,
                _align,
                entsize,
            ) = struct.unpack_from("<IIIIIIIIII", data, base)
            self.sections.append(
                {
                    "index": index,
                    "name_offset": name,
                    "type": sh_type,
                    "addr": addr,
                    "offset": offset,
                    "size": size,
                    "link": link,
                    "entsize": entsize,
                }
            )

        shstrtab = self.sections[self.shstrndx]
        self.names = data[shstrtab["offset"] : shstrtab["offset"] + shstrtab["size"]]
        for section in self.sections:
            section["name"] = c_string(self.names, section["name_offset"])

        self.data = data

    def find_section(self, name):
        matches = [s for s in self.sections if s["name"] == name]
        if not matches:
            raise CheckError("section {} not found".format(name))
        if len(matches) > 1:
            raise CheckError("section {} appears {} times".format(name, len(matches)))
        return matches[0]

    def symbols(self):
        symtab = next((s for s in self.sections if s["type"] == SHT_SYMTAB), None)
        if symtab is None:
            raise CheckError("ELF has no symbol table")
        if symtab["link"] <= 0 or symtab["link"] >= len(self.sections):
            raise CheckError("symbol table has no string table")
        strtab = self.sections[symtab["link"]]
        strings = self.data[
            strtab["offset"] : strtab["offset"] + strtab["size"]
        ]
        entsize = symtab["entsize"] or 16
        count = symtab["size"] // entsize
        result = []
        for index in range(count):
            base = symtab["offset"] + index * entsize
            if base + 16 > len(self.data):
                raise CheckError("truncated symbol {}".format(index))
            name, value, size, _info, _other, shndx = struct.unpack_from(
                "<IIIBBH", self.data, base
            )
            if shndx == SHN_UNDEF or shndx >= SHN_ABS:
                continue
            result.append(
                {
                    "name": c_string(strings, name),
                    "value": value,
                    "size": size,
                    "shndx": shndx,
                }
            )
        return result


def overlaps(start, end, reserved):
    return start <= reserved[1] and reserved[0] <= end


def describe(name, start, size):
    return "{} at 0x{:04X}..0x{:04X} ({} bytes)".format(
        name, start, start + size - 1, size
    )


def check_range(name, start, size):
    end = start + size - 1
    if size <= 0:
        raise CheckError("{} has zero size".format(name))
    if overlaps(start, end, TILE_RANGE):
        raise CheckError(
            "{} overlaps the C18 tile area 0x{:04X}..0x{:04X}".format(
                describe(name, start, size), TILE_RANGE[0], TILE_RANGE[1]
            )
        )
    if overlaps(start, end, PALETTE_RANGE):
        raise CheckError(
            "{} overlaps the hardware palette area 0x{:04X}..0x{:04X}".format(
                describe(name, start, size), PALETTE_RANGE[0], PALETTE_RANGE[1]
            )
        )
    if start < UPPER_RANGE[0] or end > UPPER_RANGE[1]:
        raise CheckError(
            "{} is outside the allowed upper IRAM range 0x{:04X}..0x{:04X}".format(
                describe(name, start, size), UPPER_RANGE[0], UPPER_RANGE[1]
            )
        )


def find_moved_section(elf, name):
    try:
        return elf.find_section(name)
    except CheckError:
        pass
    # If the placement attribute names a different explicit upper-IRAM
    # section, still inspect the one .iramC_* section directly.
    candidates = [
        section
        for section in elf.sections
        if section["name"].startswith(".iramC_")
        and not section["name"].endswith(("!", "&"))
        and section["size"] > 0
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise CheckError(
        "section {} not found and no single .iramC_* section to inspect".format(
            name
        )
    )


def run(args):
    elf = Elf(args.elf)
    section = find_moved_section(elf, args.section)
    section_name = section["name"]
    check_range(section_name, section["addr"], section["size"])

    moved = [
        sym
        for sym in elf.symbols()
        if sym["shndx"] == section["index"] and sym["size"] > 0
    ]
    for sym in moved:
        check_range(sym["name"], sym["value"], sym["size"])

    moved.sort(key=lambda sym: sym["value"])
    print(
        "PASS iram_check: {} at 0x{:04X}..0x{:04X} ({} bytes), ".format(
            section_name,
            section["addr"],
            section["addr"] + section["size"] - 1,
            section["size"],
        )
        + "{} symbols outside tiles 0x{:04X}..0x{:04X} and palettes "
        "0x{:04X}..0x{:04X}".format(
            len(moved), TILE_RANGE[0], TILE_RANGE[1], PALETTE_RANGE[0], PALETTE_RANGE[1]
        )
    )
    for sym in moved:
        print(
            "  {:<28} 0x{:04X} {:5d}".format(
                sym["name"], sym["value"], sym["size"]
            )
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--elf", required=True, help="final ELF to inspect")
    parser.add_argument(
        "--section",
        default=".iramC_C000",
        help="section holding the WSC_UPPER_RAM buffers "
        "(default: .iramC_C000)",
    )
    args = parser.parse_args(argv)
    try:
        run(args)
    except (CheckError, OSError, struct.error) as exc:
        print("FAIL iram_check: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
