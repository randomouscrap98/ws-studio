import compileEntityEvents from "../../../src/lib/compiler/compileEntityEvents";
import { getTestScriptHandlers } from "../../getTestScriptHandlers";
import { setL10NData } from "../../../src/shared/lib/lang/l10n";

const compile = async (
  command: string,
  args: Record<string, unknown>,
  wsc = true,
) => {
  const scriptEventHandlers = await getTestScriptHandlers();
  const warnings: string[] = [];
  const output = compileEntityEvents(
    "testname",
    [{ id: "orientation", command, args }],
    {
      scriptEventHandlers,
      scene: { name: "Scene" } as never,
      wsc,
      warnings: (message: string) => warnings.push(message),
    } as never,
  );
  return { output, warnings };
};

test("Set Screen Orientation emits the WSC orientation opcode", async () => {
  const { output, warnings } = await compile(
    "EVENT_SET_SCREEN_ORIENTATION",
    { orientation: "vertical" },
  );
  expect(warnings).toHaveLength(0);
  expect(output).toContain("VM_SET_ORIENTATION");
  expect(output).toContain(".ORIENTATION_VERTICAL");
});

test("Set Screen Orientation defaults to horizontal", async () => {
  const { output } = await compile("EVENT_SET_SCREEN_ORIENTATION", {});
  expect(output).toContain("VM_SET_ORIENTATION");
  expect(output).toContain(".ORIENTATION_HORIZONTAL");
});

test("Set Screen Orientation warns and is skipped on a non-WSC build", async () => {
  setL10NData({
    WARNING_WSC_ONLY_EVENT: 'Event "{event}" is not supported on Game Boy.',
  });
  const { output, warnings } = await compile(
    "EVENT_SET_SCREEN_ORIENTATION",
    { orientation: "vertical" },
    false,
  );
  expect(warnings).toHaveLength(1);
  expect(warnings[0]).toContain("EVENT_SET_SCREEN_ORIENTATION");
  expect(output).not.toContain("VM_SET_ORIENTATION");
});
