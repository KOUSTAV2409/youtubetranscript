import json
import re
from dataclasses import dataclass, replace
from urllib.parse import quote
from xml.etree.ElementTree import ParseError

import httpx

from .config import settings

VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

# Public Invidious / Piped mirrors — last-resort when YouTube blocks the host IP.
INVIDIOUS_INSTANCES = (
    "https://inv.nadeko.net",
    "https://yewtu.be",
    "https://invidious.nerdvpn.de",
    "https://vid.puffyan.us",
)

PIPED_INSTANCES = (
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://api.piped.private.coffee",
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


def _proxy_candidates() -> list[str | None]:
    """Ordered proxies to try. None = direct (no proxy)."""
    urls = [u.strip() for u in settings.youtube_proxy_url.split(",") if u.strip()]
    if urls:
        return urls
    if settings.webshare_proxy_username and settings.webshare_proxy_password:
        user = quote(settings.webshare_proxy_username, safe="")
        password = quote(settings.webshare_proxy_password, safe="")
        return [f"http://{user}:{password}@p.webshare.io:80"]
    return [None]


def _proxy_configured() -> bool:
    return any(p is not None for p in _proxy_candidates())


def _transcript_proxy_config(proxy_url: str | None):
    """Build youtube-transcript-api proxy config for this request's proxy, or None."""
    if not proxy_url:
        return None

    if (
        settings.webshare_proxy_username
        and settings.webshare_proxy_password
        and "webshare.io" in proxy_url
    ):
        from youtube_transcript_api.proxies import WebshareProxyConfig

        return WebshareProxyConfig(
            proxy_username=settings.webshare_proxy_username,
            proxy_password=settings.webshare_proxy_password,
            retries_when_blocked=5,
        )

    from youtube_transcript_api.proxies import GenericProxyConfig

    return GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)


def _ytdlp_proxy_opts(proxy: str | None) -> dict:
    return {"proxy": proxy} if proxy else {}


def _is_block_error(message: str) -> bool:
    lower = message.lower()
    return any(
        token in lower
        for token in ("block", "proxy", "cloud", "429", "too many requests", "ip")
    )


def _normalize_text(parts: list[str], max_chars: int) -> str:
    text = re.sub(r"\s+", " ", " ".join(p.strip() for p in parts if p and p.strip())).strip()
    if not text:
        raise ValueError(
            "This video's captions came back empty. Try another video, or hit Re-analyze in a minute."
        )
    return text[:max_chars]


def _blocked_message() -> str:
    if _proxy_configured():
        return (
            "YouTube still blocked transcript access through the configured proxy. "
            "Free/public proxies are usually datacenter IPs and get blocked the same way. "
            "Use residential proxies (e.g. Webshare Residential) or run the API on a home network."
        )
    return (
        "YouTube blocks automatic transcript fetch from free cloud hosts like Render. "
        "Set WEBSHARE_PROXY_USERNAME/PASSWORD (Residential) or YOUTUBE_PROXY_URL, "
        "or run the backend locally on your home network."
    )


def _friendly_transcript_error(raw: str) -> str:
    lower = raw.lower()
    if "blocked" in lower or "ip" in lower or "429" in lower or "too many requests" in lower:
        return _blocked_message()
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


def fetch_metadata(video_id: str, proxy: str | None = None) -> dict:
    """Title/channel via oEmbed; duration via yt-dlp when available."""
    if proxy is None:
        proxy = _proxy_candidates()[0]

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
            proxy=proxy,
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
            **_ytdlp_proxy_opts(proxy),
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


def _fetch_via_transcript_api(video_id: str, max_chars: int, proxy: str | None) -> VideoTranscript:
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

    proxy_config = _transcript_proxy_config(proxy)
    try:
        api = YouTubeTranscriptApi(proxy_config=proxy_config) if proxy_config else YouTubeTranscriptApi()
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


def _fetch_via_ytdlp(video_id: str, max_chars: int, proxy: str | None) -> VideoTranscript:
    try:
        import yt_dlp
    except ImportError as exc:
        raise ValueError(
            "Couldn't read captions with the primary method, and yt-dlp isn't installed. "
            "Run: pip install -U 'youtube-transcript-api>=1.2.0' yt-dlp"
        ) from exc

    url = f"https://www.youtube.com/watch?v={video_id}"
    # Mobile/TV clients sometimes succeed when the web client is IP-blocked.
    client_attempts = (
        ["android", "ios", "tv"],
        ["android_embedded", "web"],
        None,
    )

    last_error: Exception | None = None
    info = None
    for clients in client_attempts:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            **_ytdlp_proxy_opts(proxy),
        }
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    if not info:
        raise ValueError(
            _friendly_transcript_error(f"Could not load this video: {last_error or 'unknown'}")
        ) from last_error

    caption_url, language = _pick_caption_url(info)
    if not caption_url:
        raise ValueError(_friendly_transcript_error("no captions"))

    try:
        response = httpx.get(
            caption_url,
            timeout=30.0,
            follow_redirects=True,
            proxy=proxy,
        )
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


