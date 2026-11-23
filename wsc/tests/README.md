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
  `ram` may also be a path (relative to `wsc/`) to a JSON list of such
  checks. The test build may generate that file, as `datarom` does with its
  Python oracle.

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
  hand-made GB background and sprite data, so the frame must match
  `ref_render.py` at scroll 0 exactly; `scroll_x == 0`, `player_x == 16`,
  `player_y == 24`, `sprite_count == 6` and `hal_frames` is 30 +/- 2.
- `hal-scroll`: holds X2 (right) from frame 10 for 60 frames. The frame
  must match `ref_render.py` at scroll 8; `scroll_x == 8` and `hal_input`
  is the GB `J_RIGHT` bit (`0x01`). `player_x` also moves with X2, so the
  reference is given its post-latch visible x position (`--player-x 64`).
- `spr-static`: same ROM with no input. The 8x16 player metasprite and the
  H+V-flipped 8x8 metasprite must match the reference exactly; the RAM
  checks cover `player_x`, `player_y`, `sprite_count` and `scroll_x`.
- `spr-move`: holds X2 for frames 10-29 and X3 for frames 30-59. It checks
  the final player position (36, 54) in RAM and the exact reference frame.
  The WSC latches the sprite table at line 142, so the visible frame uses
  the previous y (52); the reference is given that latched position.
- `spr-overlap`: moves the player right until it overlaps the other
  metasprite, then releases the button. The exact reference pins the WSC
  sprite-to-sprite rule that the lower table index is drawn on top.

The keypad values used by the input tests correspond to the libws
`WS_KEY_*` constants:

| Button | Constant | Value |
| --- | --- | --- |
| A | `WS_KEY_A` | `0x0004` |
| X1 (up) | `WS_KEY_X1` | `0x0010` |

- `walk-free`: runs `gamerom_town_walk`, the town scene starting at tile
  (14, 41). It waits for the boot, holds X3 (down) for three tiles, then X2
  (right) for four tiles. `wsc/tools/walk_oracle.py` simulates the topdown
  collision rules from the exported collision map, then uses the camera rules
  and `ref_render.py` for an exact frame. The RAM checks pin the player at
  (144, 352) and the camera at (152, 360) pixels, i.e. scroll (40, 288).
- `walk-wall`: the same ROM holds X3 from frame 40. The player walks down
  until the solid last rows stop it at tile (14, 51); the RAM check pins
  `y = 408` pixels.
- `datarom`: links every post-processed exported data object and the converted
  scripts, then reads each scene through the bankdata helpers. Its RAM checks
  are generated by `wsc/tools/datarom_oracle.py` from the project JSON,
  exported C and s2c output; see `wsc/datarom/`.
- `script-actors`: runs `gamerom_c13`, the town data with a test init script.
  It sets and moves the Duck actor, selects direction and animation frame,
  deactivates/reactivates the Cat, switches to 8x8 sprites and moves the
  camera. `wsc/tools/c13_oracle.py` renders the final frame; the RAM checks
  pin both actors' fields and the camera.
- `overlay-mid` / `overlay-rest`: run `gamerom_c14`, the town data with an
  init script that opens the screen-2 window, moves it in from the bottom at
  1 pixel per frame, clears a framed area and waits for the window. The mid
  frame (60) is still moving; the rest frame (100) is at y=72. The RAM checks
  pin `win_pos_x`, `win_pos_y` and the destination y. `wsc/tools/overlay_oracle.py`
  renders the window cells and applies the same GB actor-hiding rule as the
  engine. `boot-logo` now waits until its own overlay has moved off-screen
  again (frame 200).
- `text-instant` / `text-wait` / `text-wait-a`: run `gamerom_c15_instant`,
  which opens the overlay at (8, 8) and prints `Wow! Found\nGOLD COIN.` at
  text speed index 0. `wsc/tools/text_oracle.py` composes the glyph tiles
  from the exported variable-width font and renders the window. `text-wait`
  holds no buttons and checks that the script is still in its modal wait
  (`VAR_QUEST10 == 0`); `text-wait-a` holds A from frame 30 and checks that
  it continued (`VAR_QUEST10 == 1`).
- `text-speed`: `gamerom_c15_speed` prints the same text at speed index 2
  (`\001\003`). `ui_time_masks[2]` is 1, so one character is rendered every
  other game frame; frame 40 shows the first eight characters. The oracle
  uses `max(0, (frames - 23) // 2)` render calls for that speed.
- `text-var`: `gamerom_c15_var` sets `VAR_QUEST10 = -42` and
  `VAR_TURNIP_COUNTER = 1234`, then prints `Var: %d and %d.` at instant
  speed. The frame pins the `-` sign and multi-digit formatting.
- `choice-frame` / `choice-down-a` / `choice-cancel`: run
  `gamerom_c16_choice`, which prints `Pick one:` and three labels, then runs
  a vertical 3-item `VM_CHOICE` (`UI_MENU_LAST_0 | UI_MENU_CANCEL_B`) after
  setting `VAR_QUEST10 = 7`. `choice-frame` holds no input and shows the
  cursor on item 1 (row 2); the oracle adds the cursor tile to the window
  map. `choice-down-a` presses down once (item 1's link to item 2) and then
  A; the result is 2 and the script moves the overlay to y=18 tiles, so the
  frame is the town without the window. `choice-cancel` presses B; the
  result is 0. All three check `vm_last_unimplemented_opcode == 0`.

- `tiles-big`: runs `gamerom_c18_big`, a generated 16x18 background with
  264 unique bank-0 tiles, a 4-tile `cgb_tileset` and attribute-bit-3
  cells. The reference (`c18_oracle.py --mode big`) has its own copy of the
  WSC tile layout and puts the bank-0 overflow and cgb tiles at bank-1
  0..7, so the exact frame proves the overflow used the background
  conversion and the bank-1 window.
- `blank-border`: runs `gamerom_c18_blank`, the exported logo background
  (20x18, centred on the 224-px screen) with a long dialogue box at
  (64, 32). Eight lines walk the text tile buffer from `0xCC` to `0xFF`;
  the 32-px border on each side must stay blank. `c18_oracle.py --mode blank`
  renders the background, frame and glyph tiles from the exported data.
