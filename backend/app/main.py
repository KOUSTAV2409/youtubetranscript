from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analyzer import analyze_video
from .cache import AnalysisCache
from .config import settings
from .models import AnalyzeRequest, AnalyzeResponse, ErrorResponse
from .youtube import enrich_with_metadata, extract_video_id, fetch_metadata, fetch_transcript

cache = AnalysisCache(settings.database_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await cache.init()
    yield


app = FastAPI(title="WorthWatch API", version="0.2.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# Empty or "*" → allow all (first deploy / Vercel preview friendly).
# Credentials must be off when using wildcard origins.
allow_all = not origins or origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True, "service": "worthwatch"}


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def analyze(body: AnalyzeRequest):
    url = str(body.url)
    try:
        video_id = extract_video_id(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not body.force:
        cached = await cache.get(video_id)
        if cached:
            return AnalyzeResponse(result=cached)

    try:
        meta = fetch_metadata(video_id)
        transcript = fetch_transcript(video_id, settings.max_transcript_chars)
        transcript = enrich_with_metadata(transcript, meta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not read this video's captions. {exc} "
                "Try Re-analyze in a minute, or pick a video with subtitles."
            ),
        ) from exc

    try:
        result = analyze_video(transcript)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    await cache.set(result)
    return AnalyzeResponse(result=result)
