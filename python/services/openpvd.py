"""
openpvd.py
Looks up property owner from Providence Open Data (Socrata).
Works without an API token for limited requests; CENSUS_API_KEY is used for Census data only.
"""

import requests

OPENPVD_PROPERTY_URL = "https://data.providenceri.gov/resource/k6gu-363f.json"


def lookup_owner_openpvd(address: str) -> str | None:
    """Look up property owner by address from Providence Open Data."""
    clean = address.strip()
    params = {"$q": clean, "limit": 1}
    try:
        r = requests.get(OPENPVD_PROPERTY_URL, params=params, timeout=7)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0].get("owner_name") or data[0].get("owner") or None
    except Exception:
        return None