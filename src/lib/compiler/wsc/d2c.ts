/**
 * TypeScript port of wsc/tools/d2c.py.
 *
 * The Python tool is the oracle: this file must produce byte-identical
 * generated trees. It is self-contained on purpose so the wsc Makefiles can
 * run it through wsc/tools/d2c-ts.js without a build step (Node 24 strips
 * types), and so the CLI can bundle it and run it in-process.
 *
 * Only erasable TypeScript syntax is used.
 */

import * as fs from "node:fs";
import * as path from "node:path";

// File-scope object definitions: const/static const ...
const DEFINITION_RE = /^(\s*)(static\s+)?const\s+(.+)$/;

// Pointer arrays such as `const metasprite_t * const foo[]` and
// `static const unsigned char* const order1[]`. Both the pointee and the
// pointer array itself have to be far, because the pointee lives in far ROM.
const PTR_ARRAY_RE =
  /^(\s*(?:static\s+)?const)\s+(.+?)\s*\*\s*const\s+([A-Za-z_]\w*)\s*\[\s*\]\s*=/;

// `extern const ...` declarations in generated headers must carry the same
// named address space as their definitions.
const EXTERN_CONST_RE = /^(\s*)extern\s+const\s+(.+)$/;

const BANKREF_RE = /^\s*BANKREF\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;?\s*$/;
const BANKREF_EXTERN_RE =
  /^\s*BANKREF_EXTERN\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;?\s*$/;
const PRAGMA_BANK_RE = /^\s*#pragma\s+bank\b.*$/;
const BANK_OBJECT_RE =
  /^\s*(?:extern\s+)?const\s+void\s+(?:__at\s*\([^)]*\)\s+)?__bank_\w+\s*;\s*$/;
const MUTE_MASK_RE =
  /^\s*void\s+AT\s*\([^)]*\)\s+__mute_mask_\w+\s*;\s*$/;

const TO_FAR_PTR_RE = /TO_FAR_PTR_T\s*\(\s*([A-Za-z_]\w*)\s*\)/g;
const SCENE_DEF_RE =
  /^\s*const\s+(?:__far\s+)?struct\s+scene_t\s+([A-Za-z_]\w*)\s*=/;
const SCRIPT_DEF_RE =
  /^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_BANK\s+([0-9]+)\s*$/gm;
const SCRIPT_OFF_RE =
  /^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_OFFSET\s+0x([0-9A-Fa-f]+)\s*$/gm;
const SCRIPT_SIZE_RE =
  /^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_SIZE\s+0x([0-9A-Fa-f]+)\s*$/gm;
const BANK_DECL_RE =
  /^extern\s+const\s+uint8_t\s+S2C_FAR\s+(s2c_bank[0-9]+)\s*\[\s*\]\s*;$/gm;

export class ConvertError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConvertError";
  }
}

/** Python's Path.read_text(): UTF-8 with universal newlines. */
function readText(file: string): string {
  return fs.readFileSync(file, "utf8").replace(/\r\n?/g, "\n");
}

function writeText(file: string, text: string): void {
  fs.writeFileSync(file, text, "utf8");
}

/** Python's str.splitlines() for text that went through readText(). */
function splitLines(text: string): string[] {
  if (text === "") return [];
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  return lines;
}

function findAll(text: string, re: RegExp): RegExpExecArray[] {
  const matches: RegExpExecArray[] = [];
  re.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    matches.push(match);
    if (match[0].length === 0) re.lastIndex += 1;
  }
  return matches;
}

function listFilesRecursive(root: string): string[] {
  const out: string[] = [];
  const walk = (dir: string): void => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else out.push(full);
    }
  };
  walk(root);
  out.sort();
  return out;
}

