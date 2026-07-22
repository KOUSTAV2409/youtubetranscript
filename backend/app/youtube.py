import json
import re
from dataclasses import dataclass
from xml.etree.ElementTree import ParseError

import httpx

VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


@dataclass
class VideoTranscript:
    video_id: str
    title: str | None
    channel: str | None
    language: str | None
    text: str
    char_count: int


def extract_video_id(url: str) -> str:
    match = VIDEO_ID_RE.search(url)
    if not match:
        raise ValueError("Could not find a YouTube video id in that URL.")
    return match.group(1)


def _normalize_text(parts: list[str], max_chars: int) -> str:
    text = re.sub(r"\s+", " ", " ".join(p.strip() for p in parts if p and p.strip())).strip()
    if not text:
        raise ValueError("Transcript was empty.")
    return text[:max_chars]


def _fetch_via_transcript_api(video_id: str, max_chars: int) -> VideoTranscript:
    """Primary path: youtube-transcript-api (v1+ preferred)."""
    from youtube_transcript_api import YouTubeTranscriptApi

    # 0.6.x exposes classmethods like list_transcripts; v1 uses instance .fetch/.list
    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        return _fetch_via_legacy_api(video_id, max_chars)

    from youtube_transcript_api._errors import (
        IpBlocked,
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeRequestFailed,
    )

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound) as exc:
        raise ValueError(str(exc) or "No transcript available for this video.") from exc
    except (RequestBlocked, IpBlocked) as exc:
        raise ValueError(
            "YouTube blocked transcript requests from this IP. Try again later or use a different network."
        ) from exc
    except YouTubeRequestFailed as exc:
        raise ValueError(f"YouTube request failed while fetching transcript: {exc}") from exc
    except ParseError as exc:
        raise ValueError(
            "YouTube returned an empty transcript response. Retrying via yt-dlp fallback."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to fetch transcript: {exc}") from exc

    parts = [snippet.text for snippet in fetched]
    text = _normalize_text(parts, max_chars)
    return VideoTranscript(
        video_id=video_id,
        title=None,
        channel=None,
        language=getattr(fetched, "language_code", None),
        text=text,
        char_count=len(text),
    )


def _fetch_via_legacy_api(video_id: str, max_chars: int) -> VideoTranscript:
    """Compatibility for youtube-transcript-api 0.6.x (broken against current YouTube)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
            except NoTranscriptFound:
                transcript = next(iter(transcript_list))
        entries = transcript.fetch()
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound) as exc:
        raise ValueError(str(exc) or "No transcript available for this video.") from exc
    except ParseError as exc:
        raise ValueError(
            "Transcript fetch failed (empty YouTube response). Run: "
            "pip install -U 'youtube-transcript-api>=1.2.0' yt-dlp"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to fetch transcript: {exc}") from exc

    parts = [entry.get("text", "") for entry in entries]
    text = _normalize_text(parts, max_chars)
    return VideoTranscript(
        video_id=video_id,
        title=None,
        channel=None,
        language=getattr(transcript, "language_code", None),
        text=text,
        char_count=len(text),
    )


def _pick_caption_url(info: dict) -> tuple[str | None, str | None]:
    preferred_langs = ("en", "en-US", "en-GB", "a.en")
    preferred_exts = ("json3", "srv3", "srv1", "vtt", "ttml")

    for source_key in ("subtitles", "automatic_captions"):
        source = info.get(source_key) or {}
        for lang in preferred_langs:
            formats = source.get(lang) or []
            by_ext = {f.get("ext"): f.get("url") for f in formats if f.get("url")}
            for ext in preferred_exts:
                if by_ext.get(ext):
                    return by_ext[ext], lang
        for lang, formats in source.items():
            by_ext = {f.get("ext"): f.get("url") for f in formats if f.get("url")}
            for ext in preferred_exts:
                if by_ext.get(ext):
                    return by_ext[ext], lang
    return None, None


def _parse_caption_payload(url: str, body: str) -> list[str]:
    if "json3" in url or body.lstrip().startswith("{"):
        data = json.loads(body)
        parts: list[str] = []
        for event in data.get("events", []):
            for seg in event.get("segs", []) or []:
                piece = seg.get("utf8")
                if piece and piece.strip() and piece != "\n":
                    parts.append(piece)
        return parts

    # VTT / plain-ish text fallback
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("WEBVTT") or "-->" in stripped or stripped.isdigit():
            continue
        if stripped.startswith("NOTE") or stripped.startswith("Kind:") or stripped.startswith("Language:"):
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return lines


def _fetch_via_ytdlp(video_id: str, max_chars: int) -> VideoTranscript:
    try:
        import yt_dlp
    except ImportError as exc:
        raise ValueError(
            "Primary transcript API failed and yt-dlp is not installed. "
            "Run: pip install -U 'youtube-transcript-api>=1.2.0' yt-dlp"
        ) from exc

    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"yt-dlp could not load this video: {exc}") from exc

    caption_url, language = _pick_caption_url(info)
    if not caption_url:
        raise ValueError("No captions/subtitles found for this video.")

    try:
        response = httpx.get(caption_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        parts = _parse_caption_payload(caption_url, response.text)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to download captions via yt-dlp: {exc}") from exc

    text = _normalize_text(parts, max_chars)
    return VideoTranscript(
        video_id=video_id,
        title=info.get("title"),
        channel=info.get("uploader") or info.get("channel"),
        language=language,
        text=text,
        char_count=len(text),
    )


def fetch_transcript(video_id: str, max_chars: int) -> VideoTranscript:
    errors: list[str] = []

    try:
        return _fetch_via_transcript_api(video_id, max_chars)
    except ValueError as exc:
        errors.append(f"transcript-api: {exc}")

    try:
        return _fetch_via_ytdlp(video_id, max_chars)
    except ValueError as exc:
        errors.append(f"yt-dlp: {exc}")

    raise ValueError(
        "Could not fetch a transcript for this video. "
        + " | ".join(errors)
    )
