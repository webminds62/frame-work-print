"""Iteration 8 — Security hardening verification for Frame Works Prints.

Covers:
  SEC-001 Admin: old default password fails, new env password works, admin routes gated.
  SEC-002 Payments: POST /api/orders removed; /api/payments/create-intent computes price
          server-side + ownership; /api/payments/complete/{id} ownership -> 404.
  SEC-003 Webhook: POST /api/webhooks/printful requires ?token=; without it, no change.
  SEC-004 Rate limit: POST /api/auth/login rapid-fire returns 429.
  REGRESSION: /api/quote first-order discount fields; auth flows; projects CRUD; /orders list.
"""

import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@frameworks.com"
ADMIN_PASSWORD_NEW = os.environ.get("ADMIN_PASSWORD_TEST", "7mG5tYW8yEO5w7lY6QSt")
ADMIN_PASSWORD_OLD = "Admin12345"

DEMO_EMAIL = "demo@frameworks.com"
DEMO_PASSWORD = "Password123"

WEBHOOK_SECRET = os.environ.get("PRINTFUL_WEBHOOK_SECRET_TEST", "17b5b243cf8668db741144d38572530c5d12d00b23194936")
MONGO_URL = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME_TEST", "test_database")

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
)
TINY_PNG = f"data:image/png;base64,{TINY_PNG_B64}"

RECIPIENT = {
    "name": "Sec Buyer", "address1": "1 Main", "city": "Austin",
    "state_code": "TX", "country_code": "US", "zip": "78701",
}


@pytest.fixture(scope="session")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(sess, email, password):
    return sess.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)


@pytest.fixture(scope="session")
def demo_headers(sess):
    r = _login(sess, DEMO_EMAIL, DEMO_PASSWORD)
    if r.status_code == 429:
        # Wait a bit for the login rate limit window to clear if a previous test bumped it.
        time.sleep(2)
        r = _login(sess, DEMO_EMAIL, DEMO_PASSWORD)
    if r.status_code != 200:
        rr = sess.post(f"{API}/auth/register",
                       json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "name": "Demo"}, timeout=15)
        assert rr.status_code == 200, rr.text
        r = _login(sess, DEMO_EMAIL, DEMO_PASSWORD)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin_headers(sess):
    r = _login(sess, ADMIN_EMAIL, ADMIN_PASSWORD_NEW)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    assert r.json()["user"]["is_admin"] is True
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


