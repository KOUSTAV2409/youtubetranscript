#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "→ Backend deps"
cd "$ROOT/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created backend/.env — add your OPENAI_API_KEY"
fi

echo "→ Frontend deps"
cd "$ROOT/frontend"
npm install

echo
echo "Done. Run in two terminals:"
echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  cd frontend && npm run dev"
