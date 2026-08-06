import { useCallback, useState } from "react";
import { View, Text, StyleSheet, Pressable, ActivityIndicator, ScrollView, RefreshControl, Dimensions } from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useFocusEffect } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { api } from "@/src/api";
import { shareImage } from "@/src/utils/share";
import { colors, spacing, radius, font, serif } from "@/src/theme";

const CARD_W = (Dimensions.get("window").width - spacing.xl * 2 - spacing.md) / 2;

export default function Gallery() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try { setProjects(await api.listProjects()); } catch {}
    finally { setLoading(false); setRefreshing(false); }
  };
  useFocusEffect(useCallback(() => { load(); }, []));

  const remove = async (id: string) => {
    await api.deleteProject(id);
    setProjects((p) => p.filter((x) => x.id !== id));
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.md }]}>
      <View style={styles.header}>
        <Text style={styles.title}>Gallery</Text>
        <Text style={styles.sub}>{projects.length} saved pieces</Text>
      </View>
      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.onSurface} /></View>
      ) : projects.length === 0 ? (
        <View style={styles.center}>
          <Feather name="image" size={48} color={colors.borderStrong} />
          <Text style={styles.emptyTitle}>Your gallery is empty</Text>
          <Text style={styles.emptySub}>Create your first piece of wall art.</Text>
          <Pressable testID="empty-create-button" style={styles.emptyCta} onPress={() => router.push("/(tabs)")}>
            <Text style={styles.emptyCtaText}>Start creating</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.grid} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
          {projects.map((p) => (
            <View key={p.id} testID={`project-${p.id}`} style={styles.card}>
              <Image source={{ uri: p.room_preview || p.current }} style={styles.thumb} contentFit="cover" />
              <View style={styles.cardFooter}>
                <Text numberOfLines={1} style={styles.cardText}>{p.material || p.style} {p.size ? `· ${p.size}` : ""}</Text>
                <Pressable testID={`share-project-${p.id}`} hitSlop={8} onPress={() => shareImage(p.room_preview || p.current, "frameworks-art.jpg")}>
                  <Feather name="share" size={16} color={colors.brandSecondary} />
                </Pressable>
                <Pressable testID={`delete-project-${p.id}`} hitSlop={8} onPress={() => remove(p.id)}>
                  <Feather name="trash-2" size={16} color={colors.muted} />
                </Pressable>
              </View>
            </View>
          ))}
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
  emptyCta: { backgroundColor: colors.brand, borderRadius: radius.md, paddingHorizontal: spacing.xl, paddingVertical: spacing.md, marginTop: spacing.lg },
  emptyCtaText: { color: colors.onBrand, fontWeight: "600", fontSize: font.base },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", padding: spacing.xl, gap: spacing.md },
  card: { width: CARD_W, borderRadius: radius.md, overflow: "hidden", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md },
  thumb: { width: "100%", height: CARD_W },
  cardFooter: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: spacing.md, gap: spacing.sm },
  cardText: { flex: 1, fontSize: font.sm, color: colors.onSurfaceTertiary, textTransform: "capitalize" },
});
