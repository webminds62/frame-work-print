import json
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import websocket

COMFY_HOST = "127.0.0.1:8188"
COMFY_HTTP = f"http://{COMFY_HOST}"


class ComfyError(RuntimeError):
    pass


class Cancelled(ComfyError):
    pass


def _request(path, data=None, method=None, timeout=30):
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(COMFY_HTTP + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = response.read()
            if not payload:
                return None
            if response.headers.get_content_type() == "application/json" or payload[:1] in (b"{", b"["):
                return json.loads(payload)
            return payload
    except Exception as exc:
        detail = ""
        if hasattr(exc, "read"):
            try:
                detail = exc.read().decode("utf-8", "ignore")
            except Exception:
                detail = ""
        raise ComfyError(detail or str(exc)) from exc


def health():
    try:
        stats = _request("/system_stats", timeout=3)
        return {"ok": True, "system": stats}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def queue_prompt(prompt, client_id, prompt_id):
    payload = {"prompt": prompt, "client_id": client_id, "prompt_id": prompt_id}
    result = _request("/prompt", data=payload, timeout=60)
    if isinstance(result, dict) and result.get("error"):
        raise ComfyError(json.dumps(result["error"]))
    if isinstance(result, dict) and result.get("node_errors"):
        raise ComfyError(json.dumps(result["node_errors"]))
    return result


def get_history(prompt_id):
    return _request(f"/history/{prompt_id}", timeout=30) or {}


def get_queue():
    return _request("/queue", timeout=10) or {"queue_running": [], "queue_pending": []}


def active_prompt_ids():
    queue = get_queue()
    ids = set()
    for bucket in (queue.get("queue_running") or [], queue.get("queue_pending") or []):
        for item in bucket:
            if isinstance(item, (list, tuple)) and len(item) > 1:
                ids.add(item[1])
    return ids


def upload_image(path, name=None):
    path = Path(path)
    name = name or path.name
    boundary = uuid.uuid4().hex
    file_bytes = path.read_bytes()
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode()
    )
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="overwrite"\r\n\r\n')
    parts.append(b"true\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = Request(
        COMFY_HTTP + "/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def view_url(filename, subfolder="", folder_type="output"):
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    return f"{COMFY_HTTP}/view?{query}"


def fetch_view(filename, subfolder="", folder_type="output"):
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    return _request(f"/view?{query}", timeout=60)


def wait_for_prompt(prompt_id, client_id, on_progress=None, timeout=3600):
    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFY_HOST}/ws?clientId={client_id}", timeout=30)
    ws.settimeout(timeout)
    try:
        while True:
            try:
                raw = ws.recv()
            except Exception:
                history = get_history(prompt_id)
                if history.get(prompt_id):
                    return history
                raise
            if not isinstance(raw, str):
                continue
            message = json.loads(raw)
            kind = message.get("type")
            data = message.get("data") or {}
            if kind == "progress" and on_progress:
                on_progress({
                    "value": data.get("value"),
                    "max": data.get("max"),
                    "prompt_id": data.get("prompt_id"),
                })
            if kind == "execution_interrupted" and data.get("prompt_id") == prompt_id:
                raise Cancelled("cancelled")
            if kind == "execution_error" and data.get("prompt_id") == prompt_id:
                raise ComfyError(data.get("exception_message") or "ComfyUI execution error")
            if kind == "executing":
                if data.get("node") is None and data.get("prompt_id") == prompt_id:
                    break
    finally:
        ws.close()
    return get_history(prompt_id)


def interrupt(prompt_id=None):
    payload = {"prompt_id": prompt_id} if prompt_id else {}
    return _request("/interrupt", data=payload, method="POST", timeout=10)


def delete_queued(prompt_id):
    return _request("/queue", data={"delete": [prompt_id]}, method="POST", timeout=10)


def collect_outputs(history, prompt_id):
    entry = history.get(prompt_id) or {}
    outputs = entry.get("outputs") or {}
    files = []
    for node_output in outputs.values():
        for key in ("images", "gifs", "videos"):
            for item in node_output.get(key, []):
                files.append({
                    "filename": item.get("filename"),
                    "subfolder": item.get("subfolder") or "",
                    "type": item.get("type") or "output",
                    "kind": "video" if str(item.get("filename", "")).endswith((".webm", ".mp4")) else "image",
                })
    return files
