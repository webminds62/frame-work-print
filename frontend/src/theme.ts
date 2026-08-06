import { Platform } from "react-native";

export const colors = {
  surface: "#F9F9F7",
  onSurface: "#1C1B1A",
  surfaceSecondary: "#FFFFFF",
  surfaceTertiary: "#EFEFEA",
  onSurfaceTertiary: "#6B655F",
  surfaceInverse: "#1C1B1A",
  onSurfaceInverse: "#F9F9F7",
  brand: "#1C1B1A",
  onBrand: "#F9F9F7",
  brandSecondary: "#8B7D72",
  brandTertiary: "#E3DDD8",
  onBrandTertiary: "#1C1B1A",
  success: "#4A5D4E",
  warning: "#C49A45",
  error: "#8C4A42",
  onError: "#FFFFFF",
  border: "rgba(28,27,26,0.08)",
  borderStrong: "rgba(28,27,26,0.20)",
  divider: "rgba(28,27,26,0.05)",
  muted: "#9A938C",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 };
export const radius = { sm: 0, md: 6, lg: 12, pill: 999 };
export const font = { sm: 12, base: 14, lg: 16, xl: 20, "2xl": 24, "3xl": 32, "4xl": 40 };

// Editorial serif for display via system fonts (no google-fonts package).
export const serif = Platform.select({ ios: "Georgia", android: "serif", default: "Georgia" });

export const STYLES = [
  { key: "canvas", label: "Canvas" },
  { key: "watercolor", label: "Watercolor" },
  { key: "bw", label: "B&W Fine Art" },
  { key: "abstract", label: "Abstract" },
  { key: "minimal", label: "Minimal" },
  { key: "luxury", label: "Luxury" },
  { key: "gallery", label: "Gallery" },
];

export const ROOMS = [
  { key: "living_room", label: "Living Room" },
  { key: "bedroom", label: "Bedroom" },
  { key: "office", label: "Office" },
  { key: "hallway", label: "Hallway" },
];

export const FRAMES = [
  { key: "wood", label: "Natural Wood", cost: 0 },
  { key: "black", label: "Matte Black", cost: 10 },
  { key: "white", label: "Gallery White", cost: 10 },
  { key: "none", label: "Frameless", cost: 0 },
];

export const MATERIALS = [
  { key: "canvas", label: "Canvas", base: 49, desc: "Textured gallery-wrapped canvas" },
  { key: "poster", label: "Fine Art Poster", base: 29, desc: "Museum-grade matte paper" },
  { key: "metal", label: "Metal", base: 89, desc: "Vivid HD aluminium print" },
  { key: "acrylic", label: "Acrylic", base: 119, desc: "Glossy premium acrylic glass" },
];

export const SIZES = [
  { key: "12x16", label: '12" × 16"', mult: 1.0 },
  { key: "18x24", label: '18" × 24"', mult: 1.5 },
  { key: "24x36", label: '24" × 36"', mult: 2.1 },
  { key: "30x40", label: '30" × 40"', mult: 2.8 },
];

export const PANELS = [
  { key: "single", label: "Single", count: 1, mult: 1.0 },
  { key: "triptych", label: "Triptych", count: 3, mult: 1.7 },
  { key: "quad", label: "4-Panel", count: 4, mult: 2.1 },
];

// Crop aspect presets (width / height)
export const ASPECTS = [
  { key: "3:4", label: "Portrait 3:4", ratio: 3 / 4 },
  { key: "2:3", label: "Portrait 2:3", ratio: 2 / 3 },
  { key: "1:1", label: "Square", ratio: 1 },
  { key: "4:3", label: "Landscape 4:3", ratio: 4 / 3 },
  { key: "3:2", label: "Landscape 3:2", ratio: 3 / 2 },
];

// Size recommendation by room
export const SIZE_RECOMMENDATION: Record<string, string> = {
  living_room: "24x36",
  bedroom: "18x24",
  office: "12x16",
  hallway: "18x24",
};

// Mirrors backend resolve_printful_variant/PRINTFUL_FRAMED_VARIANTS: only canvas/poster
// at these three sizes actually ship as a real framed product. Everything else
// (metal/acrylic, or 30x40) ships unframed regardless of the frame the user picked.
const FRAMED_MATERIALS = new Set(["canvas", "poster"]);
const FRAMED_SIZES = new Set(["12x16", "18x24", "24x36"]);
export function canBeFramed(materialKey: string, sizeKey: string): boolean {
  return FRAMED_MATERIALS.has(materialKey) && FRAMED_SIZES.has(sizeKey);
}

export function computePrice(materialKey: string, sizeKey: string, frameKey: string, panelKey: string = "single"): number {
  const m = MATERIALS.find((x) => x.key === materialKey) || MATERIALS[0];
  const s = SIZES.find((x) => x.key === sizeKey) || SIZES[0];
  const f = FRAMES.find((x) => x.key === frameKey) || FRAMES[0];
  const p = PANELS.find((x) => x.key === panelKey) || PANELS[0];
  const frameCost = canBeFramed(materialKey, sizeKey) ? f.cost : 0;
  return Math.round((m.base * s.mult * p.mult + frameCost * p.count) * 100) / 100;
}

export const IMAGES = {
  onboarding: "https://images.unsplash.com/photo-1562368764-651b0bba96af?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBtaW5pbWFsaXN0JTIwbGl2aW5nJTIwcm9vbSUyMGJsYW5rJTIwd2FsbHxlbnwwfHx8fDE3ODUzOTU4NDF8MA&ixlib=rb-4.1.0&q=85",
};
