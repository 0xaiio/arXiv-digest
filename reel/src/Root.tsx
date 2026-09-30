import React from "react";
import { Composition } from "remotion";
import { PaperReel, DURATION, FPS, WIDTH, HEIGHT } from "./PaperReel";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PaperReel"
      component={PaperReel}
      durationInFrames={DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
