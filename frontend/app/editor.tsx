import { useEffect } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import MultiPanelPreview from "@/src/components/MultiPanelPreview";
import { getProject } from "@/src/store";
import { colors, spacing, radius, font, serif, PANELS } from "@/src/theme";
import { TIER_META, type CollectionTier } from "@/src/catalog/store_skus";

/**
 * Confirm step after crop. Printful catalog removed — frame comes from Store.
 * If somehow opened without a store selection, send user to Store.
 */
export default function EditorConfirm() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();

  useEffect(() => {
    if (!project) {
      setTimeout(() => router.replace("/(tabs)/store"), 0);
      return;
    }
    // Store already chose the frame — go straight to room preview.
    if (project.store_variant_id || project.store_family_name) {
      setTimeout(() => router.replace("/room"), 0);
    }
  }, [project, router]);

  if (!project) {
    return (
      <View style={[styles.root, styles.center]}>
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  // Auto-redirect path while store selection exists
  if (project.store_variant_id || project.store_family_name) {
    return (
      <View style={[styles.root, styles.center]} testID="editor-redirect-room">
        <ActivityIndicator color={colors.brand} />
        <Text style={styles.redirectText}>Opening room preview…</Text>
      </View>
    );
  }

  const panelCount = PANELS.find((p) => p.key === project.panel_key)?.count || 1;
  const tierLabel = project.store_tier
    ? TIER_META[project.store_tier as CollectionTier]?.label
    : "";

  return (
    <View style={styles.root}>
      <FlowHeader title="Your frame" step="From the gallery" />
      <View style={styles.body}>
        <MultiPanelPreview
          image={project.current}
          count={panelCount}
          frameKey={project.frame || "wood"}
          material={project.material === "canvas" ? "canvas" : "poster"}
          width={300}
          height={280}
        />
        <Text style={styles.name}>{project.store_family_name || "Selected frame"}</Text>
        {!!tierLabel && <Text style={styles.tier}>{tierLabel}</Text>}
        <Text style={styles.meta}>
          {project.size} · ${Number(project.price || 0).toFixed(0)}
        </Text>
        {!!project.store_image && (
          <Image source={{ uri: project.store_image }} style={styles.thumb} contentFit="cover" />
        )}
      </View>
      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable
          testID="editor-to-store"
          style={styles.secondary}
          onPress={() => router.push("/(tabs)/store")}
        >
          <Text style={styles.secondaryText}>Change frame</Text>
        </Pressable>
        <Pressable
          testID="editor-to-room"
          style={styles.cta}
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
            router.push("/room");
          }}
        >
          <Text style={styles.ctaText}>Preview in room</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center", gap: spacing.md },
  redirectText: { color: colors.onSurfaceTertiary, fontSize: font.base },
  body: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.sm },
  name: { fontSize: font["2xl"], fontFamily: serif, color: colors.onSurface, textAlign: "center", marginTop: spacing.lg },
  tier: { fontSize: font.sm, fontWeight: "700", color: colors.success, letterSpacing: 1, textTransform: "uppercase" },
  meta: { fontSize: font.base, color: colors.onSurfaceTertiary },
  thumb: { width: 72, height: 90, borderRadius: radius.sm, marginTop: spacing.md },
  ctaBar: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  secondary: {
    flex: 1,
    height: 56,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryText: { fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
  cta: {
    flex: 1.4,
    height: 56,
    borderRadius: radius.md,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaText: { fontSize: font.lg, fontWeight: "600", color: colors.onBrand },
});
