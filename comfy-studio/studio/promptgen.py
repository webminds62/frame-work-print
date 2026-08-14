import os
import random

import httpx

import presets

LEMONADE_URL = os.environ.get("LEMONADE_URL", "http://127.0.0.1:13305/v1").rstrip("/")
SYSTEM = (
    "You write prompts for local text-to-video and image models (Wan, LTX, Flux). "
    "Return only the finished prompt. No quotes, no preamble, no analysis. "
    "One or two sentences. Be visual and specific: subject, action, setting, lighting. "
    "Do not mention AI or brand names."
)
SEEDS = [
    "a boy sitting on concrete steps at dusk",
    "a woman in a wool coat walking through neon rain",
    "a fox crossing a snowy forest road",
    "an old fisherman mending nets on a wooden pier",
    "a dancer spinning in an empty warehouse",
    "a motorcycle rolling down an empty coastal highway",
    "steam rising from a night market food stall",
    "a child chasing paper lanterns down an alley",
]


def _local(idea, mode, camera, fmt):
    seed = (idea or "").strip() or random.choice(SEEDS)
    camera_item = presets.camera_by_id(camera)
    motion = camera_item.get("suffix") or "locked frame, subject in clear focus"
    aspect = {
        "16x9": "widescreen cinematic frame",
        "9x16": "vertical phone-frame composition",
        "1x1": "square centered composition",
    }.get(fmt, "cinematic frame")
    if mode == "still":
        return (
            f"{seed}, {aspect}, sharp focus, detailed face and clothing, "
            "natural color, soft rim light, photorealistic"
        )
    return (
        f"{seed}, {motion}, {aspect}, natural motion, detailed clothing and skin, "
        "cinematic lighting, shallow depth of field, photorealistic"
    )


def lemonade_status():
    try:
        response = httpx.get(f"{LEMONADE_URL}/models", timeout=2)
        response.raise_for_status()
        models = [item.get("id") for item in (response.json().get("data") or []) if item.get("id")]
        return {"ok": True, "url": LEMONADE_URL, "model": _pick_model(models), "models": models}
    except Exception as exc:
        return {"ok": False, "url": LEMONADE_URL, "error": str(exc)}


PREFERRED = (
    "Qwen3.5-4B-MTP-GGUF",
    "Qwen3-0.6B-GGUF",
    "DeepSeek-Qwen3-8B-GGUF",
)


def _pick_model(models):
    forced = os.environ.get("LEMONADE_MODEL")
    if forced:
        return forced
    available = set(models or [])
    for name in PREFERRED:
        if name in available:
            return name
    skip = {"image", "edit", "upscaling", "transcription", "tts", "realtime-transcription", "coding"}
    try:
        listing = httpx.get(f"{LEMONADE_URL}/models", timeout=2).json().get("data") or []
        for item in listing:
            labels = set(item.get("labels") or [])
            if item.get("downloaded") and item.get("recipe") == "llamacpp" and not (labels & skip):
                return item.get("id")
    except Exception:
        pass
    return next(iter(models), None)


def _extract(message):
    text = (message.get("content") or "").strip().strip('"')
    if text:
        return text
    reason = (message.get("reasoning_content") or "").strip()
    if not reason:
        return None
    lines = [line.strip().strip('"') for line in reason.splitlines() if line.strip()]
    for line in reversed(lines):
        if len(line) > 40 and not line.lower().startswith(("okay", "hmm", "i should", "the user", "wait")):
            return line
    return lines[-1] if lines else None


def _lemonade(idea, mode, camera, fmt):
    info = lemonade_status()
    if not info.get("ok") or not info.get("model"):
        return None, info
    seed = (idea or "").strip() or "invent a striking original scene"
    user = (
        f"/no_think\nMode: {mode}. Camera: {camera}. Format: {fmt}. "
        f"Idea: {seed}. Write only the generation prompt."
    )
    response = httpx.post(
        f"{LEMONADE_URL}/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": info["model"],
            "temperature": 0.8,
            "max_tokens": 400,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        },
        timeout=90,
    )
    response.raise_for_status()
    message = response.json()["choices"][0]["message"]
    text = _extract(message)
    if not text:
        return None, info
    return text, info


def _grok(idea, mode, camera, fmt):
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return None
    seed = (idea or "").strip() or "invent a striking original scene"
    user = (
        f"Mode: {mode}. Camera: {camera}. Format: {fmt}. "
        f"Idea: {seed}. Write the generation prompt."
    )
    response = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "grok-4.6",
            "temperature": 0.9,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip().strip('"') or None


def generate(idea="", mode="t2v", camera="static", fmt="16x9"):
    try:
        text, info = _lemonade(idea, mode, camera, fmt)
        if text:
            return {"prompt": text, "source": "lemonade", "model": info.get("model")}
    except Exception as exc:
        lemonade_error = str(exc)
    else:
        lemonade_error = None
    try:
        text = _grok(idea, mode, camera, fmt)
        if text:
            return {"prompt": text, "source": "grok"}
    except Exception:
        pass
    result = {"prompt": _local(idea, mode, camera, fmt), "source": "local"}
    if lemonade_error:
        result["lemonade_error"] = lemonade_error
    return result
