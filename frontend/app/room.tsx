import { useState, useEffect } from "react";
import { View, Text, StyleSheet, Pressable, ScrollView, ActivityIndicator } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import FlowHeader from "@/src/components/FlowHeader";
import { api } from "@/src/api";
import { shareImage } from "@/src/utils/share";
import { getProject, updateProject } from "@/src/store";
import { colors, spacing, radius, font, ROOMS, SIZE_RECOMMENDATION, SIZES, PANELS } from "@/src/theme";

export default function Room() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();
  const [room, setRoom] = useState(project?.room || "living_room");
  const [preview, setPreview] = useState(project?.room_preview || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => { if (!project) setTimeout(() => router.replace("/(tabs)"), 0); }, [project, router]);
  if (!project) return null;

  const recommendedSize = SIZES.find((s) => s.key === SIZE_RECOMMENDATION[room])?.label;
  const panelCount = PANELS.find((p) => p.key === project.panel_key)?.count || 1;

  const generate = async () => {
    setLoading(true); setError(""); setNotice("");
    try {
      const res = await api.roomPreview(project.current, room, project.frame, project.material, panelCount);
      setPreview(res.image_base64);
      setNotice(res.notices?.[0] ?? "");
      updateProject({ room, room_preview: res.image_base64 });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) { setError(e.message || "Failed to generate room preview"); }
    finally { setLoading(false); }
  };

  const cont = () => {
    updateProject({ room, room_preview: preview });
    router.push("/product");
  };

  return (
    <View style={styles.root}>
      <FlowHeader title="Preview in Room" step="Step 3 of 4" />
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.canvas}>
          {preview ? (
            <Image source={{ uri: preview }} style={styles.img} contentFit="cover" transition={200} testID="room-preview-img" />
          ) : (
            <View style={styles.placeholder}>
              <Image source={{ uri: project.current }} style={styles.artThumb} contentFit="cover" />
              <Text style={styles.placeholderText}>See your art on a real wall</Text>
            </View>
          )}
          {loading && (
            <View style={styles.loadingOverlay}>
              <ActivityIndicator size="large" color={colors.onSurfaceInverse} />
              <Text style={styles.loadingText}>Styling your room…</Text>
            </View>
          )}
        </View>

        <Text style={styles.sectionLabel}>Room</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {ROOMS.map((r) => (
            <Pressable key={r.key} testID={`room-${r.key}`} style={[styles.chip, room === r.key && styles.chipActive]} onPress={() => { Haptics.selectionAsync(); setRoom(r.key); }}>
              <Text style={[styles.chipText, room === r.key && styles.chipTextActive]}>{r.label}</Text>
            </Pressable>
          ))}
        </ScrollView>

        {!!recommendedSize && (
          <Text style={styles.tip}>Recommended for this room: {recommendedSize}</Text>
        )}
        {!!error && <Text style={styles.error} testID="room-error">{error}</Text>}
        {!!notice && <Text style={styles.notice} testID="room-mode-notice">{notice}</Text>}

        <Pressable testID="generate-room-button" style={styles.generateBtn} onPress={generate} disabled={loading}>
          <Text style={styles.generateText}>{preview ? "Regenerate Preview" : "Generate Room Preview"}</Text>
        </Pressable>
        {!!preview && (
          <Pressable testID="share-room-button" style={styles.shareBtn} onPress={() => shareImage(preview, "frameworks-room.jpg")}>
            <Feather name="share" size={18} color={colors.brandSecondary} />
            <Text style={styles.shareText}>Save / Share preview</Text>
          </Pressable>
        )}
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable testID="room-continue-button" style={styles.cta} onPress={cont}>
          <Text style={styles.ctaText}>Continue to Order</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  canvas: { aspectRatio: 4 / 3, borderRadius: radius.lg, overflow: "hidden", backgroundColor: colors.surfaceTertiary },
  img: { width: "100%", height: "100%" },
  placeholder: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  artThumb: { width: 90, height: 110, borderRadius: radius.sm, borderWidth: 6, borderColor: colors.surfaceSecondary },
  placeholderText: { color: colors.onSurfaceTertiary, fontSize: font.base },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(28,27,26,0.55)", alignItems: "center", justifyContent: "center", gap: spacing.md },
  loadingText: { color: colors.onSurfaceInverse, fontSize: font.base },
  sectionLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: 1 },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  chip: { flexShrink: 0, height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.base, color: colors.onSurface, fontWeight: "500" },
  chipTextActive: { color: colors.onBrand },
  tip: { fontSize: font.base, color: colors.brandSecondary, fontWeight: "600" },
  error: { color: colors.error, fontSize: font.base },
  notice: { color: colors.success, fontSize: font.sm, lineHeight: 18 },
  generateBtn: { height: 52, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  generateText: { fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
  shareBtn: { flexDirection: "row", gap: spacing.sm, height: 48, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  shareText: { fontSize: font.base, fontWeight: "700", color: colors.brandSecondary },
  ctaBar: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