/** Python's int(text, 0), restricted to the forms the exporter emits. */
function parsePyInt(text: string): number {
  const value = text.trim();
  const match = /^([+-]?)(0[xX][0-9A-Fa-f]+|[0-9]+)$/.exec(value);
  if (!match) throw new ConvertError(`invalid literal for int(): ${text}`);
  const sign = match[1] === "-" ? -1 : 1;
  const digits = match[2];
  if (/^0[xX]/.test(digits)) {
    return sign * parseInt(digits.slice(2), 16);
  }
  return sign * parseInt(digits, 10);
}

function format4(value: number): string {
  return value.toString(16).toUpperCase().padStart(4, "0");
}

type Script = { bank: number; offset: number; size: number };

/** Return {script name: (bank, offset, size)} from an s2c header. */
export function readScripts(headerPath: string): Map<string, Script> {
  let text: string;
  try {
    text = readText(headerPath);
  } catch (error) {
    throw new ConvertError(
      `cannot read ${headerPath}: ${(error as Error).message}`,
    );
  }
  const banks = new Map<string, number>();
  const offsets = new Map<string, number>();
  const sizes = new Map<string, number>();
  for (const match of findAll(text, SCRIPT_DEF_RE)) {
    banks.set(match[1], parseInt(match[2], 10));
  }
  for (const match of findAll(text, SCRIPT_OFF_RE)) {
    offsets.set(match[1], parseInt(match[2], 16));
  }
  for (const match of findAll(text, SCRIPT_SIZE_RE)) {
    sizes.set(match[1], parseInt(match[2], 16));
  }
  const scripts = new Map<string, Script>();
  for (const [upper, bank] of banks) {
    if (!offsets.has(upper) || !sizes.has(upper)) {
      throw new ConvertError(`incomplete s2c macros for ${upper}`);
    }
    scripts.set(upper.toLowerCase(), {
      bank,
      offset: offsets.get(upper) as number,
      size: sizes.get(upper) as number,
    });
  }
  return scripts;
}

export function readBankSymbols(headerPath: string): string[] {
  let text: string;
  try {
    text = readText(headerPath);
  } catch (error) {
    throw new ConvertError(
      `cannot read ${headerPath}: ${(error as Error).message}`,
    );
  }
  const names = new Set<string>();
  for (const match of findAll(text, BANK_DECL_RE)) names.add(match[1]);
  return Array.from(names).sort(
    (left, right) => parseInt(left.slice(8), 10) - parseInt(right.slice(8), 10),
  );
}

/** Turn one file-scope const definition into far ROM data. */
export function farDataDef(line: string): string {
  const array = PTR_ARRAY_RE.exec(line);
  if (array) {
    const head = `${array[1]} __far ${array[2]} * const __far ${array[3]}[] =`;
    return head + line.slice(array[0].length);
  }

  const match = DEFINITION_RE.exec(line);
  if (!match) return line;
  const rest = match[3];
  // Leave declarations such as `const void __at(...) __bank_x;` to the
  // bank-marker rule and anything that is not a definition alone.
  if (rest.includes("__bank_") || rest.startsWith("void ")) return line;
  if (!rest.includes("=") && !rest.includes("[")) return line;
  const beforeEqual = rest.split("=", 1)[0];
  if (beforeEqual.includes("__far")) return line;
  return `${match[1]}${match[2] || ""}const __far ${match[3]}`;
}

export function farDataExtern(line: string): string {
  const match = EXTERN_CONST_RE.exec(line);
  if (!match) return line;
  const rest = match[2];
  if (rest.includes("__bank_") || rest.startsWith("void ")) return line;
  if (rest.includes("__far")) return line;
  return `${match[1]}extern const __far ${match[2]}`;
}

