import React, { useCallback } from "react";
import { CoordinateInput } from "ui/form/CoordinateInput";
import { SceneBoundsRect } from "shared/lib/resources/types";
import styled from "styled-components";
import clamp from "shared/lib/helpers/clamp";
import { ensureNumber } from "shared/types";
import { WSC_SCREEN_HEIGHT, WSC_SCREEN_WIDTH } from "consts";

const ScrollBoundsInputWrapper = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 10px;
`;

interface ScrollBoundsInputProps {
  name: string;
  sceneWidth: number;
  sceneHeight: number;
  value: SceneBoundsRect;
  onChange?: (newValue: SceneBoundsRect | undefined) => void;
}

const ScrollBoundsInput = ({
  name,
  value,
  sceneWidth,
  sceneHeight,
  onChange,
}: ScrollBoundsInputProps) => {
  const onChangeBoundsX = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const x = clamp(
        ensureNumber(parseInt(e.currentTarget.value, 10), 0),
        0,
        sceneWidth - WSC_SCREEN_WIDTH,
      );
      const width = clamp(
        value.width,
        WSC_SCREEN_WIDTH,
        Math.max(WSC_SCREEN_WIDTH, sceneWidth - x),
      );
      onChange?.({
        ...value,
        x,
        width,
      });
    },
    [onChange, sceneWidth, value],
  );
  const onChangeBoundsY = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const y = clamp(
        ensureNumber(parseInt(e.currentTarget.value, 10), 0),
        0,
        sceneHeight - WSC_SCREEN_HEIGHT,
      );
      const height = clamp(
        value.height,
        WSC_SCREEN_HEIGHT,
        Math.max(WSC_SCREEN_HEIGHT, sceneHeight - y),
      );

      onChange?.({
        ...value,
        y,
        height,
      });
    },
    [onChange, sceneHeight, value],
  );
  const onChangeBoundsWidth = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const width = clamp(
        ensureNumber(parseInt(e.currentTarget.value, 10), 0),
        WSC_SCREEN_WIDTH,
        Math.max(WSC_SCREEN_WIDTH, sceneWidth),
      );
      const x = clamp(value.x, 0, sceneWidth - width);
      onChange?.({
        ...value,
        x,
        width,
      });
    },
    [onChange, sceneWidth, value],
  );
  const onChangeBoundsHeight = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const height = clamp(
        ensureNumber(parseInt(e.currentTarget.value, 10), 0),
        WSC_SCREEN_HEIGHT,
        Math.max(WSC_SCREEN_HEIGHT, sceneHeight),
      );
      const y = clamp(value.y, 0, sceneHeight - height);
      onChange?.({
        ...value,
        y,
        height,
      });
    },
    [onChange, sceneHeight, value],
  );

  return (
    <ScrollBoundsInputWrapper>
      <CoordinateInput
        name={name}
        coordinate="x"
        value={value.x}
        placeholder="0"
        min={0}
        max={255 - WSC_SCREEN_WIDTH}
        onChange={onChangeBoundsX}
      />
      <CoordinateInput
        name={`${name}_y`}
        coordinate="y"
        value={value.y}
        placeholder="0"
        min={0}
        max={255 - WSC_SCREEN_HEIGHT}
        onChange={onChangeBoundsY}
      />
      <CoordinateInput
        name={`${name}_width`}
        coordinate="w"
        value={value.width}
        placeholder={String(sceneWidth)}
        min={WSC_SCREEN_WIDTH}
        max={255}
        onChange={onChangeBoundsWidth}
      />
      <CoordinateInput
        name={`${name}_height`}
        coordinate="h"
        value={value.height}
        placeholder={String(sceneHeight)}
        min={WSC_SCREEN_HEIGHT}
        max={255}
        onChange={onChangeBoundsHeight}
      />
    </ScrollBoundsInputWrapper>
  );
};

export default ScrollBoundsInput;
