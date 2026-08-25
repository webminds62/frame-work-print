#!/usr/bin/env python3
"""Probe Prodigi sandbox for wall-art SKUs that ship to the US.

Usage:
  export PRODIGI_API_KEY=...
  export PRODIGI_BASE_URL=https://api.sandbox.prodigi.com
  python3 tools/prodigi_sku_probe.py

Writes:
  tools/out/prodigi_probe_raw.json
  tools/out/prodigi_us_wall_art.json
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env")

import prodigi_client  # noqa: E402
from prodigi_catalog import list_seed_skus  # noqa: E402

OUT = ROOT / "tools" / "out"
OUT.mkdir(parents=True, exist_ok=True)


def classify(sku: str, description: str) -> str:
    blob = f"{sku} {description}".lower()
    if "can" in sku.lower() or "canvas" in blob:
        return "canvas"
    if "frame" in blob or "fap" in sku.lower() or "cfp" in sku.lower():
        return "framed"
    if "pho" in sku.lower() or "poster" in blob or "print" in blob:
        return "poster"
    return "other"


def ships_us(product: dict) -> bool:
    variants = (product.get("product") or product).get("variants") or []
    for v in variants:
        ships = v.get("shipsTo") or []
        if "US" in ships:
            return True
    # some payloads nest differently
    return "US" in json.dumps(product)


async def probe_one(sku: str) -> dict:
    try:
        data = await prodigi_client.get_product(sku)
        product = data.get("product") or data
        desc = product.get("description") or ""
        return {
            "sku": sku,
            "ok": True,
            "description": desc,
            "category_guess": classify(sku, desc),
            "ships_to_us": ships_us(data),
            "attributes": product.get("attributes") or {},
            "dimensions": product.get("productDimensions"),
            "raw_outcome": data.get("outcome"),
        }
    except Exception as e:
        return {"sku": sku, "ok": False, "error": str(e)[:200]}


async def main():
    if not prodigi_client.configured():
        print("PRODIGI_API_KEY not set in backend/.env — cannot probe live.")
        print("Add your sandbox key, then re-run.")
        seeds = list_seed_skus()
        (OUT / "prodigi_sku_seeds.json").write_text(json.dumps(seeds, indent=2))
        print(f"Wrote {len(seeds)} seed SKUs to tools/out/prodigi_sku_seeds.json")
        return 1

    seeds = list_seed_skus()
    print(f"Probing {len(seeds)} SKUs against {prodigi_client.PRODIGI_BASE_URL} ...")
    results = []
    # gentle concurrency
    sem = asyncio.Semaphore(5)

    async def run(sku):
        async with sem:
            await asyncio.sleep(0.15)
            return await probe_one(sku)

    results = await asyncio.gather(*[run(s) for s in seeds])
    raw_path = OUT / "prodigi_probe_raw.json"
    raw_path.write_text(json.dumps(results, indent=2))
    us = [
        r
        for r in results
        if r.get("ok") and r.get("ships_to_us") and r.get("category_guess") in {"canvas", "framed", "poster"}
    ]
    us_path = OUT / "prodigi_us_wall_art.json"
    us_path.write_text(json.dumps(us, indent=2))
    print(f"OK total: {sum(1 for r in results if r.get('ok'))}")
    print(f"US wall art: {len(us)}")
    print(f"Wrote {raw_path}")
    print(f"Wrote {us_path}")
    by_cat = {}
    for r in us:
        by_cat.setdefault(r["category_guess"], []).append(r["sku"])
    for k, v in by_cat.items():
        print(f"  {k}: {len(v)} e.g. {v[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