/** Rewrite one generated C source or header. Returns (text, scene names). */
export function processSource(
  text: string,
  scripts: Map<string, Script>,
  isHeader: boolean,
): { text: string; scenes: string[] } {
  const scenes: string[] = [];
  const out: string[] = [];
  for (let line of splitLines(text)) {
    if (BANKREF_RE.test(line) || BANKREF_EXTERN_RE.test(line)) continue;
    if (
      PRAGMA_BANK_RE.test(line) ||
      BANK_OBJECT_RE.test(line) ||
      MUTE_MASK_RE.test(line)
    ) {
      continue;
    }

    line = line.replace(
      TO_FAR_PTR_RE,
      (whole: string, name: string): string => {
        const script = scripts.get(name);
        if (!script) return whole;
        const { bank, offset } = script;
        return (
          `{ .bank = ${bank}, .ptr = (const void __far *)` +
          `(s2c_bank${bank} + 0x${format4(offset)}) }`
        );
      },
    );
    // The compiler emits `{ NULL, NULL }` for an empty cgb_tileset.
    // A far_ptr_t's first member is the bank byte, so the pointer NULL
    // must not be used as its initializer.
    line = line.split("{ NULL, NULL }").join("{ 0, NULL }");

    if (!isHeader) {
      const scene = SCENE_DEF_RE.exec(line);
      if (scene) scenes.push(scene[1]);
      line = farDataDef(line);
    } else {
      line = farDataExtern(line);
    }
    out.push(line);
  }
  return { text: out.join("\n") + (text.endsWith("\n") ? "\n" : ""), scenes };
}

export function writeBuildInclude(
  outDir: string,
  s2cHeaderName: string,
  scripts: Map<string, Script>,
  bankSymbols: string[],
  scenes: string[],
): void {
  const include = path.join(outDir, "include");
  fs.mkdirSync(include, { recursive: true });

  const lines = [
    "/* Generated by wsc/tools/d2c.py. Do not edit. */",
    "#ifndef D2C_SCRIPTS_H",
    "#define D2C_SCRIPTS_H",
    "",
    `#include "${s2cHeaderName}"`,
    "",
  ];
  for (const name of Array.from(scripts.keys()).sort()) {
    const script = scripts.get(name) as Script;
    lines.push(
      `#define S2C_FPTR_${name} { .bank = ${script.bank}, .ptr = ` +
        `(const void __far *)(s2c_bank${script.bank} + ` +
        `0x${format4(script.offset)}) }`,
    );
  }
  lines.push("", "#endif", "");
  writeText(path.join(include, "d2c_scripts.h"), lines.join("\n"));

  const manifest = [
    "/* Generated by wsc/tools/d2c.py. Do not edit. */",
    "#ifndef D2C_MANIFEST_H",
    "#define D2C_MANIFEST_H",
    "",
    '#include "gbs_types.h"',
    "",
    "/* Script banks are numbered from 1; slot 0 in a bank table means",
    ' * "no script" and is never one of these entries. */',
    `#define D2C_BANK_COUNT ${bankSymbols.length}`,
    `#define D2C_BANK_LIST ${bankSymbols.join(", ")}`,
    `#define D2C_SCENE_COUNT ${scenes.length}`,
  ];
  for (const scene of scenes) {
    manifest.push(`extern const __far struct scene_t ${scene};`);
  }
  manifest.push(
    `#define D2C_SCENE_LIST ${scenes.map((scene) => "&" + scene).join(", ")}`,
  );
  manifest.push("", "#endif", "");
  writeText(path.join(include, "d2c_manifest.h"), manifest.join("\n"));
}

export function copyTransform(
  exportData: string,
  outData: string,
  scripts: Map<string, Script>,
  isHeader: boolean,
): string[] {
  const scenes: string[] = [];
  for (const file of listFilesRecursive(exportData)) {
    if (!file.endsWith(".c") && !file.endsWith(".h")) continue;
    const relative = path.relative(exportData, file);
    const destination = path.join(outData, relative);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    let text: string;
    try {
      text = readText(file);
    } catch (error) {
      throw new ConvertError(
        `cannot read ${file}: ${(error as Error).message}`,
      );
    }
    const processed = processSource(text, scripts, isHeader);
    text = processed.text;
    if (!isHeader) {
      const header = '#include "d2c_scripts.h"\n';
      if (!text.includes(header)) text = header + text;
      scenes.push(...processed.scenes);
    }
    writeText(destination, text);
  }
  return scenes;
}

