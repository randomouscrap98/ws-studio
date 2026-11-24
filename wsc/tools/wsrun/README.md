# wsrun

`wsrun` is a small headless libretro frontend for running WonderSwan Color
(and, with another libretro core, Game Boy) ROMs for a fixed number of frames,
optionally synchronising on RAM markers first. It saves the last video frame
as RGB24 and PNG, plus a dump of the console's system RAM. It can also sample
RAM whenever an engine tick counter changes and schedule input by tick.

## Build

```sh
make -C wsc/tools/wsrun
```

This produces `wsc/build/wsrun`. If the core is missing, the build also runs
`fetch-core.sh`, clones the pinned core into `wsc/build/beetle-wswan`, builds
it and copies `mednafen_wswan_libretro.so` to `wsc/build/`.

Nothing is re-downloaded or rebuilt when everything is already up to date.

## Usage

```sh
wsc/build/wsrun --core SO --rom ROM --frames N \
    [--input FILE] [--png OUT] [--raw OUT] [--ram OUT] \
    [--marker ADDR:SIZE:VALUE [--marker-timeout N]] [--boot-id N] \
    [--screen-width N] [--orientation H|V] [--poke ADDR:SIZE:VALUE] \
    [--sram-in FILE] [--sram-out FILE] \
    [--tick ADDR:SIZE [--tick-gate ADDR:SIZE] [--trace OUT] [--max-ticks N] [--input-tick]]
```

- `--frames N` runs `retro_run` exactly N times, as fast as possible. With
  `--marker` it is the number of runs after the marker was observed.
- `--raw OUT` writes `width * height * 3` bytes of RGB24 with no header.
- `--png OUT` writes the same image through stb_image_write.
- `--ram OUT` writes the core's full `RETRO_MEMORY_SYSTEM_RAM` (65536 bytes
  on WSC).
- `--sram-in FILE` copies a save file into the core's
  `RETRO_MEMORY_SAVE_RAM` after `retro_load_game` and before the first
  frame. `--sram-out FILE` writes that memory after the run. Both cores
  expose it (WSC SRAM and Game Boy MBC RAM); a ROM with no save memory makes
  either option an error. Together they let a test save in one run and load
  in the next.
- `--marker ADDR:SIZE:VALUE` polls system RAM after each `retro_run` until
  the little-endian `SIZE` (1, 2 or 4) bytes at `ADDR` equal `VALUE`; only
  then does it start the `--frames` count. `ADDR` and `VALUE` accept decimal
  or `0x` notation. The option may be repeated; every marker must match in
  the same run. If the values are not seen within `--marker-timeout` frames
  (default 600), `wsrun` exits nonzero.
- `--poke ADDR:SIZE:VALUE` writes the little-endian `SIZE` (1, 2 or 4)
  bytes at `ADDR` in system RAM once, after the marker (if any) has been
  observed and before the first counted frame. The syntax matches `--marker`
  and the option may be repeated. `gbdiff.py` uses it to give the WSC engine
  the GB side's random-generator state at the start marker.
- `--tick ADDR:SIZE` makes `wsrun` watch an engine tick counter (for example
  `game_time`) after every `retro_run`. A tick is counted whenever the value
  changes. `--trace OUT` writes a binary trace: an 8-byte `GBOTRACE` magic,
  version/tick-width/RAM-size u32s, then one `tick u32, RAM size u32, RAM
  bytes` record per tick. `--max-ticks N` stops after N ticks (frames remains
  a safety limit). `--input-tick` makes input-file frame numbers mean logical
  tick numbers instead of `retro_run` indices.
- `--tick-gate ADDR:SIZE` makes a tick count only when the little-endian
  value at `ADDR` is zero after the change. A change seen while the gate is
  non-zero is dropped, so the trace contains the next completed tick instead
  of a sample taken inside an exception handler. `gbdiff.py` gates on
  `vm_exception_code`; the engine resets `game_time` inside its scene-change
  and load handlers, where a frame boundary can otherwise capture a
  half-updated handler state.
- `--boot-id N` patches the byte following the `WSCBOOT` marker in the
  loaded ROM image. The gamerom image uses it to select a start scene from
  its run-time table; the patch is in memory only.
- `--screen-width N` patches the byte after the boot id in the `WSCBOOT`
  slot. The gamerom uses it to pick its logical screen width (160 or 224 px)
  before the first scene loads. Without the option the ROM default (224) is
  used.
- `--orientation H|V` (also `horizontal`/`vertical`) patches the byte after
  the screen width. `vertical` boots the 144x224 portrait view; the HAL
  rotates the tiles, map, sprites and window 90 degrees and maps the Y pad
  to the d-pad. Without the option the ROM default (horizontal) is used.
- On success one line is printed to stdout:

  ```
  frames=N width=W height=H ram_size=S [marker_frame=M]
  ```

Core log messages go to stderr. Any bad argument, missing file, `dlopen` or
symbol failure, or rejected ROM makes `wsrun` exit nonzero.

## Input file

Lines are `FRAME BUTTONS`:

```
# hold A from frame 30; release everything at frame 90
30 A
90 -
```

`FRAME` is a 0-based `retro_run` index. With `--marker` it is relative to the
marker observation: frame 0 is the first run after the marker. From that
frame until the next line, exactly those buttons are held. `-` means no
buttons. `#` starts a comment; blank lines are ignored. Unknown button names
are an error.

Supported names: `X1 X2 X3 X4 Y1 Y2 Y3 Y4 A B START`, where `X1`/`X2`/`X3`/`X4`
are up/right/down/left on the X pad (same for Y). They map to libretro joypad
IDs through the core's horizontal-layout table:

In vertical mode the HAL uses the Y pad as the logical d-pad:
logical up/right/down/left = `Y2`/`Y3`/`Y4`/`Y1`, and `X1` is Select.

| Name | libretro ID | Name | libretro ID |
| --- | --- | --- | --- |
| X1 | `UP` | Y1 | `R2` (shoulder) |
| X2 | `RIGHT` | Y2 | `R` (shoulder) |
| X3 | `DOWN` | Y3 | `L2` (shoulder) |
| X4 | `LEFT` | Y4 | `L` (shoulder) |
| A | `A` | B | `B` |
| START | `START` | | |

## Pinned versions

- beetle-wswan libretro core:
  `4b01295838ea89e3f1355bbe4cb5cf98aa6108cd`
  (<https://github.com/libretro/beetle-wswan-libretro>)
- stb `stb_image_write.h` v1.19, commit
  `6b5799bae8a1fe3792691ef4b72ae26434c3e799`
  (<https://github.com/nothings/stb>); public domain.

## Notes

The frontend accepts both `RETRO_PIXEL_FORMAT_XRGB8888` and
`RETRO_PIXEL_FORMAT_RGB565`; with this core build it normally receives RGB565.
It returns directories under `wsc/build/` for the system and save directory
queries and declines all core options, so the core uses its defaults.
