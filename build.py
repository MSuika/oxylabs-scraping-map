#!/usr/bin/env python3
"""
Oxylabs Web Scraping Topic Map - Build Script

Fetches the live Oxylabs sitemap, classifies URLs into a topical hierarchy,
and generates a static index.html with an interactive D3-based mind map.

Run locally:  python build.py
In CI:        executed by .github/workflows/build.yml on a daily schedule.
"""

import re
import json
import sys
import datetime
from collections import defaultdict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

SITEMAP_URL = "https://oxylabs.io/sitemap.xml"
USER_AGENT = "OxylabsTopicMap/1.0 (+github.com/MSuika/oxylabs-scraping-map)"

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
    r'/blog/page/\d+', r'/blog/authors/', r'/legal/', r'/press-area',
    r'/oxycopilot-story', r'/sustainability', r'/risk-and-legal-compliance',
    r'/kyc-and-safety', r'/what-is-my-ip', r'/about-us', r'/affiliates',
    r'/blog/oxylabs-shortlisted', r'/blog/oxylabs-wins', r'/blog/oxylabs-announces',
    r'/blog/.*accreditation', r'/blog/.*-partnership', r'/blog/empowering-the-',
    r'/blog/authors$', r'/blog/cyber-insurance', r'/blog/code-university',
    r'/blog/ai4-conference', r'/blog/devworld-', r'/blog/conference-',
    r'/blog/2-weeks-until-oxycon', r'/oxycon/', r'/blog/oxycon',
    r'/project-4beta', r'/blog/free-white-paper',
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

    if slug.startswith('tools/'):     return ('Free Tools', 'Free scraping tools')
    if slug.startswith('features/'):  return ('Product Features', 'Feature pages')
    if slug.startswith('pricing'):    return ('Pricing', 'Pricing pages')

    # ===== RESOURCES =====
    if slug.startswith('resources/'):
        if 'error-codes' in slug:                                                              return ('Resources', 'API error code docs')
        if 'integrations' in slug:                                                             return ('Resources', 'Integrations')
        if 'prompts-code-samples' in slug:                                                     return ('Resources', 'AI prompts & code samples')
        if 'case-studies' in slug or 'case-study' in slug:                                     return ('Resources', 'Case studies')
        if 'ebooks' in slug or 'whitepapers' in slug or 'webinars' in slug or 'reports' in slug: return ('Resources', 'Ebooks/whitepapers/webinars')
        return ('Resources', 'Other resources')

    if slug.startswith('developers') or slug.startswith('oxycon'):
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
                     "Blog - Networking", "Blog - Other", "Blog hubs"]
    },
    "Resources & Docs": {
        "color": "#E74C3C",
        "clusters": ["Resources", "Developer / Community", "Pricing"]
    }
}


def build_tree(urls):
    clusters = defaultdict(lambda: defaultdict(list))
    for u in urls:
        primary, sub = classify(u)
        clusters[primary][sub].append(u)

    tree = {"name": "Oxylabs Web Scraping Coverage", "children": []}
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
                cluster_node["children"].append({
                    "name": sub_name, "count": len(sub_urls), "urls": sorted(sub_urls)
                })
            cluster_node["children"].sort(key=lambda x: -x["count"])
            group_node["children"].append(cluster_node)
        group_node["children"].sort(key=lambda x: -sum(c.get("count", 0) for c in x["children"]))
        tree["children"].append(group_node)
    tree["children"].sort(key=lambda x: -sum(c.get("count", 0) for c in x["children"]))
    return tree


