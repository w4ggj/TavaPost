# TavaPost Studio Backend API Node // Ver 1.1.2
import os
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai  # Matches your active requirements file library

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
        file_content = await file.read()
        import base64
        base64_image = base64.b64encode(file_content).decode("utf-8")
        
        # 🚀 FIXED: Pointing the direct network route to the stable Gemini 2.5 Flash engine
        google_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        prompt = """
        Analyze this image and provide 3 distinct social media caption variations optimized for Facebook and Instagram. 
        Separate them explicitly using 'Variation 1.', 'Variation 2.', and 'Variation 3.' labels.
        Keep the voice engaging, relevant to the scene, and clean.
        """

        body = {
            "contents": [{
                "parts": [
                    {"text": prompt},
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
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Google API Rejected Request: {response.text}"
                )
            
            data = response.json()
            
            try:
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                raise HTTPException(status_code=500, detail="Unexpected JSON format received from Google API.")

            return {
                "image_url": "https://studio.tavaone.com/placeholder.jpg",
                "draft_text": raw_text
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Fetch Fault: {str(e)}")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Google API Rejected Request: {response.text}"
                )
            
            data = response.json()
            
            # Extract the generated text cleanly from Google's native JSON tree
            try:
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                raise HTTPException(status_code=500, detail="Unexpected JSON format received from Google API.")

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
