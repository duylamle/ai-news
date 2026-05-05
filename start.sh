#!/bin/bash
# AI News local viewer for Mac/Linux
PORT=8765
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting AI News local server on http://localhost:$PORT"
echo "Press Ctrl+C to stop."

(sleep 1 && open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null) &
python3 -m http.server $PORT --directory "$DIR"
