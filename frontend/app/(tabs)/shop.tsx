import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { useRouter } from "expo-router";
import { colors } from "@/src/theme";

/** Legacy route kept as a redirect to the gallery Store. */
export default function ShopRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/(tabs)/store");
  }, [router]);
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
      <ActivityIndicator color={colors.brand} />
    </View>
  );
}
