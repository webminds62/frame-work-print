// Working project shared across the creation flow (avoids huge base64 in route params).
export type Project = {
  original: string;
  current: string;
  room: string;
  room_preview: string;
  material: string;
  size: string;
  frame: string;
  panel_key: string;
  price: number;
  project_id?: string;
  /** Gallery store selection */
  store_variant_id?: string;
  store_family_id?: string;
  store_family_name?: string;
  store_tier?: string;
  store_image?: string;
  has_mat?: boolean;
  // Legacy Printful fields (optional until checkout cutover)
  printful_variant_id?: number;
  printful_product_id?: number;
  printful_variant_name?: string;
  printful_variant_image?: string;
  printful_retail_price?: number;
};

/** Frame picked in the Store before a photo is chosen. */
export type FrameSelection = {
  store_variant_id: string;
  store_family_id: string;
  store_family_name: string;
  store_tier: string;
  store_image: string;
  material: string;
  size: string;
  size_label: string;
  frame: string;
  preview_frame: string;
  has_mat: boolean;
  panel_key: string;
  wall_hint: string;
  price: number;
};

let current: Project | null = null;
let pendingFrame: FrameSelection | null = null;

export function setPendingFrame(selection: FrameSelection | null) {
  pendingFrame = selection;
}

export function getPendingFrame(): FrameSelection | null {
  return pendingFrame;
}

export function clearPendingFrame() {
  pendingFrame = null;
}

export function newProject(image: string): Project {
  const frame = pendingFrame;
  current = {
    original: image,
    current: image,
    room: "living_room",
    room_preview: "",
    material: frame?.material || "canvas",
    size: frame?.size || "18x24",
    frame: frame?.frame || frame?.preview_frame || "wood",
    panel_key: frame?.panel_key || "single",
    price: frame?.price || 0,
    store_variant_id: frame?.store_variant_id,
    store_family_id: frame?.store_family_id,
    store_family_name: frame?.store_family_name,
    store_tier: frame?.store_tier,
    store_image: frame?.store_image,
    has_mat: frame?.has_mat,
    printful_variant_name: frame?.store_family_name,
    printful_variant_image: frame?.store_image,
    printful_retail_price: frame?.price,
  };
  return current;
}

export function getProject(): Project | null {
  return current;
}

export function updateProject(patch: Partial<Project>) {
  if (current) current = { ...current, ...patch };
}
