import { hexDec } from "shared/lib/helpers/8bit";

/**
 * WonderSwan Color RGB444 conversion.
 *
 * Stored project colours stay 24-bit. The WSC displays four bits per channel,
 * so previews map each 8-bit channel to the nearest 4-bit value and show that
 * value as `nibble * 17` in an 8-bit RGB canvas.
 *
 * The compiler emits WSC palettes as 5-bit CGB words because the WSC HAL
 * halves each channel (`nibble * 2 >> 1 == nibble`). `rgb8ToWscCgb5` is the
 * compiler side of the same mapping.
 */

export const WSC_COLOR_LEVELS = 15;

export const rgb8ToWsc4 = (value: number): number =>
  Math.round((Math.max(0, Math.min(255, Math.round(value))) * 15) / 255);

export const wsc4ToRgb8 = (value: number): number =>
  Math.max(0, Math.min(15, Math.round(value))) * 17;

export const rgb8ToWscRgb8 = (value: number): number =>
  wsc4ToRgb8(rgb8ToWsc4(value));

/** 5-bit value that the WSC HAL halves back to the RGB444 nibble. */
export const rgb8ToWscCgb5 = (value: number): number =>
  rgb8ToWsc4(value) * 2;

const channel = (hex: string, index: number): number =>
  hexDec(hex.substring(index * 2, index * 2 + 2));

const toHex = (r: number, g: number, b: number): string =>
  [r, g, b]
    .map((value) => value.toString(16).padStart(2, "0").toUpperCase())
    .join("");

export const hexToWscRgb = (
  hex: string,
): { r: number; g: number; b: number } => ({
  r: rgb8ToWscRgb8(channel(hex, 0)),
  g: rgb8ToWscRgb8(channel(hex, 1)),
  b: rgb8ToWscRgb8(channel(hex, 2)),
});

export const hexToWscRgb444 = (
  hex: string,
): { r: number; g: number; b: number } => ({
  r: rgb8ToWsc4(channel(hex, 0)),
  g: rgb8ToWsc4(channel(hex, 1)),
  b: rgb8ToWsc4(channel(hex, 2)),
});

export const hexToWscHex = (hex: string): string => {
  const { r, g, b } = hexToWscRgb(hex);
  return toHex(r, g, b);
};

const channel5To8 = (value: number): number =>
  Math.round((Math.max(0, Math.min(31, Math.round(value))) * 255) / 31);

/** Preview a canonical 5-bit (GB-storage) colour through RGB444. */
export const rgb5BitToWscHex = (
  red5: number,
  green5: number,
  blue5: number,
): string =>
  hexToWscHex(
    toHex(channel5To8(red5), channel5To8(green5), channel5To8(blue5)),
  );
