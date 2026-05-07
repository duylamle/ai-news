"""Fetch articles from a source defined in sources.json.

Output: JSON array on stdout, max 10 newest articles published in last 48h.
Each item: {title, url, date, excerpt}.

Usage:
    python scripts/fetch.py --source-id anthropic-news --state state.json --sources sources.json
"""

import argparse
import hashlib
import html
import io
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import requests
from bs4 import BeautifulSoup

# Force UTF-8 stdout/stderr on Windows so emojis from feeds don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

USER_AGENT = "ai-news-aggregator/1.0 (+https://github.com/duylamle/ai-news)"
MAX_ARTICLES = 30  # raised because 1 fetch/day model — pull more per run
DEFAULT_WINDOW_HOURS = 168  # 7 days; sources can override via recency_hours
MAX_EXCERPT_CHARS = 1000  # cap excerpt length to avoid wall-of-text in UI
MAX_LOOKBACK_DAYS = 30  # absolute cap on how far back to look (overrides last_fetched if older)


def canonical_url(url: str) -> str:
    """Strip UTM params, fragment, trailing slash."""
    parsed = urlparse(url)
    query_parts = [p for p in parsed.query.split("&") if p and not p.startswith("utm_")]
    cleaned = parsed._replace(query="&".join(query_parts), fragment="")
    out = urlunparse(cleaned).rstrip("/")
    return out


def article_id(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:12]


