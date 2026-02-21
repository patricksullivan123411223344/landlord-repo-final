from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import requests

app = FastAPI(title="RI Fair Rent + Landlord Rating API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load static data
BASE = os.path.dirname(__file__)
with open(f"{BASE}/data/safmr.json") as f:
    SAFMR = json.load(f)
with open(f"{BASE}/data/landlord_cache.json") as f:
    LANDLORD_CACHE = json.load(f)

AMENITY_ADJUSTMENTS = {
    "parking": 100,
    "in_unit_laundry": 90,
    "utilities_included": 175,
    "central_ac": 60,
    "pets_allowed": 50,
    "no_elevator": -30
}

BEDROOM_KEY_MAP = {
    "studio": "studio",
    "1": "1br",
    "2": "2br",
    "3": "3br"
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
    "02911": ["02904", "02908", "02910"]
}


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

    return {
        "zip_code": zip_code,
        "neighborhood": neighborhood,
        "base_safmr": base,
        "amenity_adjustments": adjustments,
        "sqft_adjustment": round(sqft_delta),
        "fair_rent_low": round(fair_rent * 0.93),
        "fair_rent_mid": round(fair_rent),
        "fair_rent_high": round(fair_rent * 1.07),
        "data_source": "HUD FY2025 Small Area Fair Market Rents"
    }


def get_price_flag(asking_rent: float, fair_rent_mid: float):
    if fair_rent_mid == 0:
        return {"level": "unknown", "label": "Unable to estimate", "overage_pct": 0}

    overage = (asking_rent - fair_rent_mid) / fair_rent_mid
    monthly_delta = round(asking_rent - fair_rent_mid)
    annual_delta = monthly_delta * 12

    if overage > 0.50:
        return {"level": "red", "label": "Extreme premium", "overage_pct": round(overage * 100),
                "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    elif overage > 0.35:
        return {"level": "red", "label": "Significantly overpriced", "overage_pct": round(overage * 100),
                "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    elif overage > 0.20:
        return {"level": "yellow", "label": "Above market", "overage_pct": round(overage * 100),
                "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    elif overage > -0.10:
        return {"level": "green", "label": "At market rate", "overage_pct": round(overage * 100),
                "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    else:
        return {"level": "green", "label": "Below market — good deal", "overage_pct": round(overage * 100),
                "monthly_delta": monthly_delta, "annual_delta": annual_delta}


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
                "estimated_fair_rent": round(base + adj)
            })

    results.sort(key=lambda x: x["estimated_fair_rent"])
    return results


def score_landlord(data: dict):
    score = 100
    notes = list(data.get("notes", []))

    units = data.get("total_properties", 1)
    if units > 20:
        score -= 10
    elif units > 10:
        score -= 5

    if data.get("is_llc"):
        score -= 10

    if data.get("non_resident"):
        score -= 10

    permits = data.get("recent_permits", 0)
    year_built = data.get("year_built", 2000)

    if permits == 0:
        score -= 25
        if year_built < 1980:
            score -= 15
    elif permits < 2:
        score -= 10

    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {"score": max(0, score), "grade": grade, "notes": notes}


def lookup_landlord_openpvd(address: str):
    """
    Real OpenPVD Socrata API call for property ownership.
    Falls back to cache if API is unavailable.
    """
    try:
        clean = address.upper().strip()
        params = {
            "$where": f"upper(address) like '%{clean}%'",
            "$limit": 1
        }
        # Property dataset — confirm exact dataset ID during hackathon recon
        r = requests.get(
            "https://data.providenceri.gov/resource/k6gu-363f.json",
            params=params,
            timeout=5
        )
        if r.status_code == 200 and r.json():
            d = r.json()[0]
            owner = d.get("owner_name", "Unknown")
            return {
                "owner_name": owner,
                "is_llc": "LLC" in owner.upper() or "INC" in owner.upper(),
                "non_resident": False,  # Enrich with RI SOS lookup
                "year_built": int(d.get("year_built", 1970)),
                "total_properties": 1,
                "recent_permits": 0,
                "permit_details": [],
                "score": None,
                "grade": None,
                "notes": [],
                "source": "OpenPVD live"
            }
    except Exception:
        pass
    return None


class AnalyzeRequest(BaseModel):
    address: str
    zip_code: str
    bedrooms: str  # "studio", "1", "2", "3"
    asking_rent: float
    amenities: Optional[List[str]] = []
    sqft: Optional[int] = None


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    # 1. Fair rent estimate
    rent = estimate_fair_rent(req.zip_code, req.bedrooms, req.amenities, req.sqft)

    # 2. Price flag
    flag = get_price_flag(req.asking_rent, rent["fair_rent_mid"])

    # 3. Nearby ZIP comparison
    nearby = get_nearby_comparison(req.zip_code, req.bedrooms, req.amenities)

    # 4. Landlord lookup — cache first, then live API
    address_key = req.address.upper().strip()
    landlord_raw = None
    for key in LANDLORD_CACHE:
        if key in address_key or address_key in key:
            landlord_raw = LANDLORD_CACHE[key]
            landlord_raw["source"] = "cached"
            break

    if not landlord_raw:
        landlord_raw = lookup_landlord_openpvd(req.address)

    if landlord_raw:
        if landlord_raw.get("score") is None:
            scored = score_landlord(landlord_raw)
            landlord_raw.update(scored)
        landlord = landlord_raw
    else:
        landlord = {
            "owner_name": "Not found in public records",
            "is_llc": False,
            "non_resident": False,
            "total_properties": None,
            "recent_permits": None,
            "grade": "N/A",
            "score": None,
            "notes": ["Address not found in Providence property database"],
            "source": "not found"
        }

    return {
        "rent_estimate": rent,
        "asking_rent": req.asking_rent,
        "flag": flag,
        "landlord": landlord,
        "nearby_zips": nearby
    }


@app.get("/zips")
def list_zips():
    return [{"zip": z, "neighborhood": v["neighborhood"]} for z, v in SAFMR.items()]


@app.get("/health")
def health():
    return {"status": "ok"}
