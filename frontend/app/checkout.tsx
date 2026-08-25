import { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, Pressable, ScrollView, TextInput,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from "react-native";
import { Image } from "expo-image";
import { useStripe } from "@/src/lib/stripe";

import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import FlowHeader from "@/src/components/FlowHeader";
import { api } from "@/src/api";
import { getProject } from "@/src/store";
import { colors, spacing, radius, font, serif, MATERIALS, SIZES, PANELS } from "@/src/theme";

const FIELDS = [
  { key: "name", label: "Full name", placeholder: "Alex Rivera" },
  { key: "address1", label: "Street address", placeholder: "123 Main St" },
  { key: "city", label: "City", placeholder: "Austin" },
  { key: "state_code", label: "State", placeholder: "TX" },
  { key: "zip", label: "ZIP code", placeholder: "78701", keyboard: "number-pad" as const },
  { key: "country_code", label: "Country code", placeholder: "US" },
];

export default function Checkout() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { initPaymentSheet, presentPaymentSheet } = useStripe();
  const project = getProject();
  const [form, setForm] = useState<Record<string, string>>({ country_code: "US" });
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [quote, setQuote] = useState<any>(null);

  useEffect(() => {
    if (!project) { setTimeout(() => router.replace("/(tabs)"), 0); return; }
    // Fetch an initial quote so the first-order discount + price show upfront.
    (async () => {
      try {
        const pc = PANELS.find((p) => p.key === project.panel_key)?.count || 1;
        const q = await api.quote({
          material: project.material, size: project.size, panels: pc, frame: project.frame,
          printful_variant_id: project.printful_variant_id || undefined,
          store_variant_id: project.store_variant_id,
          fallback_price: project.price,
          recipient: { name: "", address1: "", city: "", state_code: "", country_code: "US", zip: "" },
        });
        setQuote(q);
      } catch {}
    })();
  }, [project, router]);
  if (!project) return null;

  const set = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));
  const heroImg = project.room_preview || project.current;
  const materialLabel = MATERIALS.find((m) => m.key === project.material)?.label;
  const sizeLabel = SIZES.find((s) => s.key === project.size)?.label;
  const panelCount = PANELS.find((p) => p.key === project.panel_key)?.count || 1;
  const finalPrice = quote?.retail ?? project.price;
  const hasDiscount = !!quote?.first_order && (quote?.discount_amount || 0) > 0;

  const buildRecipient = () => ({
    name: form.name || "", address1: form.address1 || "", city: form.city || "",
    state_code: form.state_code || "", country_code: form.country_code || "US", zip: form.zip || "",
  });

  const startPayment = async () => {
    if (!project.store_variant_id && !project.printful_variant_id && !(project.price > 0)) { setError("Return to the Store and choose a frame first."); return; }
    for (const f of FIELDS) if (!form[f.key]?.trim()) { setError(`Please fill in ${f.label.toLowerCase()}`); return; }
    setLoading(true); setError("");
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      // Persist the project so the server can fulfil + reference the print image. The server
      // computes the amount and creates the Stripe PaymentIntent.
      const saved = await api.saveProject({
        original: project.original, current: project.current,
        room: project.room, room_preview: project.room_preview, material: project.material,
        size: project.size, frame: project.frame, panel_key: project.panel_key, panels: panelCount,
        price: project.price,
        store_variant_id: project.store_variant_id,
        store_family_id: project.store_family_id,
        store_family_name: project.store_family_name,
        store_tier: project.store_tier,
        store_image: project.store_image,
        has_mat: project.has_mat,
        printful_variant_id: project.printful_variant_id,
        printful_product_id: project.printful_product_id,
        printful_variant_name: project.store_family_name || project.printful_variant_name,
        printful_variant_image: project.store_image || project.printful_variant_image,
        printful_retail_price: project.price,
      });
      const res = await api.createPaymentIntent({
        project_id: saved.id, material: project.material, size: project.size,
        frame: project.frame,
        printful_variant_id: project.printful_variant_id || 0,
        store_variant_id: project.store_variant_id,
        fallback_price: project.price,
        panel_key: project.panel_key, panels: panelCount,
        recipient: buildRecipient(),
      });
      if (res.quote) setQuote(res.quote);
      const initialized = await initPaymentSheet({
        merchantDisplayName: "Frame Works Prints",
        paymentIntentClientSecret: res.client_secret,
        returnURL: "frameworksprints://stripe-redirect",
        allowsDelayedPaymentMethods: false,
      });
      if (initialized.error) throw new Error(initialized.error.message);
      setProcessing(true);
      const presented = await presentPaymentSheet();
      if (presented.error) {
        if (presented.error.code !== "Canceled") throw new Error(presented.error.message);
        return;
      }
      // Stripe's UI success is not trusted by itself; the server retrieves and verifies the
      // PaymentIntent before creating the order.
      await api.completePayment(res.payment_intent_id);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setDone(true);
    } catch (e: any) {
      setError(e.message || "Payment could not be completed. Please try again.");
    } finally { setLoading(false); setProcessing(false); }
  };

  if (done) {
    return (
      <View style={styles.successRoot} testID="order-success">
        <View style={styles.successCircle}><Feather name="check" size={40} color={colors.onBrand} /></View>
        <Text style={styles.doneTitle}>Order confirmed</Text>
        <Text style={styles.doneSub}>Payment received and your piece is heading to production. Track it in the Orders tab.</Text>
        <Pressable testID="view-orders-button" style={styles.cta} onPress={() => router.replace("/(tabs)/orders")}>
          <Text style={styles.ctaText}>View my orders</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <FlowHeader title="Checkout" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }} keyboardVerticalOffset={10}>
        <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
          {hasDiscount && (
            <View style={styles.promo} testID="first-order-promo">
              <Feather name="gift" size={18} color={colors.success} />
              <Text style={styles.promoText}>10% off your first print — you save ${quote.discount_amount.toFixed(2)}!</Text>
            </View>
          )}

          <View style={styles.summary}>
            <Image source={{ uri: heroImg }} style={styles.thumb} contentFit="cover" />
            <View style={{ flex: 1 }}>
              <Text style={styles.summaryTitle}>{materialLabel} · {sizeLabel}</Text>
              <Text style={styles.summaryMeta}>{panelCount > 1 ? `${panelCount}-panel · ` : ""}{project.store_family_name || project.printful_variant_name || "Gallery frame"}</Text>
              <Text style={styles.variantMeta}>{project.store_tier ? String(project.store_tier).toUpperCase() : "FRAME WORKS"} · {project.size}</Text>
            </View>
            <View style={{ alignItems: "flex-end" }}>
              {hasDiscount && <Text style={styles.strikePrice}>${quote.retail_before_discount.toFixed(2)}</Text>}
              <Text style={styles.summaryPrice}>${finalPrice.toFixed(2)}</Text>
            </View>
          </View>

          {quote && (
            <Text style={styles.quoteNote} testID="quote-note">
              {`Includes $${(quote.shipping ?? 0).toFixed(2)} shipping · gallery pricing`}
            </Text>
          )}

          <Text style={styles.sectionTitle}>Shipping address</Text>
          {FIELDS.map((f) => (
            <View key={f.key}>
              <Text style={styles.label}>{f.label}</Text>
              <TextInput
                testID={`checkout-${f.key}`}
                style={styles.input}
                placeholder={f.placeholder}
                placeholderTextColor={colors.muted}
                keyboardType={(f as any).keyboard || "default"}
                autoCapitalize={f.key === "country_code" || f.key === "state_code" ? "characters" : "words"}
                value={form[f.key] || ""}
                onChangeText={(v) => set(f.key, v)}
              />
            </View>
          ))}
          {!!error && <Text style={styles.error} testID="checkout-error">{error}</Text>}
        </ScrollView>
      </KeyboardAvoidingView>

      <View style={[styles.ctaBar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Pressable testID="pay-stripe-button" style={styles.cta} onPress={startPayment} disabled={loading || processing}>
          {loading || processing ? <ActivityIndicator color={colors.onBrand} /> : <Text style={styles.ctaText}>Pay securely · ${finalPrice.toFixed(2)}</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.md },
  summary: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border },
  thumb: { width: 60, height: 60, borderRadius: radius.sm },
  summaryTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  summaryMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2, textTransform: "capitalize" },
  variantMeta: { fontSize: 11, color: colors.muted, marginTop: 2 },
  summaryPrice: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  strikePrice: { fontSize: font.sm, color: colors.muted, textDecorationLine: "line-through" },
  promo: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: "rgba(74,93,78,0.10)", borderWidth: 1, borderColor: colors.success, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: spacing.md },
  promoText: { flex: 1, fontSize: font.base, color: colors.success, fontWeight: "700" },
  quoteNote: { fontSize: font.sm, color: colors.brandSecondary, fontWeight: "600" },
  sectionTitle: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface, marginTop: spacing.md },
  label: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginBottom: spacing.xs, fontWeight: "600", marginTop: spacing.sm },
  input: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, paddingHorizontal: spacing.lg, height: 50, fontSize: font.lg, color: colors.onSurface, borderWidth: 1, borderColor: colors.border },
  error: { color: colors.error, fontSize: font.base, marginTop: spacing.sm },
  ctaBar: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.xl },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  successRoot: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.md },
  successCircle: { width: 88, height: 88, borderRadius: 44, backgroundColor: colors.success, alignItems: "center", justifyContent: "center" },
  doneTitle: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface, marginTop: spacing.md },
  doneSub: { fontSize: font.base, color: colors.onSurfaceTertiary, textAlign: "center" },
});
