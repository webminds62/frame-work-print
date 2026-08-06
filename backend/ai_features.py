"""Provider-free image tools for the app's zero-cost AI demo mode."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_DEMO_EDGE = 1400
PRINT_SIZES = {
    "12x16": (12, 16),
    "18x24": (18, 24),
    "24x36": (24, 36),
    "30x40": (30, 40),
}

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


def _simple_background_cleanup(image: Image.Image) -> Image.Image:
    """Approximate a neutral backdrop using distance from the corner color."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((width - 1, 0)),
        rgb.getpixel((0, height - 1)),
        rgb.getpixel((width - 1, height - 1)),
    ]
    background = tuple(sum(pixel[channel] for pixel in corners) // 4 for channel in range(3))
    mask = Image.new("L", rgb.size)
    mask.putdata([
        0 if sum((channel - background[index]) ** 2 for index, channel in enumerate(pixel)) < 2600 else 255
        for pixel in rgb.get_flattened_data()
    ])
    mask = mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(2))
    neutral = Image.new("RGB", rgb.size, (244, 242, 238))
    return Image.composite(rgb, neutral, mask)


def demo_transform(image_base64: str, style: str, enhance: bool, remove_bg: bool) -> tuple[str, list[str]]:
    """Create a local style approximation for zero-cost UX testing."""
    image = _bounded(decode_image(image_base64))
    notices: list[str] = []
    if remove_bg:
        image = _simple_background_cleanup(image)
        notices.append("Demo mode approximates background cleanup; verify production subject masking separately.")
    if enhance:
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.06)
        image = ImageEnhance.Sharpness(image).enhance(1.15)

    if style == "watercolor":
        image = image.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.ModeFilter(5))
        image = ImageEnhance.Color(ImageOps.posterize(image, 5)).enhance(1.08)
    elif style == "bw":
        image = ImageOps.autocontrast(ImageOps.grayscale(image)).convert("RGB")
    elif style == "abstract":
        image = ImageEnhance.Color(ImageOps.posterize(image, 4)).enhance(1.35).filter(ImageFilter.SMOOTH)
    elif style == "minimal":
        image = ImageOps.posterize(image.filter(ImageFilter.GaussianBlur(1.2)), 4)
        image = ImageEnhance.Contrast(image).enhance(0.9)
    elif style == "luxury":
        image = Image.blend(image, Image.new("RGB", image.size, (205, 168, 120)), 0.08)
        image = ImageEnhance.Color(ImageEnhance.Contrast(image).enhance(1.12)).enhance(1.1)
    elif style == "canvas":
        image = ImageEnhance.Color(image.filter(ImageFilter.DETAIL)).enhance(0.95)
    else:
        image = ImageEnhance.Sharpness(ImageEnhance.Color(image).enhance(1.04)).enhance(1.1)

    notices.insert(0, "Local demo preview: no cloud AI call or API charge was made.")
    return encode_png(image), notices


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
    frame_colors = {
        "black": (27, 26, 25), "white": (247, 244, 236),
        "wood": (168, 113, 69), "brown": (126, 82, 49),
        "red_oak": (183, 124, 77), "none": (225, 220, 211),
        "metal": (192, 198, 202),
    }
    frame_outlines = {
        "black": (4, 4, 4), "white": (166, 158, 146),
        "wood": (100, 66, 38), "brown": (73, 46, 28),
        "red_oak": (112, 72, 43), "none": (225, 220, 211),
        "metal": (83, 91, 96),
    }
    preview_finish = "metal" if material == "metal" else frame
    border = 6 if preview_finish == "metal" else 0 if preview_finish == "none" else 18
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
            draw.rectangle(
                (px - border, y0 - border, px + panel_width + border, y0 + total_height + border),
                fill=frame_colors.get(preview_finish, frame_colors["wood"]),
                outline=frame_outlines.get(preview_finish, frame_outlines["wood"]),
                width=3,
            )
        scene.paste(crop, (px, y0))
    return encode_png(scene), ["Photorealistic local room preview: no cloud AI call or API charge was made."]


def analyze_print_quality(image_base64: str) -> dict[str, Any]:
    """Return a simple, explainable print-readiness assessment."""
    image = decode_image(image_base64)
    width, height = image.size
    short_px, long_px = sorted((width, height))
    score = 100
    issues: list[str] = []
    if short_px < 1200:
        score -= 35
        issues.append("Low resolution may look soft in larger prints.")
    elif short_px < 1800:
        score -= 15
        issues.append("Resolution is suitable for smaller prints; inspect larger sizes carefully.")

    sample = _bounded(image, 512).convert("L")
    edge_variance = ImageStat.Stat(sample.filter(ImageFilter.FIND_EDGES)).var[0]
    brightness = ImageStat.Stat(sample).mean[0]
    if edge_variance < 180:
        score -= 20
        issues.append("The image may be blurred or lack fine detail.")
    if brightness < 45:
        score -= 10
        issues.append("The image is very dark and may print with lost shadow detail.")
    elif brightness > 225:
        score -= 10
        issues.append("The image is very bright and may lose highlight detail.")

    recommended = [
        label for label, dimensions in PRINT_SIZES.items()
        if short_px >= min(dimensions) * 150 and long_px >= max(dimensions) * 150
    ]
    if not recommended:
        issues.append("Use a higher-resolution original before ordering a standard print size.")
    score = max(0, min(score, 100))
    rating = "Great" if score >= 85 else "Good" if score >= 65 else "Fair" if score >= 45 else "Needs attention"
    return {"score": score, "rating": rating, "width": width, "height": height, "recommended_sizes": recommended, "issues": issues}


def generation_cache_key(operation: str, image_base64: str, options: dict[str, Any]) -> str:
    """Build a stable key without retaining the source image in metadata."""
    digest = hashlib.sha256()
    digest.update(operation.encode("utf-8"))
    digest.update(b"\0")
    digest.update(image_base64.encode("utf-8"))
    digest.update(b"\0")
    digest.update(json.dumps(options, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()
