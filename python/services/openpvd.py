import requests 
from python.config import settings 

OPENPVD_PROPERTY_URL =  "https://data.providenceri.gov/resource/k6gu-363f.json"

def lookup_owner_openpvd(address: str) -> str | None:
    clean = address.strip()

    headers = {}
    if settings.socrata_app_token:
        headers["X-App-Tojen"] = settings.socrata_app_token

        params = {"$q": clean, "limit": 1}

        try:
             r = requests.get(OPENPVD_PROPERTY_URL, params=params, headers=headers, timeout=7)
             r.raise_for_status()
             data = r.json()
             if not data:
                return None
             return data[0].get("owner_name") or data[0].get("owner") or None
        except Exception:
            return None 