import requests

BASE = "http://localhost:8001/api"
s = requests.Session()

tok = s.post(f"{BASE}/auth/login", json={"email": "demo@threadai.com", "password": "Password123"}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}

print("generating...")
img = s.post(f"{BASE}/generate", headers=H, json={"prompt": "minimalist mountain line art"}).json()["image_base64"]
print("img len", len(img))

did = s.post(f"{BASE}/designs", headers=H, json={"prompt": "mountains", "image_base64": img}).json()["id"]
print("design id", did)

r = s.get(f"{BASE}/public/design/{did}")
print("public image:", r.status_code, r.headers.get("content-type"), len(r.content), "bytes")

print("placing Printful order...")
order = s.post(f"{BASE}/orders", headers=H, json={
    "design_id": did,
    "image_base64": img,
    "prompt": "mountains",
    "shirt_color": "black",
    "size": "M",
    "quantity": 1,
    "recipient": {
        "name": "Test Buyer",
        "address1": "19749 Dearborn St",
        "city": "Chatsworth",
        "state_code": "CA",
        "country_code": "US",
        "zip": "91311",
    },
}).json()
print("status:", order.get("status"))
print("printful_status:", order.get("printful_status"))
print("printful_order_id:", order.get("printful_order_id"))
