"""Allowlisted Printful wall-art catalog with public sync and an offline snapshot.

The Catalog API is public and does not require an account token. Order and mockup
APIs remain separately gated by PRINTFUL_TOKEN/PRINTFUL_STORE_ID in server.py.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any

import httpx

PRINTFUL_API_BASE = "https://api.printful.com"
SNAPSHOT_SYNCED_AT = "2026-08-06T16:30:00Z"
SUPPORTED_SIZE_LABELS = {
    "12″×16″": ("12x16", '12" × 16"'),
    "18″×24″": ("18x24", '18" × 24"'),
    "24″×36″": ("24x36", '24" × 36"'),
    "30″×40″": ("30x40", '30" × 40"'),
}


@dataclass(frozen=True)
class CatalogVariant:
    id: int
    product_id: int
    product_name: str
    material: str
    size_key: str
    size_label: str
    finish_key: str
    finish_label: str
    catalog_price: float
    retail_price: float
    currency: str
    image: str
    name: str
    framed: bool
    in_stock: bool


PRODUCT_SPECS = {
    614: {
        "material": "canvas",
        "product_name": "Printful Framed Canvas",
        "framed": True,
        "finishes": {
            "Black": ("black", "Black"),
            "Brown": ("brown", "Brown"),
            "White": ("white", "White"),
        },
    },
    2: {
        "material": "poster",
        "product_name": "Printful Enhanced Matte Paper Framed Poster",
        "framed": True,
        "finishes": {
            "Black": ("black", "Black"),
            "Red Oak": ("red_oak", "Red Oak"),
            "White": ("white", "White"),
        },
    },
    3: {
        "material": "canvas",
        "product_name": "Printful Canvas",
        "framed": False,
        "finishes": {None: ("none", "Unframed")},
    },
    1: {
        "material": "poster",
        "product_name": "Printful Enhanced Matte Paper Poster",
        "framed": False,
        "finishes": {None: ("none", "Unframed")},
    },
    616: {
        "material": "canvas",
        "product_name": "Printful Thin Canvas",
        "framed": False,
        "finishes": {None: ("none", "Thin canvas")},
    },
    588: {
        "material": "metal",
        "product_name": "Printful Glossy Metal Print",
        "framed": False,
        "finishes": {"White": ("metal", "Glossy metal")},
    },
    172: {
        "material": "poster",
        "product_name": "Printful Premium Luster Photo Paper Framed Poster",
        "framed": True,
        "finishes": {
            "Black": ("black", "Black"),
            "Red Oak": ("red_oak", "Red Oak"),
            "White": ("white", "White"),
        },
    },
    171: {
        "material": "poster",
        "product_name": "Printful Premium Luster Photo Paper Poster",
        "framed": False,
        "finishes": {None: ("none", "Unframed")},
    },
    795: {
        "material": "poster",
        "product_name": "Printful Matte Paper Framed Poster With Mat",
        "framed": True,
        "finishes": {
            "Black": ("black", "Black with mat"),
            "Red Oak": ("red_oak", "Red Oak with mat"),
            "White": ("white", "White with mat"),
        },
    },
}


# Verified against GET /products/{id} on 2026-08-06. Prices are Printful catalog
# prices before the configurable app markup and shipping.
SNAPSHOT_ROWS = [
    # Framed Canvas (#614)
    (16035, 614, "canvas", "12x16", "black", "Black", 51.00, "https://files.cdn.printful.com/products/614/16035_1660216838.jpg", "Framed Canvas (Black / 12″×16″)"),
    (16038, 614, "canvas", "18x24", "black", "Black", 71.40, "https://files.cdn.printful.com/products/614/16038_1660216858.jpg", "Framed Canvas (Black / 18″×24″)"),
    (16039, 614, "canvas", "24x36", "black", "Black", 99.96, "https://files.cdn.printful.com/products/614/16039_1660216958.jpg", "Framed Canvas (Black / 24″×36″)"),
    (16041, 614, "canvas", "12x16", "brown", "Brown", 51.00, "https://files.cdn.printful.com/products/614/16041_1730194267.jpg", "Framed Canvas (Brown / 12″×16″)"),
    (16044, 614, "canvas", "18x24", "brown", "Brown", 71.40, "https://files.cdn.printful.com/products/614/16044_1730194278.jpg", "Framed Canvas (Brown / 18″×24″)"),
    (16045, 614, "canvas", "24x36", "brown", "Brown", 99.96, "https://files.cdn.printful.com/products/614/16045_1730194278.jpg", "Framed Canvas (Brown / 24″×36″)"),
    (15696, 614, "canvas", "12x16", "white", "White", 51.00, "https://files.cdn.printful.com/products/614/15696_1660217017.jpg", "Framed Canvas (White / 12″×16″)"),
    (15699, 614, "canvas", "18x24", "white", "White", 71.40, "https://files.cdn.printful.com/products/614/15699_1660217200.jpg", "Framed Canvas (White / 18″×24″)"),
    (15700, 614, "canvas", "24x36", "white", "White", 99.96, "https://files.cdn.printful.com/products/614/15700_1660217220.jpg", "Framed Canvas (White / 24″×36″)"),
    # Enhanced Matte Paper Framed Poster (#2)
    (1350, 2, "poster", "12x16", "black", "Black", 31.57, "https://files.cdn.printful.com/products/2/1350_1527683296.jpg", "Enhanced Matte Paper Framed Poster (Black/12″×16″)"),
    (3, 2, "poster", "18x24", "black", "Black", 45.39, "https://files.cdn.printful.com/products/2/3_1527685193.jpg", "Enhanced Matte Paper Framed Poster (Black/18″×24″)"),
    (4, 2, "poster", "24x36", "black", "Black", 74.41, "https://files.cdn.printful.com/products/2/4_1527683261.jpg", "Enhanced Matte Paper Framed Poster (Black/24″×36″)"),
    (15025, 2, "poster", "12x16", "red_oak", "Red Oak", 31.57, "https://files.cdn.printful.com/products/2/15025_1651046798.jpg", "Enhanced Matte Paper Framed Poster (Red Oak / 12″×16″)"),
    (15031, 2, "poster", "18x24", "red_oak", "Red Oak", 45.39, "https://files.cdn.printful.com/products/2/15031_1651047284.jpg", "Enhanced Matte Paper Framed Poster (Red Oak / 18″×24″)"),
    (15032, 2, "poster", "24x36", "red_oak", "Red Oak", 74.41, "https://files.cdn.printful.com/products/2/15032_1651046859.jpg", "Enhanced Matte Paper Framed Poster (Red Oak / 24″×36″)"),
    (10751, 2, "poster", "12x16", "white", "White", 31.57, "https://files.cdn.printful.com/products/2/10751_1565081244.jpg", "Enhanced Matte Paper Framed Poster (White/12″×16″)"),
    (10749, 2, "poster", "18x24", "white", "White", 45.39, "https://files.cdn.printful.com/products/2/10749_1565081125.jpg", "Enhanced Matte Paper Framed Poster (White/18″×24″)"),
    (10750, 2, "poster", "24x36", "white", "White", 74.41, "https://files.cdn.printful.com/products/2/10750_1565092666.jpg", "Enhanced Matte Paper Framed Poster (White/24″×36″)"),
    # Unframed Canvas (#3)
    (5, 3, "canvas", "12x16", "none", "Unframed", 23.41, "https://files.cdn.printful.com/products/3/5_1712914884.jpg", "Canvas 12″×16″"),
    (7, 3, "canvas", "18x24", "none", "Unframed", 33.66, "https://files.cdn.printful.com/products/3/7_1712914904.jpg", "Canvas 18″×24″"),
    (825, 3, "canvas", "24x36", "none", "Unframed", 52.02, "https://files.cdn.printful.com/products/3/825_1712914824.jpg", "Canvas 24″×36″"),
    (19323, 3, "canvas", "30x40", "none", "Unframed", 64.26, "https://files.cdn.printful.com/products/3/19323_1712915068.jpg", "Canvas (in) (30″×40″)"),
    # Unframed Enhanced Matte Paper Poster (#1)
    (1349, 1, "poster", "12x16", "none", "Unframed", 10.89, "https://files.cdn.printful.com/products/1/1349_1527679043.jpg", "Enhanced Matte Paper Poster 12″×16″"),
    (1, 1, "poster", "18x24", "none", "Unframed", 12.89, "https://files.cdn.printful.com/products/1/1_1527683474.jpg", "Enhanced Matte Paper Poster 18″×24″"),
    (2, 1, "poster", "24x36", "none", "Unframed", 17.89, "https://files.cdn.printful.com/products/1/2_1527678974.jpg", "Enhanced Matte Paper Poster 24″×36″"),
    (48503, 1, "poster", "30x40", "none", "Unframed", 21.49, "https://files.cdn.printful.com/products/1/48503_1777277734.jpg", "Enhanced Matte Paper Poster 30″×40″"),
    # Thin Canvas (#616)
    (15702, 616, "canvas", "12x16", "none", "Thin canvas", 21.93, "https://files.cdn.printful.com/products/616/15702_1660725256.jpg", "Thin Canvas 12″×16″"),
    (15705, 616, "canvas", "18x24", "none", "Thin canvas", 30.55, "https://files.cdn.printful.com/products/616/15705_1660725274.jpg", "Thin Canvas 18″×24″"),
    (15706, 616, "canvas", "24x36", "none", "Thin canvas", 54.06, "https://files.cdn.printful.com/products/616/15706_1660725285.jpg", "Thin Canvas 24″×36″"),
    # Glossy Metal Print (#588)
    (15139, 588, "metal", "24x36", "metal", "Glossy metal", 209.05, "https://files.cdn.printful.com/products/588/15139_1652708747.jpg", "Glossy Metal Print 24″×36″"),
    # Premium Luster Photo Paper Framed Poster (#172)
    (6886, 172, "poster", "12x16", "black", "Black", 35.19, "https://files.cdn.printful.com/products/172/6886_1527683301.jpg", "Premium Luster Photo Paper Framed Poster (Black/12″×16″)"),
    (6891, 172, "poster", "18x24", "black", "Black", 55.08, "https://files.cdn.printful.com/products/172/6891_1527685200.jpg", "Premium Luster Photo Paper Framed Poster (Black/18″×24″)"),
    (7846, 172, "poster", "24x36", "black", "Black", 90.78, "https://files.cdn.printful.com/products/172/7846_1527683265.jpg", "Premium Luster Photo Paper Framed Poster (Black/24″×36″)"),
    (15010, 172, "poster", "12x16", "red_oak", "Red Oak", 35.19, "https://files.cdn.printful.com/products/172/15010_1651047538.jpg", "Premium Luster Photo Paper Framed Poster (Red Oak / 12″×16″)"),
    (15017, 172, "poster", "18x24", "red_oak", "Red Oak", 55.08, "https://files.cdn.printful.com/products/172/15017_1651047568.jpg", "Premium Luster Photo Paper Framed Poster (Red Oak / 18″×24″)"),
    (15018, 172, "poster", "24x36", "red_oak", "Red Oak", 90.78, "https://files.cdn.printful.com/products/172/15018_1651047579.jpg", "Premium Luster Photo Paper Framed Poster (Red Oak / 24″×36″)"),
    (10764, 172, "poster", "12x16", "white", "White", 35.19, "https://files.cdn.printful.com/products/172/10764_1565081255.jpg", "Premium Luster Photo Paper Framed Poster (White/12″×16″)"),
    (10769, 172, "poster", "18x24", "white", "White", 55.08, "https://files.cdn.printful.com/products/172/10769_1565081338.jpg", "Premium Luster Photo Paper Framed Poster (White/18″×24″)"),
    (10770, 172, "poster", "24x36", "white", "White", 90.78, "https://files.cdn.printful.com/products/172/10770_1565093116.jpg", "Premium Luster Photo Paper Framed Poster (White/24″×36″)"),
    # Premium Luster Photo Paper Poster (#171)
    (6875, 171, "poster", "12x16", "none", "Unframed", 13.26, "https://files.cdn.printful.com/products/171/6875_1527679033.jpg", "Premium Luster Photo Paper Poster 12″×16″"),
    (6880, 171, "poster", "18x24", "none", "Unframed", 16.32, "https://files.cdn.printful.com/products/171/6880_1527683490.jpg", "Premium Luster Photo Paper Poster 18″×24″"),
    (7845, 171, "poster", "24x36", "none", "Unframed", 22.44, "https://files.cdn.printful.com/products/171/7845_1527679000.jpg", "Premium Luster Photo Paper Poster 24″×36″"),
    # Matte Paper Framed Poster With Mat (#795)
    (20256, 795, "poster", "12x16", "black", "Black with mat", 35.70, "https://files.cdn.printful.com/products/795/20256_1722419854.jpg", "Matte Paper Framed Poster With Mat (Black / 12″×16″)"),
    (20265, 795, "poster", "18x24", "black", "Black with mat", 49.93, "https://files.cdn.printful.com/products/795/20265_1722419865.jpg", "Matte Paper Framed Poster With Mat (Black / 18″×24″)"),
    (20268, 795, "poster", "24x36", "black", "Black with mat", 80.07, "https://files.cdn.printful.com/products/795/20268_1722419872.jpg", "Matte Paper Framed Poster With Mat (Black / 24″×36″)"),
    (20257, 795, "poster", "12x16", "red_oak", "Red Oak with mat", 35.70, "https://files.cdn.printful.com/products/795/20257_1722419975.jpg", "Matte Paper Framed Poster With Mat (Red Oak / 12″×16″)"),
    (20266, 795, "poster", "18x24", "red_oak", "Red Oak with mat", 49.93, "https://files.cdn.printful.com/products/795/20266_1722419985.jpg", "Matte Paper Framed Poster With Mat (Red Oak / 18″×24″)"),
    (20269, 795, "poster", "24x36", "red_oak", "Red Oak with mat", 80.07, "https://files.cdn.printful.com/products/795/20269_1722419988.jpg", "Matte Paper Framed Poster With Mat (Red Oak / 24″×36″)"),
    (20258, 795, "poster", "12x16", "white", "White with mat", 35.70, "https://files.cdn.printful.com/products/795/20258_1722419996.jpg", "Matte Paper Framed Poster With Mat (White / 12″×16″)"),
    (20267, 795, "poster", "18x24", "white", "White with mat", 49.93, "https://files.cdn.printful.com/products/795/20267_1722420007.jpg", "Matte Paper Framed Poster With Mat (White / 18″×24″)"),
    (20270, 795, "poster", "24x36", "white", "White with mat", 80.07, "https://files.cdn.printful.com/products/795/20270_1722420007.jpg", "Matte Paper Framed Poster With Mat (White / 24″×36″)"),
]


def _size_label(size_key: str) -> str:
    for key, label in SUPPORTED_SIZE_LABELS.values():
        if key == size_key:
            return label
    return size_key


def snapshot_variants(markup: float) -> list[CatalogVariant]:
    result: list[CatalogVariant] = []
    for variant_id, product_id, material, size_key, finish_key, finish_label, price, image, name in SNAPSHOT_ROWS:
        spec = PRODUCT_SPECS[product_id]
        result.append(CatalogVariant(
            id=variant_id,
            product_id=product_id,
            product_name=spec["product_name"],
            material=material,
            size_key=size_key,
            size_label=_size_label(size_key),
            finish_key=finish_key,
            finish_label=finish_label,
            catalog_price=price,
            retail_price=round(price * markup, 2),
            currency="USD",
            image=image,
            name=name,
            framed=bool(spec["framed"]),
            in_stock=True,
        ))
    return result


def parse_product_payload(payload: dict[str, Any], product_id: int, markup: float) -> list[CatalogVariant]:
    spec = PRODUCT_SPECS[product_id]
    result: list[CatalogVariant] = []
    body = payload.get("result") or {}
    product = body.get("product") or {}
    if int(product.get("id") or 0) != product_id:
        raise ValueError(f"Printful product {product_id} response did not match the requested product")
    for raw in body.get("variants") or []:
        size = SUPPORTED_SIZE_LABELS.get(raw.get("size"))
        finish = spec["finishes"].get(raw.get("color"))
        if not size or not finish:
            continue
        price = float(raw.get("price") or 0)
        if price <= 0 or not raw.get("image"):
            continue
        result.append(CatalogVariant(
            id=int(raw["id"]),
            product_id=product_id,
            product_name=spec["product_name"],
            material=spec["material"],
            size_key=size[0],
            size_label=size[1],
            finish_key=finish[0],
            finish_label=finish[1],
            catalog_price=round(price, 2),
            retail_price=round(price * markup, 2),
            currency=product.get("currency") or "USD",
            image=raw["image"],
            name=raw.get("name") or f"Printful variant {raw['id']}",
            framed=bool(spec["framed"]),
            in_stock=bool(raw.get("in_stock")),
        ))
    return result


_cache: dict[str, Any] = {"expires": 0.0, "variants": None, "synced_at": None}
_cache_lock = asyncio.Lock()


async def get_catalog(markup: float, force: bool = False) -> tuple[list[CatalogVariant], str, str]:
    """Return current public catalog data, falling back to the verified snapshot."""
    mode = os.environ.get("PRINTFUL_CATALOG_MODE", "live_public").strip().lower()
    ttl = max(60, int(os.environ.get("PRINTFUL_CATALOG_TTL_SECONDS", "3600")))
    if mode == "snapshot":
        return snapshot_variants(markup), "verified_snapshot", SNAPSHOT_SYNCED_AT

    now = time.monotonic()
    if not force and _cache["variants"] is not None and now < _cache["expires"]:
        variants = [replace(v, retail_price=round(v.catalog_price * markup, 2)) for v in _cache["variants"]]
        return variants, "printful_live", _cache["synced_at"]

    async with _cache_lock:
        now = time.monotonic()
        if not force and _cache["variants"] is not None and now < _cache["expires"]:
            variants = [replace(v, retail_price=round(v.catalog_price * markup, 2)) for v in _cache["variants"]]
            return variants, "printful_live", _cache["synced_at"]
        try:
            async with httpx.AsyncClient(base_url=PRINTFUL_API_BASE, timeout=20) as client:
                responses = await asyncio.gather(*(client.get(f"/products/{pid}") for pid in PRODUCT_SPECS))
            variants: list[CatalogVariant] = []
            for product_id, response in zip(PRODUCT_SPECS, responses):
                response.raise_for_status()
                variants.extend(parse_product_payload(response.json(), product_id, markup))
            expected = {(v.material, v.size_key, v.finish_key) for v in snapshot_variants(markup)}
            received = {(v.material, v.size_key, v.finish_key) for v in variants}
            if not expected.issubset(received):
                raise ValueError("Printful catalog sync omitted one or more configured wall-art options")
            synced_at = datetime.now(timezone.utc).isoformat()
            _cache.update({"expires": now + ttl, "variants": variants, "synced_at": synced_at})
            return variants, "printful_live", synced_at
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return snapshot_variants(markup), "verified_snapshot", SNAPSHOT_SYNCED_AT


def serialize_variants(variants: list[CatalogVariant]) -> list[dict[str, Any]]:
    return [asdict(variant) for variant in variants]


def find_variant(variants: list[CatalogVariant], variant_id: int) -> CatalogVariant | None:
    return next((variant for variant in variants if variant.id == variant_id), None)


def find_selection(
    variants: list[CatalogVariant], material: str, size_key: str, finish_key: str
) -> CatalogVariant | None:
    return next((variant for variant in variants if (
        variant.material == material
        and variant.size_key == size_key
        and variant.finish_key == finish_key
    )), None)
