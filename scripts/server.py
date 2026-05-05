"""Local HTTP server with /api/star endpoint for persisting Lam's stars to starred.json.

GET routes: serve files from repo root (same as `python -m http.server`)
POST /api/star: { "id": "abc123", "starred": true } → updates starred.json

Usage:
    python scripts/server.py [--port 8765]

starred.json format:
    {
      "starred": {
        "abc123": "2026-05-06T08:30:00Z",
        ...
      }
    }
"""

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
STARRED_PATH = REPO_ROOT / "starred.json"


def load_starred() -> dict:
    if STARRED_PATH.exists():
        try:
            return json.loads(STARRED_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"starred": {}}


def save_starred(data: dict) -> None:
    STARRED_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def end_headers(self):
        # No-cache for live development
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_POST(self):
        if self.path != "/api/star":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 4096:
            self.send_error(400, "Bad request")
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
            entry_id = payload.get("id", "").strip()
            starred = bool(payload.get("starred"))
            if not entry_id or len(entry_id) > 200:
                raise ValueError("invalid id")
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            self.send_error(400, f"Bad payload: {e}")
            return

        data = load_starred()
        bucket = data.setdefault("starred", {})

        if starred:
            bucket[entry_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        else:
            bucket.pop(entry_id, None)

        save_starred(data)

        response = json.dumps({"ok": True, "starred_count": len(bucket)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, fmt, *args):
        # Quieter logging — only errors
        if any(s in fmt for s in ("404", "500", "400")):
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    if not STARRED_PATH.exists():
        save_starred({"starred": {}})

    print(f"AI News server")
    print(f"  Serving:  {REPO_ROOT}")
    print(f"  URL:      http://localhost:{args.port}")
    print(f"  Starred:  {STARRED_PATH.relative_to(REPO_ROOT)}")
    print(f"  Press Ctrl+C to stop.")
    print()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
