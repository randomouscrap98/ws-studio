# C05s engine hardware survey

Research artefacts for mapping the GBVM engine's Game Boy hardware
dependencies onto the WonderSwan Color. Nothing here changes the engine.

Run everything:

```sh
wsc/survey/run.sh
```

It prints the per-file hardware inventory, the trial build of every engine
`.c` file, and the vblank-interrupt ROM check. It exits 0 when the vblank
check passes; the trial build is expected to report failures for the
SDCC/GB-only files.

## Layout

| path | purpose |
| --- | --- |
| `inventory.py` | counts GBDK calls, GB registers and SDCC constructs per engine file; writes `wsc/build/survey/inventory.tsv` |
| `trial_build.py` | compiles `src/main.c`, `src/core/*.c` and `src/states/*.c` with the `wsc/vmrom` flags; writes `wsc/build/survey/trial_build.tsv` |
| `trial_include/` | shim headers for GBDK 2020 and the compiler-generated `data/*.h` headers. They let the real diagnostics show; they are not a port |
| `vblank/` | Wonderful project: libws vblank handler increments `vblank_count` |
| `vblank_check.py` | builds `vblank/`, runs it in `wsrun` and checks `vblank_count` against the frame count |
| `run.sh` | one entry point for all of the above |

Generated output lives in `wsc/build/survey/` (gitignored), except the
`vblank` project's own `build/`, `vblank.wsc` and `compile_commands.json`,
which `wsc/survey/.gitignore` covers.

## Trial build

`trial_build.py` mirrors the `wsc/vmrom` compiler flags:

```
-std=gnu11 -Wall -march=v30mz -mtune=v30mz -mregparmcall -ffreestanding
-mcmodel=medium -msegelf -mcs-jump-tables -ffunction-sections
-fdata-sections -fno-common -O2 -fno-builtin -Wno-unknown-pragmas
-Wno-pointer-sign -DGBT_PLAYER
```

The shim defines `BANKED`, `NONBANKED`, `NAKED`, `OLDCALL`,
`PRESERVES_REGS`, `SFR` and `AT` as empty, exactly like
`wsc/host/include/gbdk/platform.h`, so SDCC-only inline asm in the engine
is still diagnosed. `-DGBT_PLAYER` only selects a `TRACK_T` in
`music_manager.h`; the GB Studio build always selects GBTPlayer or
hUGETracker.

A `PASS` line means the file compiled with this shim; it does not mean the
GBDK calls are implemented by libws.

## Vblank

The ROM installs a C handler with `__attribute__((interrupt))` through
`ws_int_set_handler(WS_INT_VBLANK, ...)`, unmasks it with
`ws_int_enable(WS_INT_ENABLE_VBLANK)`, enables CPU interrupts with
`ia16_enable_irq()` and acknowledges the level-triggered interrupt with
`ws_int_ack(WS_INT_ACK_VBLANK)`. `main()` halts each frame and copies the
counter to `vblank_last_count`; both are in the `wsrun` RAM dump.

Measured: 60, 120 and 240 emulated frames give `vblank_count` 60, 120 and
240 respectively. `vblank_check.py` uses 120 frames with a +/-2 tolerance.
