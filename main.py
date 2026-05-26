# TavaPost Studio Backend API Node // Ver 2.1.2
import os
import httpx
import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

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
async def generate_draft(file: UploadFile = File(...), custom_prompt: str = Form(None)):
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
