# TavaPost Studio Backend API Node // Ver 1.5.0
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

# ... Keep your existing imports and app configuration unchanged ...

class PostRequest(BaseModel):
    image_url: str
    caption: str
    fb_account_id: str = None  # 🚀 NEW: Expects your live database channel tokens
    ig_account_id: str = None  # 🚀 NEW: Expects your live database channel tokens

# ... Keep root_check, get_connect_url, and generate_draft exactly as they are ...

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
    
    # Rebuild the platform routing list dynamically based on what accounts the user has linked
    target_platforms = []
    
    if payload.fb_account_id and payload.fb_account_id.strip():
        target_platforms.append({
            "platform": "facebook",
            "accountId": payload.fb_account_id.strip()  # 🚀 FIXED: Maps the actual validation parameter path
        })
        
    if payload.ig_account_id and payload.ig_account_id.strip():
        target_platforms.append({
            "platform": "instagram",
            "accountId": payload.ig_account_id.strip()  # 🚀 FIXED: Maps the actual validation parameter path
        })

    # Fallback default safety constraint if database hooks pull blanks
    if not target_platforms:
        raise HTTPException(status_code=400, detail="No active linked social media channel account tokens provided.")

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
            else:
                print(f"!!! ZERNIO PUBLISH REJECTION: {response.status_code} - {response.text} !!!")
                return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
