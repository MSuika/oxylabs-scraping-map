# Oxylabs Web Scraping Topic Map

An interactive mind map of every web-scraping-related URL on oxylabs.io. Auto-rebuilds daily from the live sitemap.

**Live URL (once deployed):** `https://msuika.github.io/oxylabs-scraping-map/`

## How it works

1. `build.py` fetches `https://oxylabs.io/sitemap.xml`
2. Filters and classifies every URL into a topical hierarchy (Products, Geo SEO, Solutions, Blog, Resources)
3. Generates a single static `index.html` with an interactive D3.js mind map
4. GitHub Action runs the build every morning at 06:00 UTC and auto-commits any changes
5. GitHub Pages serves `index.html` to the world

No backend, no servers. Just one HTML file regenerated daily.

## One-time setup

1. **Create the repo on GitHub**
   - Go to https://github.com/new
   - Name it `oxylabs-scraping-map`
   - Make it public (required for free GitHub Pages) or private (works on paid plan)
   - Don't initialise with a README - we already have one

2. **Push the files**
   ```bash
   cd "oxylabs-scraping-map"
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/MSuika/oxylabs-scraping-map.git
   git push -u origin main
   ```

3. **Enable GitHub Pages**
   - Go to the repo -> Settings -> Pages
   - Source: "Deploy from a branch"
   - Branch: `main` / folder: `/ (root)`
   - Click Save
   - Wait 1-2 min, then visit `https://msuika.github.io/oxylabs-scraping-map/`

4. **Trigger the first build**
   - Go to Actions tab -> "Rebuild topic map" -> "Run workflow" -> Run
   - This generates the first `index.html` from the live sitemap
   - After it finishes (~30s), refresh your Pages URL

That's it. From now on it rebuilds every morning automatically.

## Running locally

```bash
python3 build.py
open index.html
```

No dependencies - uses only the Python standard library.

## Customising

- **Change the schedule:** edit the cron in `.github/workflows/build.yml`. Format is `minute hour day month weekday` (UTC).
- **Add or remove topic clusters:** edit the `GROUPS` dict and `classify()` function in `build.py`.
- **Tweak the visuals:** all CSS and D3 code lives inside the `HTML_TEMPLATE` string in `build.py`.

## Files

| File | Purpose |
|---|---|
| `build.py` | Fetches sitemap, classifies URLs, writes `index.html` |
| `index.html` | The generated mind map (do not edit by hand - regenerated each build) |
| `.github/workflows/build.yml` | Daily cron job |
| `README.md` | This file |
