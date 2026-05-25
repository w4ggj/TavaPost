# TavaPost Studio Backend API Node // Ver 1.0.2
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="TavaPost Backend")

# Initialize robust cross-origin resource rules for secure domain mapping
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

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaPost Engine"}

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profile_id: str):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(
            status_code=500,
            detail="Backend configuration missing ZERNIO_API_KEY environment variable."
        )

    try:
        # Hardwired verified 24-character Zernio profile identifier 
        zernio_profile_id = "6a1350634beb548c15895d64"

        # 🚀 THE FIX: We build the URL and let FastAPI handle a clean browser redirection
        zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId={zernio_profile_id}&redirect_url=https://studio.tavaone.com/index.html"
        
        return RedirectResponse(url=zernio_endpoint)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing API token environment config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    
    # Broadcast content pipeline destination endpoint
    zernio_publish_url = "https://zernio.com/api/v1/publish"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "profileId": "6a1350634beb548c15895d64",
        "imageUrl": payload.image_url,
        "caption": payload.caption
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(zernio_publish_url, json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
