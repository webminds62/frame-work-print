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




export type StoreCatalogFamily = {
  id: string;
  name: string;
  tagline: string;
  tier: "essential" | "gallery" | "atelier";
  tier_rank: 1 | 2 | 3;
  material: "poster" | "framed" | "canvas";
  frame_key: string;
  preview_frame: string;
  has_mat: boolean;
  base_price: number;
  image: string;
  swatch: string;
  size_keys: string[];
};

export type StoreCatalogVariant = {
  id: string;
  family_id: string;
  family_name: string;
  tagline: string;
  tier: "essential" | "gallery" | "atelier";
  tier_rank: 1 | 2 | 3;
  material: "poster" | "framed" | "canvas";
  frame_key: string;
  preview_frame: string;
  has_mat: boolean;
  size_key: string;
  size_label: string;
  orientation: "portrait" | "landscape" | "square";
  wall_hint: string;
  retail_price: number;
  image: string;
  swatch: string;
  panel_key: string;
  prodigi_sku?: string;
  prodigi_attributes?: Record<string, string>;
};

export type StoreCatalogResponse = {
  version: number;
  source: string;
  fulfillment: string;
  prodigi_configured: boolean;
  tier_meta: Record<string, { label: string; blurb: string; rank: number }>;
  sizes: Array<{ key: string; label: string; orientation: string; wall_hint: string; mult: number }>;
  families: StoreCatalogFamily[];
  variants: StoreCatalogVariant[];
  variant_count: number;
  family_count: number;
  note?: string;
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
  roomPreview: (image_base64: string, room: string, frame: string, material: string, panels: number = 1) =>
    request<AIPreviewResponse>("/room-preview", { method: "POST", body: JSON.stringify({ image_base64, room, frame, material, panels }) }),
  prodigiStatus: () => request("/prodigi/status"),
  storeCatalog: () => request<StoreCatalogResponse>("/catalog/store", {}, false),
  prodigiQuote: (p: any) => request("/prodigi/quote", { method: "POST", body: JSON.stringify(p) }),
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
