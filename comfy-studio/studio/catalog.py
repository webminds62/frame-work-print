from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
MODELS = APP / "models"

MODELSPEC = [
    {
        "id": "wan21-1.3b-t2v",
        "label": "Wan 2.1 1.3B",
        "family": "wan",
        "mode": "t2v",
        "tier": "fast",
        "workflow": "wan21_t2v.json",
        "default": True,
        "download": "wan/text1.3b.js",
        "needs": [
            ["diffusion_models", "wan2.1_t2v_1.3B_bf16.safetensors"],
            ["vae", "wan_2.1_vae.safetensors"],
            ["text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
        ],
        "any_of": [
            ["diffusion_models", "wan2.1_t2v_1.3B_fp16.safetensors"],
        ],
        "unet_candidates": [
            "wan2.1_t2v_1.3B_bf16.safetensors",
            "wan2.1_t2v_1.3B_fp16.safetensors",
            "wan2.1_t2v_1.3B_fp8_e4m3fn.safetensors",
        ],
    },
    {
        "id": "wan21-14b-t2v",
        "label": "Wan 2.1 14B",
        "family": "wan",
        "mode": "t2v",
        "tier": "quality",
        "workflow": "wan21_t2v.json",
        "download": "wan/text14b.js",
        "needs": [
            ["vae", "wan_2.1_vae.safetensors"],
            ["text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
        ],
        "unet_candidates": [
            "wan2.1_t2v_14B_fp8_e4m3fn.safetensors",
            "wan2.1_t2v_14B_bf16.safetensors",
            "wan2.1_t2v_14B_fp16.safetensors",
        ],
    },
    {
        "id": "ltx-t2v",
        "label": "LTX Video 0.9.5",
        "family": "ltx",
        "mode": "t2v",
        "tier": "fast",
        "workflow": "ltx_t2v.json",
        "download": "ltx/install.js",
        "needs": [
            ["checkpoints", "ltx-video-2b-v0.9.5.safetensors"],
            ["clip", "t5xxl_fp8_e4m3fn_scaled.safetensors"],
        ],
    },
    {
        "id": "ltx-i2v",
        "label": "LTX Video 0.9.5",
        "family": "ltx",
        "mode": "i2v",
        "tier": "fast",
        "workflow": "ltx_i2v.json",
        "download": "ltx/install.js",
        "needs": [
            ["checkpoints", "ltx-video-2b-v0.9.5.safetensors"],
            ["clip", "t5xxl_fp8_e4m3fn_scaled.safetensors"],
        ],
    },
    {
        "id": "wan21-i2v-480",
        "label": "Wan 2.1 I2V 480p",
        "family": "wan",
        "mode": "i2v",
        "tier": "quality",
        "workflow": "wan21_i2v.json",
        "download": "wan/image480p.js",
        "needs": [
            ["vae", "wan_2.1_vae.safetensors"],
            ["text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
            ["clip_vision", "clip_vision_h.safetensors"],
        ],
        "unet_candidates": [
            "wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors",
            "wan2.1_i2v_480p_14B_fp16.safetensors",
            "wan2.1_i2v_480p_14B_bf16.safetensors",
        ],
    },
    {
        "id": "wan21-camera",
        "label": "Wan Fun Camera 1.3B",
        "family": "wan",
        "mode": "i2v",
        "tier": "fast",
        "workflow": "wan21_camera_i2v.json",
        "camera_native": True,
        "download": "wan/text1.3b.js",
        "needs": [
            ["vae", "wan_2.1_vae.safetensors"],
            ["text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
            ["clip_vision", "clip_vision_h.safetensors"],
        ],
        "unet_candidates": [
            "wan2.1_fun_camera_v1.1_1.3B_bf16.safetensors",
            "wan2.1_fun_camera_v1.1_1.3B_fp16.safetensors",
        ],
    },
    {
        "id": "lemonade-flux2-klein",
        "label": "Lemonade Flux 2 Klein 9B",
        "family": "flux",
        "mode": "still",
        "tier": "fast",
        "workflow": None,
        "lemonade_image": True,
        "lemonade_model": "Flux-2-Klein-9B-GGUF",
        "default": True,
    },
    {
        "id": "flux-schnell",
        "label": "Flux Schnell (ComfyUI)",
        "family": "flux",
        "mode": "still",
        "tier": "fast",
        "workflow": "flux_schnell_t2i.json",
        "download": "download-flux-schnell-fp8.json",
        "needs": [
            ["checkpoints", "flux1-schnell-fp8.safetensors"],
        ],
    },
    {
        "id": "qwen-image",
        "label": "Qwen Image",
        "family": "qwen",
        "mode": "still",
        "tier": "quality",
        "workflow": None,
        "download": None,
        "needs": [
            ["diffusion_models", "qwen_image_bf16.safetensors"],
        ],
    },
]


def _file_exists(parts):
    path = MODELS
    for part in parts:
        path = path / part
    return path.exists() and path.stat().st_size > 0


def _first_existing(folder, names):
    for name in names:
        path = MODELS / folder / name
        if path.exists() and path.stat().st_size > 0:
            return name
    return None


def describe(spec):
    missing = []
    resolved = {}
    if spec.get("lemonade_image"):
        import lemonade_image
        model_id = spec.get("lemonade_model") or "Flux-2-Klein-9B-GGUF"
        ready = lemonade_image.image_ready(model_id)
        if not ready:
            missing.append(f"Lemonade:{model_id}")
        return {
            "id": spec["id"],
            "label": spec["label"],
            "family": spec["family"],
            "mode": spec["mode"],
            "tier": spec["tier"],
            "workflow": None,
            "download": None,
            "lemonade_image": True,
            "lemonade_model": model_id,
            "camera_native": False,
            "default": bool(spec.get("default")),
            "ready": ready,
            "missing": missing,
            "resolved": resolved,
            "unet": None,
        }
    for item in spec.get("needs", []):
        if not _file_exists(item):
            missing.append("/".join(item))
        else:
            resolved[item[-1]] = item[-1]
    unet = None
    if spec.get("unet_candidates"):
        unet = _first_existing("diffusion_models", spec["unet_candidates"])
        if not unet:
            missing.append("diffusion_models/" + spec["unet_candidates"][0])
        else:
            resolved["unet"] = unet
    ready = not missing and spec.get("workflow")
    return {
        "id": spec["id"],
        "label": spec["label"],
        "family": spec["family"],
        "mode": spec["mode"],
        "tier": spec["tier"],
        "workflow": spec.get("workflow"),
        "download": spec.get("download"),
        "camera_native": bool(spec.get("camera_native")),
        "default": bool(spec.get("default")),
        "ready": bool(ready),
        "missing": missing,
        "resolved": resolved,
        "unet": unet,
    }


def list_models():
    return [describe(spec) for spec in MODELSPEC]


def get_model(model_id):
    for spec in MODELSPEC:
        if spec["id"] == model_id:
            return describe(spec)
    return None


UPSCALE_CANDIDATES = [
    "RealESRGAN_x2.pth",
    "RealESRGAN_x2plus.pth",
    "RealESRGAN_x4.pth",
    "4x-UltraSharp.pth",
]


def upscale_model():
    return _first_existing("upscale_models", UPSCALE_CANDIDATES)


def default_model(mode="t2v"):
    models = [item for item in list_models() if item["mode"] == mode]
    ready = [item for item in models if item["ready"]]
    for item in ready:
        if item.get("default"):
            return item
    return ready[0] if ready else (models[0] if models else None)
