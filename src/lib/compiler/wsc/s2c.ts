/**
 * TypeScript port of wsc/tools/s2c.py.
 *
 * The Python tool is the oracle: this file must produce byte-identical C,
 * headers and census files. It is self-contained on purpose so the wsc
 * Makefiles can run it through wsc/tools/s2c-ts.js without a build step
 * (Node 24 strips types) and without touching the rest of the compiler.
 *
 * Only erasable TypeScript syntax is used.
 */

import * as fs from "node:fs";
import * as path from "node:path";

export const MAX_BANK = 32767;

export class ConversionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConversionError";
  }
}

export class ExprError extends ConversionError {
  constructor(message: string) {
    super(message);
    this.name = "ExprError";
  }
}

// ---------------------------------------------------------------------------
// Expressions

type TokenKind = "sym" | "num" | "char" | "op";

type Token = { kind: TokenKind; text: string };

const TOKEN_RE =
  /\s*(?:(\d+\$|[A-Za-z_.$][A-Za-z0-9_.$]*)|(0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+)|('(?:\\.|[^'\\])')|(<<|>>|[-+*/%&|^~()]))/y;

function big(value: number): bigint {
  return BigInt(value);
}

function bitAnd(a: number, b: number): number {
  return Number(big(a) & big(b));
}

function bitOr(a: number, b: number): number {
  return Number(big(a) | big(b));
}

function bitXor(a: number, b: number): number {
  return Number(big(a) ^ big(b));
}

function bitNot(a: number): number {
  return Number(~big(a));
}

function shiftLeft(a: number, b: number): number {
  if (b < 0) throw new ExprError("negative shift count");
  return Number(big(a) << big(b));
}

function shiftRight(a: number, b: number): number {
  if (b < 0) throw new ExprError("negative shift count");
  return Number(big(a) >> big(b));
}

/** Python's floored integer remainder. */
function pyMod(a: number, b: number): number {
  let remainder = big(a) % big(b);
  if (remainder !== BigInt(0) && remainder < BigInt(0) !== b < 0) {
    remainder += big(b);
  }
  return Number(remainder);
}

const escapeRegExp = (text: string): string =>
  text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const normalizeSymbols = (text: string): string =>
  text.replace(/(?<=[A-Za-z0-9_.$])'(?=[A-Za-z0-9_.$])/g, "");

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < text.length) {
    if (/\s/.test(text[i])) {
      i += 1;
      continue;
    }
    TOKEN_RE.lastIndex = i;
    const match = TOKEN_RE.exec(text);
    if (!match || match.index !== i || match[0].length === 0) {
      throw new ExprError(
        `cannot tokenize expression: ${JSON.stringify(text)}`,
      );
    }
    const kind = (
      match[1] ? "sym" : match[2] ? "num" : match[3] ? "char" : "op"
    ) as TokenKind;
    const value = match[1] ?? match[2] ?? match[3] ?? match[4];
    tokens.push({ kind, text: value });
    i = TOKEN_RE.lastIndex;
  }
  return tokens;
}

export type Lookup = (name: string) => number | string;

export class ExprParser {
  text: string;
  lookup: Lookup;
  tokens: Token[];
  pos: number;

  constructor(text: string, lookup: Lookup) {
    this.text = normalizeSymbols(text.trim());
    this.lookup = lookup;
    this.tokens = tokenize(this.text);
    this.pos = 0;
  }

  peek(): Token | undefined {
    return this.tokens[this.pos];
  }

  isOp(value: string): boolean {
    const tok = this.peek();
    return tok !== undefined && tok.kind === "op" && tok.text === value;
  }

  take(value?: string): Token {
    const tok = this.peek();
    if (!tok) {
      throw new ExprError(
        `unexpected end of expression: ${JSON.stringify(this.text)}`,
      );
    }
    if (value !== undefined && tok.text !== value) {
      throw new ExprError(
        `expected ${JSON.stringify(value)} in ${JSON.stringify(this.text)}`,
      );
    }
    this.pos += 1;
    return tok;
  }

  parse(): number {
    const value = this.parseOr();
    if (this.pos !== this.tokens.length) {
      throw new ExprError(
        `trailing tokens in expression: ${JSON.stringify(this.text)}`,
      );
    }
    return value;
  }

  parseOr(): number {
    let value = this.parseXor();
    while (this.isOp("|")) {
      this.take();
      value = bitOr(value, this.parseXor());
    }
    return value;
  }

  parseXor(): number {
    let value = this.parseAnd();
    while (this.isOp("^")) {
      this.take();
      value = bitXor(value, this.parseAnd());
    }
    return value;
  }

  parseAnd(): number {
    let value = this.parseShift();
    while (this.isOp("&")) {
      this.take();
      value = bitAnd(value, this.parseShift());
    }
    return value;
  }

  parseShift(): number {
    let value = this.parseAdd();
    while (this.isOp("<<") || this.isOp(">>")) {
      const op = this.take().text;
      const rhs = this.parseAdd();
      value = op === "<<" ? shiftLeft(value, rhs) : shiftRight(value, rhs);
    }
    return value;
  }

  parseAdd(): number {
    let value = this.parseMul();
    while (this.isOp("+") || this.isOp("-")) {
      const op = this.take().text;
      const rhs = this.parseMul();
      value = op === "+" ? value + rhs : value - rhs;
    }
    return value;
  }

  parseMul(): number {
    let value = this.parseUnary();
    while (this.isOp("*") || this.isOp("/") || this.isOp("%")) {
      const op = this.take().text;
      const rhs = this.parseUnary();
      if (op === "*") {
        value *= rhs;
      } else if (op === "/") {
        if (rhs === 0) {
          throw new ExprError(
            `division by zero in ${JSON.stringify(this.text)}`,
          );
        }
        value = Math.trunc(value / rhs);
      } else {
        if (rhs === 0) {
          throw new ExprError(`modulo by zero in ${JSON.stringify(this.text)}`);
        }
        value = pyMod(value, rhs);
      }
    }
    return value;
  }

  parseUnary(): number {
    if (this.isOp("-")) {
      this.take();
      return -this.parseUnary();
    }
    if (this.isOp("+")) {
      this.take();
      return this.parseUnary();
    }
    if (this.isOp("~")) {
      this.take();
      return bitNot(this.parseUnary());
    }
    return this.parsePrimary();
  }

  parsePrimary(): number {
    const tok = this.take();
    if (tok.kind === "num") {
      if (tok.text.toLowerCase().startsWith("0x")) {
        return parseInt(tok.text.slice(2), 16);
      }
      if (tok.text.toLowerCase().startsWith("0b")) {
        return parseInt(tok.text.slice(2), 2);
      }
      return parseInt(tok.text, 10);
    }
    if (tok.kind === "char") {
      const body = tok.text.slice(1, -1);
      if (body.startsWith("\\")) {
        const escapes: Record<string, number> = {
          n: 10,
          r: 13,
          t: 9,
          "0": 0,
          "\\": 92,
          "'": 39,
          '"': 34,
        };
        if (/^\d$/.test(body.slice(1))) {
          return parseInt(body.slice(1), 8);
        }
        if (Object.prototype.hasOwnProperty.call(escapes, body[1])) {
          return escapes[body[1]];
        }
        return body.charCodeAt(1);
      }
      if (body.length !== 1) {
        throw new ExprError(
          `bad character literal ${JSON.stringify(tok.text)}`,
        );
      }
      return body.charCodeAt(0);
    }
    if (tok.kind === "sym") {
      const value = this.lookup(tok.text);
      if (typeof value !== "number") {
        throw new ExprError(
          `symbol ${JSON.stringify(tok.text)} is not numeric yet`,
        );
      }
      return value;
    }
    if (tok.kind === "op" && tok.text === "(") {
      const value = this.parseOr();
      this.take(")");
      return value;
    }
    throw new ExprError(
      `unexpected token ${JSON.stringify(tok.text)} in ${JSON.stringify(
        this.text,
      )}`,
    );
  }
}

