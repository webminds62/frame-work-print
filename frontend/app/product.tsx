import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import MultiPanelPreview from "@/src/components/MultiPanelPreview";
import { getProject } from "@/src/store";
import { TIER_META, type CollectionTier } from "@/src/catalog/store_skus";
import { colors, spacing, radius, font, serif, PANELS } from "@/src/theme";

export default function Product() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();

  if (!project) return null;

  const panelCount = PANELS.find((panel) => panel.key === project.panel_key)?.count || 1;
  const visualization = project.room_preview || project.current;
  const printPrice = project.price || 0;
  const ready = !!(project.store_variant_id || project.store_family_name || printPrice > 0);
  const tierLabel = project.store_tier
    ? TIER_META[project.store_tier as CollectionTier]?.label || ""
    : "";
  const frameName = project.store_family_name || project.printful_variant_name || "Your frame";
  const frameImage = project.store_image || project.printful_variant_image || "";

  const checkout = () => {
    if (!ready) {
      router.push("/(tabs)/store");
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push("/checkout");
  };

  return (
    <View style={styles.root}>
      <FlowHeader title="Review Your Print" step="Step 4 of 4" />
      <ScrollView contentContainerStyle={styles.body}>
        <View>
          <Text style={styles.sectionLabel}>Artwork visualization</Text>
          {project.room_preview ? (
            <Image source={{ uri: visualization }} style={styles.hero} contentFit="cover" />
          ) : (
            <View style={styles.previewWrap}>
              <MultiPanelPreview
                image={project.current}
                count={panelCount}
                frameKey={project.frame || "wood"}
                material={project.material === "canvas" ? "canvas" : "poster"}
                width={300}
                height={280}
              />
            </View>
          )}
        </View>

        <Text style={styles.sectionLabel}>Your gallery frame</Text>
        <View style={styles.productCard} testID="store-product-card">
          {!!frameImage && (
            <Image source={{ uri: frameImage }} style={styles.productImage} contentFit="cover" />
          )}
          <View style={{ flex: 1, gap: 4 }}>
            {!!tierLabel && <Text style={styles.tier}>{tierLabel}</Text>}
            <Text style={styles.productName}>{frameName}</Text>
            <Text style={styles.metaLine}>
              {project.size}
              {panelCount > 1 ? ` · ${panelCount}-panel` : ""}
              {project.has_mat ? " · Museum mat" : ""}
            </Text>
            <Text style={styles.price}>${printPrice.toFixed(2)}</Text>
          </View>
        </View>

        <Pressable testID="change-frame-review" style={styles.linkRow} onPress={() => router.push("/(tabs)/store")}>
          <Feather name="aperture" size={16} color={colors.brandSecondary} />
          <Text style={styles.linkText}>Change frame in Store</Text>
        </Pressable>

        <View style={styles.note}>
          <Feather name="info" size={16} color={colors.success} />
          <Text style={styles.noteText}>
            Frame chosen from the Frame Works gallery. Room preview uses your photo without altering the print file.
          </Text>
        </View>
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable
          testID="checkout-button"
          style={[styles.cta, !ready && styles.disabled]}
          onPress={checkout}
          disabled={!ready}
        >
          <Text style={styles.ctaText}>
            {ready ? `Continue to checkout · $${printPrice.toFixed(2)}` : "Pick a frame first"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  sectionLabel: {
    fontSize: font.sm,
    fontWeight: "700",
    color: colors.onSurfaceTertiary,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: spacing.sm,
  },
  hero: { width: "100%", height: 320, borderRadius: radius.lg, backgroundColor: colors.surfaceTertiary },
  previewWrap: { alignItems: "center", paddingVertical: spacing.md },
  productCard: {
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  productImage: { width: 72, height: 90, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  tier: { fontSize: 11, fontWeight: "700", color: colors.success, letterSpacing: 0.8, textTransform: "uppercase" },
  productName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  metaLine: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  price: { fontSize: font.xl, fontWeight: "700", color: colors.onSurface, marginTop: 4 },
  linkRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  linkText: { color: colors.brandSecondary, fontWeight: "600", fontSize: font.base },
  note: {
    flexDirection: "row",
    gap: spacing.sm,
    padding: spacing.md,
    backgroundColor: "rgba(74,93,78,0.08)",
    borderRadius: radius.md,
    alignItems: "flex-start",
  },
  noteText: { flex: 1, fontSize: font.sm, color: colors.onSurfaceTertiary, lineHeight: 18 },
  ctaBar: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  cta: {
    backgroundColor: colors.brand,
    height: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  disabled: { opacity: 0.4 },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
