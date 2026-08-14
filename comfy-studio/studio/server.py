import argparse
import json
import random
import threading
import time
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import catalog
import comfy_client
import downloads
import jobs
import lemonade_image
import presets
import promptgen
import transcribe

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / "workflows"
UPLOADS = ROOT / "uploads"
STATIC = ROOT / "static"
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="ComfyUI Studio")
jobs.sweep_orphans()

STALE_AFTER = 90


def stop_other_jobs(keep_id=None):
    for job in jobs.active():
        if job["id"] == keep_id:
            continue
        jobs.update(job["id"], status="cancelled", error=None)
        try:
            comfy_client.delete_queued(job["id"])
        except Exception:
            pass
        try:
            comfy_client.interrupt(job["id"])
        except Exception:
            pass


def reconcile_jobs():
    try:
        live = comfy_client.active_prompt_ids()
    except Exception:
        live = set()
    now = time.time()
    for job in jobs.active():
        job_id = job["id"]
        request = job.get("request") or {}
        spec = catalog.get_model(request.get("model")) if request.get("model") else None
        if spec and spec.get("lemonade_image"):
            if now - (job.get("updated_at") or 0) > 600:
                jobs.update(job_id, status="error", error="Still timed out on Lemonade.")
            continue
        if job_id in live:
            continue
        try:
            history = comfy_client.get_history(job_id)
        except Exception:
            history = {}
        if history.get(job_id):
            outputs = comfy_client.collect_outputs(history, job_id)
            if outputs:
                jobs.update(job_id, status="done", outputs=outputs, error=None)
            else:
                jobs.update(job_id, status="error", error="Finished without output.")
        elif now - (job.get("updated_at") or 0) > STALE_AFTER:
            jobs.update(job_id, status="error", error="Stopped. ComfyUI is no longer running this job.")


