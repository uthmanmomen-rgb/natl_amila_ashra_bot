#!/usr/bin/env bash
# Build a zip for JustRunMy.App upload (excludes secrets and local venv).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/telegram_poll_bot.zip"

cd "$ROOT"
rm -f "$OUT"
zip -r "$OUT" \
  bot.py \
  config.py \
  database.py \
  reports.py \
  requirements.txt \
  Dockerfile \
  -x "*.pyc" "__pycache__/*"

echo "Created $OUT"
echo "Upload this zip at https://justrunmy.app/panel"
echo "Do NOT include .env — set env vars in the JRMA dashboard."
