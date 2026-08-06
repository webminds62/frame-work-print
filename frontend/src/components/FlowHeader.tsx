import { View, Text, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { colors, spacing, font } from "@/src/theme";

export default function FlowHeader({ title, step }: { title: string; step?: string }) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  return (
    <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable testID="flow-back" hitSlop={10} onPress={() => router.back()}>
        <Feather name="chevron-left" size={26} color={colors.onSurface} />
      </Pressable>
      <View style={{ alignItems: "center" }}>
        <Text style={styles.title}>{title}</Text>
        {!!step && <Text style={styles.step}>{step}</Text>}
      </View>
      <View style={{ width: 26 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  step: { fontSize: font.sm, color: colors.muted, marginTop: 1 },
});
