/**
 * Frame Works gallery catalog — curated home finishes, full size matrix.
 * Essential → Gallery → Atelier. Fulfillment SKUs (Prodigi) attach later.
 */

export type CollectionTier = "essential" | "gallery" | "atelier";
export type Orientation = "portrait" | "landscape" | "square";
export type MaterialKind = "poster" | "framed" | "canvas";

export type SizeDef = {
  key: string;
  label: string;
  orientation: Orientation;
  wall_hint: string;
  /** Relative price multiplier within a family */
  mult: number;
};

export type FrameFamily = {
  id: string;
  name: string;
  tagline: string;
  tier: CollectionTier;
  tier_rank: 1 | 2 | 3;
  material: MaterialKind;
  frame_key: string;
  /** Visual key for MultiPanelPreview */
  preview_frame: string;
  has_mat: boolean;
  base_price: number;
  /** Lifestyle / product image */
  image: string;
  swatch: string;
  size_keys: string[];
};

export type StoreVariant = {
  id: string;
  family_id: string;
  family_name: string;
  tagline: string;
  tier: CollectionTier;
  tier_rank: 1 | 2 | 3;
  material: MaterialKind;
  frame_key: string;
  preview_frame: string;
  has_mat: boolean;
  size_key: string;
  size_label: string;
  orientation: Orientation;
  wall_hint: string;
  retail_price: number;
  image: string;
  swatch: string;
  panel_key: string;
};

export const TIER_META: Record<
  CollectionTier,
  { label: string; blurb: string; rank: 1 | 2 | 3 }
> = {
  essential: {
    label: "Essential",
    blurb: "Clean profiles for desks, gifts, and first walls",
    rank: 1,
  },
  gallery: {
    label: "Gallery",
    blurb: "The living-room standard — warm woods & museum mats",
    rank: 2,
  },
  atelier: {
    label: "Atelier",
    blurb: "Statement pieces with deeper moulding and presence",
    rank: 3,
  },
};

/** Full size matrix — small shelf to feature wall + orientations */
export const STORE_SIZES: SizeDef[] = [
  { key: "8x10", label: '8" × 10"', orientation: "portrait", wall_hint: "Desk & shelf", mult: 0.7 },
  { key: "11x14", label: '11" × 14"', orientation: "portrait", wall_hint: "Hallway accent", mult: 0.85 },
  { key: "12x16", label: '12" × 16"', orientation: "portrait", wall_hint: "Bedroom", mult: 1.0 },
  { key: "16x20", label: '16" × 20"', orientation: "portrait", wall_hint: "Most popular", mult: 1.25 },
  { key: "18x24", label: '18" × 24"', orientation: "portrait", wall_hint: "Above a chair", mult: 1.5 },
  { key: "24x36", label: '24" × 36"', orientation: "portrait", wall_hint: "Above a sofa", mult: 2.1 },
  { key: "30x40", label: '30" × 40"', orientation: "portrait", wall_hint: "Feature wall", mult: 2.8 },
  { key: "10x8", label: '10" × 8"', orientation: "landscape", wall_hint: "Wide desk", mult: 0.7 },
  { key: "14x11", label: '14" × 11"', orientation: "landscape", wall_hint: "Hallway", mult: 0.85 },
  { key: "16x12", label: '16" × 12"', orientation: "landscape", wall_hint: "Bedroom", mult: 1.0 },
  { key: "20x16", label: '20" × 16"', orientation: "landscape", wall_hint: "Most popular", mult: 1.25 },
  { key: "24x18", label: '24" × 18"', orientation: "landscape", wall_hint: "Over console", mult: 1.5 },
  { key: "36x24", label: '36" × 24"', orientation: "landscape", wall_hint: "Above a sofa", mult: 2.1 },
  { key: "10x10", label: '10" × 10"', orientation: "square", wall_hint: "Shelf pair", mult: 0.8 },
  { key: "12x12", label: '12" × 12"', orientation: "square", wall_hint: "Gallery start", mult: 0.95 },
  { key: "16x16", label: '16" × 16"', orientation: "square", wall_hint: "Balanced wall", mult: 1.2 },
  { key: "20x20", label: '20" × 20"', orientation: "square", wall_hint: "Statement square", mult: 1.55 },
];

const SIZE_MAP = Object.fromEntries(STORE_SIZES.map((s) => [s.key, s]));

