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
import time
import threading
from collections import defaultdict, deque
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
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

# ---- AI Guardrails / Rate Limits ---------------------------------------------
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = threading.Lock()

AI_ANSWER_LIMIT = (12, 300)      # 12 requests / 5 minutes per IP
RATING_CHAT_LIMIT = (18, 300)    # 18 requests / 5 minutes per IP
MAX_AI_TITLE_CHARS = 400
MAX_AI_BODY_CHARS = 3000
MAX_CHAT_MESSAGE_CHARS = 3500
MAX_CHAT_HISTORY_TURNS = 10
MAX_CHAT_TURN_CHARS = 1800
MAX_CHAT_TOTAL_CHARS = 12000


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return (request.client.host if request.client else "unknown").strip() or "unknown"


def _allow_rate_limit(request: Request, bucket: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    now = time.time()
    key = f"{bucket}:{_client_ip(request)}"
    with _RATE_LIMIT_LOCK:
        q = _RATE_LIMIT_BUCKETS[key]
        while q and (now - q[0]) > window_seconds:
            q.popleft()
        if len(q) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - q[0])))
            return False, retry_after
        q.append(now)
    return True, 0


def _rate_limit_error(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "answer": "Too many AI requests right now. Please wait a minute and try again.",
            "sources": [],
            "retry_after_seconds": retry_after,
        },
    )


def _trim_text(value: str, max_chars: int) -> str:
    return (value or "").strip()[:max_chars]


def _validate_chat_request(req: "RatingChatRequest") -> str | None:
    message = (req.message or "").strip()
    if not message:
        return "Please enter a message."
    if len(message) > MAX_CHAT_MESSAGE_CHARS:
        return f"Message is too long. Please keep it under {MAX_CHAT_MESSAGE_CHARS} characters."

    turns = req.history or []
    if len(turns) > MAX_CHAT_HISTORY_TURNS:
        return f"Chat history is too long. Please start a new chat after {MAX_CHAT_HISTORY_TURNS} turns."

    total_chars = len(message)
    for turn in turns:
        role = (turn.role or "").lower().strip()
        if role not in {"user", "assistant"}:
            return "Invalid chat history format."
        total_chars += len((turn.content or "").strip())
        if len((turn.content or "")) > MAX_CHAT_TURN_CHARS:
            return f"One of the prior messages is too long. Keep each message under {MAX_CHAT_TURN_CHARS} characters."
    if total_chars > MAX_CHAT_TOTAL_CHARS:
        return "Conversation is too long for one request. Start a new chat or shorten earlier messages."
    return None

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
        text = _trim_text(turn.content or "", MAX_CHAT_TURN_CHARS)
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_prompt}]})
    return contents


@app.post("/api/ai-answer")
async def ai_answer(req: AIAnswerRequest, request: Request):
    """RI landlord-tenant Q&A via Gemini."""
    allowed, retry_after = _allow_rate_limit(request, "ai_answer", *AI_ANSWER_LIMIT)
    if not allowed:
        return _rate_limit_error(retry_after)

    if not settings.gemini_api_key:
        return {"answer": "AI is not configured. Add GEMINI_API_KEY to .env and restart the server."}

    if len((req.title or "").strip()) > MAX_AI_TITLE_CHARS:
        return {"answer": f"Question title is too long. Please keep it under {MAX_AI_TITLE_CHARS} characters."}
    if len((req.body or "").strip()) > MAX_AI_BODY_CHARS:
        return {"answer": f"Question details are too long. Please keep them under {MAX_AI_BODY_CHARS} characters."}

    req = AIAnswerRequest(
        title=_trim_text(req.title, MAX_AI_TITLE_CHARS),
        body=_trim_text(req.body, MAX_AI_BODY_CHARS),
        topic=_trim_text(req.topic or "Other", 60) or "Other",
    )

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
            "maxOutputTokens": 650,
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
async def rating_chat(req: RatingChatRequest, request: Request):
    """
    Chat endpoint for /rating UI:
    - Gemini model answer
    - Local RAG context from python/rag/knowledge
    - Optional public context from Wikipedia
    """
    allowed, retry_after = _allow_rate_limit(request, "rating_chat", *RATING_CHAT_LIMIT)
    if not allowed:
        return _rate_limit_error(retry_after)

    if not settings.gemini_api_key:
        return {
            "answer": "Chat AI is not configured. Add GEMINI_API_KEY to .env and restart the server.",
            "sources": [],
        }

    validation_error = _validate_chat_request(req)
    if validation_error:
        return {"answer": validation_error, "sources": []}

    user_message = _trim_text(req.message, MAX_CHAT_MESSAGE_CHARS)

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
            "maxOutputTokens": 750,
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
