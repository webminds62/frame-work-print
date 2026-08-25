"""Backend tests for FrameWorks Prints: auth, admin, projects, orders, AI room-preview."""
import os
import uuid
import base64
import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# Tiny 1x1 PNG (data URI) — used to satisfy schema; real image is used only for AI tests.
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
)
TINY_PNG = f"data:image/png;base64,{TINY_PNG_B64}"

ADMIN_EMAIL = "admin@frameworks.com"
ADMIN_PASSWORD = "Admin12345"
DEMO_EMAIL = "demo@frameworks.com"
DEMO_PASSWORD = "Password123"

SAMPLE_IMAGE_URL = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=600"


@pytest.fixture(scope="session")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def demo_token(sess):
    r = sess.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=30)
    if r.status_code == 200:
        return r.json()["token"]
    r = sess.post(f"{API}/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "name": "Demo"}, timeout=30)
    assert r.status_code == 200, f"Demo register failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin_token(sess):
    r = sess.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def real_image_b64():
    r = requests.get(SAMPLE_IMAGE_URL, timeout=30)
    r.raise_for_status()
    return "data:image/jpeg;base64," + base64.b64encode(r.content).decode()


# ---------- Health ----------
class TestHealth:
    def test_root(self, sess):
        r = sess.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert "message" in r.json()


# ---------- Auth ----------
class TestAuth:
    def test_register_login_flow(self, sess):
        email = f"test_{uuid.uuid4().hex[:8]}@frameworks.com"
        r = sess.post(f"{API}/auth/register", json={"email": email, "password": "Testpass1", "name": "Tester"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and "user" in data
        assert data["user"]["email"] == email
        assert data["user"]["is_admin"] is False

        # Duplicate register
        r2 = sess.post(f"{API}/auth/register", json={"email": email, "password": "Testpass1"}, timeout=15)
        assert r2.status_code == 400

        # Login
        r3 = sess.post(f"{API}/auth/login", json={"email": email, "password": "Testpass1"}, timeout=15)
        assert r3.status_code == 200

        # Wrong password
        r4 = sess.post(f"{API}/auth/login", json={"email": email, "password": "bad"}, timeout=15)
        assert r4.status_code == 401

        # Cleanup: delete this account so DB stays tidy
        h = {"Authorization": f"Bearer {r3.json()['token']}", "Content-Type": "application/json"}
        sess.delete(f"{API}/auth/me", headers=h, timeout=15)

    def test_me_requires_auth(self, sess):
        r = sess.get(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)

    def test_me_with_token(self, sess, demo_headers):
        r = sess.get(f"{API}/auth/me", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL

    def test_me_invalid_token(self, sess):
        r = sess.get(f"{API}/auth/me", headers={"Authorization": "Bearer bad.tok.en"}, timeout=15)
        assert r.status_code == 401


# ---------- Account deletion cascade ----------
class TestAccountDeletion:
    def test_delete_account_requires_auth(self, sess):
        r = sess.delete(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)

    def test_delete_cascades_projects_and_orders(self, sess):
        email = f"test_del_{uuid.uuid4().hex[:8]}@frameworks.com"
        r = sess.post(f"{API}/auth/register", json={"email": email, "password": "Testpass1", "name": "Del"}, timeout=15)
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}

        # Create a project
        rp = sess.post(f"{API}/projects", headers=h,
                       json={"original": TINY_PNG, "current": TINY_PNG, "style": "canvas"}, timeout=15)
        assert rp.status_code == 200
        pid = rp.json()["id"]

        # Create an order
        ro = sess.post(f"{API}/orders", headers=h, json={
            "image_base64": TINY_PNG, "style": "canvas", "material": "canvas",
            "size": "16x20", "frame": "wood", "price": 79.0,
            "recipient": {"name": "Test User", "address1": "1 Main", "city": "Austin",
                          "state_code": "TX", "country_code": "US", "zip": "78701"},
        }, timeout=15)
        assert ro.status_code == 200

        # Delete account
        rdel = sess.delete(f"{API}/auth/me", headers=h, timeout=15)
        assert rdel.status_code == 200
        assert rdel.json().get("ok") is True

        # Login should fail (user gone)
        rl = sess.post(f"{API}/auth/login", json={"email": email, "password": "Testpass1"}, timeout=15)
        assert rl.status_code == 401

        # Re-register with same email should be free
        rr = sess.post(f"{API}/auth/register", json={"email": email, "password": "Testpass1"}, timeout=15)
        assert rr.status_code == 200
        h2 = {"Authorization": f"Bearer {rr.json()['token']}", "Content-Type": "application/json"}

        # Projects for the new (fresh) user should be empty (cascade worked)
        rlp = sess.get(f"{API}/projects", headers=h2, timeout=15)
        assert rlp.status_code == 200
        assert not any(p["id"] == pid for p in rlp.json())

        # And orders empty
        rlo = sess.get(f"{API}/orders", headers=h2, timeout=15)
        assert rlo.status_code == 200
        assert rlo.json() == [] or not any(o.get("project_id") == pid for o in rlo.json())

        # Cleanup
        sess.delete(f"{API}/auth/me", headers=h2, timeout=15)


# ---------- Projects CRUD ----------
class TestProjects:
    def test_projects_require_auth(self, sess):
        r = sess.get(f"{API}/projects", timeout=15)
        assert r.status_code in (401, 403)

    def test_save_list_delete_project(self, sess, demo_headers):
        r = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "watercolor",
            "room": "living_room", "material": "canvas", "size": "16x20",
            "frame": "wood", "price": 89.0,
        }, timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]
        assert r.json()["style"] == "watercolor"
        assert "_id" not in r.json()

        r2 = sess.get(f"{API}/projects", headers=demo_headers, timeout=15)
        assert r2.status_code == 200
        assert any(p["id"] == pid for p in r2.json())

        r3 = sess.delete(f"{API}/projects/{pid}", headers=demo_headers, timeout=15)
        assert r3.status_code == 200

        r4 = sess.get(f"{API}/projects", headers=demo_headers, timeout=15)
        assert not any(p["id"] == pid for p in r4.json())

        r5 = sess.delete(f"{API}/projects/{uuid.uuid4()}", headers=demo_headers, timeout=15)
        assert r5.status_code == 404


# ---------- Orders (user) ----------
class TestOrdersUser:
    def test_orders_require_auth(self, sess):
        r = sess.get(f"{API}/orders", timeout=15)
        assert r.status_code in (401, 403)

    def test_create_and_list_order(self, sess, demo_headers):
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "canvas",
            "size": "16x20", "frame": "wood", "price": 99.0,
            "recipient": {"name": "Demo User", "address1": "1 Main", "city": "Austin",
                          "state_code": "TX", "country_code": "US", "zip": "78701"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "received"
        assert o["price"] == 99.0
        assert o["recipient"]["city"] == "Austin"
        assert "_id" not in o
        oid = o["id"]

        r2 = sess.get(f"{API}/orders", headers=demo_headers, timeout=15)
        assert r2.status_code == 200
        assert any(x["id"] == oid for x in r2.json())


# ---------- Admin ----------
class TestAdmin:
    def test_admin_login(self, sess):
        r = sess.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["is_admin"] is True

    def test_admin_stats(self, sess, admin_headers):
        r = sess.get(f"{API}/admin/stats", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("total_orders", "revenue", "total_users", "total_projects"):
            assert k in data
        assert isinstance(data["total_orders"], int)
        assert isinstance(data["total_users"], int)

    def test_admin_orders_list(self, sess, admin_headers):
        r = sess.get(f"{API}/admin/orders", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        # All admin orders should be FrameWorks docs (have `material` field)
        for o in r.json():
            assert "material" in o, f"Admin listed non-FrameWorks doc: {o.get('id')}"

    def test_admin_update_order_status(self, sess, demo_headers, admin_headers):
        # Create an order as demo user
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "poster",
            "size": "12x16", "frame": "black", "price": 49.0,
            "recipient": {"name": "Demo", "address1": "1 Main", "city": "NYC",
                          "state_code": "NY", "country_code": "US", "zip": "10001"},
        }
        rc = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=15)
        assert rc.status_code == 200
        oid = rc.json()["id"]

        # Admin updates status
        ru = sess.patch(f"{API}/admin/orders/{oid}", headers=admin_headers,
                        json={"status": "in_production"}, timeout=15)
        assert ru.status_code == 200
        assert ru.json().get("ok") is True

        # Verify persistence via admin list
        rl = sess.get(f"{API}/admin/orders", headers=admin_headers, timeout=15)
        found = [o for o in rl.json() if o["id"] == oid]
        assert found and found[0]["status"] == "in_production"

        # Non-existent id -> 404
        rnf = sess.patch(f"{API}/admin/orders/{uuid.uuid4()}", headers=admin_headers,
                         json={"status": "shipped"}, timeout=15)
        assert rnf.status_code == 404

    def test_non_admin_blocked(self, sess, demo_headers):
        r1 = sess.get(f"{API}/admin/stats", headers=demo_headers, timeout=15)
        assert r1.status_code == 403
        r2 = sess.get(f"{API}/admin/orders", headers=demo_headers, timeout=15)
        assert r2.status_code == 403
        r3 = sess.patch(f"{API}/admin/orders/{uuid.uuid4()}", headers=demo_headers,
                        json={"status": "shipped"}, timeout=15)
        assert r3.status_code == 403


# ---------- AI (slow, real gpt-image-1 via Emergent proxy) ----------
class TestAI:
    def test_room_preview_requires_auth(self, sess):
        r = sess.post(f"{API}/room-preview", json={"image_base64": TINY_PNG, "room": "living_room"}, timeout=15)
        assert r.status_code in (401, 403)

    @pytest.mark.timeout(120)
    def test_room_preview_generates_image(self, sess, demo_headers, real_image_b64):
        payload = {"image_base64": real_image_b64, "room": "living_room", "frame": "wood", "material": "canvas"}
        r = sess.post(f"{API}/room-preview", headers=demo_headers, json=payload, timeout=120)
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            data = r.json()
            assert "image_base64" in data
            assert data["image_base64"].startswith("data:image")
            assert len(data["image_base64"]) > 1000
        else:
            pytest.skip(f"AI provider returned 502: {r.text}")


# ---------- Multi-panel + panel_key persistence (Projects + Orders) ----------
class TestPanelsPersistence:
    def test_project_persists_panels_and_panel_key(self, sess, demo_headers):
        r = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "canvas",
            "room": "living_room", "material": "canvas", "size": "18x24",
            "frame": "wood", "panels": 3, "panel_key": "triptych-3", "price": 219.0,
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["panels"] == 3
        assert body["panel_key"] == "triptych-3"
        pid = body["id"]

        # GET verifies persistence
        rl = sess.get(f"{API}/projects", headers=demo_headers, timeout=15)
        assert rl.status_code == 200
        found = [p for p in rl.json() if p["id"] == pid]
        assert found, "created project not returned"
        assert found[0]["panels"] == 3
        assert found[0]["panel_key"] == "triptych-3"

        # Cleanup
        sess.delete(f"{API}/projects/{pid}", headers=demo_headers, timeout=15)

    def test_project_defaults_panels_to_1(self, sess, demo_headers):
        r = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "canvas",
        }, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("panels") == 1
        sess.delete(f"{API}/projects/{body['id']}", headers=demo_headers, timeout=15)

    def test_order_persists_panels_and_panel_key(self, sess, demo_headers):
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "canvas",
            "size": "24x36", "frame": "black", "panels": 4, "panel_key": "quad-4", "price": 349.0,
            "recipient": {"name": "P4 Buyer", "address1": "9 Panel Rd", "city": "Austin",
                          "state_code": "TX", "country_code": "US", "zip": "78702"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["panels"] == 4
        assert body["panel_key"] == "quad-4"
        oid = body["id"]

        rl = sess.get(f"{API}/orders", headers=demo_headers, timeout=15)
        assert rl.status_code == 200
        found = [o for o in rl.json() if o["id"] == oid]
        assert found and found[0]["panels"] == 4 and found[0]["panel_key"] == "quad-4"


# ---------- Public project image (unauthenticated) ----------
class TestPublicImage:
    def test_public_project_image_returns_bytes(self, sess, demo_headers, real_image_b64):
        # Create a project owned by demo user, using real image so PIL slice works
        r = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": real_image_b64, "current": real_image_b64, "style": "canvas",
        }, timeout=30)
        assert r.status_code == 200
        pid = r.json()["id"]
        try:
            # No auth required
            rp = requests.get(f"{API}/public/project/{pid}", timeout=15)
            assert rp.status_code == 200, rp.text
            assert rp.headers.get("content-type", "").startswith("image/")
            assert len(rp.content) > 1000

            # Panel slice returns JPEG
            rp2 = requests.get(f"{API}/public/project/{pid}?panel=0&of=3", timeout=15)
            assert rp2.status_code == 200, rp2.text
            assert rp2.headers.get("content-type", "").startswith("image/jpeg")
            assert len(rp2.content) > 1000
        finally:
            sess.delete(f"{API}/projects/{pid}", headers=demo_headers, timeout=15)

    def test_public_project_image_404(self, sess):
        r = requests.get(f"{API}/public/project/{uuid.uuid4()}", timeout=15)
        assert r.status_code == 404


