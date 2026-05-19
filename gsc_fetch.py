"""
Fetch GSC data for sc-domain:oxylabs.io and cache locally.

Setup (one-time):
  pip install google-auth-oauthlib google-api-python-client
  Place credentials/client_secret.json (downloaded from GCP Console → APIs & Services → Credentials)
  First run opens browser for OAuth2 consent → saves credentials/token.json for future runs.

Usage:
  python3 gsc_fetch.py           # fetch all dimensions (90d) + range snapshots (7d/28d/90d)
  python3 gsc_fetch.py --force   # re-fetch even if today's cache already exists

Range snapshots saved to project root: gsc_7d.json.gz, gsc_28d.json.gz, gsc_90d.json.gz
(also updates gsc_data.json.gz = gsc_90d.json.gz for backwards compatibility)
"""

import gzip
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

PROPERTY = "sc-domain:oxylabs.io"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
CREDENTIALS_DIR = Path(__file__).parent / "credentials"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
CACHE_ROOT = Path(__file__).parent / "cache"
ROWS_PER_PAGE = 25_000

# Each entry: (cache_key, dimensions_list)
DIMENSION_SETS = [
    ("query_date",    ["query", "date"]),
    ("page_date",     ["page", "date"]),
    ("query_page",    ["query", "page"]),
    ("country_date",  ["country", "date"]),
    ("device_date",   ["device", "date"]),
]

# Date ranges saved as root-level snapshots for the topic map
RANGE_DAYS = [7, 28, 90]


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CLIENT_SECRET_PATH}\n"
                    "Download it from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        CREDENTIALS_DIR.mkdir(exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def fetch_dimension(service, start_date: str, end_date: str, dimensions: list[str]) -> list[dict]:
    rows = []
    start_row = 0
    while True:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": ROWS_PER_PAGE,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(siteUrl=PROPERTY, body=body).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        print(f"  [{'+'.join(dimensions)}] rows {start_row}-{start_row + len(batch) - 1}")
        if len(batch) < ROWS_PER_PAGE:
            break
        start_row += ROWS_PER_PAGE
    return rows


def save_cache(cache_dir: Path, key: str, rows: list[dict]):
    path = cache_dir / f"{key}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(rows, f)
    print(f"  Saved {len(rows):,} rows -> {path.relative_to(Path(__file__).parent)}")


def main():
    import shutil
    force = "--force" in sys.argv

    today = date.today().isoformat()
    end_date = (date.today() - timedelta(days=1)).isoformat()
    cache_dir = CACHE_ROOT / f"gsc_{today}"

    if cache_dir.exists() and not force:
        existing = list(cache_dir.glob("*.json.gz"))
        if len(existing) == len(DIMENSION_SETS):
            print(f"Cache already exists for {today}. Use --force to re-fetch.")
        else:
            cache_dir.mkdir(parents=True, exist_ok=True)
            start_date_90 = (date.today() - timedelta(days=90)).isoformat()
            print(f"Fetching GSC data: {start_date_90} to {end_date}")
            creds = get_credentials()
            service = build("searchconsole", "v1", credentials=creds)
            for key, dimensions in DIMENSION_SETS:
                if not (cache_dir / f"{key}.json.gz").exists():
                    print(f"\nFetching {key}...")
                    rows = fetch_dimension(service, start_date_90, end_date, dimensions)
                    save_cache(cache_dir, key, rows)
            meta = {"property": PROPERTY, "start_date": start_date_90, "end_date": end_date, "fetched_on": today}
            (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)
        start_date_90 = (date.today() - timedelta(days=90)).isoformat()
        print(f"Fetching GSC data: {start_date_90} to {end_date}")
        creds = get_credentials()
        service = build("searchconsole", "v1", credentials=creds)
        for key, dimensions in DIMENSION_SETS:
            print(f"\nFetching {key}...")
            rows = fetch_dimension(service, start_date_90, end_date, dimensions)
            save_cache(cache_dir, key, rows)
        meta = {"property": PROPERTY, "start_date": start_date_90, "end_date": end_date, "fetched_on": today}
        (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    # Save root-level range snapshots (page_date only) for topic map date-range toggle
    root_dir = Path(__file__).parent
    creds = get_credentials()
    service = build("searchconsole", "v1", credentials=creds)
    print(f"\nFetching page_date snapshots for date-range toggle...")
    for days in RANGE_DAYS:
        snapshot_path = root_dir / f"gsc_{days}d.json.gz"
        if snapshot_path.exists() and not force:
            print(f"  gsc_{days}d.json.gz already exists, skipping (use --force to re-fetch)")
            continue
        start_date = (date.today() - timedelta(days=days)).isoformat()
        print(f"  Fetching page_date for {days}d ({start_date} to {end_date})...")
        rows = fetch_dimension(service, start_date, end_date, ["page", "date"])
        with gzip.open(snapshot_path, "wt", encoding="utf-8") as f:
            json.dump(rows, f)
        print(f"  Saved gsc_{days}d.json.gz ({snapshot_path.stat().st_size // 1024}KB, {len(rows):,} rows)")

    # Keep gsc_data.json.gz = 90d snapshot for backwards compatibility
    snapshot_90d = root_dir / "gsc_90d.json.gz"
    if snapshot_90d.exists():
        shutil.copy2(snapshot_90d, root_dir / "gsc_data.json.gz")
        print(f"Updated gsc_data.json.gz (copy of gsc_90d.json.gz) — commit range snapshots for CI access.")
    elif (cache_dir / "page_date.json.gz").exists():
        shutil.copy2(cache_dir / "page_date.json.gz", root_dir / "gsc_data.json.gz")
        print(f"Updated gsc_data.json.gz from cache — commit this file for CI access.")

    print(f"\nDone. Commit gsc_7d.json.gz, gsc_28d.json.gz, gsc_90d.json.gz (and gsc_data.json.gz) for CI.")


if __name__ == "__main__":
    main()
