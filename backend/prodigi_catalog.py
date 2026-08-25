"""Map Frame Works store variants -> Prodigi SKUs + attributes.

Store UI stays curated (Essential / Gallery / Atelier). Each store_variant_id
optionally maps to a Prodigi fulfillment SKU. Unmapped variants still sell via
gallery_manual fulfillment until you attach SKUs from the probe script.
"""

from __future__ import annotations

from typing import Any, Optional

# Seed Prodigi SKUs commonly used for US wall art (validate with probe script).
# Keys are store family_id prefixes / exact store_variant patterns.

# size_key (app) -> Prodigi size token used in GLOBAL-* SKUs
SIZE_TO_PRODIGI = {
    "8x10": "8x10",
    "11x14": "11x14",
    "12x16": "12x16",
    "16x20": "16x20",
    "18x24": "18x24",
    "24x36": "24x36",
    "30x40": "30x40",
    "10x8": "10x8",
    "14x11": "14x11",
    "16x12": "16x12",
    "20x16": "20x16",
    "24x18": "24x18",
    "36x24": "36x24",
    "10x10": "10x10",
    "12x12": "12x12",
    "16x16": "16x16",
    "20x20": "20x20",
}

# family_id -> (sku_template with {size}, default attributes)
# Templates use uppercase size tokens as Prodigi often returns.
FAMILY_FULFILLMENT: dict[str, dict[str, Any]] = {
    # Essential
    "essential-slim-black": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "black"},
        "kind": "framed_print",
    },
    "essential-slim-white": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "white"},
        "kind": "framed_print",
    },
    "essential-matte-poster": {
        "sku_template": "GLOBAL-PHO-{size}",
        "attributes": {},
        "kind": "poster",
    },
    "essential-thin-canvas": {
        "sku_template": "GLOBAL-CAN-{size}",
        "attributes": {"wrap": "ImageWrap"},
        "kind": "canvas",
    },
    # Gallery
    "gallery-oak-mat": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "natural"},
        "kind": "framed_print",
    },
    "gallery-black-mat": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "black"},
        "kind": "framed_print",
    },
    "gallery-white-mat": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "white"},
        "kind": "framed_print",
    },
    "gallery-canvas-wrap": {
        "sku_template": "GLOBAL-CAN-{size}",
        "attributes": {"wrap": "ImageWrap"},
        "kind": "canvas",
    },
    "gallery-black-floater": {
        "sku_template": "GLOBAL-CAN-{size}",
        "attributes": {"wrap": "Black"},
        "kind": "canvas",
    },
    # Atelier
    "atelier-walnut-mat": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "black"},  # refine after probe samples
        "kind": "framed_print",
    },
    "atelier-oak-deep": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "natural"},
        "kind": "framed_print",
    },
    "atelier-black-deep": {
        "sku_template": "GLOBAL-FAP-{size}",
        "attributes": {"color": "black"},
        "kind": "framed_print",
    },
    "atelier-oak-floater": {
        "sku_template": "GLOBAL-CAN-{size}",
        "attributes": {"wrap": "ImageWrap"},
        "kind": "canvas",
    },
}


def parse_store_variant_id(store_variant_id: str) -> tuple[str, str]:
    """store_variant_id format: {family_id}__{size_key}"""
    if not store_variant_id:
        return "", ""
    if "__" in store_variant_id:
        fam, size = store_variant_id.split("__", 1)
        return fam, size
    return store_variant_id, ""


def resolve_prodigi(store_variant_id: Optional[str], size_key: str = "", family_id: str = "") -> Optional[dict]:
    """Return {sku, attributes, kind, family_id, size_key} or None if unmapped."""
    fam = family_id
    size = size_key
    if store_variant_id:
        f2, s2 = parse_store_variant_id(store_variant_id)
        fam = fam or f2
        size = size or s2
    if not fam or fam not in FAMILY_FULFILLMENT:
        return None
    spec = FAMILY_FULFILLMENT[fam]
    size_token = SIZE_TO_PRODIGI.get(size, size.replace("x", "x"))
    if not size_token:
        return None
    # Prodigi examples often use mixed case in path; normalize common form
    sku = spec["sku_template"].format(size=size_token)
    # Try uppercase size segment (GLOBAL-CAN-16X20 style)
    parts = sku.rsplit("-", 1)
    if len(parts) == 2:
        sku_alt = f"{parts[0]}-{parts[1].upper()}"
    else:
        sku_alt = sku.upper()
    return {
        "sku": sku_alt,
        "sku_candidates": [sku_alt, sku, sku.upper()],
        "attributes": dict(spec.get("attributes") or {}),
        "kind": spec.get("kind"),
        "family_id": fam,
        "size_key": size,
    }


def list_seed_skus() -> list[str]:
    """SKUs to probe in sandbox for US wall art."""
    sizes = [
        "8x10", "10x10", "11x14", "12x12", "12x16", "16x16",
        "16x20", "18x24", "20x20", "24x36", "30x40",
    ]
    prefixes = ["GLOBAL-CAN", "GLOBAL-FAP", "GLOBAL-PHO", "GLOBAL-CFP"]
    out: list[str] = []
    for pfx in prefixes:
        for s in sizes:
            out.append(f"{pfx}-{s}")
            out.append(f"{pfx}-{s.upper()}")
            out.append(f"{pfx}-{s.replace('x', 'X')}")
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq
