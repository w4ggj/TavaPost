# TavaPost Studio Backend API Node // Ver 2.1.0
import os
import httpx
import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="TavaPost Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PostRequest(BaseModel):
    image_url: str
    caption: str
    fb_account_id: str = None
    ig_account_id: str = None
    profile_id: str = None 

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaPost Engine"}

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    # Always enforce the verified master Zernio profile token workspace
    active_profile = "6a1350634beb548c15895d64"
    
    # Aggressively clean up the token string to prevent any line breaks or quote leaks
    clean_key = zernio_key.strip().replace("'", "").replace('"', "").replace("\n", "").replace("\r", "")
    
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId={active_profile}&redirect_url=https://studio.tavaone.com/index.html"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(zernio_endpoint, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                # 🚀 DIAGNOSTIC LOG: Prints the exact error reason straight into your Render terminal
                print(f"!!! ZERNIO CONNECTION HANDSHAKE CRASH: {response.status_code} - {response.text} !!!")
                raise HTTPException(status_code=response.status_code, detail=f"Zernio Handshake Rejected: {response.text}")
                
        except Exception as e:
            # Catch raw connection timeouts or network blocks
            print(f"!!! BACKEND NETWORK EXCEPTION: {str(e)} !!!")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-draft")
async def generate_draft(file: UploadFile = File(...), custom_prompt: str = Form(None)):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Backend missing GEMINI_API_KEY environment variable.")

    try:
        file_content = await file.read()
        base64_image = base64.b64encode(file_content).decode("utf-8")
        
        google_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        
        headers = {"Content-Type": "application/json"}
        
        system_rules = "CRITICAL: Output ONLY the requested caption options. Do not include introductory conversational filler text, headers, or markdown block code text backticks."
        if custom_prompt and custom_prompt.strip():
            system_rules += f"\nStrict Voice and Content Guidelines:\n{custom_prompt.strip()}"

        user_instruction = """
        Analyze this image and provide 3 distinct social media caption variations optimized for Facebook and Instagram. 
        Separate them explicitly using 'Variation 1.', 'Variation 2.', and 'Variation 3.' labels.
        """

        body = {
            "contents": [{
                "parts": [
                    {"text": f"{system_rules}\n\nTask Instructions:\n{user_instruction}"},
                    {
                        "inlineData": {
                            "mimeType": file.content_type,
                            "data": base64_image
                        }
                    }
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(google_url, json=body, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Google API Error: {response.text}")
            
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

            return {
                "image_url": "https://studio.tavaone.com/placeholder.jpg",
                "draft_text": raw_text
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Fetch Fault: {str(e)}")

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    zernio_publish_url = "https://zernio.com/api/v1/posts"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }
    
    target_platforms = []
    
    # Correctly mapping account IDs to Zernio API format
    if payload.fb_account_id and payload.fb_account_id.strip():
        target_platforms.append({
            "platform": "facebook",
            "accountId": payload.fb_account_id.strip()
        })
        
    if payload.ig_account_id and payload.ig_account_id.strip():
        target_platforms.append({
            "platform": "instagram",
            "accountId": payload.ig_account_id.strip()
        })

    if not target_platforms:
        raise HTTPException(status_code=400, detail="No connected platform account IDs found.")

    # 🚀 FIXED: Hard-coded master workspace ID
    active_profile = "6a1350634beb548c15895d64"

    body = {
        "profileId": active_profile,
        "content": payload.caption,
        "platforms": target_platforms
    }
    
    print(f"!!! SENDING PAYLOAD TO ZERNIO: {body} !!!")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(zernio_publish_url, json=body, headers=headers)
            
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
                
            return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/disconnect-platform")
async def disconnect_platform(payload: dict):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    platform = payload.get("platform")
    account_id = payload.get("account_id")
    
    zernio_disconnect_url = f"https://zernio.com/api/v1/accounts/{account_id}"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(zernio_disconnect_url, headers=headers)
            return {"status": "success", "code": response.status_code}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-accounts")
async def get_accounts():
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://zernio.com/api/v1/accounts", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail=response.text)
