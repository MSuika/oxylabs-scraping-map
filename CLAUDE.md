# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python script that fetches the live Oxylabs sitemap, classifies every URL into a topical hierarchy, and generates a static `index.html` with a D3.js mind map. `build.py` has no dependencies beyond the Python standard library. GitHub Actions rebuilds it daily at 06:00 UTC.

Live output: `https://msuika.github.io/oxylabs-scraping-map/`

## Running locally

```bash
python3 build.py   # regenerates index.html
open index.html    # view in browser
```

## Architecture

The entire pipeline lives in `build.py`:

1. **GSC load** — `load_gsc_metrics(range_key)` is called once per range (`7d`, `28d`, `90d`). For `90d` it falls back through `gsc_data.json.gz` → latest `cache/gsc_*/page_date.json.gz`. Returns a `{url: {clicks, impressions, position}}` dict; absent = bubble sizes fall back to URL counts.
2. **Fetch** — `fetch_sitemap()` pulls the sitemap XML from `SITEMAP_URL` (an obfuscated path, not `sitemap.xml`).
3. **Filter** — `is_excluded()` removes noise (pagination, blog authors) via `EXCLUDE_PATTERNS`.
4. **Classify** — `classify(url)` returns a `(primary_cluster, sub_cluster)` tuple via slug pattern matching. This is the main logic to touch when adding/changing topic coverage.
5. **New-URL tracking** — `known_urls.json` persists the first-seen ISO date per URL. `get_new_url_set()` returns URLs first seen within the last 7 days; these get `is_new: true` in the tree and a "NEW" badge in the UI.
6. **Build tree** — `build_tree()` is called once per range, producing a nested dict mapped onto the `GROUPS` hierarchy. Single-child cluster nodes are collapsed (the intermediate node is removed; its `urls`/`clicks` are promoted to the cluster level). All three range trees are collected into a `datasets` dict keyed by range.
7. **Render** — `generate_html(datasets, total, build_date)` injects data into `HTML_TEMPLATE` via three string-replace placeholders: `__DATASETS_JSON__`, `__TOTAL__`, `__BUILD_DATE__`.

`index.html` is **generated output** — never edit it by hand.

## Key data structures

- `EXCLUDE_PATTERNS` — regex list; add patterns here to suppress URL categories.
- `classify()` — returns `(primary, sub)` strings; both must map to entries in `GROUPS` (via the `clusters` list) or they'll silently appear as "Other" nodes.
- `GROUPS` dict — defines the top-level branches, their hex colors, and which `primary` cluster names belong to each. Order here controls sort order in the legend/stats panel.

## GSC integration

CI **does not** re-fetch GSC — it uses `gsc_data.json.gz`, a committed snapshot of `page_date` dimension data (page × date rows). Refresh it locally:

```bash
# One-time setup (needs external deps):
pip install google-auth-oauthlib google-api-python-client

# First run opens browser for OAuth2 consent; saves credentials/token.json
python3 gsc_fetch.py

# Force re-fetch even if today's cache exists:
python3 gsc_fetch.py --force
```

`gsc_fetch.py` requires `credentials/client_secret.json` (download from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs). Both `credentials/` and `cache/` are gitignored.

After fetching, `gsc_fetch.py` saves three root-level range snapshots (`gsc_7d.json.gz`, `gsc_28d.json.gz`, `gsc_90d.json.gz`) and copies the 90d snapshot to `gsc_data.json.gz` for backwards compatibility. **Commit all four files** so CI builds have traffic data for all range toggles.

`gsc_cache.py` is a standalone loader for ad-hoc analysis scripts:
```python
from gsc_cache import load, meta
pages = load("page_date")   # list of GSC row dicts
```
Available dimension keys: `query_date`, `page_date`, `query_page`, `country_date`, `device_date`.

## CI

`.github/workflows/build.yml` runs `python build.py` on push to `main` (when `build.py` or the workflow itself changes), on a daily cron, and on manual `workflow_dispatch`. It auto-commits `index.html` if the content changed. No GSC re-fetch happens in CI.
