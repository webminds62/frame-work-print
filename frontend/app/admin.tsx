import { useCallback, useState } from "react";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, Pressable, RefreshControl } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useFocusEffect } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { api } from "@/src/api";
import { colors, spacing, radius, font, serif } from "@/src/theme";

const NEXT_STATUS: Record<string, string> = {
  received: "in_production",
  in_production: "shipped",
  shipped: "delivered",
  delivered: "received",
};

export default function Admin() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [stats, setStats] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const [s, o] = await Promise.all([api.adminStats(), api.adminOrders()]);
      setStats(s); setOrders(o);
    } catch {}
    finally { setLoading(false); setRefreshing(false); }
  };
  useFocusEffect(useCallback(() => { load(); }, []));

  const cycleStatus = async (o: any) => {
    const next = NEXT_STATUS[o.status] || "received";
    Haptics.selectionAsync();
    await api.adminUpdateOrder(o.id, next);
    setOrders((prev) => prev.map((x) => (x.id === o.id ? { ...x, status: next } : x)));
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <View style={styles.header}>
        <Pressable testID="admin-back" hitSlop={10} onPress={() => router.back()}>
          <Feather name="chevron-left" size={26} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Admin</Text>
        <View style={{ width: 26 }} />
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.onSurface} /></View>
      ) : (
        <ScrollView contentContainerStyle={styles.body} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
          <View style={styles.statsRow}>
            <View style={styles.statCard}><Text style={styles.statNum}>${(stats?.revenue || 0).toFixed(0)}</Text><Text style={styles.statLabel}>Revenue</Text></View>
            <View style={styles.statCard}><Text style={styles.statNum}>{stats?.total_orders || 0}</Text><Text style={styles.statLabel}>Orders</Text></View>
          </View>
          <View style={styles.statsRow}>
            <View style={styles.statCard}><Text style={styles.statNum}>{stats?.total_users || 0}</Text><Text style={styles.statLabel}>Customers</Text></View>
            <View style={styles.statCard}><Text style={styles.statNum}>{stats?.total_projects || 0}</Text><Text style={styles.statLabel}>Uploads</Text></View>
          </View>
          {!!stats?.unfulfilled_orders && (
            <View style={styles.alertCard} testID="unfulfilled-alert">
              <Feather name="alert-triangle" size={18} color={colors.error} />
              <Text style={styles.alertText}>
                {stats.unfulfilled_orders} order{stats.unfulfilled_orders === 1 ? "" : "s"} paid but not auto-fulfilled — needs manual handling ({'see "Needs fulfillment" below'}).
              </Text>
            </View>
          )}

          <Text style={styles.sectionTitle}>Recent orders</Text>
          {orders.length === 0 ? (
            <Text style={styles.empty}>No orders yet.</Text>
          ) : orders.map((o) => {
            const needsFulfillment = o.printful_status === "not_fulfilled_by_printful";
            return (
              <View key={o.id} style={[styles.orderRow, needsFulfillment && styles.orderRowAlert]} testID={`admin-order-${o.id}`}>
                <Image source={{ uri: o.room_preview || o.image_base64 }} style={styles.thumb} contentFit="cover" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.orderTitle}>{o.material} · {o.size}</Text>
                  <Text style={styles.orderMeta}>{o.user_email} · ${(o.price || 0).toFixed(2)}</Text>
                  <Text style={styles.orderMeta}>Ship to: {o.recipient?.name}, {o.recipient?.city}</Text>
                  {needsFulfillment && (
                    <Text style={styles.needsFulfillmentText} testID={`needs-fulfillment-${o.id}`}>
                      ⚠ Needs fulfillment — no automated print/ship path for this item
                    </Text>
                  )}
                </View>
                <Pressable testID={`admin-status-${o.id}`} style={styles.statusBtn} onPress={() => cycleStatus(o)}>
                  <Text style={styles.statusText}>{o.status}</Text>
                </Pressable>
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
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  body: { padding: spacing.xl, gap: spacing.md },
  statsRow: { flexDirection: "row", gap: spacing.md },
  statCard: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  statNum: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  statLabel: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  alertCard: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.error },
  alertText: { flex: 1, color: colors.error, fontSize: font.sm, fontWeight: "600" },
  sectionTitle: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface, marginTop: spacing.md },
  empty: { color: colors.onSurfaceTertiary, fontSize: font.base },
  orderRow: { flexDirection: "row", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  orderRowAlert: { borderColor: colors.error, borderWidth: 1.5 },
  needsFulfillmentText: { fontSize: font.sm, color: colors.error, fontWeight: "700", marginTop: 2 },
  thumb: { width: 56, height: 56, borderRadius: radius.sm },
  orderTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, textTransform: "capitalize" },
  orderMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  statusBtn: { backgroundColor: colors.brandTertiary, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  statusText: { fontSize: font.sm, color: colors.onBrandTertiary, fontWeight: "600", textTransform: "capitalize" },
});
