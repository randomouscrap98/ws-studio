#!/usr/bin/env python3
"""Check the WonderSwan ROM size, footer and header checksum."""

import sys


def fail(message):
    print("FAIL " + message)
    return 1


def main(argv):
    if len(argv) != 2:
        print("usage: romcheck.py ROM", file=sys.stderr)
        return 2

    try:
        with open(argv[1], "rb") as f:
            data = f.read()
    except OSError as exc:
        return fail(f"cannot read {argv[1]}: {exc}")

    size = len(data)
    if size < 65536:
        return fail(f"size {size} is smaller than 64 KiB")
    if size & (size - 1):
        return fail(f"size {size} is not a power of two")

    if data[size - 16] != 0xEA:
        return fail(
            f"footer far jump byte is 0x{data[size - 16]:02X}, expected 0xEA"
        )

    checksum = int.from_bytes(data[-2:], "little")
    expected = sum(data[:-2]) & 0xFFFF
    if checksum != expected:
        return fail(
            f"checksum 0x{checksum:04X} does not match computed 0x{expected:04X}"
        )

    print(f"OK {size} 0x{checksum:04x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
