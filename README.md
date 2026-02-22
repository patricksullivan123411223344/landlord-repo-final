# Tenant Shield

Tenant Shield is a Providence-focused renter intelligence web app.

It combines:
- Rent analysis (`/rating`) from HUD SAFMR + Census + local Zillow CSV signals.
- A community tenant board (`/fair-rent`) with Supabase-backed posts, replies, and votes.
- AI-assisted tenant Q&A via Gemini (currently integrated but still under active refinement).

## Current Product Behavior

### 1. Get Rating (no login required)
- Route: `/rating`
- Input: address, ZIP, bedroom count, asking rent
- Backend endpoint: `POST /analyze`
- Returns:
  - Fair rent estimate (`low/mid/high`)
  - Pricing flag (at market / above market / etc.)
  - Nearby ZIP comparisons
  - Landlord profile lookup (OpenPVD)
  - Census rent signal
  - Zillow signal block from local CSV datasets

### 2. Tenant Board (login required)
- Route: `/fair-rent`
- Auth gate is enforced for board usage.
- Supabase persists:
  - `posts`
  - `replies`
  - `votes`
- Admin route: `/fair-rent/manage` (hidden, noindex)

### 3. AI Q&A
- Endpoint: `POST /api/ai-answer`
- Gemini API call is wired using `GEMINI_API_KEY` and `GEMINI_MODEL`.
- Current status: under development and being hardened for reliability, response quality, and legal-safe prompting.

## Zillow Data Source (CSV-first)

Zillow is currently sourced from local CSV files in `python/data` (not Zillow API).

Datasets currently used:
- `python/data/Metro_zordi_uc_sfrcondomfr_month.csv`
  - Metro-level observed rent signal (used for Providence metro trend/value)
- `python/data/National_zorf_growth_uc_sfr_sm_month.csv`
  - National forecast growth signal (used as adjustment input)

Loader:
- `python/services/zillow_loader.py`

Visualization script:
- `python/scripts/download_zillow.py`
- Generates PNG charts to: `python/data/visualizations/zillow/`

## Tech Stack

- Backend: FastAPI
- Frontend: static HTML/CSS/JS
- Auth/Forum DB: Supabase
- AI: Gemini (Google Generative Language API)
- Data sources:
  - HUD SAFMR (`python/data/safmr.json`)
  - US Census ACS API
  - Providence Open Data
  - Local Zillow CSV datasets

## Environment Variables

Set in `.env` (see `.env.example`):

- `CENSUS_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default `gemini-1.5-flash`)
- `ZILLOW_DATA_DIR` (default `python/data`)
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

Notes:
- dotenv is loaded explicitly from the project root in `python/config.py`.
- Values are normalized for surrounding quotes/whitespace.

## Run Locally

1. Create and populate `.env` from `.env.example`
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Node gateway dependencies:

```bash
npm install
```

4. Run Python backend (logic + Gemini + RAG):

```bash
uvicorn python.main:app --reload
```

5. Run Node gateway (frontend + API bridge):

```bash
npm start
```

6. Open:
- Home: `http://127.0.0.1:8000/`
- Rating: `http://127.0.0.1:8000/rating`
- Tenant Board: `http://127.0.0.1:8000/fair-rent`

If using the Node gateway, use:
- Home: `http://127.0.0.1:3000/`
- Rating: `http://127.0.0.1:3000/rating`
- Tenant Board: `http://127.0.0.1:3000/fair-rent`

## API Summary

- `GET /health`
  - Includes basic config status flags (`gemini_configured`, `census_configured`, `supabase_configured`)
- `GET /zips`
- `POST /analyze`
- `POST /api/ai-answer`
- `GET /api/board-config`

## What Is Being Fixed / Implemented Next

### In progress
- Gemini response reliability improvements:
  - Better error handling and retries
  - Prompt refinement for RI-specific tenant guidance quality
  - Safer legal-language boundaries and citation strategy
- AI observability:
  - Better logging around model failures/timeouts
  - Clearer fallback responses in UI

### Planned next
- Surface Zillow chart visualizations in UI (not just generated files)
- Add tests for `/analyze` payload parsing and response schema stability
- Add structured moderation capabilities for `/fair-rent/manage`
- Improve typed contracts between backend responses and frontend renderers

## Repo Notes

- `.env` is gitignored.
- `python/data/zillow/` is gitignored from earlier pipeline; current Zillow CSVs are under `python/data`.
- Supabase migration/setup details are documented in `supabase/README.md`.
