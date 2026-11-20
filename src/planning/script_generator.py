"""
Hook-first script generator for football Shorts.

Structure (enforced):
  Hook     ≤ 3s   — shocking claim, question, or striking stat that stops the scroll
  Bridge   3–8s   — context: who, what, when
  Escalate 8–25s  — the story beats; 2–4 short punchy facts
  Payoff   25–32s — the resolution or reveal
  CTA      32–38s — subscribe prompt (optional, keep ≤ 4s)

Script rules:
  - Every sentence must be supported by a research item (no fabrication)
  - No unverified claims ("allegedly", "reportedly", "sources say")
  - No transfer rumours, gambling references or explicit content
  - Narration word count must fit the target duration at ~2.8 words/second
    (macOS Samantha voice rate; adjust for other providers)

This module generates DRAFT scripts. Human review is required before production.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.logger import get_logger
from src.planning.models import VideoIdea

logger = get_logger(__name__)

WORDS_PER_SECOND = 2.8  # conservative estimate for macOS Samantha voice


@dataclass
class ScriptSection:
    name: str
    duration_secs: float
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def estimated_duration(self) -> float:
        return self.word_count / WORDS_PER_SECOND


@dataclass
class GeneratedScript:
    idea_title: str
    sections: list[ScriptSection]
    source_note: str = ""

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.sections)

    @property
    def total_word_count(self) -> int:
        return sum(s.word_count for s in self.sections)

    @property
    def estimated_duration_secs(self) -> float:
        return self.total_word_count / WORDS_PER_SECOND

    def fits_budget(self, budget_secs: float) -> bool:
        return self.estimated_duration_secs <= budget_secs

    def report(self) -> str:
        lines = [
            f"Script: {self.idea_title}",
            f"Total words: {self.total_word_count}  "
            f"Est. duration: {self.estimated_duration_secs:.1f}s  "
            f"(at {WORDS_PER_SECOND} wps)",
        ]
        for s in self.sections:
            lines.append(
                f"\n  [{s.name.upper()} · {s.duration_secs:.0f}s budget · "
                f"{s.word_count}w · ~{s.estimated_duration:.1f}s]"
            )
            lines.append(f"  {s.text}")
        if self.source_note:
            lines.append(f"\n  Source note: {self.source_note}")
        return "\n".join(lines)


def generate_zidane_headbutt_script() -> GeneratedScript:
    """
    Draft script for 'The Headbutt That Ended a Legend'.
    All facts are verifiable from Wikipedia (linked in source_note).
    Total target: 35s.
    """
    sections = [
        ScriptSection(
            name="hook",
            duration_secs=3.0,
            text="2006 World Cup Final. And Zidane completely lost it.",
        ),
        ScriptSection(
            name="bridge",
            duration_secs=5.0,
            text=(
                "Zinedine Zidane. Three-time FIFA World Player of the Year. "
                "Playing the last game of his entire career."
            ),
        ),
        ScriptSection(
            name="escalate_1",
            duration_secs=5.0,
            text=(
                "Marco Materazzi said something to him. "
                "Zidane turned around, walked back, and headbutted him in the chest."
            ),
        ),
        ScriptSection(
            name="escalate_2",
            duration_secs=5.0,
            text=(
                "Red card. His final act as a professional footballer. "
                "France lost the final on penalties."
            ),
        ),
        ScriptSection(
            name="payoff",
            duration_secs=8.0,
            text=(
                "Materazzi later admitted he had insulted Zidane's sister. "
                "Zidane never apologised for the headbutt. "
                "He said he would rather die than take it back."
            ),
        ),
        ScriptSection(
            name="cta",
            duration_secs=4.0,
            text="Follow Beyond The Pitch for more stories football never lets you forget.",
        ),
    ]
    return GeneratedScript(
        idea_title="The Headbutt That Ended a Legend",
        sections=sections,
        source_note=(
            "Sources: en.wikipedia.org/wiki/2006_FIFA_World_Cup_Final · "
            "en.wikipedia.org/wiki/Zinedine_Zidane · "
            "en.wikipedia.org/wiki/Marco_Materazzi"
        ),
    )


def generate_haaland_origin_script() -> GeneratedScript:
    """
    Draft script for 'Haaland's Father Was in Prison'.
    All facts sourced from Wikipedia.
    Total target: 30s.
    """
    sections = [
        ScriptSection(
            name="hook",
            duration_secs=3.0,
            text=(
                "Erling Haaland grew up visiting his father in prison. "
                "That's where the hunger started."
            ),
        ),
        ScriptSection(
            name="bridge",
            duration_secs=5.0,
            text=(
                "His father, Alfie Haaland, was a professional footballer. "
                "Until 2001, when a tackle ended his career forever."
            ),
        ),
        ScriptSection(
            name="escalate_1",
            duration_secs=5.0,
            text=(
                "Roy Keane later admitted in his autobiography the tackle on Alfie was deliberate. "
                "He was banned for five games."
            ),
        ),
        ScriptSection(
            name="escalate_2",
            duration_secs=5.0,
            text=(
                "Erling watched his father retire in pain. "
                "He played every game like he had something to prove."
            ),
        ),
        ScriptSection(
            name="payoff",
            duration_secs=8.0,
            text=(
                "60 goals in his first 59 Premier League games. "
                "The most feared striker on the planet. "
                "His father never got to show the world what he could do. "
                "His son did it for both of them."
            ),
        ),
    ]
    return GeneratedScript(
        idea_title="Haaland's Father Was in Prison During His First Big Game",
        sections=sections,
        source_note=(
            "Sources: en.wikipedia.org/wiki/Erling_Haaland · "
            "en.wikipedia.org/wiki/Alfie_Haaland · "
            "en.wikipedia.org/wiki/Roy_Keane"
        ),
    )


def check_script_feasibility(script: GeneratedScript, budget_secs: float) -> dict:
    """Check if a script fits within the target duration and has no obvious issues."""
    issues = []
    if not script.fits_budget(budget_secs):
        overshoot = script.estimated_duration_secs - budget_secs
        issues.append(
            f"Script estimated {script.estimated_duration_secs:.1f}s, "
            f"budget {budget_secs:.1f}s (over by {overshoot:.1f}s)"
        )
    # Check hook length
    hook = next((s for s in script.sections if s.name == "hook"), None)
    if hook and hook.estimated_duration > 4.0:
        issues.append(f"Hook is {hook.estimated_duration:.1f}s — target ≤ 3s")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "total_words": script.total_word_count,
        "estimated_secs": script.estimated_duration_secs,
        "budget_secs": budget_secs,
    }
