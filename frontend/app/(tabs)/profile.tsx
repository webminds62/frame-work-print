import { useState } from "react";
import { View, Text, StyleSheet, Pressable, ScrollView, Modal, ActivityIndicator } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useAuth } from "@/src/context/AuthContext";
import { api } from "@/src/api";
import { colors, spacing, radius, font, serif } from "@/src/theme";

export default function Profile() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const doLogout = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    await logout();
    router.replace("/onboarding");
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await api.deleteAccount();
      await logout();
      router.replace("/onboarding");
    } catch { setDeleting(false); setConfirm(false); }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.md }]}>
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.avatarWrap}>
          <View style={styles.avatar}><Text style={styles.avatarText}>{(user?.name || user?.email || "?")[0].toUpperCase()}</Text></View>
          <Text style={styles.name}>{user?.name || "Guest"}</Text>
          <Text style={styles.email}>{user?.email}</Text>
        </View>

        {user?.is_admin && (
          <Pressable testID="admin-dashboard-button" style={styles.adminCard} onPress={() => router.push("/admin")}>
            <Feather name="bar-chart-2" size={20} color={colors.onBrand} />
            <View style={{ flex: 1 }}>
              <Text style={styles.adminTitle}>Admin Dashboard</Text>
              <Text style={styles.adminSub}>Manage orders, uploads & revenue</Text>
            </View>
            <Feather name="chevron-right" size={20} color={colors.onBrand} />
          </Pressable>
        )}

        <View style={styles.card}>
          <Pressable testID="row-create" style={[styles.row, styles.rowBorder]} onPress={() => router.push("/(tabs)")}>
            <View style={styles.iconBox}><Feather name="camera" size={18} color={colors.onSurface} /></View>
            <Text style={styles.rowLabel}>Create new art</Text>
            <Feather name="chevron-right" size={18} color={colors.muted} />
          </Pressable>
          <Pressable testID="row-gallery" style={[styles.row, styles.rowBorder]} onPress={() => router.push("/(tabs)/gallery")}>
            <View style={styles.iconBox}><Feather name="grid" size={18} color={colors.onSurface} /></View>
            <Text style={styles.rowLabel}>My gallery</Text>
            <Feather name="chevron-right" size={18} color={colors.muted} />
          </Pressable>
          <Pressable testID="row-orders" style={styles.row} onPress={() => router.push("/(tabs)/orders")}>
            <View style={styles.iconBox}><Feather name="shopping-bag" size={18} color={colors.onSurface} /></View>
            <Text style={styles.rowLabel}>My orders</Text>
            <Feather name="chevron-right" size={18} color={colors.muted} />
          </Pressable>
        </View>

        <Pressable testID="logout-button" style={styles.logout} onPress={doLogout}>
          <Feather name="log-out" size={18} color={colors.onSurface} />
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
        <Pressable testID="delete-account-button" style={styles.deleteRow} onPress={() => setConfirm(true)}>
          <Feather name="trash-2" size={16} color={colors.error} />
          <Text style={styles.deleteText}>Delete account</Text>
        </Pressable>
      </ScrollView>

      <Modal visible={confirm} transparent animationType="fade" onRequestClose={() => setConfirm(false)}>
        <View style={styles.overlay}>
          <View style={styles.dialog} testID="delete-confirm-dialog">
            <Text style={styles.dialogTitle}>Delete account?</Text>
            <Text style={styles.dialogSub}>This permanently removes your account, saved projects, and order history.</Text>
            <Pressable testID="confirm-delete-button" style={styles.dialogDelete} onPress={doDelete} disabled={deleting}>
              {deleting ? <ActivityIndicator color={colors.onError} /> : <Text style={styles.dialogDeleteText}>Delete permanently</Text>}
            </Pressable>
            <Pressable testID="cancel-delete-button" style={styles.dialogCancel} onPress={() => setConfirm(false)} disabled={deleting}>
              <Text style={styles.dialogCancelText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl, gap: spacing.xl },
  avatarWrap: { alignItems: "center", gap: spacing.xs, marginTop: spacing.sm },
  avatar: { width: 84, height: 84, borderRadius: 42, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" },
  avatarText: { color: colors.onBrand, fontSize: 34, fontFamily: serif },
  name: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface, marginTop: spacing.sm },
  email: { fontSize: font.base, color: colors.onSurfaceTertiary },
  adminCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.brand, borderRadius: radius.md, padding: spacing.lg },
  adminTitle: { color: colors.onBrand, fontSize: font.lg, fontWeight: "700" },
  adminSub: { color: "rgba(249,249,247,0.7)", fontSize: font.sm, marginTop: 2 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", padding: spacing.lg, gap: spacing.md },
  rowBorder: { borderBottomWidth: 1, borderBottomColor: colors.divider },
  iconBox: { width: 38, height: 38, borderRadius: radius.sm, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowLabel: { flex: 1, fontSize: font.lg, color: colors.onSurface, fontWeight: "500" },
  logout: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, height: 52, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong },
  logoutText: { color: colors.onSurface, fontSize: font.lg, fontWeight: "600" },
  deleteRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, paddingVertical: spacing.xs },
  deleteText: { color: colors.error, fontSize: font.base, fontWeight: "600" },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  dialog: { width: "100%", backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md },
  dialogTitle: { fontSize: font.xl, fontFamily: serif, color: colors.onSurface },
  dialogSub: { fontSize: font.base, color: colors.onSurfaceTertiary, lineHeight: 20 },
  dialogDelete: { backgroundColor: colors.error, height: 50, borderRadius: radius.md, alignItems: "center", justifyContent: "center", marginTop: spacing.sm },
  dialogDeleteText: { color: colors.onError, fontSize: font.lg, fontWeight: "700" },
  dialogCancel: { height: 46, alignItems: "center", justifyContent: "center" },
  dialogCancelText: { color: colors.onSurface, fontSize: font.lg, fontWeight: "600" },
});
