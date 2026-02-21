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


settings = Settings()

