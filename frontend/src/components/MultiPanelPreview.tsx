import React from "react";
import { View, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { colors } from "@/src/theme";

export type FrameVisual = {
  face: string;
  bevel: string;
  edge: string;
  width: number;
  bevelWidth: number;
  edgeWidth: number;
};

// Layered tones make the four finishes readable at preview size. In particular,
// Natural Wood stays warm and visibly different from Matte Black.
const FRAME_VISUALS: Record<string, Record<string, FrameVisual>> = {
  canvas: {
    wood: { face: "#A87345", bevel: "#D8B17E", edge: "#664226", width: 8, bevelWidth: 3, edgeWidth: 1 },
    black: { face: "#171615", bevel: "#4A4743", edge: "#050505", width: 8, bevelWidth: 3, edgeWidth: 1 },
    white: { face: "#F7F4EC", bevel: "#D8D1C5", edge: "#AFA79A", width: 8, bevelWidth: 3, edgeWidth: 1 },
    none: { face: "transparent", bevel: "transparent", edge: colors.borderStrong, width: 0, bevelWidth: 0, edgeWidth: 1 },
  },
  poster: {
    wood: { face: "#B57C4D", bevel: "#E0BE91", edge: "#745034", width: 6, bevelWidth: 2, edgeWidth: 1 },
    black: { face: "#171615", bevel: "#4A4743", edge: "#050505", width: 6, bevelWidth: 2, edgeWidth: 1 },
    white: { face: "#F7F4EC", bevel: "#D8D1C5", edge: "#AFA79A", width: 6, bevelWidth: 2, edgeWidth: 1 },
    none: { face: "transparent", bevel: "transparent", edge: colors.borderStrong, width: 0, bevelWidth: 0, edgeWidth: 1 },
  },
  metal: {
    metal: { face: "#C0C6CA", bevel: "#F5F7F8", edge: "#535B60", width: 3, bevelWidth: 1, edgeWidth: 1 },
  },
};

export function getFrameVisual(material: string, frameKey: string): FrameVisual {
  const palette = FRAME_VISUALS[material] || FRAME_VISUALS.canvas;
  let normalizedFrame = frameKey;
  if (frameKey === "brown" || frameKey === "red_oak" || frameKey === "oak" || frameKey === "oak_deep" || frameKey === "oak_float" || frameKey === "walnut") {
    normalizedFrame = "wood";
  } else if (frameKey === "black_float" || frameKey === "black_deep") {
    normalizedFrame = "black";
  }
  // Walnut gets a deeper wood face when available via canvas/poster wood slot override
  if (frameKey === "walnut" && palette.wood) {
    return { ...palette.wood, face: "#5C4033", bevel: "#8B6914", edge: "#3E2723" };
  }
  return palette[normalizedFrame] || palette.wood || FRAME_VISUALS.canvas.none;
}

// Renders the artwork as `count` side-by-side panels (split canvas look).
export default function MultiPanelPreview({
  image, count = 1, frameKey = "wood", material = "canvas", width = 260, height = 300, gap = 10,
}: { image: string; count?: number; frameKey?: string; material?: string; width?: number; height?: number; gap?: number }) {
  const fb = getFrameVisual(material, frameKey);
  const panelW = (width - gap * (count - 1)) / count;
  const inset = fb.edgeWidth + fb.width + fb.bevelWidth;
  const innerW = Math.max(1, panelW - inset * 2);
  const innerH = Math.max(1, height - inset * 2);

  return (
    <View style={[styles.row, { width, height, gap }]} testID="panel-preview">
      {Array.from({ length: count }).map((_, i) => (
        <View
          key={i}
          style={[
            styles.panel,
            {
              width: panelW,
              height,
              borderColor: fb.edge,
              borderWidth: fb.edgeWidth,
              backgroundColor: fb.face,
              padding: fb.width,
            },
          ]}
        >
          <View style={{ width: innerW + fb.bevelWidth * 2, height: innerH + fb.bevelWidth * 2, borderColor: fb.bevel, borderWidth: fb.bevelWidth }}>
            <View style={{ width: innerW, height: innerH, overflow: "hidden" }}>
              <Image
                source={{ uri: image }}
                style={{ width: innerW * count + gap * (count - 1), height: innerH, marginLeft: -(innerW + gap) * i }}
                contentFit="cover"
              />
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignSelf: "center", justifyContent: "center" },
  panel: {
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#1A1510",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 7,
    elevation: 5,
  },
});