const IMG = {
  black:
    "https://images.unsplash.com/photo-1513519245088-0e12902e35ca?auto=format&fit=crop&w=800&q=80",
  oak: "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?auto=format&fit=crop&w=800&q=80",
  walnut:
    "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=800&q=80",
  white:
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=800&q=80",
  canvas:
    "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?auto=format&fit=crop&w=800&q=80",
  poster:
    "https://images.unsplash.com/photo-1513364776144-60967b0f800f?auto=format&fit=crop&w=800&q=80",
  floater:
    "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?auto=format&fit=crop&w=800&q=80",
};

const portraitCore = ["8x10", "11x14", "12x16", "16x20", "18x24", "24x36"];
const portraitFull = [...portraitCore, "30x40"];
const landscapeCore = ["10x8", "14x11", "16x12", "20x16", "24x18", "36x24"];
const squareCore = ["10x10", "12x12", "16x16", "20x20"];
const essentialPortrait = ["8x10", "11x14", "12x16", "16x20", "18x24"];
const atelierPortrait = ["16x20", "18x24", "24x36", "30x40"];
const canvasSizes = ["12x16", "16x20", "18x24", "24x36", "16x16", "20x20", "20x16", "36x24"];

/** Hero frame families — every option is hang-at-home beautiful */
export const FRAME_FAMILIES: FrameFamily[] = [
  {
    id: "essential-slim-black",
    name: "Slim Matte Black",
    tagline: "Gallery classic for any wall color",
    tier: "essential",
    tier_rank: 1,
    material: "framed",
    frame_key: "black",
    preview_frame: "black",
    has_mat: true,
    base_price: 39,
    image: IMG.black,
    swatch: "#171615",
    size_keys: [...essentialPortrait, "10x8", "14x11", "16x12"],
  },
  {
    id: "essential-slim-white",
    name: "Gallery White",
    tagline: "Airy profile for light, coastal rooms",
    tier: "essential",
    tier_rank: 1,
    material: "framed",
    frame_key: "white",
    preview_frame: "white",
    has_mat: true,
    base_price: 39,
    image: IMG.white,
    swatch: "#F7F4EC",
    size_keys: [...essentialPortrait, "10x8", "16x12"],
  },
  {
    id: "essential-matte-poster",
    name: "Matte Fine Art Poster",
    tagline: "Museum paper, unframed — clean & minimal",
    tier: "essential",
    tier_rank: 1,
    material: "poster",
    frame_key: "none",
    preview_frame: "none",
    has_mat: false,
    base_price: 29,
    image: IMG.poster,
    swatch: "#EFEFEA",
    size_keys: [...essentialPortrait, "10x8", "20x16", "24x18"],
  },
  {
    id: "essential-thin-canvas",
    name: "Studio Canvas",
    tagline: "Gallery wrap without a frame — easy modern",
    tier: "essential",
    tier_rank: 1,
    material: "canvas",
    frame_key: "none",
    preview_frame: "none",
    has_mat: false,
    base_price: 49,
    image: IMG.canvas,
    swatch: "#C4B8A8",
    size_keys: ["12x16", "16x20", "18x24", "16x16", "20x16"],
  },
  {
    id: "gallery-oak-mat",
    name: "Natural Oak · Museum Mat",
    tagline: "Warm wood that pairs with light floors",
    tier: "gallery",
    tier_rank: 2,
    material: "framed",
    frame_key: "oak",
    preview_frame: "wood",
    has_mat: true,
    base_price: 79,
    image: IMG.oak,
    swatch: "#C4A574",
    size_keys: [...portraitFull, ...landscapeCore.slice(0, 5)],
  },
  {
    id: "gallery-black-mat",
    name: "Matte Black · Museum Mat",
    tagline: "The living-room standard",
    tier: "gallery",
    tier_rank: 2,
    material: "framed",
    frame_key: "black",
    preview_frame: "black",
    has_mat: true,
    base_price: 75,
    image: IMG.black,
    swatch: "#171615",
    size_keys: [...portraitFull, ...landscapeCore.slice(0, 5)],
  },
  {
    id: "gallery-white-mat",
    name: "Soft White · Ivory Mat",
    tagline: "Bright rooms and soft family photos",
    tier: "gallery",
    tier_rank: 2,
    material: "framed",
    frame_key: "white",
    preview_frame: "white",
    has_mat: true,
    base_price: 75,
    image: IMG.white,
    swatch: "#F7F4EC",
    size_keys: [...portraitCore, "10x8", "20x16", "24x18"],
  },
  {
    id: "gallery-canvas-wrap",
    name: "Gallery Canvas Wrap",
    tagline: "Textured canvas, no glare — modern classic",
    tier: "gallery",
    tier_rank: 2,
    material: "canvas",
    frame_key: "none",
    preview_frame: "none",
    has_mat: false,
    base_price: 69,
    image: IMG.canvas,
    swatch: "#BFA890",
    size_keys: canvasSizes,
  },
  {
    id: "gallery-black-floater",
    name: "Black Floater Canvas",
    tagline: "Canvas floats inside a slim black reveal",
    tier: "gallery",
    tier_rank: 2,
    material: "canvas",
    frame_key: "black_float",
    preview_frame: "black",
    has_mat: false,
    base_price: 89,
    image: IMG.floater,
    swatch: "#1C1B1A",
    size_keys: ["16x20", "18x24", "24x36", "16x16", "20x20", "20x16", "36x24"],
  },
  {
    id: "atelier-walnut-mat",
    name: "Walnut Gallery · Deep Profile",
    tagline: "Rich wood for statement walls and gifts",
    tier: "atelier",
    tier_rank: 3,
    material: "framed",
    frame_key: "walnut",
    preview_frame: "wood",
    has_mat: true,
    base_price: 129,
    image: IMG.walnut,
    swatch: "#5C4033",
    size_keys: [...atelierPortrait, "20x16", "24x18", "36x24", "20x20"],
  },
  {
    id: "atelier-oak-deep",
    name: "Deep Oak · Wide Mat",
    tagline: "Architectural presence above a sofa",
    tier: "atelier",
    tier_rank: 3,
    material: "framed",
    frame_key: "oak_deep",
    preview_frame: "wood",
    has_mat: true,
    base_price: 139,
    image: IMG.oak,
    swatch: "#A87345",
    size_keys: ["18x24", "24x36", "30x40", "24x18", "36x24"],
  },
  {
    id: "atelier-black-deep",
    name: "Deep Matte Black · Wide Mat",
    tagline: "Museum weight for large portraits",
    tier: "atelier",
    tier_rank: 3,
    material: "framed",
    frame_key: "black_deep",
    preview_frame: "black",
    has_mat: true,
    base_price: 135,
    image: IMG.black,
    swatch: "#0E0D0C",
    size_keys: ["18x24", "24x36", "30x40", "36x24", "20x20"],
  },
  {
    id: "atelier-oak-floater",
    name: "Oak Floater Canvas",
    tagline: "Warm wood channel around gallery canvas",
    tier: "atelier",
    tier_rank: 3,
    material: "canvas",
    frame_key: "oak_float",
    preview_frame: "wood",
    has_mat: false,
    base_price: 149,
    image: IMG.floater,
    swatch: "#C4A574",
    size_keys: ["18x24", "24x36", "30x40", "20x20", "36x24"],
  },
];

