import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Linking,
  ActivityIndicator,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import {
  clearPendingFrame,
  getPendingFrame,
  newProject,
  setPendingFrame,
  type FrameSelection,
} from "@/src/store";
import {
  ALL_STORE_VARIANTS,
  FRAME_FAMILIES,
  TIER_META,
  type CollectionTier,
  getFamily,
  variantsForFamily,
} from "@/src/catalog/store_skus";
import { colors, spacing, radius, font, serif, IMAGES } from "@/src/theme";

async function safeHaptic() {
  try {
    if (Platform.OS === "web") return;
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  } catch {
    /* ignore */
  }
}

function readFileAsDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string" && result.startsWith("data:")) resolve(result);
      else reject(new Error("Invalid image data"));
    };
    reader.onerror = () => reject(new Error("Could not read that image file."));
    reader.readAsDataURL(file);
  });
}

/** Default beautiful frame so upload is never blocked. */
function ensureDefaultFrame(): FrameSelection {
  const existing = getPendingFrame();
  if (existing) return existing;

  const family =
    getFamily("gallery-oak-mat") ||
    FRAME_FAMILIES.find((f) => f.tier === "gallery") ||
    FRAME_FAMILIES[0];
  const variant =
    variantsForFamily(family.id).find((v) => v.size_key === "18x24") ||
    variantsForFamily(family.id)[0] ||
    ALL_STORE_VARIANTS[0];

  const selection: FrameSelection = {
    store_variant_id: variant.id,
    store_family_id: family.id,
    store_family_name: family.name,
    store_tier: family.tier,
    store_image: family.image,
    material: family.material === "framed" ? "poster" : family.material,
    size: variant.size_key,
    size_label: variant.size_label,
    frame: family.frame_key,
    preview_frame: family.preview_frame,
    has_mat: family.has_mat,
    panel_key: "single",
    wall_hint: variant.wall_hint,
    price: variant.retail_price,
  };
  setPendingFrame(selection);
  return selection;
}

