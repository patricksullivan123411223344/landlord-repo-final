"""
config.py
Loads .env credentials and exposes Settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(ROOT_DIR, ".env")

# Always load the workspace .env explicitly so startup cwd does not matter.
load_dotenv(dotenv_path=ENV_PATH)


def _clean_env(name: str) -> str | None:
    """
    Read env var and normalize optional wrapping quotes/whitespace.
    """
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().strip('"').strip("'")


@dataclass(frozen=True)
class Settings:
    census_api_key: str | None = _clean_env("CENSUS_API_KEY")
    gemini_api_key: str | None = _clean_env("GEMINI_API_KEY")
    gemini_model: str = _clean_env("GEMINI_MODEL") or "gemini-1.5-flash"
    zillow_api_key: str | None = _clean_env("ZILLOW_API_KEY")
    zillow_rapidapi_key: str | None = _clean_env("ZILLOW_RAPIDAPI_KEY")
    zillow_data_dir: str = _clean_env("ZILLOW_DATA_DIR") or os.path.join(os.path.dirname(__file__), "data")
    rag_knowledge_dir: str = _clean_env("RAG_KNOWLEDGE_DIR") or os.path.join(os.path.dirname(__file__), "rag", "knowledge")
    supabase_url: str | None = _clean_env("SUPABASE_URL")
    supabase_anon_key: str | None = _clean_env("SUPABASE_ANON_KEY")


settings = Settings()

