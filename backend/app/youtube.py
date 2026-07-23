import json
import re
from dataclasses import dataclass, replace
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
    duration_seconds: int | None = None
    duration_hint: str | None = None


def extract_video_id(url: str) -> str:
    match = VIDEO_ID_RE.search(url)
    if not match:
        raise ValueError("Could not find a YouTube video id in that URL.")
    return match.group(1)


def format_duration(seconds: int) -> str:
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s" if secs else f"{minutes}m"
    return f"{secs}s"


def _normalize_text(parts: list[str], max_chars: int) -> str:
    text = re.sub(r"\s+", " ", " ".join(p.strip() for p in parts if p and p.strip())).strip()
    if not text:
        raise ValueError(
            "This video's captions came back empty. Try another video, or hit Re-analyze in a minute."
        )
    return text[:max_chars]


def _friendly_transcript_error(raw: str) -> str:
    lower = raw.lower()
    if "blocked" in lower or "ip" in lower:
        return (
            "YouTube temporarily blocked transcript access from this network. "
            "Wait a minute and try Re-analyze, or switch networks."
        )
    if "disabled" in lower:
        return "Captions are disabled on this video, so we can't judge it yet."
    if "unavailable" in lower:
        return "This video looks unavailable or private."
    if "no transcript" in lower or "no caption" in lower or "no subtitles" in lower:
        return (
            "No captions found for this video. WorthWatch needs a transcript — "
            "try a video with subtitles turned on."
        )
    if "empty" in lower:
        return (
            "YouTube returned an empty transcript response. "
            "This is usually temporary — try Re-analyze shortly."
        )
    return raw


def fetch_metadata(video_id: str) -> dict:
    """Title/channel via oEmbed; duration via yt-dlp when available."""
    meta: dict = {
        "title": None,
        "channel": None,
        "duration_seconds": None,
        "duration_hint": None,
    }

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        response = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": watch_url, "format": "json"},
            timeout=12.0,
            follow_redirects=True,
        )
        if response.status_code == 200:
            data = response.json()
            meta["title"] = data.get("title")
            meta["channel"] = data.get("author_name")
    except Exception:  # noqa: BLE001
        pass

    try:
        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(watch_url, download=False)
        meta["title"] = meta["title"] or info.get("title")
        meta["channel"] = meta["channel"] or info.get("uploader") or info.get("channel")
        duration = info.get("duration")
        if isinstance(duration, (int, float)) and duration > 0:
            seconds = int(duration)
            meta["duration_seconds"] = seconds
            meta["duration_hint"] = format_duration(seconds)
    except Exception:  # noqa: BLE001
        pass

    return meta


def enrich_with_metadata(transcript: VideoTranscript, meta: dict) -> VideoTranscript:
    return replace(
        transcript,
        title=transcript.title or meta.get("title"),
        channel=transcript.channel or meta.get("channel"),
        duration_seconds=transcript.duration_seconds or meta.get("duration_seconds"),
        duration_hint=transcript.duration_hint or meta.get("duration_hint"),
    )


def _fetch_via_transcript_api(video_id: str, max_chars: int) -> VideoTranscript:
    from youtube_transcript_api import YouTubeTranscriptApi

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
        raise ValueError(_friendly_transcript_error(str(exc) or "No transcript available.")) from exc
    except (RequestBlocked, IpBlocked) as exc:
        raise ValueError(_friendly_transcript_error("blocked")) from exc
    except YouTubeRequestFailed as exc:
        raise ValueError(_friendly_transcript_error(str(exc))) from exc
    except ParseError as exc:
        raise ValueError(_friendly_transcript_error("empty")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_friendly_transcript_error(f"Failed to fetch transcript: {exc}")) from exc

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
        raise ValueError(_friendly_transcript_error(str(exc) or "No transcript available.")) from exc
    except ParseError as exc:
        raise ValueError(_friendly_transcript_error("empty")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_friendly_transcript_error(f"Failed to fetch transcript: {exc}")) from exc

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
            "Couldn't read captions with the primary method, and yt-dlp isn't installed. "
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
        raise ValueError(_friendly_transcript_error(f"Could not load this video: {exc}")) from exc

    caption_url, language = _pick_caption_url(info)
    if not caption_url:
        raise ValueError(_friendly_transcript_error("no captions"))

    try:
        response = httpx.get(caption_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        parts = _parse_caption_payload(caption_url, response.text)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_friendly_transcript_error(f"Failed to download captions: {exc}")) from exc

    text = _normalize_text(parts, max_chars)
    duration = info.get("duration")
    duration_seconds = int(duration) if isinstance(duration, (int, float)) and duration > 0 else None
    return VideoTranscript(
        video_id=video_id,
        title=info.get("title"),
        channel=info.get("uploader") or info.get("channel"),
        language=language,
        text=text,
        char_count=len(text),
        duration_seconds=duration_seconds,
        duration_hint=format_duration(duration_seconds) if duration_seconds else None,
    )


def fetch_transcript(video_id: str, max_chars: int) -> VideoTranscript:
    errors: list[str] = []

    try:
        return _fetch_via_transcript_api(video_id, max_chars)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        return _fetch_via_ytdlp(video_id, max_chars)
    except ValueError as exc:
        errors.append(str(exc))

    # Prefer the friendliest / most specific message
    primary = errors[0] if errors else "Unknown transcript error."
    raise ValueError(primary)