export function transformHugeHeaders(
  exportInclude: string,
  outInclude: string,
): void {
  for (const name of ["hUGEDriver.h", "hUGEDriverRoutines.h"]) {
    const source = path.join(exportInclude, name);
    if (!fs.statSync(source, { throwIfNoEntry: false })?.isFile()) continue;
    let text = readText(source);
    const replace = (from: string, to: string): void => {
      text = text.split(from).join(to);
    };
    replace(
      "const unsigned char * subpattern;",
      "const unsigned char __far * subpattern;",
    );
    replace(
      "const unsigned char * order_cnt;",
      "const unsigned char __far * order_cnt;",
    );
    replace(
      "const unsigned char ** order1, ** order2, ** order3, ** order4;",
      "const unsigned char __far * const __far * order1,\n" +
        "    * const __far * order2, * const __far * order3,\n" +
        "    * const __far * order4;",
    );
    replace(
      "const hUGEDutyInstr_t * duty_instruments;",
      "const hUGEDutyInstr_t __far * duty_instruments;",
    );
    replace(
      "const hUGEWaveInstr_t * wave_instruments;",
      "const hUGEWaveInstr_t __far * wave_instruments;",
    );
    replace(
      "const hUGENoiseInstr_t * noise_instruments;",
      "const hUGENoiseInstr_t __far * noise_instruments;",
    );
    replace(
      "const hUGERoutine_t ** routines;",
      "const hUGERoutine_t __far * routines;",
    );
    replace(
      "const unsigned char * waves;",
      "const unsigned char __far * waves;",
    );
    replace(
      "static const hUGERoutine_t routines[]",
      "static const __far hUGERoutine_t routines[]",
    );
    writeText(path.join(outInclude, name), text);
  }
}

/** Read NAME = VALUE lines from the exported .i files. */
export function parseConstants(includeDir: string): Map<string, number> {
  const values = new Map<string, number>();
  for (const file of listFilesRecursive(includeDir)) {
    if (!file.endsWith(".i")) continue;
    let text: string;
    try {
      text = readText(file);
    } catch (error) {
      throw new ConvertError(
        `cannot read ${file}: ${(error as Error).message}`,
      );
    }
    for (const line of splitLines(text)) {
      const match =
        /^\s*([A-Za-z_]\w*)\s*=\s*(-?0x[0-9A-Fa-f]+|-?[0-9]+)\s*$/.exec(line);
      if (match) {
        try {
          values.set(match[1], parsePyInt(match[2]));
        } catch {
          // The regex only admits integer literals, so this cannot happen.
        }
      }
    }
  }
  return values;
}

function evalValue(token: string, constants: Map<string, number>): number {
  let value = token.trim();
  if (value.startsWith(".")) value = value.slice(1);
  if (constants.has(value)) return constants.get(value) as number;
  try {
    return parsePyInt(value);
  } catch {
    return 0;
  }
}

export type EngineGlobals = { name: string; size: number; value: number };

export type EngineInit = {
  start_scene_x?: number;
  start_scene_y?: number;
  start_scene_dir?: string;
  start_scene?: string | null;
  start_player_move_speed?: number;
  start_player_anim_tick?: number;
  ui_fonts?: string[];
  globals: EngineGlobals[];
};

