# GB differential oracle

`make -C wsc gb-oracle` builds the GB oracle ROM with the pre-WSC GB Studio
engine, builds the WSC gamerom, and compares every config in `wsc/oracle/`
tick by tick. Today those are the town topdown walk and the PLATFORM scenes
(`platform-deeper`, `platform-path`, `platform-parallax`) plus the focused
regressions and the POINTNCLICK scene:

- `platform-deeper-ladder` uses the original ladder-release tick and checks
  that SameBoy's key-bounce emulation does not shift an input edge.
- `platform-parallax-actors` walks past the Parallax Example Elephant and Sign
  Post. Their activation is viewport-dependent, so the config opts into
  ignoring only the animation-phase fields of an actor whose activation
  differed outside the GB viewport; positions, direction and movement are
  still compared.
- `platform-path-hazard` falls into the Path to Sample Town pit, which enters
  BLANK state and runs the blank callback attached through `VM_CALL_NATIVE`.
- `topdown-npc` keeps the town player still for 240 ticks so the Pet Owner's
  update script starts, waits, draws a random direction and moves. GB and WSC
  compare every active actor's position, direction and animation; `rngSync`
  makes the two random walks identical.
- `pointnclick` drives the Player's House cursor to its right, bottom and left
  bounds and then back onto the window trigger. The final A press opens that
  trigger's dialogue, so the run covers cursor movement, clamps, trigger
  hover animation and trigger script execution. The scene has no actors, so
  there is no actor-click path to cover.

`platform.json` is the GB-only jump trace used by `gb-platform-smoke`, so
`gb-oracle` runs that one in `--platform-smoke` mode and the rest as full
comparisons.

`adventure-town` runs the Sample Town scene with its type changed to
ADVENTURE. The change comes from `variants/adventure-town.json`, not from the
template: `gbdiff` patches the same project copy it builds for the GB side and
exports a patched copy for a separate WSC gamerom build. The route slides
diagonally along the row-40 wall, climbs the corridor, interacts with the
Angry Guy script and then sweeps the lower area with diagonals. It compares
the adventure engine fields and runtime state (`adv_*`) in both screen widths.

`bounds` covers the screen-independent camera-bounds path. Its variant
(`variants/bounds.json`) gives Sample Town a custom `scrollBounds` rectangle
and adds a timer script that calls Set Camera Bounds with a wider rectangle
at tick 130. The route holds right along the open row-41 corridor, so the
camera first clamps to the scene's rectangle (right edge 240 px) and then to
the script's rectangle (right edge 320 px). At 160 px the run compares scroll
with GB directly. At 224 px `cameraBounds` in the config lists the two
rectangles and their `fromTick`; `gbdiff` derives the expected WSC scroll as
`clamp(GB camera centre - 112, left, max(left, right - 224))` (and the
144-px equivalent for Y) instead of comparing against GB's 160 px clamp.

`save-load` is a two-run comparison. Both runs boot the title screen. The
`save-title` variant points the title's New Game branch at the Cave save
point. Run 1 selects New Game, interacts with the save point and writes its
platform-specific SRAM; run 2 starts with that SRAM, selects Continue and
loads it. Player, actor and script variable state is compared in both runs,
including the ticks after the load. A run is:

```json
{"name": "save", "ticks": 260, "frames": 6000,
 "input": "inputs/save-save.txt", "save": "run1"}
```

`save` writes `<side>-<stem>.sram` under the config's work directory and
`load` reads it back. `gbdiff` passes the file through `wsrun --sram-out` /
`--sram-in`.

`game_time` is reset inside the scene-change and load exception handlers, but
the handler itself is not a completed engine tick. `gbdiff` therefore samples
every run with `wsrun --tick-gate` on `vm_exception_code`: a tick change seen
while an exception is in progress is dropped, and the next change after the
handler ends is recorded. Both sides then compare the first complete tick of
the new scene (and, for the load run, the first complete tick after the load)
rather than a frame boundary inside the handler.

