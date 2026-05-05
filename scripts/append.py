"""Append processed entries into data/entries-YYYY-MM.json + update manifest.json + state.json.

Usage:
    cat new_entries.json | python scripts/append.py
or
    python scripts/append.py --entries-file new_entries.json
"""

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_json(path: Path, default):
    if path.exists():
        try:
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                return default
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"[append] WARN: {path} contains invalid JSON, treating as empty", file=sys.stderr)
            return default
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    """Read JSONL file (1 entry per line). Tolerant to bad lines."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"[append] WARN: bad JSONL line in {path.name}, skipped", file=sys.stderr)
    return out


def append_to_jsonl(path: Path, entries: list[dict]) -> None:
    """Append entries to JSONL (1 line per entry, no rewrite)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rewrite_jsonl(path: Path, entries: list[dict]) -> None:
    """Rewrite JSONL file (used when sorting needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_entries(repo_root: Path, new_entries: list[dict]) -> dict:
    if not new_entries:
        return {"added": 0, "skipped": 0, "month": None}

    # Group by month from each entry's date (fallback to today UTC)
    now_month = datetime.now(timezone.utc).strftime("%Y-%m")
    by_month: dict[str, list[dict]] = {}
    for entry in new_entries:
        date = entry.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month = date[:7] if date else now_month
        by_month.setdefault(month, []).append(entry)

    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    total_added = 0
    total_skipped = 0
    touched_months = []

    for month, entries in by_month.items():
        month_path = data_dir / f"entries-{month}.jsonl"
        existing = load_jsonl(month_path)
        existing_ids = {e.get("id") for e in existing if e.get("id")}
        existing_urls = {e.get("url") for e in existing if e.get("url")}

        fresh = []
        for entry in entries:
            if entry.get("id") in existing_ids or entry.get("url") in existing_urls:
                total_skipped += 1
                continue
            fresh.append(entry)
            existing_ids.add(entry.get("id"))
            existing_urls.add(entry.get("url"))
            total_added += 1

        if fresh:
            # Sort merged then rewrite (newest first) — needed for FE rendering order
            merged = existing + fresh
            merged.sort(key=lambda e: (e.get("date") or "", e.get("id") or ""), reverse=True)
            rewrite_jsonl(month_path, merged)
            touched_months.append(month)

    update_manifest(repo_root)

    return {
        "added": total_added,
        "skipped": total_skipped,
        "months": touched_months,
    }


def update_manifest(repo_root: Path) -> None:
    data_dir = repo_root / "data"
    manifest_path = data_dir / "manifest.json"

    months = []
    sources_seen = set()
    total = 0
    for f in sorted(data_dir.glob("entries-*.jsonl")):
        month = f.stem.replace("entries-", "")
        entries = load_jsonl(f)
        months.append({"month": month, "count": len(entries)})
        for e in entries:
            if e.get("source"):
                sources_seen.add(e["source"])
        total += len(entries)

    manifest = {
        "total_entries": total,
        "months": [m["month"] for m in sorted(months, key=lambda x: x["month"], reverse=True)],
        "month_counts": {m["month"]: m["count"] for m in months},
        "sources": sorted(sources_seen),
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_json(manifest_path, manifest)


def update_state(repo_root: Path, entries: list[dict]) -> None:
    state_path = repo_root / "state.json"
    state = load_json(state_path, {})

    by_source: dict[str, list[str]] = {}
    for entry in entries:
        source = entry.get("source")
        url = entry.get("url")
        if source and url:
            by_source.setdefault(source, []).append(url)

    for source, urls in by_source.items():
        bucket = state.setdefault(source, {"seen_urls": [], "last_fetched": None})
        bucket["seen_urls"] = list(dict.fromkeys((bucket.get("seen_urls") or []) + urls))[-200:]
        bucket["last_fetched"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    save_json(state_path, state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries-file", help="JSON file with new entries (default: stdin)")
    ap.add_argument("--repo-root", default=".", help="Repo root path")
    args = ap.parse_args()

    if args.entries_file:
        new_entries = json.loads(Path(args.entries_file).read_text(encoding="utf-8"))
    else:
        new_entries = json.loads(sys.stdin.read())

    if not isinstance(new_entries, list):
        print("[append] expected JSON array of entries", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(args.repo_root).resolve()
    result = append_entries(repo_root, new_entries)
    update_state(repo_root, new_entries)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
