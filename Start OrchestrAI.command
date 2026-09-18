#!/bin/zsh
set -e

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "Preparing OrchestrAI for first use..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import flask, google.genai" 2>/dev/null; then
  echo "Installing the project dependencies..."
  .venv/bin/pip install -r requirements.txt
fi

if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

echo "Starting OrchestrAI at http://127.0.0.1:8080"
.venv/bin/python main.py &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM

sleep 1
open "http://127.0.0.1:8080"
wait "$SERVER_PID"
