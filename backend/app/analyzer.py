import json

from openai import OpenAI

from .config import settings
from .models import AnalysisResult
from .youtube import VideoTranscript

SYSTEM_PROMPT = """You are a skeptical media analyst. Judge whether a YouTube video is worth watching
BEFORE the user spends time on it.

Score for a general curious adult. Be strict about bait:
- real_value: concrete claims, steps, evidence, novel insight, clear payoff
- clickbait: title/promise oversells what the transcript actually delivers
- rage_bait: outrage hooks, tribal framing, strawmen, low substance heat
- mixed_signals: some value but also bait tactics

Return ONLY valid JSON matching this schema:
{
  "verdict": "worth_it" | "mixed" | "skip",
  "worth_score": 0-100,
  "labels": ["real_value" | "clickbait" | "rage_bait" | "mixed_signals"],
  "confidence": "high" | "medium" | "low",
  "summary_bullets": ["...", "...", "..."],
  "watch_if": "one sentence",
  "skip_if": "one sentence",
  "bait_risk": "one sentence on clickbait/rage risk",
  "evidence_quotes": ["short quotes from transcript supporting the judgment"]
}

Rules:
- worth_score >= 70 => usually worth_it; 40-69 => mixed; <40 => skip
- Prefer 1-3 labels; use mixed_signals when unclear
- summary_bullets: 3 items max, concrete, no fluff
- evidence_quotes must be grounded in the transcript text provided
- If transcript is thin/noisy, lower confidence
"""


def analyze_video(transcript: VideoTranscript, page_title: str | None = None) -> AnalysisResult:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to backend/.env before analyzing videos."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    user_payload = {
        "video_id": transcript.video_id,
        "title_hint": page_title,
        "language": transcript.language,
        "transcript_char_count": transcript.char_count,
        "transcript": transcript.text,
    }

    completion = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Analyze this YouTube transcript and decide if the video is worth watching.\n\n"
                    + json.dumps(user_payload)
                ),
            },
        ],
    )

    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)

    return AnalysisResult(
        video_id=transcript.video_id,
        title=page_title or transcript.title,
        channel=transcript.channel,
        duration_hint=None,
        verdict=data["verdict"],
        worth_score=int(data["worth_score"]),
        labels=data["labels"],
        confidence=data["confidence"],
        summary_bullets=data["summary_bullets"][:5],
        watch_if=data["watch_if"],
        skip_if=data["skip_if"],
        bait_risk=data["bait_risk"],
        evidence_quotes=data.get("evidence_quotes", [])[:5],
        cached=False,
    )
