import base64
import hashlib
import io

import pytest
from PIL import Image, ImageDraw

from ai_features import (
    ROOM_ASSETS,
    analyze_print_quality,
    decode_image,
    demo_room_preview,
    demo_transform,
    generation_cache_key,
)


def image_uri(width: int = 640, height: int = 480) -> str:
    image = Image.new("RGB", (width, height), "#e8dfd2")
    draw = ImageDraw.Draw(image)
    for x in range(0, width, 24):
        draw.rectangle((x, 0, x + 11, height), fill="#355c7d")
    draw.ellipse((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill="#f67280")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


@pytest.mark.parametrize("style", ["gallery", "watercolor", "bw", "abstract", "minimal", "luxury", "canvas"])
def test_demo_transform_returns_valid_image_without_provider(style):
    result, notices = demo_transform(image_uri(), style, enhance=True, remove_bg=False)
    assert result.startswith("data:image/png;base64,")
    assert decode_image(result).size == (640, 480)
    assert "no cloud AI call" in notices[0]


def test_demo_background_cleanup_is_labeled_as_approximation():
    _, notices = demo_transform(image_uri(), "gallery", enhance=True, remove_bg=True)
    assert any("approximates background cleanup" in notice for notice in notices)


@pytest.mark.parametrize("panels", [1, 3, 4])
def test_demo_room_preview_is_rendered_locally(panels):
    result, notices = demo_room_preview(image_uri(), "living_room", "wood", "canvas", panels)
    assert decode_image(result).size == (1200, 900)
    assert "no cloud AI call" in notices[0]


@pytest.mark.parametrize("room", ["living_room", "bedroom", "office", "hallway"])
def test_room_preview_uses_bundled_photorealistic_asset(room):
    assert ROOM_ASSETS[room].is_file()
    with Image.open(ROOM_ASSETS[room]) as background:
        assert background.size == (1200, 900)

    result, notices = demo_room_preview(image_uri(), room, "wood", "canvas", 1)
    assert decode_image(result).size == (1200, 900)
    assert "Photorealistic local room preview" in notices[0]


def test_room_and_frame_options_produce_visibly_distinct_previews():
    room_hashes = {
        hashlib.sha256(decode_image(demo_room_preview(image_uri(), room, "wood", "canvas", 1)[0]).tobytes()).hexdigest()
        for room in ROOM_ASSETS
    }
    frame_hashes = {
        hashlib.sha256(decode_image(demo_room_preview(image_uri(), "living_room", frame, "canvas", 1)[0]).tobytes()).hexdigest()
        for frame in ("wood", "black", "white", "none")
    }
    assert len(room_hashes) == 4
    assert len(frame_hashes) == 4


def test_glossy_metal_room_preview_is_not_rendered_as_a_wood_frame():
    wood = decode_image(demo_room_preview(image_uri(), "living_room", "wood", "canvas", 1)[0])
    metal = decode_image(demo_room_preview(image_uri(), "living_room", "metal", "metal", 1)[0])
    assert hashlib.sha256(wood.tobytes()).hexdigest() != hashlib.sha256(metal.tobytes()).hexdigest()


def test_print_quality_recommends_sizes_supported_by_pixels():
    result = analyze_print_quality(image_uri(1800, 2400))
    assert result["width"] == 1800
    assert result["height"] == 2400
    assert "12x16" in result["recommended_sizes"]
    assert "18x24" not in result["recommended_sizes"]


def test_print_quality_warns_for_small_images():
    result = analyze_print_quality(image_uri(500, 500))
    assert result["score"] < 70
    assert result["recommended_sizes"] == []
    assert any("Low resolution" in issue for issue in result["issues"])


def test_cache_key_is_stable_and_option_sensitive():
    source = image_uri()
    first = generation_cache_key("transform", source, {"style": "gallery", "enhance": True})
    reordered = generation_cache_key("transform", source, {"enhance": True, "style": "gallery"})
    changed = generation_cache_key("transform", source, {"style": "bw", "enhance": True})
    assert first == reordered
    assert first != changed


def test_invalid_base64_is_rejected():
    with pytest.raises(ValueError, match="valid base64"):
        decode_image("data:image/png;base64,not-valid***")
