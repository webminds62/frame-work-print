import { useState } from "react";
import { View, Text, StyleSheet, Pressable, Linking, ActivityIndicator } from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { newProject } from "@/src/store";
import { colors, spacing, radius, font, serif, IMAGES } from "@/src/theme";

export default function Create() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [permMsg, setPermMsg] = useState("");

  const handleAsset = (a: ImagePicker.ImagePickerAsset) => {
    const uri = a.base64 ? `data:image/jpeg;base64,${a.base64}` : a.uri;
    newProject(uri);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push("/style");
  };

  const takePhoto = async () => {
    setPermMsg("");
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      if (!perm.canAskAgain) setPermMsg("settings");
      else setPermMsg("Camera access is needed to take a photo.");
      return;
    }
    setBusy(true);
    try {
      const res = await ImagePicker.launchCameraAsync({ quality: 0.7, base64: true, allowsEditing: true });
      if (!res.canceled && res.assets?.[0]) handleAsset(res.assets[0]);
    } finally { setBusy(false); }
  };

  const pickFromGallery = async () => {
    setPermMsg("");
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      if (!perm.canAskAgain) setPermMsg("settings");
      else setPermMsg("Photo access is needed to upload an image.");
      return;
    }
    setBusy(true);
    try {
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"], quality: 0.7, base64: true, allowsEditing: true,
      });
      if (!res.canceled && res.assets?.[0]) handleAsset(res.assets[0]);
    } finally { setBusy(false); }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.lg }]}>
      <View style={styles.header}>
        <Text style={styles.kicker}>FRAME WORKS PRINTS</Text>
        <Text style={styles.title}>Create wall art</Text>
        <Text style={styles.sub}>Start with a photo — we’ll turn it into premium art.</Text>
      </View>

      <View style={styles.heroWrap}>
        <Image source={{ uri: IMAGES.onboarding }} style={styles.hero} contentFit="cover" />
      </View>

      <View style={styles.actions}>
        <Pressable testID="take-photo-button" style={styles.primary} onPress={takePhoto} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.onBrand} /> : (
            <><Feather name="camera" size={20} color={colors.onBrand} /><Text style={styles.primaryText}>Take a Photo</Text></>
          )}
        </Pressable>
        <Pressable testID="upload-button" style={styles.secondary} onPress={pickFromGallery} disabled={busy}>
          <Feather name="image" size={20} color={colors.onSurface} />
          <Text style={styles.secondaryText}>Upload from Gallery</Text>
        </Pressable>

        {permMsg === "settings" ? (
          <Pressable testID="open-settings-button" style={styles.settings} onPress={() => Linking.openSettings()}>
            <Text style={styles.settingsText}>Permission blocked — Open Settings</Text>
          </Pressable>
        ) : !!permMsg && <Text style={styles.perm}>{permMsg}</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  header: { gap: spacing.xs },
  kicker: { color: colors.brandSecondary, fontSize: font.sm, letterSpacing: 2, fontWeight: "700" },
  title: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  sub: { fontSize: font.base, color: colors.onSurfaceTertiary },
  heroWrap: { flex: 1, marginVertical: spacing.xl, borderRadius: radius.lg, overflow: "hidden", backgroundColor: colors.surfaceTertiary },
  hero: { width: "100%", height: "100%" },
  actions: { gap: spacing.md, paddingBottom: spacing.xl },
  primary: { flexDirection: "row", gap: spacing.sm, backgroundColor: colors.brand, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  primaryText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  secondary: { flexDirection: "row", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, height: 56, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.borderStrong },
  secondaryText: { color: colors.onSurface, fontSize: font.lg, fontWeight: "600" },
  settings: { alignItems: "center", paddingVertical: spacing.sm },
  settingsText: { color: colors.error, fontSize: font.base, fontWeight: "600" },
  perm: { color: colors.onSurfaceTertiary, fontSize: font.base, textAlign: "center" },
});
