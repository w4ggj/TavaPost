# TavaPost Studio Backend API Node // Ver 1.0.3
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="TavaPost Backend")

# Core CORS setup to allow multi-device requests cleanly
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
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(
            status_code=500,
            detail="Backend configuration missing ZERNIO_API_KEY environment variable."
        )

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    
    # 1. This is the endpoint our backend will quietly call 
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId=6a1350634beb548c15895d64&redirect_url=https://studio.tavaone.com/index.html"
    
    headers = {
        "Authorization": f"Bearer {clean_key}"
    }

    # 2. 🚀 The Backend makes the secure call to Zernio using your key
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 🚀 Everything inside here must be indented 4 extra spaces!
            response = await client.post(
                "https://zernio.com/api/v1/publish", # Swap this with your actual target variable if needed
                json=body, 
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "code": response.status_code, "detail": response.text}
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/publish-post")
async def publish_post(payload: PostRequest):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing API token environment config.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
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