def parse_date(value) -> str | None:
    """Return ISO date YYYY-MM-DD or None."""
    if not value:
        return None
    if hasattr(value, "tm_year"):
        return f"{value.tm_year:04d}-{value.tm_mon:02d}-{value.tm_mday:02d}"
    if isinstance(value, str):
        v = value.strip()
        formats = [
            ("%Y-%m-%dT%H:%M:%S", 19),
            ("%Y-%m-%d", 10),
            ("%a, %d %b %Y %H:%M:%S %Z", None),
            ("%a, %d %b %Y %H:%M:%S %z", None),
            ("%a, %d %b %Y %H:%M:%S GMT", None),
        ]
        for fmt, slice_len in formats:
            sample = v[:slice_len] if slice_len else v
            try:
                dt = datetime.strptime(sample, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def is_recent(iso_date: str | None, window_hours: int = DEFAULT_WINDOW_HOURS) -> bool:
    if not iso_date:
        return True
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return dt >= cutoff


def clean_excerpt(text: str, max_chars: int | None = None) -> str:
    """Strip tags, decode HTML entities (&#272; → Đ), collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def fetch_rss(feed_url: str, window_hours: int = DEFAULT_WINDOW_HOURS) -> list[dict]:
    feed = feedparser.parse(feed_url, agent=USER_AGENT)
    out = []
    # When window_hours is large (since-last-fetch), allow more entries
    max_to_check = max(MAX_ARTICLES * 3, 100)
    for entry in feed.entries[:max_to_check]:
        date = parse_date(entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published"))
        if not is_recent(date, window_hours):
            continue
        out.append({
            "title": entry.get("title", "").strip(),
            "url": canonical_url(entry.get("link", "")),
            "date": date,
            "excerpt": clean_excerpt(entry.get("summary") or entry.get("description") or "", MAX_EXCERPT_CHARS),
        })
        if len(out) >= MAX_ARTICLES:
            break
    return out


def fetch_html_listing(url: str, link_selector: str | None = None) -> list[dict]:
    """Scrape an HTML listing page for article links + meta."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    listing_path = urlparse(url).path.rstrip("/")

    # Filter out navigation noise: skip generic single-word links, anchor links, common nav patterns
    NAV_KEYWORDS = {
        "research", "news", "blog", "company", "products", "pricing", "about", "contact",
        "careers", "login", "signup", "home", "explore", "discover", "publications",
        "team", "models", "api", "docs", "documentation", "support", "help", "learn",
        "community", "events", "press",
    }

    candidates = []
    if link_selector:
        for a in soup.select(link_selector)[: MAX_ARTICLES * 3]:
            href = a.get("href")
            if href:
                candidates.append((a.get_text(strip=True), href))
    else:
        for a in soup.find_all("a", href=True)[:300]:
            href = a["href"]
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            if not any(p in href for p in ("/blog/", "/news/", "/posts/", "/article", "/research/", "/papers/", "/post/")):
                continue
            # Skip listing page itself or shorter parent paths
            href_path = urlparse(href if href.startswith("http") else base + href).path.rstrip("/")
            if href_path == listing_path or len(href_path) <= len(listing_path) + 1:
                continue
            title = a.get_text(strip=True)
            # Cap title length, filter nav keywords
            if not title or len(title) < 20 or len(title) > 250:
                continue
            if title.lower() in NAV_KEYWORDS:
                continue
            candidates.append((title, href))

    seen = set()
    out = []
    for title, href in candidates:
        full = href if href.startswith("http") else base + href
        cu = canonical_url(full)
        if cu in seen or cu == canonical_url(url):
            continue
        seen.add(cu)
        # Truncate title at common metadata separators (Anthropic-style "TitleProductDate")
        cleaned_title = re.split(r"\s{2,}", title)[0][:200].strip()
        out.append({"title": cleaned_title, "url": cu, "date": None, "excerpt": ""})
        if len(out) >= MAX_ARTICLES * 2:  # over-fetch, will filter by recency
            break

    enriched = []
    for item in out:
        try:
            page = requests.get(item["url"], headers={"User-Agent": USER_AGENT}, timeout=15)
            psoup = BeautifulSoup(page.text, "html.parser")

            # Prefer og:title for cleaner title
            og_title = psoup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                clean_t = og_title["content"].strip()
                if clean_t and len(clean_t) > 10:
                    item["title"] = clean_t[:200]

            # Excerpt
            og_desc = psoup.find("meta", property="og:description") or psoup.find("meta", attrs={"name": "description"})
            if og_desc and og_desc.get("content"):
                item["excerpt"] = clean_excerpt(og_desc["content"], MAX_EXCERPT_CHARS)
            else:
                article_el = psoup.find("article") or psoup.find("main")
                if article_el:
                    p = article_el.find("p")
                    if p:
                        item["excerpt"] = clean_excerpt(p.get_text(), MAX_EXCERPT_CHARS)

            # Date
            pub = (
                psoup.find("meta", property="article:published_time")
                or psoup.find("meta", attrs={"name": "publish_date"})
                or psoup.find("meta", attrs={"name": "publication_date"})
                or psoup.find("meta", attrs={"name": "date"})
                or psoup.find("time", attrs={"datetime": True})
            )
            if pub:
                date_str = pub.get("content") or pub.get("datetime")
                if date_str:
                    item["date"] = parse_date(date_str)

            enriched.append(item)
        except Exception:
            continue

    enriched = [a for a in enriched if a.get("excerpt") and is_recent(a.get("date"), DEFAULT_WINDOW_HOURS)]
    return enriched[:MAX_ARTICLES]


def compute_window_hours(source_meta: dict, state: dict, source_id: str) -> int:
    """Compute window based on last_fetched (since-last-run model).

    Logic:
      - If never fetched → use source's default recency_hours (or DEFAULT_WINDOW_HOURS)
      - If fetched before → window = now - last_fetched, capped at MAX_LOOKBACK_DAYS
      - Always at least source's recency_hours minimum (e.g. arxiv 48h)
    """
    default_window = source_meta.get("recency_hours", DEFAULT_WINDOW_HOURS)
    last_fetched_str = state.get(source_id, {}).get("last_fetched")
    if not last_fetched_str:
        return default_window

    try:
        # Strip timezone aware suffix for parsing
        last = datetime.fromisoformat(last_fetched_str.replace("Z", "+00:00"))
        if not last.tzinfo:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        hours_since = int(delta.total_seconds() / 3600) + 1  # +1 buffer
        # Cap at 30 days
        max_hours = MAX_LOOKBACK_DAYS * 24
        # At least the source's default window
        return max(default_window, min(hours_since, max_hours))
    except (ValueError, TypeError):
        return default_window


def fetch_source(source_id: str, source_meta: dict, state: dict | None = None) -> list[dict]:
    window_hours = compute_window_hours(source_meta, state or {}, source_id)
    print(f"[fetch] {source_id}: window={window_hours}h", file=sys.stderr)

    feed_url = source_meta.get("feed_url")
    if feed_url:
        try:
            return fetch_rss(feed_url, window_hours)
        except Exception as e:
            print(f"[fetch] RSS failed for {source_id}: {e}", file=sys.stderr)

    listing_url = source_meta.get("url")
    if listing_url:
        try:
            return fetch_html_listing(listing_url, source_meta.get("link_selector"))
        except Exception as e:
            print(f"[fetch] HTML scrape failed for {source_id}: {e}", file=sys.stderr)
    return []


def filter_dedup(articles: list[dict], state: dict, source_id: str) -> list[dict]:
    seen_urls = set(state.get(source_id, {}).get("seen_urls", []))
    return [a for a in articles if a["url"] not in seen_urls]


def update_fetch_history(state_path: Path, source_id: str, got_new: bool, source_meta: dict) -> None:
    """Track consecutive empty fetches; auto-flag inactive after threshold.

    Threshold by frequency:
    - quarterly: 4 consecutive empty fetches = 1 year silence → flag inactive
    - monthly: 12 consecutive empty fetches = 1 year silence → flag inactive
    - others (1-3/week): 26+ consecutive empty fetches (~6 months) → flag inactive
    """
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    bucket = state.setdefault(source_id, {})

    if got_new:
        bucket["consecutive_empty"] = 0
        bucket["last_success"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    else:
        bucket["consecutive_empty"] = bucket.get("consecutive_empty", 0) + 1

    freq = source_meta.get("frequency", 1)
    threshold_map = {"quarterly": 4, "monthly": 12}
    threshold = threshold_map.get(freq, 26)

    if bucket["consecutive_empty"] >= threshold:
        bucket["inactive_flagged_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        bucket["inactive_reason"] = (
            f"{bucket['consecutive_empty']} consecutive empty fetches "
            f"(threshold {threshold} for frequency={freq})"
        )

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--state", default="state.json")
    ap.add_argument("--sources", default="sources.json")
    args = ap.parse_args()

    sources_path = Path(args.sources)
    state_path = Path(args.state)

    if not sources_path.exists():
        print(f"[fetch] sources file not found: {sources_path}", file=sys.stderr)
        sys.exit(1)

    sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
    source_meta = sources_data.get("sources", {}).get(args.source_id)
    if not source_meta:
        print(f"[fetch] source-id not found in sources.json: {args.source_id}", file=sys.stderr)
        sys.exit(1)

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    articles = fetch_source(args.source_id, source_meta, state)
    fresh = filter_dedup(articles, state, args.source_id)

    for a in fresh:
        a["id"] = article_id(a["url"])
        a["source"] = args.source_id

    print(json.dumps(fresh, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
