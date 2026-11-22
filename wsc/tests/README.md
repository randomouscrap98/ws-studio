# WSC tests

`make -C wsc test` builds each test's ROM, runs it in `wsrun`, and checks
the final frame and selected RAM values. It prints `PASS <name>` or
`FAIL <name>: <reason>` per test.

```sh
make -C wsc test             # all tests under wsc/tests/*/test.json
make -C wsc test-negative    # the tests under wsc/tests/_negative/
python3 wsc/tests/run.py [--update-golden] [--expect-fail] [TEST_DIR ...]
```

`--update-golden` writes each test's current frame hash back to its
`test.json` instead of comparing it. It is the only way the golden values
change. `--expect-fail` inverts the exit status: it succeeds only when every
listed test fails, which is how `_negative` tests are checked.

Generated files go to `wsc/build/tests/<name>/`: `frame.png` (always kept
for inspection), `frame.rgb` (the hashed raw RGB24 frame) and `ram.bin` (the
full 64 KiB system RAM dump).

## RAM symbol → dump offset

`wf-wswantool build` allocates ordinary writable sections (`.bss*`, `.data*`,
`.sbss*`, `.sdata*`, `.srodata*`, `.snoinit*`) into the console's internal
RAM. In the resulting ELF the symbol value is already the flat IRAM byte
offset, and `wsrun --ram` dumps that same 64 KiB IRAM image starting at
offset 0. So the dump offset is simply:

```
offset = symbol_value & 0xFFFF
```

For example the C00 `hello` ROM has

```
$ ia16-elf-nm -S wsc/hello/build/hello.elf | grep ' hello_magic$'
00000040 00000002 B hello_magic
```

and the RAM dump contains `34 12` at offset `0x40`. The `hello_magic!` and
`hello_magic&` symbols are segment aliases and are ignored.

`run.py` reads the symbol with `ia16-elf-objdump -t` (the address is the same
one `nm` prints, and objdump also gives the section name). It rejects
symbols that are not in an IRAM section above, for example `*ABS*` or SRAM
far data, because those are not present in the system-RAM dump. Values are
read little-endian with `size` 1, 2 or 4.

## Test format

A test is a directory `wsc/tests/<name>/` containing `test.json`:

```json
{
  "rom": "hello/hello.wsc",
  "elf": "hello/build/hello.elf",
  "build": "hello",
  "frames": 60,
  "input": "input.txt",
  "frame_sha256": "<hex or null>",
  "reference": {
    "script": "tools/ref_render.py",
    "args": ["--scroll", "0"],
    "precision": "exact"
  },
  "ram": [
    {"symbol": "hello_magic", "size": 2, "equals": "0x1234"}
  ]
}
```

- `rom`, `elf` and `build` are relative to `wsc/`. If `build` names a
  directory, `run.py` runs `make -C` in it; otherwise it runs `make -C wsc`
  with `build` as the target.
- `frames` is the number of `retro_run` calls passed to `wsrun`.
- `input` (optional) is an input file relative to the test directory, in the
  format documented in `wsc/tools/wsrun/README.md`.
- `frame_sha256` is the SHA-256 of `wsrun --raw` output, or `null` to skip
  the frame check. The raw RGB24 file is always written.
- `reference` (optional) runs an expected-frame renderer before the hash is
  checked. `script` is relative to `wsc/`; `args` are passed to it, and
  `run.py` adds `--out <test build dir>/reference.rgb`. `precision` is
  `"exact"` (default) or `"4bit"` (compare the top four bits of each
  channel). A mismatch reports the first differing pixel.
- `ram` (optional) lists little-endian value checks. `equals` may be a hex
  string such as `"0x1234"`. An optional `offset` (bytes) is added to the
  symbol's address, for example `{"symbol": "script_memory", "offset": 4,
  "size": 2, "equals": "0x2a"}` reads `script_memory[2]`. An optional
  non-negative `tolerance` accepts values within `equals +/- tolerance`.

## Tests

- `hello`: the C00 red-screen ROM; expects `hello_magic == 0x1234` and a
  fixed frame hash.
- `input-echo-a` / `input-echo-up`: run `input-echo-rom`, which stores the
  raw result of `ws_keypad_scan()` in `volatile uint16_t echo_keys` every
  loop iteration. The input files hold one button from frame 30; the final
  RAM value must contain only that button's libws bit.
- `_negative/wrong-magic`: same ROM and frame as `hello`, but expects
  `hello_magic == 0x9999`, so it must fail. Run it with `test-negative`.
- `vmrom`: runs `wsc/vmrom`, which executes two far-const script banks
  through the portable VM core and checks the results in `script_memory`
  and named RAM variables.
- `hal-static`: runs `wsc/halrom` for 30 frames with no input. The HAL loads
  hand-made GB background data, so the frame must match `ref_render.py` at
  scroll 0 exactly; `scroll_x == 0` and `hal_frames` is 30 +/- 2.
- `hal-scroll`: holds X2 (right) from frame 10 for 60 frames. The frame
  must match `ref_render.py` at scroll 8; `scroll_x == 8` and `hal_input`
  is the GB `J_RIGHT` bit (`0x01`).

The keypad values used by the input tests correspond to the libws
`WS_KEY_*` constants:

| Button | Constant | Value |
| --- | --- | --- |
| A | `WS_KEY_A` | `0x0004` |
| X1 (up) | `WS_KEY_X1` | `0x0010` |
