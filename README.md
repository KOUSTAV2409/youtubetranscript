# WorthWatch

Paste a YouTube link → get a verdict: **worth it**, **mixed**, or **skip**, plus clickbait / rage-bait labels.

## Stack

- **Backend:** Python FastAPI (transcript fetch + LLM analysis + SQLite cache)
- **Frontend:** React (Vite) — single paste-and-result page

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

If you already installed an older transcript package, upgrade:

```bash
pip install -U 'youtube-transcript-api>=1.2.0' yt-dlp
```

Transcripts are fetched with `youtube-transcript-api` first, then **yt-dlp** as a fallback when YouTube returns empty/blocked responses.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Deploy (Render + Vercel)

### Backend on Render

1. Push this repo to GitHub.
2. [Render](https://render.com) → **New → Blueprint** → select the repo (uses `render.yaml`),  
   **or** **New → Web Service** with:
   - Root directory: `backend`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set env vars in the dashboard:
   - `OPENAI_API_KEY` (required)
   - `CORS_ORIGINS` = your Vercel URL, e.g. `https://your-app.vercel.app`
   - `DATABASE_PATH` = `data/cache.db` (ephemeral on free tier)
4. Confirm `GET /health` returns `{"ok": true}`.

### Frontend on Vercel

1. Import the same repo → root directory `frontend`
2. Build: `npm run build` · Output: `dist`
3. Env: `VITE_API_BASE` = `https://your-backend.onrender.com` (no trailing slash)
4. After deploy, update Render `CORS_ORIGINS` to the Vercel URL and redeploy the API if needed.

## API

`POST /analyze`

```json
{ "url": "https://www.youtube.com/watch?v=VIDEO_ID" }
```

Returns a structured verdict (`worth_score`, labels, watch/skip guidance, transcript evidence).

Same `video_id` is cached in SQLite for instant replays. Send `"force": true` to bypass cache and re-analyze.

### Phase 1 result fields

- Real **title** + **channel** (oEmbed + yt-dlp)
- **duration_hint**
- **title_content_gap** (title promise vs transcript)
- **payoff_around** (when value starts)
- UI **Re-analyze** button + clearer transcript errors
