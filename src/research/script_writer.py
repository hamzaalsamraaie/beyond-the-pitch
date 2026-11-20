"""
Script writer: converts a ScoredTopic into a Storyboard.

BaseScriptWriter (ABC)
  └─ MockScriptWriter   — deterministic output, zero API calls, used in all tests
  └─ ClaudeScriptWriter — calls the Anthropic Messages API

IMPORTANT: ClaudeScriptWriter enforces strict anti-fabrication rules via the
system prompt. It raises RuntimeError if ANTHROPIC_API_KEY is not set, so
tests must always use MockScriptWriter explicitly.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod

import anthropic

from src.core.config import get_section
from src.core.database import count_api_requests_today, record_api_usage
from src.core.kill_switch import require_clear
from src.core.logger import get_logger
from src.research.models import (
    ContentType,
    ResearchItem,
    ScoredTopic,
    SourceCitation,
    Storyboard,
    StoryboardScene,
)

logger = get_logger(__name__)

# ── System prompt (shared between real and mock) ───────────────────────────────

_SYSTEM_PROMPT = """You are a football content writer for "Beyond The Pitch", a YouTube Shorts channel.
Your job is to write original, emotionally engaging 20–45 second Shorts scripts.

STRICT RULES — you must follow every one of these:
1. Only use facts from the research items provided. Do not add statistics, dates, quotes or events not present in the research items.
2. Never fabricate quotes. If a direct quote is not in the research items, do not include one.
3. Never present transfer rumours or unverified news as confirmed facts.
4. Never include gambling, betting, wagering or odds references.
5. Never claim any specific footage is available or licensed. visual_requirement must describe the type of visual needed, not name specific clips.
6. Write original narration. Do not reproduce match commentary or broadcast transcripts.
7. If the research items do not contain enough facts for the full duration, write a shorter script that is honest about what is known.
8. Each scene must cite at least one research item by its 0-based index.

OUTPUT: Return ONLY a valid JSON object — no markdown fences, no commentary outside the JSON.
Schema:
{
  "title": "<short punchy storyboard title>",
  "hook": "<2–5 word on-screen opening hook>",
  "scenes": [
    {
      "scene_number": 1,
      "start_time": 0.0,
      "end_time": 6.0,
      "narration": "<spoken narration>",
      "on_screen_text": "<brief subtitle or headline>",
      "visual_requirement": "<type of visual needed — no specific clips>",
      "source_indices": [0]
    }
  ],
  "proposed_titles": ["<title 1>", "<title 2>", "<title 3>"],
  "hashtags": ["#Shorts", "#football", ...]
}

