#!/bin/zsh
set -e
cd "$(dirname "$0")/.."
URL="http://127.0.0.1:8765"
(sleep 1; open "$URL") &
exec python3 recorder/server.py

