from fastapi import FastAPI, APIRouter, HTTPException, Depends, Response, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import uuid
import bcrypt
import jwt
from pathlib import Path
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta

import litellm
import io
import asyncio
import tempfile
import html as html_lib
import hashlib
import hmac
import json
import httpx
from PIL import Image as PILImage
from pymongo import ReturnDocument

from ai_features import (
    demo_room_preview,
    generation_cache_key,
)
from pathlib import Path as _PathForDotenv
from dotenv import load_dotenv as _load_dotenv_early
_load_dotenv_early(_PathForDotenv(__file__).resolve().parent / ".env")
import prodigi_client
from prodigi_catalog import resolve_prodigi

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 30
# Image previews default to a provider-free demo mode. Cloud mode is opt-in.
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
AI_DEMO_MODE = os.environ.get("AI_DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
AI_DAILY_CLOUD_LIMIT = max(1, int(os.environ.get("AI_DAILY_CLOUD_LIMIT", "3")))
AI_CACHE_TTL_HOURS = max(1, int(os.environ.get("AI_CACHE_TTL_HOURS", "24")))
IMAGE_MODEL = os.environ.get("AI_IMAGE_MODEL", "openai/gpt-image-1")
IMAGE_QUALITY = os.environ.get("AI_IMAGE_QUALITY", "low").lower()
if IMAGE_QUALITY not in {"low", "medium", "high"}:
    IMAGE_QUALITY = "low"
IMAGE_API_KEY = OPENAI_API_KEY
IMAGE_PROXY_BASE = None

PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
INHOUSE_SHIPPING = 12.0

# Emergent-managed Resend email (base URL is a hardcoded constant so it survives deploy)
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMERGENT_EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Frame Works Prints")

# Admin seeding + webhook auth (secrets come from env — never hard-coded)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# Prodigi Print API
PRODIGI_API_KEY = os.environ.get("PRODIGI_API_KEY", "").strip()
PRODIGI_BASE_URL = os.environ.get("PRODIGI_BASE_URL", "https://api.sandbox.prodigi.com").rstrip("/")
PRODIGI_MARKUP = float(os.environ.get("PRODIGI_MARKUP", "1.6"))
PRODIGI_DEFAULT_SHIPPING = os.environ.get("PRODIGI_DEFAULT_SHIPPING", "Budget")
PRODIGI_SUBMIT_ORDERS = os.environ.get("PRODIGI_SUBMIT_ORDERS", "false").strip().lower() in {"1", "true", "yes", "on"}
PRODIGI_WEBHOOK_SECRET = os.environ.get("PRODIGI_WEBHOOK_SECRET", "").strip()


# Sign in with Apple
APPLE_AUDIENCES = [a.strip() for a in os.environ.get("APPLE_AUDIENCES", "").split(",") if a.strip()]
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

# Server-authoritative pricing (must mirror frontend src/theme.ts computePrice)
MATERIAL_BASE = {"canvas": 49, "poster": 29, "metal": 89, "acrylic": 119}
SIZE_MULT = {"12x16": 1.0, "18x24": 1.5, "24x36": 2.1, "30x40": 2.8}
FRAME_COST = {"wood": 0, "black": 10, "white": 10, "none": 0}
PANEL_MULT_BY_COUNT = {1: 1.0, 3: 1.7, 4: 2.1}
FIRST_ORDER_DISCOUNT = 0.10
VALID_ORDER_STATUS = {"received", "in_production", "shipped", "delivered", "cancelled"}


def compute_base_price(material: str, size: str, frame: str, panels: int, is_framed: bool = True) -> float:
    n = max(1, panels or 1)
    base = MATERIAL_BASE.get(material, 49)
    smult = SIZE_MULT.get(size, 1.0)
    pmult = PANEL_MULT_BY_COUNT.get(n, 1.0)
    fcost = FRAME_COST.get(frame or "none", 0) if is_framed else 0
    return round(base * smult * pmult + fcost * n, 2)

def normalize_finish(material: str, finish: str) -> str:
    """Translate the legacy generic wood key to the official product finish."""
    if finish == "wood":
        return "brown" if material == "canvas" else "red_oak"
    return finish or "none"


from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------- Models ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    is_admin: bool = False


class AuthOut(BaseModel):
    token: str
    user: UserOut


class AppleSignInIn(BaseModel):
    identity_token: str
    name: Optional[str] = None
    email: Optional[str] = None


class RoomPreviewIn(BaseModel):
    image_base64: str
    room: str
    frame: str = "wood"
    material: str = "canvas"
    panels: int = 1


class ProjectIn(BaseModel):
    original: str
    current: str
    room: Optional[str] = None
    room_preview: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    frame: Optional[str] = None
    panels: Optional[int] = 1
    panel_key: Optional[str] = None
    price: Optional[float] = None
    store_variant_id: Optional[str] = None
    store_family_id: Optional[str] = None
    store_family_name: Optional[str] = None
    store_tier: Optional[str] = None
    store_image: Optional[str] = None
    has_mat: Optional[bool] = None
    prodigi_sku: Optional[str] = None
    prodigi_variant_name: Optional[str] = None
    prodigi_variant_image: Optional[str] = None


class Recipient(BaseModel):
    name: str
    address1: str
    city: str
    state_code: Optional[str] = None
    country_code: str = "US"
    zip: str


# ---------- Helpers ----------
import time as _time
from collections import defaultdict as _defaultdict
_RATE_HITS: dict = _defaultdict(list)
_RATE_LAST_PRUNE = 0.0
_RATE_MAX_KEYS = 10000


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_rate_hits(now: float):
    """Drop keys whose most recent hit is older than an hour so the map stays bounded."""
    global _RATE_LAST_PRUNE
    _RATE_LAST_PRUNE = now
    stale = [k for k, v in _RATE_HITS.items() if not v or now - v[-1] > 3600]
    for k in stale:
        _RATE_HITS.pop(k, None)


def rate_limit(key: str, max_calls: int, window: int):
    """Simple in-memory sliding-window limiter (per process). Raises 429 when exceeded."""
    now = _time.time()
    if len(_RATE_HITS) > _RATE_MAX_KEYS or now - _RATE_LAST_PRUNE > 300:
        _prune_rate_hits(now)
    hits = [t for t in _RATE_HITS[key] if now - t < window]
    hits.append(now)
    _RATE_HITS[key] = hits
    if len(hits) > max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def user_out(u: dict) -> UserOut:
    return UserOut(id=u["id"], email=u["email"], name=u.get("name"), is_admin=bool(u.get("is_admin")))


def _sync_image_edit(image_bytes: bytes, prompt: str) -> str:
    """Run a direct provider image edit in a worker thread."""
    tmp_path = None
    try:
        # Normalize to a valid PNG the image-edit API reliably accepts.
        im = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            im.save(tf, format="PNG")
            tmp_path = tf.name
        with open(tmp_path, "rb") as f:
            resp = litellm.image_edit(
                model=IMAGE_MODEL,
                image=f,
                prompt=prompt,
                api_key=IMAGE_API_KEY,
                api_base=IMAGE_PROXY_BASE,
                n=1,
                size="1024x1024",
                quality=IMAGE_QUALITY,
            )
        d = resp.data[0]
        b64 = getattr(d, "b64_json", None)
        if not b64:
            url = getattr(d, "url", None)
            if not url:
                raise RuntimeError("No image returned")
            import requests as _rq
            b64 = base64.b64encode(_rq.get(url).content).decode()
        return f"data:image/png;base64,{b64}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


async def gemini_edit(image_base64: str, prompt: str) -> str:
    if not IMAGE_API_KEY:
        raise HTTPException(status_code=500, detail="AI key not configured")
    raw = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    try:
        image_bytes = base64.b64decode(raw)
        return await asyncio.to_thread(_sync_image_edit, image_bytes, prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image edit failed: {e}")
        raise HTTPException(status_code=502, detail="AI processing failed, please try again")


async def get_cached_generation(cache_key: str) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    return await db.ai_cache.find_one({"_id": cache_key, "expires_at": {"$gt": now}})


async def cache_generation(cache_key: str, image_base64: str) -> None:
    now = datetime.now(timezone.utc)
    await db.ai_cache.update_one(
        {"_id": cache_key},
        {"$set": {
            "image_base64": image_base64,
            "created_at": now,
            "expires_at": now + timedelta(hours=AI_CACHE_TTL_HOURS),
        }},
        upsert=True,
    )


async def consume_cloud_generation(user_id: str) -> int:
    """Atomically reserve one daily cloud call and return today's remaining calls."""
    day = datetime.now(timezone.utc).date().isoformat()
    usage_id = f"{user_id}:{day}"
    usage = await db.ai_usage.find_one_and_update(
        {"_id": usage_id},
        {"$inc": {"count": 1}, "$setOnInsert": {"user_id": user_id, "day": day}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    count = int(usage.get("count", 1))
    if count > AI_DAILY_CLOUD_LIMIT:
        await db.ai_usage.update_one({"_id": usage_id, "count": {"$gt": 0}}, {"$inc": {"count": -1}})
        raise HTTPException(
            status_code=429,
            detail=f"Daily AI preview limit reached ({AI_DAILY_CLOUD_LIMIT}). Try again tomorrow.",
        )
    return AI_DAILY_CLOUD_LIMIT - count


# ---------- Auth ----------
@api_router.post("/auth/register", response_model=AuthOut)
async def register(data: RegisterIn, request: Request):
    rate_limit(f"reg:{client_ip(request)}", 5, 300)
    if await db.users.find_one({"email": data.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": data.email.lower(),
        "name": data.name or data.email.split("@")[0],
        "hashed_password": hash_password(data.password),
        "is_admin": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user)
    return AuthOut(token=create_token(user["id"]), user=user_out(user))


@api_router.post("/auth/login", response_model=AuthOut)
async def login(data: LoginIn, request: Request):
    rate_limit(f"login:{client_ip(request)}", 10, 300)
    user = await db.users.find_one({"email": data.email.lower()})
    if not user or not user.get("hashed_password") or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return AuthOut(token=create_token(user["id"]), user=user_out(user))


@api_router.get("/auth/me", response_model=UserOut)
async def me(user=Depends(get_current_user)):
    return user_out(user)


_apple_jwk_client = None


def _get_apple_jwk_client():
    global _apple_jwk_client
    if _apple_jwk_client is None:
        _apple_jwk_client = jwt.PyJWKClient(APPLE_JWKS_URL)
    return _apple_jwk_client


@api_router.post("/auth/apple", response_model=AuthOut)
async def apple_signin(data: AppleSignInIn, request: Request):
    """Verify an Apple identity token against Apple's JWKS, then upsert the user (keyed by the
    stable Apple 'sub') and return our own app JWT. Name/email only arrive on first sign-in."""
    rate_limit(f"apple:{client_ip(request)}", 10, 300)
    if not APPLE_AUDIENCES:
        raise HTTPException(status_code=500, detail="Apple Sign-In not configured")
    try:
        signing_key = await asyncio.to_thread(
            _get_apple_jwk_client().get_signing_key_from_jwt, data.identity_token)
        claims = jwt.decode(
            data.identity_token, signing_key.key, algorithms=["RS256"],
            audience=APPLE_AUDIENCES, issuer=APPLE_ISSUER,
        )
    except Exception as e:
        logger.error(f"Apple token verify failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Apple token")
    apple_sub = claims.get("sub")
    if not apple_sub:
        raise HTTPException(status_code=401, detail="Invalid Apple token")
    user = await db.users.find_one({"apple_sub": apple_sub})
    if not user:
        email = (data.email or claims.get("email") or f"{apple_sub}@privaterelay.appleid.com").lower()
        user = {
            "id": str(uuid.uuid4()),
            "apple_sub": apple_sub,
            "email": email,
            "name": data.name or email.split("@")[0],
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
    return AuthOut(token=create_token(user["id"]), user=user_out(user))


@api_router.delete("/auth/me")
async def delete_account(user=Depends(get_current_user)):
    await db.projects.delete_many({"user_id": user["id"]})
    await db.orders.delete_many({"user_id": user["id"]})
    await db.users.delete_one({"id": user["id"]})
    return {"ok": True}


# ---------- AI ----------
# Per-material frame descriptions for the room-preview prompt.
def frame_description(material: str, frame: str) -> str:
    if frame == "none":
        if material == "canvas":
            return "a frameless gallery-wrapped canvas, with the image continuing around the 1.25-inch wrapped edges"
        return "an unframed, flat printed poster with no border"
    if frame in {"wood", "brown", "red_oak", "oak", "oak_deep", "oak_float", "natural"}:
        return "a natural oak wood gallery frame with an ivory museum mat"
    if frame == "walnut":
        return "a deep walnut wood gallery frame with an ivory museum mat"
    if frame in {"black", "black_deep", "black_float"}:
        return "a matte black wood gallery frame with an ivory museum mat"
    if frame == "white":
        return "a clean white wood gallery frame with an ivory museum mat"
    return f"a {frame} gallery frame"


@api_router.post("/room-preview")
async def room_preview(data: RoomPreviewIn, user=Depends(get_current_user)):
    rate_limit(f"ai:{user['id']}", 20, 60)
    options = {
        "room": data.room,
        "frame": data.frame,
        "material": data.material,
        "panels": data.panels,
    }
    cache_key = generation_cache_key("room-preview", data.image_base64, options)
    if AI_DEMO_MODE:
        try:
            result, notices = await asyncio.to_thread(
                demo_room_preview,
                data.image_base64,
                data.room,
                data.frame,
                data.material,
                data.panels,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "image_base64": result,
            "mode": "demo",
            "cached": False,
            "remaining_today": AI_DAILY_CLOUD_LIMIT,
            "notices": notices,
        }

    cached = await get_cached_generation(cache_key)
    if cached:
        return {
            "image_base64": cached["image_base64"],
            "mode": "cloud",
            "cached": True,
            "remaining_today": None,
            "notices": ["Reused a cached preview; no new AI generation was billed."],
        }
    if not IMAGE_API_KEY:
        raise HTTPException(status_code=503, detail="Cloud AI is disabled because OPENAI_API_KEY is not configured.")
    remaining = await consume_cloud_generation(user["id"])
    room_names = {
        "living_room": "modern minimalist living room above a sofa",
        "bedroom": "serene bedroom above the bed headboard",
        "office": "stylish home office above the desk",
        "hallway": "elegant entryway hallway wall",
    }
    where = room_names.get(data.room, "modern living room wall")
    frame_desc = frame_description(data.material, data.frame)
    if data.panels and data.panels > 1:
        piece = (f"as a {data.panels}-panel split-canvas set ({data.panels} equal {data.material} panels, "
                 f"each with {frame_desc}, arranged side by side with small even gaps)")
    else:
        piece = f"as a single {data.material} wall art piece with {frame_desc}"
    prompt = (
        f"Take this artwork and present it {piece}, hanging on the wall of a {where}. "
        "Photorealistic interior scene, correct scale and perspective, "
        "soft natural lighting, premium home-decor magazine styling, warm neutral tones."
    )
    result = await gemini_edit(data.image_base64, prompt)
    await cache_generation(cache_key, result)
    return {
        "image_base64": result,
        "mode": "cloud",
        "cached": False,
        "remaining_today": remaining,
        "notices": [f"Cloud preview generated at {IMAGE_QUALITY} quality."],
    }


# ---------- Projects ----------
@api_router.post("/projects")
async def save_project(data: ProjectIn, user=Depends(get_current_user)):
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "created_at": datetime.now(timezone.utc).isoformat(), **data.model_dump()}
    await db.projects.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/projects")
async def list_projects(user=Depends(get_current_user)):
    docs = await db.projects.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return docs


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    res = await db.projects.delete_one({"id": project_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}



class QuoteIn(BaseModel):
    material: str
    size: str
    panels: int = 1
    frame: Optional[str] = "none"
    store_variant_id: Optional[str] = None
    # Gallery store retail when Prodigi is not configured or unavailable.
    fallback_price: Optional[float] = None
    recipient: Recipient


async def compute_quote(
    user_id: str,
    material: str,
    size: str,
    frame: str,
    panels: int,
    recipient: dict,
    store_variant_id: Optional[str] = None,
    fallback_price: Optional[float] = None,
) -> dict:
    """Server-authoritative price using the selected Prodigi product when available."""
    frame = frame or "none"
    n = max(1, panels or 1)
    prior = await db.orders.count_documents({"user_id": user_id, "material": {"$exists": True}})
    first_order = prior == 0
    disc_pct = FIRST_ORDER_DISCOUNT if first_order else 0.0

    def finalize_gallery(retail, product, shipping, source="gallery", currency="USD", **extra):
        retail = round(float(retail), 2)
        discount_amount = round(retail * disc_pct, 2)
        out = {
            "retail": round(retail - discount_amount, 2),
            "retail_before_discount": retail,
            "first_order": first_order,
            "discount_pct": disc_pct,
            "discount_amount": discount_amount,
            "product": round(float(product), 2),
            "shipping": round(float(shipping), 2),
            "base_cost": None,
            "source": source,
            "currency": currency,
            "store_variant_id": store_variant_id,
            "finish_label": frame,
        }
        out.update(extra)
        return out

    if not store_variant_id:
        raise HTTPException(status_code=422, detail="Choose a frame in the Store before checkout.")
    mapping = resolve_prodigi(store_variant_id, size_key=size)
    if not mapping:
        raise HTTPException(status_code=422, detail="This frame is not mapped to a Prodigi product yet.")
    if fallback_price is None or float(fallback_price) <= 0:
        raise HTTPException(status_code=422, detail="Choose a frame in the Store before checkout.")

    if not prodigi_client.configured():
        product = round(float(fallback_price), 2)
        return finalize_gallery(product + INHOUSE_SHIPPING, product, INHOUSE_SHIPPING, source="gallery_fallback", prodigi_sku=mapping["sku"], prodigi_attributes=mapping["attributes"])

    try:
        raw = await prodigi_client.create_quote(
            sku=mapping["sku"],
            copies=n,
            attributes=mapping["attributes"] or None,
            destination_country_code=(recipient.get("country_code") or "US").upper(),
        )
        totals = prodigi_client.parse_quote_totals(raw)
        product = round(totals["product"] * prodigi_client.PRODIGI_MARKUP, 2)
        shipping = round(totals["shipping"] * prodigi_client.PRODIGI_MARKUP, 2)
        if product <= 0:
            raise ValueError("Prodigi returned no product cost")
        retail = round(product + shipping, 2)
        discount_amount = round(retail * disc_pct, 2)
        return {
            "retail": round(retail - discount_amount, 2),
            "retail_before_discount": retail,
            "first_order": first_order,
            "discount_pct": disc_pct,
            "discount_amount": discount_amount,
            "product": product,
            "shipping": shipping,
            "base_cost": totals.get("total"),
            "source": "prodigi",
            "currency": totals.get("currency") or "USD",
            "prodigi_sku": mapping["sku"],
            "prodigi_attributes": mapping["attributes"],
            "finish_label": frame,
        }
    except Exception as e:
        logger.error("Prodigi quote failed: %s", e)
        product = round(float(fallback_price), 2)
        return finalize_gallery(product + INHOUSE_SHIPPING, product, INHOUSE_SHIPPING, source="gallery_fallback", prodigi_sku=mapping["sku"], prodigi_attributes=mapping["attributes"])


@api_router.post("/quote")
async def quote(data: QuoteIn, user=Depends(get_current_user)):
    return await compute_quote(
        user["id"], data.material, data.size, data.frame or "none",
        data.panels, data.recipient.model_dump(),
        store_variant_id=data.store_variant_id, fallback_price=data.fallback_price,
    )




# ---------- Prodigi fulfillment ----------
@api_router.get("/prodigi/status")
async def prodigi_status():
    """Whether Prodigi is configured (never returns the API key). Public for setup checks."""
    return {
        "configured": prodigi_client.configured(),
        "base_url": prodigi_client.PRODIGI_BASE_URL,
        "submit_orders": prodigi_client.PRODIGI_SUBMIT_ORDERS,
        "default_shipping": prodigi_client.PRODIGI_DEFAULT_SHIPPING,
        "markup": prodigi_client.PRODIGI_MARKUP,
        "public_base_url_set": bool(PUBLIC_BASE_URL and PUBLIC_BASE_URL.startswith("http")),
        "public_base_url_https": bool(PUBLIC_BASE_URL and PUBLIC_BASE_URL.startswith("https://")),
        "webhook_secret_set": bool(PRODIGI_WEBHOOK_SECRET),
        "ready_to_quote": prodigi_client.configured(),
        "ready_to_submit_orders": bool(
            prodigi_client.configured()
            and prodigi_client.PRODIGI_SUBMIT_ORDERS
            and PUBLIC_BASE_URL
            and PUBLIC_BASE_URL.startswith("https://")
            and PRODIGI_WEBHOOK_SECRET
        ),
        "hint": (
            None
            if prodigi_client.configured()
            else "Set PRODIGI_API_KEY in backend/.env (sandbox key from https://www.prodigi.com/), then restart the API."
        ),
    }


@api_router.get("/catalog/store")
async def store_catalog():
    """Full curated Frame Works gallery catalog (Essential / Gallery / Atelier).

    This is the source of truth for the Store UI.
    Includes families, sizes, variants, prices, and Prodigi mapping hints.
    Public so the Store can load before/without blocking on edge auth issues.
    """
    from prodigi_catalog import FAMILY_FULFILLMENT, resolve_prodigi

    catalog_path = ROOT_DIR / "catalog" / "store_catalog.json"
    if not catalog_path.exists():
        raise HTTPException(status_code=503, detail="Store catalog is not available on the server.")
    try:
        payload = json.loads(catalog_path.read_text())
    except Exception as exc:
        logger.error("Failed to read store catalog: %s", exc)
        raise HTTPException(status_code=503, detail="Store catalog could not be loaded.") from exc

    # Attach Prodigi fulfillment hints per family (no secrets)
    fulfillment_by_family = {}
    for fid, spec in FAMILY_FULFILLMENT.items():
        fulfillment_by_family[fid] = {
            "kind": spec.get("kind"),
            "sku_template": spec.get("sku_template"),
            "attributes": spec.get("attributes") or {},
        }

    # Annotate variants with Prodigi SKUs and live product details when configured.
    variants = []
    prodigi_skus: set[str] = set()
    for v in payload.get("variants") or []:
        mapped = resolve_prodigi(v.get("id"), size_key=v.get("size_key") or "", family_id=v.get("family_id") or "")
        item = dict(v)
        if mapped:
            item["prodigi_sku"] = mapped.get("sku")
            item["prodigi_attributes"] = mapped.get("attributes") or {}
            prodigi_skus.add(mapped["sku"])
        variants.append(item)

    prodigi_products: dict[str, dict] = {}
    if prodigi_client.configured():
        results = await asyncio.gather(
            *(prodigi_client.get_product(sku) for sku in sorted(prodigi_skus)),
            return_exceptions=True,
        )
        for sku, result in zip(sorted(prodigi_skus), results):
            if isinstance(result, dict):
                prodigi_products[sku] = result.get("product") or result
        for item in variants:
            product = prodigi_products.get(item.get("prodigi_sku"))
            if product:
                item["prodigi_product"] = product

    return {
        "version": payload.get("version", 1),
        "source": payload.get("source", "frame_works_gallery"),
        "fulfillment": "prodigi" if prodigi_client.configured() else "gallery_manual",
        "prodigi_configured": prodigi_client.configured(),
        "tier_meta": payload.get("tier_meta") or {},
        "sizes": payload.get("sizes") or [],
        "families": payload.get("families") or [],
        "variants": variants,
        "variant_count": len(variants),
        "family_count": len(payload.get("families") or []),
        "fulfillment_by_family": fulfillment_by_family,
        "prodigi_products": prodigi_products,
        "note": "Curated store catalog enriched with live Prodigi product details when configured.",
    }


@api_router.post("/prodigi/quote")
async def prodigi_quote_endpoint(data: QuoteIn, user=Depends(get_current_user)):
    """Live Prodigi cost for a store_variant_id (falls back to gallery price)."""
    mapping = resolve_prodigi(data.store_variant_id, size_key=data.size or "")
    if not mapping:
        raise HTTPException(status_code=422, detail="No Prodigi mapping for this store frame yet.")
    if not prodigi_client.configured():
        # offline / no key — return gallery fallback
        product = float(data.fallback_price or 0)
        if product <= 0:
            raise HTTPException(status_code=503, detail="Prodigi is not configured and no fallback price was provided.")
        shipping = INHOUSE_SHIPPING
        retail = round((product + shipping), 2)
        return {
            "source": "gallery_fallback",
            "prodigi_sku": mapping["sku"],
            "attributes": mapping["attributes"],
            "product": product,
            "shipping": shipping,
            "retail": retail,
            "currency": "USD",
        }
    try:
        raw = await prodigi_client.create_quote(
            sku=mapping["sku"],
            copies=max(1, data.panels or 1),
            attributes=mapping["attributes"] or None,
            destination_country_code=(data.recipient.country_code if data.recipient else "US") or "US",
        )
        totals = prodigi_client.parse_quote_totals(raw)
        product = round(totals["product"] * prodigi_client.PRODIGI_MARKUP, 2)
        shipping = round(totals["shipping"] * prodigi_client.PRODIGI_MARKUP, 2)
        if product <= 0 and data.fallback_price:
            product = float(data.fallback_price)
            shipping = INHOUSE_SHIPPING
        return {
            "source": "prodigi",
            "prodigi_sku": mapping["sku"],
            "attributes": mapping["attributes"],
            "product": product,
            "shipping": shipping,
            "retail": round(product + shipping, 2),
            "currency": totals.get("currency") or "USD",
            "base_cost": totals.get("total"),
        }
    except Exception as e:
        logger.error("prodigi quote failed: %s", e)
        if data.fallback_price:
            product = float(data.fallback_price)
            return {
                "source": "gallery_fallback",
                "prodigi_sku": mapping["sku"],
                "attributes": mapping["attributes"],
                "product": product,
                "shipping": INHOUSE_SHIPPING,
                "retail": round(product + INHOUSE_SHIPPING, 2),
                "currency": "USD",
                "error": str(e)[:200],
            }
        raise HTTPException(status_code=502, detail="Prodigi quote unavailable")


@api_router.post("/webhooks/prodigi")
async def prodigi_webhook(request: Request, token: str = ""):
    """Prodigi order status callback, protected by a deployment-owned token."""
    if not PRODIGI_WEBHOOK_SECRET or not hmac.compare_digest(token, PRODIGI_WEBHOOK_SECRET):
        logger.warning("Rejected Prodigi webhook (secret unset or token invalid)")
        return {"ok": True}
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    data = payload.get("data") or payload
    order_obj = (data.get("order") if isinstance(data, dict) else None) or data
    prodigi_id = None
    if isinstance(order_obj, dict):
        prodigi_id = order_obj.get("id")
    merchant_ref = None
    if isinstance(order_obj, dict):
        merchant_ref = order_obj.get("merchantReference")
    stage = None
    if isinstance(order_obj, dict):
        stage = (order_obj.get("status") or {}).get("stage")

    # Prefer authenticated GET when configured
    if prodigi_id and prodigi_client.configured():
        try:
            fresh = await prodigi_client.get_order(prodigi_id)
            fo = fresh.get("order") or fresh
            stage = (fo.get("status") or {}).get("stage") or stage
            merchant_ref = fo.get("merchantReference") or merchant_ref
            shipments = fo.get("shipments") or []
            tracking_url = ""
            if shipments:
                tracking_url = (shipments[0] or {}).get("trackingUrl") or (shipments[0] or {}).get("tracking_url") or ""
        except Exception as e:
            logger.error("prodigi webhook re-fetch failed: %s", e)
            tracking_url = ""
    else:
        tracking_url = ""

    status_map = {
        "InProgress": "in_production",
        "Complete": "shipped",
        "Cancelled": "cancelled",
    }
    local_status = status_map.get(stage or "", None)

    q = {}
    if merchant_ref:
        q["id"] = merchant_ref
    if prodigi_id:
        q = {"$or": [{"id": merchant_ref} if merchant_ref else {"_id": None}, {"prodigi_order_id": prodigi_id}]}
        # clean null
        q["$or"] = [x for x in q["$or"] if x and list(x.values())[0]]

    if q:
        update = {"prodigi_stage": stage, "prodigi_order_id": prodigi_id}
        if local_status:
            update["status"] = local_status
        if tracking_url:
            update["tracking_url"] = tracking_url
        await db.orders.update_one(q if "$or" not in q else q, {"$set": update})
        if merchant_ref:
            await db.orders.update_one({"id": merchant_ref}, {"$set": update})

    return {"received": True, "stage": stage}


async def submit_prodigi_order(order_id: str, project_id: str, cart: dict, user: dict) -> tuple[str, str, Optional[str]]:
    """Submit to Prodigi when enabled. Returns (status, prodigi_status, prodigi_order_id)."""
    if not prodigi_client.configured():
        return "received", "prodigi_not_configured", None
    if not prodigi_client.PRODIGI_SUBMIT_ORDERS:
        return "received", "prodigi_submit_disabled", None
    if not PUBLIC_BASE_URL:
        logger.error("PUBLIC_BASE_URL required for Prodigi asset download")
        return "received", "prodigi_missing_public_url", None

    store_variant_id = cart.get("store_variant_id")
    mapping = resolve_prodigi(store_variant_id, size_key=cart.get("size") or "", family_id=cart.get("store_family_id") or "")
    if not mapping:
        return "received", "prodigi_unmapped_sku", None

    asset_url = f"{PUBLIC_BASE_URL}/api/public/project/{project_id}"
    recipient = prodigi_client.recipient_from_app(cart.get("recipient") or {}, email=user.get("email") or "")
    callback = None
    if PUBLIC_BASE_URL.startswith("https") and PRODIGI_WEBHOOK_SECRET:
        callback = f"{PUBLIC_BASE_URL}/api/webhooks/prodigi?token={PRODIGI_WEBHOOK_SECRET}"
    try:
        result = await prodigi_client.create_order(
            merchant_reference=order_id,
            recipient=recipient,
            sku=mapping["sku"],
            asset_url=asset_url,
            copies=max(1, int(cart.get("panels") or 1)),
            attributes=mapping["attributes"] or None,
            callback_url=callback,
            idempotency_key=order_id,
        )
        order_obj = result.get("order") or result
        pid = order_obj.get("id")
        stage = (order_obj.get("status") or {}).get("stage") or "InProgress"
        return "in_production", f"prodigi:{stage}", pid
    except Exception as e:
        logger.error("Prodigi create_order failed: %s", e)
        return "received", "prodigi_submit_failed", None


# ---------- Public project image (unauthenticated so Prodigi can fetch it) ----------
@api_router.get("/public/project/{project_id}")
async def public_project_image(project_id: str, panel: int = 0, of: int = 1):
    doc = await db.projects.find_one({"id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    data_uri = doc.get("current") or doc.get("original")
    raw = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
    img_bytes = base64.b64decode(raw)
    if of and of > 1:
        try:
            im = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = im.size
            slice_w = w // of
            left = panel * slice_w
            right = w if panel == of - 1 else left + slice_w
            im = im.crop((left, 0, right, h))
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=92)
            img_bytes = out.getvalue()
            return Response(content=img_bytes, media_type="image/jpeg")
        except Exception as e:
            logger.error(f"panel slice failed: {e}")
    mime = "image/png" if data_uri.startswith("data:image/png") else "image/jpeg"
    return Response(content=img_bytes, media_type=mime)


# ---------- Orders ----------
async def _post_email(to_email: str, subject: str, html: str):
    """Low-level send via Emergent-managed Resend. Never raises."""
    if not (EMERGENT_EMAIL_KEY and to_email):
        return
    payload = {"to": [to_email], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                headers={"X-Email-Key": EMERGENT_EMAIL_KEY}, json=payload)
        if resp.status_code >= 400:
            logger.error(f"Email failed {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Email error: {e}")


STATUS_COPY = {
    "received": ("Order received", "We've received your order and it's queued for production."),
    "in_production": ("Your art is in production", "Great news — your piece is now being printed and framed."),
    "shipped": ("Your order has shipped", "Your wall art is on its way! It should arrive soon."),
    "delivered": ("Delivered", "Your order has been delivered. We hope you love it!"),
    "cancelled": ("Order cancelled", "Your order has been cancelled. Reach out if this was a mistake."),
}


async def send_status_email(to_email: str, order: dict, status: str, tracking_url: str = ""):
    """Notify the buyer when their order status changes."""
    title, msg = STATUS_COPY.get(status, ("Order update", f"Your order status is now: {status}."))
    oid = str(order.get("id", ""))[:8].upper()
    safe_track = html_lib.escape(tracking_url, quote=True)
    track = (f'<p style="margin:16px 0 0;"><a href="{safe_track}" '
             f'style="color:#a07d4f;font-weight:bold;">Track your package →</a></p>') if tracking_url else ""
    html = f"""
    <div style="background:#f5f1ea;padding:32px 0;font-family:Georgia,'Times New Roman',serif;color:#1c1b1a;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto;background:#fffdf9;border:1px solid #e6ddd0;border-radius:14px;">
        <tr><td style="padding:32px;">
          <div style="font-size:12px;letter-spacing:3px;color:#a07d4f;font-family:Arial,sans-serif;font-weight:bold;">FRAME WORKS PRINTS</div>
          <h1 style="font-size:24px;margin:12px 0 6px;">{title}</h1>
          <p style="font-family:Arial,sans-serif;font-size:14px;color:#6b6459;line-height:1.6;margin:0;">Order <b>#{oid}</b> — {msg}{track}</p>
          <p style="font-family:Arial,sans-serif;font-size:13px;color:#6b6459;margin:20px 0 0;">Follow along in the app under the Orders tab.</p>
        </td></tr>
      </table>
    </div>
    """
    await _post_email(to_email, f"{title} · #{oid} — Frame Works Prints", html)


async def send_order_email(to_email: str, order: dict):
    """Send a branded order-confirmation receipt via Emergent-managed Resend.
    Never raises — a failed email must not break order creation."""
    if not (EMERGENT_EMAIL_KEY and to_email):
        return
    material = (order.get("material") or "").replace("_", " ").title()
    size = order.get("size") or ""
    frame = (order.get("frame") or "").replace("_", " ").title()
    panels = order.get("panels") or 1
    price = float(order.get("price") or 0)
    oid = str(order.get("id", ""))[:8].upper()
    rcp = order.get("recipient") or {}
    ship = "<br>".join([p for p in [
        rcp.get("name", ""), rcp.get("address1", ""),
        f"{rcp.get('city','')}, {rcp.get('state_code','') or ''} {rcp.get('zip','')}".strip(),
        rcp.get("country_code", "US"),
    ] if p and p.strip(", ")])
    panel_line = f"{panels}-panel set · " if panels and panels > 1 else ""
    html = f"""
    <div style="background:#f5f1ea;padding:32px 0;font-family:Georgia,'Times New Roman',serif;color:#1c1b1a;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fffdf9;border:1px solid #e6ddd0;border-radius:14px;overflow:hidden;">
        <tr><td style="padding:28px 32px 8px;">
          <div style="font-size:12px;letter-spacing:3px;color:#a07d4f;font-family:Arial,sans-serif;font-weight:bold;">FRAME WORKS PRINTS</div>
          <h1 style="font-size:26px;margin:12px 0 4px;color:#1c1b1a;">Your order is confirmed</h1>
          <p style="font-family:Arial,sans-serif;font-size:14px;color:#6b6459;margin:0;">Thank you — we've received your payment and your piece is heading into production.</p>
        </td></tr>
        <tr><td style="padding:20px 32px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;font-size:14px;color:#1c1b1a;border:1px solid #e6ddd0;border-radius:10px;">
            <tr><td style="padding:14px 16px;color:#6b6459;">Order</td><td style="padding:14px 16px;text-align:right;font-weight:bold;">#{oid}</td></tr>
            <tr><td style="padding:14px 16px;color:#6b6459;border-top:1px solid #f0e9de;">Artwork</td><td style="padding:14px 16px;text-align:right;border-top:1px solid #f0e9de;">{panel_line}{material} · {size}</td></tr>
            <tr><td style="padding:14px 16px;color:#6b6459;border-top:1px solid #f0e9de;">Frame</td><td style="padding:14px 16px;text-align:right;border-top:1px solid #f0e9de;">{frame}</td></tr>
            <tr><td style="padding:14px 16px;color:#6b6459;border-top:1px solid #f0e9de;font-size:16px;">Total paid</td><td style="padding:14px 16px;text-align:right;border-top:1px solid #f0e9de;font-size:16px;font-weight:bold;">${price:.2f}</td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 32px 8px;">
          <div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:1px;color:#a07d4f;font-weight:bold;text-transform:uppercase;">Shipping to</div>
          <p style="font-family:Arial,sans-serif;font-size:14px;color:#1c1b1a;line-height:1.5;margin:8px 0 0;">{ship}</p>
        </td></tr>
        <tr><td style="padding:24px 32px 32px;">
          <p style="font-family:Arial,sans-serif;font-size:13px;color:#6b6459;line-height:1.6;margin:0;">You can track your order status any time in the app under the Orders tab. We'll keep you posted as it moves to production and ships.</p>
        </td></tr>
      </table>
      <p style="text-align:center;font-family:Arial,sans-serif;font-size:12px;color:#a89f92;margin-top:20px;">Frame Works Prints · Premium wall art from your photos</p>
    </div>
    """
    await _post_email(to_email, f"Order confirmed · #{oid} — Frame Works Prints", html)


async def create_order_internal(user: dict, cart: dict, price: float, stripe_payment_intent_id: str) -> dict:
    """Create the fulfilled order. Called ONLY after a verified Stripe payment — never
    directly by the client, so orders cannot be placed without payment."""
    project = await db.projects.find_one({"id": cart.get("project_id"), "user_id": user["id"]}) or {}
    order_id = str(uuid.uuid4())
    store_variant_id = cart.get("store_variant_id") or project.get("store_variant_id")

    status = "received"
    prodigi_status = "prodigi_not_configured"
    prodigi_order_id = None
    finish_label = cart.get("frame") or project.get("frame") or "none"

    status, prodigi_status, prodigi_order_id = await submit_prodigi_order(
        order_id, cart.get("project_id") or "", cart, user
    )

    frame_name = (
        project.get("store_family_name") or cart.get("store_family_name") or "Gallery frame"
    )
    frame_image = (
        project.get("store_image") or cart.get("store_image")
    )

    doc = {
        "id": order_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "status": status,
        "prodigi_status": prodigi_status,
        "prodigi_order_id": prodigi_order_id,
        "prodigi_sku": (resolve_prodigi(store_variant_id, size_key=cart.get("size") or "") or {}).get("sku"),
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "project_id": cart.get("project_id"),
        "image_base64": project.get("current"),
        "room_preview": project.get("room_preview"),
        "material": cart.get("material") or project.get("material"),
        "size": cart.get("size") or project.get("size"),
        "frame": cart.get("frame") or project.get("frame") or "none",
        "prodigi_variant_name": frame_name,
        "prodigi_variant_image": frame_image,
        "store_variant_id": store_variant_id,
        "store_family_name": project.get("store_family_name") or cart.get("store_family_name"),
        "store_tier": project.get("store_tier"),
        "price_source": cart.get("price_source") or "prodigi",
        "prodigi_finish_label": finish_label,
        "panel_key": cart.get("panel_key") or project.get("panel_key"),
        "panels": cart.get("panels") or 1,
        "price": round(price, 2),
        "recipient": cart["recipient"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.orders.insert_one(doc)
    doc.pop("_id", None)
    await send_order_email(user["email"], doc)
    return doc


@api_router.get("/orders")
async def list_orders(user=Depends(get_current_user)):
    docs = await db.orders.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return docs


@api_router.get("/orders/{order_id}/tracking")
async def track_order(order_id: str, user=Depends(get_current_user)):
    """Fetch the owned order from Prodigi's GET /v4.0/Orders/{id} endpoint."""
    local = await db.orders.find_one({"id": order_id, "user_id": user["id"]}, {"_id": 0})
    if not local:
        raise HTTPException(status_code=404, detail="Order not found")
    prodigi_id = str(local.get("prodigi_order_id") or "")
    if not prodigi_id:
        raise HTTPException(status_code=409, detail="This order has not been submitted to Prodigi")
    if not prodigi_client.configured():
        raise HTTPException(status_code=503, detail="Prodigi tracking is not configured")
    try:
        response = await prodigi_client.get_order(prodigi_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Prodigi order not found") from exc
        raise HTTPException(status_code=502, detail="Prodigi tracking unavailable") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Prodigi tracking unavailable") from exc

    remote = response.get("order") or response
    stage = (remote.get("status") or {}).get("stage")
    shipments = remote.get("shipments") or []
    tracking = []
    for shipment in shipments:
        shipment_tracking = shipment.get("tracking") or {}
        tracking.append({
            "id": shipment.get("id"),
            "status": shipment.get("status"),
            "carrier": shipment.get("carrier"),
            "url": shipment_tracking.get("url") or shipment.get("trackingUrl") or "",
            "number": shipment_tracking.get("number") or "",
        })
    status_map = {"InProgress": "in_production", "Complete": "shipped", "Cancelled": "cancelled"}
    update = {"prodigi_stage": stage, "prodigi_last_checked_at": datetime.now(timezone.utc).isoformat()}
    if tracking and tracking[0].get("url"):
        update["tracking_url"] = tracking[0]["url"]
    if stage in status_map:
        update["status"] = status_map[stage]
    await db.orders.update_one({"id": order_id}, {"$set": update})
    return {
        "local_order_id": order_id,
        "prodigi_order_id": prodigi_id,
        "stage": stage,
        "status": status_map.get(stage, local.get("status")),
        "shipments": tracking,
    }


# ---------- Admin ----------
@api_router.get("/admin/stats")
async def admin_stats(user=Depends(require_admin)):
    q = {"material": {"$exists": True}}
    orders = await db.orders.find(q).to_list(1000)
    revenue = sum(o.get("price", 0) for o in orders)
    # Orders that took payment but have no automated fulfillment path need manual handling.
    unfulfilled_statuses = {"prodigi_not_configured", "prodigi_submit_disabled", "prodigi_unmapped_sku", "prodigi_submit_failed"}
    unfulfilled = sum(1 for o in orders if o.get("prodigi_status") in unfulfilled_statuses)
    return {
        "total_orders": len(orders),
        "revenue": round(revenue, 2),
        "total_users": await db.users.count_documents({}),
        "total_projects": await db.projects.count_documents({}),
        "unfulfilled_orders": unfulfilled,
    }


@api_router.get("/admin/orders")
async def admin_orders(user=Depends(require_admin)):
    docs = await db.orders.find({"material": {"$exists": True}}).sort("created_at", -1).to_list(300)
    for d in docs:
        d.pop("_id", None)
    return docs


class OrderStatusIn(BaseModel):
    status: str


@api_router.patch("/admin/orders/{order_id}")
async def admin_update_order(order_id: str, data: OrderStatusIn, user=Depends(require_admin)):
    if data.status not in VALID_ORDER_STATUS:
        raise HTTPException(status_code=400, detail="Invalid status")
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Not found")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": data.status}})
    if order.get("user_email"):
        await send_status_email(order["user_email"], order, data.status, order.get("tracking_url", ""))
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"message": "FrameWorks API"}


# ---------- Stripe payments ----------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_BASE = "https://api.stripe.com/v1"


class PaymentCreateIn(BaseModel):
    project_id: str
    material: str
    size: str
    frame: str = "none"
    store_variant_id: Optional[str] = None
    fallback_price: Optional[float] = None
    panel_key: Optional[str] = None
    panels: int = 1
    recipient: Recipient


async def stripe_request(method: str, path: str, *, data=None, idempotency_key: str = "") -> dict:
    """Call Stripe without logging credentials or client secrets."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    headers = {"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, f"{STRIPE_API_BASE}{path}", headers=headers, data=data)
    if response.status_code >= 400:
        try:
            stripe_message = response.json().get("error", {}).get("message", "")
        except ValueError:
            stripe_message = ""
        logger.error("Stripe API error %s on %s", response.status_code, path)
        raise HTTPException(status_code=502, detail=stripe_message or "Stripe payment service unavailable")
    return response.json()


@api_router.post("/payments/create-intent")
async def create_payment(data: PaymentCreateIn, user=Depends(get_current_user)):
    # Verify the project belongs to the caller; compute the price SERVER-SIDE (ignore any client amount).
    project = await db.projects.find_one({"id": data.project_id, "user_id": user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    store_variant_id = data.store_variant_id or project.get("store_variant_id")
    fallback_price = data.fallback_price if data.fallback_price is not None else project.get("price")
    q = await compute_quote(
        user["id"], data.material, data.size, data.frame, data.panels,
        data.recipient.model_dump(),
        store_variant_id=store_variant_id, fallback_price=fallback_price,
    )
    amount = q["retail"]
    currency = q.get("currency", "USD")
    payment_id = str(uuid.uuid4())
    body = await stripe_request("POST", "/payment_intents", data={
        "amount": str(int(round(amount * 100))),
        "currency": currency.lower(),
        "automatic_payment_methods[enabled]": "true",
        "receipt_email": user["email"],
        "description": "Frame Works Prints order",
        "metadata[internal_payment_id]": payment_id,
        "metadata[user_id]": user["id"],
        "metadata[project_id]": data.project_id,
    }, idempotency_key=f"create-payment-{payment_id}")
    # Bind the Stripe intent to the caller + exact server-computed amount and cart.
    await db.payments.insert_one({
        "id": payment_id, "stripe_payment_intent_id": body["id"],
        "user_id": user["id"], "project_id": data.project_id,
        "amount": amount, "currency": currency, "status": "created",
        "material": data.material, "size": data.size, "frame": data.frame,
        "prodigi_sku": q.get("prodigi_sku") or (resolve_prodigi(store_variant_id, size_key=data.size) or {}).get("sku"),
        "prodigi_variant_name": project.get("store_family_name"),
        "prodigi_variant_image": project.get("store_image"),
        "store_variant_id": store_variant_id,
        "store_family_name": project.get("store_family_name"),
        "price_source": q.get("source"),
        "panel_key": data.panel_key, "panels": data.panels,
        "recipient": data.recipient.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"payment_intent_id": body["id"], "client_secret": body["client_secret"], "amount": amount, "quote": q}


async def fulfill_stripe_payment(payment_intent_id: str, expected_user_id: Optional[str] = None) -> dict:
    query = {"stripe_payment_intent_id": payment_intent_id}
    if expected_user_id:
        query["user_id"] = expected_user_id
    pending = await db.payments.find_one(query)
    if not pending:
        raise HTTPException(status_code=404, detail="Payment not found")
    # Recover from a process interruption after the order insert but before the payment record
    # was marked captured. The provider intent remains the durable idempotency key.
    existing_order = await db.orders.find_one({"stripe_payment_intent_id": payment_intent_id}, {"_id": 0})
    if existing_order:
        await db.payments.update_one(
            {"stripe_payment_intent_id": payment_intent_id},
            {"$set": {"status": "captured", "order_id": existing_order["id"]}},
        )
        return existing_order
    # Idempotency: already fulfilled -> return the existing order.
    if pending.get("status") == "captured" and pending.get("order_id"):
        existing = await db.orders.find_one({"id": pending["order_id"]}, {"_id": 0})
        if existing:
            return existing
    body = await stripe_request("GET", f"/payment_intents/{payment_intent_id}")
    paid_cents = body.get("amount_received")
    expected_cents = int(round(float(pending["amount"]) * 100))
    currency = str(body.get("currency", "")).upper()
    if body.get("status") != "succeeded" or paid_cents != expected_cents or currency != pending.get("currency", "USD"):
        logger.error("Stripe payment verification mismatch for %s", payment_intent_id)
        raise HTTPException(status_code=402, detail="Payment verification failed")
    # Atomically claim the pending record so an intent fulfils at most one order.
    claim = await db.payments.update_one(
        {"stripe_payment_intent_id": payment_intent_id, "status": "created"},
        {"$set": {"status": "capturing"}})
    if claim.modified_count == 0:
        again = await db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
        if again and again.get("order_id"):
            existing = await db.orders.find_one({"id": again["order_id"]}, {"_id": 0})
            if existing:
                return existing
        existing = await db.orders.find_one({"stripe_payment_intent_id": payment_intent_id}, {"_id": 0})
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Payment already being processed")
    user = await db.users.find_one({"id": pending["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Payment user not found")
    order = await create_order_internal(user, pending, float(pending["amount"]), payment_intent_id)
    await db.payments.update_one({"stripe_payment_intent_id": payment_intent_id},
                                 {"$set": {"status": "captured", "order_id": order["id"]}})
    return order


@api_router.post("/payments/complete/{payment_intent_id}")
async def complete_payment(payment_intent_id: str, user=Depends(get_current_user)):
    return await fulfill_stripe_payment(payment_intent_id, user["id"])


def verify_stripe_signature(payload: bytes, signature_header: str, tolerance_seconds: int = 300) -> bool:
    """Verify Stripe's v1 webhook HMAC and reject stale deliveries."""
    parts = [part.split("=", 1) for part in signature_header.split(",") if "=" in part]
    timestamp = next((value for key, value in parts if key == "t"), "")
    signatures = [value for key, value in parts if key == "v1"]
    try:
        if abs(int(datetime.now(timezone.utc).timestamp()) - int(timestamp)) > tolerance_seconds:
            return False
    except ValueError:
        return False
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    if not STRIPE_WEBHOOK_SECRET or not verify_stripe_signature(payload, request.headers.get("stripe-signature", "")):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    if event.get("type") == "payment_intent.succeeded":
        payment_intent_id = (event.get("data", {}).get("object", {}) or {}).get("id")
        if payment_intent_id:
            try:
                await fulfill_stripe_payment(payment_intent_id)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
    return {"received": True}


@app.on_event("startup")
async def seed_admin():
    """Seed an admin ONLY from env vars, idempotently. Never hard-code a password and never
    reset an existing admin's password on restart."""
    if not (ADMIN_EMAIL and ADMIN_PASSWORD):
        return
    email = ADMIN_EMAIL.lower()
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": email,
            "name": "FrameWorks Admin",
            "hashed_password": hash_password(ADMIN_PASSWORD),
            "is_admin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Seeded admin user from env")
    elif not existing.get("is_admin"):
        await db.users.update_one({"email": email}, {"$set": {"is_admin": True}})


@app.on_event("startup")
async def create_ai_indexes():
    """Expire cached preview images automatically and keep daily counters unique."""
    await db.ai_cache.create_index("expires_at", expireAfterSeconds=0)
    await db.ai_usage.create_index([("user_id", 1), ("day", 1)], unique=True)


app.include_router(api_router)
cors_origins = [origin.strip() for origin in os.environ.get(
    "CORS_ORIGINS", "http://localhost:8081,http://localhost:19006"
).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=cors_origins,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Stripe-Signature"])


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
