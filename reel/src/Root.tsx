import React from "react";
import { Composition } from "remotion";
import { PaperReel, DURATION, FPS, WIDTH, HEIGHT } from "./PaperReel";
import {
  TrendReel,
  DURATION as TREND_DURATION,
  FPS as TREND_FPS,
  WIDTH as TREND_WIDTH,
  HEIGHT as TREND_HEIGHT,
} from "./TrendReel";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="PaperReel"
        component={PaperReel}
        durationInFrames={DURATION}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      <Composition
        id="TrendReel"
        component={TrendReel}
        durationInFrames={TREND_DURATION}
        fps={TREND_FPS}
        width={TREND_WIDTH}
        height={TREND_HEIGHT}
      />
    </>
  );
};