def _fetch_via_piped(video_id: str, max_chars: int, proxy: str | None) -> VideoTranscript:
    """Pull subtitle URLs from public Piped API instances (free)."""
    for base in PIPED_INSTANCES:
        try:
            resp = httpx.get(
                f"{base}/streams/{video_id}",
                timeout=18.0,
                follow_redirects=True,
                proxy=proxy,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            subs = data.get("subtitles") or []
            if not subs:
                continue

            preferred = None
            for sub in subs:
                code = (sub.get("code") or sub.get("languageCode") or "").lower()
                name = (sub.get("name") or "").lower()
                if code.startswith("en") or "english" in name:
                    preferred = sub
                    break
            preferred = preferred or subs[0]
            caption_url = preferred.get("url")
            if not caption_url:
                continue

            cap_resp = httpx.get(caption_url, timeout=20.0, follow_redirects=True, proxy=proxy)
            cap_resp.raise_for_status()
            parts = _parse_caption_payload(caption_url, cap_resp.text)
            text = _normalize_text(parts, max_chars)
            duration = data.get("duration")
            duration_seconds = int(duration) if isinstance(duration, (int, float)) and duration > 0 else None
            return VideoTranscript(
                video_id=video_id,
                title=data.get("title"),
                channel=data.get("uploader"),
                language=preferred.get("code") or preferred.get("languageCode"),
                text=text,
                char_count=len(text),
                duration_seconds=duration_seconds,
                duration_hint=format_duration(duration_seconds) if duration_seconds else None,
            )
        except Exception:  # noqa: BLE001
            continue

    raise ValueError(_friendly_transcript_error("blocked"))


def _fetch_via_invidious(video_id: str, max_chars: int, proxy: str | None) -> VideoTranscript:
    """Last resort: pull captions through public Invidious instances."""
    errors: list[str] = []

    for base in INVIDIOUS_INSTANCES:
        try:
            list_resp = httpx.get(
                f"{base}/api/v1/captions/{video_id}",
                timeout=15.0,
                follow_redirects=True,
                proxy=proxy,
            )
            if list_resp.status_code != 200:
                errors.append(f"{base}: HTTP {list_resp.status_code}")
                continue

            captions = list_resp.json()
            if not isinstance(captions, list) or not captions:
                errors.append(f"{base}: no captions")
                continue

            preferred = None
            for cap in captions:
                label = (cap.get("label") or "").lower()
                lang = (cap.get("language_code") or "").lower()
                if lang.startswith("en") or "english" in label:
                    preferred = cap
                    break
            preferred = preferred or captions[0]
            caption_path = preferred.get("url")
            if not caption_path:
                continue

            caption_url = caption_path if caption_path.startswith("http") else f"{base}{caption_path}"
            cap_resp = httpx.get(caption_url, timeout=20.0, follow_redirects=True, proxy=proxy)
            cap_resp.raise_for_status()
            parts = _parse_caption_payload(caption_url, cap_resp.text)
            text = _normalize_text(parts, max_chars)
            return VideoTranscript(
                video_id=video_id,
                title=None,
                channel=None,
                language=preferred.get("language_code"),
                text=text,
                char_count=len(text),
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")
            continue

    raise ValueError(_friendly_transcript_error("blocked"))


def fetch_transcript(video_id: str, max_chars: int) -> VideoTranscript:
    errors: list[str] = []
    fetchers = (
        _fetch_via_transcript_api,
        _fetch_via_ytdlp,
        _fetch_via_piped,
        _fetch_via_invidious,
    )

    for proxy in _proxy_candidates():
        for fetcher in fetchers:
            try:
                return fetcher(video_id, max_chars, proxy)
            except ValueError as exc:
                errors.append(str(exc))
                # Non-block failures (no captions, private, etc.) — stop proxy hopping.
                if not _is_block_error(str(exc)):
                    raise

    for msg in errors:
        if _is_block_error(msg):
            raise ValueError(msg)
    raise ValueError(errors[0] if errors else "Unknown transcript error.")
