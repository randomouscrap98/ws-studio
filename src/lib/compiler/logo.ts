// The boot logo is a fixed 160x144 image, independent of the device's
// logical screen size. Keep its layout here instead of deriving it from the
// GB screen constants so a wider screen does not reshape the logo asset.
export const LOGO_TILES_W = 20;
export const LOGO_TILES_H = 18;
export const LOGO_PX_W = LOGO_TILES_W * 8;
export const LOGO_PX_H = LOGO_TILES_H * 8;
