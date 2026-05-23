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
async def generate_draft(file: UploadFile = File(...), user = Depends(get_current_user)):
    try:
        profile_response = supabase.table("user_profiles").select("gemini_prompt_instructions").eq("id", user.id).execute()
        
        instructions = "Write an engaging social media post for this image."
        if profile_response.data and profile_response.data[0].get("gemini_prompt_instructions"):
            instructions = profile_response.data[0]["gemini_prompt_instructions"]

        image_bytes = await file.read()
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([
            instructions, 
            {"mime_type": file.content_type, "data": image_bytes}
        ])

        return {"draft_text": response.text, "status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")

@app.post("/approve-and-post")
async def approve_post(data: dict, user = Depends(get_current_user)):
    return {"status": "success", "message": "Post approved! (Publishing logic coming soon)"}