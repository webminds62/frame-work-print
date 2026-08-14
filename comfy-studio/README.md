# ComfyUI + Studio

A Pinokio launcher for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) with a cinematic **Studio** frontend for text-to-video, image-to-video, and still generation.

ComfyUI remains the node graph and inference engine. Studio is a control surface that submits official-style workflows through the ComfyUI HTTP API.

## What it does

- Generate short clips from a text prompt (Wan 2.1 1.3B, LTX Video).
- Animate a start frame or character still (LTX image-to-video; Wan I2V when those weights are downloaded).
- Create stills with Flux Schnell and send them into image-to-video.
- Apply camera language (dolly, pan, crane, orbit, handheld). If Wan Fun Camera weights are present, Studio uses the native camera node; otherwise the same preset is written into the prompt.
- Keep social formats (16:9, 9:16, 1:1) and 3s / 5s durations model-safe for a 32 GB Radeon AI PRO R9700.

On this launcher the default path is **Wan 2.1 1.3B text-to-video**. That model, its VAE, and the UMT5 encoder are already wired by the existing download scripts.

## Where to find it

Studio lives in the **AMD Ai One** folder:

- `/home/mark/AMD Ai One`
- `/home/mark/Desktop/AMD Ai One`
- `/home/mark/pinokio/api/comfy.git/AMD Ai One`

Clips are in `clips/` inside that folder. Double-click `Open-Studio.sh` to open the web app. In Pinokio the menu item is **AMD Ai One**.

## How to use

1. Install this app in Pinokio (`install.js`). That clones ComfyUI, installs PyTorch, and creates the Studio venv.
2. Download the models you want from **Download Mix** / **Download Models**. Wan 1.3B, LTX 0.9.5, and Flux Schnell are the Studio MVP set.
3. Click **Start Studio** (the default) to open the cinematic UI. That also launches ComfyUI in the background if it is not already running. Use **Start ComfyUI** if you only want the node graph.
4. Pick a mode, write a prompt, choose camera / format / duration, and Generate. **Record voice** or **Upload audio** sends speech to Lemonade `Whisper-Large-v3-Turbo` and fills the prompt.
5. Finished clips land in the Studio gallery and in `app/output/studio/`.

Models without weights stay visible but are marked **download required**. They cannot be queued.

## Hardware notes

Studio is built for a single local GPU, including AMD ROCm (Radeon AI PRO R9700 32 GB). It does not install a second PyTorch. All diffusion stays in `app/env`.

- Fast: Wan 1.3B, LTX 2B, Flux Schnell
- Quality, one job at a time: Hunyuan 720p fp8, Wan 2.2 5B / 14B (later)

## API

Studio listens on `127.0.0.1` at the Pinokio-assigned port. Replace `BASE` with that URL (shown as **Open Studio**).

### Javascript

```javascript
const health = await fetch(`${BASE}/api/health`).then((r) => r.json())

const body = new FormData()
body.set("prompt", "a fox running through winter trees, tracking camera")
body.set("model", "wan21-1.3b-t2v")
body.set("mode", "t2v")
body.set("camera", "dolly_in")
body.set("format", "16x9")
body.set("duration", "5s")

const job = await fetch(`${BASE}/api/generate`, { method: "POST", body }).then((r) => r.json())
const status = await fetch(`${BASE}/api/jobs/${job.job_id}`).then((r) => r.json())
```

### Python

```python
import httpx

base = "http://127.0.0.1:PORT"
print(httpx.get(f"{base}/api/models").json())

files = None  # or {"image": open("frame.png", "rb")}
data = {
    "prompt": "neon rain on a city street, cinematic",
    "model": "ltx-t2v",
    "mode": "t2v",
    "camera": "handheld",
    "format": "9x16",
    "duration": "3s",
}
print(httpx.post(f"{base}/api/generate", data=data, files=files).json())
```

### Curl

```bash
curl -s "$BASE/api/health"
curl -s "$BASE/api/presets"
curl -s "$BASE/api/gallery"

curl -s -F "prompt=a woman walking through neon rain" \
  -F "model=wan21-1.3b-t2v" \
  -F "mode=t2v" \
  -F "camera=static" \
  -F "format=16x9" \
  -F "duration=5s" \
  "$BASE/api/generate"
```

Useful endpoints: `GET /api/health`, `GET /api/models`, `GET /api/presets`, `POST /api/generate`, `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/gallery`, `GET /api/media`.

ComfyUI itself remains at `http://127.0.0.1:8188` and can still be used as a graph editor.
