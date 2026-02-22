"""
download_zillow.py

Downloads Zillow Research CSVs into `python/data/zillow/` and produces small JSON summaries:
 - <csvname>.meta.json  => { columns: [...], row_count: N }
 - <csvname>.sample.json => first N rows as list-of-dicts

Usage:
  python python/scripts/download_zillow.py               # download defaults
  python python/scripts/download_zillow.py --urls URL1 URL2
  python python/scripts/download_zillow.py --list        # show default named datasets

Notes:
- Default URLs point to Zillow "research" CSVs; you can pass any direct CSV URL.
- Respect Zillow terms; these datasets are the public research CSVs intended for research use.
"""

import os
import argparse
import httpx
import csv
import json
from urllib.parse import urlparse
from dotenv import load_dotenv

DEFAULT_DATASETS = {
    "zip_zri_allhomes": "https://files.zillowstatic.com/research/public/Zip_Zri_AllHomes.csv",
    "zip_zhvi_allhomes": "https://files.zillowstatic.com/research/public/Zip_Zhvi_AllHomes.csv",
}

DEFAULT_OUTDIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "zillow")
load_dotenv()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def basename_from_url(url: str) -> str:
    p = urlparse(url)
    return os.path.basename(p.path)


def download_url(url: str, dest_path: str, client: httpx.Client):
    with client.stream("GET", url, timeout=60.0) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)


def parse_csv_summary(csv_path: str, sample_n: int = 10, state_filter: str | None = None):
    meta = {"columns": [], "row_count": 0}
    sample = []
    with open(csv_path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return meta, sample
        meta["columns"] = reader.fieldnames
        for i, row in enumerate(reader, start=1):
            if state_filter:
                # common Zillow CSVs use 'State' for state abbreviation
                if (row.get("State") or row.get("state") or row.get("StateName") or row.get("statename") or "").strip().upper() != state_filter.upper():
                    continue
            if len(sample) < sample_n:
                sample.append(row)
            meta["row_count"] += 1
    return meta, sample


def run_download(urls, outdir=DEFAULT_OUTDIR, sample_n=10, state_filter: str | None = None):
    ensure_dir(outdir)
    client = httpx.Client()
    results = []
    for url in urls:
        try:
            name = basename_from_url(url) or url.replace('/', '_')
            dest_csv = os.path.join(outdir, name)
            print(f"Downloading {url} -> {dest_csv}")
            download_url(url, dest_csv, client)

            # If a state filter is provided, create a filtered CSV first
            target_csv = dest_csv
            if state_filter:
                filtered_csv = dest_csv + f".{state_filter.upper()}.csv"
                print(f"Filtering {dest_csv} -> {filtered_csv} (state={state_filter})")
                # read original and write only rows matching the state
                with open(dest_csv, newline='', encoding='utf-8') as src, open(filtered_csv, 'w', newline='', encoding='utf-8') as dst:
                    reader = csv.DictReader(src)
                    if reader.fieldnames is None:
                        print(f"No columns found in {dest_csv}, skipping filter")
                    else:
                        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
                        writer.writeheader()
                        for row in reader:
                            if (row.get('State') or row.get('state') or row.get('StateName') or row.get('statename') or '').strip().upper() == state_filter.upper():
                                writer.writerow(row)
                target_csv = filtered_csv

            print(f"Parsing {target_csv}")
            meta, sample = parse_csv_summary(target_csv, sample_n=sample_n, state_filter=None)
            meta_path = target_csv + ".meta.json"
            sample_path = target_csv + ".sample.json"
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2)
            with open(sample_path, "w", encoding="utf-8") as fh:
                json.dump(sample, fh, indent=2)

            results.append({"url": url, "csv": dest_csv, "meta": meta_path, "sample": sample_path})
            print(f"Saved meta -> {meta_path}, sample -> {sample_path}\n")
        except Exception as e:
            print(f"Failed to download or parse {url}: {e}")
    client.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Download Zillow Research CSVs and produce JSON summaries")
    parser.add_argument(
        "--outdir",
        "-o",
        default=os.getenv("ZILLOW_DATA_DIR", DEFAULT_OUTDIR),
        help="Output directory (defaults to ZILLOW_DATA_DIR or python/data/zillow)",
    )
    parser.add_argument("--sample", "-n", type=int, default=10, help="Number of sample rows to save")
    parser.add_argument("--list", action="store_true", help="List default named datasets")
    parser.add_argument("--urls", nargs="*", help="One or more dataset URLs (if none, defaults are used)")
    parser.add_argument("--state", "-s", help="State filter (e.g. RI) to produce a smaller, state-specific CSV and summaries")
    args = parser.parse_args()

    if args.list:
        print("Default datasets:")
        for k, v in DEFAULT_DATASETS.items():
            print(f"  {k}: {v}")
        return

    if args.urls and len(args.urls) > 0:
        urls = args.urls
    else:
        urls = list(DEFAULT_DATASETS.values())

    results = run_download(urls, outdir=args.outdir, sample_n=args.sample, state_filter=args.state)
    print("Done. Files saved:")
    for r in results:
        print(f" - {r['csv']}")


if __name__ == '__main__':
    main()
