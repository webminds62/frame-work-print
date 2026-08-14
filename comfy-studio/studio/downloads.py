import threading
import time
import urllib.request
from pathlib import Path

from catalog import MODELS, _file_exists

HF = "https://huggingface.co"

PACKS = [
    {
        "id": "wan-i2v-480",
        "label": "Wan 2.1 I2V 480p (fp8)",
        "note": "Image-to-video, ~14 GB",
        "files": [{
            "url": f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors?download=true",
            "path": ["diffusion_models", "wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors"],
        }],
    },
    {
        "id": "wan-camera",
        "label": "Wan Fun Camera 1.3B",
        "note": "Native camera moves for I2V",
        "files": [{
            "url": f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_fun_camera_v1.1_1.3B_bf16.safetensors?download=true",
            "path": ["diffusion_models", "wan2.1_fun_camera_v1.1_1.3B_bf16.safetensors"],
        }],
    },
    {
        "id": "wan-t2v-14b",
        "label": "Wan 2.1 T2V 14B (fp8)",
        "note": "Sharper text-to-video, ~14 GB",
        "files": [{
            "url": f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_14B_fp8_e4m3fn.safetensors?download=true",
            "path": ["diffusion_models", "wan2.1_t2v_14B_fp8_e4m3fn.safetensors"],
        }],
    },
    {
        "id": "hunyuan-support",
        "label": "Hunyuan 720p encoders + VAE",
        "note": "Unlocks the Hunyuan unet already on disk",
        "files": [
            {
                "url": f"{HF}/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/vae/hunyuan_video_vae_bf16.safetensors?download=true",
                "path": ["vae", "hunyuan_video_vae_bf16.safetensors"],
            },
            {
                "url": f"{HF}/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/text_encoders/clip_l.safetensors?download=true",
                "path": ["text_encoders", "clip_l.safetensors"],
            },
            {
                "url": f"{HF}/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/text_encoders/llava_llama3_fp8_scaled.safetensors?download=true",
                "path": ["text_encoders", "llava_llama3_fp8_scaled.safetensors"],
            },
        ],
    },
    {
        "id": "upscale-x2",
        "label": "Final render upscale (RealESRGAN 2x)",
        "note": "Post-process sharper frames",
        "files": [{
            "url": f"{HF}/ai-forever/Real-ESRGAN/resolve/main/RealESRGAN_x2.pth?download=true",
            "path": ["upscale_models", "RealESRGAN_x2.pth"],
        }],
    },
]

_STATE = {
    "id": None,
    "status": "idle",
    "label": None,
    "file": None,
    "bytes": 0,
    "total": 0,
    "error": None,
}
_LOCK = threading.Lock()


def _dest(parts):
    path = MODELS
    for part in parts:
        path = path / part
    return path


def describe_pack(pack):
    missing = [item["path"][-1] for item in pack["files"] if not _file_exists(item["path"])]
    return {
        "id": pack["id"],
        "label": pack["label"],
        "note": pack.get("note") or "",
        "installed": not missing,
        "missing": missing,
    }


def list_packs():
    return [describe_pack(pack) for pack in PACKS]


def get_pack(pack_id):
    for pack in PACKS:
        if pack["id"] == pack_id:
            return pack
    return None


def status():
    with _LOCK:
        return dict(_STATE)


def _set(**fields):
    with _LOCK:
        _STATE.update(fields)


def start(pack_id):
    pack = get_pack(pack_id)
    if not pack:
        raise ValueError("unknown download")
    with _LOCK:
        if _STATE["status"] == "running":
            raise RuntimeError(f"already downloading {_STATE['label']}")
    _set(id=pack_id, status="running", label=pack["label"], file=None, bytes=0, total=0, error=None)
    thread = threading.Thread(target=_run, args=(pack,), daemon=True)
    thread.start()
    return status()


def _run(pack):
    try:
        for item in pack["files"]:
            dest = _dest(item["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size > 0:
                continue
            tmp = dest.with_suffix(dest.suffix + ".part")
            _set(file=dest.name, bytes=0, total=0)

            def hook(block, size, total):
                _set(bytes=block * size, total=total or 0)

            urllib.request.urlretrieve(item["url"], tmp, hook)
            tmp.replace(dest)
        _set(status="done", bytes=_STATE.get("total") or _STATE.get("bytes") or 0)
    except Exception as exc:
        _set(status="error", error=str(exc))