# ---------- Printful fulfillment on POST /api/orders ----------
class TestPrintfulFulfillment:
    def test_metal_order_stays_received(self, sess, demo_headers):
        # metal is NOT in PRINTFUL_VARIANTS -> should remain received / not_fulfilled_by_printful
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "metal",
            "size": "18x24", "frame": "black", "price": 199.0,
            "recipient": {"name": "Metal Buyer", "address1": "1 Ore Rd", "city": "Reno",
                          "state_code": "NV", "country_code": "US", "zip": "89501"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "received"
        assert o["printful_status"] == "not_fulfilled_by_printful"
        assert o.get("printful_order_id") in (None, "")

    def test_acrylic_order_stays_received(self, sess, demo_headers):
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "acrylic",
            "size": "12x16", "frame": "wood", "price": 149.0,
            "recipient": {"name": "Acrylic Buyer", "address1": "2 Glass Ln", "city": "Miami",
                          "state_code": "FL", "country_code": "US", "zip": "33101"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=30)
        assert r.status_code == 200
        o = r.json()
        assert o["status"] == "received"
        assert o["printful_status"] == "not_fulfilled_by_printful"

    @pytest.mark.timeout(120)
    def test_canvas_order_submits_to_printful(self, sess, demo_headers):
        # Create a project first so public URL exists (Printful will fetch it)
        rp = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "canvas",
        }, timeout=15)
        assert rp.status_code == 200
        pid = rp.json()["id"]

        payload = {
            "project_id": pid, "image_base64": TINY_PNG, "style": "canvas",
            "material": "canvas", "size": "12x16", "frame": "wood", "panels": 1, "price": 89.0,
            "recipient": {"name": "Canvas Buyer", "address1": "1 Art Way", "city": "Austin",
                          "state_code": "TX", "country_code": "US", "zip": "78701"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=120)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "in_production", f"Expected in_production, got {o}"
        assert o["printful_status"] == "draft_created"
        assert o.get("printful_order_id"), "printful_order_id should be set"

    @pytest.mark.timeout(120)
    def test_poster_order_submits_to_printful(self, sess, demo_headers):
        rp = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "minimal",
        }, timeout=15)
        assert rp.status_code == 200
        pid = rp.json()["id"]

        payload = {
            "project_id": pid, "image_base64": TINY_PNG, "style": "minimal",
            "material": "poster", "size": "18x24", "frame": "black", "panels": 1, "price": 59.0,
            "recipient": {"name": "Poster Buyer", "address1": "5 Wall St", "city": "NYC",
                          "state_code": "NY", "country_code": "US", "zip": "10005"},
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=120)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "in_production"
        assert o["printful_status"] == "draft_created"
        assert o.get("printful_order_id")


