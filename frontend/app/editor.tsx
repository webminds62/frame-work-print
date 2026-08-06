import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import MultiPanelPreview from "@/src/components/MultiPanelPreview";
import { api, PrintfulCatalogResponse, PrintfulCatalogVariant } from "@/src/api";
import { getProject, updateProject } from "@/src/store";
import { colors, spacing, radius, font, PANELS, SIZES } from "@/src/theme";

const PRODUCT_LABELS: Record<number, { title: string; detail: string }> = {
  614: { title: "Framed Canvas", detail: "Floating frame in black, brown, or white" },
  3: { title: "Canvas", detail: "Gallery-wrapped canvas" },
  616: { title: "Thin Canvas", detail: "Slim gallery canvas" },
  2: { title: "Framed Poster", detail: "Matte paper with frame choices" },
  172: { title: "Luster Framed", detail: "Premium photo paper with frame choices" },
  795: { title: "Framed Poster + Mat", detail: "Matte paper with mat and frame" },
  1: { title: "Matte Poster", detail: "Enhanced matte paper, unframed" },
  171: { title: "Luster Poster", detail: "Premium photo paper, unframed" },
  588: { title: "Glossy Metal", detail: "Modern aluminum wall print" },
};
const PREFERRED_FINISH: Record<string, string> = { canvas: "brown", poster: "red_oak" };

function normalizedLegacyFinish(material: string, finish: string) {
  if (finish === "wood") return material === "canvas" ? "brown" : "red_oak";
  return finish || PREFERRED_FINISH[material];
}

