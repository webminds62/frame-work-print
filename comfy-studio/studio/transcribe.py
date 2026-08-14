import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from promptgen import LEMONADE_URL

WHISPER_PREFERRED = (
    "Whisper-Large-v3-Turbo",
    "Whisper-Tiny",
)


def whisper_status():
    try:
        response = httpx.get(f"{LEMONADE_URL}/models", timeout=2)
        response.raise_for_status()
        models = [item.get("id") for item in (response.json().get("data") or []) if item.get("id")]
    except Exception as exc:
        return {"ok": False, "url": LEMONADE_URL, "error": str(exc), "model": None, "models": []}
    forced = os.environ.get("LEMONADE_WHISPER")
    available = set(models)
    if forced:
        model = forced if forced in available else None
    else:
        model = next((name for name in WHISPER_PREFERRED if name in available), None)
    return {
        "ok": bool(model),
        "url": LEMONADE_URL,
        "model": model,
        "models": [name for name in models if "whisper" in name.lower()],
    }


def _to_wav(src, dest):
    if src.suffix.lower() == ".wav":
        shutil.copyfile(src, dest)
        return dest
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Lemonade Whisper needs WAV. Install ffmpeg to convert other audio.")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "ffmpeg failed").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "Could not convert audio to WAV")
    return dest


def transcribe(path, filename="audio.wav"):
    info = whisper_status()
    if not info.get("ok") or not info.get("model"):
        raise RuntimeError(info.get("error") or "Whisper-Large-v3-Turbo is not available on Lemonade")
    src = Path(path)
    with tempfile.TemporaryDirectory() as tmp:
        wav = _to_wav(src, Path(tmp) / "speech.wav")
        with wav.open("rb") as handle:
            response = httpx.post(
                f"{LEMONADE_URL}/audio/transcriptions",
                data={"model": info["model"], "response_format": "json"},
                files={"file": (filename if filename.lower().endswith(".wav") else "speech.wav", handle, "audio/wav")},
                timeout=180,
            )
        if response.status_code >= 400:
            raise RuntimeError(response.text[:400] or f"Lemonade {response.status_code}")
        body = response.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise RuntimeError("Whisper returned empty text")
    return {"text": text, "model": info["model"], "source": "lemonade"}
