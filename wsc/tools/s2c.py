#!/usr/bin/env python3
"""Convert GB Studio exported sdas VM scripts into WSC C byte arrays.

The converter reads the macro definitions from vm.i/macro.i, evaluates the
sdas expressions used by the generated scripts, packs whole scripts into
banks <= 32767 bytes, and rewrites label/bank/native operands into the fork's
bank+offset model. It emits one C source with the banks and one header with
script constants and clearly named external placeholders.

Usage:
    s2c.py --include DIR --out DIR [--name NAME] [--bank NAME=N] file.s ...
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_BANK = 32767


class ConversionError(Exception):
    pass


# ---------------------------------------------------------------------------
# Expressions


class ExprError(ConversionError):
    pass


_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<sym>\d+\$|[A-Za-z_.$][A-Za-z0-9_.$]*)
      | (?P<num>0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+)
      | (?P<char>'(?:\\.|[^'\\])')
      | (?P<op><<|>>|[-+*/%&|^~()])
    )
    """,
    re.VERBOSE,
)


def _normalize_symbols(text):
    # sdas apostrophe concatenates adjacent symbol pieces: b'SYM, ___bank'SYM.
    return re.sub(r"(?<=[A-Za-z0-9_.$])'(?=[A-Za-z0-9_.$])", "", text)


class ExprParser:
    def __init__(self, text, lookup):
        self.text = _normalize_symbols(text.strip())
        self.lookup = lookup
        self.tokens = self._tokenize(self.text)
        self.pos = 0

    @staticmethod
    def _tokenize(text):
        tokens = []
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
                continue
            m = _TOKEN_RE.match(text, i)
            if not m or m.end() == i:
                raise ExprError("cannot tokenize expression: {!r}".format(text))
            kind = m.lastgroup
            tokens.append((kind, m.group(kind)))
            i = m.end()
        return tokens

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if tok[0] is None:
            raise ExprError("unexpected end of expression: {!r}".format(self.text))
        if value is not None and tok[1] != value:
            raise ExprError("expected {!r} in {!r}".format(value, self.text))
        self.pos += 1
        return tok

    def parse(self):
        value = self.parse_or()
        if self.pos != len(self.tokens):
            raise ExprError("trailing tokens in expression: {!r}".format(self.text))
        return value

    def parse_or(self):
        value = self.parse_xor()
        while self.peek() == ("op", "|"):
            self.take()
            value |= self.parse_xor()
        return value

    def parse_xor(self):
        value = self.parse_and()
        while self.peek() == ("op", "^"):
            self.take()
            value ^= self.parse_and()
        return value

    def parse_and(self):
        value = self.parse_shift()
        while self.peek() == ("op", "&"):
            self.take()
            value &= self.parse_shift()
        return value

    def parse_shift(self):
        value = self.parse_add()
        while self.peek() in (("op", "<<"), ("op", ">>")):
            op = self.take()[1]
            rhs = self.parse_add()
            value = value << rhs if op == "<<" else value >> rhs
        return value

    def parse_add(self):
        value = self.parse_mul()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            rhs = self.parse_mul()
            value = value + rhs if op == "+" else value - rhs
        return value

    def parse_mul(self):
        value = self.parse_unary()
        while self.peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self.take()[1]
            rhs = self.parse_unary()
            if op == "*":
                value *= rhs
            elif op == "/":
                if rhs == 0:
                    raise ExprError("division by zero in {!r}".format(self.text))
                value = int(value / rhs)
            else:
                if rhs == 0:
                    raise ExprError("modulo by zero in {!r}".format(self.text))
                value = value % rhs
        return value

    def parse_unary(self):
        tok = self.peek()
        if tok == ("op", "-"):
            self.take()
            return -self.parse_unary()
        if tok == ("op", "+"):
            self.take()
            return self.parse_unary()
        if tok == ("op", "~"):
            self.take()
            return ~self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        kind, text = self.take()
        if kind == "num":
            if text.lower().startswith("0x"):
                return int(text, 16)
            if text.lower().startswith("0b"):
                return int(text, 2)
            return int(text, 10)
        if kind == "char":
            body = text[1:-1]
            if body.startswith("\\"):
                escapes = {"n": 10, "r": 13, "t": 9, "0": 0, "\\": 92, "'": 39, '"': 34}
                if body[1:].isdigit():
                    return int(body[1:], 8)
                if body[1] in escapes:
                    return escapes[body[1]]
                return ord(body[1])
            if len(body) != 1:
                raise ExprError("bad character literal {!r}".format(text))
            return ord(body)
        if kind == "sym":
            return self.lookup(text)
        if (kind, text) == ("op", "("):
            value = self.parse_or()
            self.take(")")
            return value
        raise ExprError("unexpected token {!r} in {!r}".format(text, self.text))


def eval_expression(text, lookup):
    return ExprParser(text, lookup).parse()


def expression_symbols(text):
    return [tok[1] for tok in ExprParser._tokenize(_normalize_symbols(text)) if tok[0] == "sym"]