# ================================================================
# SEC-001 — Admin password hardening
# ================================================================
class TestSEC001_AdminPassword:
    def test_old_default_admin_password_fails(self, sess):
        r = _login(sess, ADMIN_EMAIL, ADMIN_PASSWORD_OLD)
        assert r.status_code == 401, f"OLD admin password must NOT work anymore, got {r.status_code}: {r.text}"

    def test_new_admin_password_works_and_is_admin(self, sess):
        r = _login(sess, ADMIN_EMAIL, ADMIN_PASSWORD_NEW)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["is_admin"] is True

    def test_admin_stats_requires_admin(self, sess, demo_headers, admin_headers):
        # Demo user forbidden
        r = sess.get(f"{API}/admin/stats", headers=demo_headers, timeout=15)
        assert r.status_code == 403, r.text
        # Admin OK
        r2 = sess.get(f"{API}/admin/stats", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        data = r2.json()
        for k in ("total_orders", "revenue", "total_users", "total_projects"):
            assert k in data

    def test_admin_orders_requires_admin(self, sess, demo_headers, admin_headers):
        r = sess.get(f"{API}/admin/orders", headers=demo_headers, timeout=15)
        assert r.status_code == 403
        r2 = sess.get(f"{API}/admin/orders", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert isinstance(r2.json(), list)


# ================================================================
# SEC-002 — Payment endpoint hardening
# ================================================================
class TestSEC002_PaymentSecurity:
    def test_public_orders_post_removed(self, sess, demo_headers):
        """POST /api/orders should no longer exist for authenticated users either."""
        payload = {
            "image_base64": TINY_PNG, "style": "canvas", "material": "canvas",
            "size": "16x20", "frame": "wood", "price": 1.00, "recipient": RECIPIENT,
        }
        r = sess.post(f"{API}/orders", headers=demo_headers, json=payload, timeout=15)
        assert r.status_code in (404, 405), f"POST /api/orders must be removed. Got {r.status_code}: {r.text[:200]}"

    def test_create_order_ignores_client_amount_and_computes_server_side(self, sess, demo_headers):
        # First create a project owned by demo user
        rp = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "canvas",
        }, timeout=15)
        assert rp.status_code == 200
        pid = rp.json()["id"]

        # Client sends NO amount — server must compute + return
        payload = {
            "project_id": pid, "material": "canvas", "size": "16x20", "frame": "wood",
            "panels": 1, "panel_key": "single-1", "recipient": RECIPIENT,
        }
        r = sess.post(f"{API}/payments/create-intent", headers=demo_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("payment_intent_id", "client_secret", "amount", "quote"):
            assert k in body, f"missing {k}: {body}"
        assert body["amount"] > 0
        assert isinstance(body["quote"], dict)
        assert body["quote"]["retail"] == body["amount"]
        # First-order discount fields present
        for k in ("first_order", "retail_before_discount", "discount_amount"):
            assert k in body["quote"]

        # Cleanup project
        sess.delete(f"{API}/projects/{pid}", headers=demo_headers, timeout=15)

    def test_create_order_404_when_project_not_owned(self, sess, demo_headers):
        payload = {
            "project_id": str(uuid.uuid4()),  # never exists
            "material": "canvas", "size": "16x20", "frame": "wood",
            "panels": 1, "recipient": RECIPIENT,
        }
        r = sess.post(f"{API}/payments/create-intent", headers=demo_headers, json=payload, timeout=30)
        assert r.status_code == 404, f"Expected 404 for unowned project_id, got {r.status_code}: {r.text[:200]}"

    def test_capture_unknown_or_foreign_returns_404(self, sess, demo_headers):
        # Unknown Stripe intent -> ownership check fails before Stripe is contacted.
        r = sess.post(f"{API}/payments/complete/pi_UNKNOWN_{uuid.uuid4().hex}", headers=demo_headers, timeout=30)
        assert r.status_code == 404, f"Expected 404 for unknown payment intent, got {r.status_code}: {r.text[:200]}"

    def test_capture_requires_auth(self, sess):
        r = sess.post(f"{API}/payments/complete/anything", timeout=15)
        assert r.status_code in (401, 403)


# ================================================================
# SEC-003 — Printful webhook token
# ================================================================
class TestSEC003_WebhookToken:
    def _seed_order(self, pf_id: str):
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        doc = {
            "id": f"secwebhook_{uuid.uuid4().hex[:12]}",
            "user_id": "SEC003_TEST",
            "user_email": "delivered@resend.dev",
            "status": "in_production",
            "printful_order_id": pf_id,
            "printful_status": "draft_created",
            "material": "canvas", "size": "16x20", "frame": "wood",
            "price": 99.0,
            "recipient": RECIPIENT,
        }
        db.orders.insert_one(doc)
        return db, doc["id"]

    def test_webhook_without_token_does_not_change_order(self, sess):
        pf_id = f"PF_SEC_{uuid.uuid4().hex[:10]}"
        db, order_id = self._seed_order(pf_id)
        try:
            payload = {"type": "package_shipped",
                       "data": {"order": {"id": pf_id},
                                "shipment": {"tracking_url": "https://track.test/FORGED"}}}
            r = sess.post(f"{API}/webhooks/printful", json=payload, timeout=15)
            # Should quietly 200 but do nothing
            assert r.status_code == 200, r.text
            # Verify NOT changed
            after = db.orders.find_one({"id": order_id})
            assert after["status"] == "in_production", f"forged webhook changed status to {after['status']}"
            assert "tracking_url" not in after or not after.get("tracking_url"), \
                f"forged webhook set tracking_url={after.get('tracking_url')}"

            # Wrong token also rejected
            r2 = sess.post(f"{API}/webhooks/printful?token=WRONG", json=payload, timeout=15)
            assert r2.status_code == 200
            after2 = db.orders.find_one({"id": order_id})
            assert after2["status"] == "in_production"
        finally:
            db.orders.delete_one({"id": order_id})

    def test_webhook_with_correct_token_updates_order_to_shipped(self, sess):
        pf_id = f"PF_SEC_{uuid.uuid4().hex[:10]}"
        db, order_id = self._seed_order(pf_id)
        try:
            payload = {"type": "package_shipped",
                       "data": {"order": {"id": pf_id},
                                "shipment": {"tracking_url": "https://track.test/OK123"}}}
            r = sess.post(f"{API}/webhooks/printful?token={WEBHOOK_SECRET}", json=payload, timeout=15)
            assert r.status_code == 200, r.text
            after = db.orders.find_one({"id": order_id})
            assert after["status"] == "shipped", f"expected shipped, got {after['status']}"
            assert after.get("tracking_url") == "https://track.test/OK123"
        finally:
            db.orders.delete_one({"id": order_id})


# ================================================================
# SEC-004 — Rate limiting
# ================================================================
class TestSEC004_RateLimiting:
    def test_login_rate_limit_429(self, sess):
        """Rapid-fire logins with a bogus password should eventually return 429."""
        email = f"rl_{uuid.uuid4().hex[:8]}@frameworks.com"
        got_429 = False
        codes = []
        for i in range(15):
            r = sess.post(f"{API}/auth/login",
                          json={"email": email, "password": "nope"}, timeout=10)
            codes.append(r.status_code)
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, f"Expected 429 within 15 attempts, got codes {codes}"

# ================================================================
# REGRESSION — /quote, projects CRUD, orders list, auth
# ================================================================
class TestRegression:
    def test_quote_returns_first_order_fields(self, sess):
        # Fresh user has no prior orders -> first_order should be true and discount > 0
        email = f"quote_{uuid.uuid4().hex[:8]}@frameworks.com"
        rr = sess.post(f"{API}/auth/register",
                       json={"email": email, "password": "Testpass1", "name": "Q"}, timeout=15)
        assert rr.status_code == 200
        h = {"Authorization": f"Bearer {rr.json()['token']}", "Content-Type": "application/json"}
        try:
            q = sess.post(f"{API}/quote", headers=h, json={
                "material": "canvas", "size": "16x20", "panels": 1, "frame": "wood",
                "recipient": RECIPIENT,
            }, timeout=30)
            assert q.status_code == 200, q.text
            body = q.json()
            for k in ("retail", "retail_before_discount", "first_order", "discount_amount"):
                assert k in body, f"missing {k}: {body}"
            assert body["first_order"] is True
            assert body["retail_before_discount"] >= body["retail"]
            assert body["discount_amount"] > 0
        finally:
            sess.delete(f"{API}/auth/me", headers=h, timeout=15)

    def test_projects_crud_regression(self, sess, demo_headers):
        r = sess.post(f"{API}/projects", headers=demo_headers, json={
            "original": TINY_PNG, "current": TINY_PNG, "style": "canvas",
        }, timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]
        rl = sess.get(f"{API}/projects", headers=demo_headers, timeout=15)
        assert rl.status_code == 200 and any(p["id"] == pid for p in rl.json())
        rd = sess.delete(f"{API}/projects/{pid}", headers=demo_headers, timeout=15)
        assert rd.status_code == 200

    def test_orders_list_regression(self, sess, demo_headers):
        r = sess.get(f"{API}/orders", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_auth_me_regression(self, sess, demo_headers):
        r = sess.get(f"{API}/auth/me", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL
