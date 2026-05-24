import uuid
import os
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TavaPost API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token = authorization.split(" ")[1]
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Unauthorized: Please log in again.")
    return user_response.user

@app.post("/generate-draft")
async def generate_draft(file: UploadFile = File(...), authorization: str = Header(None)):
    # 1. Security Check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split(" ")[1]
    user_res = supabase.auth.get_user(token)
    if not user_res or not user_res.user:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    user_id = user_res.user.id
    
    try:
        # 2. Upload Image to Supabase Storage
        file_bytes = await file.read()
        file_ext = file.filename.split('.')[-1]
        unique_filename = f"{user_id}_{uuid.uuid4().hex}.{file_ext}"
        
        supabase.storage.from_("tavapost-images").upload(
            path=unique_filename,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )
        
        # 3. Get the Public URL for Zapier
        image_url = supabase.storage.from_("tavapost-images").get_public_url(unique_filename)
        
        # 4. Fetch Your Custom Instructions
        settings = supabase.table("user_settings").select("custom_prompt").eq("user_id", user_id).execute()
        
        if settings.data and settings.data[0].get('custom_prompt'):
            custom_prompt = settings.data[0]['custom_prompt']
        else:
            custom_prompt = "Write a standard social media caption for this image."
        
        # 5. Ask Gemini for 3 Options
        image_parts = [{"mime_type": file.content_type, "data": file_bytes}]
        prompt_text = f"{custom_prompt}\n\nPlease generate exactly 3 distinct caption options based on these instructions. Format the output as a numbered list (1, 2, 3) so I can easily choose one."
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([prompt_text, image_parts[0]])
        
        # 6. Send the text AND the new image link back to the website
        return {
            "draft_text": response.text,
            "image_url": image_url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
