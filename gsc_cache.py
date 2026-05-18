"""
Loader for cached GSC data. Used by analysis scripts so they don't re-fetch.

Usage:
  from gsc_cache import load, meta

  queries = load("query_date")   # list of dicts with keys: keys[], clicks, impressions, ctr, position
  pages   = load("page_date")
  pairs   = load("query_page")
  info    = meta()               # {"property", "start_date", "end_date", "fetched_on"}

Available keys: query_date, page_date, query_page, country_date, device_date
"""

import gzip
import json
from pathlib import Path

_CACHE_ROOT = Path(__file__).parent / "cache"


def _latest_cache_dir() -> Path:
    dirs = sorted(_CACHE_ROOT.glob("gsc_*"), reverse=True)
    if not dirs:
        raise FileNotFoundError(
            "No GSC cache found. Run: python3 gsc_fetch.py"
        )
    return dirs[0]


def load(key: str, cache_date: str | None = None) -> list[dict]:
    """
    Load a dimension dataset from cache.
    key: one of query_date, page_date, query_page, country_date, device_date
    cache_date: YYYY-MM-DD string to pick a specific cache; defaults to latest.
    """
    if cache_date:
        cache_dir = _CACHE_ROOT / f"gsc_{cache_date}"
    else:
        cache_dir = _latest_cache_dir()

    path = cache_dir / f"{key}.json.gz"
    if not path.exists():
        raise FileNotFoundError(f"Cache file not found: {path}\nRun: python3 gsc_fetch.py")

    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def meta(cache_date: str | None = None) -> dict:
    if cache_date:
        cache_dir = _CACHE_ROOT / f"gsc_{cache_date}"
    else:
        cache_dir = _latest_cache_dir()
    return json.loads((cache_dir / "meta.json").read_text())


def available_dates() -> list[str]:
    return sorted(
        p.name.replace("gsc_", "") for p in _CACHE_ROOT.glob("gsc_*") if p.is_dir()
    )
