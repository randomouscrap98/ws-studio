# GB differential oracle

`make -C wsc gb-oracle` builds the GB oracle ROM with the pre-WSC GB Studio
engine, builds the WSC gamerom, and compares the town topdown scene tick by
tick. `make -C wsc gb-platform-smoke` records the GB-only platform jump trace.

The comparison front end is `wsc/tools/gbdiff.py`. Each `*.json` here selects
the start scene, tick count, input script and the explicit intended
differences. `inputs/*.txt` lines are `TICK BUTTONS` (tick-relative, not
emulator frames).

## What it builds

- GB engine: `b242ab79fd8a6aa0fe41d43b51a345685b11f9c3`, the last
  `appData/engine/gbvm` revision before the WSC port. The CLI builds it from a
  temporary project copy with a local engine (the WSC-only source files that
  the CLI would otherwise keep are replaced by empty stubs).
- GBDK: GBDK-2020 4.5.0, SHA-256
  `d7857a5f6d135ee4c249043ca26aad9f2ec8ab5d4106d97720d404114f42605c`.
- GB emulator: SameBoy libretro, commit
  `aa158a889a48b538a0302873704a34577c8eb67d`, fetched by
  `wsc/tools/wsrun/fetch-gb-core.sh`.
- WSC emulator: the pinned beetle-wswan core already used by `wsrun`.

## Addresses and layouts

No RAM address is hard-coded. GB addresses come from the linker `.noi`, WSC
addresses from the ELF symbol table. CGB WRAM is mapped to SameBoy's 8-bank
dump (C000-CFFF is bank 0, D000-DFFF is bank 1, the GBDK default).

Struct offsets are compiled at run time by the real toolchains: an
`offsetof(actor_t, ...)` probe is assembled with SDCC (GB) and compiled with
gcc-ia16 (WSC). This is why the two actor layouts differ (56 vs 68 bytes).
