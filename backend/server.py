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
    analyze_print_quality,
    demo_room_preview,
    demo_transform,
    generation_cache_key,
)
from printful_catalog import (
    CatalogVariant,
    find_selection,
    find_variant,
    get_catalog,
    serialize_variants,
    snapshot_variants,
)

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

PRINTFUL_TOKEN = os.environ.get('PRINTFUL_TOKEN', '')
PRINTFUL_STORE_ID = os.environ.get('PRINTFUL_STORE_ID', '')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
PRINTFUL_MARKUP = float(os.environ.get('PRINTFUL_MARKUP', '1.6'))
INHOUSE_SHIPPING = 12.0

# Emergent-managed Resend email (base URL is a hardcoded constant so it survives deploy)
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMERGENT_EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Frame Works Prints")

# Admin seeding + webhook auth (secrets come from env — never hard-coded)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
PRINTFUL_WEBHOOK_SECRET = os.environ.get("PRINTFUL_WEBHOOK_SECRET", "")

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
    """is_framed must come from resolve_printful_variant — never charge the frame
    surcharge for a combo that can't actually ship framed (wrong size/material)."""
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


def resolve_printful_variant(material: str, size: str, frame: str):
    """Legacy read-only resolver with no product substitution.

    New app flows persist a concrete printful_variant_id. This helper remains for
    older saved projects, but unlike the former implementation it never silently
    converts an unavailable framed choice into an unframed product.
    """
    finish = normalize_finish(material, frame)
    variant = find_selection(snapshot_variants(PRINTFUL_MARKUP), material, size, finish)
    return (variant.id, variant.framed) if variant else (None, False)


async def validated_printful_variant(
    variant_id: int,
    material: str,
    size: str,
    frame: str,
    *,
    require_in_stock: bool = True,
) -> CatalogVariant:
    variants, _, _ = await get_catalog(PRINTFUL_MARKUP)
    variant = find_variant(variants, int(variant_id))
    expected_finish = normalize_finish(material, frame)
    if not variant:
        raise HTTPException(status_code=422, detail="The selected Printful variant is not in the approved wall-art catalog.")
    if (variant.material, variant.size_key, variant.finish_key) != (material, size, expected_finish):
        raise HTTPException(status_code=422, detail="The selected Printful variant does not match the chosen product, size, and finish.")
    if require_in_stock and not variant.in_stock:
        raise HTTPException(status_code=409, detail="The selected Printful variant is currently out of stock.")
    return variant


async def generate_printful_mockup(project_id: str, variant: CatalogVariant) -> Optional[dict]:
    """Request a real product photo mockup for one exact validated variant.
    Returns None when account authorization or a public print-file URL is unavailable,
    so callers can continue showing the official Catalog API product image.
    Note: this renders ONE representative panel — see server.py multi-panel print-file
    handling for why the true panel-split print isn't reproduced here."""
    if not (PRINTFUL_TOKEN and variant.id and variant.product_id and PUBLIC_BASE_URL):
        return None
    image_url = f"{PUBLIC_BASE_URL}/api/public/project/{project_id}"
    headers = {"Authorization": f"Bearer {PRINTFUL_TOKEN}", "Content-Type": "application/json"}
    if PRINTFUL_STORE_ID:
        headers["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    payload = {
        "variant_ids": [variant.id],
        "format": "jpg",
        "files": [{"placement": "default", "image_url": image_url}],
    }
    try:
        async with httpx.AsyncClient(base_url="https://api.printful.com", headers=headers, timeout=30) as c:
            r = await c.post(f"/mockup-generator/create-task/{variant.product_id}", json=payload)
            if r.status_code >= 400:
                logger.error(f"Printful mockup create-task error {r.status_code}: {r.text[:300]}")
                return None
            task_key = (r.json().get("result") or {}).get("task_key")
            if not task_key:
                return None
            for _ in range(18):  # ~27s max
                await asyncio.sleep(1.5)
                pr = await c.get("/mockup-generator/task", params={"task_key": task_key})
                result = (pr.json().get("result") or {}) if pr.status_code < 400 else {}
                status = result.get("status")
                if status == "completed":
                    mockups = result.get("mockups") or []
                    if mockups and mockups[0].get("mockup_url"):
                        return {"mockup_url": mockups[0]["mockup_url"], "product_id": variant.product_id, "variant_id": variant.id}
                    return None
                if status == "failed":
                    logger.error(f"Printful mockup task failed: {result}")
                    return None
            logger.warning(f"Printful mockup task {task_key} timed out")
            return None
    except Exception as e:
        logger.error(f"Printful mockup generation error: {e}")
        return None


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


