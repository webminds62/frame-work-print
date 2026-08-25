"""Provider-free image tools for the app's zero-cost AI demo mode."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageOps

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_DEMO_EDGE = 1400

ROOM_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "rooms"
ROOM_ASSETS = {
    "living_room": ROOM_ASSET_DIR / "living_room.jpg",
    "bedroom": ROOM_ASSET_DIR / "bedroom.jpg",
    "office": ROOM_ASSET_DIR / "office.jpg",
    "hallway": ROOM_ASSET_DIR / "hallway.jpg",
}
ROOM_ART_PLACEMENTS = {
    "living_room": (620, 390, 110),
    "bedroom": (600, 370, 110),
    "office": (600, 360, 125),
    "hallway": (560, 360, 120),
}


def decode_image(image_base64: str) -> Image.Image:
    """Decode and validate a client image without trusting its data-URI label."""
    payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Image must be valid base64") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be between 1 byte and 12 MB")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, ValueError) as exc:
        raise ValueError("Unsupported or damaged image") from exc


def encode_png(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _bounded(image: Image.Image, max_edge: int = MAX_DEMO_EDGE) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return copy


def demo_room_preview(
    image_base64: str,
    room: str,
    frame: str,
    material: str,
    panels: int,
) -> tuple[str, list[str]]:
    """Composite artwork into a bundled photorealistic room for free testing."""
    artwork = _bounded(decode_image(image_base64), 900)
    room_key = room if room in ROOM_ASSETS else "living_room"
    asset_path = ROOM_ASSETS[room_key]
    try:
        with Image.open(asset_path) as asset:
            scene = ImageOps.fit(asset.convert("RGB"), (1200, 900), method=Image.Resampling.LANCZOS)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Room background is unavailable: {asset_path.name}") from exc

    panel_count = max(1, min(int(panels or 1), 4))
    base_width, base_height, y0 = ROOM_ART_PLACEMENTS[room_key]
    total_width, total_height = (base_width, base_height) if panel_count == 1 else (min(base_width + 40, 660), base_height)
    gap = 18
    panel_width = (total_width - gap * (panel_count - 1)) // panel_count
    x0 = (scene.width - total_width) // 2
    # Normalize gallery store finishes -> paint keys
    finish_aliases = {
        "oak": "wood", "oak_deep": "wood", "oak_float": "wood",
        "brown": "wood", "red_oak": "wood", "natural": "wood",
        "walnut": "walnut",
        "black": "black", "black_deep": "black", "black_float": "black",
        "white": "white", "none": "none", "metal": "metal",
        "wood": "wood",
    }
    frame_colors = {
        "black": (23, 22, 21),
        "white": (247, 244, 236),
        "wood": (196, 165, 116),       # natural oak
        "walnut": (92, 64, 51),        # deep walnut
        "brown": (126, 82, 49),
        "red_oak": (183, 124, 77),
        "none": (225, 220, 211),
        "metal": (192, 198, 202),
    }
    frame_outlines = {
        "black": (5, 5, 5),
        "white": (166, 158, 146),
        "wood": (120, 90, 55),
        "walnut": (55, 35, 28),
        "brown": (73, 46, 28),
        "red_oak": (112, 72, 43),
        "none": (225, 220, 211),
        "metal": (83, 91, 96),
    }
    # Deeper profiles get a thicker moulding so Atelier reads premium on the wall
    deep = frame in {"oak_deep", "black_deep", "walnut", "oak_float", "black_float"}
    preview_finish = "metal" if material == "metal" else finish_aliases.get(frame or "wood", frame or "wood")
    if material == "canvas" and preview_finish == "none":
        border = 0
    elif preview_finish == "none":
        border = 0
    elif preview_finish == "metal":
        border = 6
    else:
        border = 28 if deep else 18
    fitted = ImageOps.fit(artwork, (total_width, total_height), method=Image.Resampling.LANCZOS)

    # Soft shadows make each panel sit naturally against the photographed wall.
    shadow_layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    for index in range(panel_count):
        left = index * (panel_width + gap)
        px = x0 + left
        shadow_draw.rectangle(
            (px - border + 7, y0 - border + 9, px + panel_width + border + 7, y0 + total_height + border + 9),
            fill=(20, 16, 12, 90),
        )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(12))
    scene = Image.alpha_composite(scene.convert("RGBA"), shadow_layer).convert("RGB")
    draw = ImageDraw.Draw(scene)

    for index in range(panel_count):
        left = index * (panel_width + gap)
        crop = fitted.crop((left, 0, left + panel_width, total_height))
        px = x0 + left
        if border:
            # Outer moulding
            draw.rectangle(
                (px - border, y0 - border, px + panel_width + border, y0 + total_height + border),
                fill=frame_colors.get(preview_finish, frame_colors["wood"]),
                outline=frame_outlines.get(preview_finish, frame_outlines["wood"]),
                width=3,
            )
            # Inner bevel highlight
            bevel = 4
            draw.rectangle(
                (px - border + bevel, y0 - border + bevel,
                 px + panel_width + border - bevel, y0 + total_height + border - bevel),
                outline=(255, 255, 255, 40) if preview_finish != "black" else (70, 70, 70),
                width=2,
            )
            # Museum mat for paper prints (not canvas wrap / frameless)
            mat = 14 if material != "canvas" and preview_finish != "none" else 0
            if mat:
                draw.rectangle(
                    (px - mat, y0 - mat, px + panel_width + mat, y0 + total_height + mat),
                    fill=(245, 242, 235),
                    outline=(220, 214, 204),
                    width=1,
                )
        scene.paste(crop, (px, y0))
    return encode_png(scene), ["Photorealistic local room preview: no cloud AI call or API charge was made."]


def generation_cache_key(operation: str, image_base64: str, options: dict[str, Any]) -> str:
    """Build a stable key without retaining the source image in metadata."""
    digest = hashlib.sha256()
    digest.update(operation.encode("utf-8"))
    digest.update(b"\0")
    digest.update(image_base64.encode("utf-8"))
    digest.update(b"\0")
    digest.update(json.dumps(options, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()
