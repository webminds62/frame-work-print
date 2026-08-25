"""Prodigi Print API v4 client (sandbox + live)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

# Ensure .env is loaded even if this module is imported before server.load_dotenv.
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _api_key() -> str:
    return _env("PRODIGI_API_KEY")


def _base_url() -> str:
    return _env("PRODIGI_BASE_URL", "https://api.sandbox.prodigi.com").rstrip("/")


def _markup() -> float:
    return float(_env("PRODIGI_MARKUP", "1.6") or "1.6")


def _default_shipping() -> str:
    return _env("PRODIGI_DEFAULT_SHIPPING", "Budget") or "Budget"


def _submit_orders() -> bool:
    return _env("PRODIGI_SUBMIT_ORDERS", "false").lower() in {"1", "true", "yes", "on"}


# Module-level names kept for callers (server.py reads these). Re-read on each access via properties below.
class _Settings:
    @property
    def PRODIGI_API_KEY(self) -> str:
        return _api_key()

    @property
    def PRODIGI_BASE_URL(self) -> str:
        return _base_url()

    @property
    def PRODIGI_MARKUP(self) -> float:
        return _markup()

    @property
    def PRODIGI_DEFAULT_SHIPPING(self) -> str:
        return _default_shipping()

    @property
    def PRODIGI_SUBMIT_ORDERS(self) -> bool:
        return _submit_orders()


_settings = _Settings()

# Back-compat: attribute access on module via __getattr__
def __getattr__(name: str):
    if name in {
        "PRODIGI_API_KEY",
        "PRODIGI_BASE_URL",
        "PRODIGI_MARKUP",
        "PRODIGI_DEFAULT_SHIPPING",
        "PRODIGI_SUBMIT_ORDERS",
    }:
        return getattr(_settings, name)
    raise AttributeError(name)


def configured() -> bool:
    return bool(_api_key())


def _headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        raise RuntimeError("PRODIGI_API_KEY is not set")
    return {
        "X-API-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _request(
    method: str,
    path: str,
    *,
    json_body: Any = None,
    timeout: float = 45.0,
) -> dict:
    url = f"{_base_url()}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, url, headers=_headers(), json=json_body)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:500]}
    if resp.status_code >= 400:
        logger.error("Prodigi %s %s -> %s %s", method, path, resp.status_code, str(data)[:400])
        raise httpx.HTTPStatusError(
            f"Prodigi error {resp.status_code}",
            request=resp.request,
            response=resp,
        )
    return data if isinstance(data, dict) else {"data": data}


async def get_product(sku: str) -> dict:
    """GET /v4.0/products/{sku}"""
    return await _request("GET", f"/v4.0/products/{sku}")


async def create_quote(
    *,
    sku: str,
    copies: int = 1,
    attributes: Optional[dict] = None,
    destination_country_code: str = "US",
    shipping_method: Optional[str] = None,
    assets: Optional[list] = None,
) -> dict:
    """POST /v4.0/quotes — cost estimate for one line item."""
    item: dict[str, Any] = {
        "sku": sku,
        "copies": max(1, copies),
        "sizing": "fillPrintArea",
    }
    if attributes:
        item["attributes"] = attributes
    if assets:
        item["assets"] = assets
    else:
        # Quote without a real file URL still usually works for cost.
        item["assets"] = [{"printArea": "default"}]

    body = {
        "shippingMethod": shipping_method or _default_shipping(),
        "destinationCountryCode": destination_country_code,
        "items": [item],
    }
    return await _request("POST", "/v4.0/quotes", json_body=body)


async def create_order(
    *,
    merchant_reference: str,
    recipient: dict,
    sku: str,
    asset_url: str,
    copies: int = 1,
    attributes: Optional[dict] = None,
    shipping_method: Optional[str] = None,
    callback_url: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """POST /v4.0/orders — submit fulfillment (sandbox will not charge/ship)."""
    item: dict[str, Any] = {
        "sku": sku,
        "copies": max(1, copies),
        "sizing": "fillPrintArea",
        "assets": [
            {
                "printArea": "default",
                "url": asset_url,
            }
        ],
    }
    if attributes:
        item["attributes"] = attributes

    body: dict[str, Any] = {
        "merchantReference": merchant_reference,
        "shippingMethod": shipping_method or _default_shipping(),
        "recipient": recipient,
        "items": [item],
        "idempotencyKey": idempotency_key or merchant_reference,
    }
    if callback_url:
        body["callbackUrl"] = callback_url
    return await _request("POST", "/v4.0/orders", json_body=body)


async def get_order(order_id: str) -> dict:
    return await _request("GET", f"/v4.0/orders/{order_id}")


def parse_quote_totals(quote_response: dict) -> dict:
    """Best-effort extract product + shipping + currency from a Quotes response."""
    # Response shapes vary slightly; try common paths.
    quotes = quote_response.get("quotes") or quote_response.get("quote") or []
    if isinstance(quotes, dict):
        quotes = [quotes]
    if not quotes and quote_response.get("outcome"):
        # sometimes top-level
        quotes = [quote_response]

    best = quotes[0] if quotes else quote_response
    cost = best.get("cost") or best.get("costs") or {}
    if isinstance(cost, list) and cost:
        cost = cost[0]

    def _num(*keys, default=0.0):
        for k in keys:
            if k in cost and cost[k] is not None:
                try:
                    return float(cost[k])
                except (TypeError, ValueError):
                    pass
            if k in best and best[k] is not None:
                try:
                    return float(best[k])
                except (TypeError, ValueError):
                    pass
        return default

    product = _num("items", "product", "itemCost", "printCost")
    shipping = _num("shipping", "shippingCost")
    total = _num("total", "amount")
    if total and not product:
        product = max(0.0, total - shipping)
    currency = (
        cost.get("currency")
        or best.get("currency")
        or quote_response.get("currency")
        or "USD"
    )
    return {
        "product": round(product, 2),
        "shipping": round(shipping, 2),
        "total": round(total or (product + shipping), 2),
        "currency": str(currency).upper(),
        "raw": best,
    }


def recipient_from_app(recipient: dict, email: str = "") -> dict:
    """Map app checkout recipient -> Prodigi recipient object."""
    return {
        "name": recipient.get("name") or "Customer",
        "email": email or recipient.get("email") or None,
        "phoneNumber": recipient.get("phone") or None,
        "address": {
            "line1": recipient.get("address1") or recipient.get("line1") or "",
            "line2": recipient.get("address2") or recipient.get("line2") or None,
            "postalOrZipCode": recipient.get("zip") or recipient.get("postalOrZipCode") or "",
            "countryCode": (recipient.get("country_code") or recipient.get("countryCode") or "US").upper(),
            "townOrCity": recipient.get("city") or recipient.get("townOrCity") or "",
            "stateOrCounty": recipient.get("state_code") or recipient.get("stateOrCounty") or None,
        },
    }
