"""
python/scripts/download_zillow.py

Refactored for local CSV workflow:
- Reads Zillow CSVs already present in python/data
- Generates visualization PNG charts (no API/download required)

Outputs:
- python/data/visualizations/zillow/metro_providence_zordi.png
- python/data/visualizations/zillow/national_zorf_growth.png

Usage:
  python python/scripts/download_zillow.py
  python python/scripts/download_zillow.py --region Providence
  python python/scripts/download_zillow.py --outdir python/data/visualizations/zillow
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import matplotlib.pyplot as plt
from dotenv import load_dotenv

# Allow direct script execution: `python python/scripts/download_zillow.py`
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from python.config import settings
from python.services.zillow_loader import (
    DATASETS,
    get_dataset_catalog,
    get_metro_series,
    get_national_growth_series,
)

load_dotenv()

DEFAULT_OUTDIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "visualizations", "zillow")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _label_stride(n: int) -> int:
    if n <= 12:
        return 1
    if n <= 36:
        return 3
    if n <= 72:
        return 6
    return 12


def plot_series(
    x_labels: list[str],
    y_values: list[float],
    title: str,
    ylabel: str,
    out_path: str,
    color: str,
    baseline: Optional[float] = None,
) -> Optional[str]:
    if not x_labels or not y_values:
        return None

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(range(len(y_values)), y_values, linewidth=2.3, color=color)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.25)

    if baseline is not None:
        ax.axhline(baseline, linestyle="--", linewidth=1, alpha=0.5, color="#888")

    stride = _label_stride(len(x_labels))
    tick_idx = list(range(0, len(x_labels), stride))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([x_labels[i] for i in tick_idx], rotation=40, ha="right", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def build_visualizations(region: str, outdir: str) -> list[str]:
    ensure_dir(outdir)
    generated: list[str] = []

    metro_x, metro_y = get_metro_series(region)
    metro_path = os.path.join(outdir, "metro_providence_zordi.png")
    out = plot_series(
        metro_x,
        metro_y,
        f"Zillow Metro Rent Signal ({region})",
        "ZORDI Value",
        metro_path,
        color="#1e6bff",
    )
    if out:
        generated.append(out)

    growth_x, growth_y = get_national_growth_series()
    growth_path = os.path.join(outdir, "national_zorf_growth.png")
    out = plot_series(
        growth_x,
        growth_y,
        "Zillow National Rent Growth Forecast",
        "Growth (%)",
        growth_path,
        color="#2ed8a3",
        baseline=0.0,
    )
    if out:
        generated.append(out)

    return generated


def print_dataset_catalog() -> None:
    print("Detected Zillow datasets:")
    for ds in get_dataset_catalog():
        status = "FOUND" if ds["exists"] else "MISSING"
        print(f"- {ds['filename']} [{status}]")
        print(f"  purpose: {ds['purpose']}")
        print(f"  metric: {ds['metric']}")
        print(f"  granularity: {ds['granularity']}")
        print(f"  path: {ds['path']}")



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Zillow visualizations from local CSVs")
    parser.add_argument("--region", default="Providence", help="Metro region search term for metro chart")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Output directory for PNG charts")
    parser.add_argument("--catalog", action="store_true", help="Print dataset catalog and exit")
    args = parser.parse_args()

    if args.catalog:
        print_dataset_catalog()
        return

    missing = [k for k, ds in DATASETS.items() if not os.path.isfile(os.path.join(settings.zillow_data_dir, ds.filename))]
    if missing:
        print("Warning: some expected dataset files are missing in python/data:")
        for key in missing:
            print(f"- {DATASETS[key].filename}")

    print_dataset_catalog()
    generated = build_visualizations(args.region, args.outdir)

    if not generated:
        print("No charts generated. Check that dataset CSVs exist and have numeric date columns.")
        return

    print("Generated charts:")
    for path in generated:
        print(f"- {path}")


if __name__ == "__main__":
    main()
