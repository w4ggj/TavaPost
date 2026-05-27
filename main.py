# TavaPost Studio Backend API Node // Ver 2.1.2
import os
import io
import httpx
import base64
import stripe
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from fastapi import Header, Request
from PIL import Image

# Setup
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

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaOne Engine"}

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
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Zernio Error: {response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-draft")
async def generate_draft(
    file: UploadFile = File(...), 
    custom_prompt: str = Form(None),
    user_id: str = Form(...) 
):
    # Initialize jpeg_content as None so it is defined for the whole function scope
    jpeg_content = None 

    # 1. Verify User and Check Limits
    try:
        response = supabase.table('user_profiles').select('subscription_tier, monthly_draft_count').eq('id', user_id.strip()).execute()
        profile = response.data[0] if response.data else {'subscription_tier': 'starter', 'monthly_draft_count': 0}
        usage_count = profile.get('monthly_draft_count', 0)
        
        if profile.get('subscription_tier') == 'starter' and usage_count >= 25:
            raise HTTPException(status_code=403, detail="Monthly limit reached.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database check failed: {str(e)}")

    # 2. UPLOAD TO SUPABASE BUCKET
    try:
        file_content = await file.read()
        img = Image.open(io.BytesIO(file_content))
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90, optimize=True)
        jpeg_content = buffer.getvalue() # Now this is accessible to the rest of the function
        
        file_name = f"{uuid.uuid4()}.jpg"
        supabase_admin.storage.from_("tavapost-images").upload(file_name, jpeg_content, {"content_type": "image/jpeg"})
        public_url = supabase_admin.storage.from_("tavapost-images").get_public_url(file_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

    # 3. GEMINI AI GENERATION
    gemini_key = os.environ.get("GEMINI_API_KEY")
    try:
        if jpeg_content is None:
            raise Exception("Image processing failed.")
            
        base64_image = base64.b64encode(jpeg_content).decode("utf-8")
        
        # All of this must be indented inside the try block
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
                raise Exception(f"Gemini Error: {response.text}")
            
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            
        # 4. Increment usage
        supabase_admin.table('user_profiles').update({'monthly_draft_count': usage_count + 1}).eq('id', user_id).execute()
        
        # 5. Sanitize hashtags (already correct)
        # ... (keep your existing hashtag sanitization code here) ...
        
        return {"image_url": public_url, "draft_text": raw_text}
        
    except Exception as e:
        print(f"Error in Gemini generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    media_items = [{"type": "image", "url": payload.image_url}]
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    if not payload.platforms:
        raise HTTPException(status_code=400, detail="No platforms selected.")

    headers = {
        "Authorization": f"Bearer {zernio_key.strip()}",
        "Content-Type": "application/json"
    }
    
    body = {
        "profileId": "6a1350634beb548c15895d64",
        "content": payload.caption,
        "publishNow": True,
        "status": "published", 
        "platforms": [p.dict() for p in payload.platforms]
    }
    
    # Inject the image URL if it exists
    if payload.image_url:
        body["mediaItems"] = [
            {
                "type": "image",
                "url": payload.image_url
            }
        ]
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post("https://zernio.com/api/v1/posts", json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            return {"status": "error", "detail": response.text}
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

# --- ADMIN ENDPOINTS ---

ADMIN_SECRET = os.environ.get("ADMIN_SECRET_KEY", "super-secret-tava-key-123") # Change this in Render later!

@app.post("/admin/disconnect")
async def admin_disconnect_social(request: AdminRequest, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Example: Update the user's row in your database to wipe their Meta tokens
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
        # This completely deletes the user from the Supabase Authentication system
        supabase_admin.auth.admin.delete_user(request.target_user_id)
        
        # Note: If your tables have "ON DELETE CASCADE" set up in Supabase, 
        # deleting them from Auth will automatically wipe their rows in your other tables!
        
        return {"status": "success", "message": "User permanently deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/users")
async def admin_list_users(x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # 1. Securely fetch all user emails from the Auth system
        auth_users = supabase_admin.auth.admin.list_users()
        
        # 2. Fetch all subscription tiers and usage stats from the public profiles table
        profiles_response = supabase_admin.table('user_profiles').select('id, subscription_tier, monthly_draft_count').execute()
        
        # Convert the profile list into a dictionary for super-fast lookups
        profiles_data = {p['id']: p for p in profiles_response.data}
        
        # 3. Merge the data together
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

@app.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id, # Dynamically uses the ID from the frontend
                'quantity': 1,
            }],
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
        
        # We store this payment intent so we can "find" it when they register
        if customer_email:
            print(f"Payment successful for: {customer_email}")
            # Optional: Add to a 'pending_registrations' table in Supabase
            supabase_admin.table('pending_registrations').insert({
                'email': customer_email,
                'tier': 'founders',
                'status': 'paid'
            }).execute()
            
    return {"status": "success"}
