# wsrun

`wsrun` is a small headless libretro frontend for running WonderSwan Color
ROMs in the beetle-wswan core for a fixed number of frames, optionally
synchronising on a RAM marker first. It saves the last video frame as RGB24
and PNG, plus a dump of the console's 64 KiB system RAM.

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
    [--marker ADDR:SIZE:VALUE [--marker-timeout N]] [--boot-id N]
```

- `--frames N` runs `retro_run` exactly N times, as fast as possible. With
  `--marker` it is the number of runs after the marker was observed.
- `--raw OUT` writes `width * height * 3` bytes of RGB24 with no header.
- `--png OUT` writes the same image through stb_image_write.
- `--ram OUT` writes the core's full `RETRO_MEMORY_SYSTEM_RAM` (65536 bytes
  on WSC).
- `--marker ADDR:SIZE:VALUE` polls system RAM after each `retro_run` until
  the little-endian `SIZE` (1, 2 or 4) bytes at `ADDR` equal `VALUE`; only
  then does it start the `--frames` count. `ADDR` and `VALUE` accept decimal
  or `0x` notation. If the value is not seen within `--marker-timeout`
  frames (default 600), `wsrun` exits nonzero.
- `--boot-id N` patches the byte following the `WSCBOOT` marker in the
  loaded ROM image. The gamerom image uses it to select a start scene from
  its run-time table; the patch is in memory only.
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
