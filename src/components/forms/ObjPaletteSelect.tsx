import PaletteBlock from "components/forms/PaletteBlock";
import { hexToWscHex } from "shared/lib/helpers/wscColor";
import React, { memo, useMemo } from "react";
import {
  OptionLabelWithPreview,
  Select,
  SingleValueWithPreview,
} from "ui/form/Select";
import l10n from "shared/lib/lang/l10n";
import { SingleValue } from "react-select";
import { MonoOBJPalette, ObjPalette } from "shared/lib/resources/types";
import { DMG_PALETTE } from "consts";

interface ObjPaletteSelectProps {
  name: string;
  value?: ObjPalette;
  onChange?: (newValue: ObjPalette) => void;
  monoPalettes: [MonoOBJPalette, MonoOBJPalette];
}

interface ObjPaletteOption {
  value: ObjPalette;
  label: string;
  colors: string[];
}

const ObjPaletteSelectComponent = ({
  name,
  value = "OBP0",
  monoPalettes,
  onChange,
}: ObjPaletteSelectProps) => {
  const options: ObjPaletteOption[] = useMemo(() => {
    return [
      {
        value: "OBP0",
        label: "0: OBP0",
        colors: [
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[0][0]]),
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[0][1]]),
          "",
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[0][2]]),
        ],
      },
      {
        value: "OBP1",
        label: "1: OBP1",
        colors: [
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[1][0]]),
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[1][1]]),
          "",
          hexToWscHex(DMG_PALETTE.colors[monoPalettes[1][2]]),
        ],
      },
    ];
  }, [monoPalettes]);

  const currentValue = options.find((o) => o.value === value);
  return (
    <Select
      name={name}
      value={currentValue}
      options={options}
      onChange={(newValue: SingleValue<ObjPaletteOption>) => {
        if (newValue) {
          onChange?.(newValue.value);
        }
      }}
      formatOptionLabel={(option: ObjPaletteOption) => {
        return (
          <OptionLabelWithPreview
            preview={
              <PaletteBlock type="sprite" colors={option.colors} size={20} />
            }
          >
            {l10n("FIELD_PALETTE")} {option.label}
          </OptionLabelWithPreview>
        );
      }}
      components={{
        SingleValue: () => (
          <SingleValueWithPreview
            preview={
              <PaletteBlock
                type="sprite"
                colors={currentValue?.colors || []}
                size={20}
              />
            }
          >
            {l10n("FIELD_PALETTE")} {currentValue?.label}
          </SingleValueWithPreview>
        ),
      }}
    />
  );
};

export const ObjPaletteSelect = memo<ObjPaletteSelectProps>(
  ObjPaletteSelectComponent,
);
