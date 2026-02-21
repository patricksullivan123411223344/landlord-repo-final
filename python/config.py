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
    socrata_app_token: str | None = os.getenv("SOCRATA_APP_TOKEN")

settings = Settings()

