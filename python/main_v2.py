from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import requests

app = FastAPI(title="RI Fair Rent + Landlord Rating API")

# Enable CORS so the HTML frontend can communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA LOADING ---


BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "data")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_data():
    try:
        with open(os.path.join(DATA_DIR, "safmr.json")) as f:
            safmr = json.load(f)
        with open(os.path.join(DATA_DIR, "landlord_cache.json")) as f:
            cache = json.load(f)
        return safmr, cache
    except FileNotFoundError:
        return {}, {} # Or raise a structured error
def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"CRITICAL: {filename} not found in {DATA_DIR}")
        return {}

SAFMR = load_json("safmr.json")
LANDLORD_CACHE = load_json("landlord_cache.json")
# Update: Define the path to the 'data' subfolder to avoid FileNotFoundError
DATA_DIR = os.path.join(BASE, "data")

try:
    with open(os.path.join(DATA_DIR, "safmr.json")) as f:
        SAFMR = json.load(f) #
    with open(os.path.join(DATA_DIR, "landlord_cache.json")) as f:
        LANDLORD_CACHE = json.load(f) #
except FileNotFoundError as e:
    print(f"Error: Could not find data files in {DATA_DIR}. Ensure the 'data' folder exists. {e}")

# Amenity value adjustments for rent calculation
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

# Mapping for nearby ZIP codes in Providence
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

# --- LOGIC ENGINES ---

def estimate_fair_rent(zip_code: str, bedrooms: str, amenities: List[str], sqft: Optional[int] = None):
    """Calculates fair market rent based on HUD SAFMR data and amenities."""
    if zip_code not in SAFMR:
        raise HTTPException(status_code=404, detail=f"ZIP code {zip_code} not in Providence coverage area")

    bed_key = BEDROOM_KEY_MAP.get(bedrooms)
    if not bed_key:
        raise HTTPException(status_code=400, detail="Invalid bedroom count")

    base = SAFMR[zip_code][bed_key]
    neighborhood = SAFMR[zip_code]["neighborhood"]
    adjustments = sum(AMENITY_ADJUSTMENTS.get(a, 0) for a in amenities)

    # Optional adjustment based on square footage
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
    """Flags if the asking rent is above or below market rate."""
    if fair_rent_mid == 0:
        return {"level": "unknown", "label": "Unable to estimate", "overage_pct": 0}

    overage = (asking_rent - fair_rent_mid) / fair_rent_mid
    monthly_delta = round(asking_rent - fair_rent_mid)
    annual_delta = monthly_delta * 12

    if overage > 0.35:
        return {"level": "red", "label": "Significantly overpriced", "overage_pct": round(overage * 100), "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    elif overage > 0.20:
        return {"level": "yellow", "label": "Above market", "overage_pct": round(overage * 100), "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    elif overage > -0.10:
        return {"level": "green", "label": "At market rate", "overage_pct": round(overage * 100), "monthly_delta": monthly_delta, "annual_delta": annual_delta}
    else:
        return {"level": "green", "label": "Below market — good deal", "overage_pct": round(overage * 100), "monthly_delta": monthly_delta, "annual_delta": annual_delta}

def score_landlord(data: dict):
    """Calculates a letter grade (A-F) based on property history and ownership type."""
    score = 100
    notes = list(data.get("notes", []))

    if data.get("is_llc"): score -= 10
    if data.get("non_resident"): score -= 10
    
    permits = data.get("recent_permits", 0)
    if permits == 0:
        score -= 25
    elif permits < 2:
        score -= 10

    if score >= 85: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 55: grade = "C"
    elif score >= 40: grade = "D"
    else: grade = "F"

    return {"score": max(0, score), "grade": grade, "notes": notes}

# --- API ENDPOINTS ---

class AnalyzeRequest(BaseModel):
    address: str
    zip_code: str
    bedrooms: str
    asking_rent: float
    amenities: Optional[List[str]] = []
    sqft: Optional[int] = None

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    # 1. Fair rent estimate
    rent = estimate_fair_rent(req.zip_code, req.bedrooms, req.amenities, req.sqft)

    # 2. Price flag
    flag = get_price_flag(req.asking_rent, rent["fair_rent_mid"])

    # 3. Landlord lookup — cache first
    address_key = req.address.upper().strip()
    landlord = LANDLORD_CACHE.get(address_key, {
        "owner_name": "Not in cache",
        "grade": "N/A",
        "notes": ["No public permit history found in local cache"]
    })

    return {
        "rent_estimate": rent,
        "asking_rent": req.asking_rent,
        "flag": flag,
        "landlord": landlord
    }

@app.get("/health")
def health():
    return {"status": "ok"}
