import { Platform, Alert } from "react-native";
import * as Sharing from "expo-sharing";
import * as LegacyFS from "expo-file-system/legacy";

// Save/share an image (data-uri or file uri). On iOS the share sheet includes "Save Image".
export async function shareImage(dataUri: string, filename = "frameworks-art.jpg") {
  try {
    if (!dataUri) return;
    if (Platform.OS === "web") {
      if (typeof document !== "undefined") {
        const a = document.createElement("a");
        a.href = dataUri;
        a.download = filename;
        a.click();
      }
      return;
    }
    let fileUri = dataUri;
    if (dataUri.startsWith("data:")) {
      const b64 = dataUri.split(",")[1];
      fileUri = `${LegacyFS.cacheDirectory}${filename}`;
      await LegacyFS.writeAsStringAsync(fileUri, b64, { encoding: LegacyFS.EncodingType.Base64 });
    }
    if (!(await Sharing.isAvailableAsync())) {
      Alert.alert("Sharing unavailable", "Sharing isn't available on this device.");
      return;
    }
    await Sharing.shareAsync(fileUri, { mimeType: "image/jpeg", dialogTitle: "Share your wall art" });
  } catch (e: any) {
    Alert.alert("Couldn't share", e?.message || "Please try again.");
  }
}