export default function Create() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [permMsg, setPermMsg] = useState("");
  const [frame, setFrame] = useState<FrameSelection | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const resolvePickRef = useRef<((uri: string | null) => void) | null>(null);

  useFocusEffect(
    useCallback(() => {
      setFrame(getPendingFrame());
      setPermMsg("");
    }, []),
  );

  // Mount permanent file inputs on web (most reliable picker)
  useEffect(() => {
    if (Platform.OS !== "web" || typeof document === "undefined") return;

    const makeInput = (capture?: string) => {
      const input = document.createElement("input");
      input.type = "file";
      // image/* + capture is required for iOS to offer Camera
      input.accept = "image/*";
      input.setAttribute("accept", "image/*");
      if (capture) {
        // Boolean capture + environment helps Android; iOS uses capture attribute
        input.capture = capture as any;
        input.setAttribute("capture", capture);
      }
      input.style.cssText =
        "position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0;overflow:hidden;";
      input.addEventListener("change", async () => {
        const file = input.files?.[0] || null;
        input.value = "";
        const done = resolvePickRef.current;
        resolvePickRef.current = null;
        if (!done) return;
        if (!file) {
          done(null);
          return;
        }
        try {
          const uri = await readFileAsDataUri(file);
          done(uri);
        } catch {
          done(null);
        }
      });
      document.body.appendChild(input);
      return input;
    };

    fileInputRef.current = makeInput();
    // Mobile Safari/Chrome: capture=environment opens the rear camera directly
    cameraInputRef.current = makeInput("environment");

    return () => {
      fileInputRef.current?.remove();
      cameraInputRef.current?.remove();
      fileInputRef.current = null;
      cameraInputRef.current = null;
    };
  }, []);

  const pickWithInput = (input: HTMLInputElement | null) =>
    new Promise<string | null>((resolve) => {
      if (!input) {
        resolve(null);
        return;
      }
      resolvePickRef.current = resolve;
      // Must run synchronously from click handler
      input.click();
      // If user cancels, change never fires — clear after delay
      window.setTimeout(() => {
        if (resolvePickRef.current === resolve) {
          resolvePickRef.current = null;
          resolve(null);
        }
      }, 60_000);
    });

  const startWithImage = async (uri: string) => {
    if (!uri || !uri.startsWith("data:")) {
      setPermMsg("That file could not be used. Try a JPG or PNG.");
      return;
    }
    // Always have a frame so the rest of the flow works
    const selected = ensureDefaultFrame();
    setFrame(selected);
    newProject(uri);
    await safeHaptic();
    setPermMsg("");
    router.push("/crop");
  };

  const takePhoto = async () => {
    setPermMsg("");
    setBusy(true);
    try {
      if (Platform.OS === "web") {
        const uri = await pickWithInput(cameraInputRef.current || fileInputRef.current);
        if (uri) await startWithImage(uri);
        else setPermMsg("Camera canceled. On a phone, tap Take a Photo and allow camera access.");
        return;
      }
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        if (!perm.canAskAgain) setPermMsg("settings");
        else setPermMsg("Camera access is needed to take a photo.");
        return;
      }
      const res = await ImagePicker.launchCameraAsync({
        quality: 0.85,
        base64: true,
        allowsEditing: false,
        exif: false,
      });
      if (!res.canceled && res.assets?.[0]) {
        const a = res.assets[0];
        const uri = a.base64
          ? `data:${a.mimeType || "image/jpeg"};base64,${a.base64}`
          : a.uri;
        await startWithImage(uri);
      }
    } catch (e: any) {
      setPermMsg(e?.message || "Could not open the camera.");
    } finally {
      setBusy(false);
    }
  };

  const pickFromGallery = async () => {
    setPermMsg("");
    setBusy(true);
    try {
      if (Platform.OS === "web") {
        const uri = await pickWithInput(fileInputRef.current);
        if (uri) await startWithImage(uri);
        else setPermMsg("No image selected. Click Upload again and choose a photo.");
        return;
      }
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        if (!perm.canAskAgain) setPermMsg("settings");
        else setPermMsg("Photo access is needed to upload an image.");
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.85,
        base64: true,
        allowsEditing: false,
        exif: false,
      });
      if (!res.canceled && res.assets?.[0]) {
        const a = res.assets[0];
        const uri = a.base64
          ? `data:${a.mimeType || "image/jpeg"};base64,${a.base64}`
          : a.uri;
        await startWithImage(uri);
      }
    } catch (e: any) {
      setPermMsg(e?.message || "Could not open your photos.");
    } finally {
      setBusy(false);
    }
  };

  const tierLabel = frame?.store_tier
    ? TIER_META[frame.store_tier as CollectionTier]?.label || frame.store_tier
    : "";

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.lg }]} testID="create-screen">
      <View style={styles.header}>
        <Text style={styles.kicker}>FRAME WORKS PRINTS</Text>
        <Text style={styles.title}>Add your photo</Text>
        <Text style={styles.sub}>
          {frame
            ? "Frame ready — take or upload a photo to continue."
            : "Take or upload a photo. You can change the frame anytime in Store."}
        </Text>
      </View>

      {frame ? (
        <Pressable
          testID="selected-frame-card"
          style={styles.frameCard}
          onPress={() => router.push("/(tabs)/store")}
        >
          <Image source={{ uri: frame.store_image }} style={styles.frameThumb} contentFit="cover" />
          <View style={{ flex: 1 }}>
            <Text style={styles.frameLabel}>{tierLabel || "Selected"}</Text>
            <Text style={styles.frameTitle} numberOfLines={2}>
              {frame.store_family_name}
            </Text>
            <Text style={styles.frameMeta}>
              {frame.size_label} · ${frame.price.toFixed(0)}
              {frame.has_mat ? " · Mat" : ""}
            </Text>
          </View>
          <Feather name="edit-2" size={18} color={colors.muted} />
        </Pressable>
      ) : (
        <Pressable
          testID="go-store-card"
          style={styles.shopPrompt}
          onPress={() => router.push("/(tabs)/store")}
        >
          <View style={styles.shopIcon}>
            <Feather name="aperture" size={22} color={colors.success} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.shopPromptTitle}>Optional: pick a frame first</Text>
            <Text style={styles.shopPromptSub}>
              Or upload now — we will use Natural Oak 18×24 by default
            </Text>
          </View>
          <Feather name="chevron-right" size={20} color={colors.muted} />
        </Pressable>
      )}

      <View style={styles.heroWrap}>
        <Image source={{ uri: IMAGES.onboarding }} style={styles.hero} contentFit="cover" />
      </View>

      <View style={styles.actions}>
        {/* Take a Photo — primary on phone; opens rear camera via capture on mobile browsers */}
        <Pressable
          testID="take-photo-button"
          style={[styles.primary, busy && styles.primaryDisabled]}
          onPress={takePhoto}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Take a photo with your camera"
        >
          {busy ? (
            <ActivityIndicator color={colors.onBrand} />
          ) : (
            <>
              <Feather name="camera" size={22} color={colors.onBrand} />
              <Text style={styles.primaryText}>Take a Photo</Text>
            </>
          )}
        </Pressable>

        <Pressable
          testID="upload-button"
          style={[styles.secondary, busy && styles.primaryDisabled]}
          onPress={pickFromGallery}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Upload a photo from your gallery"
        >
          <Feather name="image" size={20} color={colors.onSurface} />
          <Text style={styles.secondaryText}>Upload from Gallery</Text>
        </Pressable>

        <Text style={styles.hint}>
          {Platform.OS === "web"
            ? "On your phone: open this page in Safari or Chrome, then tap Take a Photo to use the camera."
            : "Use your camera or choose a photo from your library."}
        </Text>

        <Pressable
          testID="go-store-cta"
          style={styles.linkBtn}
          onPress={() => router.push("/(tabs)/store")}
        >
          <Text style={styles.linkText}>Browse frame gallery</Text>
        </Pressable>

        {frame && (
          <Pressable
            testID="change-frame-link"
            style={styles.changeFrame}
            onPress={() => {
              clearPendingFrame();
              setFrame(null);
              router.push("/(tabs)/store");
            }}
          >
            <Text style={styles.changeFrameText}>Change frame</Text>
          </Pressable>
        )}

        {permMsg === "settings" ? (
          <Pressable
            testID="open-settings-button"
            style={styles.settings}
            onPress={() => Linking.openSettings()}
          >
            <Text style={styles.settingsText}>Permission blocked — Open Settings</Text>
          </Pressable>
        ) : (
          !!permMsg && (
            <Text style={styles.perm} testID="upload-error">
              {permMsg}
            </Text>
          )
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  header: { gap: spacing.xs },
  kicker: { color: colors.brandSecondary, fontSize: font.sm, letterSpacing: 2, fontWeight: "700" },
  title: { fontSize: font["3xl"], fontFamily: serif, color: colors.onSurface },
  sub: { fontSize: font.base, color: colors.onSurfaceTertiary, lineHeight: 20 },
  frameCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  frameThumb: {
    width: 64,
    height: 80,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
  },
  frameLabel: {
    fontSize: font.sm,
    color: colors.success,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  frameTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, marginTop: 2 },
  frameMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  shopPrompt: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: "rgba(74,93,78,0.08)",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.success,
  },
  shopIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  shopPromptTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  shopPromptSub: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  heroWrap: {
    flex: 1,
    marginTop: spacing.lg,
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surfaceSecondary,
    minHeight: 100,
  },
  hero: { width: "100%", height: "100%" },
  actions: { gap: spacing.md, paddingVertical: spacing.xl },
  primary: {
    backgroundColor: colors.brand,
    height: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  primaryDisabled: { opacity: 0.55 },
  primaryText: { color: colors.onBrand, fontSize: font.lg, fontWeight: "600" },
  secondary: {
    backgroundColor: colors.surfaceSecondary,
    height: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  secondaryText: { color: colors.onSurface, fontSize: font.lg, fontWeight: "600" },
  linkBtn: { alignItems: "center", paddingVertical: spacing.sm },
  linkText: { color: colors.brandSecondary, fontSize: font.base, fontWeight: "700" },
  changeFrame: { alignItems: "center", paddingVertical: spacing.xs },
  changeFrameText: { color: colors.muted, fontSize: font.base, fontWeight: "600" },
  settings: {
    backgroundColor: "rgba(140,74,66,0.12)",
    padding: spacing.md,
    borderRadius: radius.md,
    alignItems: "center",
  },
  settingsText: { color: colors.error, fontWeight: "600" },
  perm: { color: colors.error, textAlign: "center", fontSize: font.base, lineHeight: 20 },
});
