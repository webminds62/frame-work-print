import { useState } from "react";
import {
  Text, TextInput, Pressable, StyleSheet, KeyboardAvoidingView,
  Platform, ScrollView, ActivityIndicator,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useAuth } from "@/src/context/AuthContext";
import AppleButton from "@/src/components/AppleButton";
import { colors, spacing, radius, font, serif } from "@/src/theme";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!email || !password) { setError("Enter email and password"); return; }
    setLoading(true); setError("");
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await login(email.trim(), password);
      router.replace("/(tabs)");
    } catch (e: any) { setError(e.message || "Login failed"); }
    finally { setLoading(false); }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.root}>
      <ScrollView contentContainerStyle={[styles.form, { paddingTop: insets.top + spacing["2xl"] }]} keyboardShouldPersistTaps="handled">
        <Pressable testID="back-button" onPress={() => router.back()} style={styles.back}>
          <Feather name="chevron-left" size={26} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Welcome back</Text>
        <Text style={styles.sub}>Sign in to continue creating.</Text>

        <Text style={styles.label}>Email</Text>
        <TextInput testID="login-email-input" style={styles.input} placeholder="you@example.com" placeholderTextColor={colors.muted} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
        <Text style={styles.label}>Password</Text>
        <TextInput testID="login-password-input" style={styles.input} placeholder="••••••••" placeholderTextColor={colors.muted} secureTextEntry value={password} onChangeText={setPassword} />
        {!!error && <Text style={styles.error} testID="login-error">{error}</Text>}

        <Pressable testID="login-submit-button" style={styles.cta} onPress={submit} disabled={loading}>
          {loading ? <ActivityIndicator color={colors.onBrand} /> : <Text style={styles.ctaText}>Log In</Text>}
        </Pressable>
        <Pressable testID="go-register-button" style={styles.link} onPress={() => router.replace("/register")}>
          <Text style={styles.linkText}>New here? <Text style={styles.linkStrong}>Create an account</Text></Text>
        </Pressable>
        <AppleButton />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  form: { padding: spacing.xl, gap: spacing.sm },
  back: { marginBottom: spacing.lg },
  title: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  sub: { fontSize: font.base, color: colors.onSurfaceTertiary, marginBottom: spacing.xl },
  label: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: spacing.sm, marginBottom: spacing.xs, fontWeight: "600" },
  input: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, paddingHorizontal: spacing.lg, height: 52, fontSize: font.lg, color: colors.onSurface, borderWidth: 1, borderColor: colors.border },
  error: { color: colors.error, marginTop: spacing.sm, fontSize: font.base },
  cta: { backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", marginTop: spacing.xl },
  ctaText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  link: { alignItems: "center", marginTop: spacing.lg },
  linkText: { color: colors.onSurfaceTertiary, fontSize: font.base },
  linkStrong: { color: colors.onSurface, fontWeight: "700" },
});
