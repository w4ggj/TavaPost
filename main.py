# TavaPost Studio Backend API Node // Ver 2.2.0
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MODELS ───────────────────────────────────────────────────────────────────

class AdminRequest(BaseModel):
    target_user_id: str

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

# ─── CONNECT ──────────────────────────────────────────────────────────────────

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    active_profile = profile_id or "6a1350634beb548c15895d64"
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}"

    params = {
        "profileId": active_profile,
        "redirect_url": "https://studio.tavaone.com/index.html"
    }

    headers = {
        "Authorization": f"Bearer {zernio_key.strip()}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(zernio_endpoint, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=f"Zernio Error: {response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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

# ─── GENERATE DRAFT ───────────────────────────────────────────────────────────

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
        usage_count = profile.get('monthly_draft_count', 0)

        if profile.get('subscription_tier') == 'starter' and usage_count >= 25:
            raise HTTPException(status_code=403, detail="Monthly limit reached.")

        # B. Process image
        file_content = await file.read()
        img = Image.open(io.BytesIO(file_content))
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Scale down if too large
        w, h = img.size
        max_dim = 1080
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        # Enforce Instagram aspect ratio (4:5 to 1.91:1)
        w, h = img.size
        aspect = w / h
        if aspect < 0.8:
            new_h = int(w / 0.8)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        elif aspect > 1.91:
            new_w = int(h * 1.91)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))

        # Minimum 320px on shortest side
        w, h = img.size
        if w < 320 or h < 320:
            scale = 320 / min(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90, optimize=True)
        jpeg_content = buffer.getvalue()

        # Save to /tmp — served via /image/ endpoint for Instagram
        file_name = f"{uuid.uuid4()}.jpg"
        tmp_path = os.path.join(tempfile.gettempdir(), file_name)
        with open(tmp_path, "wb") as f:
            f.write(jpeg_content)

        # Also upload to Supabase for permanent storage
        supabase_admin.storage.from_("tavapost-images").upload(
            file_name, jpeg_content, {"content_type": "image/jpeg"}
        )

        # Use Render URL — clean, direct, Instagram-compatible
        public_url = f"https://tavapost-backend.onrender.com/image/{file_name}"
        print(f"DEBUG: Serving image at {public_url}")

        # C. Gemini caption generation
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

        # D. Increment usage
        supabase_admin.table('user_profiles').update({'monthly_draft_count': usage_count + 1}).eq('id', user_id).execute()

        return {"image_url": public_url, "draft_text": raw_text}

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

    body = {
        "profileId": "6a1350634beb548c15895d64",
        "content": payload.caption,
        "publishNow": True,
        "platforms": [p.dict() for p in payload.platforms]
    }

    # Only attach image if a real URL is provided
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

# ─── ADMIN ────────────────────────────────────────────────────────────────────

ADMIN_SECRET = os.environ.get("ADMIN_SECRET_KEY", "super-secret-tava-key-123")

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

# ─── STRIPE ───────────────────────────────────────────────────────────────────

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

# ─── Add User ───────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: str
    password: str
    tier: str

@app.post("/admin/create-user")
async def create_user(request: CreateUserRequest):
    # CRITICAL: Add a check here to ensure only YOU can call this
    try:
        # Create user via Supabase Auth
        new_user = supabase_admin.auth.admin.create_user({
            "email": request.email,
            "password": request.password,
            "email_confirm": True
        })
        
        # Add profile
        supabase_admin.table('user_profiles').insert({
            'id': new_user.user.id,
            'subscription_tier': request.tier,
            'monthly_draft_count': 0
        }).execute()
        
        return {"status": "success", "user_id": new_user.user.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateTierRequest(BaseModel):
    target_user_id: str
    new_tier: str

@app.post("/admin/create-user")
async def create_user(request: CreateUserRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != os.environ.get("ADMIN_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    try:
        # 1. Create the Auth User
        new_user = supabase_admin.auth.admin.create_user({
            "email": request.email,
            "password": request.password,
            "email_confirm": True
        })
        
        # 2. Use UPSERT instead of UPDATE
        # This will either overwrite the tier the trigger created, 
        # or create it if the trigger hasn't fired yet.
        supabase_admin.table('user_profiles').upsert({
            'id': new_user.user.id,
            'subscription_tier': request.tier,
            'monthly_draft_count': 0
        }).execute()
        
        return {"status": "success", "user_id": new_user.user.id}
        
    except Exception as e:
        # If it's a genuine error, we log it
        print(f"Provisioning error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
