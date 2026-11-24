import compileEntityEvents from "../../../src/lib/compiler/compileEntityEvents";
import { getTestScriptHandlers } from "../../getTestScriptHandlers";
import {
  WSC_TRUE_BRANCH_EVENT_ID,
  WSC_UNSUPPORTED_EVENT_IDS,
  filterWscSupportedEvents,
  isWscHiddenEvent,
} from "../../../src/shared/lib/scripts/wscEvents";
import { EVENT_TEXT } from "../../../src/consts";
import { setL10NData } from "../../../src/shared/lib/lang/l10n";

test("add-event list hides every GB-only WSC event", async () => {
  const handlers = await getTestScriptHandlers();
  const events = Object.values(handlers);
  const supported = filterWscSupportedEvents(events);
  const ids = new Set(supported.map((event) => event.id));

  for (const id of WSC_UNSUPPORTED_EVENT_IDS) {
    expect(isWscHiddenEvent(id)).toBe(true);
    expect(ids.has(id)).toBe(false);
  }
  expect(isWscHiddenEvent(WSC_TRUE_BRANCH_EVENT_ID)).toBe(true);
  expect(ids.has(WSC_TRUE_BRANCH_EVENT_ID)).toBe(false);
  expect(ids.has(EVENT_TEXT)).toBe(true);
});

test("WSC build warns and skips an unsupported event", async () => {
  setL10NData({
    WARNING_WSC_UNSUPPORTED_EVENT:
      'Event "{event}" is not supported on WonderSwan Color and was skipped in scene "{scene}".',
  });
  const scriptEventHandlers = await getTestScriptHandlers();
  const warnings: string[] = [];
  const output = compileEntityEvents(
    "testname",
    [
      {
        id: "print",
        command: "EVENT_PRINT",
        args: { source: "background", margin: 2 },
      },
    ],
    {
      scriptEventHandlers,
      scene: { name: "Scene" } as never,
      wsc: true,
      warnings: (message: string) => warnings.push(message),
    } as never,
  );

  expect(warnings).toHaveLength(1);
  expect(warnings[0]).toContain("EVENT_PRINT");
  expect(warnings[0]).toContain("WonderSwan Color");
  expect(output).toContain("VM_STOP");
  expect(output).not.toContain("print_status");
  expect(output).not.toContain("VM_PRINTER");
});

test("WSC build keeps only the true branch of If Color Supported", async () => {
  const scriptEventHandlers = await getTestScriptHandlers();
  const warnings: string[] = [];
  const output = compileEntityEvents(
    "testname",
    [
      {
        id: "color",
        command: WSC_TRUE_BRANCH_EVENT_ID,
        children: {
          true: [
            {
              id: "true-wait",
              command: "EVENT_WAIT",
              args: { units: "frames", frames: { type: "number", value: 10 } },
            },
          ],
          false: [
            {
              id: "false-idle",
              command: "EVENT_IDLE",
              args: {},
            },
          ],
        },
      },
    ],
    {
      scriptEventHandlers,
      scene: { name: "Scene" } as never,
      wsc: true,
      warnings: (message: string) => warnings.push(message),
    } as never,
  );

  expect(warnings).toHaveLength(0);
  expect(output).toContain("Wait 10 frames");
  expect(output).not.toContain("VM_IDLE");
});