`shmup-cull` is a 160 px Space Battle route with an A-button player bullet.
Its variant slows the shooter auto-scroll to `16` subpixels per tick so the
bullet reaches the 20-tile right-hand cull edge while it still has lifetime
left; this is the C25 culling path. Reverting the culling fix to the physical
28-tile device width makes this config diverge at 160 px.

Every WSC comparison runs in both logical screen widths by default:
`"screenWidth": "both"` runs 160 px and 224 px. `wsrun --screen-width 160` patches the byte
after the boot id in the gamerom's `WSCBOOT` ROM slot, so the engine starts
with a GB-sized viewport before it loads its first scene. In 160 px mode
`gbdiff` additionally compares `camera_x`, `camera_y`, `scroll_x` and
`scroll_y`, and it does not ignore off-screen activation or viewport-caused
animation phases: the WSC viewport is now identical to the GB one, so any
such difference is a real bug. The 224 px run keeps the older exclusions.

`shmup.json` is the Space Battle SHMUP comparison (movement, screen clamps,
auto-scroll, enemy scripts, projectiles and the player hit). It sets
`"screenWidth": 160` because the scene's `shooter_dest`, player clamp, actor
activation window and projectile culling are all defined by the GB's 160 px
viewport and would change on the native 224 px WSC playfield.

The comparison front end is `wsc/tools/gbdiff.py`. Each `*.json` here selects
the start scene, tick count, input script and the explicit intended
differences. `inputs/*.txt` lines are `TICK BUTTONS` (tick-relative, not
emulator frames; multiple buttons are comma-separated).

A config can add `"variant": "<name>"`. Variants live in `variants/<name>.json`
as a JSON list of `{"file", "path", "value"}` edits. `file` is relative to
the template's `project/` data directory, `path` is a dot-separated JSON path
(numeric segments index arrays, a final `-` appends), and `value` is the new
JSON value. For example, `adventure-town.json` sets
`scenes/town/sample_town/scene.gbsres` path `type` to `"ADVENTURE"` and
appends non-default `adv_*` engine field values to
`engine_field_values.gbsres`.

With a variant, gbdiff applies the edits to its temporary GB project copy
before the CLI builds the GB ROM. For WSC it writes a separate project copy
under `wsc/build/variants/<name>/project`, exports it with
`wsc/export/run.sh`'s `TEMPLATE` override into
`wsc/build/variants/<name>/export`, and builds that export with its own
`BUILDDIR`, `GEN_DIR` and `ROM` under the same directory. The normal
gamerom (`wsc/gamerom/gamerom.wsc`, `wsc/build/gamerom`, `wsc/build/export`)
is not touched by a variant. The GB ROM cache key includes the variant file's
SHA-256, so editing a variant rebuilds the GB ROM; the WSC export is skipped
until the variant digest changes, while `make` still relinks when engine
sources change.

Screen width is selected with the gamerom's `WSCBOOT` slot: byte 7 is the
boot id and byte 8 the logical width in pixels (default 224). The engine calls
`hal_screen_set_width()` from `wsc_boot_select()`, before the first scene, so
`hal_screen_w*`, the scroll padding/refresh sizes, camera and actor activation
all see the selected width. The WSC display itself stays 224 px wide; a
160 px logical screen is centred and only that region needs to be correct.

Platform configs add the state-machine/velocity symbols to `playerFields`
(`plat_vel_x`, `plat_vel_y`, `plat_state`, `plat_grounded`, jump/ladder
counters, and so on). SHMUP adds `shooter_scroll_speed`,
`shooter_reached_end`, `shooter_dest`, `shooter_direction` and
`player_iframes`; POINTNCLICK adds `last_hit_trigger`; ADVENTURE adds the
`adv_*` engine fields and runtime state (walk/run/knockback/dash/push
configuration, velocity, state, attached-actor tracking and timers). Their
sizes are listed in `STATE_FIELDS` in `gbdiff.py` and resolved from each
side's own symbol table, like the existing player fields. A config with `"variableIndices"` compares those 16-bit words of
`script_memory` on every tick. The `save-load` config compares words 0-39,
which covers the menu and save-point local variables. A config with
`projectileFields` walks `projectiles_active_head` on both sides and compares
each active projectile's position, delta, frame and remaining lifetime; the
`projectile_t`/`projectile_def_t` offsets come from the same compiled
offsetof probe as the actor layout.

