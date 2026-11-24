import React, { useCallback } from "react";
import l10n from "shared/lib/lang/l10n";
import { PaletteSelect } from "components/forms/PaletteSelect";
import { Button } from "ui/buttons/Button";
import { CardAnchor, CardButtons, CardHeading } from "ui/cards/Card";
import { SearchableSettingRow } from "ui/form/SearchableSettingRow";
import { SettingRowInput, SettingRowLabel } from "ui/form/SettingRow";
import { SearchableCard } from "ui/cards/SearchableCard";
import { FormInfo } from "ui/form/FormInfo";
import { FormField } from "ui/form/layout/FormLayout";
import { FixedSpacer } from "ui/spacing/Spacing";
import { AutoTileFlipSelect } from "components/forms/AutoTileFlipSelect";
import { useAppDispatch, useAppSelector } from "store/hooks";
import settingsActions from "store/features/settings/settingsActions";
import { NavigationSection } from "store/features/navigation/navigationState";
import navigationActions from "store/features/navigation/navigationActions";

interface SettingsSectionColorProps {
  searchTerm: string;
}

export const SettingsSectionColor = ({
  searchTerm,
}: SettingsSectionColorProps) => {
  const dispatch = useAppDispatch();

  const autoTileFlipEnabled = useAppSelector(
    (state) => state.project.present.settings.autoTileFlipEnabled,
  );

  const defaultBackgroundPaletteIds = useAppSelector(
    (state) => state.project.present.settings.defaultBackgroundPaletteIds,
  );

  const defaultSpritePaletteIds = useAppSelector(
    (state) => state.project.present.settings.defaultSpritePaletteIds,
  );

  // WonderSwan Color is always colour; existing mono setting values stay
  // untouched in project files but the editor presents colour palettes.
  const colorEnabled = true;

  const setSection = useCallback(
    (section: NavigationSection) => {
      dispatch(navigationActions.setSection(section));
    },
    [dispatch],
  );

  const onChangeAutoTileFlip = useCallback(
    (e: boolean) =>
      dispatch(settingsActions.editSettings({ autoTileFlipEnabled: e })),
    [dispatch],
  );

  const onEditPaletteId = useCallback(
    (index: number, e: string) => {
      const paletteIds = defaultBackgroundPaletteIds
        ? [...defaultBackgroundPaletteIds]
        : [];
      paletteIds[index] = e;
      dispatch(
        settingsActions.editSettings({
          defaultBackgroundPaletteIds: [
            paletteIds[0],
            paletteIds[1],
            paletteIds[2],
            paletteIds[3],
            paletteIds[4],
            paletteIds[5],
            paletteIds[6],
            paletteIds[7],
          ],
        }),
      );
    },
    [defaultBackgroundPaletteIds, dispatch],
  );

  const onEditSpritePaletteId = useCallback(
    (index: number, e: string) => {
      const paletteIds = defaultSpritePaletteIds
        ? [...defaultSpritePaletteIds]
        : [];
      paletteIds[index] = e;
      dispatch(
        settingsActions.editSettings({
          defaultSpritePaletteIds: [
            paletteIds[0],
            paletteIds[1],
            paletteIds[2],
            paletteIds[3],
            paletteIds[4],
            paletteIds[5],
            paletteIds[6],
            paletteIds[7],
          ],
        }),
      );
    },
    [defaultSpritePaletteIds, dispatch],
  );

  return (
    <SearchableCard
      searchTerm={searchTerm}
      searchMatches={[
        l10n("FIELD_EXPORT_IN_COLOR"),
        l10n("FIELD_DEFAULT_BACKGROUND_PALETTES"),
        l10n("FIELD_DEFAULT_SPRITE_PALETTES"),
        l10n("FIELD_AUTO_TILE_FLIP"),
      ]}
    >
      <CardAnchor id="settingsColor" />
      <CardHeading>{l10n("SETTINGS_COLOR")}</CardHeading>

      {colorEnabled && (
        <>
          <SearchableSettingRow
            searchTerm={searchTerm}
            searchMatches={[l10n("FIELD_AUTO_TILE_FLIP")]}
          >
            <SettingRowLabel>{l10n("FIELD_AUTO_TILE_FLIP")}</SettingRowLabel>
            <SettingRowInput>
              <AutoTileFlipSelect
                value={autoTileFlipEnabled}
                onChange={onChangeAutoTileFlip}
              />
              <FormInfo>
                {l10n("FIELD_AUTO_TILE_FLIP_DESC")}
              </FormInfo>
            </SettingRowInput>
          </SearchableSettingRow>
        </>
      )}

      {colorEnabled && (
        <>
          <SearchableSettingRow
            searchTerm={searchTerm}
            searchMatches={[l10n("FIELD_DEFAULT_BACKGROUND_PALETTES")]}
          >
            <SettingRowLabel>
              {l10n("FIELD_DEFAULT_BACKGROUND_PALETTES")}
            </SettingRowLabel>
            <SettingRowInput>
              <div>
                {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
                  <FormField key={index} name={`scenePalette${index}`}>
                    <PaletteSelect
                      name={`scenePalette${index}`}
                      prefix={`${index + 1}:`}
                      value={
                        (defaultBackgroundPaletteIds &&
                          defaultBackgroundPaletteIds[index]) ||
                        ""
                      }
                      onChange={(e: string) => {
                        onEditPaletteId(index, e);
                      }}
                    />
                    {index !== 7 && <FixedSpacer height={3} />}
                    {index === 7 && (
                      <FormInfo>{l10n("FIELD_UI_PALETTE_NOTE")}</FormInfo>
                    )}
                  </FormField>
                ))}
              </div>
            </SettingRowInput>
          </SearchableSettingRow>

          <SearchableSettingRow
            searchTerm={searchTerm}
            searchMatches={[l10n("FIELD_DEFAULT_SPRITE_PALETTES")]}
          >
            <SettingRowLabel>
              {l10n("FIELD_DEFAULT_SPRITE_PALETTES")}
            </SettingRowLabel>
            <SettingRowInput>
              <div key={JSON.stringify(defaultSpritePaletteIds)}>
                {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
                  <FormField key={index} name={`spritePalette${index}`}>
                    <PaletteSelect
                      name={`spritePalette${index}`}
                      prefix={`${index + 1}:`}
                      value={
                        (defaultSpritePaletteIds &&
                          defaultSpritePaletteIds[index]) ||
                        ""
                      }
                      type="sprite"
                      onChange={(e: string) => {
                        onEditSpritePaletteId(index, e);
                      }}
                    />
                    {index !== 7 && <FixedSpacer height={3} />}
                    {index === 7 && (
                      <FormInfo>{l10n("FIELD_EMOTE_PALETTE_NOTE")}</FormInfo>
                    )}
                  </FormField>
                ))}
              </div>
            </SettingRowInput>
          </SearchableSettingRow>
          {!searchTerm && (
            <CardButtons>
              <Button onClick={() => setSection("palettes")}>
                {l10n("FIELD_EDIT_PALETTES")}
              </Button>
            </CardButtons>
          )}
        </>
      )}
    </SearchableCard>
  );
};