class TransformIn(BaseModel):
    image_base64: str
    style: str
    enhance: bool = True
    remove_bg: bool = False


class RoomPreviewIn(BaseModel):
    image_base64: str
    room: str
    frame: str = "wood"
    material: str = "canvas"
    panels: int = 1


class PrintQualityIn(BaseModel):
    image_base64: str


class ProjectIn(BaseModel):
    original: str
    current: str
    style: str
    room: Optional[str] = None
    room_preview: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    frame: Optional[str] = None
    panels: Optional[int] = 1
    panel_key: Optional[str] = None
    price: Optional[float] = None
    printful_variant_id: Optional[int] = None
    printful_product_id: Optional[int] = None
    printful_variant_name: Optional[str] = None
    printful_variant_image: Optional[str] = None
    printful_retail_price: Optional[float] = None


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


STYLE_PROMPTS = {
    "canvas": "Reproduce this photo as a premium hand-painted canvas print with subtle brush texture, gallery quality.",
    "watercolor": "Transform this photo into an elegant watercolor painting with soft washes and artistic edges.",
    "bw": "Convert this photo into high-contrast black-and-white fine art photography with rich tonal range, gallery print quality.",
    "abstract": "Reinterpret this photo as a modern abstract art piece with bold shapes and a refined color palette while keeping the subject recognizable.",
    "minimal": "Transform this photo into a minimalist fine-art poster interpretation with clean lines and generous negative space.",
    "luxury": "Render this photo as a luxury framed art rendition with rich, opulent, refined color grading suitable for a high-end home.",
    "gallery": "Enhance this photo into a museum gallery-style fine art print with refined, balanced composition and premium color.",
}


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
@api_router.post("/transform")
async def transform(data: TransformIn, user=Depends(get_current_user)):
    rate_limit(f"ai:{user['id']}", 20, 60)
    options = {"style": data.style, "enhance": data.enhance, "remove_bg": data.remove_bg}
    cache_key = generation_cache_key("transform", data.image_base64, options)
    if AI_DEMO_MODE:
        try:
            result, notices = await asyncio.to_thread(
                demo_transform, data.image_base64, data.style, data.enhance, data.remove_bg
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
    base = STYLE_PROMPTS.get(data.style, STYLE_PROMPTS["gallery"])
    parts = []
    if data.enhance:
        parts.append("First, enhance lighting, sharpness, color balance and composition.")
    parts.append(base)
    if data.remove_bg:
        parts.append("Replace the background with a clean, neutral studio backdrop suitable for wall art.")
    parts.append("Output a high-resolution, print-ready artwork. Keep the main subject clearly recognizable.")
    prompt = " ".join(parts)
    result = await gemini_edit(data.image_base64, prompt)
    await cache_generation(cache_key, result)
    return {
        "image_base64": result,
        "mode": "cloud",
        "cached": False,
        "remaining_today": remaining,
        "notices": [f"Cloud preview generated at {IMAGE_QUALITY} quality."],
    }


@api_router.post("/print-quality")
async def print_quality(data: PrintQualityIn, user=Depends(get_current_user)):
    rate_limit(f"quality:{user['id']}", 30, 60)
    try:
        result = await asyncio.to_thread(analyze_print_quality, data.image_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


# Per-material frame descriptions for the room-preview prompt. These labels match
# the exact finish keys returned by the verified Printful catalog boundary.
def frame_description(material: str, frame: str) -> str:
    if frame == "none":
        if material == "canvas":
            return "a frameless gallery-wrapped canvas, with the image continuing around the 1.25-inch wrapped edges"
        return "an unframed, flat printed poster with no border"
    if frame in {"wood", "brown", "red_oak"}:
        wood_desc = "a dark brown pine" if material == "canvas" else "a light red oak wood"
        return f"{wood_desc} frame"
    if frame == "black":
        return "a matte black wood frame"
    if frame == "white":
        return "a clean white wood frame"
    return f"a {frame} frame"


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


@api_router.get("/printful/catalog")
async def printful_catalog(user=Depends(get_current_user)):
    """Approved wall-art variants from Printful's public Catalog API.

    Public catalog synchronization needs no account token. `orders_configured`
    only reports readiness; credentials are never returned to the client.
    """
    variants, source, synced_at = await get_catalog(PRINTFUL_MARKUP)
    return {
        "variants": serialize_variants(variants),
        "source": source,
        "synced_at": synced_at,
        "orders_configured": bool(PRINTFUL_TOKEN),
        "store_context_configured": bool(PRINTFUL_STORE_ID),
        "markup": PRINTFUL_MARKUP,
        "note": (
            "Live public Printful catalog; shipping is calculated at checkout."
            if source == "printful_live"
            else "Verified offline Printful catalog snapshot; refresh before enabling live sales."
        ),
    }


class QuoteIn(BaseModel):
    material: str
    size: str
    panels: int = 1
    frame: Optional[str] = "none"
    printful_variant_id: Optional[int] = None
    fallback_price: Optional[float] = None  # deprecated/ignored; price is computed server-side
    recipient: Recipient


async def compute_quote(
    user_id: str,
    material: str,
    size: str,
    frame: str,
    panels: int,
    recipient: dict,
    printful_variant_id: Optional[int] = None,
) -> dict:
    """Server-authoritative price for one exact Printful catalog variant."""
    frame = frame or "none"
    variant_id = printful_variant_id
    if variant_id is None:
        # Backward-compatible path for older saved projects; it resolves an exact
        # tuple and never substitutes a different product or finish.
        variant_id, _ = resolve_printful_variant(material, size, frame)
    if variant_id is None:
        raise HTTPException(status_code=422, detail="Choose an available Printful product, size, and finish before checkout.")
    variant = await validated_printful_variant(variant_id, material, size, frame)
    n = max(1, panels or 1)
    base_price = round(variant.retail_price * n, 2)
    prior = await db.orders.count_documents({"user_id": user_id, "material": {"$exists": True}})
    first_order = prior == 0
    disc_pct = FIRST_ORDER_DISCOUNT if first_order else 0.0

    def finalize(retail, product, shipping, base_cost, source, currency="USD"):
        retail = round(retail, 2)
        discount_amount = round(retail * disc_pct, 2)
        return {
            "retail": round(retail - discount_amount, 2),
            "retail_before_discount": retail,
            "first_order": first_order,
            "discount_pct": disc_pct,
            "discount_amount": discount_amount,
            "product": round(product, 2), "shipping": round(shipping, 2),
            "base_cost": base_cost, "source": source, "currency": currency,
            "printful_variant_id": variant.id,
            "printful_product_id": variant.product_id,
            "printful_variant_name": variant.name,
            "printful_variant_image": variant.image,
            "finish_label": variant.finish_label,
        }

    if not PRINTFUL_TOKEN:
        return finalize(base_price + INHOUSE_SHIPPING, base_price, INHOUSE_SHIPPING, None, "catalog")
    headers = {"Authorization": f"Bearer {PRINTFUL_TOKEN}"}
    if PRINTFUL_STORE_ID:
        headers["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    payload = {
        "recipient": {
            "address1": recipient.get("address1", ""), "city": recipient.get("city", ""),
            "state_code": recipient.get("state_code"), "country_code": recipient.get("country_code", "US"),
            "zip": recipient.get("zip", ""),
        },
        "items": [{"variant_id": variant.id, "quantity": n, "files": [{"url": f"{PUBLIC_BASE_URL}/api/public/project/placeholder"}]}],
    }
    try:
        async with httpx.AsyncClient(base_url="https://api.printful.com", headers=headers, timeout=45) as c:
            r = await c.post("/orders/estimate-costs", json=payload)
            if r.status_code >= 400:
                logger.error(f"Printful estimate error {r.status_code}: {r.text[:200]}")
                raise Exception("estimate failed")
            costs = (r.json().get("result") or {}).get("costs") or {}
            base_cost = float(costs.get("total") or 0)
            shipping = float(costs.get("shipping") or 0)
            if base_cost <= 0:
                raise Exception("no cost")
            return finalize(base_cost * PRINTFUL_MARKUP, (base_cost - shipping) * PRINTFUL_MARKUP,
                            shipping * PRINTFUL_MARKUP, round(base_cost, 2), "printful", costs.get("currency", "USD"))
    except Exception as e:
        logger.error(f"quote fallback: {e}")
        return finalize(base_price + INHOUSE_SHIPPING, base_price, INHOUSE_SHIPPING, None, "fallback")


@api_router.post("/quote")
async def quote(data: QuoteIn, user=Depends(get_current_user)):
    return await compute_quote(user["id"], data.material, data.size, data.frame or "none",
                               data.panels, data.recipient.model_dump(), data.printful_variant_id)


class MockupIn(BaseModel):
    project_id: str
    material: str
    size: str
    frame: Optional[str] = "none"
    printful_variant_id: int


@api_router.post("/mockup")
async def mockup(data: MockupIn, user=Depends(get_current_user)):
    """Real Printful product-photo mockup for the exact material/size/frame selected.
    Returns {available: false} when the mockup API is not configured, together with
    the official catalog image for the already-validated exact variant."""
    doc = await db.projects.find_one({"id": data.project_id, "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    variant = await validated_printful_variant(data.printful_variant_id, data.material, data.size, data.frame or "none")
    result = await generate_printful_mockup(data.project_id, variant)
    if not result:
        return {"available": False, "catalog_image": variant.image, "variant_id": variant.id}
    return {"available": True, **result}


# ---------- Public project image (unauthenticated so Printful can fetch it) ----------
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
    style = (order.get("style") or "").replace("_", " ").title()
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
            <tr><td style="padding:14px 16px;color:#6b6459;border-top:1px solid #f0e9de;">Frame &amp; style</td><td style="padding:14px 16px;text-align:right;border-top:1px solid #f0e9de;">{frame} · {style}</td></tr>
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


async def submit_printful_order(
    external_order_id: str,
    project_id: str,
    material: str,
    size: str,
    panels: int,
    frame: str,
    printful_variant_id: int,
    recipient: dict,
):
    """Create a Printful draft order. Returns (status, printful_status, printful_order_id)."""
    variant = await validated_printful_variant(printful_variant_id, material, size, frame)
    if not PRINTFUL_TOKEN:
        return "received", "printful_not_configured", None
    if not PUBLIC_BASE_URL or not project_id:
        return "received", "not_fulfilled_by_printful", None
    n = max(1, panels or 1)
    items = []
    for i in range(n):
        url = f"{PUBLIC_BASE_URL}/api/public/project/{project_id}"
        if n > 1:
            url += f"?panel={i}&of={n}"
        items.append({"variant_id": variant.id, "quantity": 1, "files": [{"url": url}]})
    payload = {
        "external_id": external_order_id,
        "recipient": {
            "name": recipient["name"], "address1": recipient["address1"], "city": recipient["city"],
            "state_code": recipient.get("state_code"), "country_code": recipient.get("country_code", "US"),
            "zip": recipient["zip"],
        },
        "items": items,
    }
    headers = {"Authorization": f"Bearer {PRINTFUL_TOKEN}"}
    if PRINTFUL_STORE_ID:
        headers["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    try:
        async with httpx.AsyncClient(base_url="https://api.printful.com", headers=headers, timeout=90) as c:
            r = await c.post("/orders", json=payload)
            if r.status_code >= 400:
                logger.error(f"Printful order error {r.status_code}: {r.text[:300]}")
                return "received", f"printful_error_{r.status_code}", None
            pid = str((r.json().get("result") or {}).get("id") or "")
            return "in_production", ("framed_draft_created" if variant.framed else "draft_created"), pid
    except Exception as e:
        logger.error(f"Printful call failed: {e}")
        return "received", "printful_unreachable", None


async def create_order_internal(user: dict, cart: dict, price: float, stripe_payment_intent_id: str) -> dict:
    """Create the fulfilled order. Called ONLY after a verified Stripe payment — never
    directly by the client, so orders cannot be placed without payment."""
    project = await db.projects.find_one({"id": cart.get("project_id"), "user_id": user["id"]}) or {}
    order_id = str(uuid.uuid4())
    status, printful_status, printful_order_id = await submit_printful_order(
        order_id, cart.get("project_id"), cart["material"], cart["size"], cart.get("panels") or 1,
        cart.get("frame") or "none", cart["printful_variant_id"], cart["recipient"],
    )
    variant = await validated_printful_variant(
        cart["printful_variant_id"], cart["material"], cart["size"], cart.get("frame") or "none"
    )
    doc = {
        "id": order_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "status": status,
        "printful_status": printful_status,
        "printful_order_id": printful_order_id,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "project_id": cart.get("project_id"),
        "image_base64": project.get("current"),
        "room_preview": project.get("room_preview"),
        "style": project.get("style") or cart.get("style"),
        "material": cart["material"],
        "size": cart["size"],
        "frame": cart.get("frame") or "none",
        "printful_variant_id": variant.id,
        "printful_product_id": variant.product_id,
        "printful_variant_name": variant.name,
        "printful_variant_image": variant.image,
        "printful_finish_label": variant.finish_label,
        "panel_key": cart.get("panel_key"),
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


# ---------- Admin ----------
@api_router.get("/admin/stats")
async def admin_stats(user=Depends(require_admin)):
    q = {"material": {"$exists": True}}
    orders = await db.orders.find(q).to_list(1000)
    revenue = sum(o.get("price", 0) for o in orders)
    # Orders that took payment but have no automated fulfillment path need manual handling.
    unfulfilled_statuses = {"not_fulfilled_by_printful", "printful_not_configured"}
    unfulfilled = sum(1 for o in orders if o.get("printful_status") in unfulfilled_statuses)
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
    printful_variant_id: int
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
    variant = await validated_printful_variant(data.printful_variant_id, data.material, data.size, data.frame)
    saved_variant_id = project.get("printful_variant_id")
    if saved_variant_id is not None and int(saved_variant_id) != variant.id:
        raise HTTPException(status_code=409, detail="The checkout variant no longer matches the saved project selection.")
    q = await compute_quote(
        user["id"], data.material, data.size, data.frame, data.panels,
        data.recipient.model_dump(), data.printful_variant_id,
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
        "printful_variant_id": variant.id,
        "printful_product_id": variant.product_id,
        "printful_variant_name": variant.name,
        "printful_variant_image": variant.image,
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


# ---------- Printful webhooks (order tracking) ----------
PRINTFUL_EVENT_STATUS_POLICY = {
    "package_shipped": ({"partial", "fulfilled"}, "shipped"),
    "package_returned": ({"partial", "fulfilled"}, "received"),
    "order_put_hold": ({"onhold"}, "in_production"),
    "order_remove_hold": ({"pending", "inreview", "inprocess"}, "in_production"),
    "order_failed": ({"failed"}, "cancelled"),
    "order_canceled": ({"canceled"}, "cancelled"),
}


class PrintfulVerificationUnavailable(RuntimeError):
    """The authenticated Printful cross-check could not be completed."""


def printful_auth_headers() -> dict[str, str]:
    headers = {"Authorization": f"Bearer {PRINTFUL_TOKEN}"}
    if PRINTFUL_STORE_ID:
        headers["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    return headers


async def fetch_printful_order(printful_order_id: str) -> Optional[dict]:
    """Fetch an order through the authenticated API; never trust webhook order data."""
    if not PRINTFUL_TOKEN:
        raise PrintfulVerificationUnavailable("Printful order verification is not configured")
    # Printful webhook order IDs are integers. Refusing anything else also prevents an
    # untrusted payload from changing the API path (the API's @external-id form is not needed here).
    if not printful_order_id.isdigit():
        return None
    try:
        async with httpx.AsyncClient(
            base_url="https://api.printful.com",
            headers=printful_auth_headers(),
            timeout=20,
        ) as c:
            response = await c.get(f"/orders/{printful_order_id}")
    except httpx.HTTPError as exc:
        raise PrintfulVerificationUnavailable("Printful order verification request failed") from exc
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise PrintfulVerificationUnavailable(
            f"Printful order verification returned HTTP {response.status_code}"
        )
    result = response.json().get("result") or {}
    if not isinstance(result, dict) or str(result.get("id") or "") != printful_order_id:
        raise PrintfulVerificationUnavailable("Printful returned a mismatched order identifier")
    return result


def verified_printful_webhook_update(payload: dict, local_order: dict, printful_order: dict) -> Optional[dict]:
    """Return a safe local update only when the event matches authoritative Printful data."""
    event_type = str(payload.get("type") or "")
    policy = PRINTFUL_EVENT_STATUS_POLICY.get(event_type)
    if not policy:
        return None
    data = payload.get("data") or {}
    payload_order_id = str((data.get("order") or {}).get("id") or "")
    if not payload_order_id or payload_order_id != str(local_order.get("printful_order_id") or ""):
        return None
    if str(printful_order.get("id") or "") != payload_order_id:
        return None

    # Webhook payloads always identify the store. The authenticated order must agree,
    # and an account-level token must also be constrained to the configured store.
    payload_store = str(payload.get("store") or "")
    authoritative_store = str(printful_order.get("store") or "")
    if not payload_store or not authoritative_store or payload_store != authoritative_store:
        return None
    if PRINTFUL_STORE_ID and authoritative_store != str(PRINTFUL_STORE_ID):
        return None

    # New orders carry our UUID as Printful external_id. Allow missing external_id only
    # for legacy orders created before this binding was added; never allow a mismatch.
    external_id = str(printful_order.get("external_id") or "")
    if external_id and external_id != str(local_order.get("id") or ""):
        return None

    allowed_statuses, app_status = policy
    authoritative_status = str(printful_order.get("status") or "").lower()
    if authoritative_status not in allowed_statuses:
        return None

    update = {
        "status": app_status,
        "printful_status": authoritative_status,
        "printful_store_id": authoritative_store,
        "printful_last_verified_event": event_type,
        "printful_verified_at": datetime.now(timezone.utc).isoformat(),
    }
    if event_type in {"package_shipped", "package_returned"}:
        payload_shipment_id = str((data.get("shipment") or {}).get("id") or "")
        shipment = next(
            (item for item in (printful_order.get("shipments") or [])
             if str(item.get("id") or "") == payload_shipment_id),
            None,
        )
        if not payload_shipment_id or not shipment:
            return None
        if event_type == "package_shipped" and shipment.get("tracking_url"):
            # The tracking URL comes from the authenticated GET response, not the webhook body.
            update["tracking_url"] = shipment["tracking_url"]
    return update


@api_router.post("/webhooks/printful")
async def printful_webhook(payload: dict, token: str = ""):
    """Apply a Printful event only after an authenticated API cross-check."""
    # Fail closed: only process when a secret is configured AND the token matches.
    if not PRINTFUL_WEBHOOK_SECRET or not hmac.compare_digest(
        token.encode("utf-8"), PRINTFUL_WEBHOOK_SECRET.encode("utf-8")
    ):
        logger.warning("Rejected Printful webhook (secret unset or token invalid)")
        return {"ok": True}
    event_type = str(payload.get("type") or "")
    if event_type not in PRINTFUL_EVENT_STATUS_POLICY:
        return {"ok": True, "verified": False}
    data = payload.get("data") or {}
    printful_order_id = str((data.get("order") or {}).get("id") or "")
    if not printful_order_id.isdigit():
        return {"ok": True, "verified": False}
    order = await db.orders.find_one({"printful_order_id": printful_order_id})
    if not order:
        return {"ok": True, "verified": False}
    try:
        authoritative_order = await fetch_printful_order(printful_order_id)
    except PrintfulVerificationUnavailable as exc:
        logger.error("Printful webhook cross-check unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Printful verification unavailable") from exc
    if not authoritative_order:
        logger.warning("Printful webhook referenced an order absent from the authenticated store")
        return {"ok": True, "verified": False}
    update = verified_printful_webhook_update(payload, order, authoritative_order)
    if not update:
        logger.warning("Printful webhook did not match authoritative order state")
        return {"ok": True, "verified": False}
    result = await db.orders.update_one({"id": order["id"]}, {"$set": update})
    tracking = str(update.get("tracking_url") or "")
    if result.modified_count and order.get("user_email"):
        await send_status_email(order["user_email"], order, update["status"], tracking)
    logger.info(
        "Verified Printful webhook %s -> order %s = %s (%s)",
        event_type, order["id"], update["status"], update["printful_status"],
    )
    return {"ok": True, "verified": True}


@app.on_event("startup")
async def register_printful_webhook():
    """Point the Printful store's webhook at this deployment (idempotent per startup)."""
    if not (PRINTFUL_TOKEN and PUBLIC_BASE_URL):
        return
    tok = f"?token={PRINTFUL_WEBHOOK_SECRET}" if PRINTFUL_WEBHOOK_SECRET else ""
    url = f"{PUBLIC_BASE_URL}/api/webhooks/printful{tok}"
    headers = {"Authorization": f"Bearer {PRINTFUL_TOKEN}", "Content-Type": "application/json"}
    if PRINTFUL_STORE_ID:
        headers["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    body = {"url": url, "types": ["package_shipped", "package_returned", "order_failed",
                                  "order_canceled", "order_put_hold", "order_remove_hold"]}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.printful.com/webhooks", headers=headers, json=body)
        if r.status_code >= 400:
            logger.error(f"Printful webhook register failed {r.status_code}: {r.text[:200]}")
        else:
            logger.info(f"Printful webhook registered -> {PUBLIC_BASE_URL}/api/webhooks/printful")
    except Exception as e:
        logger.error(f"Printful webhook register error: {e}")


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
