import { useEffect, useRef, useState } from "react";
import {
  View, Text, StyleSheet, Pressable, ScrollView, PanResponder,
  Animated, Platform, ActivityIndicator, Dimensions,
} from "react-native";
import * as ImageManipulator from "expo-image-manipulator";
import * as LegacyFS from "expo-file-system/legacy";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import { getProject, updateProject } from "@/src/store";
import { colors, spacing, radius, font, ASPECTS } from "@/src/theme";

const SCREEN_W = Dimensions.get("window").width;
const MAX_W = SCREEN_W - spacing.xl * 2;
const MAX_H = 420;
const MAX_ZOOM = 4;

async function toFileUri(dataUri: string): Promise<string> {
  if (Platform.OS === "web" || !dataUri.startsWith("data:")) return dataUri;
  const b64 = dataUri.split(",")[1];
  const path = `${LegacyFS.cacheDirectory}crop_src_${Date.now()}.jpg`;
  await LegacyFS.writeAsStringAsync(path, b64, { encoding: LegacyFS.EncodingType.Base64 });
  return path;
}

export default function Crop() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();
  const [srcUri, setSrcUri] = useState("");
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const [aspectKey, setAspectKey] = useState("3:4");
  const [saving, setSaving] = useState(false);
  const [ready, setReady] = useState(false);

  const pan = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const panRef = useRef({ x: 0, y: 0 });
  const zoom = useRef(new Animated.Value(1)).current;
  const zoomRef = useRef(1);
  const singleRef = useRef({ active: false, sx: 0, sy: 0, vx: 0, vy: 0 });
  const pinchRef = useRef({ active: false, startDist: 1, startZoom: 1 });
  const limitsRef = useRef({ scale: 1, frameW: 0, frameH: 0, baseW: 0, baseH: 0 });

  useEffect(() => {
    const pid = pan.addListener((v) => (panRef.current = v));
    const zid = zoom.addListener((v) => (zoomRef.current = v.value));
    return () => { pan.removeListener(pid); zoom.removeListener(zid); };
  }, [pan, zoom]);

  useEffect(() => {
    (async () => {
      if (!project) { setTimeout(() => router.replace("/(tabs)"), 0); return; }
      try {
        const file = await toFileUri(project.current);
        const info = await ImageManipulator.manipulateAsync(file, [], {});
        setSrcUri(info.uri);
        setDims({ w: info.width, h: info.height });
      } catch {
        setSrcUri(project.current);
        setDims({ w: 1024, h: 1024 });
      } finally {
        setReady(true);
      }
    })();
  }, [project, router]);

  const aspect = ASPECTS.find((a) => a.key === aspectKey)!;
  let frameW = MAX_W, frameH = MAX_W / aspect.ratio;
  if (frameH > MAX_H) { frameH = MAX_H; frameW = MAX_H * aspect.ratio; }
  if (frameW > MAX_W) { frameW = MAX_W; frameH = MAX_W / aspect.ratio; }

  let scale = 1, baseW = frameW, baseH = frameH;
  if (dims) {
    scale = Math.max(frameW / dims.w, frameH / dims.h);
    baseW = dims.w * scale; baseH = dims.h * scale;
  }
  limitsRef.current = { scale, frameW, frameH, baseW, baseH };

  const clamp = (v: number, m: number) => Math.max(-m, Math.min(m, v));
  const maxT = (z: number) => {
    const { baseW, baseH, frameW, frameH } = limitsRef.current;
    return { mtx: Math.max(0, (baseW * z - frameW) / 2), mty: Math.max(0, (baseH * z - frameH) / 2) };
  };
  const dist = (t: any[]) => Math.hypot(t[0].pageX - t[1].pageX, t[0].pageY - t[1].pageY);
  const clampCurrentPan = () => {
    const { mtx, mty } = maxT(zoomRef.current);
    pan.setValue({ x: clamp(panRef.current.x, mtx), y: clamp(panRef.current.y, mty) });
  };
  const beginPan = (t: any) => { singleRef.current = { active: true, sx: t.pageX, sy: t.pageY, vx: panRef.current.x, vy: panRef.current.y }; };
  const beginPinch = (touches: any[]) => { pinchRef.current = { active: true, startDist: dist(touches) || 1, startZoom: zoomRef.current }; singleRef.current.active = false; };

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (evt) => {
        const t = evt.nativeEvent.touches;
        if (t.length >= 2) beginPinch(t as any);
        else if (t.length === 1) beginPan(t[0]);
      },
      onPanResponderMove: (evt) => {
        const t = evt.nativeEvent.touches;
        if (t.length >= 2) {
          if (!pinchRef.current.active) beginPinch(t as any);
          let z = pinchRef.current.startZoom * (dist(t as any) / pinchRef.current.startDist);
          z = Math.max(1, Math.min(MAX_ZOOM, z));
          zoom.setValue(z); zoomRef.current = z;
          clampCurrentPan();
        } else if (t.length === 1) {
          if (pinchRef.current.active) { pinchRef.current.active = false; beginPan(t[0]); }
          else if (!singleRef.current.active) beginPan(t[0]);
          const { sx, sy, vx, vy } = singleRef.current;
          const { mtx, mty } = maxT(zoomRef.current);
          pan.setValue({ x: clamp(vx + (t[0].pageX - sx), mtx), y: clamp(vy + (t[0].pageY - sy), mty) });
        }
      },
      onPanResponderRelease: () => { pinchRef.current.active = false; singleRef.current.active = false; },
      onPanResponderTerminate: () => { pinchRef.current.active = false; singleRef.current.active = false; },
    })
  ).current;

  const selectAspect = (k: string) => {
    Haptics.selectionAsync();
    pan.setValue({ x: 0, y: 0 }); panRef.current = { x: 0, y: 0 };
    zoom.setValue(1); zoomRef.current = 1;
    setAspectKey(k);
  };

  const resetView = () => {
    Haptics.selectionAsync();
    pan.setValue({ x: 0, y: 0 }); panRef.current = { x: 0, y: 0 };
    zoom.setValue(1); zoomRef.current = 1;
  };

  const confirm = async () => {
    if (!dims) return;
    setSaving(true);
    try {
      const { scale, frameW, frameH, baseW, baseH } = limitsRef.current;
      const z = zoomRef.current;
      const effScale = scale * z;
      const dispW = baseW * z, dispH = baseH * z;
      const tx = panRef.current.x, ty = panRef.current.y;
      const x0 = (frameW - dispW) / 2 + tx;
      const y0 = (frameH - dispH) / 2 + ty;
      let originX = (0 - x0) / effScale;
      let originY = (0 - y0) / effScale;
      const cw = frameW / effScale;
      const ch = frameH / effScale;
      originX = Math.max(0, Math.min(originX, dims.w - cw));
      originY = Math.max(0, Math.min(originY, dims.h - ch));
      const res = await ImageManipulator.manipulateAsync(
        srcUri,
        [{ crop: { originX: Math.round(originX), originY: Math.round(originY), width: Math.round(cw), height: Math.round(ch) } }],
        { base64: true, compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
      );
      const dataUri = res.base64 ? `data:image/jpeg;base64,${res.base64}` : res.uri;
      updateProject({ current: dataUri });
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      router.push("/editor");
    } catch {
      router.push("/editor");
    } finally {
      setSaving(false);
    }
  };

  const skip = () => router.push("/editor");

  return (
    <View style={styles.root}>
      <FlowHeader title="Crop" step="Adjust framing" />
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.stage}>
          {!ready ? (
            <ActivityIndicator size="large" color={colors.onSurface} />
          ) : (
            <View style={[styles.frame, { width: frameW, height: frameH }]} {...panResponder.panHandlers} testID="crop-frame">
              <Animated.Image
                source={{ uri: srcUri }}
                style={{
                  width: Animated.multiply(zoom, baseW),
                  height: Animated.multiply(zoom, baseH),
                  transform: [{ translateX: pan.x }, { translateY: pan.y }],
                }}
                resizeMode="cover"
              />
              <View pointerEvents="none" style={styles.gridOverlay}>
                <View style={styles.gridV} /><View style={[styles.gridV, { left: "66%" }]} />
                <View style={styles.gridH} /><View style={[styles.gridH, { top: "66%" }]} />
              </View>
            </View>
          )}
        </View>
        <View style={styles.hintRow}>
          <Text style={styles.hint}>Pinch to zoom · drag to reposition</Text>
          <Pressable testID="crop-reset-button" hitSlop={8} onPress={resetView}><Text style={styles.reset}>Reset</Text></Pressable>
        </View>

        <Text style={styles.sectionLabel}>Aspect ratio</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {ASPECTS.map((a) => (
            <Pressable key={a.key} testID={`aspect-${a.key}`} style={[styles.chip, aspectKey === a.key && styles.chipActive]} onPress={() => selectAspect(a.key)}>
              <Text style={[styles.chipText, aspectKey === a.key && styles.chipTextActive]}>{a.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable testID="crop-skip-button" style={styles.skip} onPress={skip}>
          <Text style={styles.skipText}>Skip</Text>
        </Pressable>
        <Pressable testID="crop-apply-button" style={styles.cta} onPress={confirm} disabled={saving || !ready}>
          {saving ? <ActivityIndicator color={colors.onBrand} /> : <Text style={styles.ctaText}>Apply Crop</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  stage: { minHeight: 300, alignItems: "center", justifyContent: "center" },
  frame: { overflow: "hidden", backgroundColor: colors.surfaceTertiary, borderRadius: radius.sm },
  gridOverlay: { ...StyleSheet.absoluteFillObject },
  gridV: { position: "absolute", left: "33%", top: 0, bottom: 0, width: 1, backgroundColor: "rgba(255,255,255,0.4)" },
  gridH: { position: "absolute", top: "33%", left: 0, right: 0, height: 1, backgroundColor: "rgba(255,255,255,0.4)" },
  hintRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hint: { fontSize: font.base, color: colors.onSurfaceTertiary },
  reset: { fontSize: font.base, color: colors.brandSecondary, fontWeight: "700" },
  sectionLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: 1 },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  chip: { flexShrink: 0, height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.base, color: colors.onSurface, fontWeight: "500" },
  chipTextActive: { color: colors.onBrand },
  ctaBar: { flexDirection: "row", gap: spacing.md, paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  skip: { height: 56, paddingHorizontal: spacing.xl, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center" },
  skipText: { fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
  cta: { flex: 1, backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