_INDEX_EXPR_RE = re.compile(
    r"^(_[A-Za-z0-9_]+)([+-](?:0[xX][0-9A-Fa-f]+|\d+))?$"
)


def canonical_expr(text):
    """Whitespace-free expression with redundant enclosing parentheses removed."""
    text = re.sub(r"\s+", "", text)
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        enclosed = True
        for index, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    if index != len(text) - 1:
                        enclosed = False
                    break
        if not enclosed:
            break
        text = text[1:-1]
    return text


def parse_index_expr(text):
    """Split a RAM/data expression into (canonical key, symbol, byte offset).

    An index table entry can only name one object. The generated scripts use
    expressions such as `_joypads + 1`; give those their own entry.
    """
    key = canonical_expr(text)
    match = _INDEX_EXPR_RE.match(key)
    if not match:
        raise ConversionError(
            "{} cannot be expressed as a table index; expected SYM or SYM+offset"
            .format(text.strip())
        )
    symbol, offset_text = match.groups()
    offset = int(offset_text, 0) if offset_text else 0
    return key, symbol, offset


# ---------------------------------------------------------------------------
# Source cleanup and sdas directives


def strip_comment(line):
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == ";":
            break
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def split_items(text):
    items = []
    start = 0
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail or items:
        items.append(tail)
    return items