/** Extract the bootstrap data prefix and the platform globals script. */
export function parseEngineInit(
  file: string,
  constants: Map<string, number>,
): EngineInit {
  let lines: string[];
  try {
    lines = splitLines(readText(file));
  } catch (error) {
    throw new ConvertError(`cannot read ${file}: ${(error as Error).message}`);
  }

  const data: EngineInit = { globals: [] };
  let i = 0;
  while (i < lines.length) {
    const match =
      /^_(start_scene_x|start_scene_y|start_scene_dir|start_scene|start_player_move_speed|start_player_anim_tick|ui_fonts)::\s*(.*)$/.exec(
        lines[i],
      );
    if (!match) {
      i += 1;
      continue;
    }
    const name = match[1];
    let rest = match[2].trim();
    if (name === "ui_fonts") {
      const fonts: string[] = [];
      let j = i + 1;
      while (j < lines.length) {
        const font = /^\s*IMPORT_FAR_PTR_DATA\s+_(\w+)\s*$/.exec(lines[j]);
        if (font) {
          fonts.push(font[1]);
          j += 1;
          continue;
        }
        if (lines[j].trim() && !lines[j].replace(/^\s+/, "").startsWith(";")) {
          break;
        }
        j += 1;
      }
      data.ui_fonts = fonts;
      i = j;
      continue;
    }
    if (!rest && i + 1 < lines.length) rest = lines[i + 1].trim();
    if (name === "start_scene") {
      const scene = /^IMPORT_FAR_PTR_DATA\s+_(\w+)/.exec(rest);
      data.start_scene = scene ? scene[1] : null;
    } else if (name === "start_scene_dir") {
      const value = rest.replace(/^\.db\s+/, "").trim();
      data.start_scene_dir = value.replace(/^\.+/, "");
    } else {
      const value = /^\.d[bw]\s+(-?0x[0-9A-Fa-f]+|-?[0-9]+)/.exec(rest);
      const parsed = value ? parsePyInt(value[1]) : 0;
      if (name === "start_scene_x") data.start_scene_x = parsed;
      else if (name === "start_scene_y") data.start_scene_y = parsed;
      else if (name === "start_player_move_speed") {
        data.start_player_move_speed = parsed;
      } else if (name === "start_player_anim_tick") {
        data.start_player_anim_tick = parsed;
      }
    }
    i += 1;
  }

  const globals: EngineGlobals[] = [];
  let last: { size: number; value: number } | null = null;
  let inInit = false;
  for (const line of lines) {
    if (line.trim().startsWith("_script_engine_init::")) {
      inInit = true;
      continue;
    }
    if (!inInit) continue;
    const int = /^\s*\.R_INT(8|16)\s+(\S+)/.exec(line);
    if (int) {
      last = {
        size: parseInt(int[1], 10),
        value: evalValue(int[2], constants),
      };
      continue;
    }
    const set = /^\s*\.R_REF_MEM_SET\s+\.MEM_I(8|16)\s*,\s*_(\w+)/.exec(line);
    if (set && last !== null) {
      globals.push({
        name: set[2],
        size: parseInt(set[1], 10),
        value: last.value,
      });
      last = null;
    }
  }
  data.globals = globals;
  return data;
}

export type StateTables = { start: string[]; update: string[] };

export function parseStates(file: string): StateTables {
  let lines: string[];
  try {
    lines = splitLines(readText(file));
  } catch (error) {
    throw new ConvertError(`cannot read ${file}: ${(error as Error).message}`);
  }
  const tables: StateTables = { start: [], update: [] };
  let current: "start" | "update" | null = null;
  for (const line of lines) {
    const stripped = line.trim();
    if (stripped.startsWith("_state_start_fns::")) {
      current = "start";
      continue;
    }
    if (stripped.startsWith("_state_update_fns::")) {
      current = "update";
      continue;
    }
    const match = /^IMPORT_FAR_PTR\s+_(\w+)/.exec(stripped);
    if (match && current) tables[current].push(match[1]);
  }
  return tables;
}

