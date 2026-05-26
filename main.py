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

    # Strictly use master profile ID to ensure handshake workspace continuity
    active_profile = "6a1350634beb548c15895d64"
    clean_key = zernio_key.strip().replace("'", "").replace('"', "").replace("\n", "").replace("\r", "")
    
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId={active_profile}&redirect_url=https://studio.tavaone.com/index.html"
    
    headers = {"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(zernio_endpoint, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Zernio Handshake Rejected: {response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    zernio_publish_url = "https://zernio.com/api/v1/posts"
    
    headers = {"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"}
    
    target_platforms = []
    if payload.fb_account_id and payload.fb_account_id.strip():
        target_platforms.append({"platform": "facebook", "accountId": payload.fb_account_id.strip()})
    if payload.ig_account_id and payload.ig_account_id.strip():
        target_platforms.append({"platform": "instagram", "accountId": payload.ig_account_id.strip()})

    if not target_platforms:
        raise HTTPException(status_code=400, detail="No connected platform account IDs found.")

    body = {
        "profileId": "6a1350634beb548c15895d64",
        "content": payload.caption,
        "platforms": target_platforms
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(zernio_publish_url, json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