def generate_html(tree, total, group_summary, build_date):
    tree_json = json.dumps(tree, separators=(',', ':'))
    return HTML_TEMPLATE.replace("__TREE_JSON__", tree_json) \
                        .replace("__GROUP_SUMMARY__", json.dumps(group_summary)) \
                        .replace("__TOTAL__", str(total)) \
                        .replace("__BUILD_DATE__", build_date)


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oxylabs Web Scraping Topic Map</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
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
  .stat-card .share { font-size: 10px; color: #8893a8; }
  .legend { position: fixed; bottom: 16px; left: 16px; background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 14px; font-size: 11px; color: #b8c2d6; max-width: 280px; z-index: 50; line-height: 1.5; }
  .legend strong { color: #e8edf5; font-size: 12px; display: block; margin-bottom: 4px; }
  .controls { position: fixed; top: 80px; right: 16px; display: flex; gap: 6px; z-index: 50; }
  .btn { background: rgba(20,26,42,0.92); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); color: #e8edf5; padding: 7px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
  .btn:hover { background: rgba(40,50,75,0.95); border-color: rgba(255,255,255,0.2); }
  #viz { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
  .link { fill: none; stroke-width: 1.5px; }
  .node circle { stroke-width: 2px; cursor: pointer; transition: r 0.15s, stroke 0.15s; }
  .node:hover circle { stroke: #fff !important; }
  .node text { font-size: 12px; fill: #e8edf5; pointer-events: none; font-weight: 500; paint-order: stroke; stroke: #0a0e1a; stroke-width: 4px; stroke-linecap: round; stroke-linejoin: round; }
  .node.root > circle { fill: #fff; stroke: #fff; }
  .node.root > text { font-size: 14px; font-weight: 700; }
  .node.group > text { font-size: 13px; font-weight: 600; }
  .panel { position: fixed; right: 16px; top: 110px; bottom: 16px; width: 360px; background: rgba(20,26,42,0.96); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 18px; z-index: 90; display: none; flex-direction: column; }
  .panel.open { display: flex; }
  .panel h2 { font-size: 15px; margin-bottom: 3px; }
  .panel .meta { font-size: 11px; color: #8893a8; margin-bottom: 14px; }
  .panel .close { position: absolute; top: 10px; right: 10px; background: none; border: none; color: #8893a8; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 4px; line-height: 1; }
  .panel .close:hover { background: rgba(255,255,255,0.08); color: #fff; }
  .panel .urls { overflow-y: auto; flex: 1; padding-right: 4px; }
  .panel .url-item { display: block; padding: 7px 9px; border-radius: 5px; color: #b8c2d6; font-size: 11px; text-decoration: none; margin-bottom: 1px; word-break: break-all; line-height: 1.4; transition: background 0.15s; }
  .panel .url-item:hover { background: rgba(255,255,255,0.06); color: #fff; }
  .tooltip { position: fixed; background: rgba(15,20,35,0.98); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.15); padding: 8px 12px; border-radius: 6px; font-size: 11px; pointer-events: none; opacity: 0; transition: opacity 0.15s; z-index: 200; max-width: 240px; }
  .tooltip.visible { opacity: 1; }
  .tooltip strong { font-size: 12px; display: block; margin-bottom: 2px; }
  .tooltip .hint { color: #8893a8; font-size: 10px; margin-top: 3px; }
</style>
</head>
<body>
<div class="header">
  <h1>Oxylabs - Web Scraping Topic Coverage Map</h1>
  <div class="subtitle">__TOTAL__ scraping-related URLs from oxylabs.io sitemap. Click nodes to expand. Drag to pan, scroll to zoom.</div>
  <div class="build">Last rebuilt: __BUILD_DATE__ (rebuilds daily via GitHub Actions)</div>
</div>
<div class="stats" id="stats"></div>
<div class="controls">
  <button class="btn" onclick="expandAll()">Expand all</button>
  <button class="btn" onclick="collapseAll()">Collapse</button>
  <button class="btn" onclick="resetView()">Reset</button>
</div>
<div class="legend">
  <strong>How to read this</strong>
  Circle size = # of pages. Click any colored node to expand it. Click smallest nodes (leaves) to see actual URLs.
</div>
<svg id="viz"></svg>
<div class="panel" id="panel">
  <button class="close" onclick="closePanel()">x</button>
  <h2 id="panel-title"></h2>
  <div class="meta" id="panel-meta"></div>
  <div class="urls" id="panel-urls"></div>
</div>
<div class="tooltip" id="tooltip"></div>
<script>
const TREE_DATA = __TREE_JSON__;
const GROUP_SUMMARY = __GROUP_SUMMARY__;
const TOTAL = __TOTAL__;

const statsEl = document.getElementById('stats');
const totalCard = document.createElement('div');
totalCard.className = 'stat-card';
totalCard.innerHTML = `<div class="name">Total scraping URLs</div><div class="count">${TOTAL.toLocaleString()}</div><div class="share">across 5 content groups</div>`;
statsEl.appendChild(totalCard);
GROUP_SUMMARY.forEach(g => {
  const el = document.createElement('div');
  el.className = 'stat-card';
  el.innerHTML = `<div class="name"><span class="dot" style="background:${g.color}"></span>${g.name}</div><div class="count">${g.count.toLocaleString()}</div><div class="share">${g.share}% of total</div>`;
  statsEl.appendChild(el);
});

const width = window.innerWidth, height = window.innerHeight;
const dx = 22, dy = 240;

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

const root = d3.hierarchy(TREE_DATA);
root.x0 = 0; root.y0 = 0;
root.children.forEach(groupNode => {
  const color = groupNode.data.color;
  groupNode.each(n => n.groupColor = color);
});
root.sum(d => d.count || 0);
root.descendants().forEach(d => {
  if (d.depth >= 1 && d.children) { d._children = d.children; d.children = null; }
});

function nodeRadius(d) {
  if (d.depth === 0) return 9;
  const v = d.value || 1;
  return Math.max(4, Math.min(20, Math.sqrt(v) * 0.9));
}

function update(source) {
  d3.tree().nodeSize([dx, dy])(root);
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
    .attr("dy", "0.31em")
    .attr("x", d => (d._children || d.children) && d.depth > 0 ? -nodeRadius(d) - 6 : nodeRadius(d) + 6)
    .attr("text-anchor", d => (d._children || d.children) && d.depth > 0 ? "end" : "start")
    .text(d => { let label = d.data.name; if (d.value) label += ` (${d.value})`; return label; });
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
  nodeUpdate.select("circle").attr("fill-opacity", d => d._children ? 0.4 : 1);
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
  const count = d.value || (d.data.urls ? d.data.urls.length : 0);
  const hasChildren = d._children || d.children;
  tooltip.innerHTML = `<strong>${d.data.name}</strong>${count} URL${count===1?'':'s'}<div class="hint">${hasChildren ? 'Click to ' + (d.children ? 'collapse' : 'expand') : 'Click to view URLs'}</div>`;
  moveTooltip(event); tooltip.classList.add('visible');
}
function moveTooltip(event) {
  tooltip.style.left = (event.clientX+14)+'px';
  tooltip.style.top = (event.clientY+14)+'px';
}
function hideTooltip() { tooltip.classList.remove('visible'); }

function showUrls(d) {
  document.getElementById('panel-title').textContent = d.data.name;
  document.getElementById('panel-meta').textContent = `${d.data.urls.length} URLs - ${d.parent.data.name}`;
  const urlsEl = document.getElementById('panel-urls'); urlsEl.innerHTML = '';
  d.data.urls.sort().forEach(url => {
    const a = document.createElement('a');
    a.className = 'url-item'; a.href = url; a.target = '_blank'; a.rel = 'noopener';
    a.textContent = url.replace('https://oxylabs.io', '');
    urlsEl.appendChild(a);
  });
  document.getElementById('panel').classList.add('open');
}
function closePanel() { document.getElementById('panel').classList.remove('open'); }

if (root._children) { root.children = root._children; root._children = null; }
update(root);
setTimeout(fitToView, 100);

window.addEventListener('resize', () => {
  const w=window.innerWidth, h=window.innerHeight;
  svg.attr("width",w).attr("height",h).attr("viewBox", [-w/2,-h/2,w,h]);
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

    tree = build_tree(urls)

    group_summary = []
    total = 0
    for g in tree["children"]:
        g_total = sum(ch["count"] for ch in g["children"])
        total += g_total
    for g in tree["children"]:
        g_total = sum(ch["count"] for ch in g["children"])
        group_summary.append({
            "name": g["name"], "count": g_total, "color": g["color"],
            "share": round(g_total/total*100, 1) if total else 0
        })

    build_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = generate_html(tree, total, group_summary, build_date)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK. Wrote index.html ({len(html):,} bytes).")
    print(f"Total scraping-related URLs: {total}")
    for g in group_summary:
        print(f"  {g['name']}: {g['count']} ({g['share']}%)")


if __name__ == "__main__":
    main()
