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
from python.services.rag_knowledge import search_knowledge, format_knowledge_context


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


class ChatTurn(BaseModel):
    role: str
    content: str


class RatingChatRequest(BaseModel):
    message: str
    history: List[ChatTurn] = []


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


def _sanitize_history(history: List[ChatTurn], keep_last: int = 10) -> List[ChatTurn]:
    # Keep bounded history for token control and predictable latency.
    return history[-keep_last:]


async def _fetch_public_context(query: str) -> dict:
    """
    Lightweight public-web context from Wikipedia.
    Returns {} on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                },
            )
            search_resp.raise_for_status()
            data = search_resp.json()
            titles = data[1] if isinstance(data, list) and len(data) > 1 else []
            if not titles:
                return {}
            title = titles[0]
            summary_resp = await client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()
            extract = (summary.get("extract") or "").strip()
            if not extract:
                return {}
            return {
                "source": f"Wikipedia:{title}",
                "url": summary.get("content_urls", {}).get("desktop", {}).get("page"),
                "text": extract,
            }
    except Exception:
        return {}


def _build_rating_chat_prompt(user_message: str, rag_context: str, public_context_text: str) -> str:
    return f"""
You are Tenant Shield AI, a Rhode Island lease and housing guidance assistant.
Tone: protective, trustworthy, data-driven, and concise.

Rules:
- Provide practical next steps and risk flags.
- Prefer Rhode Island-specific lease/tenant guidance when available.
- If you are unsure, say what is uncertain.
- Do not claim to be a lawyer. Include a short legal-information disclaimer.

RAG Context:
{rag_context or "No relevant local knowledgebase context found."}

Public Web Context:
{public_context_text or "No public web context retrieved."}

User message:
{user_message}
""".strip()


def _build_gemini_chat_contents(history: List[ChatTurn], user_prompt: str) -> List[dict]:
    contents: List[dict] = []
    for turn in _sanitize_history(history):
        role = "model" if turn.role.lower() == "assistant" else "user"
        text = (turn.content or "").strip()
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_prompt}]})
    return contents


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


@app.post("/api/rating-chat")
async def rating_chat(req: RatingChatRequest):
    """
    Chat endpoint for /rating UI:
    - Gemini model answer
    - Local RAG context from python/rag/knowledge
    - Optional public context from Wikipedia
    """
    if not settings.gemini_api_key:
        return {
            "answer": "Chat AI is not configured. Add GEMINI_API_KEY to .env and restart the server.",
            "sources": [],
        }

    user_message = (req.message or "").strip()
    if not user_message:
        return {"answer": "Please enter a message.", "sources": []}

    rag_chunks = search_knowledge(user_message, top_k=4)
    rag_context = format_knowledge_context(rag_chunks)
    public_context = await _fetch_public_context(user_message)
    public_context_text = public_context.get("text", "")

    prompt = _build_rating_chat_prompt(
        user_message=user_message,
        rag_context=rag_context,
        public_context_text=public_context_text,
    )
    contents = _build_gemini_chat_contents(req.history, prompt)

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 900,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(
                endpoint,
                params={"key": settings.gemini_api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code >= 400:
            return {"answer": "AI is temporarily unavailable. Please try again shortly.", "sources": []}

        data = resp.json()
        text = _extract_gemini_text(data) or "I could not generate a response for that request."

        sources = []
        for ch in rag_chunks:
            sources.append({"type": "rag", "label": ch.source})
        if public_context:
            sources.append(
                {
                    "type": "public",
                    "label": public_context.get("source", "Public web"),
                    "url": public_context.get("url"),
                }
            )

        return {
            "answer": text,
            "sources": sources,
            "context": {
                "rag_used": bool(rag_chunks),
                "public_used": bool(public_context),
            },
        }
    except Exception:
        return {"answer": "AI is temporarily unavailable. Please try again shortly.", "sources": []}


# ---- Static Mounts (after routes so API/HTML routes take precedence) ----
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
