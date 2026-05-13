import json

from anthropic import AsyncAnthropic

from app.config import get_settings

_SYSTEM_PROMPT = """\
You analyze redacted call transcripts and extract structured outcomes.
Respond with valid JSON only — no markdown fences, no extra text.
Required fields:
  summary      - 2-3 sentence summary of the call
  disposition  - exactly one of: interested, not_interested, callback, voicemail, no_answer, other
  next_action  - specific follow-up action as a string, or null if none"""


async def extract(redacted_text: str) -> dict:
    """Send redacted transcript to Claude and return a structured outcome dict."""
    client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": redacted_text}],
    )
    raw = message.content[0].text
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON response: {raw!r}") from exc
