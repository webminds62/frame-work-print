import { useCallback, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator, ScrollView, RefreshControl, Pressable, Linking } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useFocusEffect } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { api } from "@/src/api";
import { colors, spacing, radius, font, serif, MATERIALS, SIZES, FRAMES } from "@/src/theme";

const STATUS: Record<string, { text: string; color: string }> = {
  received: { text: "Received", color: colors.warning },
  in_production: { text: "In production", color: colors.brandSecondary },
  shipped: { text: "Shipped", color: colors.success },
  delivered: { text: "Delivered", color: colors.success },
  cancelled: { text: "Cancelled", color: colors.error },
};

export default function Orders() {
  const insets = useSafeAreaInsets();
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try { setOrders(await api.listOrders()); } catch {}
    finally { setLoading(false); setRefreshing(false); }
  };
  useFocusEffect(useCallback(() => { load(); }, []));

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.md }]}>
      <View style={styles.header}>
        <Text style={styles.title}>Orders</Text>
        <Text style={styles.sub}>{orders.length} total</Text>
      </View>
      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.onSurface} /></View>
      ) : orders.length === 0 ? (
        <View style={styles.center}>
          <Feather name="shopping-bag" size={48} color={colors.borderStrong} />
          <Text style={styles.emptyTitle}>No orders yet</Text>
          <Text style={styles.emptySub}>Your orders will appear here.</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.list} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
          {orders.map((o) => {
            const s = STATUS[o.status] || { text: o.status, color: colors.muted };
            const mat = MATERIALS.find((m) => m.key === o.material)?.label || o.material;
            const sz = SIZES.find((x) => x.key === o.size)?.label || o.size;
            const fr = FRAMES.find((f) => f.key === o.frame)?.label;
            const framed = o.frame && o.frame !== "none";
            return (
              <View key={o.id} style={styles.card} testID={`order-${o.id}`}>
                <Image source={{ uri: o.room_preview || o.image_base64 }} style={styles.thumb} contentFit="cover" />
                <View style={{ flex: 1, gap: 4 }}>
                  <Text style={styles.cardTitle}>{mat} · {sz}</Text>
                  <Text style={styles.cardMeta}>{framed ? `${fr} frame · ` : ""}${(o.price || 0).toFixed(2)}</Text>
                  <View style={[styles.badge, { backgroundColor: s.color }]}><Text style={styles.badgeText}>{s.text}</Text></View>
                  {!!o.tracking_url && (
                    <Pressable testID={`track-${o.id}`} style={styles.track} onPress={() => Linking.openURL(o.tracking_url)}>
                      <Feather name="truck" size={14} color={colors.brandSecondary} />
                      <Text style={styles.trackText}>Track package</Text>
                    </Pressable>
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.xl, paddingVertical: spacing.sm },
  title: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  sub: { fontSize: font.base, color: colors.onSurfaceTertiary },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm, padding: spacing.xl },
  emptyTitle: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface, marginTop: spacing.md },
  emptySub: { fontSize: font.base, color: colors.onSurfaceTertiary, textAlign: "center" },
  list: { padding: spacing.xl, gap: spacing.md },
  card: { flexDirection: "row", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  thumb: { width: 72, height: 72, borderRadius: radius.sm },
  cardTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  cardMeta: { fontSize: font.base, color: colors.onSurfaceTertiary },
  badge: { alignSelf: "flex-start", borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 3 },
  badgeText: { color: "#FFFFFF", fontSize: font.sm, fontWeight: "600" },
  track: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  trackText: { color: colors.brandSecondary, fontSize: font.sm, fontWeight: "700" },
});
