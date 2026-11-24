/**
 * Events that are GB-only and hidden from the WonderSwan Color editor.
 *
 * Existing projects keep their events. The editor shows them with an
 * "unsupported" warning, and WSC builds skip them with a compiler warning.
 */
export const WSC_UNSUPPORTED_EVENT_IDS = [
  "EVENT_LINK_HOST",
  "EVENT_LINK_JOIN",
  "EVENT_LINK_CLOSE",
  "EVENT_LINK_TRANSFER",
  "EVENT_PRINT",
  "EVENT_PALETTE_SET_SGB",
  "EVENT_SET_SGB_COLOR_AREA",
  "EVENT_IF_DEVICE_SGB",
  "EVENT_IF_DEVICE_GBA",
] as const;

/**
 * Also hidden from the menu, but not skipped: the WSC is always colour, so
 * existing uses compile as the "true" branch.
 */
export const WSC_TRUE_BRANCH_EVENT_ID = "EVENT_IF_COLOR_SUPPORTED";

const unsupportedEventIds = new Set<string>(WSC_UNSUPPORTED_EVENT_IDS);

export const isWscUnsupportedEvent = (id: string): boolean =>
  unsupportedEventIds.has(id);

export const isWscHiddenEvent = (id: string): boolean =>
  isWscUnsupportedEvent(id) || id === WSC_TRUE_BRANCH_EVENT_ID;

export const isWscCompileSkippedEvent = (id: string): boolean =>
  isWscUnsupportedEvent(id);

export const filterWscSupportedEvents = <T extends { id: string }>(
  events: T[],
): T[] => events.filter((event) => !isWscHiddenEvent(event.id));