export function evalExpression(text: string, lookup: Lookup): number {
  return new ExprParser(text, lookup).parse();
}

export function expressionSymbols(text: string): string[] {
  return tokenize(normalizeSymbols(text))
    .filter((tok) => tok.kind === "sym")
    .map((tok) => tok.text);
}

const INDEX_EXPR_RE = /^(_[A-Za-z0-9_]+)([+-](?:0[xX][0-9A-Fa-f]+|\d+))?$/;

/** Whitespace-free expression with redundant enclosing parentheses removed. */
export function canonicalExpr(text: string): string {
  let result = text.replace(/\s+/g, "");
  while (result.startsWith("(") && result.endsWith(")")) {
    let depth = 0;
    let enclosed = true;
    for (let index = 0; index < result.length; index += 1) {
      const ch = result[index];
      if (ch === "(") depth += 1;
      else if (ch === ")") {
        depth -= 1;
        if (depth === 0) {
          if (index !== result.length - 1) enclosed = false;
          break;
        }
      }
    }
    if (!enclosed) break;
    result = result.slice(1, -1);
  }
  return result;
}

/** Python's int(text, 0). */
export function parseAutoInt(text: string): number {
  const trimmed = text.trim();
  const match = /^([+-]?)(0[xX][0-9A-Fa-f]+|0[bB][01]+|0[oO][0-7]+|\d+)$/.exec(
    trimmed,
  );
  if (!match) throw new Error(`invalid integer ${JSON.stringify(text)}`);
  const sign = match[1] === "-" ? -1 : 1;
  const body = match[2];
  let value: number;
  if (/^0[xX]/.test(body)) value = parseInt(body.slice(2), 16);
  else if (/^0[bB]/.test(body)) value = parseInt(body.slice(2), 2);
  else if (/^0[oO]/.test(body)) value = parseInt(body.slice(2), 8);
  else if (/^0\d+$/.test(body)) value = parseInt(body.slice(1), 8);
  else value = parseInt(body, 10);
  return sign * value;
}

export type IndexExpr = { key: string; symbol: string; offset: number };

/** Split a RAM/data expression into (canonical key, symbol, byte offset). */
export function parseIndexExpr(text: string): IndexExpr {
  const key = canonicalExpr(text);
  const match = INDEX_EXPR_RE.exec(key);
  if (!match) {
    throw new ConversionError(
      `${text.trim()} cannot be expressed as a table index; ` +
        "expected SYM or SYM+offset",
    );
  }
  const symbol = match[1];
  const offsetText = match[2];
  const offset = offsetText ? parseAutoInt(offsetText) : 0;
  return { key, symbol, offset };
}

// ---------------------------------------------------------------------------
// Source cleanup and sdas directives

export function stripComment(line: string): string {
  const out: string[] = [];
  let quote: string | null = null;
  let i = 0;
  while (i < line.length) {
    const ch = line[i];
    if (quote) {
      out.push(ch);
      if (ch === "\\" && i + 1 < line.length) {
        out.push(line[i + 1]);
        i += 2;
        continue;
      }
      if (ch === quote) quote = null;
      i += 1;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      out.push(ch);
      i += 1;
      continue;
    }
    if (ch === ";") break;
    out.push(ch);
    i += 1;
  }
  return out.join("").replace(/\s+$/, "");
}

export function splitItems(text: string): string[] {
  const items: string[] = [];
  let start = 0;
  let depth = 0;
  let quote: string | null = null;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (quote) {
      if (ch === "\\") {
        i += 2;
        continue;
      }
      if (ch === quote) quote = null;
      i += 1;
      continue;
    }
    if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "(" || ch === "[" || ch === "{") depth += 1;
    else if (ch === ")" || ch === "]" || ch === "}") depth -= 1;
    else if (ch === "," && depth === 0) {
      items.push(text.slice(start, i).trim());
      start = i + 1;
    }
    i += 1;
  }
  const tail = text.slice(start).trim();
  if (tail || items.length) items.push(tail);
  return items;
}

export function splitMacroArgs(text: string): string[] {
  if (!text.trim()) return [];
  let args = splitItems(text);
  if (args.length === 1) {
    // sdas also accepts whitespace-separated macro arguments.
    const words: string[] = [];
    let start = 0;
    let depth = 0;
    let quote: string | null = null;
    let i = 0;
    while (i < text.length) {
      const ch = text[i];
      if (quote) {
        if (ch === "\\") {
          i += 2;
          continue;
        }
        if (ch === quote) quote = null;
        i += 1;
        continue;
      }
      if (ch === '"' || ch === "'") quote = ch;
      else if (ch === "(" || ch === "[" || ch === "{") depth += 1;
      else if (ch === ")" || ch === "]" || ch === "}") depth -= 1;
      else if (/\s/.test(ch) && depth === 0) {
        words.push(text.slice(start, i).trim());
        start = i + 1;
      }
      i += 1;
    }
    words.push(text.slice(start).trim());
    const nonEmpty = words.filter((word) => word.length > 0);
    if (nonEmpty.length > 1) args = nonEmpty;
  }
  return args;
}

const STRING_ESCAPE: Record<string, number> = {
  a: 7,
  b: 8,
  f: 12,
  n: 10,
  r: 13,
  t: 9,
  v: 11,
  "\\": 92,
  "'": 39,
  '"': 34,
  "0": 0,
};

