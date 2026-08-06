import { useState, useEffect } from "react";
import { View, Text, StyleSheet, Pressable, ScrollView, ActivityIndicator } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import { api, type PrintQualityResponse } from "@/src/api";
import { getProject, updateProject } from "@/src/store";
import { colors, spacing, radius, font, STYLES } from "@/src/theme";

export default function StyleScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();
  const [style, setStyle] = useState(project?.style || "gallery");
  const [enhance, setEnhance] = useState(project?.enhance ?? true);
  const [removeBg, setRemoveBg] = useState(project?.remove_bg ?? false);
  const [result, setResult] = useState(project?.current !== project?.original ? project?.current : "");
  const [loading, setLoading] = useState(false);
  const [showBefore, setShowBefore] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [quality, setQuality] = useState<PrintQualityResponse | null>(null);

  useEffect(() => { if (!project) setTimeout(() => router.replace("/(tabs)"), 0); }, [project, router]);
  useEffect(() => {
    if (!project?.original) return;
    let active = true;
    api.printQuality(project.original)
      .then((value) => { if (active) setQuality(value); })
      .catch(() => { if (active) setQuality(null); });
    return () => { active = false; };
  }, [project?.original]);
  if (!project) return null;

  const apply = async () => {
    setLoading(true); setError(""); setNotice("");
    try {
      const res = await api.transform(project.original, style, enhance, removeBg);
      setResult(res.image_base64);
      setNotice(res.notices?.[0] ?? "");
      updateProject({ current: res.image_base64, style, enhance, remove_bg: removeBg });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) { setError(e.message || "Failed to generate"); }
    finally { setLoading(false); }
  };

  const displayed = showBefore || !result ? project.original : result;

  return (
    <View style={styles.root}>
      <FlowHeader title="Choose a Style" step="Step 1 of 4" />
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.canvas}>
          <Image source={{ uri: displayed }} style={styles.img} contentFit="cover" transition={200} testID="style-preview" />
          {loading && (
            <View style={styles.loadingOverlay}>
              <ActivityIndicator size="large" color={colors.onSurfaceInverse} />
              <Text style={styles.loadingText}>Creating your artwork…</Text>
            </View>
          )}
          {!!result && !loading && (
            <Pressable testID="before-after-toggle" style={styles.baToggle} onPressIn={() => setShowBefore(true)} onPressOut={() => setShowBefore(false)}>
              <Feather name="eye" size={16} color={colors.onSurfaceInverse} />
              <Text style={styles.baText}>Hold: Before</Text>
            </Pressable>
          )}
        </View>

        {!!quality && (
          <View style={styles.qualityCard} testID="print-quality-card">
            <View style={styles.qualityHeader}>
              <Text style={styles.qualityTitle}>Print quality</Text>
              <Text style={styles.qualityScore}>{quality.rating} · {quality.score}/100</Text>
            </View>
            <Text style={styles.qualityMeta}>{quality.width} × {quality.height} pixels</Text>
            <Text style={styles.qualityMeta}>
              {quality.recommended_sizes.length
                ? `Recommended sizes: ${quality.recommended_sizes.join(", ")}`
                : quality.issues[0]}
            </Text>
          </View>
        )}

        <Text style={styles.sectionLabel}>Art style</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {STYLES.map((s) => (
            <Pressable
              key={s.key}
              testID={`style-${s.key}`}
              style={[styles.chip, style === s.key && styles.chipActive]}
              onPress={() => { Haptics.selectionAsync(); setStyle(s.key); }}
            >
              <Text style={[styles.chipText, style === s.key && styles.chipTextActive]}>{s.label}</Text>
            </Pressable>
          ))}
        </ScrollView>

        <View style={styles.toggleRow}>
          <Pressable testID="toggle-enhance" style={styles.toggle} onPress={() => setEnhance((v) => !v)}>
            <Feather name={enhance ? "check-square" : "square"} size={20} color={colors.onSurface} />
            <Text style={styles.toggleText}>AI enhance (light, sharpness, color)</Text>
          </Pressable>
          <Pressable testID="toggle-removebg" style={styles.toggle} onPress={() => setRemoveBg((v) => !v)}>
            <Feather name={removeBg ? "check-square" : "square"} size={20} color={colors.onSurface} />
            <Text style={styles.toggleText}>Clean up / remove background</Text>
          </Pressable>
        </View>

        {!!error && <Text style={styles.error} testID="style-error">{error}</Text>}
        {!!notice && <Text style={styles.notice} testID="ai-mode-notice">{notice}</Text>}

        <Pressable testID="apply-style-button" style={styles.applyBtn} onPress={apply} disabled={loading}>
          <Feather name="zap" size={18} color={colors.onSurface} />
          <Text style={styles.applyText}>{result ? "Regenerate" : "Apply AI Style"}</Text>
        </Pressable>
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable
          testID="style-continue-button"
          style={[styles.cta, !result && styles.ctaDisabled]}
          onPress={() => result && router.push("/crop")}
          disabled={!result}
        >
          <Text style={styles.ctaText}>Continue</Text>
        </Pressable>
        <Pressable
          testID="style-skip-button"
          style={styles.skipBtn}
          onPress={() => {
            updateProject({ current: project.original, enhance: false, remove_bg: false });
            router.push("/crop");
          }}
        >
          <Text style={styles.skipText}>{result ? "Continue with original instead" : "Skip AI — use original photo"}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  canvas: { aspectRatio: 1, borderRadius: radius.lg, overflow: "hidden", backgroundColor: colors.surfaceTertiary },
  img: { width: "100%", height: "100%" },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(28,27,26,0.55)", alignItems: "center", justifyContent: "center", gap: spacing.md },
  loadingText: { color: colors.onSurfaceInverse, fontSize: font.base },
  baToggle: { position: "absolute", bottom: spacing.md, right: spacing.md, flexDirection: "row", gap: 6, backgroundColor: "rgba(28,27,26,0.7)", paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill, alignItems: "center" },
  baText: { color: colors.onSurfaceInverse, fontSize: font.sm, fontWeight: "600" },
  sectionLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: 1 },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  chip: { flexShrink: 0, height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.base, color: colors.onSurface, fontWeight: "500" },
  chipTextActive: { color: colors.onBrand },
  toggleRow: { gap: spacing.md },
  toggle: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  toggleText: { fontSize: font.base, color: colors.onSurface },
  error: { color: colors.error, fontSize: font.base },
  notice: { color: colors.success, fontSize: font.sm, lineHeight: 18 },
  qualityCard: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.xs },
  qualityHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.md },
  qualityTitle: { color: colors.onSurface, fontSize: font.base, fontWeight: "700" },
  qualityScore: { color: colors.success, fontSize: font.sm, fontWeight: "700" },
  qualityMeta: { color: colors.onSurfaceTertiary, fontSize: font.sm, lineHeight: 18 },
  applyBtn: { flexDirection: "row", gap: spacing.sm, height: 52, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  applyText: { fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
  ctaBar: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  ctaDisabled: { opacity: 0.4 },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  skipBtn: { height: 44, alignItems: "center", justifyContent: "center", marginTop: spacing.sm },
  skipText: { color: colors.onSurfaceTertiary, fontSize: font.base, fontWeight: "600", textDecorationLine: "underline" },
});
