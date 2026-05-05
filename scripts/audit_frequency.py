"""Audit publication velocity of all sources by sampling RSS feed.

For each source with feed_url, count posts per week over last 60 days.
Recommend frequency tier: 3/week (high-volume), 2/week (medium),
1/week (low), or "drop" (DEAD if no posts in 180 days).

Output: pretty table + suggested frequency map.
"""

import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def parse_pub(s):
    if not s:
        return None
    if hasattr(s, "tm_year"):
        try:
            return datetime(s.tm_year, s.tm_mon, s.tm_mday, tzinfo=timezone.utc)
        except Exception:
            return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def recommend_frequency(posts_per_week: float, status: str):
    """Recommend frequency based on post velocity + activity status.

    Tiers:
      3 = high (3x/week, Mon/Wed/Fri)     ppw >= 5
      2 = medium (2x/week)                ppw 2-5
      1 = low (1x/week)                   ppw 0.5-2
      "monthly" = 1x/month                ppw 0.1-0.5
      "quarterly" = 1x/3-months           ppw < 0.1
      "drop" = inactive >180d             status DEAD
    """
    if status == "DEAD":
        return "drop"
    if posts_per_week >= 5:
        return 3
    if posts_per_week >= 2:
        return 2
    if posts_per_week >= 0.5:
        return 1
    if posts_per_week >= 0.1:
        return "monthly"
    return "quarterly"


def main():
    sources = json.loads(Path("sources.json").read_text(encoding="utf-8"))["sources"]
    now = datetime.now(timezone.utc)
    window = 60
    threshold_dead = now - timedelta(days=180)

    rows = []
    for sid, meta in sources.items():
        feed_url = meta.get("feed_url")
        if not feed_url:
            rows.append((sid, meta["name"][:35], "no-feed", 0, 0, "?", meta.get("frequency", 1)))
            continue

        try:
            f = feedparser.parse(feed_url)
        except Exception as e:
            rows.append((sid, meta["name"][:35], f"err:{str(e)[:8]}", 0, 0, "?", meta.get("frequency", 1)))
            continue

        recent_count = 0
        latest_date = None
        for entry in f.entries:
            pub = parse_pub(
                entry.get("published_parsed")
                or entry.get("updated_parsed")
                or entry.get("published")
                or entry.get("updated")
            )
            if not pub:
                continue
            if latest_date is None or pub > latest_date:
                latest_date = pub
            if pub >= now - timedelta(days=window):
                recent_count += 1

        ppw = recent_count / (window / 7)
        if latest_date and latest_date < threshold_dead:
            status = "DEAD"
        elif latest_date and latest_date >= now - timedelta(days=30):
            status = "active"
        elif latest_date and latest_date >= now - timedelta(days=90):
            status = "slow"
        else:
            status = "stale"

        suggested = recommend_frequency(ppw, status)
        latest_str = latest_date.strftime("%Y-%m-%d") if latest_date else "—"
        rows.append((sid, meta["name"][:35], status, recent_count, round(ppw, 1), latest_str, suggested))

    rows.sort(key=lambda r: (-r[4], r[0]))

    print(f"{'SOURCE_ID':<22} {'NAME':<37} {'STATUS':<7} {'60d':<5} {'PPW':<5} {'LATEST':<11} {'SUGG':<5}")
    print("-" * 100)
    for r in rows:
        print(f"{r[0]:<22} {r[1]:<37} {r[2]:<7} {r[3]:<5} {r[4]:<5} {r[5]:<11} {r[6]:<5}")

    # Suggest changes
    print()
    print("=" * 60)
    print("SUGGESTED CHANGES (frequency != current):")
    for sid, _, status, _, ppw, _, suggested in rows:
        current = sources[sid].get("frequency", 1)
        if status == "DEAD":
            print(f"  DROP    {sid}  (DEAD, latest > 180d ago)")
        elif suggested != current:
            print(f"  {current} → {suggested}  {sid}  (ppw={ppw})")


if __name__ == "__main__":
    main()
