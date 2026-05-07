"""Backfill `language` + `excerpt_vn` fields on existing entries.

Idempotent — only sets fields if missing.
"""
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VN_CHARS = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"


def detect_language(text: str) -> str:
    if not text:
        return "en"
    cnt = sum(1 for c in text if c in VN_CHARS or c in VN_CHARS.upper())
    return "vi" if cnt / max(len(text), 1) > 0.02 else "en"


def main():
    data_dir = Path(__file__).parent.parent / "data"
    total = 0
    backfilled_lang = 0
    backfilled_vn = 0

    for f in sorted(data_dir.glob("entries-*.jsonl")):
        entries = []
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        changed = False
        for e in entries:
            if "language" not in e:
                text = (e.get("title", "") + " " + e.get("excerpt", ""))
                e["language"] = detect_language(text)
                backfilled_lang += 1
                changed = True
            if not e.get("excerpt_vn"):
                e["excerpt_vn"] = e.get("excerpt", "")
                backfilled_vn += 1
                changed = True
        if changed:
            with f.open("w", encoding="utf-8") as fh:
                for e in entries:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        total += len(entries)

    print(f"[backfill] Total entries: {total}, language added: {backfilled_lang}, excerpt_vn added: {backfilled_vn}")


if __name__ == "__main__":
    main()