export function writeBootstrap(
  outDir: string,
  initData: EngineInit,
  s2cHeaderName: string,
  scenes: Set<string>,
): void {
  void s2cHeaderName;
  const out = path.join(outDir, "bootstrap.c");
  const startScene = initData.start_scene || "scene_logo";
  if (!scenes.has(startScene)) {
    throw new ConvertError(
      `start scene ${startScene} is not an exported scene`,
    );
  }
  const get = <T>(key: keyof EngineInit, fallback: T): T => {
    const value = initData[key];
    return (value === undefined || value === null ? fallback : value) as T;
  };
  const lines = [
    "/* Generated by wsc/tools/d2c.py from script_engine_init.s. Do not edit. */",
    "#include <stdint.h>",
    '#include "gbdk/platform.h"',
    '#include "gbs_types.h"',
    '#include "data/data_bootstrap.h"',
  ];
  for (const font of initData.ui_fonts || []) {
    lines.push(`#include "data/${font}.h"`);
  }
  lines.push(
    "",
    "/* Defaults; the test image overrides the start scene at run time. */",
    "#ifndef BOOT_START_SCENE",
    `#define BOOT_START_SCENE ${startScene}`,
    "#endif",
    "#ifndef BOOT_START_X",
    `#define BOOT_START_X ${get("start_scene_x", 0)}`,
    "#endif",
    "#ifndef BOOT_START_Y",
    `#define BOOT_START_Y ${get("start_scene_y", 0)}`,
    "#endif",
    "#ifndef BOOT_START_DIR",
    `#define BOOT_START_DIR ${get("start_scene_dir", "DIR_RIGHT")}`,
    "#endif",
    "",
    "extern const __far struct scene_t BOOT_START_SCENE;",
    "",
    "/* These are not const so a platform can select a start scene at run time",
    " * (the WSC test image writes a boot id into its ROM). */",
    "INT16 start_scene_x = BOOT_START_X;",
    "INT16 start_scene_y = BOOT_START_Y;",
    "direction_e start_scene_dir = BOOT_START_DIR;",
    "far_ptr_t start_scene = {",
    "    .bank = 0,",
    "    .ptr = (const void __far *)&BOOT_START_SCENE",
    "};",
    `const __far UBYTE start_player_move_speed = ${get(
      "start_player_move_speed",
      32,
    )};`,
    `const __far UBYTE start_player_anim_tick = ${get(
      "start_player_anim_tick",
      15,
    )};`,
    "",
    "const __far far_ptr_t ui_fonts[] = {",
  );
  for (const font of initData.ui_fonts || []) {
    lines.push(`    TO_FAR_PTR_T(${font}),`);
  }
  lines.push(
    "};",
    "",
    "/* Implemented by the platform's boot table. */",
    "void wsc_boot_select(far_ptr_t *scene, INT16 *x, INT16 *y);",
    "",
    "/* Platform globals assigned by the script_engine_init VM routine. They",
    " * are weak so engine sources that define one keep their definition. */",
  );
  for (const global of initData.globals || []) {
    const ctype = global.size === 16 ? "WORD" : "UBYTE";
    lines.push(`__attribute__((weak)) ${ctype} ${global.name};`);
  }
  lines.push("", "void bootstrap_init(void) {");
  for (const global of initData.globals || []) {
    lines.push(`    ${global.name} = ${global.value};`);
  }
  lines.push(
    "    wsc_boot_select(&start_scene, &start_scene_x, &start_scene_y);",
    "}",
    "",
    "/* VM_LOCK, VM_RAISE(EXCEPTION_RESET, 0): platform globals are set by",
    " * bootstrap_init() instead of the GB script init routine. */",
    "const UBYTE bootstrap_script[] = { 0x25, 0x27, 0x00, 0x01, 0x00 };",
    "",
  );
  writeText(out, lines.join("\n"));

  // The runtime selector assigns these through pointers, so their public
  // declarations cannot stay const.
  const header = path.join(outDir, "include", "data", "data_bootstrap.h");
  if (fs.statSync(header, { throwIfNoEntry: false })?.isFile()) {
    let text = readText(header);
    for (const decl of [
      "INT16 start_scene_x;",
      "INT16 start_scene_y;",
      "direction_e start_scene_dir;",
      "far_ptr_t start_scene;",
    ]) {
      for (const prefix of ["extern const __far ", "extern const "]) {
        text = text.split(prefix + decl).join("extern " + decl);
      }
    }
    writeText(header, text);
  }
}