Parallax configs add `parallaxFields`: `scx`, `shadow_scx`, `next_y`, `shift`,
`start_tile` and `tile_height` for each of the three `parallax_rows` bands.
At 160 px every value is compared with the GB band state directly. At 224 px
the WSC viewport is 64 px wider, so `scx`/`shadow_scx` are legitimately
viewport-relative. `gbdiff` derives the expected WSC scroll from the GB
`scroll_x` and `image_width`: `clamp(gb_scroll_x - 32, 0, image_width - 224)`
(or the centred origin for a scene narrower than 224), applies the GB band
`shift`, and compares that with the WSC band value. The five width-independent
band fields are still compared raw with GB. The live `scx` at 160 px is one
trace sample behind GB because the WSC trace lands after the vblank latch
copy and the GB trace before it; the comparison follows that latch.

`make -C wsc parallax-visual` is the independent hardware-path check. It
captures GB and WSC frames at ticks 100, 200 and 300 in 160 px mode and
compares each band's background against the GB reference render by
cross-correlating binary horizontal-edge maps. A wrong or missing screen-1
scroll write moves that band's best offset away from 0 even though the
engine RAM (and therefore `gbdiff`) still matches.

Script banks are numbered from 1 (`s2c_bank1`, ...) by `s2c.py`, and the
zero slot in `vm_bank_base()`'s table is unused, so the engine's `.bank`
presence tests keep the GB meaning of "bank 0 = no script". The town and
path scenes have actors with update/interact scripts, so those scripts run on
WSC exactly as they do on GB.

A config with `"rngSync": true` copies the GB `__rand_seed` value at tick 1
into the WSC `__rand_seed` RAM word with a `wsrun --poke` before the first
counted frame. The WSC `randw()` uses GBDK-2020 4.5.0's 16-bit LCG
(`X = 17*X + 0x5C93`) and returns it byte-swapped like GBDK's assembly, so
the `VM_RAND` results match. No RNG is consumed before the first waited
script, so the copied state stays aligned.

## What it builds

- GB compiler and engine: both come from the same pinned revision
  `b242ab79fd8a6aa0fe41d43b51a345685b11f9c3`. `gbdiff` extracts that
  revision under `wsc/build/gb-cli/<revision>/repo`, symlinks the checkout's
  `node_modules`, and builds its CLI once (cached). The GB ROM is built by
  that CLI, so the GB side keeps the pinned compiler's screen-subtracted
  bounds while the WSC side uses the current compiler's raw rectangles.
- GB engine: `b242ab79fd8a6aa0fe41d43b51a345685b11f9c3`, the last
  `appData/engine/gbvm` revision before the WSC port. The pinned CLI's own
  engine is used directly; no local-engine overlay or WSC stubs are needed.
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
- Script banks: `s2c.py` packs converted scripts into banks numbered from 1.
  `d2c.py` writes those numbers into every generated `far_ptr_t` and
  `D2C_BANK_LIST`, and the gamerom/datarom `vm_bank_base()` tables reserve
  slot 0 for "no script".

## Addresses and layouts

No RAM address is hard-coded. GB addresses come from the linker `.noi`, WSC
addresses from the ELF symbol table. CGB WRAM is mapped to SameBoy's 8-bank
dump (C000-CFFF is bank 0, D000-DFFF is bank 1, the GBDK default).

Struct offsets are compiled at run time by the real toolchains: an
`offsetof(actor_t, ...)` probe is assembled with SDCC (GB) and compiled with
gcc-ia16 (WSC). This is why the two actor layouts differ (56 vs 68 bytes).
