import fs from "fs";
import os from "os";
import Path from "path";
import {
  farDataDef,
  parseStates,
  processSource,
  writeBootstrap,
  writeStates,
} from "../../../src/lib/compiler/wsc/d2c";

const temporaryDir = (): string =>
  fs.mkdtempSync(Path.join(os.tmpdir(), "d2c-test-"));

const script = (bank: number, offset: number) => ({
  bank,
  offset,
  size: 16,
});

test("rewrites const objects and pointer arrays to far data", () => {
  expect(farDataDef("const unsigned char tiles[] = { 1, 2 };")).toBe(
    "const __far unsigned char tiles[] = { 1, 2 };",
  );
  expect(
    farDataDef("static const metasprite_t * const frames[] = { 0 };"),
  ).toBe("static const __far metasprite_t * const __far frames[] = { 0 };");
  expect(
    farDataDef("const unsigned char __far already[] = { 1 };"),
  ).toBe("const unsigned char __far already[] = { 1 };");
});

test("rewrites script references and empty CGB tile sets", () => {
  const scripts = new Map([["actor_1_update", script(2, 0x1a)]]);
  const input = [
    "const struct actor_t actors[] = {",
    "    .script_update = TO_FAR_PTR_T(actor_1_update),",
    "    .cgb_tileset = { NULL, NULL },",
    "};",
    "",
  ].join("\n");
  const result = processSource(input, scripts, false);
  expect(result.text).toContain(
    ".script_update = { .bank = 2, .ptr = (const void __far *)" +
      "(s2c_bank2 + 0x001A) },",
  );
  expect(result.text).toContain(".cgb_tileset = { 0, NULL },");
});

test("parses and emits the state dispatch table", () => {
  const dir = temporaryDir();
  const source = Path.join(dir, "states_ptrs.s");
  fs.writeFileSync(
    source,
    [
      "_state_start_fns::",
      "        IMPORT_FAR_PTR _topdown_init",
      "        IMPORT_FAR_PTR _shmup_init",
      "",
      "_state_update_fns::",
      "        IMPORT_FAR_PTR _topdown_update",
      "        IMPORT_FAR_PTR _shmup_update",
      "",
    ].join("\n"),
  );
  const tables = parseStates(source);
  expect(tables).toEqual({
    start: ["topdown_init", "shmup_init"],
    update: ["topdown_update", "shmup_update"],
  });

  writeStates(dir, tables, new Set(["topdown"]));
  const states = fs.readFileSync(Path.join(dir, "states.c"), "utf8");
  expect(states).toContain("    topdown_init,\n    state_unavailable,");
  expect(states).toContain("    topdown_update,\n    state_unavailable,");
  expect(states).toContain("if (scene_type < 2) state_start_fns");
});

test("writes the bootstrap scene, fonts and platform globals", () => {
  const dir = temporaryDir();
  writeBootstrap(
    dir,
    {
      start_scene: "scene_cave",
      start_scene_x: 16,
      start_scene_dir: "DIR_LEFT",
      ui_fonts: ["font_a"],
      start_player_move_speed: 32,
      start_player_anim_tick: 15,
      globals: [{ name: "plat_grav", size: 16, value: 1792 }],
    },
    "product.h",
    new Set(["scene_cave", "scene_logo"]),
  );
  const bootstrap = fs.readFileSync(Path.join(dir, "bootstrap.c"), "utf8");
  expect(bootstrap).toContain("#define BOOT_START_SCENE scene_cave");
  expect(bootstrap).toContain("#define BOOT_START_X 16");
  expect(bootstrap).toContain("#define BOOT_START_DIR DIR_LEFT");
  expect(bootstrap).toContain("TO_FAR_PTR_T(font_a),");
  expect(bootstrap).toContain("__attribute__((weak)) WORD plat_grav;");
  expect(bootstrap).toContain("    plat_grav = 1792;");
});
