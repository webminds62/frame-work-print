import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import { getProject } from "@/src/store";
import { colors, spacing, radius, font, serif, PANELS } from "@/src/theme";

export default function Product() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();

  if (!project) return null;
  const panelCount = PANELS.find((panel) => panel.key === project.panel_key)?.count || 1;
  const visualization = project.room_preview || project.current;
  const printPrice = project.price || (project.printful_retail_price || 0) * panelCount;
  const checkout = () => {
    if (!project.printful_variant_id) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push("/checkout");
  };

  return (
    <View style={styles.root}>
      <FlowHeader title="Review Your Print" step="Step 4 of 4" />
      <ScrollView contentContainerStyle={styles.body}>
        <View>
          <Text style={styles.sectionLabel}>Artwork visualization</Text>
          <Text style={styles.sectionHelp}>Room previews help with scale; the product choice below controls fulfillment.</Text>
        </View>
        <Image source={{ uri: visualization }} style={styles.hero} contentFit="cover" testID="product-hero" />

        <View>
          <Text style={styles.sectionLabel}>Your Printful product</Text>
          <Text style={styles.sectionHelp}>Official catalog product that will be sent to fulfillment</Text>
        </View>
        <View style={styles.productCard} testID="exact-printful-product">
          {!!project.printful_variant_image && (
            <Image source={{ uri: project.printful_variant_image }} style={styles.productImage} contentFit="cover" />
          )}
          <View style={styles.productBody}>
            <View style={styles.verifiedRow}>
              <Feather name="check-circle" size={16} color={colors.success} />
              <Text style={styles.verifiedText}>Exact catalog variant selected</Text>
            </View>
            <Text style={styles.productName}>{project.printful_variant_name || "Printful wall art"}</Text>
            <Text style={styles.variantId}>Printful variant #{project.printful_variant_id}</Text>
            <View style={styles.details}>
              <Detail label="Product" value={project.printful_variant_name || "Printful wall art"} />
              <Detail label="Size" value={(project.size || "").replace("x", '" × ') + '"'} />
              <Detail label="Finish" value={(project.frame || "").replace("red_oak", "Red Oak").replace("brown", "Brown").replace("black", "Black").replace("white", "White").replace("none", "Unframed")} />
              <Detail label="Quantity" value={String(panelCount)} />
            </View>
          </View>
        </View>

        <View style={styles.fulfillmentNote}>
          <Feather name="shield" size={18} color={colors.brandSecondary} />
          <Text style={styles.fulfillmentText}>Checkout preserves variant #{project.printful_variant_id}; the server rejects any mismatched product, size, or finish.</Text>
        </View>
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <View>
          <Text style={styles.priceLabel}>Print price</Text>
          <Text style={styles.price} testID="product-price">${printPrice.toFixed(2)}</Text>
          <Text style={styles.shipping}>Shipping calculated next</Text>
        </View>
        <Pressable testID="checkout-button" style={[styles.cta, !project.printful_variant_id && styles.disabled]}
          onPress={checkout} disabled={!project.printful_variant_id}>
          <Text style={styles.ctaText}>Checkout</Text>
        </Pressable>
      </View>
    </View>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <View style={styles.detailRow}><Text style={styles.detailLabel}>{label}</Text><Text style={styles.detailValue}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  sectionLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: 1 },
  sectionHelp: { fontSize: font.sm, lineHeight: 18, color: colors.muted, marginTop: spacing.xs },
  hero: { width: "100%", aspectRatio: 4 / 3, borderRadius: radius.lg, backgroundColor: colors.surfaceTertiary },
  productCard: { borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surfaceSecondary, overflow: "hidden" },
  productImage: { width: "100%", height: 210, backgroundColor: colors.surfaceTertiary },
  productBody: { padding: spacing.lg, gap: spacing.sm },
  verifiedRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  verifiedText: { fontSize: font.sm, color: colors.success, fontWeight: "700" },
  productName: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface, marginTop: spacing.xs },
  variantId: { fontSize: font.sm, color: colors.muted },
  details: { marginTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  detailRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  detailLabel: { fontSize: font.base, color: colors.onSurfaceTertiary },
  detailValue: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, textTransform: "capitalize" },
  fulfillmentNote: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  fulfillmentText: { flex: 1, fontSize: font.sm, lineHeight: 18, color: colors.onSurfaceTertiary },
  ctaBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  priceLabel: { fontSize: font.sm, color: colors.muted },
  price: { fontSize: font["2xl"], fontFamily: serif, color: colors.onSurface },
  shipping: { fontSize: 10, color: colors.muted },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing["2xl"] },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  disabled: { opacity: 0.4 },
});
