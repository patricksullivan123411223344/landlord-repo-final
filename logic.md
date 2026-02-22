# Tenant Shield Logic Overview

## What the system does

Tenant Shield runs as a two-layer web app:

- `node/server.js` serves the website pages/assets and proxies API requests to Python.
- `python/main.py` serves the backend APIs (including Gemini chat + RAG knowledge lookup).

This lets the frontend use one web origin (Node gateway) while Python handles the app logic.

## Request Flow (High Level)

1. Browser loads pages from Node (`/`, `/rating`, `/fair-rent`).
2. Frontend JS sends API calls to Node (for example `POST /api/rating-chat`).
3. Node proxies matching API paths to the Python backend (`PYTHON_BACKEND_URL`, default `http://127.0.0.1:8000`).
4. Python processes the request, may call Gemini and local RAG knowledge, then returns JSON.
5. Node returns that backend response to the browser.

## Node Gateway (`node/server.js`)

### Responsibilities

- Loads environment variables from the root `.env` using `dotenv`.
- Serves static files:
  - `/css/*`
  - `/js/*`
- Serves HTML pages:
  - `/` -> `index.html`
  - `/rating` -> `html/ratingPage.html`
  - `/fair-rent` -> `html/ri-fair-rent.html`
  - `/fair-rent/manage` -> `html/admin.html` (with `noindex`)
- Proxies backend/API routes to Python:
  - `/api/*`
  - `/analyze`
  - `/zips`
  - `/health`
  - `/robots.txt`

### Important proxy behavior

The proxy is configured with `pathFilter` and mounted with `app.use(apiProxy)` so the original path is preserved.

This is important because Python expects exact paths like:

- `/api/rating-chat`
- `/health`

If the proxy strips the mount path, Python will receive the wrong route and return `404`.

## Python Config (`python/config.py`)

### dotenv usage

Python explicitly loads the repo-root `.env` file:

- `load_dotenv(dotenv_path=ENV_PATH)`

This avoids issues where startup working directory changes.

### Settings object

`Settings` centralizes env-based config, including:

- `GEMINI_API_KEY`
- `GEMINI_MODEL` (defaults to `gemini-1.5-flash` if unset)
- `RAG_KNOWLEDGE_DIR`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- other APIs (Census/Zillow legacy config)

Values are normalized by `_clean_env()` so quoted values in `.env` still parse correctly.

## Python Backend (`python/main.py`)

### Main responsibilities

- Serves pages (same routes as Node if Python is run directly)
- Exposes health/config diagnostics
- Legacy rent analysis endpoints
- Gemini-backed Q&A endpoints
- RAG-based tenant guidance chat endpoint

### Key endpoints

- `GET /health`
  - Returns status + config flags (Gemini configured, model name, Supabase configured, etc.)
- `GET /api/board-config`
  - Returns Supabase URL + anon key for frontend board auth/client init
- `POST /analyze`
  - Legacy fair-rent analysis flow
- `POST /api/ai-answer`
  - Single-turn Gemini Q&A
- `POST /api/rating-chat`
  - Multi-turn chat endpoint for the new rating/chat UI

## Rating Chat Logic (`POST /api/rating-chat`)

### Input

Request body:

- `message`: current user message
- `history`: prior chat turns (`role`, `content`)

### Processing pipeline

1. Validate Gemini key exists (`GEMINI_API_KEY`).
2. Validate message is not empty.
3. Search local RAG knowledge docs (`python/rag/knowledge/*.md|*.txt`) using token overlap scoring.
4. Build formatted RAG context from top matches.
5. Fetch optional public context from Wikipedia (best-effort, fails safely).
6. Build a Tenant Shield system-style prompt with:
   - tone constraints
   - legal-information disclaimer requirement
   - RAG context
   - public context
   - user message
7. Convert prior chat history into Gemini `contents` format (`user` / `model` roles).
8. Call Gemini `generateContent` using the configured model (`GEMINI_MODEL`, e.g. `gemini-2.5-flash`).
9. Extract text from Gemini response.
10. Return:
   - `answer`
   - `sources` (RAG file names + optional public source URL)
   - `context` flags (`rag_used`, `public_used`)

### Failure behavior

The endpoint returns graceful JSON fallbacks if:

- Gemini key is missing
- Gemini API returns an error
- public context fetch fails
- model response is malformed

## RAG Knowledge Logic (`python/services/rag_knowledge.py`)

### How retrieval works (simple local retrieval)

- Reads `.md` and `.txt` files from `RAG_KNOWLEDGE_DIR`
- Splits documents into paragraph-like chunks
- Tokenizes query + chunks (basic regex tokenization)
- Scores chunks by token overlap ratio
- Returns top matches (`top_k`, default 4)
- Formats matched chunks into a bounded context string for Gemini

### Current knowledge sources (examples)

- `python/rag/knowledge/ri_security_deposit.md`
- `python/rag/knowledge/ri_repairs_habitability.md`
- `python/rag/knowledge/knowledge_base.md`

## Startup / Runtime Notes

### Python (backend)

Run Python backend (direct):

```bash
uvicorn python.main:app --reload --port 8000
```

If using Windows Git Bash and a virtualenv, use the correct path format (for example):

```bash
./.venv/Scripts/python.exe -m uvicorn python.main:app --reload --port 8000
```

### Node (gateway)

Run Node gateway:

```bash
npm start
```

By default it serves on `http://127.0.0.1:3000` and proxies to Python at `http://127.0.0.1:8000`.

## What is currently under development

- Gemini prompting and response quality tuning
- Broader API integrations (some legacy endpoints still exist)
- RAG knowledgebase expansion and stronger retrieval quality
- Frontend chat UX polish and source rendering improvements

