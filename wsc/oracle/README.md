# GB differential oracle

`make -C wsc gb-oracle` builds the GB oracle ROM with the pre-WSC GB Studio
engine, builds the WSC gamerom, and compares every config in `wsc/oracle/`
tick by tick. Today those are the town topdown walk and the PLATFORM scenes
(`platform-deeper`, `platform-path`, `platform-parallax`) plus three focused
regressions:

- `platform-deeper-ladder` uses the original ladder-release tick and checks
  that SameBoy's key-bounce emulation does not shift an input edge.
- `platform-parallax-actors` walks past the Parallax Example Elephant and Sign
  Post. Their activation is viewport-dependent, so the config opts into
  ignoring only the animation-phase fields of an actor whose activation
  differed outside the GB viewport; positions, direction and movement are
  still compared.
- `platform-path-hazard` falls into the Path to Sample Town pit, which enters
  BLANK state and runs the blank callback attached through `VM_CALL_NATIVE`.

`platform.json` is the GB-only jump trace used by `gb-platform-smoke`, so
`gb-oracle` runs that one in `--platform-smoke` mode and the rest as full
comparisons.

The comparison front end is `wsc/tools/gbdiff.py`. Each `*.json` here selects
the start scene, tick count, input script and the explicit intended
differences. `inputs/*.txt` lines are `TICK BUTTONS` (tick-relative, not
emulator frames; multiple buttons are comma-separated).

Platform configs add the state-machine/velocity symbols to `playerFields`
(`plat_vel_x`, `plat_vel_y`, `plat_state`, `plat_grounded`, jump/ladder
counters, and so on). Their sizes are listed in `STATE_FIELDS` in
`gbdiff.py` and resolved from each side's own symbol table, like the existing
player fields.

## What it builds

- GB engine: `b242ab79fd8a6aa0fe41d43b51a345685b11f9c3`, the last
  `appData/engine/gbvm` revision before the WSC port. The CLI builds it from a
  temporary project copy with a local engine (the WSC-only source files that
  the CLI would otherwise keep are replaced by empty stubs).
- GBDK: GBDK-2020 4.5.0, SHA-256
  `d7857a5f6d135ee4c249043ca26aad9f2ec8ab5d4106d97720d404114f42605c`.
- GB emulator: SameBoy libretro, commit
  `aa158a889a48b538a0302873704a34577c8eb67d`, fetched by
  `wsc/tools/wsrun/fetch-gb-core.sh`. The fetch script disables SameBoy's key
  contact-bounce emulation in the libretro front end; bounce holds a released
  key for a pseudo-random number of frames and makes an input edge land on a
  different game tick than on WSC.
- WSC emulator: the pinned beetle-wswan core already used by `wsrun`.
- Native table: `s2c.py` emits `vm_native_fns[]` from the script's native
  symbols (`wait_frames`, `camera_shake_frames`, `plat_callback_attach`) in the
  same order as the bytecode indexes. Entries are far function pointers on
  WSC. The table is guarded by `GBVM_ENGINE_HANDLERS`, so data-only ROMs
  (datarom) can convert the same scripts without linking the VM.

## Addresses and layouts

No RAM address is hard-coded. GB addresses come from the linker `.noi`, WSC
addresses from the ELF symbol table. CGB WRAM is mapped to SameBoy's 8-bank
dump (C000-CFFF is bank 0, D000-DFFF is bank 1, the GBDK default).

Struct offsets are compiled at run time by the real toolchains: an
`offsetof(actor_t, ...)` probe is assembled with SDCC (GB) and compiled with
gcc-ia16 (WSC). This is why the two actor layouts differ (56 vs 68 bytes).
