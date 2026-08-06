import { View, Text, StyleSheet, Pressable } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius, font, serif, IMAGES } from "@/src/theme";

export default function Onboarding() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  return (
    <View style={styles.root} testID="onboarding-screen">
      <Image source={{ uri: IMAGES.onboarding }} style={StyleSheet.absoluteFill} contentFit="cover" />
      <LinearGradient
        colors={["rgba(28,27,26,0.1)", "rgba(28,27,26,0.35)", "rgba(28,27,26,0.92)"]}
        locations={[0, 0.45, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={[styles.content, { paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + spacing.lg }]}>
        <Text style={styles.kicker}>FRAME WORKS PRINTS</Text>
        <View style={{ flex: 1 }} />
        <Text style={styles.title}>Turn your memories{"\n"}into art.</Text>
        <Text style={styles.sub}>
          Transform any photo into premium, gallery-quality wall art — preview it on your own walls before you order.
        </Text>
        <Pressable
          testID="get-started-button"
          style={styles.cta}
          onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); router.push("/register"); }}
        >
          <Text style={styles.ctaText}>Create Your Art</Text>
        </Pressable>
        <Pressable testID="signin-link" style={styles.signin} onPress={() => router.push("/login")}>
          <Text style={styles.signinText}>I already have an account</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surfaceInverse },
  content: { flex: 1, paddingHorizontal: spacing.xl },
  kicker: { color: "rgba(249,249,247,0.85)", fontSize: font.sm, letterSpacing: 3, fontWeight: "600" },
  title: { color: colors.onSurfaceInverse, fontSize: font["4xl"], fontFamily: serif, lineHeight: 46 },
  sub: { color: "rgba(249,249,247,0.85)", fontSize: font.lg, lineHeight: 24, marginTop: spacing.md },
  cta: { backgroundColor: colors.surface, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", marginTop: spacing.xl },
  ctaText: { color: colors.onSurface, fontSize: font.lg, fontWeight: "600" },
  signin: { alignItems: "center", paddingVertical: spacing.md, marginTop: spacing.xs },
  signinText: { color: "rgba(249,249,247,0.9)", fontSize: font.base },
});
