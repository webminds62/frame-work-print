import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import {
  ALL_STORE_VARIANTS,
  CollectionTier,
  FRAME_FAMILIES,
  FrameFamily,
  Orientation,
  STORE_SIZES,
  SizeDef,
  TIER_META,
  getFamily as localGetFamily,
  sizesForFamily as localSizesForFamily,
  variantsForFamily as localVariantsForFamily,
} from "@/src/catalog/store_skus";
import { api, StoreCatalogFamily, StoreCatalogResponse, StoreCatalogVariant } from "@/src/api";
import { setPendingFrame } from "@/src/store";
import { colors, spacing, radius, font, serif, PANELS } from "@/src/theme";

const COLS = 2;
const GAP = spacing.md;
const H_PAD = spacing.xl;
const CARD_W = (Dimensions.get("window").width - H_PAD * 2 - GAP) / COLS;

type TierFilter = "all" | CollectionTier;
type OrientFilter = "all" | Orientation;
type BrowseMode = "frame" | "size";

function toFamily(f: StoreCatalogFamily): FrameFamily {
  return {
    id: f.id,
    name: f.name,
    tagline: f.tagline,
    tier: f.tier,
    tier_rank: f.tier_rank,
    material: f.material,
    frame_key: f.frame_key,
    preview_frame: f.preview_frame,
    has_mat: f.has_mat,
    base_price: f.base_price,
    image: f.image,
    swatch: f.swatch,
    size_keys: f.size_keys,
  };
}