export function writeStates(
  outDir: string,
  tables: StateTables,
  implemented: Set<string>,
): void {
  const out = path.join(outDir, "states.c");
  const count = tables.start.length;
  if (count !== tables.update.length) {
    throw new ConvertError("state start/update tables differ in length");
  }

  const emitTable = (kind: string, names: string[]): string[] => {
    const result = [`const state_fn_t state_${kind}_fns[] = {`];
    for (const name of names) {
      let state = name;
      if (name.endsWith("_init")) state = name.slice(0, -"_init".length);
      else if (name.endsWith("_update")) {
        state = name.slice(0, -"_update".length);
      }
      if (implemented.has(state)) result.push(`    ${name},`);
      else result.push("    state_unavailable,");
    }
    result.push("};");
    return result;
  };

  const lines = [
    "/* Generated by wsc/tools/d2c.py from states_ptrs.s. Do not edit. */",
    '#include "gbdk/platform.h"',
    '#include "gbs_types.h"',
    '#include "data/scene_types.h"',
    '#include "data_manager.h"',
    '#include "states_caller.h"',
    '#include "states/topdown.h"',
    '#include "states/platform.h"',
    '#include "states/adventure.h"',
    '#include "states/shmup.h"',
    '#include "states/pointnclick.h"',
    "",
    "typedef void (*state_fn_t)(void);",
    "",
    "static void state_unavailable(void) {",
    "}",
    "",
  ];
  lines.push(...emitTable("start", tables.start));
  lines.push(...emitTable("update", tables.update));
  lines.push(
    "",
    "void state_init(void) {",
    `    if (scene_type < ${count}) state_start_fns[scene_type]();`,
    "}",
    "",
    "void state_update(void) {",
    `    if (scene_type < ${count}) state_update_fns[scene_type]();`,
    "}",
    "",
  );
  writeText(out, lines.join("\n"));
}

/** Define the engine RAM globals that scripts reach through vm_ram_syms[]. */
export function writeStubs(outDir: string, s2cSource: string): string[] {
  const text = readText(s2cSource);
  const names: string[] = [];
  for (const match of findAll(
    text,
    /^extern uint8_t ([A-Za-z_]\w*)\[\];$/gm,
  )) {
    names.push(match[1]);
  }
  const seen = new Set<string>();
  const lines = [
    "/* Generated by wsc/tools/d2c.py. Do not edit. */",
    "/* Test-only storage for engine globals named by vm_ram_syms[]. */",
    "#include <stdint.h>",
    "",
  ];
  for (const name of names.sort()) {
    if (seen.has(name)) continue;
    seen.add(name);
    lines.push(`uint8_t ${name}[4];`);
  }
  lines.push("");
  writeText(path.join(outDir, "data_stubs.c"), lines.join("\n"));
  return Array.from(seen).sort();
}

