import fs from "fs";
import os from "os";
import Path from "path";
import {
  Converter,
  Definitions,
  evalExpression,
  MAX_BANK,
  newScript,
  parseAutoInt,
  parseIndexExpr,
  ScriptParser,
} from "../../../src/lib/compiler/wsc/s2c";

const temporaryInclude = (files: Record<string, string>): string => {
  const dir = fs.mkdtempSync(Path.join(os.tmpdir(), "s2c-test-"));
  for (const [name, contents] of Object.entries(files)) {
    fs.writeFileSync(Path.join(dir, name), contents);
  }
  return dir;
};

const parse = (include: string, source: string) => {
  const script = newScript("test.s", "test", source);
  new ScriptParser(new Definitions(include), script).process(
    source.split("\n"),
  );
  return script;
};

test("expands macro arguments, including whitespace-separated ones", () => {
  const include = temporaryInclude({
    "vm.i": [
      ".macro SET_BYTES A B",
      "        .db ^!A!",
      "        .db ^!B!",
      ".endm",
      "",
    ].join("\n"),
  });
  const comma = parse(include, "SET_BYTES 1, 2");
  const space = parse(include, "SET_BYTES 1 2");
  expect(comma.emissions.map((em) => em.expr)).toEqual(["1", "2"]);
  expect(space.emissions.map((em) => em.expr)).toEqual(["1", "2"]);
  expect(comma.size).toBe(2);
});

test("keeps .db low/high operand forms and evaluates expressions", () => {
  const include = temporaryInclude({});
  const script = parse(include, ".db #<0x1234, #>0x1234");
  expect(script.emissions.map((em) => [em.expr, em.mode])).toEqual([
    ["0x1234", "low"],
    ["0x1234", "high"],
  ]);
  const parser = new ScriptParser(new Definitions(include), script);
  expect(parser.expandWrappers("^/BASE + 1/")).toBe("(BASE + 1)");
  expect(evalExpression("7 + 5", () => 0)).toBe(12);
});

test("parses RAM index expressions and integer forms", () => {
  expect(parseIndexExpr("(_joypads + 1)")).toEqual({
    key: "_joypads+1",
    symbol: "_joypads",
    offset: 1,
  });
  expect(parseIndexExpr("_scene_17")).toEqual({
    key: "_scene_17",
    symbol: "_scene_17",
    offset: 0,
  });
  expect(parseAutoInt("0x20")).toBe(32);
  expect(parseAutoInt("-2")).toBe(-2);
});

test("assigns one-based banks by first fit and forced bank", () => {
  const defs = new Definitions(temporaryInclude({}));
  const first = newScript("a.s", "a", "");
  const second = newScript("b.s", "b", "");
  const third = newScript("c.s", "c", "");
  first.size = MAX_BANK - 10;
  second.size = 20;
  third.size = 20;

  const converter = new Converter(defs, []);
  converter.scripts = [first, second, third];
  converter.layout();
  expect(converter.banks).toHaveLength(2);
  expect([first.bank, first.offset]).toEqual([1, 0]);
  expect([second.bank, second.offset]).toEqual([2, 0]);
  expect([third.bank, third.offset]).toEqual([2, 20]);

  const forced = new Converter(defs, [], new Map([["a", 3]]));
  forced.scripts = [first, second];
  forced.layout();
  expect(forced.banks).toHaveLength(3);
  expect([first.bank, first.offset]).toEqual([3, 0]);
  expect([second.bank, second.offset]).toEqual([1, 0]);
});
