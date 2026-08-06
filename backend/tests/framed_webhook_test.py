import os, uuid, requests
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv("/app/backend/.env")

BASE = "http://localhost:8001/api"
r = requests.post(f"{BASE}/auth/login", json={"email": "demo@frameworks.com", "password": "Password123"}, timeout=30)
if r.status_code != 200:
    r = requests.post(f"{BASE}/auth/register", json={"email": "demo@frameworks.com", "password": "Password123", "name": "Demo"}, timeout=30)
tok = r.json()["token"]
H = {"Authorization": f"Bearer {tok}"}
rcp = {"name": "Alex", "address1": "123 Main St", "city": "Austin", "state_code": "TX", "country_code": "US", "zip": "78701"}

def quote(material, size, frame):
    q = {"material": material, "size": size, "panels": 1, "frame": frame, "fallback_price": 89.0, "recipient": rcp}
    rr = requests.post(f"{BASE}/quote", headers=H, json=q, timeout=90)
    return rr.status_code, rr.json()

print("=== QUOTE framed vs frameless (canvas 18x24) ===")
for frame in ["none", "wood", "black"]:
    sc, j = quote("canvas", "18x24", frame)
    print(f"frame={frame:5s} -> {sc} source={j.get('source')} retail={j.get('retail')} product={j.get('product')} ship={j.get('shipping')}")

print("\n=== WEBHOOK package_shipped ===")
mongo = MongoClient(os.environ["MONGO_URL"])
db = mongo[os.environ["DB_NAME"]]
pf_id = "TESTPF" + uuid.uuid4().hex[:6]
oid = str(uuid.uuid4())
db.orders.insert_one({
    "id": oid, "user_id": "webhook-test", "user_email": "delivered@resend.dev",
    "status": "in_production", "printful_order_id": pf_id, "material": "canvas",
    "size": "18x24", "frame": "wood", "price": 149.0, "created_at": "2026-07-30T00:00:00",
})
payload = {"type": "package_shipped", "data": {"order": {"id": pf_id},
           "shipment": {"tracking_url": "https://tracking.example.com/XYZ123"}}}
rr = requests.post(f"{BASE}/webhooks/printful", json=payload, timeout=30)
print("webhook status", rr.status_code, rr.json())
doc = db.orders.find_one({"id": oid}, {"_id": 0, "status": 1, "tracking_url": 1})
print("order after webhook ->", doc)
db.orders.delete_one({"id": oid})
print("cleaned up test order:", "OK" if doc and doc.get("status") == "shipped" else "STATUS NOT UPDATED")
