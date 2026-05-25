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
async def generate_draft(file: UploadFile = File(...), custom_prompt: str = Form(None)):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Backend missing GEMINI_API_KEY environment variable.")

    try:
        file_content = await file.read()
        base64_image = base64.b64encode(file_content).decode("utf-8")
        
        google_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        
        headers = {"Content-Type": "application/json"}
        
        # 🚀 FIXED: System prompt injection with mandatory execution layout rules
        system_rules = "CRITICAL: Output ONLY the requested caption options. Do not include intro text, conversational filler, markdown formatting wrappers, or headers."
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
    
    # 🚀 FIXED: Structured correctly as an explicit account array payload for Zernio's channel parser
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
