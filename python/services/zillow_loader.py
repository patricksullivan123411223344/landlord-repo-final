from __future__ import annotations

import csv
import os
from statistics import mean
from typing import Dict, Iterable, Optional

from python.config import settings

# Providence-area ZIPs used for local Zillow signal fallback.
PROVIDENCE_ZIPS = {
    "02903", "02904", "02905", "02906", "02907",
    "02908", "02909", "02910", "02911", "02912",
}

META_COLS = {
    "RegionID", "SizeRank", "RegionName", "RegionType", "StateName", "State",
}


def _iter_csv_paths() -> Iterable[str]:
    data_dir = settings.zillow_data_dir
    if not os.path.isdir(data_dir):
        return []
    return [
        os.path.join(data_dir, name)
        for name in os.listdir(data_dir)
        if name.lower().endswith(".csv")
    ]


def _find_candidates(*terms: str) -> list[str]:
    terms_lc = [t.lower() for t in terms]
    out = []
    for path in _iter_csv_paths():
        name = os.path.basename(path).lower()
        if all(t in name for t in terms_lc):
            out.append(path)
    return out


def _latest_value(row: Dict[str, str], date_cols: Iterable[str]) -> Optional[float]:
    for col in reversed(list(date_cols)):
        raw = (row.get(col) or "").strip()
        if raw in {"", "NA", "nan"}:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _read_latest_by_region(path: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return out
        date_cols = [c for c in reader.fieldnames if c not in META_COLS]
        for row in reader:
            region = (row.get("RegionName") or row.get("Region") or "").strip()
            if not region:
                continue
            latest = _latest_value(row, date_cols)
            if latest is not None:
                out[region] = latest
    return out


def get_metro_latest(region_search: str) -> Optional[float]:
    """Return latest metro-level value for a region (e.g. Providence) if available."""
    candidates = (
        _find_candidates("metro", "zori")
        + _find_candidates("metro", "zri")
        + _find_candidates("metro", "zorf")
    )
    for path in candidates:
        try:
            region_values = _read_latest_by_region(path)
            for region, value in region_values.items():
                if region_search.lower() in region.lower():
                    return value
        except Exception:
            continue
    return None


def _is_national_row(region_name: str) -> bool:
    rn = region_name.lower()
    return "united states" in rn or rn in {"usa", "national", "us total"}


def _is_providence_zip_row(row: Dict[str, str], region_name: str) -> bool:
    region_id = (row.get("RegionName") or "").strip()
    if region_id in PROVIDENCE_ZIPS:
        return True
    return region_name in PROVIDENCE_ZIPS


def load_national_zori_latest() -> Optional[float]:
    """
    Return a single Zillow rent signal:
    1) Prefer explicit national row from zori/zri/zorf files.
    2) Fallback to Providence ZIP average from ZIP zri files.
    """
    candidates = (
        _find_candidates("zori")
        + _find_candidates("zri")
        + _find_candidates("zorf")
    )
    if not candidates:
        return None

    # Pass 1: explicit national rows.
    for path in candidates:
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    continue
                date_cols = [c for c in reader.fieldnames if c not in META_COLS]
                for row in reader:
                    region = (row.get("RegionName") or row.get("Region") or "").strip()
                    if not region:
                        continue
                    if _is_national_row(region):
                        value = _latest_value(row, date_cols)
                        if value is not None:
                            return value
        except Exception:
            continue

    # Pass 2: Providence ZIP-based fallback.
    for path in candidates:
        name = os.path.basename(path).lower()
        if "zip" not in name:
            continue
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    continue
                date_cols = [c for c in reader.fieldnames if c not in META_COLS]
                vals: list[float] = []
                for row in reader:
                    region = (row.get("RegionName") or row.get("Region") or "").strip()
                    if not region:
                        continue
                    if _is_providence_zip_row(row, region):
                        latest = _latest_value(row, date_cols)
                        if latest is not None:
                            vals.append(latest)
                if vals:
                    return round(mean(vals), 2)
        except Exception:
            continue

    return None
