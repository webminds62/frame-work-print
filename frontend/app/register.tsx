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

export default function Register() {
  const { register } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!email || !password) { setError("Enter email and password"); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters"); return; }
    setLoading(true); setError("");
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await register(email.trim(), password, name.trim());
      router.replace("/(tabs)");
    } catch (e: any) { setError(e.message || "Registration failed"); }
    finally { setLoading(false); }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.root}>
      <ScrollView contentContainerStyle={[styles.form, { paddingTop: insets.top + spacing["2xl"] }]} keyboardShouldPersistTaps="handled">
        <Pressable testID="back-button" onPress={() => router.back()} style={styles.back}>
          <Feather name="chevron-left" size={26} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Create account</Text>
        <Text style={styles.sub}>Start turning photos into art.</Text>

        <Text style={styles.label}>Name</Text>
        <TextInput testID="register-name-input" style={styles.input} placeholder="Your name" placeholderTextColor={colors.muted} value={name} onChangeText={setName} />
        <Text style={styles.label}>Email</Text>
        <TextInput testID="register-email-input" style={styles.input} placeholder="you@example.com" placeholderTextColor={colors.muted} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
        <Text style={styles.label}>Password</Text>
        <TextInput testID="register-password-input" style={styles.input} placeholder="At least 6 characters" placeholderTextColor={colors.muted} secureTextEntry value={password} onChangeText={setPassword} />
        {!!error && <Text style={styles.error} testID="register-error">{error}</Text>}

        <Pressable testID="register-submit-button" style={styles.cta} onPress={submit} disabled={loading}>
          {loading ? <ActivityIndicator color={colors.onBrand} /> : <Text style={styles.ctaText}>Create Account</Text>}
        </Pressable>
        <Pressable testID="go-login-button" style={styles.link} onPress={() => router.replace("/login")}>
          <Text style={styles.linkText}>Already have an account? <Text style={styles.linkStrong}>Log in</Text></Text>
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
