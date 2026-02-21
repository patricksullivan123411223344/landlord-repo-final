from __future__ import annotations

import json
import os
from typing import List, Optional
from fastapi import HTTPException

# Load SAFMR from python/data/safmr.json
PY_DIR = os.path.dirname(os.path.dirname(__file__))         # .../python
DATA_PATH = os.path.join(PY_DIR, "data", "safmr.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    SAFMR = json.load(f)

# Optional Zillow metro data (RI) — provide a recent market signal if available
try:
    from python.services.zillow_loader import get_metro_latest
except Exception:
    get_metro_latest = lambda _: None
try:
    from python.services.zillow_loader import load_national_zori_latest
except Exception:
    load_national_zori_latest = lambda: None

AMENITY_ADJUSTMENTS = {
    "parking": 100,
    "in_unit_laundry": 90,
    "utilities_included": 175,
    "central_ac": 60,
    "pets_allowed": 50,
    "no_elevator": -30,
}

BEDROOM_KEY_MAP = {
    "studio": "studio",
    "1": "1br",
    "2": "2br",
    "3": "3br",
}

NEARBY_ZIPS = {
    "02903": ["02906", "02905", "02908"],
    "02906": ["02903", "02912", "02904"],
    "02912": ["02906", "02903", "02904"],
    "02908": ["02904", "02909", "02911"],
    "02909": ["02907", "02908", "02905"],
    "02907": ["02909", "02905", "02910"],
    "02904": ["02906", "02908", "02911"],
    "02905": ["02907", "02909", "02910"],
    "02910": ["02905", "02907", "02904"],
    "02911": ["02904", "02908", "02910"],
}

def list_zips():
    # SAFMR is a dict: { "02903": {...}, ... }
    return [{"zip": z, "neighborhood": v.get("neighborhood", "")} for z, v in SAFMR.items()]

def estimate_fair_rent(zip_code: str, bedrooms: str, amenities: List[str], sqft: Optional[int] = None):
    if zip_code not in SAFMR:
        raise HTTPException(status_code=404, detail=f"ZIP code {zip_code} not in Providence coverage area")

    bed_key = BEDROOM_KEY_MAP.get(bedrooms)
    if not bed_key:
        raise HTTPException(status_code=400, detail="Invalid bedroom count")

    base = SAFMR[zip_code][bed_key]
    neighborhood = SAFMR[zip_code]["neighborhood"]

    adjustments = sum(AMENITY_ADJUSTMENTS.get(a, 0) for a in amenities)

    sqft_delta = 0
    if sqft:
        median_sqft = {"studio": 450, "1br": 650, "2br": 850, "3br": 1100}[bed_key]
        sqft_delta = ((sqft - median_sqft) / median_sqft) * base * 0.10

    fair_rent = base + adjustments + sqft_delta

    result = {
        "zip_code": zip_code,
        "neighborhood": neighborhood,
        "base_safmr": base,
        "amenity_adjustments": adjustments,
        "sqft_adjustment": round(sqft_delta),
        "fair_rent_low": round(fair_rent * 0.93),
        "fair_rent_mid": round(fair_rent),
        "fair_rent_high": round(fair_rent * 1.07),
        "data_source": "HUD FY2025 Small Area Fair Market Rents",
        # Zillow metro data is metro-level (Providence); attempt to fetch by metro name
        "zillow_metro_value": get_metro_latest("Providence") if callable(get_metro_latest) else None,
        # national ZORI/ZORF growth value (if available)
        "zori_national_value": load_national_zori_latest() if callable(load_national_zori_latest) else None,
    }

    # Conservative ZORI-based adjustment: apply half of national ZORI percent to SAFMR base
    zori_val = result.get("zori_national_value")
    if isinstance(zori_val, (int, float)):
        # treat as percent change if magnitude looks like a percent
        try:
            adj_pct = float(zori_val)
            zori_adj = round(base * (adj_pct / 100.0) * 0.5)
            result["zori_adjustment"] = zori_adj
            # update mid/low/high
            result["fair_rent_mid"] = round(result["fair_rent_mid"] + zori_adj)
            result["fair_rent_low"] = round(result["fair_rent_mid"] * 0.93)
            result["fair_rent_high"] = round(result["fair_rent_mid"] * 1.07)
        except Exception:
            pass

    return result

def get_price_flag(asking_rent: float, fair_rent_mid: float):
    if fair_rent_mid == 0:
        return {"level": "unknown", "label": "Unable to estimate", "overage_pct": 0}

    overage = (asking_rent - fair_rent_mid) / fair_rent_mid
    monthly_delta = round(asking_rent - fair_rent_mid)
    annual_delta = monthly_delta * 12

    if overage > 0.50:
        label, level = "Extreme premium", "red"
    elif overage > 0.35:
        label, level = "Significantly overpriced", "red"
    elif overage > 0.20:
        label, level = "Above market", "yellow"
    elif overage > -0.10:
        label, level = "At market rate", "green"
    else:
        label, level = "Below market — good deal", "green"

    return {
        "level": level,
        "label": label,
        "overage_pct": round(overage * 100),
        "monthly_delta": monthly_delta,
        "annual_delta": annual_delta,
    }

def get_nearby_comparison(zip_code: str, bedrooms: str, amenities: List[str]):
    nearby = NEARBY_ZIPS.get(zip_code, [])
    results = []
    bed_key = BEDROOM_KEY_MAP.get(bedrooms, "2br")

    for z in nearby:
        if z in SAFMR:
            base = SAFMR[z][bed_key]
            adj = sum(AMENITY_ADJUSTMENTS.get(a, 0) for a in amenities)
            results.append({
                "zip_code": z,
                "neighborhood": SAFMR[z]["neighborhood"],
                "estimated_fair_rent": round(base + adj),
            })

    results.sort(key=lambda x: x["estimated_fair_rent"])
    return results