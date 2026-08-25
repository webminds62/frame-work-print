import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import FlowHeader from "@/src/components/FlowHeader";
import MultiPanelPreview from "@/src/components/MultiPanelPreview";
import { api } from "@/src/api";
import { shareImage } from "@/src/utils/share";
import { getProject, updateProject } from "@/src/store";
import { TIER_META, type CollectionTier } from "@/src/catalog/store_skus";
import {
  colors,
  spacing,
  radius,
  font,
  serif,
  ROOMS,
  SIZE_RECOMMENDATION,
  SIZES,
  PANELS,
} from "@/src/theme";

async function softHaptic(success = false) {
  try {
    if (Platform.OS === "web") return;
    if (success) {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } else {
      await Haptics.selectionAsync();
    }
  } catch {
    /* ignore */
  }
}

export default function Room() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();
  const [room, setRoom] = useState(project?.room || "living_room");
  const [preview, setPreview] = useState(project?.room_preview || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const autoKey = useRef("");

  useEffect(() => {
    if (!project) setTimeout(() => router.replace("/(tabs)"), 0);
  }, [project, router]);

  const panelCount = PANELS.find((p) => p.key === project?.panel_key)?.count || 1;
  const frameKey = project?.frame || "wood";
  const material = project?.material === "canvas" ? "canvas" : project?.material === "metal" ? "metal" : "poster";
  const frameName = project?.store_family_name || "Your frame";
  const tierLabel = project?.store_tier
    ? TIER_META[project.store_tier as CollectionTier]?.label || ""
    : "";
  const sizeLabel =
    SIZES.find((s) => s.key === project?.size)?.label || project?.size || "";
  const recommendedSize = SIZES.find((s) => s.key === SIZE_RECOMMENDATION[room])?.label;

  const generate = useCallback(
    async (roomKey: string, opts?: { silent?: boolean }) => {
      if (!project?.current) return;
      setLoading(true);
      setError("");
      if (!opts?.silent) setNotice("");
      try {
        const res = await api.roomPreview(
          project.current,
          roomKey,
          frameKey,
          material,
          panelCount,
        );
        setPreview(res.image_base64);
        setNotice(
          res.notices?.[0] ||
            `${frameName} shown on the wall — this is how it will look at home.`,
        );
        updateProject({ room: roomKey, room_preview: res.image_base64 });
        await softHaptic(true);
      } catch (e: any) {
        setError(e?.message || "Failed to generate room preview");
      } finally {
        setLoading(false);
      }
    },
    [project?.current, frameKey, material, panelCount, frameName],
  );

  // Auto-generate when landing on this screen or when room / frame context changes
  useEffect(() => {
    if (!project?.current) return;
    const key = `${project.current.slice(0, 64)}|${room}|${frameKey}|${panelCount}`;
    if (autoKey.current === key && preview) return;
    autoKey.current = key;
    generate(room, { silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.current, room, frameKey, panelCount]);

  if (!project) return null;

  const pickRoom = async (key: string) => {
    await softHaptic(false);
    setRoom(key);
    setPreview(""); // show loading state for new room
  };

  const cont = () => {
    updateProject({ room, room_preview: preview || project.room_preview || "" });
    router.push("/product");
  };

  return (
    <View style={styles.root} testID="room-screen">
      <FlowHeader title="See it on your wall" step="Before you buy" />
      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
        {/* Selected frame recap */}
        <View style={styles.frameRecap} testID="room-frame-recap">
          <View style={styles.frameRecapIcon}>
            <Feather name="aperture" size={16} color={colors.success} />
          </View>
          <View style={{ flex: 1 }}>
            {!!tierLabel && <Text style={styles.tier}>{tierLabel}</Text>}
            <Text style={styles.frameTitle} numberOfLines={1}>
              {frameName}
            </Text>
            <Text style={styles.frameMeta}>
              {sizeLabel}
              {panelCount > 1 ? ` · ${panelCount}-panel` : ""}
              {project.has_mat ? " · Museum mat" : ""}
              {project.price ? ` · $${Number(project.price).toFixed(0)}` : ""}
            </Text>
          </View>
          <Pressable onPress={() => router.push("/(tabs)/store")} hitSlop={8}>
            <Text style={styles.changeLink}>Change</Text>
          </Pressable>
        </View>

        <View style={styles.canvas}>
          {preview ? (
            <Image
              source={{ uri: preview }}
              style={styles.img}
              contentFit="cover"
              transition={200}
              testID="room-preview-img"
            />
          ) : (
            <View style={styles.placeholder}>
              <MultiPanelPreview
                image={project.current}
                count={panelCount}
                frameKey={frameKey}
                material={material === "metal" ? "canvas" : material}
                width={200}
                height={180}
              />
              <Text style={styles.placeholderText}>
                {loading ? "Placing your frame on the wall…" : "Preparing room preview…"}
              </Text>
            </View>
          )}
          {loading && (
            <View style={styles.loadingOverlay}>
              <ActivityIndicator size="large" color={colors.onSurfaceInverse} />
              <Text style={styles.loadingText}>Showing {frameName} in this room…</Text>
            </View>
          )}
        </View>

        <Text style={styles.sectionLabel}>Room</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
        >
          {ROOMS.map((r) => (
            <Pressable
              key={r.key}
              testID={`room-${r.key}`}
              style={[styles.chip, room === r.key && styles.chipActive]}
              onPress={() => pickRoom(r.key)}
            >
              <Text style={[styles.chipText, room === r.key && styles.chipTextActive]}>
                {r.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {!!recommendedSize && (
          <Text style={styles.tip}>Suggested size for this room: {recommendedSize}</Text>
        )}
        {!!error && (
          <Text style={styles.error} testID="room-error">
            {error}
          </Text>
        )}
        {!!notice && !error && (
          <Text style={styles.notice} testID="room-mode-notice">
            {notice}
          </Text>
        )}

        <Pressable
          testID="generate-room-button"
          style={styles.generateBtn}
          onPress={() => generate(room)}
          disabled={loading}
        >
          <Feather name="refresh-cw" size={16} color={colors.onSurface} />
          <Text style={styles.generateText}>
            {preview ? "Refresh wall preview" : "Generate wall preview"}
          </Text>
        </Pressable>

        {!!preview && (
          <Pressable
            testID="share-room-button"
            style={styles.shareBtn}
            onPress={() => shareImage(preview, "frameworks-room.jpg")}
          >
            <Feather name="share" size={18} color={colors.brandSecondary} />
            <Text style={styles.shareText}>Save / Share preview</Text>
          </Pressable>
        )}
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable
          testID="room-continue-button"
          style={[styles.cta, !preview && !loading && styles.ctaMuted]}
          onPress={cont}
        >
          <Text style={styles.ctaText}>
            {preview ? "Continue to order" : loading ? "Preparing preview…" : "Continue"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg, paddingBottom: spacing["2xl"] },
  frameRecap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  frameRecapIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(74,93,78,0.12)",
    alignItems: "center",
    justifyContent: "center",
  },
  tier: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.success,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  frameTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  frameMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  changeLink: { color: colors.brandSecondary, fontWeight: "700", fontSize: font.sm },
  canvas: {
    aspectRatio: 4 / 3,
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surfaceTertiary,
  },
  img: { width: "100%", height: "100%" },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.lg,
  },
  placeholderText: { color: colors.onSurfaceTertiary, fontSize: font.base, textAlign: "center" },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(28,27,26,0.45)",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  loadingText: {
    color: colors.onSurfaceInverse,
    fontSize: font.base,
    textAlign: "center",
    fontWeight: "600",
  },
  sectionLabel: {
    fontSize: font.sm,
    fontWeight: "700",
    color: colors.onSurfaceTertiary,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  chip: {
    flexShrink: 0,
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceSecondary,
  },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.base, color: colors.onSurface, fontWeight: "500" },
  chipTextActive: { color: colors.onBrand },
  tip: { fontSize: font.base, color: colors.brandSecondary, fontWeight: "600" },
  error: { color: colors.error, fontSize: font.base },
  notice: { color: colors.success, fontSize: font.sm, lineHeight: 18 },
  generateBtn: {
    height: 52,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceSecondary,
    flexDirection: "row",
    gap: spacing.sm,
  },
  generateText: { fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
  shareBtn: {
    flexDirection: "row",
    gap: spacing.sm,
    height: 48,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  shareText: { fontSize: font.base, fontWeight: "700", color: colors.brandSecondary },
  ctaBar: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  cta: {
    backgroundColor: colors.brand,
    height: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaMuted: { opacity: 0.7 },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