Constraints:
- total_duration = last scene's end_time, must be 20–45 seconds
- 3–8 scenes
- exactly 3 proposed_titles
- 5–10 hashtags including #Shorts and #football
"""


def _build_user_prompt(topic: ScoredTopic) -> str:
    candidate = topic.candidate
    items_text = "\n".join(
        f"[{i}] {item.fact} (source: {item.source.title})"
        for i, item in enumerate(candidate.research_items)
    )
    return (
        f"Content type: {candidate.content_type.value}\n"
        f"Topic: {candidate.title}\n"
        f"Summary: {candidate.summary}\n\n"
        f"Research items (use ONLY these facts):\n{items_text}\n\n"
        f"Suggested opening hook: {candidate.suggested_hook or 'write your own'}\n\n"
        "Generate the storyboard JSON now."
    )


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseScriptWriter(ABC):
    @abstractmethod
    def generate(self, topic: ScoredTopic) -> Storyboard:
        """
        Convert a scored topic into a fully validated Storyboard.
        Raises ValueError if the generated content fails validation.
        """
        ...


# ── Mock script writer ─────────────────────────────────────────────────────────

def _mock_storyboard_for(topic: ScoredTopic) -> Storyboard:
    """
    Build a deterministic mock storyboard from the topic's research items.
    Always produces exactly 3 scenes to satisfy the Storyboard minimum.
    Used in all automated tests. Output is labelled generated_by='mock'.
    """
    candidate = topic.candidate
    items = list(candidate.research_items[:4])

    # Visual requirement varies by content type
    visual = (
        "Animated text graphic over a solid-colour background"
        if candidate.content_type == ContentType.FOOTBALL_MOTIVATION
        else "Archive-style photo collage or illustrated graphic"
    )

    def _item_at(idx: int) -> ResearchItem:
        # Wrap-around so we can build 3 scenes even with 1 research item
        return items[idx % len(items)]

    def _src_idx(idx: int) -> int:
        return idx % len(items)

    scenes: list[StoryboardScene] = [
        # Scene 1 — hook (5 s)
        StoryboardScene(
            scene_number=1,
            start_time=0.0,
            end_time=5.0,
            narration=candidate.suggested_hook or candidate.title[:120],
            on_screen_text=candidate.title[:60],
            visual_requirement=visual,
            source_indices=[_src_idx(0)],
        ),
        # Scene 2 — main content (15 s)
        StoryboardScene(
            scene_number=2,
            start_time=5.0,
            end_time=20.0,
            narration=_item_at(0).fact[:200],
            on_screen_text="The Story",
            visual_requirement=visual,
            source_indices=[_src_idx(0)],
        ),
        # Scene 3 — second fact or outro (10 s)
        StoryboardScene(
            scene_number=3,
            start_time=20.0,
            end_time=30.0,
            narration=_item_at(1).fact[:200] if len(items) > 1 else candidate.summary[:200],
            on_screen_text="Part 2" if len(items) > 1 else "The Legacy",
            visual_requirement=visual,
            source_indices=[_src_idx(1)],
        ),
    ]

    # If there's a 4th research item, add a 4th scene
    if len(items) >= 3:
        scenes.append(
            StoryboardScene(
                scene_number=4,
                start_time=30.0,
                end_time=38.0,
                narration=_item_at(2).fact[:200],
                on_screen_text="The Impact",
                visual_requirement=visual,
                source_indices=[_src_idx(2)],
            )
        )

    total_duration = float(scenes[-1].end_time)

    sb = Storyboard(
        title=f"[MOCK] {candidate.title[:180]}",
        content_type=candidate.content_type,
        hook=candidate.suggested_hook[:80] if candidate.suggested_hook else "THE STORY",
        scenes=scenes,
        total_duration=total_duration,
        proposed_titles=[
            f"{candidate.title[:70]}",
            f"The Story of {candidate.title[:60]}",
            f"You Won't Believe This: {candidate.title[:50]}",
        ],
        hashtags=["#Shorts", "#football", "#footballstories", "#beyondthepitch", "#sports"],
        research_items=items,
        generated_by="mock",
    )
    sb = Storyboard.model_validate(
        {**sb.model_dump(), "script_hash": sb.compute_hash()}
    )
    return sb


class MockScriptWriter(BaseScriptWriter):
    """
    Returns a deterministic storyboard built from the topic's research items.
    No API calls. Safe to use in all tests and CI.
    """

    def generate(self, topic: ScoredTopic) -> Storyboard:
        require_clear("MockScriptWriter.generate")
        return _mock_storyboard_for(topic)


# ── Claude script writer ───────────────────────────────────────────────────────

class ClaudeScriptWriter(BaseScriptWriter):
    """
    Calls the Anthropic Claude API to generate a storyboard.

    Requires ANTHROPIC_API_KEY in the environment.
    Enforces a daily request cap (stored in SQLite api_usage table).
    Uses the cheapest capable model (claude-haiku) with a capped token budget.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it in your .env file or use MockScriptWriter for testing."
            )
        cfg = get_section("claude")
        self._model: str = cfg.get("model", "claude-haiku-4-5-20251001")
        self._max_tokens: int = int(cfg.get("max_tokens_per_request", 1500))
        self._daily_cap: int = int(cfg.get("max_requests_per_day", 10))
        self._client = anthropic.Anthropic(api_key=api_key)

    def _check_daily_cap(self) -> None:
        used = count_api_requests_today("claude")
        if used >= self._daily_cap:
            raise RuntimeError(
                f"Daily Claude API cap reached ({used}/{self._daily_cap}). "
                "Increase claude.max_requests_per_day in settings.yaml to continue."
            )

    def _call_api(self, user_prompt: str) -> tuple[str, int]:
        """Return (raw_text, tokens_used)."""
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = message.content[0].text
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        return raw_text, tokens_used

    def _parse_response(
        self, raw: str, topic: ScoredTopic
    ) -> Storyboard:
        """Extract JSON from the response and validate into a Storyboard."""
        # Strip any accidental markdown fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.M)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.M)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Claude returned non-JSON output: {exc}\nRaw: {raw[:300]}"
            ) from exc

        # Inject fields that Claude doesn't generate
        data["content_type"] = topic.candidate.content_type.value
        data["research_items"] = [
            item.model_dump() for item in topic.candidate.research_items
        ]
        data["generated_by"] = self._model

        try:
            sb = Storyboard.model_validate(data)
        except Exception as exc:
            raise ValueError(
                f"Claude storyboard failed Pydantic validation: {exc}"
            ) from exc

        # Attach the script hash
        return Storyboard.model_validate(
            {**sb.model_dump(), "script_hash": sb.compute_hash()}
        )

    def generate(self, topic: ScoredTopic) -> Storyboard:
        require_clear("ClaudeScriptWriter.generate")
        self._check_daily_cap()

        user_prompt = _build_user_prompt(topic)
        logger.info(
            "claude_request_start",
            topic=topic.candidate.title[:60],
            model=self._model,
        )

        raw, tokens = self._call_api(user_prompt)
        record_api_usage("claude", tokens, topic.candidate.title[:100])

        logger.info("claude_request_done", tokens=tokens)
        return self._parse_response(raw, topic)
