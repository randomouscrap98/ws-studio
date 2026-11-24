import { compileWscColor } from "../../../src/lib/compiler/generateGBVMData";
import {
  hexToWscHex,
  hexToWscRgb,
  rgb8ToWsc4,
  rgb8ToWscCgb5,
  wsc4ToRgb8,
} from "../../../src/shared/lib/helpers/wscColor";

const parseCompiled = (color: string) => {
  const match = /^RGB\((\d+), (\d+), (\d+)\)$/.exec(color);
  if (!match) {
    throw new Error(`Unexpected compiled colour ${color}`);
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])] as const;
};

const hexFor = (channels: number[]) =>
  channels.map((value) => value.toString(16).padStart(2, "0")).join("");

test("RGB444 preview matches the compiler conversion for every channel value", () => {
  for (let channel = 0; channel < 3; channel++) {
    for (let value = 0; value < 256; value++) {
      const channels = [0, 0, 0];
      channels[channel] = value;
      const hex = hexFor(channels);

      const cgb5 = parseCompiled(compileWscColor(hex));
      // The WSC HAL halves each 5-bit channel when writing RGB444 registers.
      const halNibble = cgb5[channel] >> 1;
      expect(halNibble).toBe(rgb8ToWsc4(value));
      expect(cgb5[channel]).toBe(rgb8ToWscCgb5(value));

      const preview = hexToWscRgb(hex);
      expect(
        [preview.r, preview.g, preview.b][channel],
      ).toBe(wsc4ToRgb8(halNibble));
    }
  }
});

test("preview shows each RGB444 nibble as n * 17", () => {
  expect(hexToWscHex("000000")).toBe("000000");
  expect(hexToWscHex("FFFFFF")).toBe("FFFFFF");
  expect(hexToWscHex("0F0F0F")).toBe("111111");
  expect(hexToWscHex("808080")).toBe("888888");
});

test("RGB444 values are the nearest 4-bit level", () => {
  expect(rgb8ToWsc4(0)).toBe(0);
  expect(rgb8ToWsc4(8)).toBe(0);
  expect(rgb8ToWsc4(9)).toBe(1);
  expect(rgb8ToWsc4(255)).toBe(15);
  expect(wsc4ToRgb8(15)).toBe(255);
});
