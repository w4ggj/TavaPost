# TavaPost Studio Backend API Node // Ver 2.1.2
import os
import httpx
import base64
import stripe
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from supabase import create_client, Client
from pydantic import BaseModel
from fastapi import Header, HTTPException

# Your existing setup probably looks like this:
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

class CheckoutRequest(BaseModel):
    user_id: str

# ADD THIS NEW ADMIN SETUP:
# This uses the master key to bypass normal security rules for admin tasks
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase_admin: Client = create_client(url, service_key)

# A simple Pydantic model to accept the user ID from the frontend
class AdminRequest(BaseModel):
    target_user_id: str

app = FastAPI(title="TavaOne Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlatformTarget(BaseModel):
    platform: str
    accountId: str

class PostRequest(BaseModel):
    image_url: Optional[str] = ""
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
    user_id: str = Form(...) # NEW: We need to know who is requesting this
):
    # 1. Verify User and Check Limits
    try:
        user_response = supabase.table('user_profiles').select('subscription_tier, monthly_draft_count').eq('id', user_id).single().execute()
        profile = user_response.data
        
        tier = profile.get('subscription_tier', 'starter')
        usage_count = profile.get('monthly_draft_count', 0)
        
        # Enforce the 50-post limit for the Starter tier
        if tier == 'starter' and usage_count >= 50:
            raise HTTPException(status_code=403, detail="Monthly limit reached. Please upgrade to Pro.")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database verification failed: {str(e)}")

    # 2. Proceed with Gemini AI Generation
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY.")

    try:
        file_content = await file.read()
        base64_image = base64.b64encode(file_content).decode("utf-8")
        google_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        
        system_rules = "CRITICAL: Output ONLY the requested caption options. Do not include introductory conversational filler."
        if custom_prompt and custom_prompt.strip():
            system_rules += f"\nStrict Voice Guidelines:\n{custom_prompt.strip()}"

        body = {
            "contents": [{"parts": [
                {"text": f"{system_rules}\n\nTask: Provide 3 distinct social media caption variations. Separate using 'Variation 1.', 'Variation 2.', and 'Variation 3.'"},
                {"inlineData": {"mimeType": file.content_type, "data": base64_image}}
            ]}]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(google_url, json=body, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Google API Error: {response.text}")
            
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # 3. Increment the User's Usage Counter on Success
            try:
                supabase.table('user_profiles').update({
                    'monthly_draft_count': usage_count + 1
                }).eq('id', user_id).execute()
            except Exception as e:
                print(f"Non-fatal error updating count for {user_id}: {str(e)}")
                
            return {"image_url": "https://studio.tavaone.com/placeholder.jpg", "draft_text": raw_text}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/disconnect-platform")
async def disconnect_platform(payload: dict):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    account_id = payload.get("account_id")
    
    if not account_id:
        raise HTTPException(status_code=400, detail="Missing account_id")

    zernio_disconnect_url = f"https://zernio.com/api/v1/accounts/{account_id}"
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(zernio_disconnect_url, headers=headers)
            if response.status_code in [200, 204, 404]:
                return {"status": "success"}
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
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
        
    print("DEBUG - SENDING TO ZERNIO:", body)
    
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
        # Create a secure Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': 'price_1TbMC2B4jnTQeHqCSznEjs01', 
                    'quantity': 1,
                },
            ],
            mode='subscription',
            # USE THIS ONE:
            client_reference_id=request.user_id, 
            success_url='https://studio.tavaone.com/success',
            cancel_url='https://studio.tavaone.com/cancel',
        )
        
        # Return the secure Stripe URL to the frontend
        return {"url": checkout_session.url}
        
    except Exception as e:
        print(f"Checkout Error: {e}") # This will show the error in Render logs!
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        print(f"Auth failed: {e}")
        raise HTTPException(status_code=400)

    # Debug: Print every event type we receive to the logs
    print(f"Received event type: {event['type']}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Check if the client_reference_id is actually there
        user_id = session.get('client_reference_id')
        print(f"Processing checkout.session.completed for user: {user_id}")
        
        if user_id:
            supabase_admin.table('user_profiles').update({'subscription_tier': 'pro'}).eq('id', user_id).execute()
            print("Database updated to pro")
            
    return {"status": "success"}
