# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python script that fetches the live Oxylabs sitemap, classifies every URL into a topical hierarchy, and generates a static `index.html` with a D3.js mind map. No dependencies beyond the Python standard library. GitHub Actions rebuilds it daily at 06:00 UTC.

Live output: `https://msuika.github.io/oxylabs-scraping-map/`

## Running locally

```bash
python3 build.py   # regenerates index.html
open index.html    # view in browser
```

## Architecture

The entire pipeline lives in `build.py`:

1. **Fetch** — `fetch_sitemap()` pulls the sitemap XML from `SITEMAP_URL` (an obfuscated path, not `sitemap.xml`).
2. **Filter** — `is_excluded()` removes noise (pagination, legal, press, event pages) via `EXCLUDE_PATTERNS`.
3. **Classify** — `classify(url)` returns a `(primary_cluster, sub_cluster)` tuple based on slug pattern matching. This is the main logic to touch when adding/changing topic coverage.
4. **Build tree** — `build_tree()` groups classified URLs into a nested dict, then maps clusters onto the `GROUPS` hierarchy (controls node colors and grouping in the viz).
5. **Render** — `generate_html()` injects the tree JSON and stats into `HTML_TEMPLATE` via string replacement of four placeholders: `__TREE_JSON__`, `__GROUP_SUMMARY__`, `__TOTAL__`, `__BUILD_DATE__`.

`index.html` is **generated output** — never edit it by hand; it's overwritten on every build.

## Key data structures

- `EXCLUDE_PATTERNS` — regex list; add patterns here to suppress URL categories from the map.
- `classify()` — returns `(primary, sub)` strings; both must map to entries in `GROUPS` (via the `clusters` list) or they'll silently appear as orphaned "Other" nodes.
- `GROUPS` dict — defines the five top-level branches, their hex colors, and which `primary` cluster names belong to each group. Order here controls sort order in the legend/stats panel.

## CI

`.github/workflows/build.yml` runs `python build.py` on push to `main` (when `build.py` or the workflow itself changes), on a daily cron, and on manual `workflow_dispatch`. It auto-commits `index.html` if the content changed.