def load_workflow(name):
    path = WORKFLOWS / name
    if not path.exists():
        raise HTTPException(404, f"workflow missing: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def patch_workflow(graph, model, payload, image_name=None):
    prompt = presets.apply_prompt(
        payload.get("prompt") or "",
        payload.get("camera") or "static",
        cinematic=bool(payload.get("cinematic", True)),
        family=model["family"],
    )
    negative = payload.get("negative")
    if negative is None or negative == "":
        negative = presets.DEFAULT_NEGATIVES["still" if model["mode"] == "still" else "video"]
    quality_id = payload.get("quality") or "quality"
    width, height = presets.size_for(payload.get("format") or "16x9", model["family"], quality_id)
    steps = presets.steps_for(model["family"], quality_id)
    seconds = 5
    duration = payload.get("duration") or "5s"
    if str(duration).endswith("s"):
        try:
            seconds = int(str(duration).replace("s", ""))
        except ValueError:
            seconds = 5
    length = presets.frames_for(model["family"], seconds)
    seed = payload.get("seed")
    if seed in (None, "", -1):
        seed = random.randint(0, 2**32 - 1)
    seed = int(seed)
    camera = presets.camera_by_id(payload.get("camera") or "static")

    if model.get("unet"):
        for node in graph.values():
            if node.get("class_type") == "UNETLoader":
                node["inputs"]["unet_name"] = model["unet"]

    for node_id, node in graph.items():
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type == "CLIPTextEncode":
            if node_id in ("6",):
                inputs["text"] = prompt
            elif node_id in ("7", "33"):
                inputs["text"] = negative
        elif class_type == "EmptyHunyuanLatentVideo":
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = length
        elif class_type == "EmptyLTXVLatentVideo":
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = length
        elif class_type == "EmptySD3LatentImage":
            inputs["width"] = width
            inputs["height"] = height
        elif class_type in ("WanImageToVideo", "WanCameraImageToVideo", "LTXVImgToVideo"):
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = length
        elif class_type == "WanCameraEmbedding":
            inputs["camera_pose"] = camera["wan_pose"]
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = length
        elif class_type == "KSampler":
            inputs["seed"] = seed
            inputs["steps"] = steps
        elif class_type == "SamplerCustom":
            inputs["noise_seed"] = seed
        elif class_type == "LTXVScheduler":
            inputs["steps"] = steps
        elif class_type == "LoadImage" and image_name:
            inputs["image"] = image_name
        elif class_type == "SaveAnimatedWEBP":
            inputs["filename_prefix"] = f"studio/{model['id']}"
            inputs["quality"] = 95
        elif class_type == "SaveImage":
            inputs["filename_prefix"] = f"studio/{model['id']}"
    refine = bool(payload.get("refine", True))
    attach_final_render(graph, refine)
    return {
        "prompt": prompt,
        "negative": negative,
        "width": width,
        "height": height,
        "length": length,
        "seed": seed,
        "steps": steps,
        "quality": quality_id,
        "refine": refine and bool(catalog.upscale_model()),
    }


def attach_final_render(graph, enabled):
    if not enabled:
        return
    model_name = catalog.upscale_model()
    if not model_name:
        return
    decode_id = None
    save_ids = []
    for node_id, node in graph.items():
        if node.get("class_type") == "VAEDecode":
            decode_id = node_id
        if node.get("class_type") in ("SaveAnimatedWEBP", "SaveImage", "SaveWEBM"):
            save_ids.append(node_id)
    if not decode_id:
        return
    graph["90"] = {
        "class_type": "UpscaleModelLoader",
        "inputs": {"model_name": model_name},
    }
    graph["91"] = {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {
            "upscale_model": ["90", 0],
            "image": [decode_id, 0],
        },
    }
    graph["92"] = {
        "class_type": "ImageSharpen",
        "inputs": {
            "image": ["91", 0],
            "sharpen_radius": 1,
            "sigma": 0.6,
            "alpha": 0.3,
        },
    }
    for save_id in save_ids:
        inputs = graph[save_id].setdefault("inputs", {})
        if "images" in inputs or graph[save_id]["class_type"] != "SaveImage":
            inputs["images"] = ["92", 0]
        if graph[save_id]["class_type"] == "SaveImage":
            inputs["images"] = ["92", 0]


def run_lemonade_still(job_id, model, payload):
    try:
        jobs.update(job_id, status="running", progress=0, progress_max=1)
        prompt = presets.apply_prompt(
            payload.get("prompt") or "",
            payload.get("camera") or "static",
            cinematic=bool(payload.get("cinematic", True)),
            family="still",
        )
        quality_id = payload.get("quality") or "quality"
        width, height = presets.size_for(payload.get("format") or "1x1", "flux", quality_id)
        steps = 8 if quality_id == "quality" else 4
        output = lemonade_image.generate_still(
            prompt=prompt,
            width=width,
            height=height,
            seed=payload.get("seed"),
            steps=steps,
            model_id=model.get("lemonade_model") or "Flux-2-Klein-9B-GGUF",
        )
        jobs.update(
            job_id,
            status="done",
            outputs=[output],
            meta={"prompt": prompt, "width": width, "height": height, "steps": steps, "backend": "lemonade"},
            progress=1,
            progress_max=1,
        )
    except Exception as exc:
        current = jobs.get(job_id) or {}
        if current.get("status") == "cancelled":
            return
        jobs.update(job_id, status="error", error=str(exc))


def run_job(job_id, model, payload, upload_path):
    if model.get("lemonade_image"):
        run_lemonade_still(job_id, model, payload)
        return
    try:
        jobs.update(job_id, status="running")
        image_name = None
        if upload_path:
            uploaded = comfy_client.upload_image(upload_path)
            image_name = uploaded.get("name") or Path(upload_path).name
        graph = load_workflow(model["workflow"])
        meta = patch_workflow(graph, model, payload, image_name=image_name)
        client_id = str(uuid.uuid4())
        prompt_id = job_id

        def on_progress(event):
            jobs.update(job_id, progress=event.get("value") or 0, progress_max=event.get("max") or 0)

        comfy_client.queue_prompt(graph, client_id, prompt_id)
        history = comfy_client.wait_for_prompt(prompt_id, client_id, on_progress=on_progress)
        current = jobs.get(job_id) or {}
        if current.get("status") == "cancelled":
            return
        outputs = comfy_client.collect_outputs(history, prompt_id)
        jobs.update(job_id, status="done", outputs=outputs, meta=meta, progress=1, progress_max=1)
    except comfy_client.Cancelled:
        jobs.update(job_id, status="cancelled", error=None)
    except Exception as exc:
        current = jobs.get(job_id) or {}
        if current.get("status") == "cancelled":
            return
        jobs.update(job_id, status="error", error=str(exc))


@app.get("/api/health")
def api_health():
    comfy = comfy_client.health()
    return {
        "ok": True,
        "studio": True,
        "comfy": comfy,
        "lemonade": promptgen.lemonade_status(),
        "whisper": transcribe.whisper_status(),
    }


@app.get("/api/models")
def api_models():
    return {"models": catalog.list_models()}


@app.post("/api/prompt")
def api_prompt(payload: dict = Body(default={})):
    result = promptgen.generate(
        idea=payload.get("idea") or "",
        mode=payload.get("mode") or "t2v",
        camera=payload.get("camera") or "static",
        fmt=payload.get("format") or "16x9",
    )
    return result


@app.post("/api/transcribe")
async def api_transcribe(audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "speech.webm").suffix or ".webm"
    path = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(await audio.read())
    try:
        return transcribe.transcribe(path, filename=audio.filename or path.name)
    except Exception as exc:
        raise HTTPException(502, str(exc))
    finally:
        try:
            path.unlink()
        except Exception:
            pass


@app.get("/api/downloads")
def api_downloads():
    return {"packs": downloads.list_packs(), "current": downloads.status()}


@app.post("/api/downloads/{pack_id}")
def api_download_start(pack_id: str):
    try:
        return downloads.start(pack_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/presets")
def api_presets():
    return {
        "cameras": presets.CAMERA_PRESETS,
        "formats": presets.FORMATS,
        "durations": presets.DURATIONS,
        "qualities": presets.QUALITY_LEVELS,
        "defaults": {
            "mode": "t2v",
            "model": (catalog.default_model("t2v") or {}).get("id"),
            "camera": "static",
            "format": "16x9",
            "duration": "5s",
            "quality": "quality",
            "refine": True,
            "cinematic": True,
            "refine_ready": bool(catalog.upscale_model()),
        },
    }


@app.get("/api/jobs")
def api_jobs():
    reconcile_jobs()
    return {"jobs": jobs.list_jobs()}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.get("status") not in ("queued", "running"):
        return {"ok": True, "job": job}
    jobs.update(job_id, status="cancelled", error=None)
    try:
        comfy_client.delete_queued(job_id)
    except Exception:
        pass
    try:
        comfy_client.interrupt(job_id)
    except Exception as exc:
        raise HTTPException(502, f"Could not stop ComfyUI: {exc}")
    return {"ok": True, "job": jobs.get(job_id)}


@app.get("/api/gallery")
def api_gallery():
    return {"items": jobs.gallery()}


@app.get("/api/media")
def api_media(filename: str, subfolder: str = "", type: str = "output"):
    payload = None
    try:
        payload = comfy_client.fetch_view(filename, subfolder=subfolder, folder_type=type)
    except Exception:
        payload = None
    if payload is None:
        local = Path(__file__).resolve().parent.parent / "app" / "output" / (subfolder or "") / filename
        if local.exists():
            payload = local.read_bytes()
    if payload is None:
        raise HTTPException(404, "media not found")
    media_type = "application/octet-stream"
    lower = filename.lower()
    if lower.endswith(".webp"):
        media_type = "image/webp"
    elif lower.endswith(".png"):
        media_type = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif lower.endswith(".mp4"):
        media_type = "video/mp4"
    elif lower.endswith(".webm"):
        media_type = "video/webm"
    return Response(content=payload, media_type=media_type)


@app.post("/api/generate")
async def api_generate(
    prompt: str = Form(...),
    model: str = Form(None),
    mode: str = Form("t2v"),
    camera: str = Form("static"),
    format: str = Form("16x9"),
    duration: str = Form("5s"),
    quality: str = Form("quality"),
    negative: str = Form(""),
    seed: str = Form(""),
    cinematic: str = Form("true"),
    refine: str = Form("true"),
    image: UploadFile | None = File(None),
):
    spec = catalog.get_model(model) if model else catalog.default_model(mode)
    if spec and spec.get("lemonade_image"):
        if not lemonade_image.image_ready(spec.get("lemonade_model")):
            raise HTTPException(503, "Lemonade is not reachable or Flux 2 Klein is not installed")
    else:
        comfy = comfy_client.health()
        if not comfy.get("ok"):
            raise HTTPException(503, f"ComfyUI is not reachable on 127.0.0.1:8188 ({comfy.get('error')})")

    spec = spec or catalog.default_model(mode)
    if not spec:
        raise HTTPException(400, "unknown model")
    if spec["mode"] != mode:
        raise HTTPException(400, f"{spec['label']} does not support {mode}")
    if not spec["ready"]:
        missing = ", ".join(spec["missing"]) or "workflow"
        raise HTTPException(409, f"{spec['label']} is not ready. Missing: {missing}")
    if mode in ("i2v",) and image is None:
        raise HTTPException(400, "image-to-video needs a start frame")

    upload_path = None
    if image is not None:
        suffix = Path(image.filename or "frame.png").suffix or ".png"
        upload_path = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
        upload_path.write_bytes(await image.read())

    payload = {
        "prompt": prompt,
        "model": spec["id"],
        "mode": mode,
        "camera": camera,
        "format": format,
        "duration": duration,
        "quality": quality if quality in ("fast", "quality") else "quality",
        "negative": negative,
        "seed": int(seed) if str(seed).strip().lstrip("-").isdigit() else None,
        "cinematic": str(cinematic).lower() not in ("0", "false", "no"),
        "refine": str(refine).lower() not in ("0", "false", "no"),
    }
    stop_other_jobs()
    job = jobs.create(payload)
    thread = threading.Thread(
        target=run_job,
        args=(job["id"], spec, payload, str(upload_path) if upload_path else None),
        daemon=True,
    )
    thread.start()
    return {"job_id": job["id"], "job": job}


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    import uvicorn

    url = f"http://{args.host}:{args.port}"
    access = ROOT.parent / "AMD Ai One" / "STUDIO-URL.txt"
    access.parent.mkdir(parents=True, exist_ok=True)
    access.write_text(url + "\n", encoding="utf-8")
    print(url, flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
