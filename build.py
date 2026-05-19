#!/usr/bin/env python3
"""
Oxylabs Web Scraping Topic Map - Build Script

Fetches the live Oxylabs sitemap, classifies URLs into a topical hierarchy,
and generates a static index.html with an interactive D3-based mind map.
If a local GSC cache (cache/gsc_*/page_date.json.gz) is present, bubble sizes
and the URL panel reflect real click / impression / position data.

Run locally:  python build.py
In CI:        executed by .github/workflows/build.yml on a daily schedule.
"""

import gzip
import re
import json
import sys
import datetime
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

SITEMAP_URL = "https://oxylabs.io/f3h5j7k9m2n4p6q8r0.xml"
USER_AGENT = "OxylabsTopicMap/1.0 (+github.com/MSuika/oxylabs-scraping-map)"

RANGE_KEYS = ["7d", "28d", "90d"]
RANGE_LABELS = {"7d": "last 7 days", "28d": "last 28 days", "90d": "last 90 days"}


# ---------- 0. GSC Cache ----------

def load_gsc_metrics(range_key: str = "90d") -> dict:
    """Load page-level GSC metrics for a given date range.
    Looks for gsc_{range_key}.json.gz; for 90d also falls back to gsc_data.json.gz
    and finally to the latest cache/gsc_*/page_date.json.gz."""
    root = Path(__file__).parent
    path = root / f"gsc_{range_key}.json.gz"
    if not path.exists():
        if range_key == "90d":
            path = root / "gsc_data.json.gz"
            if not path.exists():
                dirs = sorted((root / "cache").glob("gsc_*"), reverse=True)
                if not dirs:
                    return {}
                path = dirs[0] / "page_date.json.gz"
        else:
            return {}
    if not path.exists():
        return {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception as e:
        print(f"Warning: could not load GSC cache ({range_key}): {e}", file=sys.stderr)
        return {}
    metrics: dict = {}
    for row in rows:
        url = row["keys"][0]
        if url not in metrics:
            metrics[url] = {"clicks": 0, "impressions": 0, "_pos_sum": 0.0, "_pos_w": 0}
        m = metrics[url]
        m["clicks"] += row.get("clicks", 0)
        m["impressions"] += row.get("impressions", 0)
        imp = row.get("impressions", 0)
        m["_pos_sum"] += row.get("position", 0) * imp
        m["_pos_w"] += imp
    for m in metrics.values():
        m["position"] = round(m["_pos_sum"] / m["_pos_w"], 1) if m["_pos_w"] > 0 else None
        del m["_pos_sum"]
        del m["_pos_w"]
    return metrics


def fmt_k(n: int) -> str:
    if n >= 1_000_000:
        s = f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        s = f"{n / 1_000:.1f}k"
    else:
        return str(n)
    return s.rstrip('0').rstrip('.')


# ---------- 1. Fetch ----------

def fetch_sitemap(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (URLError, HTTPError) as e:
        print(f"ERROR: failed to fetch sitemap: {e}", file=sys.stderr)
        sys.exit(1)


# ---------- 2. Filter noise ----------

EXCLUDE_PATTERNS = [
    r'/blog/page/\d+',
    r'/blog/authors/',
    r'/blog/authors$',
]

def is_excluded(url: str) -> bool:
    return any(re.search(p, url) for p in EXCLUDE_PATTERNS)


# ---------- 3. Classify ----------

def classify(url: str):
    u = url.lower()
    slug = u.replace('https://oxylabs.io/', '').rstrip('/')

    # ===== PRODUCTS - SCRAPER APIs =====
    if slug.startswith('products/scraper-api'):
        if '/ecommerce/' in u:    return ('Scraper APIs', 'E-commerce scrapers')
        if '/serp/' in u:         return ('Scraper APIs', 'SERP scrapers')
        if '/real-estate' in u:   return ('Scraper APIs', 'Real estate scrapers')
        if '/travel' in u:        return ('Scraper APIs', 'Travel scrapers')
        if '/social-media' in u:  return ('Scraper APIs', 'Social media scrapers')
        if 'ai' in slug:          return ('Scraper APIs', 'AI scrapers / Copilot')
        return ('Scraper APIs', 'Web Scraper API (core)')

    # ===== PRODUCTS - OTHER =====
    if slug.startswith('products/'):
        p = slug.replace('products/', '')
        if 'web-unblocker' in p or 'unblock' in p:           return ('Products - Tools', 'Web Unblocker')
        if 'residential' in p:                                return ('Products - Proxies', 'Residential proxies')
        if 'mobile' in p:                                     return ('Products - Proxies', 'Mobile proxies')
        if 'datacenter' in p or 'data-center' in p:           return ('Products - Proxies', 'Datacenter proxies')
        if 'isp' in p:                                        return ('Products - Proxies', 'ISP proxies')
        if 'dataset' in p or p.startswith('data-'):           return ('Products - Data', 'Datasets & data')
        if 'oxycopilot' in p or 'ai-' in p:                   return ('Products - AI', 'AI tools')
        if 'open-source' in p:                                return ('Products - Tools', 'Open source tools')
        if 'alternative' in p:                                return ('Products - Comparison', 'Competitor alternatives')
        if 'proxies' in p or 'proxy' in p:                    return ('Products - Target Proxies', 'Site/use-case specific proxies')
        return ('Products - Tools', 'Other products')

    # ===== GEO PROXIES =====
    if slug.startswith('location-proxy/'):
        return ('Geo-Targeted Proxies', 'Country/region landing pages')

    # ===== SOLUTIONS =====
    if slug.startswith('solutions'):
        if 'ecommerce' in slug or 'retail' in slug or 'pricing' in slug: return ('Solutions', 'E-commerce / retail')
        if 'travel' in slug:                  return ('Solutions', 'Travel & hospitality')
        if 'real-estate' in slug:             return ('Solutions', 'Real estate')
        if 'seo' in slug or 'serp' in slug:   return ('Solutions', 'SEO / SERP')
        if 'cyber' in slug or 'fraud' in slug:return ('Solutions', 'Cybersecurity & fraud')
        if 'ai' in slug or 'llm' in slug:     return ('Solutions', 'AI / LLM training')
        if 'finance' in slug:                 return ('Solutions', 'Finance / alt-data')
        if 'market-research' in slug:         return ('Solutions', 'Market research')
        return ('Solutions', 'Other industry solutions')

    if slug.startswith('tools/'):      return ('Free Tools', 'Free scraping tools')
    if slug == 'what-is-my-ip':        return ('Free Tools', 'Free scraping tools')
    if slug.startswith('features/'):   return ('Product Features', 'Feature pages')
    if slug.startswith('pricing'):     return ('Pricing', 'Pricing pages')

    # ===== COMPANY & BRAND =====
    if slug in ('about-us', 'sustainability', 'press-area', 'affiliates',
                'oxycopilot-story', 'project-4beta', 'careers'):
        return ('Company & Brand', 'Company pages')
    if slug.startswith('oxycon'):
        return ('Company & Brand', 'Events & community')

    # ===== LEGAL & TRUST =====
    if slug.startswith('legal'):
        return ('Legal & Trust', 'Legal documents')
    if slug in ('risk-and-legal-compliance', 'kyc-and-safety'):
        return ('Legal & Trust', 'Compliance & trust')

    # ===== RESOURCES =====
    if slug.startswith('resources/'):
        if 'error-codes' in slug:                                                              return ('Resources', 'API error code docs')
        if 'integrations' in slug:                                                             return ('Resources', 'Integrations')
        if 'prompts-code-samples' in slug:                                                     return ('Resources', 'AI prompts & code samples')
        if 'case-studies' in slug or 'case-study' in slug:                                     return ('Resources', 'Case studies')
        if 'ebooks' in slug or 'whitepapers' in slug or 'webinars' in slug or 'reports' in slug: return ('Resources', 'Ebooks/whitepapers/webinars')
        return ('Resources', 'Other resources')

    if slug.startswith('developers'):
        return ('Developer / Community', 'Developer pages')

    # ===== BLOG =====
    if slug.startswith('blog/'):
        b = slug.replace('blog/', '')
        if b.startswith('category/'):
            return ('Blog hubs', 'Category landing pages')

        if any(k in b for k in ['amazon','google','ebay','walmart','tiktok','instagram','youtube','linkedin','twitter','facebook-','-facebook','reddit','aliexpress','shopify','idealo','yelp','craigslist','zillow','redfin','airbnb','booking','expedia','glassdoor','indeed','tripadvisor']):
            return ('Blog - Target sites', 'Site-specific scraping guides')
        if 'serp' in b or 'search-engine' in b or 'rank-track' in b or 'search-result' in b:
            return ('Blog - SERP', 'Search engine scraping')
        if any(k in b for k in ['python','javascript','nodejs','node-js','node.js','golang','-go-','java-','php-','ruby-','rust-','c-sharp','csharp','puppeteer','playwright','selenium','scrapy','beautifulsoup','cheerio','axios','requests-library','curl-','httpx','aiohttp']):
            return ('Blog - Languages & Libraries', 'Languages, libraries, frameworks')
        if any(k in b for k in ['captcha','blocked','-block','block-','anti-bot','antibot','detect','fingerprint','cloudflare','bypass','banned','stealth','ban-','datadome','akamai','incapsula','perimeter']):
            return ('Blog - Anti-bot & evasion', 'Anti-bot, blocking, evasion')
        if any(k in b for k in ['ai-','-ai-','llm','gpt','mcp','agent','rag','machine-learning','dataset','data-collection','data-extraction','data-quality','data-parsing','data-mining','alternative-data','data-driven','firmographic','big-data','web-data','data-pipeline','data-research','data-wrangling','etl-pipeline','data-acquisition','extract-data']):
            return ('Blog - AI & data', 'AI, LLM, data engineering')
        if any(k in b for k in ['proxy','proxies','rotat','ip-','-ip-','residential','datacenter','isp-','mobile-proxy','sock5','socks5','http-proxy']):
            return ('Blog - Proxies', 'Proxy guides & types')
        if any(k in b for k in ['ecommerce','e-commerce','price-','pricing-','retail','product-data','map-monitoring','competitor-monitoring','product-monitoring','dynamic-pricing','minimum-advertised','review-analysis','review-monitoring']):
            return ('Blog - E-commerce & pricing intel', 'Pricing, retail intel')
        if any(k in b for k in ['how-to-','tutorial','guide-to','getting-started','step-by-step']):
            return ('Blog - Tutorials', 'How-to guides')
        if any(k in b for k in ['vs-','-vs-','review','best-','top-','alternatives','comparison']):
            return ('Blog - Comparisons & reviews', 'Tool comparisons')
        if any(k in b for k in ['legal','gdpr','compliance','ethical','lawful','is-it-legal']):
            return ('Blog - Legal & compliance', 'Legal aspects')
        if any(k in b for k in ['lead-gen','market-research','competitive-intel','sentiment','brand-monitor','ad-intelligence','sales-intelligence','use-case','business-','investment','travel-fare','fare-aggregation']):
            return ('Blog - Business use cases', 'Business use cases')
        if any(k in b for k in ['scrap','crawl','parser','parsing','web-data','extract','fetch','request','http-','headless','browser-automation','user-agent','xpath','regex','css-selector','json','html-parsing','web-scraping','data-extract','spider']):
            return ('Blog - Scraping fundamentals', 'Core scraping concepts')
        if any(k in b for k in ['curl-','http-','rest-','graphql','api-','webhook','oauth']):
            return ('Blog - API & networking', 'API/networking tutorials')
        if any(k in b for k in ['ip-address','geolocation','geo-target','vpn','tor-']):
            return ('Blog - Networking', 'IP, geo, networking')
        if any(k in b for k in ['oxylabs-shortlisted','oxylabs-wins','oxylabs-announces',
                                  'oxylabs-launches','accreditation','-partnership',
                                  'empowering-the-','free-white-paper']):
            return ('Blog - Company News', 'Company announcements & PR')
        if any(k in b for k in ['oxycon','devworld-','conference-','ai4-conference',
                                  'code-university','cyber-insurance','2-weeks-until']):
            return ('Blog - Events', 'Events & community')

        return ('Blog - Other', 'Other blog content')

    return ('Other', 'Misc')


GROUPS = {
    "Products": {
        "color": "#0066FF",
        "clusters": ["Scraper APIs", "Products - Proxies", "Products - Target Proxies",
                     "Products - Tools", "Products - Data", "Products - AI",
                     "Products - Comparison", "Product Features"]
    },
    "Geo SEO (Location Proxies)": {
        "color": "#7B61FF",
        "clusters": ["Geo-Targeted Proxies"]
    },
    "Solutions & Use Cases": {
        "color": "#00B8A9",
        "clusters": ["Solutions", "Free Tools"]
    },
    "Blog / Content": {
        "color": "#F39C12",
        "clusters": ["Blog - Scraping fundamentals", "Blog - Tutorials", "Blog - Languages & Libraries",
                     "Blog - Target sites", "Blog - SERP", "Blog - Proxies", "Blog - Anti-bot & evasion",
                     "Blog - AI & data", "Blog - E-commerce & pricing intel", "Blog - Business use cases",
                     "Blog - Comparisons & reviews", "Blog - Legal & compliance", "Blog - API & networking",
                     "Blog - Networking", "Blog - Company News", "Blog - Events", "Blog - Other", "Blog hubs"]
    },
    "Resources & Docs": {
        "color": "#E74C3C",
        "clusters": ["Resources", "Developer / Community", "Pricing"]
    },
    "Company & Brand": {
        "color": "#27AE60",
        "clusters": ["Company & Brand"]
    },
    "Legal & Trust": {
        "color": "#95A5A6",
        "clusters": ["Legal & Trust"]
    },
}


def load_known_urls() -> dict:
    """Load known_urls.json -> {url: first_seen_iso_date}"""
    path = Path(__file__).parent / "known_urls.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_known_urls(known_urls: dict):
    path = Path(__file__).parent / "known_urls.json"
    path.write_text(json.dumps(known_urls, sort_keys=True, indent=2), encoding="utf-8")


def get_new_url_set(current_urls: list, known_urls: dict) -> set:
    """Return set of URLs first seen within the last 7 days.
    Updates known_urls in-place. On first run all URLs are backdated so nothing shows as NEW."""
    today = datetime.date.today()
    if not known_urls:
        old_date = (today - datetime.timedelta(days=8)).isoformat()
        for u in current_urls:
            known_urls[u] = old_date
        return set()
    today_iso = today.isoformat()
    cutoff = (today - datetime.timedelta(days=7)).isoformat()
    new_urls = set()
    for u in current_urls:
        if u not in known_urls:
            known_urls[u] = today_iso
        if known_urls[u] >= cutoff:
            new_urls.add(u)
    return new_urls


def build_tree(urls, gsc=None, new_urls=None):
    if gsc is None:
        gsc = {}
    if new_urls is None:
        new_urls = set()
    clusters = defaultdict(lambda: defaultdict(list))
    for u in urls:
        primary, sub = classify(u)
        clusters[primary][sub].append(u)

    tree = {"name": "oxylabs.io", "children": []}
    for group_name, info in GROUPS.items():
        group_node = {"name": group_name, "color": info["color"], "children": []}
        for cl_name in info["clusters"]:
            if cl_name not in clusters:
                continue
            cluster_total = sum(len(v) for v in clusters[cl_name].values())
            if cluster_total == 0:
                continue
            cluster_node = {"name": cl_name, "count": cluster_total, "children": []}
            for sub_name, sub_urls in clusters[cl_name].items():
                if not sub_urls:
                    continue
                url_data = []
                sub_clicks = 0
                sub_new = 0
                for u in sub_urls:
                    m = gsc.get(u, {})
                    clicks = m.get("clicks", 0)
                    sub_clicks += clicks
                    is_new = u in new_urls
                    if is_new:
                        sub_new += 1
                    entry = {
                        "url": u,
                        "clicks": clicks,
                        "impressions": m.get("impressions", 0),
                        "position": m.get("position"),
                    }
                    if is_new:
                        entry["is_new"] = True
                    url_data.append(entry)
                url_data.sort(key=lambda x: (-x["clicks"], x["url"]))
                sub_node = {
                    "name": sub_name,
                    "count": len(sub_urls),
                    "clicks": sub_clicks,
                    "urls": url_data,
                }
                if sub_new:
                    sub_node["new_count"] = sub_new
                cluster_node["children"].append(sub_node)
            cluster_new = sum(c.get("new_count", 0) for c in cluster_node["children"])
            if cluster_new:
                cluster_node["new_count"] = cluster_new
            cluster_node["children"].sort(key=lambda x: (-x.get("clicks", 0), -x.get("count", 0)))
            # Collapse single-child clusters — the intermediate node adds no information
            if len(cluster_node["children"]) == 1:
                only = cluster_node["children"][0]
                cluster_node["clicks"] = only["clicks"]
                cluster_node["urls"] = only["urls"]
                if "new_count" in only:
                    cluster_node["new_count"] = only["new_count"]
                del cluster_node["children"]
            group_node["children"].append(cluster_node)
        group_new = sum(cl.get("new_count", 0) for cl in group_node["children"])
        if group_new:
            group_node["new_count"] = group_new
        group_node["children"].sort(
            key=lambda x: (
                -sum(c.get("clicks", 0) for c in x.get("children", [])) - x.get("clicks", 0),
                -sum(c.get("count", 0) for c in x.get("children", [])) - x.get("count", 0),
            )
        )
        tree["children"].append(group_node)
    tree["children"].sort(
        key=lambda x: -sum(
            (sum(c.get("clicks", 0) for c in cl.get("children", [])) or cl.get("clicks", 0))
            for cl in x["children"]
        )
    )
    return tree


def compute_stats(tree):
    """Return (total_urls, total_clicks, group_summary) from a built tree."""
    total = 0
    total_clicks = 0
    for g in tree["children"]:
        g_total = sum(ch["count"] for ch in g["children"])
        g_clicks = sum(
            (sum(c.get("clicks", 0) for c in cl.get("children", [])) or cl.get("clicks", 0))
            for cl in g["children"]
        )
        total += g_total
        total_clicks += g_clicks
    group_summary = []
    for g in tree["children"]:
        g_total = sum(ch["count"] for ch in g["children"])
        g_clicks = sum(
            (sum(c.get("clicks", 0) for c in cl.get("children", [])) or cl.get("clicks", 0))
            for cl in g["children"]
        )
        group_summary.append({
            "name": g["name"],
            "count": g_total,
            "clicks": g_clicks,
            "color": g["color"],
            "share": round(g_total / total * 100, 1) if total else 0,
            "clicks_share": round(g_clicks / total_clicks * 100, 1) if total_clicks else 0,
        })
    return total, total_clicks, group_summary


def generate_html(datasets, total, build_date):
    return (HTML_TEMPLATE
            .replace("__DATASETS_JSON__", json.dumps(datasets, separators=(',', ':')))
            .replace("__TOTAL__", str(total))
            .replace("__BUILD_DATE__", build_date))


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oxylabs.io Topic Map</title>
<link rel="icon" type="image/webp" href="Oxylabs_logo.webp">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif; background: #0a0e1a; color: #e8edf5; }
  .header { position: fixed; top: 0; left: 0; right: 0; padding: 14px 24px; background: rgba(10,14,26,0.92); backdrop-filter: blur(12px); z-index: 100; border-bottom: 1px solid rgba(255,255,255,0.06); }
  .header h1 { font-size: 17px; font-weight: 600; margin-bottom: 3px; letter-spacing: -0.01em; }
  .header .subtitle { font-size: 12px; color: #8893a8; }
  .header .build { font-size: 10px; color: #5a6378; margin-top: 4px; }
  .stats { position: fixed; top: 80px; left: 16px; z-index: 50; display: flex; flex-direction: column; gap: 6px; width: 240px; }
  .stat-card { background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 12px; }
  .stat-card .name { font-size: 11px; font-weight: 500; color: #b8c2d6; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; }
  .stat-card .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .stat-card .count { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }
  .stat-card .clicks-sub { font-size: 11px; font-weight: 400; color: #8893a8; margin-left: 2px; }
  .stat-card .share { font-size: 10px; color: #8893a8; }
  .legend { position: fixed; bottom: 16px; left: 16px; background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 14px; font-size: 11px; color: #b8c2d6; max-width: 280px; z-index: 50; line-height: 1.5; }
  .legend strong { color: #e8edf5; font-size: 12px; display: block; margin-bottom: 4px; }
  .controls { position: fixed; top: 80px; right: 16px; display: flex; gap: 6px; z-index: 50; align-items: center; }
  .btn { background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); color: #e8edf5; padding: 7px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
  .btn:hover { background: rgba(40,50,75,0.95); border-color: rgba(255,255,255,0.2); }
  .range-picker { display: flex; gap: 2px; background: rgba(10,14,26,0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 7px; padding: 3px; }
  .range-btn { background: transparent; border: none; color: #8893a8; padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; letter-spacing: 0.02em; }
  .range-btn:hover { color: #e8edf5; background: rgba(255,255,255,0.06); }
  .range-btn.active { background: rgba(50,70,120,0.9); color: #fff; border: 1px solid rgba(100,150,255,0.35); }
  .range-btn.no-data { opacity: 0.45; }
  .search-wrap { display: flex; align-items: center; gap: 3px; background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 4px 8px; }
  .search-input { background: none; border: none; color: #e8edf5; font-size: 12px; font-family: inherit; outline: none; width: 148px; }
  .search-input::placeholder { color: #5a6378; }
  .search-input:focus { width: 180px; transition: width 0.2s; }
  .search-count { font-size: 11px; color: #8893a8; white-space: nowrap; min-width: 36px; text-align: center; }
  .search-count.no-match { color: #c0392b; }
  .search-nav { background: none; border: none; color: #8893a8; cursor: pointer; padding: 1px 4px; font-size: 13px; line-height: 1; border-radius: 3px; transition: color 0.15s; }
  .search-nav:hover:not(:disabled) { color: #e8edf5; background: rgba(255,255,255,0.08); }
  .search-nav:disabled { opacity: 0.2; cursor: default; }
  .node.search-dim { opacity: 0.1; pointer-events: none; }
  .node.search-match > circle { stroke: rgba(255,255,255,0.85) !important; stroke-width: 3px !important; }
  .node.search-current > circle { stroke: #fff !important; stroke-width: 4px !important; filter: drop-shadow(0 0 8px rgba(255,255,255,0.7)); }
  #viz { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
  .link { fill: none; stroke-width: 1.5px; }
  .node circle { stroke-width: 2px; cursor: pointer; transition: r 0.15s, stroke 0.15s; }
  .node:hover circle { stroke: #fff !important; }
  .node text { font-size: 12px; fill: #e8edf5; pointer-events: none; font-weight: 500; paint-order: stroke; stroke: #0a0e1a; stroke-width: 4px; stroke-linecap: round; stroke-linejoin: round; }
  .node text.inner { font-size: 9px; fill: #fff; stroke: none; paint-order: normal; font-weight: 700; letter-spacing: -0.03em; }
  .node.root > circle { fill: #fff; stroke: #fff; }
  .node.root > text { font-size: 14px; font-weight: 700; }
  .node.root > text.inner { fill: #0a0e1a; font-size: 10px; }
  .node.group > text { font-size: 13px; font-weight: 600; }
  .panel { position: fixed; right: 16px; top: 110px; bottom: 16px; width: 460px; background: rgba(20,26,42,0.96); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 18px; z-index: 90; display: none; flex-direction: column; }
  .panel.open { display: flex; }
  .panel h2 { font-size: 15px; margin-bottom: 3px; padding-right: 24px; }
  .panel .meta { font-size: 11px; color: #8893a8; margin-bottom: 14px; }
  .panel .close { position: absolute; top: 10px; right: 10px; background: none; border: none; color: #8893a8; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 4px; line-height: 1; }
  .panel .close:hover { background: rgba(255,255,255,0.08); color: #fff; }
  .export-bar { display: flex; gap: 6px; margin-bottom: 10px; flex-shrink: 0; }
  .export-btn { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #b8c2d6; padding: 5px 11px; border-radius: 5px; font-size: 11px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
  .export-btn:hover { background: rgba(255,255,255,0.12); color: #fff; border-color: rgba(255,255,255,0.25); }
  .panel .urls { overflow-y: auto; flex: 1; }
  .url-table { width: 100%; border-collapse: collapse; font-size: 11px; }
  .url-table th { text-align: left; color: #8893a8; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.1); position: sticky; top: 0; background: rgba(20,26,42,0.98); white-space: nowrap; z-index: 1; }
  .url-table th.num { text-align: right; }
  .url-table th.sortable { cursor: pointer; user-select: none; }
  .url-table th.sortable:hover { color: #c8d2e6; background: rgba(255,255,255,0.05); }
  .url-table th.sort-active { color: #7b9fd4; }
  .sort-ind { margin-left: 3px; font-size: 9px; opacity: 0.3; }
  .sort-active .sort-ind { opacity: 1; }
  .url-table td { padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); vertical-align: middle; }
  .url-table td.num { text-align: right; color: #b8c2d6; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .url-table td.pos { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .url-table tr:hover td { background: rgba(255,255,255,0.04); }
  .url-link { color: #b8c2d6; text-decoration: none; word-break: break-all; line-height: 1.4; display: block; }
  .url-link:hover { color: #fff; text-decoration: underline; }
  .pos-good { color: #27AE60; }
  .pos-mid { color: #F39C12; }
  .pos-low { color: #8893a8; }
  .badge-new { display: inline-block; background: #27AE60; color: #fff; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; margin-left: 5px; letter-spacing: 0.04em; vertical-align: middle; text-transform: uppercase; line-height: 1.6; }
  .node text.new-label { font-size: 8px; fill: #27AE60; stroke: none; paint-order: normal; font-weight: 800; letter-spacing: 0.06em; }
  .tooltip { position: fixed; background: rgba(15,20,35,0.98); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.15); padding: 8px 12px; border-radius: 6px; font-size: 11px; pointer-events: none; opacity: 0; transition: opacity 0.15s; z-index: 200; max-width: 240px; }
  .tooltip.visible { opacity: 1; }
  .tooltip strong { font-size: 12px; display: block; margin-bottom: 2px; }
  .tooltip .hint { color: #8893a8; font-size: 10px; margin-top: 3px; }
  .tooltip .metric { color: #b8c2d6; }
</style>
</head>
<body>
<div class="header">
  <h1>Oxylabs.io — Full Website Topic Map</h1>
  <div class="subtitle" id="subtitle"></div>
  <div class="build">Last rebuilt: __BUILD_DATE__ (rebuilds daily via GitHub Actions)</div>
</div>
<div class="stats" id="stats"></div>
<div class="controls">
  <div class="search-wrap">
    <input type="text" id="search-input" class="search-input" placeholder="Search nodes…" oninput="onSearch(this.value)" onkeydown="onSearchKey(event)" autocomplete="off" spellcheck="false">
    <span id="search-count" class="search-count"></span>
    <button class="search-nav" id="search-prev" onclick="searchNav(-1)" disabled title="Previous (Shift+Enter)">↑</button>
    <button class="search-nav" id="search-next" onclick="searchNav(1)" disabled title="Next (Enter)">↓</button>
  </div>
  <div class="range-picker" id="range-picker">
    <button class="range-btn" data-range="7d" onclick="switchRange('7d')">7d</button>
    <button class="range-btn" data-range="28d" onclick="switchRange('28d')">28d</button>
    <button class="range-btn" data-range="90d" onclick="switchRange('90d')">90d</button>
  </div>
  <button class="btn" onclick="expandAll()">Expand all</button>
  <button class="btn" onclick="collapseAll()">Collapse</button>
  <button class="btn" onclick="resetView()">Reset</button>
</div>
<div class="legend">
  <strong>How to read this</strong>
  <span id="legend-hint"></span>
</div>
<svg id="viz"></svg>
<div class="panel" id="panel">
  <button class="close" onclick="closePanel()">&#xD7;</button>
  <h2 id="panel-title"></h2>
  <div class="meta" id="panel-meta"></div>
  <div class="export-bar">
    <button class="export-btn" onclick="exportCSV()">&#8595; CSV</button>
    <button class="export-btn" onclick="exportXLSX()">&#8595; XLSX</button>
  </div>
  <div class="urls" id="panel-urls"></div>
</div>
<div class="tooltip" id="tooltip"></div>
<script>
let _exportRows = [];
let _exportTitle = '';

const DATASETS = __DATASETS_JSON__;
const TOTAL = __TOTAL__;
const RANGE_KEYS = ['7d', '28d', '90d'];
let activeKey = RANGE_KEYS.find(k => DATASETS[k].total_clicks > 0) || '90d';
let USE_CLICKS = false;
let root;

function fmtK(n) {
  if (!n) return '0';
  if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'k';
  return n.toLocaleString();
}

// ---------- Search ----------
let _searchQuery = '';
let _searchMatches = [];
let _searchIdx = 0;

function allNodes(node, result = []) {
  result.push(node);
  (node.children || node._children || []).forEach(c => allNodes(c, result));
  return result;
}

function onSearch(q) {
  _searchQuery = q.trim().toLowerCase();
  _searchMatches = _searchQuery
    ? allNodes(root).filter(d => d.depth > 0 && d.data.name.toLowerCase().includes(_searchQuery))
    : [];
  _searchIdx = 0;
  updateSearchCount();
  update(root);
  if (_searchMatches.length > 0) revealAndZoom(_searchMatches[0]);
}

function onSearchKey(e) {
  if (e.key === 'Enter') { e.preventDefault(); searchNav(e.shiftKey ? -1 : 1); }
  if (e.key === 'Escape') { document.getElementById('search-input').value = ''; onSearch(''); }
}

function searchNav(dir) {
  if (!_searchMatches.length) return;
  _searchIdx = (_searchIdx + dir + _searchMatches.length) % _searchMatches.length;
  updateSearchCount();
  revealAndZoom(_searchMatches[_searchIdx]);
}

function updateSearchCount() {
  const el = document.getElementById('search-count');
  const prev = document.getElementById('search-prev');
  const next = document.getElementById('search-next');
  if (!_searchQuery) {
    el.textContent = ''; el.className = 'search-count';
    prev.disabled = next.disabled = true;
  } else if (_searchMatches.length === 0) {
    el.textContent = 'No match'; el.className = 'search-count no-match';
    prev.disabled = next.disabled = true;
  } else {
    el.textContent = `${_searchIdx + 1} / ${_searchMatches.length}`; el.className = 'search-count';
    prev.disabled = next.disabled = false;
  }
}

function revealAndZoom(d) {
  let node = d;
  while (node.parent) {
    if (node.parent._children) { node.parent.children = node.parent._children; node.parent._children = null; }
    node = node.parent;
  }
  update(root);
  setTimeout(() => {
    const scale = 1.6;
    const tx = -d.y * scale;
    const ty = -d.x * scale;
    svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }, 420);
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  _searchQuery = ''; _searchMatches = []; _searchIdx = 0;
  updateSearchCount();
}
// ---------- End Search ----------

function renderStats() {
  const ds = DATASETS[activeKey];
  USE_CLICKS = ds.total_clicks > 0;
  const statsEl = document.getElementById('stats');
  statsEl.innerHTML = '';
  const totalCard = document.createElement('div');
  totalCard.className = 'stat-card';
  totalCard.innerHTML = `<div class="name">Total indexed</div><div class="count">${TOTAL.toLocaleString()} <span class="clicks-sub">URLs</span></div><div class="share">${USE_CLICKS ? fmtK(ds.total_clicks) + ' clicks · ' + ds.label : 'No GSC data for this range'}</div>`;
  statsEl.appendChild(totalCard);
  ds.group_summary.forEach(g => {
    const el = document.createElement('div');
    el.className = 'stat-card';
    const clicksBadge = (USE_CLICKS && g.clicks > 0) ? ` <span class="clicks-sub">· ${fmtK(g.clicks)} clicks</span>` : '';
    const clicksShare = (USE_CLICKS && g.clicks_share > 0) ? ` · ${g.clicks_share}% of clicks` : '';
    el.innerHTML = `<div class="name"><span class="dot" style="background:${g.color}"></span>${g.name}</div><div class="count">${g.count.toLocaleString()}${clicksBadge}</div><div class="share">${g.share}% of URLs${clicksShare}</div>`;
    statsEl.appendChild(el);
  });
}

function updateSubtitle() {
  const ds = DATASETS[activeKey];
  const clicksLabel = ds.total_clicks > 0 ? fmtK(ds.total_clicks) + ' clicks · ' + ds.label : 'no GSC data';
  document.getElementById('subtitle').textContent = `${TOTAL} URLs · ${clicksLabel}. Click nodes to expand. Drag to pan, scroll to zoom.`;
}

function updateLegend() {
  const ds = DATASETS[activeKey];
  document.getElementById('legend-hint').textContent = ds.total_clicks > 0
    ? `Bubble size = clicks (${ds.label}). Number inside bubble = total clicks. Click any node to expand, or leaf nodes to see page-level data.`
    : 'Bubble size = URL count. Click any node to expand, or leaf nodes to see page-level data.';
}

const width = window.innerWidth, height = window.innerHeight;
const dy = 300;

function computeDx() {
  let maxR = 12;
  root.descendants().forEach(d => { const r = nodeRadius(d); if (r > maxR) maxR = r; });
  return maxR * 2 + 20;
}

const svg = d3.select("#viz")
  .attr("width", width).attr("height", height)
  .attr("viewBox", [-width/2, -height/2, width, height])
  .style("user-select", "none");

const gZoom = svg.append("g");
const gLinks = gZoom.append("g").attr("fill", "none");
const gNodes = gZoom.append("g");

const zoom = d3.zoom().scaleExtent([0.2, 3])
  .on("zoom", (event) => gZoom.attr("transform", event.transform));
svg.call(zoom);

function initTree() {
  const ds = DATASETS[activeKey];
  USE_CLICKS = ds.total_clicks > 0;
  gLinks.selectAll('*').remove();
  gNodes.selectAll('*').remove();
  root = d3.hierarchy(ds.tree);
  root.x0 = 0; root.y0 = 0;
  root.children.forEach(groupNode => {
    const color = groupNode.data.color;
    groupNode.each(n => n.groupColor = color);
  });
  root.sum(d => USE_CLICKS ? (d.clicks || 0) : (d.count || 0));
  root.descendants().forEach(d => {
    if (d.depth >= 1 && d.children) { d._children = d.children; d.children = null; }
  });
  if (root._children) { root.children = root._children; root._children = null; }
  update(root);
  setTimeout(fitToView, 100);
}

function switchRange(key) {
  if (key === activeKey) return;
  activeKey = key;
  document.querySelectorAll('.range-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === key);
  });
  closePanel();
  clearSearch();
  updateSubtitle();
  updateLegend();
  renderStats();
  initTree();
}

function nodeRadius(d) {
  if (d.depth === 0) {
    if (!USE_CLICKS || !d.value) return 22;
    return Math.max(22, Math.min(52, Math.log10(d.value + 1) * 10));
  }
  const v = d.value || 0;
  if (!USE_CLICKS || v === 0) {
    return Math.max(5, Math.min(32, Math.sqrt(v || 1) * 1.4));
  }
  return Math.max(4, Math.min(42, Math.log10(v + 1) * 8));
}

function update(source) {
  d3.tree().nodeSize([computeDx(), dy])(root);
  const nodes = root.descendants(), links = root.links();

  const link = gLinks.selectAll("path.link")
    .data(links, d => d.target.data.name + "@" + d.target.depth + "@" + (d.target.parent ? d.target.parent.data.name : ""));
  link.enter().append("path")
    .attr("class", "link")
    .attr("stroke", d => d.target.groupColor || "rgba(255,255,255,0.2)")
    .attr("stroke-opacity", 0.35)
    .attr("d", () => { const o = {x: source.x0 ?? 0, y: source.y0 ?? 0}; return diagonal({source: o, target: o}); })
    .merge(link).transition().duration(400).attr("d", diagonal);
  link.exit().transition().duration(400)
    .attr("d", () => { const o = {x: source.x, y: source.y}; return diagonal({source: o, target: o}); })
    .remove();

  const node = gNodes.selectAll("g.node")
    .data(nodes, d => d.data.name + "@" + d.depth + "@" + (d.parent ? d.parent.data.name : "root"));
  const nodeEnter = node.enter().append("g")
    .attr("class", d => "node " + (d.depth === 0 ? "root" : d.depth === 1 ? "group" : ""))
    .attr("transform", () => `translate(${source.y0 ?? 0},${source.x0 ?? 0})`)
    .attr("opacity", 0).style("cursor", "pointer");

  nodeEnter.append("circle")
    .attr("r", d => nodeRadius(d))
    .attr("fill", d => d.depth === 0 ? "#fff" : (d.groupColor || "#666"))
    .attr("stroke", d => d.depth === 0 ? "#fff" : (d.groupColor || "#666"))
    .attr("fill-opacity", d => d._children ? 0.4 : 1);

  nodeEnter.append("text")
    .attr("class", "inner")
    .attr("dy", "0.35em")
    .attr("text-anchor", "middle")
    .attr("x", 0);

  nodeEnter.append("text")
    .attr("class", "outer")
    .attr("dy", "0.31em")
    .attr("x", d => (d._children || d.children) && d.depth > 0 ? -nodeRadius(d) - 6 : nodeRadius(d) + 6)
    .attr("text-anchor", d => (d._children || d.children) && d.depth > 0 ? "end" : "start")
    .text(d => {
      let label = d.data.name;
      if (d.data.count) label += ` (${d.data.count})`;
      return label;
    });

  nodeEnter.append("text")
    .attr("class", "new-label")
    .attr("x", 0)
    .attr("text-anchor", "middle")
    .attr("y", d => -(nodeRadius(d) + 4))
    .text(d => d.data.new_count ? 'NEW' : '');

  nodeEnter.on("click", (event, d) => {
    if (d.depth === 0) return;
    if (d.children || d._children) {
      if (d.children) { d._children = d.children; d.children = null; }
      else { d.children = d._children; d._children = null; }
      update(d);
    } else if (d.data.urls) { showUrls(d); }
  });
  nodeEnter.on("mouseenter", (event, d) => showTooltip(event, d))
    .on("mousemove", (event) => moveTooltip(event))
    .on("mouseleave", hideTooltip);

  const nodeUpdate = nodeEnter.merge(node);
  nodeUpdate.transition().duration(400)
    .attr("transform", d => `translate(${d.y},${d.x})`)
    .attr("opacity", 1);
  nodeUpdate.select("circle")
    .attr("r", d => nodeRadius(d))
    .attr("fill-opacity", d => d._children ? 0.4 : 1);
  const matchSet = new Set(_searchMatches);
  nodeUpdate
    .classed("search-match", d => matchSet.has(d))
    .classed("search-current", d => d === _searchMatches[_searchIdx])
    .classed("search-dim", d => _searchQuery.length > 0 && matchSet.size > 0 && !matchSet.has(d));
  nodeUpdate.select("text.inner")
    .text(d => {
      if (!USE_CLICKS || !d.value) return '';
      return nodeRadius(d) >= 12 ? fmtK(d.value) : '';
    });
  nodeUpdate.select("text.outer")
    .attr("x", d => (d._children || d.children) && d.depth > 0 ? -nodeRadius(d) - 6 : nodeRadius(d) + 6)
    .attr("text-anchor", d => (d._children || d.children) && d.depth > 0 ? "end" : "start");

  nodeUpdate.select("text.new-label")
    .attr("y", d => -(nodeRadius(d) + 4));

  node.exit().transition().duration(400)
    .attr("transform", () => `translate(${source.y},${source.x})`)
    .attr("opacity", 0).remove();
  root.each(d => { d.x0 = d.x; d.y0 = d.y; });
}

function diagonal(d) {
  return `M${d.source.y},${d.source.x} C${(d.source.y+d.target.y)/2},${d.source.x} ${(d.source.y+d.target.y)/2},${d.target.x} ${d.target.y},${d.target.x}`;
}

function expandAll() {
  root.each(d => { if (d._children) { d.children = d._children; d._children = null; } });
  update(root); setTimeout(fitToView, 450);
}
function collapseAll() {
  root.each(d => { if (d.depth >= 1 && d.children) { d._children = d.children; d.children = null; } });
  update(root); setTimeout(fitToView, 450);
}
function resetView() { fitToView(); }

function fitToView() {
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  root.descendants().forEach(d => {
    if (d.x<x0) x0=d.x; if (d.x>x1) x1=d.x;
    if (d.y<y0) y0=d.y; if (d.y>y1) y1=d.y;
  });
  const bw=(y1-y0)+300, bh=(x1-x0)+100;
  const scale = Math.min(0.95, (width-280)/bw, (height-140)/bh);
  const tx = -((y0+y1)/2)*scale + (width/2 - 140) - width/2;
  const ty = -((x0+x1)/2)*scale;
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(tx,ty).scale(scale));
}

const tooltip = document.getElementById('tooltip');
function showTooltip(event, d) {
  if (d.depth === 0) return;
  const urlCount = d.data.count || (d.data.urls ? d.data.urls.length : 0);
  const clicks = d.value || 0;
  const hasChildren = d._children || d.children;
  let html = `<strong>${d.data.name}</strong>`;
  html += `<span class="metric">${urlCount} URL${urlCount===1?'':'s'}`;
  if (USE_CLICKS && clicks > 0) html += ` · ${fmtK(clicks)} clicks`;
  if (d.data.new_count) html += ` · <span style="color:#27AE60;font-weight:700">${d.data.new_count} new</span>`;
  html += `</span>`;
  html += `<div class="hint">${hasChildren ? 'Click to ' + (d.children ? 'collapse' : 'expand') : 'Click to view page data'}</div>`;
  tooltip.innerHTML = html;
  moveTooltip(event);
  tooltip.classList.add('visible');
}
function moveTooltip(event) {
  tooltip.style.left = (event.clientX + 14) + 'px';
  tooltip.style.top = (event.clientY + 14) + 'px';
}
function hideTooltip() { tooltip.classList.remove('visible'); }

function posClass(p) {
  if (p === null || p === undefined) return 'pos-low';
  if (p <= 10) return 'pos-good';
  if (p <= 30) return 'pos-mid';
  return 'pos-low';
}

function buildExportRows(urls) {
  if (USE_CLICKS) {
    return urls.map(u => ({
      URL: u.url,
      Clicks: u.clicks || 0,
      Impressions: u.impressions || 0,
      'Avg Position': u.position !== null && u.position !== undefined ? u.position : '',
    }));
  }
  return urls.map(u => ({ URL: typeof u === 'string' ? u : u.url }));
}

function slugify(s) { return s.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '').toLowerCase(); }

function exportCSV() {
  if (!_exportRows.length) return;
  const headers = Object.keys(_exportRows[0]);
  const lines = [headers.join(','), ..._exportRows.map(r =>
    headers.map(h => { const v = r[h]; return typeof v === 'string' && v.includes(',') ? `"${v}"` : v; }).join(',')
  )];
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `oxylabs_${slugify(_exportTitle)}.csv`;
  a.click();
}

function exportXLSX() {
  if (!_exportRows.length) return;
  const ws = XLSX.utils.json_to_sheet(_exportRows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, _exportTitle.slice(0, 31));
  XLSX.writeFile(wb, `oxylabs_${slugify(_exportTitle)}.xlsx`);
}

let _currentUrls = [];
let _sortCol = null;
let _sortDir = -1;

function sortUrls(urls, col, dir) {
  if (!col) return urls;
  return [...urls].sort((a, b) => {
    if (col === 'url') {
      const av = (a.url || '').replace('https://oxylabs.io', '');
      const bv = (b.url || '').replace('https://oxylabs.io', '');
      return dir * av.localeCompare(bv);
    }
    const av = (a[col] == null) ? (col === 'position' ? 9999 : -1) : a[col];
    const bv = (b[col] == null) ? (col === 'position' ? 9999 : -1) : b[col];
    return dir * (av - bv);
  });
}

function buildTableHeader() {
  function th(col, label, cls) {
    const active = _sortCol === col;
    const arrow = active ? (_sortDir === -1 ? ' ↓' : ' ↑') : ' ↕';
    const activeCls = active ? ' sort-active' : '';
    return `<th class="${cls}sortable${activeCls}" onclick="sortBy('${col}')">${label}<span class="sort-ind">${arrow}</span></th>`;
  }
  let html = th('url', 'URL', '');
  if (USE_CLICKS) {
    html += th('clicks', 'Clicks', 'num ');
    html += th('impressions', 'Impr.', 'num ');
    html += th('position', 'Avg Pos', 'num ');
  }
  return `<thead><tr>${html}</tr></thead>`;
}

function renderTableBody() {
  const tbody = document.querySelector('#panel-urls .url-table tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  sortUrls(_currentUrls, _sortCol, _sortDir).forEach(item => {
    const url = typeof item === 'string' ? item : item.url;
    const path = url.replace('https://oxylabs.io', '') || '/';
    const tr = document.createElement('tr');
    const newBadge = item.is_new ? '<span class="badge-new">new</span>' : '';
    let cells = `<td><a href="${url}" target="_blank" rel="noopener" class="url-link">${path}</a>${newBadge}</td>`;
    if (USE_CLICKS) {
      const pos = item.position;
      const noData = item.is_new && !item.clicks && !item.impressions;
      cells += `<td class="num">${noData ? '—' : (item.clicks || 0).toLocaleString()}</td>`;
      cells += `<td class="num">${noData ? '—' : (item.impressions || 0).toLocaleString()}</td>`;
      cells += `<td class="pos ${noData ? 'pos-low' : posClass(pos)}">${noData ? '—' : (pos !== null && pos !== undefined) ? pos.toFixed(1) : '—'}</td>`;
    }
    tr.innerHTML = cells;
    tbody.appendChild(tr);
  });
}

function sortBy(col) {
  _sortDir = (_sortCol === col) ? _sortDir * -1 : (col === 'url' ? 1 : -1);
  _sortCol = col;
  const table = document.querySelector('#panel-urls .url-table');
  table.querySelector('thead').remove();
  table.insertAdjacentHTML('afterbegin', buildTableHeader());
  renderTableBody();
  _exportRows = buildExportRows(sortUrls(_currentUrls, _sortCol, _sortDir));
}

function showUrls(d) {
  _currentUrls = d.data.urls || [];
  _sortCol = USE_CLICKS ? 'clicks' : 'url';
  _sortDir = USE_CLICKS ? -1 : 1;
  _exportTitle = d.data.name;
  _exportRows = buildExportRows(_currentUrls);

  document.getElementById('panel-title').textContent = d.data.name;
  const totalClicks = _currentUrls.reduce((s, u) => s + (u.clicks || 0), 0);
  const totalImpr = _currentUrls.reduce((s, u) => s + (u.impressions || 0), 0);
  let meta = `${_currentUrls.length} URL${_currentUrls.length === 1 ? '' : 's'}`;
  if (USE_CLICKS && totalClicks > 0) meta += ` · ${fmtK(totalClicks)} clicks · ${fmtK(totalImpr)} impressions`;
  meta += ` · ${d.parent.data.name}`;
  document.getElementById('panel-meta').textContent = meta;

  const urlsEl = document.getElementById('panel-urls');
  urlsEl.innerHTML = '';
  const table = document.createElement('table');
  table.className = 'url-table';
  table.innerHTML = buildTableHeader();
  table.appendChild(document.createElement('tbody'));
  urlsEl.appendChild(table);
  renderTableBody();

  document.getElementById('panel').classList.add('open');
}
function closePanel() { document.getElementById('panel').classList.remove('open'); }

// Mark range buttons with no data
RANGE_KEYS.forEach(k => {
  const btn = document.querySelector(`.range-btn[data-range="${k}"]`);
  if (btn && DATASETS[k].total_clicks === 0) btn.classList.add('no-data');
});

// Set initial active button
document.querySelectorAll('.range-btn').forEach(btn => {
  btn.classList.toggle('active', btn.dataset.range === activeKey);
});

updateSubtitle();
updateLegend();
renderStats();
initTree();

window.addEventListener('resize', () => {
  const w = window.innerWidth, h = window.innerHeight;
  svg.attr("width", w).attr("height", h).attr("viewBox", [-w/2, -h/2, w, h]);
  fitToView();
});
</script>
</body>
</html>'''


def main():
    print(f"Fetching sitemap from {SITEMAP_URL}...")
    xml = fetch_sitemap(SITEMAP_URL)
    urls = sorted(set(re.findall(r'<loc>(.*?)</loc>', xml)))
    urls = [u for u in urls if u.strip() and u != "https://oxylabs.io/"]
    print(f"Found {len(urls)} unique URLs in sitemap.")

    urls = [u for u in urls if not is_excluded(u)]
    print(f"After excluding noise (legal, pagination, press): {len(urls)}")

    known_urls = load_known_urls()
    new_urls = get_new_url_set(urls, known_urls)
    save_known_urls(known_urls)
    print(f"New URLs (added in last 7d): {len(new_urls)}")

    datasets = {}
    total = None
    for key in RANGE_KEYS:
        print(f"Loading GSC cache ({key})...")
        gsc = load_gsc_metrics(key)
        if gsc:
            print(f"  {len(gsc):,} URLs with metrics.")
        else:
            print(f"  No data — bubbles will reflect URL counts for this range.")
        tree = build_tree(urls, gsc=gsc, new_urls=new_urls)
        t, total_clicks, group_summary = compute_stats(tree)
        if total is None:
            total = t
        datasets[key] = {
            "tree": tree,
            "total_clicks": total_clicks,
            "group_summary": group_summary,
            "label": RANGE_LABELS[key],
        }
        print(f"  total_clicks={total_clicks:,}")

    build_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = generate_html(datasets, total, build_date)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK. Wrote index.html ({len(html):,} bytes).")
    print(f"Total URLs indexed: {total}")
    for key, ds in datasets.items():
        print(f"  {key}: {ds['total_clicks']:,} clicks")


if __name__ == "__main__":
    main()
