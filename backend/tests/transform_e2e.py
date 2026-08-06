import base64, io, time, requests
from PIL import Image

BASE = "http://localhost:8001/api"

# login as demo (fallback register)
r = requests.post(f"{BASE}/auth/login", json={"email": "demo@frameworks.com", "password": "Password123"})
if r.status_code != 200:
    r = requests.post(f"{BASE}/auth/register", json={"email": "demo@frameworks.com", "password": "Password123", "name": "Demo"})
tok = r.json()["token"]
print("auth ok")

# make a small test image
im = Image.new("RGB", (256, 256), (180, 140, 90))
buf = io.BytesIO(); im.save(buf, format="PNG")
b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

t0 = time.time()
r = requests.post(f"{BASE}/transform", headers={"Authorization": f"Bearer {tok}"},
                  json={"image_base64": b64, "style": "watercolor", "enhance": True, "remove_bg": False}, timeout=180)
print("transform status", r.status_code, "elapsed", round(time.time()-t0, 1), "s")
if r.status_code == 200:
    out = r.json()["image_base64"]
    print("result len", len(out), "prefix", out[:30])
else:
    print("body", r.text[:400])