function priceFor(family: FrameFamily, sizeKey: string): number {
  const size = SIZE_MAP[sizeKey];
  const mult = size?.mult ?? 1;
  return Math.round(family.base_price * mult);
}

/** Every sellable variant (family × size). Well over 20 options. */
export function buildStoreVariants(panel_key: string = "single"): StoreVariant[] {
  const out: StoreVariant[] = [];
  for (const family of FRAME_FAMILIES) {
    for (const size_key of family.size_keys) {
      const size = SIZE_MAP[size_key];
      if (!size) continue;
      out.push({
        id: `${family.id}__${size_key}`,
        family_id: family.id,
        family_name: family.name,
        tagline: family.tagline,
        tier: family.tier,
        tier_rank: family.tier_rank,
        material: family.material,
        frame_key: family.frame_key,
        preview_frame: family.preview_frame,
        has_mat: family.has_mat,
        size_key,
        size_label: size.label,
        orientation: size.orientation,
        wall_hint: size.wall_hint,
        retail_price: priceFor(family, size_key),
        image: family.image,
        swatch: family.swatch,
        panel_key,
      });
    }
  }
  return out.sort((a, b) => a.retail_price - b.retail_price || a.tier_rank - b.tier_rank);
}

export const ALL_STORE_VARIANTS = buildStoreVariants("single");

export function getFamily(id: string): FrameFamily | undefined {
  return FRAME_FAMILIES.find((f) => f.id === id);
}

export function variantsForFamily(familyId: string, panel_key: string = "single"): StoreVariant[] {
  return buildStoreVariants(panel_key).filter((v) => v.family_id === familyId);
}

export function getVariant(id: string): StoreVariant | undefined {
  return ALL_STORE_VARIANTS.find((v) => v.id === id);
}

export function sizesForFamily(
  familyId: string,
  orientation?: Orientation | "all",
): SizeDef[] {
  const family = getFamily(familyId);
  if (!family) return [];
  return family.size_keys
    .map((k) => SIZE_MAP[k])
    .filter(Boolean)
    .filter((s) => !orientation || orientation === "all" || s.orientation === orientation) as SizeDef[];
}
