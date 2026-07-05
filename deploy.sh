#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  deploy.sh  —  Codex Legalis v1.0.0 Deployment Script
#  Usage:  ./deploy.sh [--port 8000] [--no-reload]
# ─────────────────────────────────────────────────────────────────
set -e

# ── Defaults ──────────────────────────────────────────────────────
PORT=8000
RELOAD="--reload"

# ── Parse args ────────────────────────────────────────────────────
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --port)    PORT="$2"; shift ;;
    --no-reload) RELOAD="" ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

# ── Resolve project root (always run from script's directory) ─────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ⚖  Codex Legalis — Deployment"
echo "  ────────────────────────────────"
echo "  Project root : $SCRIPT_DIR"
echo "  Port         : $PORT"
echo "  Hot-reload   : ${RELOAD:-(disabled)}"
echo ""

# ── Virtual environment ───────────────────────────────────────────
if [ ! -d "venv" ]; then
  echo "=> Creating Python virtual environment…"
  python3 -m venv venv
fi

PYTHON="$SCRIPT_DIR/venv/bin/python"
PIP="$SCRIPT_DIR/venv/bin/pip"
UVICORN="$SCRIPT_DIR/venv/bin/uvicorn"

# ── Install / upgrade dependencies ───────────────────────────────
echo "=> Installing dependencies from requirements.txt…"
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt --quiet

echo ""
echo "=> All dependencies installed."
echo ""

# ── Check for .env ────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    echo "⚠  No .env found — copying .env.example as .env"
    echo "   Edit it and add your API keys before using live features."
    cp .env.example .env
  else
    echo "⚠  No .env file found. Live LLM features may fail without API keys."
  fi
fi

# ── Free up the port ────────────────────────────────────────────────
echo "=> Checking for processes on port $PORT…"
lsof -ti :"$PORT" | xargs kill -9 2>/dev/null || true

# ── Start server ──────────────────────────────────────────────────
echo "=> Starting Codex Legalis on http://localhost:$PORT"
echo "   Press Ctrl+C to stop."
echo ""

exec "$UVICORN" server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  $RELOAD