def split_macro_args(text):
    if not text.strip():
        return []
    args = split_items(text)
    if len(args) == 1:
        # sdas also accepts whitespace-separated macro arguments.
        words = []
        start = 0
        depth = 0
        quote = None
        i = 0
        while i < len(text):
            ch = text[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
                i += 1
                continue
            if ch in "\"'":
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch.isspace() and depth == 0:
                words.append(text[start:i].strip())
                start = i + 1
            i += 1
        words.append(text[start:].strip())
        words = [word for word in words if word]
        if len(words) > 1:
            args = words
    return args


_ESCAPE = {
    "a": 7,
    "b": 8,
    "f": 12,
    "n": 10,
    "r": 13,
    "t": 9,
    "v": 11,
    "\\": 92,
    "'": 39,
    '"': 34,
    "0": 0,
}


def parse_string(text):
    text = text.strip()
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        raise ConversionError("bad string literal: {!r}".format(text))
    body = text[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ord(ch) & 0xFF)
            i += 1
            continue
        i += 1
        if i >= len(body):
            raise ConversionError("trailing backslash in string: {!r}".format(text))
        ch = body[i]
        if ch == "x":
            j = i + 1
            while j < len(body) and body[j] in "0123456789abcdefABCDEF":
                j += 1
            if j == i + 1:
                raise ConversionError("bad \\x escape in {!r}".format(text))
            out.append(int(body[i + 1:j], 16) & 0xFF)
            i = j
        elif ch in "01234567":
            j = i
            while j < len(body) and j < i + 3 and body[j] in "01234567":
                j += 1
            out.append(int(body[i:j], 8) & 0xFF)
            i = j
        elif ch in _ESCAPE:
            out.append(_ESCAPE[ch])
            i += 1
        else:
            out.append(ord(ch) & 0xFF)
            i += 1
    return bytes(out)


# ---------------------------------------------------------------------------
# Model


@dataclass
class Macro:
    name: str
    params: list
    body: list


@dataclass
class Emission:
    expr: str = ""
    width: int = 1
    byte_index: int = 0
    mode: str = "byte"
    literal: bytes = b""


@dataclass
class PointerRef:
    expr: str
    symbols: list
    kind: str
    width: int
    byte_index: int
    mode: str


@dataclass
class Script:
    path: Path
    name: str
    source: str
    labels: dict = field(default_factory=dict)
    exported: list = field(default_factory=list)
    consts: dict = field(default_factory=dict)
    emissions: list = field(default_factory=list)
    size: int = 0
    bank: int = -1
    offset: int = -1
    data: bytearray = field(default_factory=bytearray)
    refs: dict = field(default_factory=dict)  # byte offset -> PointerRef


@dataclass
class Model:
    scripts: list
    banks: list
    skipped: list
    externals: dict
    pointer_bytes: int


# ---------------------------------------------------------------------------
# Definitions


class Definitions:
    def __init__(self, include_dir):
        self.include_dir = Path(include_dir)
        self.constants = {}
        self.macros = {}
        self._load()

    def _files(self):
        preferred = [
            self.include_dir / "vm.i",
            self.include_dir / "macro.i",
        ]
        files = [p for p in preferred if p.is_file()]
        for path in sorted(self.include_dir.rglob("*.i")):
            if path not in files:
                files.append(path)
        return files

    def _load(self):
        for path in self._files():
            self._parse_file(path)

    def _parse_file(self, path):
        lines = path.read_text().splitlines()
        i = 0
        while i < len(lines):
            raw = strip_comment(lines[i]).strip()
            if not raw:
                i += 1
                continue
            m = re.match(r"^\.macro\s+([.]?[A-Za-z_]\w*)\s*(.*)$", raw, re.I)
            if m:
                name = m.group(1)
                params = [p for p in re.split(r"[\s,]+", m.group(2).strip()) if p]
                body = []
                i += 1
                while i < len(lines):
                    body_line = strip_comment(lines[i]).strip()
                    if re.match(r"^\.endm\b", body_line, re.I):
                        break
                    body.append(lines[i])
                    i += 1
                if i >= len(lines):
                    raise ConversionError("unterminated .macro {} in {}".format(name, path))
                self.macros[name] = Macro(name, params, body)
                i += 1
                continue
            m = re.match(r"^([.]?[A-Za-z_]\w*)\s*=\s*(.+)$", raw)
            if m:
                name, expr = m.groups()
                try:
                    self.constants[name] = eval_expression(
                        expr, lambda sym: self.constants[sym]
                    )
                except (ExprError, KeyError):
                    # Leave forward/unsupported definitions for the source pass.
                    self.constants[name] = expr
                i += 1
                continue
            i += 1


# ---------------------------------------------------------------------------
# Script parser


class ScriptParser:
    def __init__(self, defs, script):
        self.defs = defs
        self.script = script
        self.env = dict(defs.constants)
        self.env.update(script.consts)
    def lookup_now(self, name):
        if name in self.env:
            value = self.env[name]
            if isinstance(value, int):
                return value
            try:
                return eval_expression(value, self.lookup_now)
            except (ExprError, KeyError) as exc:
                raise ExprError("constant {!r} is not numeric yet".format(name)) from exc
        raise ExprError("unknown constant {!r}".format(name))

    def eval_now(self, text):
        return eval_expression(text, self.lookup_now)

    def expand_wrappers(self, text):
        # ^!ARG! and ^/(expr)/ are sdas macro substitution operators.
        def repl_bang(match):
            name = match.group(1)
            if name not in self.env:
                raise ConversionError("unknown macro argument {!r}".format(name))
            return str(self.env[name])

        def repl_expr(match):
            inner = match.group(1)
            try:
                return str(self.eval_now(inner))
            except ExprError:
                # Keep unresolved expressions for the deferred pass.
                return "(" + inner + ")"

        text = re.sub(r"\^!(.*?)!", repl_bang, text)
        text = re.sub(r"\^/(.*?)/", repl_expr, text)
        return text

    def substitute_macro_line(self, line, params, args):
        values = dict(zip(params, args))
        line = re.sub(r"\^!(.*?)!", lambda m: values[m.group(1)], line)
        if params:
            alternation = "|".join(re.escape(p) for p in sorted(params, key=len, reverse=True))
            pattern = r"(?<![A-Za-z0-9_.$])(" + alternation + r")(?![A-Za-z0-9_.$])"
            line = re.sub(pattern, lambda m: values[m.group(1)], line)
        return line

    def emit_literal(self, data):
        self.script.emissions.append(Emission(literal=bytes(data)))
        self.script.size += len(data)

    def emit_items(self, directive, rest):
        items = split_items(rest)
        if directive == ".db":
            for item in items:
                if not item:
                    continue
                mode = "byte"
                expr = item.strip()
                if expr.startswith("#>"):
                    mode, expr = "high", expr[2:].strip()
                elif expr.startswith("#<"):
                    mode, expr = "low", expr[2:].strip()
                elif expr.startswith("#"):
                    expr = expr[1:].strip()
                if expr.startswith('"'):
                    self.emit_literal(parse_string(expr))
                else:
                    self.script.emissions.append(
                        Emission(expr=expr, width=1, mode=mode)
                    )
                    self.script.size += 1
        elif directive == ".dw":
            for item in items:
                if not item:
                    continue
                expr = item.strip()
                if expr.startswith("#"):
                    expr = expr[1:].strip()
                self.script.emissions.append(
                    Emission(expr=expr, width=2, byte_index=0, mode="word")
                )
                self.script.emissions.append(
                    Emission(expr=expr, width=2, byte_index=1, mode="word")
                )
                self.script.size += 2
        elif directive == ".asciz":
            data = parse_string(rest)
            self.emit_literal(data + b"\0")
        else:
            raise ConversionError("unsupported directive {}".format(directive))

    def process(self, lines, depth=0):
        if depth > 30:
            raise ConversionError("macro nesting too deep")
        cond_stack = []

        def active():
            return all(cond_stack)

        for raw in lines:
            line = strip_comment(raw).strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith(".if "):
                if active():
                    cond_stack.append(bool(self.eval_now(self.expand_wrappers(line[4:]))))
                else:
                    cond_stack.append(False)
                continue
            if lowered == ".else":
                if not cond_stack:
                    raise ConversionError(".else without .if")
                cond_stack[-1] = not cond_stack[-1]
                continue
            if lowered == ".endif":
                if not cond_stack:
                    raise ConversionError(".endif without .if")
                cond_stack.pop()
                continue
            if not active():
                continue

            if re.match(r"^\.(module|include|area|globl|local|list|nlist|title|page)\b", line, re.I):
                continue
            if line.startswith(".db ") or line.startswith(".dw ") or line.startswith(".asciz "):
                directive, rest = line.split(None, 1)
                self.emit_items(directive, self.expand_wrappers(rest))
                continue

            m = re.match(r"^([.]?[A-Za-z_]\w*)\s*=\s*(.+)$", line)
            if m:
                name, expr = m.groups()
                value = self.eval_now(self.expand_wrappers(expr))
                self.env[name] = value
                self.script.consts[name] = value
                continue

            m = re.match(r"^([A-Za-z_.$][\w.$]*|\d+\$):{1,2}\s*(.*)$", line)
            if m:
                label, rest = m.groups()
                if label in self.script.labels:
                    raise ConversionError(
                        "duplicate label {} in {}".format(label, self.script.path)
                    )
                self.script.labels[label] = self.script.size
                if "::" in line.split(";")[0] and self.script.path:
                    self.script.exported.append(label)
                if rest:
                    self.process([rest], depth + 1)
                continue

            m = re.match(r"^([.]?[A-Za-z_]\w*)\b(.*)$", line)
            if not m:
                raise ConversionError(
                    "unsupported line in {}: {!r}".format(self.script.path, raw)
                )
            name, rest = m.groups()
            macro = self.defs.macros.get(name)
            if macro is None:
                raise ConversionError(
                    "unknown directive/macro {!r} in {}".format(name, self.script.path)
                )
            args = split_macro_args(self.expand_wrappers(rest.strip()))
            if len(args) != len(macro.params):
                raise ConversionError(
                    "macro {} expects {} args, got {} in {}".format(
                        name, len(macro.params), len(args), self.script.path
                    )
                )
            body = [
                self.substitute_macro_line(line, macro.params, args)
                for line in macro.body
            ]
            old = self.env
            self.env = dict(old)
            self.env.update(zip(macro.params, args))
            try:
                self.process(body, depth + 1)
            finally:
                self.env = old


# ---------------------------------------------------------------------------
# Script preparation


def prepare_source(path):
    text = Path(path).read_text()
    if re.search(r"^\s*\.module\b", text, re.M):
        return text, False
    m = re.search(r"^_script_engine_init::", text, re.M)
    if not m:
        return None, False
    lines = text.splitlines()
    entry = m.start()
    before = text[:entry].splitlines()
    includes = [line for line in before if re.match(r"^\s*\.include\b", line)]
    area = None
    for line in before:
        if re.match(r"^\s*\.area\b", line):
            area = line
    code = text[entry:].splitlines()
    prepared = includes + ([area] if area else []) + code
    return "\n".join(prepared) + "\n", True


def script_name(text, path):
    m = re.search(r"^\s*\.module\s+(\S+)", text, re.M)
    if m:
        return m.group(1)
    labels = re.findall(r"^([A-Za-z_]\w*)::", text, re.M)
    for label in labels:
        if label.startswith("_"):
            return label[1:]
    return path.stem


# ---------------------------------------------------------------------------
# Conversion


class Converter:
    def __init__(self, defs, files, forced_banks=None):
        self.defs = defs
        self.files = sorted(Path(f) for f in files)
        self.forced_banks = forced_banks or {}
        self.scripts = []
        self.skipped = []
        self.externals = {}
        self.ram_symbols = []
        self.far_bank_symbols = []
        self.far_addr_symbols = []
        self.native_addr_symbols = []
        self.other_symbols = []
        self.ram_expr_index = {}
        self.ram_symbol_index = {}
        self.far_expr_index = {}
        self.far_symbol_index = {}
        self.ram_table = []
        self.far_table = []

    def parse(self):
        for path in self.files:
            text, special = prepare_source(path)
            if text is None:
                self.skipped.append((path, "no .module and no _script_engine_init VM entry"))
                continue
            name = script_name(text, path)
            script = Script(path=path, name=name, source=text)
            parser = ScriptParser(self.defs, script)
            parser.process(text.splitlines())
            if special:
                self.skipped.append((path, "header data before _script_engine_init (VM code converted)"))
            elif path.name == "states_ptrs.s":
                self.skipped.append((path, "far-pointer table, not a VM script"))
            self.scripts.append(script)

    def classify_symbols(self):
        all_text = "\n".join(script.source for script in self.scripts)
        far_bases = set(re.findall(r"___bank_([A-Za-z0-9_]+)", all_text))
        native_bases = set(re.findall(r"\bb_([A-Za-z0-9_]+)", all_text))
        script_names = {script.name for script in self.scripts}
        self.script_labels = {}
        for script in self.scripts:
            for label in script.exported:
                self.script_labels[label] = script
        self.script_names = script_names
        self.far_bases = far_bases - script_names
        self.native_bases = native_bases

        file_consts = set()
        for script in self.scripts:
            file_consts.update(script.consts)
        symbols = set()
        for script in self.scripts:
            for em in script.emissions:
                if em.expr:
                    try:
                        symbols.update(expression_symbols(em.expr))
                    except ExprError as exc:
                        raise ConversionError(str(exc))
        self.symbol_kinds = {}
        ram, far_bank, far_addr, native_addr, other = [], [], [], [], []
        for sym in sorted(symbols):
            if sym in self.defs.constants or sym in self.script_labels:
                continue
            if sym.startswith(".") and sym in file_consts:
                continue
            if sym.startswith("___bank_"):
                base = sym[len("___bank_"):]
                if base in script_names:
                    self.symbol_kinds[sym] = ("script_bank", base)
                else:
                    self.symbol_kinds[sym] = ("far_bank", base)
                    far_bank.append(sym)
            elif sym.startswith("b_"):
                base = sym[2:]
                if base in native_bases:
                    self.symbol_kinds[sym] = ("native_bank", base)
                else:
                    self.symbol_kinds[sym] = ("other", sym)
                    other.append(sym)
            elif sym.startswith("_"):
                base = sym[1:]
                if sym in self.script_labels:
                    self.symbol_kinds[sym] = ("script_label", base)
                elif base in self.far_bases:
                    self.symbol_kinds[sym] = ("far_addr", base)
                    far_addr.append(sym)
                elif base in self.native_bases:
                    self.symbol_kinds[sym] = ("native_addr", base)
                    native_addr.append(sym)
                else:
                    self.symbol_kinds[sym] = ("ram", base)
                    ram.append(sym)
            elif re.match(r"^\d+\$$", sym):
                self.symbol_kinds[sym] = ("local_label", sym)
            else:
                self.symbol_kinds[sym] = ("other", sym)
                other.append(sym)

        self.ram_symbols = ram
        self.far_bank_symbols = far_bank
        self.far_addr_symbols = far_addr
        self.native_addr_symbols = native_addr
        self.native_bank_symbols = [
            sym for sym, kind in self.symbol_kinds.items() if kind[0] == "native_bank"
        ]
        self.other_symbols = other

    def build_tables(self):
        """Assign indexes for RAM pointers and far-data pointers.

        Every expression that reaches a RAM address becomes one index table
        entry. Offset expressions (`_joypads + 1`) get their own entry; the
        base object is always present too.
        """
        ram_entries = {}
        far_entries = {}

        def add(entries, expr):
            key, symbol, offset = parse_index_expr(expr)
            entries.setdefault(key, (symbol, offset))
            if offset:
                entries.setdefault(symbol, (symbol, 0))

        for script in self.scripts:
            for em in script.emissions:
                if not em.expr:
                    continue
                try:
                    symbols = expression_symbols(em.expr)
                except ExprError as exc:
                    raise ConversionError(str(exc))
                kind = self.pointer_kind(symbols, script)
                if kind == "ram":
                    add(ram_entries, em.expr)
                elif kind == "far":
                    if any(
                        self.symbol_kinds.get(sym, ("",))[0] == "far_bank"
                        for sym in symbols
                    ):
                        # ___bank_<object> is always the constant zero.
                        continue
                    add(far_entries, em.expr)

        for sym in self.ram_symbols:
            ram_entries.setdefault(sym, (sym, 0))
        for sym in self.far_addr_symbols:
            far_entries.setdefault(sym, (sym, 0))

        def order_for(entries):
            return lambda key: (entries[key][0].lower(), entries[key][1])

        self.ram_table = sorted(ram_entries, key=order_for(ram_entries))
        self.far_table = sorted(far_entries, key=order_for(far_entries))
        for index, key in enumerate(self.ram_table):
            self.ram_expr_index[key] = index
        for index, key in enumerate(self.far_table):
            self.far_expr_index[key] = index
        for key in self.ram_table:
            symbol, offset = ram_entries[key]
            if offset == 0:
                self.ram_symbol_index[symbol[1:]] = self.ram_expr_index[key]
        for key in self.far_table:
            symbol, offset = far_entries[key]
            if offset == 0:
                self.far_symbol_index[symbol[1:]] = self.far_expr_index[key]

        self.ram_table_entries = ram_entries
        self.far_table_entries = far_entries

        externals = {}
        for sym in self.ram_symbols:
            base = sym[1:]
            externals[sym] = ("ram", self.ram_symbol_index[base], sym)
        for sym in self.far_bank_symbols:
            externals[sym] = ("far_bank", 0, sym)
        for sym in self.far_addr_symbols:
            base = sym[1:]
            externals[sym] = ("far_addr", self.far_symbol_index[base], sym)
        ordered_native = sorted(
            self.native_addr_symbols, key=lambda s: (s != "_wait_frames", s)
        )
        for idx, sym in enumerate(ordered_native):
            externals[sym] = ("native_addr", idx, sym)
        for bank_sym in self.native_bank_symbols:
            externals[bank_sym] = ("native_bank", 0, bank_sym)
        for idx, sym in enumerate(self.other_symbols):
            externals[sym] = ("other", 0x4000 + idx, sym)
        self.externals = externals

    def ram_expr_value(self, expr):
        key = canonical_expr(expr)
        if key not in self.ram_expr_index:
            raise ConversionError("unknown RAM index expression {!r}".format(expr))
        return self.ram_expr_index[key]

    def far_expr_value(self, expr):
        key = canonical_expr(expr)
        if key in self.far_expr_index:
            return self.far_expr_index[key]
        for sym in expression_symbols(expr):
            kind = self.symbol_kinds.get(sym)
            if kind and kind[0] == "far_bank":
                return 0
        raise ConversionError("unknown far-data index expression {!r}".format(expr))

    def layout(self):
        # Script banks are numbered from 1, like GB Studio's exported banks.
        # Bank 0 means "no script" to the engine, so no script ever lives in
        # the first list slot; s2c_bank1 is banks[0].
        banks = []
        for script in self.scripts:
            forced = self.forced_banks.get(script.name)
            if forced is not None:
                target = forced - 1
                while len(banks) <= target:
                    banks.append([])
                used = sum(item.size for item in banks[target])
                if used + script.size > MAX_BANK:
                    raise ConversionError(
                        "script {} does not fit in forced bank {}".format(script.name, forced)
                    )
                banks[target].append(script)
                continue
            placed = False
            for index, items in enumerate(banks):
                used = sum(item.size for item in items)
                if used + script.size <= MAX_BANK:
                    items.append(script)
                    placed = True
                    break
            if not placed:
                banks.append([script])
        for bank_index, items in enumerate(banks):
            offset = 0
            for script in items:
                script.bank = bank_index + 1
                script.offset = offset
                offset += script.size
        self.banks = banks

    def resolve_symbol(self, name, script):
        if name in script.labels:
            return script.offset + script.labels[name]
        if name.startswith("___bank_"):
            base = name[len("___bank_"):]
            target = self.script_labels.get("_" + base)
            if target is not None:
                return target.bank
        if name in script.consts:
            value = script.consts[name]
            if isinstance(value, int):
                return value
            return self.resolve_symbol(value, script)
        if name in self.defs.constants:
            value = self.defs.constants[name]
            if isinstance(value, int):
                return value
            return eval_expression(value, lambda sym: self.resolve_symbol(sym, script))
        kind = self.symbol_kinds.get(name)
        if kind is None:
            if name in self.script_labels:
                return self.script_labels[name].offset
            raise ExprError("unresolved symbol {!r}".format(name))
        what, base = kind
        if what == "script_label":
            return self.script_labels[name].offset
        if what == "script_bank":
            target = self.script_labels.get("_" + base)
            if target is None:
                raise ExprError("unknown script bank symbol {!r}".format(name))
            return target.bank
        if what == "local_label":
            if name not in script.labels:
                raise ExprError("unresolved local label {!r}".format(name))
            return script.offset + script.labels[name]
        if name in self.externals:
            return self.externals[name][1]
        raise ExprError("unresolved external symbol {!r}".format(name))

    def pointer_kind(self, symbols, script):
        kinds = []
        for sym in symbols:
            if sym in script.consts or sym in self.defs.constants:
                continue
            if sym in script.labels or sym in self.script_labels or re.match(r"^\d+\$$", sym):
                kinds.append("script")
                continue
            kind = self.symbol_kinds.get(sym)
            if not kind:
                continue
            what = kind[0]
            if what in ("script_label", "script_bank", "local_label"):
                kinds.append("script")
            elif what in ("far_addr", "far_bank"):
                kinds.append("far")
            elif what in ("native_addr", "native_bank"):
                kinds.append("native")
            elif what == "ram":
                kinds.append("ram")
            else:
                kinds.append("other")
        for wanted in ("script", "far", "native", "ram", "other"):
            if wanted in kinds:
                return wanted
        return None

    def emit(self):
        pointer_bytes = 0
        for script in self.scripts:
            data = bytearray(script.size)
            pos = 0
            for em in script.emissions:
                if em.literal:
                    data[pos:pos + len(em.literal)] = em.literal
                    pos += len(em.literal)
                    continue
                lookup = lambda sym, s=script: self.resolve_symbol(sym, s)
                symbols = []
                try:
                    symbols = expression_symbols(em.expr)
                except ExprError:
                    pass
                kind = self.pointer_kind(symbols, script)
                if kind == "ram":
                    value = self.ram_expr_value(em.expr)
                elif kind == "far":
                    value = self.far_expr_value(em.expr)
                else:
                    value = eval_expression(em.expr, lookup)
                if em.mode == "word":
                    byte = (value >> (8 * em.byte_index)) & 0xFF
                elif em.mode == "high":
                    byte = (value >> 8) & 0xFF
                else:
                    byte = value & 0xFF
                data[pos] = byte
                if kind:
                    script.refs[pos] = PointerRef(
                        expr=em.expr,
                        symbols=symbols,
                        kind=kind,
                        width=em.width,
                        byte_index=em.byte_index,
                        mode=em.mode,
                    )
                    pointer_bytes += 1
                pos += 1
            if pos != script.size:
                raise ConversionError("internal size mismatch for {}".format(script.path))
            script.data = data
        self.pointer_bytes = pointer_bytes

    def run(self):
        self.parse()
        self.classify_symbols()
        self.build_tables()
        self.layout()
        self.emit()


# ---------------------------------------------------------------------------
# Output


def sanitize(name):
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if name and name[0].isdigit():
        name = "_" + name
    return name.upper()


def table_c_expr(entries, key):
    symbol, offset = entries[key]
    c_name = symbol[1:]
    if offset == 0:
        return c_name
    return "{} {:+d}".format(c_name, offset)


def write_output(model, out_dir, name):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    header = out_dir / (name + ".h")
    source = out_dir / (name + ".c")

    lines = [
        "/* Generated by wsc/tools/s2c.py. Do not edit. */",
        "#ifndef {}_H".format(sanitize(name)),
        "#define {}_H".format(sanitize(name)),
        "",
        "#include <stdint.h>",
        "",
        "#if defined(__ia16__)",
        "#define S2C_FAR __far",
        "#else",
        "#define S2C_FAR",
        "#endif",
        "",
        "#define S2C_BANK_COUNT {}".format(len(model.banks)),
        "#define S2C_RAM_SYMBOL_COUNT {}".format(len(model.ram_table)),
        "#define S2C_FAR_DATA_COUNT {}".format(len(model.far_table)),
        "",
    ]
    for bank_index in range(len(model.banks)):
        lines.append(
            "extern const uint8_t S2C_FAR s2c_bank{}[];".format(bank_index + 1)
        )
    lines.extend([
        "",
        "/* Index tables consumed by vm_ram_ptr() and vm_far_data_ptr(). */",
        "extern uint8_t *const vm_ram_syms[];",
        "extern const uint8_t S2C_FAR *const vm_far_data[];",
        "",
    ])
    for script in model.scripts:
        base = sanitize(script.name)
        lines.append("#define S2C_SCRIPT_{}_BANK {}".format(base, script.bank))
        lines.append("#define S2C_SCRIPT_{}_OFFSET 0x{:04X}".format(base, script.offset))
        lines.append("#define S2C_SCRIPT_{}_SIZE 0x{:04X}".format(base, script.size))
        for label in script.exported:
            label_base = sanitize(label[1:] if label.startswith("_") else label)
            if label_base != base:
                lines.append("#define S2C_SCRIPT_{}_BANK {}".format(label_base, script.bank))
                lines.append("#define S2C_SCRIPT_{}_OFFSET 0x{:04X}".format(label_base, script.offset))
                lines.append("#define S2C_SCRIPT_{}_SIZE 0x{:04X}".format(label_base, script.size))
    lines.extend(["", "#endif", ""])
    header.write_text("\n".join(lines))

    c_lines = [
        "/* Generated by wsc/tools/s2c.py. Do not edit. */",
        '#include "{}"'.format(header.name),
        "",
    ]
    ram_entries = model.ram_table_entries
    far_entries = model.far_table_entries
    ram_bases = sorted({ram_entries[key][0][1:] for key in model.ram_table})
    far_bases = sorted({far_entries[key][0][1:] for key in model.far_table})
    if ram_bases:
        c_lines.append("/* C RAM symbols reached through vm_ram_syms[]. */")
        for base in ram_bases:
            c_lines.append("extern uint8_t {}[];".format(base))
        c_lines.append("")
    if far_bases:
        c_lines.append("/* C data objects reached through vm_far_data[]. */")
        for base in far_bases:
            c_lines.append("extern const uint8_t S2C_FAR {}[];".format(base))
        c_lines.append("")
    if model.ram_table:
        c_lines.append("uint8_t *const vm_ram_syms[] = {")
        for key in model.ram_table:
            c_lines.append("    {}, /* {} */".format(
                table_c_expr(ram_entries, key), key
            ))
        c_lines.append("};")
    else:
        c_lines.append("uint8_t *const vm_ram_syms[1] = { (uint8_t *)0 };")
    c_lines.append("")
    if model.far_table:
        c_lines.append("const uint8_t S2C_FAR *const vm_far_data[] = {")
        for key in model.far_table:
            c_lines.append("    {}, /* {} */".format(
                table_c_expr(far_entries, key), key
            ))
        c_lines.append("};")
    else:
        c_lines.append(
            "const uint8_t S2C_FAR *const vm_far_data[1] = "
            "{ (const uint8_t S2C_FAR *)0 };"
        )
    c_lines.append("")
    # Native functions reached by VM_INVOKE and VM_CALL_NATIVE. Their operand
    # is the index into this table, in the same order as the converter's
    # native_addr indexes (wait_frames first, then the rest by symbol name).
    native = sorted(
        model.native_addr_symbols, key=lambda sym: (sym != "_wait_frames", sym)
    )
    if native:
        # Only the full engine build has the native handlers and defines this
        # macro. Data-only ROMs (datarom) convert the same scripts but do not
        # link the VM, so they must not emit an unresolved table.
        c_lines.append("#if defined(GBVM_ENGINE_HANDLERS)")
        c_lines.append("/* Native functions reached through vm_invoke/vm_call_native. */")
        for sym in native:
            c_lines.append("extern void {}();".format(sym[1:]))
        c_lines.append("typedef void (* S2C_FAR s2c_native_fn_t)(void);")
        c_lines.append("s2c_native_fn_t vm_native_fns[] = {")
        for sym in native:
            c_lines.append("    (s2c_native_fn_t){}, /* {} */".format(sym[1:], sym))
        c_lines.append("};")
        c_lines.append("#endif")
        c_lines.append("")
    for bank_index, items in enumerate(model.banks):
        total = sum(script.size for script in items)
        bank = bank_index + 1
        c_lines.append("/* bank {}: {} bytes, {} script(s) */".format(
            bank, total, len(items)
        ))
        c_lines.append("const uint8_t S2C_FAR s2c_bank{}[] = {{".format(bank))
        offset = 0
        for script in items:
            c_lines.append("    /* {} at 0x{:04X}, {} bytes */".format(
                script.name, offset, script.size
            ))
            for i in range(0, len(script.data), 12):
                chunk = script.data[i:i + 12]
                c_lines.append("    " + ", ".join("0x{:02X}".format(b) for b in chunk) + ",")
            offset += script.size
        c_lines.append("};")
        c_lines.append("")
    source.write_text("\n".join(c_lines) + "\n")
    return header, source


def make_census(model):
    counts = {"ram": 0, "far_bank": 0, "far_addr": 0, "native_addr": 0, "native_bank": 0, "other": 0}
    for kind, _value, _original in model.externals.values():
        counts[kind] = counts.get(kind, 0) + 1
    lines = [
        "scripts {}".format(len(model.scripts)),
        "bytes {}".format(sum(script.size for script in model.scripts)),
        "banks {}".format(len(model.banks)),
        "pointer_bytes {}".format(model.pointer_bytes),
        "externals {}".format(len(model.externals)),
        "ram_symbols {}".format(len(model.ram_table)),
        "far_data {}".format(len(model.far_table)),
    ]
    for kind in ("ram", "far_bank", "far_addr", "native_addr", "native_bank", "other"):
        lines.append("external_{} {}".format(kind, counts.get(kind, 0)))
    for kind in ("ram", "far_bank", "far_addr", "native_addr", "native_bank", "other"):
        for sym in sorted(model.externals, key=lambda s: (model.externals[s][0], s)):
            k, value, original = model.externals[sym]
            if k == kind:
                lines.append("external {} {} 0x{:04X}".format(kind, original, value & 0xFFFF))
    lines.append("skipped {}".format(len(model.skipped)))
    for path, reason in model.skipped:
        lines.append("skipped_file {} {}".format(path.name, reason))
    for key in model.ram_table:
        symbol, offset = model.ram_table_entries[key]
        lines.append("ram_entry {} {:+d}".format(symbol, offset))
    for key in model.far_table:
        symbol, offset = model.far_table_entries[key]
        lines.append("far_entry {} {:+d}".format(symbol, offset))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include", required=True, help="directory containing vm.i/macro.i")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--name", default="s2c_scripts", help="output basename")
    parser.add_argument("--bank", action="append", default=[], metavar="NAME=N",
                        help="force script NAME into bank N")
    parser.add_argument("--census", help="write a text census to this path")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("files", nargs="+", help="input .s files")
    args = parser.parse_args(argv)

    forced = {}
    for item in args.bank:
        if "=" not in item:
            parser.error("--bank needs NAME=N")
        name, value = item.rsplit("=", 1)
        try:
            number = int(value, 0)
        except ValueError:
            parser.error("bad bank number {!r}".format(value))
        if number < 1:
            parser.error("bank numbers start at 1, got {!r}".format(value))
        forced[name.lstrip("_")] = number

    try:
        defs = Definitions(args.include)
        converter = Converter(defs, args.files, forced)
        converter.run()
        write_output(converter, args.out, args.name)
        if args.census:
            Path(args.census).write_text(make_census(converter))
        if not args.quiet:
            print(
                "s2c: {} scripts, {} bytes, {} banks, {} pointer bytes, {} externals, "
                "{} ram symbols, {} far data, {} skipped".format(
                    len(converter.scripts),
                    sum(script.size for script in converter.scripts),
                    len(converter.banks),
                    converter.pointer_bytes,
                    len(converter.externals),
                    len(converter.ram_table),
                    len(converter.far_table),
                    len(converter.skipped),
                )
            )
    except (ConversionError, ExprError) as exc:
        print("s2c: error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
