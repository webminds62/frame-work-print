"""
P0 Bug Regression Tests — AI image-edit refactor (async litellm.aimage_edit → sync
litellm.image_edit inside asyncio.to_thread with a temp PNG file).

Scenarios (per review_request):
1. POST /api/transform  style=watercolor, enhance=true, remove_bg=false  → 200 + data:image/png;base64,...
2. POST /api/transform  style=gallery,   enhance=true, remove_bg=false  → 200 + valid image
3. POST /api/transform  style=gallery,   enhance=true, remove_bg=true   → 200 + valid image
4. POST /api/room-preview panels=1  → 200 + valid image
5. POST /api/room-preview panels=3  → 200 + valid image
6. Both endpoints must be auth-gated (401/403) without a valid Bearer token.

gpt-image-1 edits take 20-50s each — timeouts are set to 180s.
"""
import os
import base64
import io
import pytest
import requests
from PIL import Image as PILImage

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@frameworks.com"
DEMO_PASSWORD = "Password123"

AI_TIMEOUT = 180  # seconds

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
)
TINY_PNG_DATA_URI = f"data:image/png;base64,{TINY_PNG_B64}"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def demo_token(sess):
    r = sess.post(f"{API}/auth/login",
                  json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
                  timeout=30)
    if r.status_code == 200:
        return r.json()["token"]
    r = sess.post(f"{API}/auth/register",
                  json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "name": "Demo"},
                  timeout=30)
    assert r.status_code == 200, f"Demo auth failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def real_image_data_uri():
    """A real ~512x512 photograph, base64-encoded as data URI (what /style.tsx would send)."""
    url = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=512&h=512&fit=crop"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    # Re-encode to PNG to match what a phone would send.
    im = PILImage.open(io.BytesIO(r.content)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _assert_valid_image_response(r):
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:400]}"
    data = r.json()
    assert "image_base64" in data, f"Missing image_base64 key: {data}"
    img = data["image_base64"]
    assert img.startswith("data:image/"), f"Not a data URI: {img[:80]}"
    assert "base64," in img, f"Not a base64 data URI: {img[:80]}"
    payload = img.split("base64,", 1)[1]
    assert len(payload) > 5000, f"Payload too small ({len(payload)} chars) — likely not a real image"
    # Round-trip decode to confirm it's a real image
    raw = base64.b64decode(payload)
    im = PILImage.open(io.BytesIO(raw))
    im.verify()


# ---------- Auth gating ----------

class TestAuthGating:
    """/api/transform and /api/room-preview must reject unauthenticated calls."""

    def test_transform_no_auth_header(self, sess):
        r = sess.post(f"{API}/transform",
                      json={"image_base64": TINY_PNG_DATA_URI, "style": "gallery"},
                      timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_transform_invalid_bearer(self, sess):
        r = sess.post(f"{API}/transform",
                      headers={"Authorization": "Bearer not-a-real-token",
                               "Content-Type": "application/json"},
                      json={"image_base64": TINY_PNG_DATA_URI, "style": "gallery"},
                      timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_room_preview_no_auth_header(self, sess):
        r = sess.post(f"{API}/room-preview",
                      json={"image_base64": TINY_PNG_DATA_URI, "room": "living_room"},
                      timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_room_preview_invalid_bearer(self, sess):
        r = sess.post(f"{API}/room-preview",
                      headers={"Authorization": "Bearer not-a-real-token",
                               "Content-Type": "application/json"},
                      json={"image_base64": TINY_PNG_DATA_URI, "room": "living_room"},
                      timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"


# ---------- P0 bug fix: /api/transform ----------

class TestTransformStyles:
    """The P0 was that Apply AI Style / Clean up crashed the Emergent proxy. Confirm each variation now returns a real image."""

    @pytest.mark.timeout(AI_TIMEOUT + 30)
    def test_transform_watercolor_enhance_no_bg(self, sess, auth_headers, real_image_data_uri):
        payload = {
            "image_base64": real_image_data_uri,
            "style": "watercolor",
            "enhance": True,
            "remove_bg": False,
        }
        r = sess.post(f"{API}/transform", headers=auth_headers, json=payload, timeout=AI_TIMEOUT)
        _assert_valid_image_response(r)

    @pytest.mark.timeout(AI_TIMEOUT + 30)
    def test_transform_gallery_enhance_no_bg(self, sess, auth_headers, real_image_data_uri):
        payload = {
            "image_base64": real_image_data_uri,
            "style": "gallery",
            "enhance": True,
            "remove_bg": False,
        }
        r = sess.post(f"{API}/transform", headers=auth_headers, json=payload, timeout=AI_TIMEOUT)
        _assert_valid_image_response(r)

    @pytest.mark.timeout(AI_TIMEOUT + 30)
    def test_transform_remove_bg_true(self, sess, auth_headers, real_image_data_uri):
        """remove_bg=true is the second CTA that was broken on the Style screen."""
        payload = {
            "image_base64": real_image_data_uri,
            "style": "gallery",
            "enhance": True,
            "remove_bg": True,
        }
        r = sess.post(f"{API}/transform", headers=auth_headers, json=payload, timeout=AI_TIMEOUT)
        _assert_valid_image_response(r)


# ---------- P0 bug fix: /api/room-preview ----------

class TestRoomPreview:
    """Continue button on Style screen navigates to room preview — confirm both single- and multi-panel work."""

    @pytest.mark.timeout(AI_TIMEOUT + 30)
    def test_room_preview_panels_1(self, sess, auth_headers, real_image_data_uri):
        payload = {
            "image_base64": real_image_data_uri,
            "room": "living_room",
            "frame": "wood",
            "material": "canvas",
            "panels": 1,
        }
        r = sess.post(f"{API}/room-preview", headers=auth_headers, json=payload, timeout=AI_TIMEOUT)
        _assert_valid_image_response(r)

    @pytest.mark.timeout(AI_TIMEOUT + 30)
    def test_room_preview_panels_3(self, sess, auth_headers, real_image_data_uri):
        payload = {
            "image_base64": real_image_data_uri,
            "room": "living_room",
            "frame": "wood",
            "material": "canvas",
            "panels": 3,
        }
        r = sess.post(f"{API}/room-preview", headers=auth_headers, json=payload, timeout=AI_TIMEOUT)
        _assert_valid_image_response(r)