export default function Editor() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const project = getProject();
  const initialMaterial = project?.material === "metal" ? "metal" : project?.material === "poster" ? "poster" : "canvas";
  const initialProductId = project?.printful_product_id || (initialMaterial === "metal" ? 588 : initialMaterial === "poster" ? 2 : 614);
  const [productId, setProductId] = useState(initialProductId);
  const [size, setSize] = useState(project?.size || "18x24");
  const [panelKey, setPanelKey] = useState(project?.panel_key || "single");
  const [variantId, setVariantId] = useState(project?.printful_variant_id || 0);
  const [catalog, setCatalog] = useState<PrintfulCatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState("");

  useEffect(() => { if (!project) setTimeout(() => router.replace("/(tabs)"), 0); }, [project, router]);
  useEffect(() => {
    let cancelled = false;
    api.printfulCatalog()
      .then((result) => { if (!cancelled) setCatalog(result); })
      .catch((error: Error) => { if (!cancelled) setCatalogError(error.message || "Printful catalog is unavailable"); });
    return () => { cancelled = true; };
  }, []);

  const productVariants = useMemo(
    () => (catalog?.variants || []).filter((variant) => variant.product_id === productId), [catalog, productId],
  );
  const availableSizes = useMemo(() => {
    const keys = new Set(productVariants.map((variant) => variant.size_key));
    return SIZES.filter((option) => keys.has(option.key));
  }, [productVariants]);
  const finishVariants = useMemo(
    () => productVariants.filter((variant) => variant.size_key === size), [productVariants, size],
  );
  const selectedVariant = catalog?.variants.find((variant) => variant.id === variantId) || null;

  useEffect(() => {
    if (!catalog || productVariants.length === 0) return;
    const nextSize = availableSizes.some((option) => option.key === size) ? size : availableSizes[0]?.key;
    if (!nextSize) return;
    if (nextSize !== size) { setSize(nextSize); return; }
    const current = catalog.variants.find((variant) => (
      variant.id === variantId && variant.product_id === productId && variant.size_key === nextSize
    ));
    if (current) return;
    const material = productVariants[0]?.material || initialMaterial;
    const preferredFinish = normalizedLegacyFinish(material, project?.frame || PREFERRED_FINISH[material]);
    const choices = productVariants.filter((variant) => variant.size_key === nextSize);
    const preferred = choices.find((variant) => variant.finish_key === preferredFinish && variant.in_stock)
      || choices.find((variant) => variant.finish_key === PREFERRED_FINISH[material] && variant.in_stock)
      || choices.find((variant) => variant.in_stock) || choices[0];
    if (preferred) setVariantId(preferred.id);
  }, [availableSizes, catalog, initialMaterial, productId, productVariants, project?.frame, size, variantId]);

  if (!project) return null;
  const panelCount = PANELS.find((panel) => panel.key === panelKey)?.count || 1;
  const productPrice = selectedVariant ? selectedVariant.retail_price * panelCount : 0;

  const chooseProduct = (nextProductId: number) => {
    Haptics.selectionAsync(); setProductId(nextProductId); setVariantId(0);
  };
  const chooseSize = (nextSize: string) => {
    Haptics.selectionAsync(); setSize(nextSize); setVariantId(0);
  };
  const chooseVariant = (variant: PrintfulCatalogVariant) => {
    if (!variant.in_stock) return;
    Haptics.selectionAsync(); setVariantId(variant.id);
  };
  const cont = () => {
    if (!selectedVariant) return;
    updateProject({
      material: selectedVariant.material, size: selectedVariant.size_key,
      frame: selectedVariant.finish_key, panel_key: panelKey, price: productPrice,
      printful_variant_id: selectedVariant.id, printful_product_id: selectedVariant.product_id,
      printful_variant_name: selectedVariant.name, printful_variant_image: selectedVariant.image,
      printful_retail_price: selectedVariant.retail_price, room_preview: "",
    });
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push("/room");
  };

  return (
    <View style={styles.root}>
      <FlowHeader title="Choose Your Print" step="Step 2 of 4" />
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.previewWrap}>
          <MultiPanelPreview image={project.current} count={panelCount}
            frameKey={selectedVariant?.finish_key || PREFERRED_FINISH[selectedVariant?.material || initialMaterial] || "none"}
            material={selectedVariant?.material || initialMaterial} width={300} height={260} />
        </View>

        <View style={styles.catalogHeading}>
          <View style={styles.catalogIcon}><Feather name="package" size={16} color={colors.success} /></View>
          <View style={{ flex: 1 }}>
            <Text style={styles.catalogTitle}>Official Printful catalog</Text>
            <Text style={styles.catalogMeta}>
              {catalog?.source === "printful_live" ? "Live product data" : "Verified development snapshot"} · Shipping at checkout
            </Text>
          </View>
        </View>
        {!catalog && !catalogError && <ActivityIndicator color={colors.brand} testID="catalog-loading" />}
        {!!catalogError && <Text style={styles.error} testID="catalog-error">{catalogError}</Text>}

        <Text style={styles.sectionLabel}>Print product</Text>
        <Text style={styles.sectionHelp}>Choose the product first. Available sizes and real frame options update below.</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.productGrid}>
          {Object.entries(PRODUCT_LABELS).filter(([key]) => (catalog?.variants || []).some((variant) => variant.product_id === Number(key))).map(([key, copy]) => {
            const id = Number(key); const active = productId === id;
            return <Pressable key={key} testID={`printful-product-${key}`} accessibilityRole="button"
              accessibilityState={{ selected: active }} style={[styles.productCard, active && styles.productCardActive]}
              onPress={() => chooseProduct(id)}>
              <Text style={[styles.productTitle, active && styles.productTextActive]}>{copy.title}</Text>
              <Text style={[styles.productDetail, active && styles.productDetailActive]}>{copy.detail}</Text>
            </Pressable>;
          })}
        </ScrollView>

        <Text style={styles.sectionLabel}>Size</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {availableSizes.map((option) => (
            <Pressable key={option.key} testID={`printful-size-${option.key}`} accessibilityRole="button"
              accessibilityState={{ selected: size === option.key }}
              style={[styles.chip, size === option.key && styles.chipActive]}
              onPress={() => chooseSize(option.key)}>
              <Text style={[styles.chipText, size === option.key && styles.chipTextActive]}>{option.label}</Text>
            </Pressable>
          ))}
        </ScrollView>

        <View>
          <Text style={styles.sectionLabel}>Printful finish</Text>
          <Text style={styles.sectionHelp}>Official product photo and exact variant for this size</Text>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.variantRow}>
          {finishVariants.map((variant) => {
            const selected = variant.id === variantId;
            return (
              <Pressable key={variant.id} testID={`printful-variant-${variant.id}`}
                accessibilityRole="button"
                accessibilityLabel={`${variant.finish_label}, ${variant.size_label}, $${variant.retail_price.toFixed(2)}`}
                accessibilityState={{ selected, disabled: !variant.in_stock }} disabled={!variant.in_stock}
                style={[styles.variantCard, selected && styles.variantCardActive, !variant.in_stock && styles.disabled]}
                onPress={() => chooseVariant(variant)}>
                <Image source={{ uri: variant.image }} style={styles.variantImage} contentFit="cover" transition={150} />
                <View style={styles.variantInfo}>
                  <View style={styles.variantTitleRow}>
                    <Text style={styles.variantTitle}>{variant.finish_label}</Text>
                    {selected && <Feather name="check-circle" size={16} color={colors.success} />}
                  </View>
                  <Text style={styles.variantPrice}>${variant.retail_price.toFixed(2)}</Text>
                  <Text style={styles.variantId}>Printful variant #{variant.id}</Text>
                  {!variant.in_stock && <Text style={styles.outOfStock}>Out of stock</Text>}
                </View>
              </Pressable>
            );
          })}
        </ScrollView>

        <Text style={styles.sectionLabel}>Layout</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {PANELS.map((panel) => (
            <Pressable key={panel.key} testID={`panel-${panel.key}`}
              style={[styles.chip, panelKey === panel.key && styles.chipActive]}
              onPress={() => { Haptics.selectionAsync(); setPanelKey(panel.key); }}>
              <Text style={[styles.chipText, panelKey === panel.key && styles.chipTextActive]}>{panel.label}</Text>
            </Pressable>
          ))}
        </ScrollView>

        {!!selectedVariant && (
          <View style={styles.selectionRecap} testID="printful-selection-recap">
            <Feather name="check-circle" size={18} color={colors.success} />
            <View style={{ flex: 1 }}>
              <Text style={styles.recapTitle}>{selectedVariant.name}</Text>
              <Text style={styles.recapMeta}>
                {panelCount > 1 ? `${panelCount} × ` : ""}{selectedVariant.product_name} · Exact variant #{selectedVariant.id}
              </Text>
            </View>
          </View>
        )}
        {catalog && !catalog.orders_configured && (
          <View style={styles.devNote} testID="printful-dev-note">
            <Feather name="info" size={16} color={colors.warning} />
            <Text style={styles.devNoteText}>Catalog testing is ready. Printful order authorization is not connected.</Text>
          </View>
        )}
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <View><Text style={styles.priceLabel}>Print price</Text>
          <Text style={styles.price}>{selectedVariant ? `$${productPrice.toFixed(2)}` : "—"}</Text></View>
        <Pressable testID="editor-continue-button" style={[styles.cta, !selectedVariant && styles.ctaDisabled]}
          onPress={cont} disabled={!selectedVariant}>
          <Text style={styles.ctaText}>Preview in Room</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.lg },
  previewWrap: { alignItems: "center", paddingVertical: spacing.sm },
  catalogHeading: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md },
  catalogIcon: { width: 34, height: 34, borderRadius: 17, backgroundColor: "rgba(74,93,78,0.10)", alignItems: "center", justifyContent: "center" },
  catalogTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  catalogMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  sectionLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: 1 },
  sectionHelp: { fontSize: font.sm, color: colors.muted, marginTop: spacing.xs },
  productGrid: { flexDirection: "row", gap: spacing.md, paddingRight: spacing.xl },
  productCard: { width: 154, minHeight: 92, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surfaceSecondary, justifyContent: "center" },
  productCardActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  productTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  productTextActive: { color: colors.onBrand },
  productDetail: { fontSize: font.sm, lineHeight: 17, color: colors.onSurfaceTertiary, marginTop: spacing.xs },
  productDetailActive: { color: "rgba(249,249,247,0.72)" },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  chip: { flexShrink: 0, height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.base, color: colors.onSurface, fontWeight: "600" },
  chipTextActive: { color: colors.onBrand },
  variantRow: { gap: spacing.md, paddingRight: spacing.xl },
  variantCard: { width: 176, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surfaceSecondary, overflow: "hidden" },
  variantCardActive: { borderColor: colors.success, borderWidth: 2 },
  variantImage: { width: "100%", height: 118, backgroundColor: colors.surfaceTertiary },
  variantInfo: { padding: spacing.md, gap: 3 },
  variantTitleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  variantTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  variantPrice: { fontSize: font.base, fontWeight: "700", color: colors.brandSecondary },
  variantId: { fontSize: 11, color: colors.muted },
  outOfStock: { fontSize: font.sm, color: colors.error, fontWeight: "700" },
  disabled: { opacity: 0.45 },
  selectionRecap: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(74,93,78,0.08)", borderWidth: 1, borderColor: "rgba(74,93,78,0.30)" },
  recapTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  recapMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  devNote: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(196,154,69,0.08)" },
  devNoteText: { flex: 1, fontSize: font.sm, color: colors.onSurfaceTertiary },
  error: { color: colors.error, fontSize: font.base },
  ctaBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  priceLabel: { fontSize: font.sm, color: colors.muted },
  price: { fontSize: font.xl, fontWeight: "700", color: colors.onSurface },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.xl },
  ctaDisabled: { opacity: 0.4 },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
