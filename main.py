# TavaPost Studio Backend API Node // Ver 1.0.4
import os
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(
            status_code=500,
            detail="Backend configuration missing ZERNIO_API_KEY environment variable."
        )

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    zernio_endpoint = f"https://zernio.com/api/v1/connect/{platform}?profileId=6a1350634beb548c15895d64&redirect_url=https://studio.tavaone.com/index.html"
    
    headers = {"Authorization": f"Bearer {clean_key}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(zernio_endpoint, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-draft")
async def generate_draft(file: UploadFile = File(...)):
    # 🚀 FIXED: Put the missing draft endpoint back on the map!
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Backend configuration missing ZERNIO_API_KEY.")

    clean_key = zernio_key.strip().replace("'", "").replace('"', "")
    zernio_draft_url = "https://zernio.com/api/v1/publish" # Update this string if Zernio uses a different split draft endpoint URL

    headers = {
        "Authorization": f"Bearer {clean_key}"
    }

    # Prepare file payload binary stream for image transfer block routing
    file_content = await file.read()
    files = {"file": (file.filename, file_content, file.content_type)}

    # 60-second breathing room timeout context allocation
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # We send a background POST request to the engine node layout map
            response = await client.post(zernio_draft_url, files=files, headers=headers)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
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
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(zernio_publish_url, json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
