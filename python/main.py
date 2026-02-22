"""
main.py

What this does:
1) Serves frontend files
2) Exposes API:
 - GET /health
 - GET /zips
 - POST /analyze

Secrets:
- CENSUS_API_KEY in .env for Census Bureau API (ACS housing data)
"""

import os
import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from python.config import settings

# ---- Service Imports ----
from python.services.fair_rent import (
    estimate_fair_rent,
    get_price_flag,
    get_nearby_comparison,
    list_zips,
)
from python.services.openpvd import lookup_owner_openpvd
from python.services.landlord_score import build_landlord_profile
from python.services.census import get_acs_rent_by_zip


# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # landlord-rating-final/
HTML_DIR = os.path.join(BASE_DIR, "html")

# ---- App ----
app = FastAPI(title="Landlord Rating")

# ---- Frontend Routes (defined before mounts so they take precedence) ----
@app.get("/")
def home():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/rating")
def rating_page():
    return FileResponse(os.path.join(HTML_DIR, "ratingPage.html"))


@app.get("/fair-rent")
def fair_rent_page():
    return FileResponse(os.path.join(HTML_DIR, "ri-fair-rent.html"))


@app.get("/fair-rent/manage")
def admin_page():
    """Hidden admin panel. Not linked from main site. Add noindex header."""
    response = FileResponse(os.path.join(HTML_DIR, "admin.html"))
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


# ---- Health ----
@app.get("/health")
def health():
    return {
        "status": "ok",
        "config": {
            "gemini_configured": bool(settings.gemini_api_key),
            "gemini_model": settings.gemini_model,
            "census_configured": bool(settings.census_api_key),
            "supabase_configured": bool(settings.supabase_url and settings.supabase_anon_key),
        },
    }


@app.get("/robots.txt")
def robots():
    """Exclude hidden admin path from crawlers."""
    return PlainTextResponse("User-agent: *\nDisallow: /fair-rent/manage\n")


# ---- Board Config (Supabase for Tenant Board forum) ----
@app.get("/api/board-config")
def board_config():
    """Public config for Tenant Board frontend (Supabase client init)."""
    return {
        "supabaseUrl": settings.supabase_url or "",
        "supabaseAnonKey": settings.supabase_anon_key or "",
    }


# ---- API Models ----
class AnalyzeRequest(BaseModel):
    address: str
    zip_code: str
    bedrooms: str          # "studio", "1", "2", "3"
    asking_rent: float
    amenities: Optional[List[str]] = []
    sqft: Optional[int] = None


# ---- API Routes ----
@app.get("/zips")
def zips():
    return list_zips()


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    # Fair rent
    rent = estimate_fair_rent(
        req.zip_code,
        req.bedrooms,
        req.amenities,
        req.sqft
    )

    # Pricing flag
    flag = get_price_flag(req.asking_rent, rent["fair_rent_mid"])

    # Nearby comparison
    nearby = get_nearby_comparison(
        req.zip_code,
        req.bedrooms,
        req.amenities
    )

    # Landlord lookup (Providence Open Data)
    owner = lookup_owner_openpvd(req.address)
    landlord = build_landlord_profile(owner_name=owner)

    # Census ACS housing data by ZIP (uses CENSUS_API_KEY)
    census_rent = get_acs_rent_by_zip(req.zip_code)

    return {
        "rent_estimate": rent,
        "asking_rent": req.asking_rent,
        "flag": flag,
        "landlord": landlord,
        "nearby_zips": nearby,
        "census_acs": census_rent,
    }


# ---- AI Answer (RI landlord-tenant law) ----
class AIAnswerRequest(BaseModel):
    title: str
    body: str = ""
    topic: str = "Other"


def _build_ai_prompt(req: AIAnswerRequest) -> str:
    return f"""
You are a legal information assistant for Rhode Island renters.
Provide concise, practical guidance with clear next steps.
Do not claim to be a lawyer, and include a brief disclaimer.
If relevant, mention RI landlord-tenant law concepts and suggest documentation steps.

Topic: {req.topic}
Question: {req.title}
Details: {req.body or "No additional details provided."}
""".strip()


def _extract_gemini_text(data: dict) -> str | None:
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    chunks = [p.get("text", "").strip() for p in parts if p.get("text")]
    text = "\n".join([c for c in chunks if c])
    return text or None


@app.post("/api/ai-answer")
async def ai_answer(req: AIAnswerRequest):
    """RI landlord-tenant Q&A via Gemini."""
    if not settings.gemini_api_key:
        return {"answer": "AI is not configured. Add GEMINI_API_KEY to .env and restart the server."}

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_ai_prompt(req)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 700,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                params={"key": settings.gemini_api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code >= 400:
            return {"answer": "AI is temporarily unavailable. Please try again shortly."}

        data = resp.json()
        text = _extract_gemini_text(data)
        if not text:
            return {"answer": "AI could not generate an answer for this question."}
        return {"answer": text}
    except Exception:
        return {"answer": "AI is temporarily unavailable. Please try again shortly."}


# ---- Static Mounts (after routes so API/HTML routes take precedence) ----
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
