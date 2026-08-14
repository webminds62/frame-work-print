import base64
import os
import uuid
from pathlib import Path

import httpx

from promptgen import LEMONADE_URL

FLUX_KLEIN = "Flux-2-Klein-9B-GGUF"
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "output" / "studio"


def image_ready(model_id=FLUX_KLEIN):
    try:
        data = httpx.get(f"{LEMONADE_URL}/models", timeout=2).json()
        for item in data.get("data") or []:
            if item.get("id") == model_id and item.get("downloaded"):
                return True
    except Exception:
        return False
    return False


def generate_still(prompt, width, height, seed=None, steps=4, cfg_scale=1.0, model_id=FLUX_KLEIN):
    payload = {
        "model": model_id,
        "prompt": prompt,
        "n": 1,
        "size": f"{int(width)}x{int(height)}",
        "response_format": "b64_json",
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
    }
    if seed not in (None, ""):
        payload["seed"] = int(seed)
    response = httpx.post(
        f"{LEMONADE_URL}/images/generations",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    body = response.json()
    data = (body.get("data") or [None])[0] or {}
    b64 = data.get("b64_json")
    if not b64:
        raise RuntimeError(body.get("error") or "Lemonade returned no image")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    name = f"lemonade_flux2_{uuid.uuid4().hex[:8]}.png"
    path = OUTPUT / name
    path.write_bytes(base64.b64decode(b64))
    return {
        "filename": name,
        "subfolder": "studio",
        "type": "output",
        "kind": "image",
        "model": model_id,
    }
