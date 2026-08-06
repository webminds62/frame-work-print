import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import server


def webhook_payload(*, order_id="123", store=99, shipment_id=10, tracking="https://forged.invalid/track"):
    return {
        "type": "package_shipped",
        "created": 1_700_000_000,
        "retries": 0,
        "store": store,
        "data": {
            "order": {"id": order_id},
            "shipment": {"id": shipment_id, "tracking_url": tracking},
        },
    }


def authoritative_order(*, order_id="123", local_id="local-1", store=99, status="fulfilled", shipment_id=10):
    return {
        "id": order_id,
        "external_id": local_id,
        "store": store,
        "status": status,
        "shipments": [{"id": shipment_id, "tracking_url": "https://printful.example/verified"}],
    }


def test_verified_update_uses_authenticated_tracking_not_webhook_tracking(monkeypatch):
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    local = {"id": "local-1", "printful_order_id": "123"}
    update = server.verified_printful_webhook_update(
        webhook_payload(), local, authoritative_order()
    )
    assert update["status"] == "shipped"
    assert update["printful_status"] == "fulfilled"
    assert update["tracking_url"] == "https://printful.example/verified"
    assert "forged.invalid" not in update["tracking_url"]


@pytest.mark.parametrize(
    "payload,remote",
    [
        (webhook_payload(store=98), authoritative_order()),
        (webhook_payload(shipment_id=11), authoritative_order()),
        (webhook_payload(), authoritative_order(status="inprocess")),
        (webhook_payload(), authoritative_order(local_id="another-local-order")),
    ],
)
def test_verified_update_rejects_store_shipment_status_and_external_id_mismatches(
    monkeypatch, payload, remote
):
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    local = {"id": "local-1", "printful_order_id": "123"}
    assert server.verified_printful_webhook_update(payload, local, remote) is None


def test_fetch_printful_order_uses_private_token_and_store_context(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"result": authoritative_order()}

    class Client:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, path):
            captured["path"] = path
            return Response()

    monkeypatch.setattr(server, "PRINTFUL_TOKEN", "test_private_token")
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    monkeypatch.setattr(server.httpx, "AsyncClient", Client)
    result = asyncio.run(server.fetch_printful_order("123"))
    assert result["id"] == "123"
    assert captured["path"] == "/orders/123"
    assert captured["kwargs"]["headers"] == {
        "Authorization": "Bearer test_private_token",
        "X-PF-Store-Id": "99",
    }


def test_new_printful_draft_is_bound_to_local_order_id(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"result": {"id": 123}}

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, path, json):
            captured["path"] = path
            captured["payload"] = json
            return Response()

    async def variant(*_args, **_kwargs):
        return SimpleNamespace(id=16044, framed=True)

    monkeypatch.setattr(server, "PRINTFUL_TOKEN", "test_private_token")
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    monkeypatch.setattr(server, "PUBLIC_BASE_URL", "https://api.example.test")
    monkeypatch.setattr(server, "validated_printful_variant", variant)
    monkeypatch.setattr(server.httpx, "AsyncClient", Client)
    result = asyncio.run(server.submit_printful_order(
        "local-order-uuid",
        "project-1",
        "canvas",
        "18x24",
        1,
        "brown",
        16044,
        {
            "name": "Test Buyer",
            "address1": "123 Main St",
            "city": "Austin",
            "state_code": "TX",
            "country_code": "US",
            "zip": "78701",
        },
    ))
    assert result == ("in_production", "framed_draft_created", "123")
    assert captured["path"] == "/orders"
    assert captured["payload"]["external_id"] == "local-order-uuid"


def test_webhook_updates_database_only_after_authenticated_cross_check(monkeypatch):
    local = {
        "id": "local-1",
        "printful_order_id": "123",
        "user_email": "buyer@example.com",
    }
    writes = []
    emails = []

    class Orders:
        async def find_one(self, query):
            assert query == {"printful_order_id": "123"}
            return local

        async def update_one(self, query, update):
            writes.append((query, update))
            return SimpleNamespace(modified_count=1)

    async def fetch(order_id):
        assert order_id == "123"
        return authoritative_order()

    async def email(*args):
        emails.append(args)

    monkeypatch.setattr(server, "PRINTFUL_WEBHOOK_SECRET", "test_webhook_secret")
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    monkeypatch.setattr(server, "db", SimpleNamespace(orders=Orders()))
    monkeypatch.setattr(server, "fetch_printful_order", fetch)
    monkeypatch.setattr(server, "send_status_email", email)

    result = asyncio.run(server.printful_webhook(webhook_payload(), "test_webhook_secret"))
    assert result == {"ok": True, "verified": True}
    assert writes[0][0] == {"id": "local-1"}
    assert writes[0][1]["$set"]["tracking_url"] == "https://printful.example/verified"
    assert len(emails) == 1


def test_webhook_does_not_write_when_authoritative_status_disagrees(monkeypatch):
    local = {"id": "local-1", "printful_order_id": "123"}

    class Orders:
        async def find_one(self, _query):
            return local

        async def update_one(self, *_args):
            raise AssertionError("unverified webhook must not write")

    async def fetch(_order_id):
        return authoritative_order(status="inprocess")

    monkeypatch.setattr(server, "PRINTFUL_WEBHOOK_SECRET", "test_webhook_secret")
    monkeypatch.setattr(server, "PRINTFUL_STORE_ID", "99")
    monkeypatch.setattr(server, "db", SimpleNamespace(orders=Orders()))
    monkeypatch.setattr(server, "fetch_printful_order", fetch)
    result = asyncio.run(server.printful_webhook(webhook_payload(), "test_webhook_secret"))
    assert result == {"ok": True, "verified": False}


def test_webhook_returns_503_when_printful_cannot_be_cross_checked(monkeypatch):
    local = {"id": "local-1", "printful_order_id": "123"}

    class Orders:
        async def find_one(self, _query):
            return local

        async def update_one(self, *_args):
            raise AssertionError("unverified webhook must not write")

    async def unavailable(_order_id):
        raise server.PrintfulVerificationUnavailable("offline")

    monkeypatch.setattr(server, "PRINTFUL_WEBHOOK_SECRET", "test_webhook_secret")
    monkeypatch.setattr(server, "db", SimpleNamespace(orders=Orders()))
    monkeypatch.setattr(server, "fetch_printful_order", unavailable)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.printful_webhook(webhook_payload(), "test_webhook_secret"))
    assert exc.value.status_code == 503
