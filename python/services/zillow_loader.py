from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from python.config import settings


@dataclass(frozen=True)
class ZillowDataset:
    filename: str
    metric: str
    granularity: str
    purpose: str


DATASETS = {
    "metro_zordi": ZillowDataset(
        filename="Metro_zordi_uc_sfrcondomfr_month.csv",
        metric="Observed rent index/value",
        granularity="Metro",
        purpose="Current rent signal for Providence metro",
    ),
    "national_zorf_growth": ZillowDataset(
        filename="National_zorf_growth_uc_sfr_sm_month.csv",
        metric="Forecast rent growth (%)",
        granularity="National",
        purpose="Forward rent trend adjustment signal",
    ),
}

META_COLS = {"RegionID", "SizeRank", "RegionName", "RegionType", "StateName", "State", "BaseDate"}


def _data_dir() -> str:
    return settings.zillow_data_dir


def _dataset_path(dataset_key: str) -> Optional[str]:
    ds = DATASETS.get(dataset_key)
    if not ds:
        return None
    path = os.path.join(_data_dir(), ds.filename)
    return path if os.path.isfile(path) else None


def get_dataset_catalog() -> list[dict]:
    out = []
    for key, ds in DATASETS.items():
        out.append(
            {
                "key": key,
                "filename": ds.filename,
                "metric": ds.metric,
                "granularity": ds.granularity,
                "purpose": ds.purpose,
                "path": os.path.join(_data_dir(), ds.filename),
                "exists": os.path.isfile(os.path.join(_data_dir(), ds.filename)),
            }
        )
    return out


def _date_cols(fieldnames: Iterable[str]) -> list[str]:
    return [c for c in fieldnames if c not in META_COLS]


def _parse_float(v: str | None) -> Optional[float]:
    raw = (v or "").strip()
    if raw in {"", "NA", "nan"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _latest_from_row(row: Dict[str, str], cols: list[str]) -> Optional[float]:
    for c in reversed(cols):
        n = _parse_float(row.get(c))
        if n is not None:
            return n
    return None


def get_metro_latest(region_search: str = "Providence") -> Optional[float]:
    """Latest metro series value for matching metro name (e.g. Providence)."""
    path = _dataset_path("metro_zordi")
    if not path:
        return None

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return None
        cols = _date_cols(reader.fieldnames)

        # Prefer exact-ish region match.
        for row in reader:
            region = (row.get("RegionName") or "").strip()
            if region_search.lower() in region.lower():
                return _latest_from_row(row, cols)

    return None


def get_metro_series(region_search: str = "Providence") -> tuple[list[str], list[float]]:
    """Return full date/value series for one metro region."""
    path = _dataset_path("metro_zordi")
    if not path:
        return [], []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return [], []
        cols = _date_cols(reader.fieldnames)

        for row in reader:
            region = (row.get("RegionName") or "").strip()
            if region_search.lower() not in region.lower():
                continue
            xs: list[str] = []
            ys: list[float] = []
            for c in cols:
                n = _parse_float(row.get(c))
                if n is None:
                    continue
                xs.append(c)
                ys.append(n)
            return xs, ys

    return [], []


def load_national_zori_latest() -> Optional[float]:
    """
    Latest available national forecast growth value from
    National_zorf_growth_uc_sfr_sm_month.csv.
    """
    path = _dataset_path("national_zorf_growth")
    if not path:
        return None

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return None
        cols = _date_cols(reader.fieldnames)

        # File is typically one row for United States.
        for row in reader:
            region = (row.get("RegionName") or "").strip().lower()
            if region and "united states" not in region and "national" not in region and region != "usa":
                continue
            return _latest_from_row(row, cols)

    return None


def get_national_growth_series() -> tuple[list[str], list[float]]:
    path = _dataset_path("national_zorf_growth")
    if not path:
        return [], []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return [], []
        cols = _date_cols(reader.fieldnames)
        for row in reader:
            xs: list[str] = []
            ys: list[float] = []
            for c in cols:
                n = _parse_float(row.get(c))
                if n is None:
                    continue
                xs.append(c)
                ys.append(n)
            return xs, ys

    return [], []