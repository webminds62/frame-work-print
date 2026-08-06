// Working project shared across the creation flow (avoids huge base64 in route params).
export type Project = {
  original: string;
  current: string;
  style: string;
  enhance: boolean;
  remove_bg: boolean;
  room: string;
  room_preview: string;
  material: string;
  size: string;
  frame: string;
  panel_key: string;
  price: number;
  project_id?: string;
  printful_variant_id?: number;
  printful_product_id?: number;
  printful_variant_name?: string;
  printful_variant_image?: string;
  printful_retail_price?: number;
};

let current: Project | null = null;

export function newProject(image: string): Project {
  current = {
    original: image,
    current: image,
    style: "gallery",
    enhance: true,
    remove_bg: false,
    room: "living_room",
    room_preview: "",
    material: "canvas",
    size: "18x24",
    frame: "wood",
    panel_key: "single",
    price: 0,
  };
  return current;
}

export function getProject(): Project | null {
  return current;
}

export function updateProject(patch: Partial<Project>) {
  if (current) current = { ...current, ...patch };
}
