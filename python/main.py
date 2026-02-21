"""
main.py

What this does:
1) Serves frontend files
2) Exposes API:
 - GET /health
 - GET /zips
 - POST /analyze

Secrets:
- Loaded from .env via python/config.py
- Never exposed to browser or github
"""

import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
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


# ---- Health ----
@app.get("/health")
def health():
    return {"status": "ok"}


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

    # Landlord lookup (uses Socrata token from .env internally)
    owner = lookup_owner_openpvd(req.address)
    landlord = build_landlord_profile(owner_name=owner)

    return {
        "rent_estimate": rent,
        "asking_rent": req.asking_rent,
        "flag": flag,
        "landlord": landlord,
        "nearby_zips": nearby,
    }


# ---- AI Answer (RI landlord-tenant law) ----
class AIAnswerRequest(BaseModel):
    title: str
    body: str = ""
    topic: str = "Other"


@app.post("/api/ai-answer")
async def ai_answer(req: AIAnswerRequest):
    """Proxy to Anthropic for RI landlord-tenant law Q&A."""
    from python.config import settings

    import httpx

    key = settings.anthropic_api_key
    if not key:
        return {"answer": "AI is not configured. Add ANTHROPIC_API_KEY to .env."}

    prompt = f"""You are an expert on Rhode Island landlord-tenant law (RIGL Chapter 34-18). A Providence tenant asked this question anonymously. Give a clear, practical answer citing specific RI statutes. Be direct and helpful. Max 160 words. Speak directly to the tenant.

Question: {req.title}
{f'Details: {req.body}' if req.body else ''}
Topic: {req.topic}"""

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
        if r.status_code != 200:
            return {"answer": "AI unavailable right now. Try again later."}

        data = r.json()
        text = data.get("content", [{}])[0].get("text", "Unable to generate answer.")
        return {"answer": text}
    except Exception:
        return {"answer": "AI unavailable right now. Try again later."}


# ---- Static Mounts (after routes so API/HTML routes take precedence) ----
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")