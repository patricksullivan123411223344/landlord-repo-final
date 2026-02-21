import os
import csv
from typing import Dict, Optional

PY_DIR = os.path.dirname(os.path.dirname(__file__))
ZILLOW_DIR = os.path.join(PY_DIR, "data", "zillow")


def _find_ri_csv() -> Optional[str]:
    if not os.path.isdir(ZILLOW_DIR):
        return None
    for name in os.listdir(ZILLOW_DIR):
        if name.endswith('.RI.csv') and name.lower().startswith('metro'):
            return os.path.join(ZILLOW_DIR, name)
    # fallback: any .RI.csv
    for name in os.listdir(ZILLOW_DIR):
        if name.endswith('.RI.csv'):
            return os.path.join(ZILLOW_DIR, name)
    return None


def load_metro_latest() -> Dict[str, float]:
    """Return mapping RegionName -> latest numeric value from the Zillow metro CSV (RI filtered)."""
    path = _find_ri_csv()
    out: Dict[str, float] = {}
    if not path:
        return out

    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return out
        # date columns are all except the known metadata columns
        meta_cols = {'RegionID', 'SizeRank', 'RegionName', 'RegionType', 'StateName', 'State'}
        date_cols = [c for c in reader.fieldnames if c not in meta_cols]

        for row in reader:
            name = row.get('RegionName') or row.get('Region')
            if not name:
                continue
            # pick the last non-empty date value from date_cols
            latest = None
            for col in reversed(date_cols):
                v = (row.get(col) or '').strip()
                if v not in ('', 'NA', 'nan'):
                    try:
                        latest = float(v)
                        break
                    except ValueError:
                        continue
            if latest is not None:
                out[name] = latest

    return out


_CACHE: Optional[Dict[str, float]] = None


def get_metro_latest(region_search: str) -> Optional[float]:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_metro_latest()
    # simple substring match (case-insensitive)
    for name, val in _CACHE.items():
        if region_search.lower() in name.lower():
            return val
    return None


def _find_zillow_files(containing: str) -> list[str]:
    if not os.path.isdir(ZILLOW_DIR):
        return []
    out = []
    for name in os.listdir(ZILLOW_DIR):
        if containing.lower() in name.lower():
            out.append(os.path.join(ZILLOW_DIR, name))
    return out


def load_national_zori_latest() -> Optional[float]:
    """Load national ZORI/ZORF growth numeric latest value if present."""
    # look for zorf/zori files
    candidates = _find_zillow_files('zorf') + _find_zillow_files('zori') + _find_zillow_files('zorf_growth')
    if not candidates:
        return None
    # prefer national file
    for path in candidates:
        # open and look for a national row
        try:
            with open(path, newline='', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    continue
                meta_cols = {'RegionID', 'SizeRank', 'RegionName', 'RegionType', 'StateName', 'State'}
                date_cols = [c for c in reader.fieldnames if c not in meta_cols]
                for row in reader:
                    rn = (row.get('RegionName') or row.get('Region') or '').strip().lower()
                    if 'united' in rn or 'national' in rn or 'usa' in rn or 'national' in path.lower():
                        # pick last non-empty date column
                        for col in reversed(date_cols):
                            v = (row.get(col) or '').strip()
                            if v not in ('', 'NA', 'nan'):
                                try:
                                    return float(v)
                                except ValueError:
                                    continue
        except Exception:
            continue
    # fallback: try first candidate and return its last numeric
    for path in candidates:
        try:
            with open(path, newline='', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    continue
                meta_cols = {'RegionID', 'SizeRank', 'RegionName', 'RegionType', 'StateName', 'State'}
                date_cols = [c for c in reader.fieldnames if c not in meta_cols]
                for row in reader:
                    for col in reversed(date_cols):
                        v = (row.get(col) or '').strip()
                        if v not in ('', 'NA', 'nan'):
                            try:
                                return float(v)
                            except ValueError:
                                continue
        except Exception:
            continue
    return None

