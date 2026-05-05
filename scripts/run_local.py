"""End-to-end local test pipeline (no LLM, no Claude).

Fetches a list of source-ids, classifies rule-based, appends to data files.
Used for smoke-testing FE render. Real routine on cloud uses Haiku for VN
translation + classification refinement.

Usage:
    python scripts/run_local.py --sources-list arxiv-cs-ai openai-blog ...
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


UTF8_ENV = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def run_fetch(source_id: str, sources_path: str, state_path: str) -> list[dict]:
    cmd = [
        sys.executable, str(Path(__file__).parent / "fetch.py"),
        "--source-id", source_id,
        "--state", state_path,
        "--sources", sources_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV)
    if r.returncode != 0:
        print(f"[run] fetch failed for {source_id}: {r.stderr[:200]}", file=sys.stderr)
        return []
    try:
        return json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError:
        return []


def run_classify(entries: list[dict], sources_path: str) -> list[dict]:
    if not entries:
        return []
    cmd = [sys.executable, str(Path(__file__).parent / "classify.py"), "--sources", sources_path]
    r = subprocess.run(cmd, input=json.dumps(entries, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV)
    if r.returncode != 0:
        print(f"[run] classify failed: {r.stderr[:300]}", file=sys.stderr)
        return entries
    try:
        return json.loads(r.stdout) if r.stdout.strip() else entries
    except json.JSONDecodeError:
        print(f"[run] classify returned invalid JSON", file=sys.stderr)
        return entries


def run_append(entries: list[dict], repo_root: str) -> dict:
    if not entries:
        return {"added": 0, "skipped": 0}
    cmd = [sys.executable, str(Path(__file__).parent / "append.py"), "--repo-root", repo_root]
    r = subprocess.run(cmd, input=json.dumps(entries, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV)
    if r.returncode != 0:
        print(f"[run] append failed: {r.stderr[:300]}", file=sys.stderr)
        return {"error": r.stderr[:200]}
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {"error": "empty"}
    except json.JSONDecodeError:
        return {"error": "invalid JSON from append"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources-list", nargs="+", required=True, help="Source IDs to fetch")
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    sources_path = str(repo / "sources.json")
    state_path = str(repo / "state.json")

    total_fetched = 0
    total_added = 0
    total_skipped = 0

    for sid in args.sources_list:
        entries = run_fetch(sid, sources_path, state_path)
        if not entries:
            print(f"  [{sid:25}] 0 fetched")
            continue
        total_fetched += len(entries)

        classified = run_classify(entries, sources_path)
        result = run_append(classified, str(repo))
        added = result.get("added", 0)
        skipped = result.get("skipped", 0)
        total_added += added
        total_skipped += skipped
        print(f"  [{sid:25}] fetched={len(entries):2d}  added={added:2d}  skipped={skipped:2d}")

    print()
    print(f"Total: fetched {total_fetched}, added {total_added}, skipped (dedup) {total_skipped}")


if __name__ == "__main__":
    main()