export default function StoreScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [catalog, setCatalog] = useState<StoreCatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [sourceLabel, setSourceLabel] = useState("loading");

  const [browseMode, setBrowseMode] = useState<BrowseMode>("frame");
  const [tier, setTier] = useState<TierFilter>("all");
  const [orientation, setOrientation] = useState<OrientFilter>("all");
  const [familyId, setFamilyId] = useState<string>("");
  const [sizeKey, setSizeKey] = useState<string>("18x24");
  const [panelKey, setPanelKey] = useState("single");
  const [shopSizeKey, setShopSizeKey] = useState("18x24");

  // Load catalog from backend API (not Printful). Fall back to local bundle if offline.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingCatalog(true);
      setCatalogError("");
      try {
        const data = await api.storeCatalog();
        if (cancelled) return;
        if (!data?.families?.length || !data?.variants?.length) {
          throw new Error("Catalog empty");
        }
        setCatalog(data);
        setSourceLabel(data.source || "api");
        const preferred =
          data.families.find((f) => f.id === "gallery-oak-mat") || data.families[0];
        setFamilyId(preferred.id);
      } catch (e: any) {
        if (cancelled) return;
        // Local fallback so Store still works offline
        setCatalog(null);
        setSourceLabel("local_fallback");
        setCatalogError(e?.message ? `API: ${e.message} — using offline catalog` : "Using offline catalog");
        setFamilyId(FRAME_FAMILIES[4]?.id || FRAME_FAMILIES[0].id);
      } finally {
        if (!cancelled) setLoadingCatalog(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const familiesAll: FrameFamily[] = useMemo(() => {
    if (catalog?.families?.length) return catalog.families.map(toFamily);
    return FRAME_FAMILIES;
  }, [catalog]);

  const sizesAll: SizeDef[] = useMemo(() => {
    if (catalog?.sizes?.length) {
      return catalog.sizes.map((s) => ({
        key: s.key,
        label: s.label,
        orientation: s.orientation as Orientation,
        wall_hint: s.wall_hint,
        mult: s.mult,
      }));
    }
    return STORE_SIZES;
  }, [catalog]);

  const variantsAll = useMemo(() => {
    if (catalog?.variants?.length) return catalog.variants;
    return ALL_STORE_VARIANTS as unknown as StoreCatalogVariant[];
  }, [catalog]);

  const tierMeta = catalog?.tier_meta || TIER_META;

  const families = useMemo(() => {
    let list = [...familiesAll];
    if (tier !== "all") list = list.filter((f) => f.tier === tier);
    return list.sort((a, b) => a.tier_rank - b.tier_rank || a.base_price - b.base_price);
  }, [familiesAll, tier]);

  const family: FrameFamily | undefined =
    familiesAll.find((f) => f.id === familyId) || families[0] || familiesAll[0];

  const sizeOptions = useMemo(() => {
    if (!family) return [] as SizeDef[];
    const keys = new Set(family.size_keys);
    return sizesAll
      .filter((s) => keys.has(s.key))
      .filter((s) => orientation === "all" || s.orientation === orientation);
  }, [family, sizesAll, orientation]);

  const activeSizeKey = sizeOptions.some((s) => s.key === sizeKey)
    ? sizeKey
    : sizeOptions[0]?.key || "18x24";

  const panelMult = PANELS.find((p) => p.key === panelKey)?.mult || 1;
  const panelCount = PANELS.find((p) => p.key === panelKey)?.count || 1;

  const selectedVariant = useMemo(() => {
    if (!family) return null;
    const base = variantsAll.find(
      (v) => v.family_id === family.id && v.size_key === activeSizeKey,
    );
    if (!base) return null;
    return {
      ...base,
      retail_price: Math.round(base.retail_price * panelMult),
      panel_key: panelKey,
    };
  }, [family, activeSizeKey, panelKey, panelMult, variantsAll]);

  const shopBySizeFamilies = useMemo(() => {
    return familiesAll
      .filter((f) => f.size_keys.includes(shopSizeKey))
      .filter((f) => tier === "all" || f.tier === tier)
      .sort((a, b) => a.base_price - b.base_price);
  }, [familiesAll, shopSizeKey, tier]);

  const totalVariantCount = variantsAll.length;

  const chooseFamily = (id: string) => {
    Haptics.selectionAsync();
    setFamilyId(id);
  };
  const chooseSize = (key: string) => {
    Haptics.selectionAsync();
    setSizeKey(key);
  };

  const confirm = () => {
    if (!selectedVariant || !family) return;
    // IMPORTANT: save real frame_key (oak/walnut/black) for room preview API
    setPendingFrame({
      store_variant_id: selectedVariant.id,
      store_family_id: family.id,
      store_family_name: family.name,
      store_tier: family.tier,
      store_image: family.image,
      material: family.material === "framed" ? "poster" : family.material,
      size: selectedVariant.size_key,
      size_label: selectedVariant.size_label,
      frame: family.frame_key,
      preview_frame: family.preview_frame,
      has_mat: family.has_mat,
      panel_key: panelKey,
      wall_hint: selectedVariant.wall_hint,
      price: selectedVariant.retail_price,
    });
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push("/(tabs)/index");
  };

  const tierChip = (key: TierFilter, label: string) => {
    const active = tier === key;
    return (
      <Pressable
        key={key}
        testID={`tier-${key}`}
        onPress={() => {
          Haptics.selectionAsync();
          setTier(key);
        }}
        style={[styles.chip, active && styles.chipActive]}
      >
        <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
      </Pressable>
    );
  };

  if (loadingCatalog) {
    return (
      <View style={[styles.root, styles.center, { paddingTop: insets.top }]} testID="store-loading">
        <ActivityIndicator size="large" color={colors.brand} />
        <Text style={styles.loadingText}>Loading frame gallery…</Text>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]} testID="store-screen">
      <View style={styles.header}>
        <Text style={styles.kicker}>FRAME GALLERY</Text>
        <Text style={styles.title}>Choose a frame</Text>
        <Text style={styles.sub}>
          Essential → Gallery → Atelier · {totalVariantCount}+ sizes · every option made to hang at home
        </Text>
        <Text style={styles.source} testID="catalog-source">
          Catalog: {sourceLabel === "local_fallback" ? "offline bundle" : "API /catalog/store"}
          {catalog?.prodigi_configured ? " · Prodigi ready" : ""}
        </Text>
        {!!catalogError && (
          <Text style={styles.warn} testID="catalog-warn">
            {catalogError}
          </Text>
        )}
      </View>

      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
        <View style={styles.modeRow}>
          <Pressable
            testID="browse-by-frame"
            style={[styles.modeBtn, browseMode === "frame" && styles.modeBtnActive]}
            onPress={() => setBrowseMode("frame")}
          >
            <Text style={[styles.modeText, browseMode === "frame" && styles.modeTextActive]}>
              Shop frames
            </Text>
          </Pressable>
          <Pressable
            testID="browse-by-size"
            style={[styles.modeBtn, browseMode === "size" && styles.modeBtnActive]}
            onPress={() => setBrowseMode("size")}
          >
            <Text style={[styles.modeText, browseMode === "size" && styles.modeTextActive]}>
              Shop by size
            </Text>
          </Pressable>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {tierChip("all", "All")}
          {tierChip("essential", "Essential")}
          {tierChip("gallery", "Gallery")}
          {tierChip("atelier", "Atelier")}
        </ScrollView>

        {tier !== "all" && (
          <Text style={styles.tierBlurb}>
            {(tierMeta as any)[tier]?.blurb || TIER_META[tier].blurb}
          </Text>
        )}

        {family && selectedVariant && browseMode === "frame" && (
          <View style={styles.hero} testID="store-hero">
            <Image source={{ uri: family.image }} style={styles.heroImage} contentFit="cover" transition={200} />
            <View style={styles.heroOverlay}>
              <View style={[styles.swatch, { backgroundColor: family.swatch }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.heroTier}>
                  {(tierMeta as any)[family.tier]?.label || TIER_META[family.tier].label}
                </Text>
                <Text style={styles.heroName}>{family.name}</Text>
                <Text style={styles.heroMeta}>
                  {selectedVariant.size_label} · {selectedVariant.wall_hint}
                  {family.has_mat ? " · Museum mat" : ""}
                </Text>
              </View>
              <Text style={styles.heroPrice}>${selectedVariant.retail_price}</Text>
            </View>
          </View>
        )}

        {browseMode === "frame" ? (
          <>
            <Text style={styles.sectionLabel}>Finishes</Text>
            <Text style={styles.sectionHelp}>Loaded from the Frame Works catalog API</Text>
            <View style={styles.grid}>
              {families.map((f) => {
                const active = f.id === family?.id;
                const fromPrices = variantsAll
                  .filter((v) => v.family_id === f.id)
                  .map((v) => v.retail_price);
                const from = fromPrices.length ? Math.min(...fromPrices) : f.base_price;
                return (
                  <Pressable
                    key={f.id}
                    testID={`family-${f.id}`}
                    onPress={() => chooseFamily(f.id)}
                    style={[styles.card, active && styles.cardActive]}
                  >
                    <Image source={{ uri: f.image }} style={styles.cardImage} contentFit="cover" />
                    <View style={[styles.cardSwatch, { backgroundColor: f.swatch }]} />
                    <View style={styles.cardBody}>
                      <Text style={styles.cardTier}>
                        {(tierMeta as any)[f.tier]?.label || f.tier}
                      </Text>
                      <Text style={styles.cardName} numberOfLines={2}>
                        {f.name}
                      </Text>
                      <Text style={styles.cardTag} numberOfLines={2}>
                        {f.tagline}
                      </Text>
                      <Text style={styles.cardPrice}>From ${from}</Text>
                    </View>
                    {active && (
                      <View style={styles.check}>
                        <Feather name="check" size={14} color={colors.onBrand} />
                      </View>
                    )}
                  </Pressable>
                );
              })}
            </View>

            <Text style={styles.sectionLabel}>Orientation</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
              {(["all", "portrait", "landscape", "square"] as OrientFilter[]).map((o) => {
                const active = orientation === o;
                const label = o === "all" ? "All" : o[0].toUpperCase() + o.slice(1);
                return (
                  <Pressable
                    key={o}
                    testID={`orient-${o}`}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => {
                      Haptics.selectionAsync();
                      setOrientation(o);
                    }}
                  >
                    <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
                  </Pressable>
                );
              })}
            </ScrollView>

            <Text style={styles.sectionLabel}>Size</Text>
            <Text style={styles.sectionHelp}>Price updates with your frame — then preview it on a wall</Text>
            <View style={styles.sizeGrid}>
              {sizeOptions.map((s) => {
                const active = s.key === activeSizeKey;
                const variant = variantsAll.find(
                  (v) => v.family_id === family?.id && v.size_key === s.key,
                );
                const price = variant ? Math.round(variant.retail_price * panelMult) : 0;
                return (
                  <Pressable
                    key={s.key}
                    testID={`size-${s.key}`}
                    onPress={() => chooseSize(s.key)}
                    style={[styles.sizeChip, active && styles.sizeChipActive]}
                  >
                    <Text style={[styles.sizeLabel, active && styles.sizeLabelActive]}>{s.label}</Text>
                    <Text style={[styles.sizeHint, active && styles.sizeHintActive]}>{s.wall_hint}</Text>
                    <Text style={[styles.sizePrice, active && styles.sizePriceActive]}>${price}</Text>
                  </Pressable>
                );
              })}
              {sizeOptions.length === 0 && (
                <Text style={styles.empty}>No sizes in this orientation — try All.</Text>
              )}
            </View>
          </>
        ) : (
          <>
            <Text style={styles.sectionLabel}>Pick a wall size first</Text>
            <View style={styles.sizeGrid}>
              {sizesAll.map((s) => {
                const active = s.key === shopSizeKey;
                return (
                  <Pressable
                    key={s.key}
                    testID={`shop-size-${s.key}`}
                    onPress={() => {
                      Haptics.selectionAsync();
                      setShopSizeKey(s.key);
                    }}
                    style={[styles.sizeChip, active && styles.sizeChipActive]}
                  >
                    <Text style={[styles.sizeLabel, active && styles.sizeLabelActive]}>{s.label}</Text>
                    <Text style={[styles.sizeHint, active && styles.sizeHintActive]}>{s.wall_hint}</Text>
                  </Pressable>
                );
              })}
            </View>
            <Text style={styles.sectionLabel}>
              Frames in {sizesAll.find((s) => s.key === shopSizeKey)?.label}
            </Text>
            <View style={styles.grid}>
              {shopBySizeFamilies.map((f) => {
                const v = variantsAll.find((x) => x.family_id === f.id && x.size_key === shopSizeKey);
                const active = f.id === family?.id && activeSizeKey === shopSizeKey;
                return (
                  <Pressable
                    key={f.id}
                    testID={`size-family-${f.id}`}
                    onPress={() => {
                      chooseFamily(f.id);
                      setSizeKey(shopSizeKey);
                      setBrowseMode("frame");
                    }}
                    style={[styles.card, active && styles.cardActive]}
                  >
                    <Image source={{ uri: f.image }} style={styles.cardImage} contentFit="cover" />
                    <View style={styles.cardBody}>
                      <Text style={styles.cardTier}>
                        {(tierMeta as any)[f.tier]?.label || f.tier}
                      </Text>
                      <Text style={styles.cardName} numberOfLines={2}>
                        {f.name}
                      </Text>
                      <Text style={styles.cardPrice}>${v?.retail_price ?? "—"}</Text>
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </>
        )}

        <Text style={styles.sectionLabel}>Layout</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
          {PANELS.map((p) => {
            const active = panelKey === p.key;
            return (
              <Pressable
                key={p.key}
                testID={`panel-${p.key}`}
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => {
                  Haptics.selectionAsync();
                  setPanelKey(p.key);
                }}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{p.label}</Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <View style={{ height: 120 }} />
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <View style={styles.ctaSummary}>
          <Text style={styles.ctaTitle} numberOfLines={1}>
            {family?.name || "Select a frame"}
          </Text>
          <Text style={styles.ctaMeta} numberOfLines={1}>
            {selectedVariant
              ? `${selectedVariant.size_label}${panelCount > 1 ? ` · ${panelCount}-panel` : ""} · ${selectedVariant.wall_hint}`
              : "Choose finish & size"}
          </Text>
        </View>
        <Pressable
          testID="use-frame-button"
          style={[styles.cta, !selectedVariant && styles.ctaDisabled]}
          disabled={!selectedVariant}
          onPress={confirm}
        >
          <Text style={styles.ctaText}>
            {selectedVariant ? `Use frame · $${selectedVariant.retail_price}` : "Select frame"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center", gap: spacing.md },
  loadingText: { color: colors.onSurfaceTertiary, fontSize: font.base },
  header: { paddingHorizontal: H_PAD, gap: spacing.xs, marginBottom: spacing.sm },
  kicker: { color: colors.brandSecondary, fontSize: font.sm, letterSpacing: 2, fontWeight: "700" },
  title: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  sub: { fontSize: font.base, color: colors.onSurfaceTertiary, lineHeight: 20 },
  source: { fontSize: 11, color: colors.muted, marginTop: 2 },
  warn: { fontSize: font.sm, color: colors.warning, marginTop: 4 },
  body: { paddingHorizontal: H_PAD, gap: spacing.md, paddingBottom: spacing.xl },
  modeRow: { flexDirection: "row", gap: spacing.sm },
  modeBtn: {
    flex: 1,
    height: 40,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceSecondary,
  },
  modeBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  modeText: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  modeTextActive: { color: colors.onBrand },
  chipsRow: { gap: spacing.sm, paddingVertical: 2 },
  chip: {
    paddingHorizontal: spacing.lg,
    height: 36,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: font.sm, fontWeight: "600", color: colors.onSurface },
  chipTextActive: { color: colors.onBrand },
  tierBlurb: { fontSize: font.sm, color: colors.brandSecondary, fontStyle: "italic" },
  hero: {
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  heroImage: { width: "100%", height: 200 },
  heroOverlay: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
  },
  swatch: { width: 28, height: 28, borderRadius: 14, borderWidth: 1, borderColor: colors.borderStrong },
  heroTier: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.success,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  heroName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  heroMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  heroPrice: { fontSize: font.xl, fontWeight: "700", color: colors.onSurface },
  sectionLabel: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface, marginTop: spacing.sm },
  sectionHelp: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: -spacing.sm },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: GAP },
  card: {
    width: CARD_W,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  cardActive: { borderColor: colors.success, borderWidth: 2 },
  cardImage: { width: "100%", height: CARD_W * 0.85, backgroundColor: colors.surfaceTertiary },
  cardSwatch: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#fff",
  },
  cardBody: { padding: spacing.md, gap: 3 },
  cardTier: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.brandSecondary,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  cardName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  cardTag: { fontSize: font.sm, color: colors.onSurfaceTertiary, lineHeight: 16 },
  cardPrice: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, marginTop: 4 },
  check: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.success,
    alignItems: "center",
    justifyContent: "center",
  },
  sizeGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sizeChip: {
    width: (Dimensions.get("window").width - H_PAD * 2 - spacing.sm * 2) / 3,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    gap: 2,
  },
  sizeChipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  sizeLabel: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  sizeLabelActive: { color: colors.onBrand },
  sizeHint: { fontSize: 11, color: colors.onSurfaceTertiary },
  sizeHintActive: { color: "rgba(249,249,247,0.75)" },
  sizePrice: { fontSize: font.sm, fontWeight: "700", color: colors.onSurface, marginTop: 4 },
  sizePriceActive: { color: colors.onBrand },
  empty: { color: colors.muted, fontSize: font.base },
  ctaBar: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: H_PAD,
    paddingTop: spacing.md,
    gap: spacing.sm,
  },
  ctaSummary: { gap: 2 },
  ctaTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  ctaMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  cta: {
    backgroundColor: colors.brand,
    height: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaDisabled: { opacity: 0.4 },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
});