# ---------- Stripe payments ----------
class TestStripe:
    def test_create_order_requires_auth(self, sess):
        r = sess.post(f"{API}/payments/create-intent", json={"amount": 12.34}, timeout=15)
        assert r.status_code in (401, 403)

    def test_capture_requires_auth(self, sess):
        r = sess.post(f"{API}/payments/complete/pi_FAKEID", timeout=15)
        assert r.status_code in (401, 403)

    def test_complete_unknown_intent_returns_404(self, sess, demo_headers):
        r = sess.post(f"{API}/payments/complete/pi_DOES_NOT_EXIST", headers=demo_headers, timeout=30)
        assert r.status_code == 404, r.text


# ---------- Multi-panel Room Preview (real gpt-image-1) ----------
class TestRoomPreviewPanels:
    @pytest.mark.timeout(180)
    def test_room_preview_single_panel(self, sess, demo_headers, real_image_b64):
        payload = {"image_base64": real_image_b64, "room": "living_room",
                   "frame": "wood", "material": "canvas", "panels": 1}
        r = sess.post(f"{API}/room-preview", headers=demo_headers, json=payload, timeout=180)
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["image_base64"].startswith("data:image")
            assert len(d["image_base64"]) > 1000
        else:
            pytest.skip(f"AI 502 for single-panel: {r.text}")

    @pytest.mark.timeout(180)
    def test_room_preview_triptych(self, sess, demo_headers, real_image_b64):
        payload = {"image_base64": real_image_b64, "room": "living_room",
                   "frame": "wood", "material": "canvas", "panels": 3}
        r = sess.post(f"{API}/room-preview", headers=demo_headers, json=payload, timeout=180)
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["image_base64"].startswith("data:image")
            assert len(d["image_base64"]) > 1000
        else:
            pytest.skip(f"AI 502 for triptych: {r.text}")
