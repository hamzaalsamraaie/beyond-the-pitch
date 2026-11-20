"""
Highlight scorer: finds the most exciting windows in a football transcript.

Scoring uses three tiers of football excitement keywords plus density bonuses.
Windows are scored on a rolling basis; the highest-scoring window(s) are
returned as candidates for clip selection.

Tier 1 (+3.0): peak excitement exclamatives
Tier 2 (+2.0): football action moments
Tier 3 (+1.0): narrative / emotional beats
Density bonus: extra 0.5 per additional tier-1 word within 10s of the first
"""

from __future__ import annotations

from src.clipping.models import ScoredWindow, Transcript
from src.core.logger import get_logger

logger = get_logger(__name__)

# ── Keyword tiers ──────────────────────────────────────────────────────────────

_TIER1: frozenset[str] = frozenset({
    "goal", "incredible", "unbelievable", "unreal", "sensational",
    "spectacular", "magnificent", "brilliant", "extraordinary",
    "outstanding", "phenomenal", "what a", "oh my", "yes yes yes",
    "screamer", "worldie",
})

_TIER2: frozenset[str] = frozenset({
    "shot", "save", "penalty", "free kick", "header",
    "volley", "assist", "red card", "yellow card", "offside",
    "champion", "champions", "legend", "world class", "top class",
    "corner", "hat trick", "hat-trick", "equaliser", "equalizer",
    "winner", "winning", "comeback", "comeback win", "stunner",
})

_TIER3: frozenset[str] = frozenset({
    "never", "first", "last", "record", "history", "historic",
    "miracle", "upset", "shock", "incredible", "unforgettable",
    "emotional", "tears", "reaction", "moment", "career",
    "debut", "farewell", "retirement", "legend", "captain",
})

_TIER_SCORES: dict[str, float] = {}
for _w in _TIER3:
    _TIER_SCORES[_w] = 1.0
for _w in _TIER2:
    _TIER_SCORES[_w] = 2.0
for _w in _TIER1:
    _TIER_SCORES[_w] = 3.0


def _score_words(words: list[str]) -> tuple[float, list[str]]:
    """Return (raw_score, list of matched peak words)."""
    score = 0.0
    peaks: list[str] = []
    for w in words:
        clean = w.strip().lower().rstrip(".,!?;:")
        if clean in _TIER_SCORES:
            score += _TIER_SCORES[clean]
            if _TIER_SCORES[clean] >= 2.0:
                peaks.append(clean)
    # Density bonus: >3 tier-1/2 hits in a window = extra points
    if len(peaks) >= 3:
        score += (len(peaks) - 2) * 0.5
    return score, peaks


# ── Window scorer ─────────────────────────────────────────────────────────────

def score_windows(
    transcript: Transcript,
    window_secs: float = 50.0,
    step_secs: float = 5.0,
    min_words: int = 3,
) -> list[ScoredWindow]:
    """
    Slide a window across the transcript and score each position.

    Returns list of ScoredWindow sorted by score descending.
    Windows with fewer than min_words are skipped.
    """
    if not transcript.segments:
        return []

    total = transcript.source_duration or (
        transcript.segments[-1].end if transcript.segments else 0.0
    )
    if total <= 0:
        return []

    all_words = transcript.all_words
    if not all_words:
        return []

    scored: list[ScoredWindow] = []
    t = 0.0
    while t + window_secs <= total + step_secs:
        win_start = t
        win_end = min(t + window_secs, total)
        window_words = transcript.words_in_range(win_start, win_end)

        if len(window_words) < min_words:
            t += step_secs
            continue

        word_texts = [w.word for w in window_words]
        raw_score, peaks = _score_words(word_texts)

        # Normalise by window length to avoid favouring longer windows
        density = raw_score / (win_end - win_start)

        # Hook quality bonus: score for first 5s being exciting
        hook_words = transcript.words_in_range(win_start, win_start + 5.0)
        hook_score, _ = _score_words([w.word for w in hook_words])
        hook_bonus = hook_score * 0.3  # 30% bonus for strong hook

        final_score = density + hook_bonus
        hook_text = " ".join(w.word for w in hook_words).strip()

        scored.append(ScoredWindow(
            start=win_start,
            end=win_end,
            score=final_score,
            peak_words=peaks[:8],
            hook_text=hook_text,
        ))
        t += step_secs

    scored.sort(key=lambda w: w.score, reverse=True)
    logger.info(
        "highlight_windows_scored",
        total_windows=len(scored),
        top_score=round(scored[0].score, 3) if scored else 0,
        top_peaks=scored[0].peak_words[:3] if scored else [],
    )
    return scored


def top_window(
    transcript: Transcript,
    target_duration: float = 45.0,
    min_duration: float = 20.0,
) -> ScoredWindow | None:
    """Return the single best window, adjusting length to target_duration."""
    source_dur = transcript.source_duration or (
        transcript.segments[-1].end if transcript.segments else 0.0
    )
    effective_window = min(target_duration, source_dur) if source_dur > 0 else target_duration

    windows = score_windows(transcript, window_secs=effective_window)
    if not windows:
        windows = score_windows(transcript, window_secs=min(min_duration, source_dur or min_duration))
    if not windows:
        # Fallback for no-speech footage (B-roll, crowd atmosphere): return a
        # window covering the available duration so the editor can still run.
        if source_dur >= min_duration:
            clip_dur = min(target_duration, source_dur)
            logger.info("highlight_fallback_no_speech", duration=round(clip_dur, 1))
            return ScoredWindow(
                start=0.0,
                end=clip_dur,
                score=0.0,
                peak_words=[],
                hook_text="",
            )
        return None

    best = windows[0]
    # Trim to natural sentence boundary if the top window ends mid-sentence
    segs = transcript.segments_in_range(best.start, best.end)
    if segs:
        best = ScoredWindow(
            start=best.start,
            end=min(segs[-1].end, best.start + effective_window),
            score=best.score,
            peak_words=best.peak_words,
            hook_text=best.hook_text,
        )
    return best