export function parseString(text: string): number[] {
  const trimmed = text.trim();
  if (
    trimmed.length < 2 ||
    trimmed[0] !== '"' ||
    trimmed[trimmed.length - 1] !== '"'
  ) {
    throw new ConversionError(`bad string literal: ${JSON.stringify(trimmed)}`);
  }
  const body = trimmed.slice(1, -1);
  const out: number[] = [];
  let i = 0;
  while (i < body.length) {
    const ch = body[i];
    if (ch !== "\\") {
      out.push(body.charCodeAt(i) & 0xff);
      i += 1;
      continue;
    }
    i += 1;
    if (i >= body.length) {
      throw new ConversionError(
        `trailing backslash in string: ${JSON.stringify(trimmed)}`,
      );
    }
    const escaped = body[i];
    if (escaped === "x") {
      let j = i + 1;
      while (j < body.length && /[0-9a-fA-F]/.test(body[j])) j += 1;
      if (j === i + 1) {
        throw new ConversionError(
          `bad \\x escape in ${JSON.stringify(trimmed)}`,
        );
      }
      out.push(parseInt(body.slice(i + 1, j), 16) & 0xff);
      i = j;
    } else if (/[0-7]/.test(escaped)) {
      let j = i;
      while (j < body.length && j < i + 3 && /[0-7]/.test(body[j])) j += 1;
      out.push(parseInt(body.slice(i, j), 8) & 0xff);
      i = j;
    } else if (Object.prototype.hasOwnProperty.call(STRING_ESCAPE, escaped)) {
      out.push(STRING_ESCAPE[escaped]);
      i += 1;
    } else {
      out.push(body.charCodeAt(i) & 0xff);
      i += 1;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Model

export type Macro = { name: string; params: string[]; body: string[] };

export type Emission = {
  expr: string;
  width: number;
  byteIndex: number;
  mode: string;
  literal: number[] | null;
};

export type PointerRef = {
  expr: string;
  symbols: string[];
  kind: string;
  width: number;
  byteIndex: number;
  mode: string;
};

export type Script = {
  path: string;
  name: string;
  source: string;
  labels: Map<string, number>;
  exported: string[];
  consts: Map<string, number | string>;
  emissions: Emission[];
  size: number;
  bank: number;
  offset: number;
  data: number[];
  refs: Map<number, PointerRef>;
};

export type External = { kind: string; value: number; original: string };

type TableEntry = { symbol: string; offset: number };

export function newScript(
  filePath: string,
  name: string,
  source: string,
): Script {
  return {
    path: filePath,
    name,
    source,
    labels: new Map(),
    exported: [],
    consts: new Map(),
    emissions: [],
    size: 0,
    bank: -1,
    offset: -1,
    data: [],
    refs: new Map(),
  };
}

// ---------------------------------------------------------------------------
// Definitions

export class Definitions {
  includeDir: string;
  constants: Map<string, number | string>;
  macros: Map<string, Macro>;

  constructor(includeDir: string) {
    this.includeDir = includeDir;
    this.constants = new Map();
    this.macros = new Map();
    this.load();
  }

  files(): string[] {
    const preferred = [
      path.join(this.includeDir, "vm.i"),
      path.join(this.includeDir, "macro.i"),
    ].filter((p) => fs.existsSync(p) && fs.statSync(p).isFile());
    const all = listFilesRecursive(this.includeDir)
      .filter((p) => p.endsWith(".i"))
      .sort();
    const files = preferred.slice();
    for (const file of all) {
      if (!files.includes(file)) files.push(file);
    }
    return files;
  }

  load(): void {
    for (const file of this.files()) this.parseFile(file);
  }

  parseFile(file: string): void {
    const lines = fs.readFileSync(file, "utf8").split(/\r\n|\r|\n/);
    let i = 0;
    while (i < lines.length) {
      const raw = stripComment(lines[i]).trim();
      if (!raw) {
        i += 1;
        continue;
      }
      let match = /^\.macro\s+([.]?[A-Za-z_]\w*)\s*(.*)$/i.exec(raw);
      if (match) {
        const name = match[1];
        const params = match[2]
          .trim()
          .split(/[\s,]+/)
          .filter(Boolean);
        const body: string[] = [];
        i += 1;
        while (i < lines.length) {
          const bodyLine = stripComment(lines[i]).trim();
          if (/^\.endm\b/i.test(bodyLine)) break;
          body.push(lines[i]);
          i += 1;
        }
        if (i >= lines.length) {
          throw new ConversionError(`unterminated .macro ${name} in ${file}`);
        }
        this.macros.set(name, { name, params, body });
        i += 1;
        continue;
      }
      match = /^([.]?[A-Za-z_]\w*)\s*=\s*(.+)$/.exec(raw);
      if (match) {
        const name = match[1];
        const expr = match[2];
        try {
          this.constants.set(
            name,
            evalExpression(expr, (sym) => {
              if (!this.constants.has(sym)) {
                throw new ExprError(`unknown constant ${JSON.stringify(sym)}`);
              }
              return this.constants.get(sym) as number;
            }),
          );
        } catch (error) {
          if (!(error instanceof ExprError)) throw error;
          // Leave forward/unsupported definitions for the source pass.
          this.constants.set(name, expr);
        }
        i += 1;
        continue;
      }
      i += 1;
    }
  }
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
  return out;
}

// ---------------------------------------------------------------------------
// Script parser

export class ScriptParser {
  defs: Definitions;
  script: Script;
  env: Map<string, number | string>;

  constructor(defs: Definitions, script: Script) {
    this.defs = defs;
    this.script = script;
    this.env = new Map(defs.constants);
    for (const [key, value] of script.consts) this.env.set(key, value);
  }

  lookupNow(name: string): number {
    if (this.env.has(name)) {
      const value = this.env.get(name) as number | string;
      if (typeof value === "number") return value;
      try {
        return evalExpression(value, (sym) => this.lookupNow(sym));
      } catch (error) {
        if (error instanceof ExprError) {
          throw new ExprError(
            `constant ${JSON.stringify(name)} is not numeric yet`,
          );
        }
        throw error;
      }
    }
    throw new ExprError(`unknown constant ${JSON.stringify(name)}`);
  }

  evalNow(text: string): number {
    return evalExpression(text, (sym) => this.lookupNow(sym));
  }

  expandWrappers(text: string): string {
    // ^!ARG! and ^/(expr)/ are sdas macro substitution operators.
    let result = text.replace(/\^!(.*?)!/g, (_match, name: string) => {
      if (!this.env.has(name)) {
        throw new ConversionError(
          `unknown macro argument ${JSON.stringify(name)}`,
        );
      }
      return String(this.env.get(name));
    });
    result = result.replace(/\^\/(.*?)\//g, (_match, inner: string) => {
      try {
        return String(this.evalNow(inner));
      } catch (error) {
        if (error instanceof ExprError) {
          // Keep unresolved expressions for the deferred pass.
          return `(${inner})`;
        }
        throw error;
      }
    });
    return result;
  }

  substituteMacroLine(line: string, params: string[], args: string[]): string {
    const values = new Map<string, string>();
    params.forEach((param, index) => values.set(param, args[index]));
    let result = line.replace(/\^!(.*?)!/g, (_match, name: string) => {
      if (!values.has(name) || values.get(name) === undefined) {
        throw new ConversionError(
          `unknown macro argument ${JSON.stringify(name)}`,
        );
      }
      return values.get(name) as string;
    });
    if (params.length) {
      const alternation = params
        .slice()
        .sort((a, b) => b.length - a.length)
        .map(escapeRegExp)
        .join("|");
      const pattern = new RegExp(
        `(?<![A-Za-z0-9_.$])(${alternation})(?![A-Za-z0-9_.$])`,
        "g",
      );
      result = result.replace(
        pattern,
        (name: string) => values.get(name) as string,
      );
    }
    return result;
  }

  emitLiteral(data: number[]): void {
    this.script.emissions.push({
      expr: "",
      width: 1,
      byteIndex: 0,
      mode: "byte",
      literal: data.slice(),
    });
    this.script.size += data.length;
  }

  emitItems(directive: string, rest: string): void {
    const items = splitItems(rest);
    if (directive === ".db") {
      for (const item of items) {
        if (!item) continue;
        let mode = "byte";
        let expr = item.trim();
        if (expr.startsWith("#>")) {
          mode = "high";
          expr = expr.slice(2).trim();
        } else if (expr.startsWith("#<")) {
          mode = "low";
          expr = expr.slice(2).trim();
        } else if (expr.startsWith("#")) {
          expr = expr.slice(1).trim();
        }
        if (expr.startsWith('"')) {
          this.emitLiteral(parseString(expr));
        } else {
          this.script.emissions.push({
            expr,
            width: 1,
            byteIndex: 0,
            mode,
            literal: null,
          });
          this.script.size += 1;
        }
      }
    } else if (directive === ".dw") {
      for (const item of items) {
        if (!item) continue;
        let expr = item.trim();
        if (expr.startsWith("#")) expr = expr.slice(1).trim();
        this.script.emissions.push({
          expr,
          width: 2,
          byteIndex: 0,
          mode: "word",
          literal: null,
        });
        this.script.emissions.push({
          expr,
          width: 2,
          byteIndex: 1,
          mode: "word",
          literal: null,
        });
        this.script.size += 2;
      }
    } else if (directive === ".asciz") {
      const data = parseString(rest);
      this.emitLiteral(data.concat([0]));
    } else {
      throw new ConversionError(`unsupported directive ${directive}`);
    }
  }

  process(lines: string[], depth = 0): void {
    if (depth > 30) throw new ConversionError("macro nesting too deep");
    const condStack: boolean[] = [];
    const active = (): boolean => condStack.every(Boolean);

    for (const raw of lines) {
      const line = stripComment(raw).trim();
      if (!line) continue;
      const lowered = line.toLowerCase();
      if (lowered.startsWith(".if ")) {
        if (active()) {
          condStack.push(
            Boolean(this.evalNow(this.expandWrappers(line.slice(4)))),
          );
        } else {
          condStack.push(false);
        }
        continue;
      }
      if (lowered === ".else") {
        if (!condStack.length) {
          throw new ConversionError(".else without .if");
        }
        condStack[condStack.length - 1] = !condStack[condStack.length - 1];
        continue;
      }
      if (lowered === ".endif") {
        if (!condStack.length) {
          throw new ConversionError(".endif without .if");
        }
        condStack.pop();
        continue;
      }
      if (!active()) continue;

      if (
        /^\.(module|include|area|globl|local|list|nlist|title|page)\b/i.test(
          line,
        )
      ) {
        continue;
      }
      if (
        line.startsWith(".db ") ||
        line.startsWith(".dw ") ||
        line.startsWith(".asciz ")
      ) {
        const split = /^(\S+)\s+(.*)$/.exec(line);
        if (!split) continue;
        this.emitItems(split[1], this.expandWrappers(split[2]));
        continue;
      }

      let match = /^([.]?[A-Za-z_]\w*)\s*=\s*(.+)$/.exec(line);
      if (match) {
        const name = match[1];
        const value = this.evalNow(this.expandWrappers(match[2]));
        this.env.set(name, value);
        this.script.consts.set(name, value);
        continue;
      }

      match = /^([A-Za-z_.$][\w.$]*|\d+\$):{1,2}\s*(.*)$/.exec(line);
      if (match) {
        const label = match[1];
        const rest = match[2];
        if (this.script.labels.has(label)) {
          throw new ConversionError(
            `duplicate label ${label} in ${this.script.path}`,
          );
        }
        this.script.labels.set(label, this.script.size);
        const withoutComment = line.split(";")[0];
        if (withoutComment.includes("::")) {
          this.script.exported.push(label);
        }
        if (rest) this.process([rest], depth + 1);
        continue;
      }

      match = /^([.]?[A-Za-z_]\w*)\b(.*)$/.exec(line);
      if (!match) {
        throw new ConversionError(
          `unsupported line in ${this.script.path}: ${JSON.stringify(raw)}`,
        );
      }
      const name = match[1];
      const rest = match[2];
      const macro = this.defs.macros.get(name);
      if (macro === undefined) {
        throw new ConversionError(
          `unknown directive/macro ${JSON.stringify(name)} in ${this.script.path}`,
        );
      }
      const args = splitMacroArgs(this.expandWrappers(rest.trim()));
      if (args.length !== macro.params.length) {
        throw new ConversionError(
          `macro ${name} expects ${macro.params.length} args, got ` +
            `${args.length} in ${this.script.path}`,
        );
      }
      const body = macro.body.map((bodyLine) =>
        this.substituteMacroLine(bodyLine, macro.params, args),
      );
      const old = this.env;
      this.env = new Map(old);
      macro.params.forEach((param, index) => this.env.set(param, args[index]));
      try {
        this.process(body, depth + 1);
      } finally {
        this.env = old;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Script preparation

export function prepareSource(filePath: string): {
  text: string | null;
  special: boolean;
} {
  const text = fs.readFileSync(filePath, "utf8");
  if (/^\s*\.module\b/m.test(text)) {
    return { text, special: false };
  }
  const entry = /^_script_engine_init::/m.exec(text);
  if (!entry) {
    return { text: null, special: false };
  }
  const index = entry.index;
  const before = text.slice(0, index).split(/\r\n|\r|\n/);
  const includes = before.filter((line) => /^\s*\.include\b/.test(line));
  let area: string | null = null;
  for (const line of before) {
    if (/^\s*\.area\b/.test(line)) area = line;
  }
  const code = text.slice(index).split(/\r\n|\r|\n/);
  const prepared = includes
    .concat(area === null ? [] : [area])
    .concat(code)
    .join("\n");
  return { text: prepared + "\n", special: true };
}

export function scriptName(text: string, filePath: string): string {
  const moduleMatch = /^\s*\.module\s+(\S+)/m.exec(text);
  if (moduleMatch) return moduleMatch[1];
  const labelRe = /^([A-Za-z_]\w*)::/gm;
  let match: RegExpExecArray | null;
  while ((match = labelRe.exec(text)) !== null) {
    if (match[1].startsWith("_")) return match[1].slice(1);
  }
  return path.basename(filePath, path.extname(filePath));
}

// ---------------------------------------------------------------------------
// Conversion

export class Converter {
  defs: Definitions;
  files: string[];
  forcedBanks: Map<string, number>;
  scripts: Script[];
  skipped: Array<{ path: string; reason: string }>;
  externals: Map<string, External>;
  ramSymbols: string[];
  farBankSymbols: string[];
  farAddrSymbols: string[];
  nativeAddrSymbols: string[];
  nativeBankSymbols: string[];
  otherSymbols: string[];
  symbolKinds: Map<string, [string, string]>;
  scriptLabels: Map<string, Script>;
  scriptNames: Set<string>;
  farBases: Set<string>;
  nativeBases: Set<string>;
  ramExprIndex: Map<string, number>;
  ramSymbolIndex: Map<string, number>;
  farExprIndex: Map<string, number>;
  farSymbolIndex: Map<string, number>;
  ramTable: string[];
  farTable: string[];
  ramTableEntries: Map<string, TableEntry>;
  farTableEntries: Map<string, TableEntry>;
  nativeAddrOrder: string[];
  banks: Script[][];
  pointerBytes: number;

  constructor(
    defs: Definitions,
    files: string[],
    forcedBanks?: Map<string, number>,
  ) {
    this.defs = defs;
    this.files = files.slice().sort();
    this.forcedBanks = forcedBanks ?? new Map();
    this.scripts = [];
    this.skipped = [];
    this.externals = new Map();
    this.ramSymbols = [];
    this.farBankSymbols = [];
    this.farAddrSymbols = [];
    this.nativeAddrSymbols = [];
    this.nativeBankSymbols = [];
    this.otherSymbols = [];
    this.symbolKinds = new Map();
    this.scriptLabels = new Map();
    this.scriptNames = new Set();
    this.farBases = new Set();
    this.nativeBases = new Set();
    this.ramExprIndex = new Map();
    this.ramSymbolIndex = new Map();
    this.farExprIndex = new Map();
    this.farSymbolIndex = new Map();
    this.ramTable = [];
    this.farTable = [];
    this.ramTableEntries = new Map();
    this.farTableEntries = new Map();
    this.nativeAddrOrder = [];
    this.banks = [];
    this.pointerBytes = 0;
  }

  parse(): void {
    for (const filePath of this.files) {
      const prepared = prepareSource(filePath);
      if (prepared.text === null) {
        this.skipped.push({
          path: filePath,
          reason: "no .module and no _script_engine_init VM entry",
        });
        continue;
      }
      const text = prepared.text;
      const name = scriptName(text, filePath);
      const script = newScript(filePath, name, text);
      const parser = new ScriptParser(this.defs, script);
      parser.process(text.split(/\r\n|\r|\n/));
      if (prepared.special) {
        this.skipped.push({
          path: filePath,
          reason: "header data before _script_engine_init (VM code converted)",
        });
      } else if (path.basename(filePath) === "states_ptrs.s") {
        this.skipped.push({
          path: filePath,
          reason: "far-pointer table, not a VM script",
        });
      }
      this.scripts.push(script);
    }
  }

  classifySymbols(): void {
    const allText = this.scripts.map((script) => script.source).join("\n");
    const farBases = new Set(
      Array.from(allText.matchAll(/___bank_([A-Za-z0-9_]+)/g)).map(
        (match) => match[1],
      ),
    );
    const nativeBases = new Set(
      Array.from(allText.matchAll(/\bb_([A-Za-z0-9_]+)/g)).map(
        (match) => match[1],
      ),
    );
    const scriptNames = new Set(this.scripts.map((script) => script.name));
    this.scriptLabels = new Map();
    for (const script of this.scripts) {
      for (const label of script.exported) {
        this.scriptLabels.set(label, script);
      }
    }
    this.scriptNames = scriptNames;
    this.farBases = new Set(
      Array.from(farBases).filter((base) => !scriptNames.has(base)),
    );
    this.nativeBases = nativeBases;

    const fileConsts = new Set<string>();
    for (const script of this.scripts) {
      for (const key of script.consts.keys()) fileConsts.add(key);
    }
    const symbols = new Set<string>();
    for (const script of this.scripts) {
      for (const em of script.emissions) {
        if (!em.expr) continue;
        try {
          for (const symbol of expressionSymbols(em.expr)) symbols.add(symbol);
        } catch (error) {
          if (error instanceof ExprError) {
            throw new ConversionError(error.message);
          }
          throw error;
        }
      }
    }

    this.symbolKinds = new Map();
    const ram: string[] = [];
    const farBank: string[] = [];
    const farAddr: string[] = [];
    const nativeAddr: string[] = [];
    const other: string[] = [];
    for (const sym of Array.from(symbols).sort()) {
      if (this.defs.constants.has(sym) || this.scriptLabels.has(sym)) {
        continue;
      }
      if (sym.startsWith(".") && fileConsts.has(sym)) continue;
      if (sym.startsWith("___bank_")) {
        const base = sym.slice("___bank_".length);
        if (scriptNames.has(base)) {
          this.symbolKinds.set(sym, ["script_bank", base]);
        } else {
          this.symbolKinds.set(sym, ["far_bank", base]);
          farBank.push(sym);
        }
      } else if (sym.startsWith("b_")) {
        const base = sym.slice(2);
        if (nativeBases.has(base)) {
          this.symbolKinds.set(sym, ["native_bank", base]);
        } else {
          this.symbolKinds.set(sym, ["other", sym]);
          other.push(sym);
        }
      } else if (sym.startsWith("_")) {
        const base = sym.slice(1);
        if (this.scriptLabels.has(sym)) {
          this.symbolKinds.set(sym, ["script_label", base]);
        } else if (this.farBases.has(base)) {
          this.symbolKinds.set(sym, ["far_addr", base]);
          farAddr.push(sym);
        } else if (this.nativeBases.has(base)) {
          this.symbolKinds.set(sym, ["native_addr", base]);
          nativeAddr.push(sym);
        } else {
          this.symbolKinds.set(sym, ["ram", base]);
          ram.push(sym);
        }
      } else if (/^\d+\$$/.test(sym)) {
        this.symbolKinds.set(sym, ["local_label", sym]);
      } else {
        this.symbolKinds.set(sym, ["other", sym]);
        other.push(sym);
      }
    }

    this.ramSymbols = ram;
    this.farBankSymbols = farBank;
    this.farAddrSymbols = farAddr;
    this.nativeAddrSymbols = nativeAddr;
    this.nativeBankSymbols = Array.from(this.symbolKinds.entries())
      .filter(([, kind]) => kind[0] === "native_bank")
      .map(([sym]) => sym);
    this.otherSymbols = other;
  }

  buildTables(): void {
    /**
     * Assign indexes for RAM pointers and far-data pointers.
     *
     * Every expression that reaches a RAM address becomes one index table
     * entry. Offset expressions (`_joypads + 1`) get their own entry; the
     * base object is always present too.
     */
    const ramEntries = new Map<string, TableEntry>();
    const farEntries = new Map<string, TableEntry>();

    const add = (entries: Map<string, TableEntry>, expr: string): void => {
      const parsed = parseIndexExpr(expr);
      if (!entries.has(parsed.key)) {
        entries.set(parsed.key, {
          symbol: parsed.symbol,
          offset: parsed.offset,
        });
      }
      if (parsed.offset) {
        if (!entries.has(parsed.symbol)) {
          entries.set(parsed.symbol, { symbol: parsed.symbol, offset: 0 });
        }
      }
    };

    for (const script of this.scripts) {
      for (const em of script.emissions) {
        if (!em.expr) continue;
        let symbols: string[];
        try {
          symbols = expressionSymbols(em.expr);
        } catch (error) {
          if (error instanceof ExprError) {
            throw new ConversionError(error.message);
          }
          throw error;
        }
        const kind = this.pointerKind(symbols, script);
        if (kind === "ram") {
          add(ramEntries, em.expr);
        } else if (kind === "far") {
          if (
            symbols.some((sym) => this.symbolKinds.get(sym)?.[0] === "far_bank")
          ) {
            // ___bank_<object> is always the constant zero.
            continue;
          }
          add(farEntries, em.expr);
        }
      }
    }

    for (const sym of this.ramSymbols) {
      if (!ramEntries.has(sym)) {
        ramEntries.set(sym, { symbol: sym, offset: 0 });
      }
    }
    for (const sym of this.farAddrSymbols) {
      if (!farEntries.has(sym)) {
        farEntries.set(sym, { symbol: sym, offset: 0 });
      }
    }

    const orderFor = (entries: Map<string, TableEntry>) => {
      return (a: string, b: string): number => {
        const ea = entries.get(a) as TableEntry;
        const eb = entries.get(b) as TableEntry;
        const al = ea.symbol.toLowerCase();
        const bl = eb.symbol.toLowerCase();
        if (al !== bl) return al < bl ? -1 : 1;
        return ea.offset - eb.offset;
      };
    };

    this.ramTable = Array.from(ramEntries.keys()).sort(orderFor(ramEntries));
    this.farTable = Array.from(farEntries.keys()).sort(orderFor(farEntries));
    this.ramTable.forEach((key, index) => this.ramExprIndex.set(key, index));
    this.farTable.forEach((key, index) => this.farExprIndex.set(key, index));
    for (const key of this.ramTable) {
      const entry = ramEntries.get(key) as TableEntry;
      if (entry.offset === 0) {
        this.ramSymbolIndex.set(
          entry.symbol.slice(1),
          this.ramExprIndex.get(key) as number,
        );
      }
    }
    for (const key of this.farTable) {
      const entry = farEntries.get(key) as TableEntry;
      if (entry.offset === 0) {
        this.farSymbolIndex.set(
          entry.symbol.slice(1),
          this.farExprIndex.get(key) as number,
        );
      }
    }

    this.ramTableEntries = ramEntries;
    this.farTableEntries = farEntries;

    const externals = new Map<string, External>();
    for (const sym of this.ramSymbols) {
      const base = sym.slice(1);
      externals.set(sym, {
        kind: "ram",
        value: this.ramSymbolIndex.get(base) as number,
        original: sym,
      });
    }
    for (const sym of this.farBankSymbols) {
      externals.set(sym, { kind: "far_bank", value: 0, original: sym });
    }
    for (const sym of this.farAddrSymbols) {
      const base = sym.slice(1);
      externals.set(sym, {
        kind: "far_addr",
        value: this.farSymbolIndex.get(base) as number,
        original: sym,
      });
    }
    const orderedNative = this.nativeAddrSymbols.slice().sort((a, b) => {
      const aFirst = a === "_wait_frames" ? 0 : 1;
      const bFirst = b === "_wait_frames" ? 0 : 1;
      if (aFirst !== bFirst) return aFirst - bFirst;
      return a < b ? -1 : a > b ? 1 : 0;
    });
    orderedNative.forEach((sym, index) => {
      externals.set(sym, {
        kind: "native_addr",
        value: index,
        original: sym,
      });
    });
    this.nativeAddrOrder = orderedNative;
    for (const sym of this.nativeBankSymbols) {
      externals.set(sym, { kind: "native_bank", value: 0, original: sym });
    }
    this.otherSymbols.forEach((sym, index) => {
      externals.set(sym, {
        kind: "other",
        value: 0x4000 + index,
        original: sym,
      });
    });
    this.externals = externals;
  }

  ramExprValue(expr: string): number {
    const key = canonicalExpr(expr);
    const value = this.ramExprIndex.get(key);
    if (value === undefined) {
      throw new ConversionError(
        `unknown RAM index expression ${JSON.stringify(expr)}`,
      );
    }
    return value;
  }

  farExprValue(expr: string): number {
    const key = canonicalExpr(expr);
    const value = this.farExprIndex.get(key);
    if (value !== undefined) return value;
    for (const sym of expressionSymbols(expr)) {
      const kind = this.symbolKinds.get(sym);
      if (kind && kind[0] === "far_bank") return 0;
    }
    throw new ConversionError(
      `unknown far-data index expression ${JSON.stringify(expr)}`,
    );
  }

  layout(): void {
    // Script banks are numbered from 1, like GB Studio's exported banks.
    // Bank 0 means "no script" to the engine, so no script ever lives in
    // the first list slot; s2c_bank1 is banks[0].
    const banks: Script[][] = [];
    for (const script of this.scripts) {
      const forced = this.forcedBanks.get(script.name);
      if (forced !== undefined) {
        const target = forced - 1;
        while (banks.length <= target) banks.push([]);
        const used = banks[target].reduce((sum, item) => sum + item.size, 0);
        if (used + script.size > MAX_BANK) {
          throw new ConversionError(
            `script ${script.name} does not fit in forced bank ${forced}`,
          );
        }
        banks[target].push(script);
        continue;
      }
      let placed = false;
      for (const items of banks) {
        const used = items.reduce((sum, item) => sum + item.size, 0);
        if (used + script.size <= MAX_BANK) {
          items.push(script);
          placed = true;
          break;
        }
      }
      if (!placed) banks.push([script]);
    }
    banks.forEach((items, bankIndex) => {
      let offset = 0;
      for (const script of items) {
        script.bank = bankIndex + 1;
        script.offset = offset;
        offset += script.size;
      }
    });
    this.banks = banks;
  }

  resolveSymbol(name: string, script: Script): number {
    const label = script.labels.get(name);
    if (label !== undefined) return script.offset + label;
    if (name.startsWith("___bank_")) {
      const base = name.slice("___bank_".length);
      const target = this.scriptLabels.get("_" + base);
      if (target !== undefined) return target.bank;
    }
    if (script.consts.has(name)) {
      const value = script.consts.get(name) as number | string;
      if (typeof value === "number") return value;
      return this.resolveSymbol(value, script);
    }
    if (this.defs.constants.has(name)) {
      const value = this.defs.constants.get(name) as number | string;
      if (typeof value === "number") return value;
      return evalExpression(value, (sym) => this.resolveSymbol(sym, script));
    }
    const kind = this.symbolKinds.get(name);
    if (kind === undefined) {
      const target = this.scriptLabels.get(name);
      if (target !== undefined) return target.offset;
      throw new ExprError(`unresolved symbol ${JSON.stringify(name)}`);
    }
    const [what, base] = kind;
    if (what === "script_label") {
      return (this.scriptLabels.get(name) as Script).offset;
    }
    if (what === "script_bank") {
      const target = this.scriptLabels.get("_" + base);
      if (target === undefined) {
        throw new ExprError(
          `unknown script bank symbol ${JSON.stringify(name)}`,
        );
      }
      return target.bank;
    }
    if (what === "local_label") {
      const value = script.labels.get(name);
      if (value === undefined) {
        throw new ExprError(`unresolved local label ${JSON.stringify(name)}`);
      }
      return script.offset + value;
    }
    const external = this.externals.get(name);
    if (external !== undefined) return external.value;
    throw new ExprError(`unresolved external symbol ${JSON.stringify(name)}`);
  }

  pointerKind(symbols: string[], script: Script): string | null {
    const kinds: string[] = [];
    for (const sym of symbols) {
      if (script.consts.has(sym) || this.defs.constants.has(sym)) continue;
      if (
        script.labels.has(sym) ||
        this.scriptLabels.has(sym) ||
        /^\d+\$$/.test(sym)
      ) {
        kinds.push("script");
        continue;
      }
      const kind = this.symbolKinds.get(sym);
      if (!kind) continue;
      const what = kind[0];
      if (
        what === "script_label" ||
        what === "script_bank" ||
        what === "local_label"
      ) {
        kinds.push("script");
      } else if (what === "far_addr" || what === "far_bank") {
        kinds.push("far");
      } else if (what === "native_addr" || what === "native_bank") {
        kinds.push("native");
      } else if (what === "ram") {
        kinds.push("ram");
      } else {
        kinds.push("other");
      }
    }
    for (const wanted of ["script", "far", "native", "ram", "other"]) {
      if (kinds.includes(wanted)) return wanted;
    }
    return null;
  }

  emit(): void {
    let pointerBytes = 0;
    for (const script of this.scripts) {
      const data: number[] = new Array(script.size).fill(0);
      let pos = 0;
      for (const em of script.emissions) {
        if (em.literal && em.literal.length) {
          for (const value of em.literal) {
            data[pos] = value;
            pos += 1;
          }
          continue;
        }
        const lookup = (sym: string): number => this.resolveSymbol(sym, script);
        let symbols: string[] = [];
        try {
          symbols = expressionSymbols(em.expr);
        } catch {
          symbols = [];
        }
        const kind = this.pointerKind(symbols, script);
        let value: number;
        if (kind === "ram") {
          value = this.ramExprValue(em.expr);
        } else if (kind === "far") {
          value = this.farExprValue(em.expr);
        } else {
          value = evalExpression(em.expr, lookup);
        }
        let byte: number;
        if (em.mode === "word") {
          byte = extractByte(value, 8 * em.byteIndex);
        } else if (em.mode === "high") {
          byte = extractByte(value, 8);
        } else {
          byte = extractByte(value, 0);
        }
        data[pos] = byte;
        if (kind) {
          script.refs.set(pos, {
            expr: em.expr,
            symbols,
            kind,
            width: em.width,
            byteIndex: em.byteIndex,
            mode: em.mode,
          });
          pointerBytes += 1;
        }
        pos += 1;
      }
      if (pos !== script.size) {
        throw new ConversionError(`internal size mismatch for ${script.path}`);
      }
      script.data = data;
    }
    this.pointerBytes = pointerBytes;
  }

  run(): void {
    this.parse();
    this.classifySymbols();
    this.buildTables();
    this.layout();
    this.emit();
  }
}

function extractByte(value: number, shift: number): number {
  return Number(big(value) >> big(shift)) & 0xff;
}

// ---------------------------------------------------------------------------
// Output

export function sanitize(name: string): string {
  let result = name.replace(/[^A-Za-z0-9_]/g, "_");
  if (result && /^\d/.test(result)) result = "_" + result;
  return result.toUpperCase();
}

function tableCExpr(entries: Map<string, TableEntry>, key: string): string {
  const entry = entries.get(key) as TableEntry;
  const cName = entry.symbol.slice(1);
  if (entry.offset === 0) return cName;
  return `${cName} ${entry.offset > 0 ? "+" : "-"}${Math.abs(entry.offset)}`;
}

function hex4(value: number): string {
  return value.toString(16).toUpperCase().padStart(4, "0");
}

function signed(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`;
}

export function makeCensus(model: Converter): string {
  const counts: Record<string, number> = {
    ram: 0,
    far_bank: 0,
    far_addr: 0,
    native_addr: 0,
    native_bank: 0,
    other: 0,
  };
  for (const external of model.externals.values()) {
    counts[external.kind] = (counts[external.kind] ?? 0) + 1;
  }
  const lines = [
    `scripts ${model.scripts.length}`,
    `bytes ${model.scripts.reduce((sum, script) => sum + script.size, 0)}`,
    `banks ${model.banks.length}`,
    `pointer_bytes ${model.pointerBytes}`,
    `externals ${model.externals.size}`,
    `ram_symbols ${model.ramTable.length}`,
    `far_data ${model.farTable.length}`,
  ];
  const kinds = [
    "ram",
    "far_bank",
    "far_addr",
    "native_addr",
    "native_bank",
    "other",
  ];
  for (const kind of kinds) {
    lines.push(`external_${kind} ${counts[kind] ?? 0}`);
  }
  for (const kind of kinds) {
    const names = Array.from(model.externals.keys())
      .filter((sym) => model.externals.get(sym)?.kind === kind)
      .sort();
    for (const sym of names) {
      const external = model.externals.get(sym) as External;
      lines.push(
        `external ${kind} ${external.original} 0x${hex4(
          external.value & 0xffff,
        )}`,
      );
    }
  }
  lines.push(`skipped ${model.skipped.length}`);
  for (const entry of model.skipped) {
    lines.push(`skipped_file ${path.basename(entry.path)} ${entry.reason}`);
  }
  for (const key of model.ramTable) {
    const entry = model.ramTableEntries.get(key) as TableEntry;
    lines.push(`ram_entry ${entry.symbol} ${signed(entry.offset)}`);
  }
  for (const key of model.farTable) {
    const entry = model.farTableEntries.get(key) as TableEntry;
    lines.push(`far_entry ${entry.symbol} ${signed(entry.offset)}`);
  }
  return lines.join("\n") + "\n";
}

export function writeOutput(
  model: Converter,
  outDir: string,
  name: string,
): { header: string; source: string } {
  fs.mkdirSync(outDir, { recursive: true });
  const header = path.join(outDir, name + ".h");
  const source = path.join(outDir, name + ".c");

  const lines = [
    "/* Generated by wsc/tools/s2c.py. Do not edit. */",
    `#ifndef ${sanitize(name)}_H`,
    `#define ${sanitize(name)}_H`,
    "",
    "#include <stdint.h>",
    "",
    "#if defined(__ia16__)",
    "#define S2C_FAR __far",
    "#else",
    "#define S2C_FAR",
    "#endif",
    "",
    `#define S2C_BANK_COUNT ${model.banks.length}`,
    `#define S2C_RAM_SYMBOL_COUNT ${model.ramTable.length}`,
    `#define S2C_FAR_DATA_COUNT ${model.farTable.length}`,
    "",
  ];
  for (let bankIndex = 0; bankIndex < model.banks.length; bankIndex += 1) {
    lines.push(`extern const uint8_t S2C_FAR s2c_bank${bankIndex + 1}[];`);
  }
  lines.push(
    "",
    "/* Index tables consumed by vm_ram_ptr() and vm_far_data_ptr(). */",
    "extern uint8_t *const vm_ram_syms[];",
    "extern const uint8_t S2C_FAR *const vm_far_data[];",
    "",
  );
  for (const script of model.scripts) {
    const base = sanitize(script.name);
    lines.push(`#define S2C_SCRIPT_${base}_BANK ${script.bank}`);
    lines.push(`#define S2C_SCRIPT_${base}_OFFSET 0x${hex4(script.offset)}`);
    lines.push(`#define S2C_SCRIPT_${base}_SIZE 0x${hex4(script.size)}`);
    for (const label of script.exported) {
      const labelBase = sanitize(
        label.startsWith("_") ? label.slice(1) : label,
      );
      if (labelBase !== base) {
        lines.push(`#define S2C_SCRIPT_${labelBase}_BANK ${script.bank}`);
        lines.push(
          `#define S2C_SCRIPT_${labelBase}_OFFSET 0x${hex4(script.offset)}`,
        );
        lines.push(
          `#define S2C_SCRIPT_${labelBase}_SIZE 0x${hex4(script.size)}`,
        );
      }
    }
  }
  lines.push("", "#endif", "");
  fs.writeFileSync(header, lines.join("\n"));

  const cLines = [
    "/* Generated by wsc/tools/s2c.py. Do not edit. */",
    `#include "${path.basename(header)}"`,
    "",
  ];
  const ramEntries = model.ramTableEntries;
  const farEntries = model.farTableEntries;
  const ramBases = Array.from(
    new Set(
      model.ramTable.map((key) =>
        (ramEntries.get(key) as TableEntry).symbol.slice(1),
      ),
    ),
  ).sort();
  const farBases = Array.from(
    new Set(
      model.farTable.map((key) =>
        (farEntries.get(key) as TableEntry).symbol.slice(1),
      ),
    ),
  ).sort();
  if (ramBases.length) {
    cLines.push("/* C RAM symbols reached through vm_ram_syms[]. */");
    for (const base of ramBases) cLines.push(`extern uint8_t ${base}[];`);
    cLines.push("");
  }
  if (farBases.length) {
    cLines.push("/* C data objects reached through vm_far_data[]. */");
    for (const base of farBases) {
      cLines.push(`extern const uint8_t S2C_FAR ${base}[];`);
    }
    cLines.push("");
  }
  if (model.ramTable.length) {
    cLines.push("uint8_t *const vm_ram_syms[] = {");
    for (const key of model.ramTable) {
      cLines.push(`    ${tableCExpr(ramEntries, key)}, /* ${key} */`);
    }
    cLines.push("};");
  } else {
    cLines.push("uint8_t *const vm_ram_syms[1] = { (uint8_t *)0 };");
  }
  cLines.push("");
  if (model.farTable.length) {
    cLines.push("const uint8_t S2C_FAR *const vm_far_data[] = {");
    for (const key of model.farTable) {
      cLines.push(`    ${tableCExpr(farEntries, key)}, /* ${key} */`);
    }
    cLines.push("};");
  } else {
    cLines.push(
      "const uint8_t S2C_FAR *const vm_far_data[1] = " +
        "{ (const uint8_t S2C_FAR *)0 };",
    );
  }
  cLines.push("");
  // Native functions reached by VM_INVOKE and VM_CALL_NATIVE. Their operand
  // is the index into this table, in the same order as the converter's
  // native_addr indexes (wait_frames first, then the rest by symbol name).
  const native = model.nativeAddrOrder;
  // Only the full engine build has the native handlers and defines this
  // macro. Data-only ROMs (datarom) convert the same scripts but do not link
  // the VM, so they must not emit an unresolved table. A project with no
  // scripts still needs the symbol because the linked VM references it.
  cLines.push("#if defined(GBVM_ENGINE_HANDLERS)");
  cLines.push(
    "/* Native functions reached through vm_invoke/vm_call_native. */",
  );
  for (const sym of native) cLines.push(`extern void ${sym.slice(1)}();`);
  cLines.push("typedef void (* S2C_FAR s2c_native_fn_t)(void);");
  const size = native.length ? "[]" : "[1]";
  cLines.push(`s2c_native_fn_t vm_native_fns${size} = {`);
  for (const sym of native) {
    cLines.push(`    (s2c_native_fn_t)${sym.slice(1)}, /* ${sym} */`);
  }
  if (!native.length) cLines.push("    (s2c_native_fn_t)0,");
  cLines.push("};");
  cLines.push("#endif");
  cLines.push("");
  model.banks.forEach((items, bankIndex) => {
    const total = items.reduce((sum, script) => sum + script.size, 0);
    const bank = bankIndex + 1;
    cLines.push(
      `/* bank ${bank}: ${total} bytes, ${items.length} script(s) */`,
    );
    cLines.push(`const uint8_t S2C_FAR s2c_bank${bank}[] = {`);
    let offset = 0;
    for (const script of items) {
      cLines.push(
        `    /* ${script.name} at 0x${hex4(offset)}, ${script.size} bytes */`,
      );
      for (let i = 0; i < script.data.length; i += 12) {
        const chunk = script.data.slice(i, i + 12);
        cLines.push(
          "    " + chunk.map((byte) => `0x${hex2(byte)}`).join(", ") + ",",
        );
      }
      offset += script.size;
    }
    cLines.push("};");
    cLines.push("");
  });
  fs.writeFileSync(source, cLines.join("\n") + "\n");
  return { header, source };
}

function hex2(value: number): string {
  return value.toString(16).toUpperCase().padStart(2, "0");
}

export type S2COptions = {
  include: string;
  out: string;
  name: string;
  census?: string;
  quiet: boolean;
  banks: string[];
  files: string[];
};

function usageError(message: string): number {
  process.stderr.write(`s2c: error: ${message}\n`);
  return 2;
}

export function parseArgs(argv: string[]): S2COptions | number {
  const options: S2COptions = {
    include: "",
    out: "",
    name: "s2c_scripts",
    quiet: false,
    banks: [],
    files: [],
  };
  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];
    if (arg.startsWith("--") && arg.includes("=")) {
      const equal = arg.indexOf("=");
      const key = arg.slice(0, equal);
      const value = arg.slice(equal + 1);
      if (
        ["--include", "--out", "--name", "--bank", "--census"].includes(key)
      ) {
        if (key === "--include") options.include = value;
        else if (key === "--out") options.out = value;
        else if (key === "--name") options.name = value;
        else if (key === "--bank") options.banks.push(value);
        else options.census = value;
        i += 1;
        continue;
      }
    }
    if (arg === "--include" || arg === "--out" || arg === "--name") {
      if (i + 1 >= argv.length) return usageError(`${arg} needs a value`);
      const value = argv[i + 1];
      if (arg === "--include") options.include = value;
      else if (arg === "--out") options.out = value;
      else options.name = value;
      i += 2;
      continue;
    }
    if (arg === "--bank" || arg === "--census") {
      if (i + 1 >= argv.length) return usageError(`${arg} needs a value`);
      const value = argv[i + 1];
      if (arg === "--bank") options.banks.push(value);
      else options.census = value;
      i += 2;
      continue;
    }
    if (arg === "--quiet") {
      options.quiet = true;
      i += 1;
      continue;
    }
    if (arg.startsWith("-") && arg !== "-") {
      return usageError(`unrecognized argument ${JSON.stringify(arg)}`);
    }
    options.files.push(arg);
    i += 1;
  }
  if (!options.include) return usageError("--include is required");
  if (!options.out) return usageError("--out is required");
  if (!options.files.length)
    return usageError("at least one .s file is required");
  return options;
}

export function main(argv?: string[]): number {
  const args = argv ?? process.argv.slice(2);
  const parsed = parseArgs(args);
  if (typeof parsed === "number") return parsed;

  const forced = new Map<string, number>();
  for (const item of parsed.banks) {
    if (!item.includes("=")) return usageError("--bank needs NAME=N");
    const split = item.lastIndexOf("=");
    const name = item.slice(0, split);
    const value = item.slice(split + 1);
    let number: number;
    try {
      number = parseAutoInt(value);
    } catch {
      return usageError(`bad bank number ${JSON.stringify(value)}`);
    }
    if (number < 1) {
      return usageError(
        `bank numbers start at 1, got ${JSON.stringify(value)}`,
      );
    }
    forced.set(name.replace(/^_+/, ""), number);
  }

  try {
    const defs = new Definitions(parsed.include);
    const converter = new Converter(defs, parsed.files, forced);
    converter.run();
    writeOutput(converter, parsed.out, parsed.name);
    if (parsed.census) {
      fs.writeFileSync(parsed.census, makeCensus(converter));
    }
    if (!parsed.quiet) {
      process.stdout.write(
        `s2c: ${converter.scripts.length} scripts, ` +
          `${converter.scripts.reduce((sum, script) => sum + script.size, 0)} bytes, ` +
          `${converter.banks.length} banks, ${converter.pointerBytes} pointer bytes, ` +
          `${converter.externals.size} externals, ${converter.ramTable.length} ram symbols, ` +
          `${converter.farTable.length} far data, ${converter.skipped.length} skipped\n`,
      );
    }
  } catch (error) {
    if (error instanceof ConversionError) {
      process.stderr.write(`s2c: error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }
  return 0;
}
