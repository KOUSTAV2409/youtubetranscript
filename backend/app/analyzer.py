import json

from openai import OpenAI

from .config import settings
from .models import AnalysisResult, Label, PackagingStyle
from .youtube import VideoTranscript

ALLOWED_LABELS = set(Label.__args__)
ALLOWED_PACKAGING = set(PackagingStyle.__args__)

SYSTEM_PROMPT = """You are a sharp, slightly witty media critic who judges whether a YouTube video
is worth watching BEFORE the user spends time on it. Be fair. Have a sense of humor when the
creator is clearly joking with the packaging — never confuse satire with a scam.

Score for a general curious adult.

Labels (use 1-3):
- real_value: concrete claims, steps, evidence, novel insight, clear payoff
- clickbait: title/thumbnail hype DECEPTIVELY oversells thin content (user feels cheated)
- rage_bait: outrage hooks, tribal framing, strawmen, low substance heat
- satire_packaging: title/thumbnail is ironic, deadpan, or jokingly opposite of the real content
  on purpose — creator is having fun, content still delivers. Example: a deep system-design
  lecture titled "System Design is Dead" → satire_packaging + real_value, NOT clickbait.
- mixed_signals: some value but also messy or unclear packaging

CRITICAL distinction — ironic satire vs deceptive clickbait:
- Ironic satire: title says the opposite / is jokey, but transcript is substantive and the joke
  is the packaging. Do NOT punish the worth_score for the joke. Prefer packaging_style =
  "ironic_satire". Say so clearly in packaging_note with a dry one-liner.
- Deceptive clickbait: title promises fireworks; transcript is fluff/repetition. Lower score.
  packaging_style = "hype_clickbait".
- If unsure between satire and clickbait, lean satire when substance in the transcript is high.

Always compare TITLE to TRANSCRIPT:
- For satire: title_content_gap should explain "title is tongue-in-cheek; content actually …"
- For clickbait: "title promises X; transcript mostly delivers filler/Y"

Also estimate payoff_around (when value starts).

Return ONLY valid JSON:
{
  "verdict": "worth_it" | "mixed" | "skip",
  "worth_score": 0-100,
  "labels": ["real_value" | "clickbait" | "rage_bait" | "satire_packaging" | "mixed_signals"],
  "confidence": "high" | "medium" | "low",
  "packaging_style": "straight" | "ironic_satire" | "hype_clickbait" | "rage",
  "packaging_note": "one witty or plain sentence about how the title/thumbnail packages the video (or null)",
  "summary_bullets": ["...", "...", "..."],
  "watch_if": "one sentence",
  "skip_if": "one sentence",
  "bait_risk": "one sentence — if satire, say the 'bait' is jokey packaging, not a ripoff",
  "title_content_gap": "one sentence comparing title promise vs transcript delivery",
  "payoff_around": "short timing hint for when value starts",
  "evidence_quotes": ["short quotes from transcript supporting the judgment"]
}

Rules:
- worth_score >= 70 => usually worth_it; 40-69 => mixed; <40 => skip
- High-substance + ironic title => high worth_score is allowed (do not dock for the joke)
- Prefer 1-3 labels; can combine real_value + satire_packaging
- summary_bullets: 3 items max, concrete; a light wry tone is OK, never mean
- evidence_quotes must be grounded in the transcript
- If transcript is thin/noisy or title is missing, lower confidence
- Use duration_hint when judging whether the video is too long for its payoff
- packaging_note should sound human (e.g. "Title says system design is dead; the video is busy proving otherwise.")
"""


def _sanitize_labels(raw_labels: list) -> list[Label]:
    cleaned: list[Label] = []
    for item in raw_labels or []:
        if item in ALLOWED_LABELS and item not in cleaned:
            cleaned.append(item)  # type: ignore[arg-type]
    if not cleaned:
        cleaned = ["mixed_signals"]
    return cleaned


def analyze_video(transcript: VideoTranscript) -> AnalysisResult:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to backend/.env before analyzing videos."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    user_payload = {
        "video_id": transcript.video_id,
        "title": transcript.title,
        "channel": transcript.channel,
        "duration_hint": transcript.duration_hint,
        "duration_seconds": transcript.duration_seconds,
        "language": transcript.language,
        "transcript_char_count": transcript.char_count,
        "transcript": transcript.text,
        "hint": (
            "Watch for ironic or satirical titles that joke about the topic while the "
            "transcript still teaches it seriously (common in tech creator culture)."
        ),
    }

    completion = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Analyze this YouTube video. Distinguish ironic/satirical packaging from "
                    "deceptive clickbait. Score the CONTENT, not the joke on the thumbnail.\n\n"
                    + json.dumps(user_payload)
                ),
            },
        ],
    )

    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)

    confidence = data["confidence"]
    if transcript.char_count < 800 and confidence == "high":
        confidence = "medium"
    if not transcript.title and confidence == "high":
        confidence = "medium"

    packaging_style = data.get("packaging_style") or "straight"
    if packaging_style not in ALLOWED_PACKAGING:
        packaging_style = "straight"

    labels = _sanitize_labels(data.get("labels", []))
    if packaging_style == "ironic_satire" and "satire_packaging" not in labels:
        labels = (["satire_packaging"] + labels)[:3]
    if packaging_style == "ironic_satire" and "clickbait" in labels:
        # Don't double-punish satire as clickbait
        labels = [label for label in labels if label != "clickbait"]
        if not labels:
            labels = ["satire_packaging", "real_value"]

    return AnalysisResult(
        video_id=transcript.video_id,
        title=transcript.title,
        channel=transcript.channel,
        duration_hint=transcript.duration_hint,
        duration_seconds=transcript.duration_seconds,
        verdict=data["verdict"],
        worth_score=int(data["worth_score"]),
        labels=labels,
        confidence=confidence,
        packaging_style=packaging_style,
        packaging_note=data.get("packaging_note") or None,
        summary_bullets=data["summary_bullets"][:5],
        watch_if=data["watch_if"],
        skip_if=data["skip_if"],
        bait_risk=data["bait_risk"],
        title_content_gap=data.get("title_content_gap"),
        payoff_around=data.get("payoff_around"),
        evidence_quotes=data.get("evidence_quotes", [])[:5],
        cached=False,
    )
