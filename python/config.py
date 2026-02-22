"""
config.py
Loads .env credentials and exposes Settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    census_api_key: str | None = os.getenv("CENSUS_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    zillow_api_key: str | None = os.getenv("ZILLOW_API_KEY")
    zillow_rapidapi_key: str | None = os.getenv("ZILLOW_RAPIDAPI_KEY")
    zillow_data_dir: str = os.getenv("ZILLOW_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_anon_key: str | None = os.getenv("SUPABASE_ANON_KEY")


settings = Settings()

