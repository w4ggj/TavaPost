# TavaPost Studio Backend API Node // Ver 2.2.1
import os
import io
import httpx
import base64
import stripe
import tempfile
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from PIL import Image

# ─── SETUP ────────────────────────────────────────────────────────────────────

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase_admin: Client = create_client(url, service_key)

app = FastAPI(title="TavaOne Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://studio.tavaone.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MODELS (ALL UNIFIED AT TOP FOR PYTHON TYPE PARSING) ──────────────────────

class CheckoutRequest(BaseModel):
    price_id: str

class PlatformTarget(BaseModel):
    platform: str
    accountId: str

class PostRequest(BaseModel):
    image_url: str
    caption: str
    platforms: List[PlatformTarget]
    profile_id: Optional[str] = None

class ProfileCreateRequest(BaseModel):
    user_id: str

class AdminRequest(BaseModel):
    target_user_id: str

class UpdateTierRequest(BaseModel):
    target_user_id: str
    new_tier: str

class CreateUserRequest(BaseModel):
    email: str
    password: str
    tier: str

# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaOne Engine"}

# ─── IMAGE SERVING ────────────────────────────────────────────────────────────

@app.get("/image/{filename}")
async def serve_image(filename: str):
    file_path = os.path.join(tempfile.gettempdir(), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(file_path, media_type="image/jpeg")

# ─── CONNECT & PROVISION WORKSPACES ───────────────────────────────────────────

@app.post("/api/create-zernio-profile")
async def create_zernio_profile(payload: ProfileCreateRequest):
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")

    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY")

    headers = {"Authorization": f"Bearer {zernio_key.strip()}", "Content-Type": "application/json"}
    unique_id = str(uuid.uuid4())[:8]
    body = {"name": f"TavaOne_{payload.user_id}_{unique_id}"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("https://zernio.com/api/v1/profiles", json=body, headers=headers, timeout=15.0)
            
            # --- DEBUGGING BLOCK ---
            raw_json = resp.json()
            print(f"DEBUG: Full Zernio Response JSON: {raw_json}")
            # -----------------------

            if resp.status_code not in [200, 201]:
                raise HTTPException(status_code=resp.status_code, detail=f"Zernio API Error: {resp.text}")
            
            # Use a more flexible search for the ID
            new_profile_id = raw_json.get("_id") or raw_json.get("id") or (raw_json.get("profile") or {}).get("_id")
            
            if not new_profile_id:
                raise HTTPException(status_code=500, detail=f"Zernio response format unexpected. Response: {raw_json}")

            # Database write
            supabase_admin.table('user_settings').upsert({
                "user_id": payload.user_id,
                "zernio_profile_id": new_profile_id
            }, on_conflict="user_id").execute()

            return {"zernio_profile_id": new_profile_id}

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")

import asyncio  # add this at the top of the file with the other imports

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profileId: str):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    headers = {"Authorization": f"Bearer {zernio_key.strip()}"}
    
    redirect_url = "https://studio.tavaone.com/"  # ← sends user back here after auth
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId={profileId}&redirectUri={redirect_uri}"
    
    # Retry loop — Zernio has a propagation delay after profile creation.
    # A newly created profile may return 404 for 1-5 seconds. Retry before giving up.
    MAX_RETRIES = 4
    RETRY_DELAY = 1.5  # seconds between attempts

    async with httpx.AsyncClient() as client:
        for attempt in range(1, MAX_RETRIES + 1):
            response = await client.get(zernio_endpoint, headers=headers, timeout=10.0)
            print(f"DEBUG get-connect-url: attempt {attempt}, status {response.status_code}")

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    raise HTTPException(status_code=500, detail="Invalid JSON from Zernio")

            if response.status_code == 404:
                if attempt < MAX_RETRIES:
                    print(f"INFO: Profile {profileId} not yet indexed by Zernio. Retrying in {RETRY_DELAY}s... ({attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    # Only clear the DB record after all retries are exhausted —
                    # this means the profile is genuinely gone, not just slow to propagate.
                    print(f"CRITICAL: Profile {profileId} not found after {MAX_RETRIES} attempts. Clearing stale DB record.")
                    supabase_admin.table('user_settings').update({"zernio_profile_id": None}).eq("zernio_profile_id", profileId).execute()
                    raise HTTPException(status_code=404, detail="Workspace expired or not found. Please click Connect again.")

            # Any other non-200 status (500, 403, etc.) — fail immediately
            raise HTTPException(status_code=response.status_code, detail=f"Zernio error: {response.text}")

@app.get("/api/debug-zernio-profile")
async def debug_zernio_profile(profileId: str):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    headers = {"Authorization": f"Bearer {zernio_key.strip()}"}
    
    async with httpx.AsyncClient() as client:
        # Test 1: Does the profile exist at all?
        r1 = await client.get(f"https://zernio.com/api/v1/profiles/{profileId}", headers=headers, timeout=10.0)
        
        # Test 2: Does the /auth sub-path exist?
        r2 = await client.get(f"https://zernio.com/api/v1/profiles/{profileId}/auth?platform=facebook", headers=headers, timeout=10.0)
        
        # Test 3: What does the top-level profiles list look like?
        r3 = await client.get("https://zernio.com/api/v1/profiles", headers=headers, timeout=10.0)
        
        return {
            "profile_direct": {"status": r1.status_code, "body": r1.text},
            "profile_auth":   {"status": r2.status_code, "body": r2.text},
            "profiles_list":  {"status": r3.status_code, "body": r3.text},
        }
        
@app.get("/api/get-accounts")
async def get_accounts():
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    headers = {
        "Authorization": f"Bearer {zernio_key.strip()}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("https://zernio.com/api/v1/accounts", headers=headers)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ─── CAPTION GENERATOR PIPELINE ───────────────────────────────────────────────

@app.post("/generate-draft")
async def generate_draft(
    file: UploadFile = File(...),
    custom_prompt: str = Form(None),
    user_id: str = Form(...)
):
    usage_count = 0
    gemini_key = os.environ.get("GEMINI_API_KEY")

    try:
        # A. Usage check
        response = supabase.table('user_profiles').select('subscription_tier, monthly_draft_count').eq('id', user_id.strip()).execute()
        profile = response.data[0] if response.data else {'subscription_tier': 'starter', 'monthly_draft_count': 0}
        tier = profile.get('subscription_tier')
        usage_count = profile.get('monthly_draft_count', 0)

        if tier == 'starter' and usage_count >= 25:
            raise HTTPException(status_code=403, detail="Monthly limit reached.")

        # B. Process image
        file_content = await file.read()
        img = Image.open(io.BytesIO(file_content))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        max_dim = 1080
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        jpeg_content = buffer.getvalue()

        # Save to /tmp
        file_name = f"{uuid.uuid4()}.jpg"
        tmp_path = os.path.join(tempfile.gettempdir(), file_name)
        with open(tmp_path, "wb") as f:
            f.write(jpeg_content)

        # Upload to Supabase
        supabase_admin.storage.from_("tavapost-images").upload(
            file_name, jpeg_content, {"content_type": "image/jpeg"}
        )
        public_url = f"https://tavapost-backend.onrender.com/image/{file_name}"

        # C. Gemini caption generation (WITH DEMO INTERCEPT)
        is_mock = False
        if tier == 'demo':
            raw_text = "✨ [DEMO MODE] This is a mock caption generated for demonstration purposes. In a live account, our AI engine would analyze your media and craft a custom brand-aligned caption here. ###SEPARATOR### Draft option two: Your brand voice would appear here for your audience to engage with. ###SEPARATOR### Draft option three: Experience the power of TavaOne Studio with real AI analysis."
            is_mock = True
        else:
            if not gemini_key:
                raise Exception("Gemini key missing.")
            
            base64_image = base64.b64encode(jpeg_content).decode("utf-8")
            system_rules = "CRITICAL: Output ONLY caption options. Use '###SEPARATOR###' between each option. No filler."
            if custom_prompt and custom_prompt.strip():
                system_rules += f"\nStrict Voice Guidelines:\n{custom_prompt.strip()}"

            body = {
                "contents": [{"parts": [
                    {"text": f"{system_rules}\n\nTask: Provide 3 distinct social media caption variations. Separate each one with ###SEPARATOR###."},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_image}}
                ]}]
            }

            google_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(google_url, json=body, headers={"Content-Type": "application/json"})
                if response.status_code != 200:
                    raise Exception(f"Gemini API Error: {response.text}")
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        if not is_mock:
            supabase_admin.table('user_profiles').update({'monthly_draft_count': usage_count + 1}).eq('id', user_id).execute()

        return {"image_url": public_url, "draft_text": raw_text, "is_mock": is_mock}

    except Exception as e:
        print(f"DEBUG: Process failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── PUBLISH ──────────────────────────────────────────────────────────────────

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    headers = {
        "Authorization": f"Bearer {zernio_key.strip()}",
        "Content-Type": "application/json"
    }

    active_profile = payload.profile_id or "6a1350634beb548c15895d64"

    body = {
        "profileId": active_profile,
        "content": payload.caption,
        "publishNow": True,
        "platforms": [p.dict() for p in payload.platforms]
    }

    if payload.image_url and payload.image_url.strip() and "placeholder" not in payload.image_url:
        body["mediaItems"] = [
            {
                "type": "image",
                "url": payload.image_url.strip()
            }
        ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post("https://zernio.com/api/v1/posts", json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            print(f"Zernio API Error Details: {response.text}")
            return {"status": "error", "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Publishing failed: {str(e)}")

# ─── STRIPE SUB SERVICES ──────────────────────────────────────────────────────

@app.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': request.price_id, 'quantity': 1}],
            mode='subscription',
            success_url='https://studio.tavaone.com/setup-account.html?email={CHECKOUT_SESSION_EMAIL}',
            cancel_url='https://studio.tavaone.com/',
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')
        if customer_email:
            print(f"Payment successful for: {customer_email}")
            supabase_admin.table('pending_registrations').insert({
                'email': customer_email,
                'tier': 'founders',
                'status': 'paid'
            }).execute()

    return {"status": "success"}

# ─── ADMIN SYSTEM METHODS ─────────────────────────────────────────────────────

ADMIN_SECRET = os.environ.get("ADMIN_SECRET_KEY", "tava-admin-998877")

@app.post("/admin/create-user")
async def create_user(request: CreateUserRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    try:
        new_user = supabase_admin.auth.admin.create_user({
            "email": request.email,
            "password": request.password,
            "email_confirm": True
        })
        
        supabase_admin.table('user_profiles').upsert({
            'id': new_user.user.id,
            'subscription_tier': request.tier,
            'monthly_draft_count': 0
        }).execute()
        
        return {"status": "success", "user_id": new_user.user.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/update-tier")
async def update_tier(request: UpdateTierRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    try:
        supabase_admin.table('user_profiles').update({
            'subscription_tier': request.new_tier
        }).eq('id', request.target_user_id).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/disconnect")
async def admin_disconnect_social(request: AdminRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        supabase_admin.table('user_profiles').update({
            'meta_access_token': None,
            'meta_page_id': None
        }).eq('id', request.target_user_id).execute()
        return {"status": "success", "message": "Social accounts disconnected."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/delete")
async def admin_delete_user(request: AdminRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        supabase_admin.auth.admin.delete_user(request.target_user_id)
        return {"status": "success", "message": "User permanently deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/users")
async def admin_list_users(x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        auth_users = supabase_admin.auth.admin.list_users()
        profiles_response = supabase_admin.table('user_profiles').select('id, subscription_tier, monthly_draft_count').execute()
        profiles_data = {p['id']: p for p in profiles_response.data}

        user_list = []
        for u in auth_users:
            profile = profiles_data.get(u.id, {})
            user_list.append({
                "id": u.id,
                "email": u.email,
                "tier": profile.get('subscription_tier', 'starter'),
                "usage": profile.get('monthly_draft_count', 0)
            })
        return {"status": "success", "data": user_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
