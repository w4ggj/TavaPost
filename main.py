# TavaPost Studio Backend API Node // Ver 1.1.1
import os
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai  # 🚀 FIXED: Matches your exact library dependency

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

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaPost Engine"}

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

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
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Backend missing GEMINI_API_KEY environment variable.")

    try:
        # Configure the legacy generativeai engine parameters cleanly
        genai.configure(api_key=gemini_key)
        
        file_content = await file.read()
        
        # Format image blob structure for legacy library multi-modal execution
        image_part = {
            "mime_type": file.content_type,
            "data": file_content
        }
        
        prompt = """
        Analyze this image and provide 3 distinct social media caption variations optimized for Facebook and Instagram. 
        Separate them explicitly using 'Variation 1.', 'Variation 2.', and 'Variation 3.' labels.
        Keep the voice engaging, relevant to the scene, and clean.
        """

        # Call Gemini 1.5 Flash using your active requirements engine core
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image_part])

        return {
            "image_url": "https://studio.tavaone.com/placeholder.jpg",
            "draft_text": response.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Engine Fault: {str(e)}")

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
    
    body = {
        "content": payload.caption,
        "platforms": [
            {"platform": "facebook", "accountId": "6a1350634beb548c15895d64"},
            {"platform": "instagram", "accountId": "6a1350634beb548c15895d64"}
        ]
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(zernio_publish_url, json=body, headers=headers)
            if response.status_code in [200, 201]:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "code": response.status_code, "detail": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))# TavaPost Studio Backend API Node // Ver 1.1.1
import os
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai  # 🚀 FIXED: Matches your exact library dependency

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

@app.get("/")
async def root_check():
    return {"status": "online", "service": "TavaPost Engine"}

@app.get("/api/get-connect-url")
async def get_connect_url(platform: str, profile_id: str = None):
    zernio_key = os.environ.get("ZERNIO_API_KEY")
    if not zernio_key:
        raise HTTPException(status_code=500, detail="Missing ZERNIO_API_KEY config.")

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
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Backend missing GEMINI_API_KEY environment variable.")

    try:
        # Configure the legacy generativeai engine parameters cleanly
        genai.configure(api_key=gemini_key)
        
        file_content = await file.read()
        
        # Format image blob structure for legacy library multi-modal execution
        image_part = {
            "mime_type": file.content_type,
            "data": file_content
        }
        
        prompt = """
        Analyze this image and provide 3 distinct social media caption variations optimized for Facebook and Instagram. 
        Separate them explicitly using 'Variation 1.', 'Variation 2.', and 'Variation 3.' labels.
        Keep the voice engaging, relevant to the scene, and clean.
        """

        # Call Gemini 1.5 Flash using your active requirements engine core
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image_part])

        return {
            "image_url": "https://studio.tavaone.com/placeholder.jpg",
            "draft_text": response.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Engine Fault: {str(e)}")

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
    
    body = {
        "content": payload.caption,
        "platforms": [
            {"platform": "facebook", "accountId": "6a1350634beb548c15895d64"},
            {"platform": "instagram", "accountId": "6a1350634beb548c15895d64"}
        ]
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
