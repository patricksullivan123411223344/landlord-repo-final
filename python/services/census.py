"""
census.py
Fetches housing and demographic data from the US Census Bureau API (ACS 5-year).
Uses CENSUS_API_KEY from .env for higher rate limits.
"""

import requests
from python.config import settings

CENSUS_BASE = "https://api.census.gov/data/2023/acs/acs5"
# B25031: Median gross rent by bedrooms (001=total, 002=studio, 003=1br, 004=2br, 005=3+br)
RENT_VARS = "NAME,B25031_001E,B25031_002E,B25031_003E,B25031_004E,B25031_005E"


def _build_params(zip_code: str) -> dict:
    """Build Census API query params. Key is required for >500 req/day."""
    params = {
        "get": RENT_VARS,
        "for": f"zip code tabulation area:{zip_code}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key
    return params


def get_acs_rent_by_zip(zip_code: str) -> dict | None:
    """
    Fetch ACS 5-year median gross rent by bedroom count for a ZCTA.
    Returns dict with studio, 1br, 2br, 3br, total or None on failure.
    """
    try:
        r = requests.get(
            CENSUS_BASE,
            params=_build_params(zip_code),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data or len(data) < 2:
            return None
        headers = data[0]
        values = data[1]
        row = dict(zip(headers, values))
        # Parse values; Census uses -666666666 for N/A, -222222222 for margin of error
        def _safe_int(v):
            try:
                n = int(float(v))
                return n if n > 0 else None
            except (ValueError, TypeError):
                return None

        return {
            "total": _safe_int(row.get("B25031_001E")),
            "studio": _safe_int(row.get("B25031_002E")),
            "1br": _safe_int(row.get("B25031_003E")),
            "2br": _safe_int(row.get("B25031_004E")),
            "3br": _safe_int(row.get("B25031_005E")),
            "zip_code": zip_code,
            "source": "Census ACS 5-Year",
        }
    except Exception:
        return None
