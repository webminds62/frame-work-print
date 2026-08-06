import { storage } from "@/src/utils/storage";

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
export const TOKEN_KEY = "frameworks_token";

export type AIPreviewResponse = {
  image_base64: string;
  mode: "demo" | "cloud";
  cached: boolean;
  remaining_today: number | null;
  notices: string[];
};

export type PrintQualityResponse = {
  score: number;
  rating: "Great" | "Good" | "Fair" | "Needs attention";
  width: number;
  height: number;
  recommended_sizes: string[];
  issues: string[];
};

export type PrintfulCatalogVariant = {
  id: number;
  product_id: number;
  product_name: string;
  material: "canvas" | "poster";
  size_key: string;
  size_label: string;
  finish_key: string;
  finish_label: string;
  catalog_price: number;
  retail_price: number;
  currency: string;
  image: string;
  name: string;
  framed: boolean;
  in_stock: boolean;
};

export type PrintfulCatalogResponse = {
  variants: PrintfulCatalogVariant[];
  source: "printful_live" | "verified_snapshot";
  synced_at: string;
  orders_configured: boolean;
  store_context_configured: boolean;
  markup: number;
  note: string;
};

async function authHeaders() {
  const token = await storage.secureGet<string>(TOKEN_KEY, "");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T = any>(path: string, options: RequestInit = {}, auth = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (auth) Object.assign(headers, await authHeaders());
  const res = await fetch(`${BASE}/api${path}`, { ...options, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

export const api = {
  register: (email: string, password: string, name?: string) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password, name }) }, false),
  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false),
  appleLogin: (identity_token: string, name?: string, email?: string) =>
    request("/auth/apple", { method: "POST", body: JSON.stringify({ identity_token, name, email }) }, false),
  me: () => request("/auth/me"),
  deleteAccount: () => request("/auth/me", { method: "DELETE" }),
  transform: (image_base64: string, style: string, enhance: boolean, remove_bg: boolean) =>
    request<AIPreviewResponse>("/transform", { method: "POST", body: JSON.stringify({ image_base64, style, enhance, remove_bg }) }),
  roomPreview: (image_base64: string, room: string, frame: string, material: string, panels: number = 1) =>
    request<AIPreviewResponse>("/room-preview", { method: "POST", body: JSON.stringify({ image_base64, room, frame, material, panels }) }),
  printQuality: (image_base64: string) =>
    request<PrintQualityResponse>("/print-quality", { method: "POST", body: JSON.stringify({ image_base64 }) }),
  printfulCatalog: () => request<PrintfulCatalogResponse>("/printful/catalog"),
  saveProject: (p: any) => request("/projects", { method: "POST", body: JSON.stringify(p) }),
  listProjects: () => request("/projects"),
  deleteProject: (id: string) => request(`/projects/${id}`, { method: "DELETE" }),
  quote: (p: any) => request("/quote", { method: "POST", body: JSON.stringify(p) }),
  // Real Printful product-photo mockup for the exact material/size/frame. Requires
  // the project to already be saved server-side (project_id must exist in the DB).
  mockup: (project_id: string, material: string, size: string, frame: string, printful_variant_id: number) =>
    request("/mockup", { method: "POST", body: JSON.stringify({ project_id, material, size, frame, printful_variant_id }) }),
  // Server computes the price from the cart; the client can no longer set the amount.
  createPaymentIntent: (cart: any) =>
    request("/payments/create-intent", { method: "POST", body: JSON.stringify(cart) }),
  // The server retrieves the intent from Stripe before fulfilling the order.
  completePayment: (paymentIntentId: string) =>
    request(`/payments/complete/${paymentIntentId}`, { method: "POST" }),
  listOrders: () => request("/orders"),
  adminStats: () => request("/admin/stats"),
  adminOrders: () => request("/admin/orders"),
  adminUpdateOrder: (id: string, status: string) =>
    request(`/admin/orders/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
};