export function convert(
  exportDir: string,
  outDir: string,
  s2cHeader: string,
  s2cSource: string,
  states?: string,
): { scenes: number; scripts: number; stubs: number } {
  const exportData = path.join(exportDir, "src", "data");
  const exportInclude = path.join(exportDir, "include");
  if (!fs.statSync(exportData, { throwIfNoEntry: false })?.isDirectory()) {
    throw new ConvertError(`export data directory ${exportData} is missing`);
  }
  if (!fs.statSync(s2cHeader, { throwIfNoEntry: false })?.isFile()) {
    throw new ConvertError(`s2c header ${s2cHeader} is missing`);
  }
  if (!fs.statSync(s2cSource, { throwIfNoEntry: false })?.isFile()) {
    throw new ConvertError(`s2c source ${s2cSource} is missing`);
  }

  const scripts = readScripts(s2cHeader);
  const bankSymbols = readBankSymbols(s2cHeader);
  if (bankSymbols.length === 0) {
    throw new ConvertError(`no s2c bank arrays declared in ${s2cHeader}`);
  }

  const outData = path.join(outDir, "data");
  const outInclude = path.join(outDir, "include");
  fs.mkdirSync(outInclude, { recursive: true });

  let scenes = copyTransform(exportData, outData, scripts, false);
  copyTransform(path.join(exportInclude, "data"), path.join(outInclude, "data"), scripts, true);

  transformHugeHeaders(exportInclude, outInclude);
  scenes = scenes.sort();
  writeBuildInclude(
    outDir,
    path.basename(s2cHeader),
    scripts,
    bankSymbols,
    scenes,
  );
  const stubs = writeStubs(outDir, s2cSource);

  const initPath = path.join(exportData, "script_engine_init.s");
  const statesPath = path.join(exportData, "states_ptrs.s");
  if (fs.statSync(initPath, { throwIfNoEntry: false })?.isFile()) {
    const constants = parseConstants(exportInclude);
    const initData = parseEngineInit(initPath, constants);
    writeBootstrap(outDir, initData, path.basename(s2cHeader), new Set(scenes));
  }
  if (fs.statSync(statesPath, { throwIfNoEntry: false })?.isFile()) {
    const implemented = new Set((states || "topdown").split(","));
    writeStates(outDir, parseStates(statesPath), implemented);
  }
  return { scenes: scenes.length, scripts: scripts.size, stubs: stubs.length };
}

export type D2COptions = {
  exportDir: string;
  outDir: string;
  s2cHeader: string;
  s2cSource: string;
  states: string;
};

function usageError(message: string): number {
  process.stderr.write(`d2c: error: ${message}\n`);
  return 2;
}

export function parseArgs(argv: string[]): D2COptions | number {
  const options: D2COptions = {
    exportDir: "",
    outDir: "",
    s2cHeader: "",
    s2cSource: "",
    states: "topdown",
  };
  const setValue = (key: string, value: string): boolean => {
    if (key === "--export") options.exportDir = value;
    else if (key === "--out") options.outDir = value;
    else if (key === "--s2c-header") options.s2cHeader = value;
    else if (key === "--s2c-source") options.s2cSource = value;
    else if (key === "--states") options.states = value;
    else return false;
    return true;
  };
  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];
    if (arg.startsWith("--") && arg.includes("=")) {
      const equal = arg.indexOf("=");
      if (setValue(arg.slice(0, equal), arg.slice(equal + 1))) {
        i += 1;
        continue;
      }
    }
    if (
      ["--export", "--out", "--s2c-header", "--s2c-source", "--states"].includes(
        arg,
      )
    ) {
      if (i + 1 >= argv.length) return usageError(`${arg} needs a value`);
      setValue(arg, argv[i + 1]);
      i += 2;
      continue;
    }
    if (arg === "--help" || arg === "-h") {
      process.stdout.write(
        "usage: d2c [--export DIR] [--out DIR] [--s2c-header FILE] " +
          "[--s2c-source FILE] [--states LIST]\n",
      );
      return 0;
    }
    return usageError(`unrecognized argument ${JSON.stringify(arg)}`);
  }
  if (!options.exportDir) return usageError("--export is required");
  if (!options.outDir) return usageError("--out is required");
  if (!options.s2cHeader) return usageError("--s2c-header is required");
  if (!options.s2cSource) return usageError("--s2c-source is required");
  return options;
}

export function main(argv?: string[]): number {
  const args = argv ?? process.argv.slice(2);
  const parsed = parseArgs(args);
  if (typeof parsed === "number") return parsed;

  try {
    const result = convert(
      parsed.exportDir,
      parsed.outDir,
      parsed.s2cHeader,
      parsed.s2cSource,
      parsed.states,
    );
    process.stdout.write(
      `d2c: ${result.scenes} scenes, ${result.scripts} scripts, ` +
        `${result.stubs} RAM stubs\n`,
    );
  } catch (error) {
    if (error instanceof ConvertError) {
      process.stderr.write(`d2c: ${error.message}\n`);
      return 1;
    }
    throw error;
  }
  return 0;
}
