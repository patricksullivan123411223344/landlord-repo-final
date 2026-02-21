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
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

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
    return {"status": "ok"}


@app.get("/robots.txt")
def robots():
    """Exclude hidden admin path from crawlers."""
    return PlainTextResponse("User-agent: *\nDisallow: /fair-rent/manage\n")


# ---- Board Config (Supabase for Tenant Board forum) ----
@app.get("/api/board-config")
def board_config():
    """Public config for Tenant Board frontend (Supabase client init)."""
    from python.config import settings
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


@app.post("/api/ai-answer")
async def ai_answer(req: AIAnswerRequest):
    """Placeholder for RI landlord-tenant law Q&A. AI requires separate configuration."""
    return {"answer": "AI is not configured. Add GEMINI_API_KEY or another AI provider to .env."}


# ---- Static Mounts (after routes so API/HTML routes take precedence) ----
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")