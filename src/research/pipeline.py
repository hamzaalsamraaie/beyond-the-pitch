"""
StoryboardPipeline — the Phase 2 orchestrator.

Sequence for each content_type requested:
  1. Fetch topic candidates from the research provider
  2. Safety-screen research items (reject bad topics immediately)
  3. Score and rank surviving candidates
  4. Filter below min_score_threshold
  5. Check originality against topic_history in DB
  6. Generate storyboard for the top candidate via the script writer
  7. Safety-screen the generated storyboard
  8. Persist to DB and record topic in topic_history
  9. Return the validated Storyboard

No YouTube uploading or automatic publishing occurs in Phase 2.
"""

from __future__ import annotations

from src.core.config import get_section
from src.core.database import (
    get_recent_topics,
    init_db,
    insert_storyboard,
    record_topic_used,
    storyboard_hash_exists,
)
from src.core.kill_switch import require_clear
from src.core.logger import configure_logging, get_logger
from src.research.models import ContentType, ScoredTopic, Storyboard
from src.research.providers import ResearchProvider
from src.research.safety import is_safe_research, is_safe_storyboard
from src.research.scorer import TopicScorer
from src.research.script_writer import BaseScriptWriter

logger = get_logger(__name__)


class StoryboardPipeline:
    def __init__(
        self,
        provider: ResearchProvider,
        writer: BaseScriptWriter,
        min_score_threshold: float | None = None,
        topics_per_type: int | None = None,
    ) -> None:
        self._provider = provider
        self._writer = writer
        cfg = get_section("research")
        self._min_score = (
            min_score_threshold
            if min_score_threshold is not None
            else cfg.get("min_score_threshold", 0.40)
        )
        self._topics_per_type = topics_per_type or cfg.get("topics_per_run", 5)

    def _load_existing_topics(self) -> list[str]:
        rows = get_recent_topics(days=90)
        return [r["topic"] for r in rows]

    def _run_for_type(
        self, content_type: ContentType, existing_topics: list[str]
    ) -> Storyboard | None:
        logger.info("pipeline_start", content_type=content_type.value)

        # 1. Fetch candidates
        candidates = self._provider.get_topics(content_type, count=self._topics_per_type)
        if not candidates:
            logger.warning("no_candidates", content_type=content_type.value)
            return None

        # 2. Safety screen research items
        safe_candidates = []
        for candidate in candidates:
            is_safe, violations = is_safe_research(candidate.research_items)
            if not is_safe:
                logger.warning(
                    "research_safety_rejected",
                    topic=candidate.title,
                    violations=violations,
                )
                continue
            safe_candidates.append(candidate)

        if not safe_candidates:
            logger.error("all_candidates_rejected_safety", content_type=content_type.value)
            return None

        # 3. Score and rank
        scorer = TopicScorer(existing_topics=existing_topics)
        ranked = scorer.rank(safe_candidates)

        logger.info(
            "topics_ranked",
            count=len(ranked),
            top_topic=ranked[0].candidate.title[:60] if ranked else "—",
            top_score=ranked[0].total_score if ranked else 0,
        )

        # 4. Filter below threshold
        ranked = [t for t in ranked if t.total_score >= self._min_score]
        if not ranked:
            logger.warning(
                "all_below_threshold",
                content_type=content_type.value,
                threshold=self._min_score,
            )
            return None

        # 5–8. Try candidates in rank order until one succeeds
        for scored_topic in ranked:
            result = self._try_generate(scored_topic, content_type)
            if result is not None:
                return result

        logger.error("all_candidates_failed", content_type=content_type.value)
        return None

    def _try_generate(
        self, scored_topic: ScoredTopic, content_type: ContentType
    ) -> Storyboard | None:
        title = scored_topic.candidate.title

        try:
            storyboard = self._writer.generate(scored_topic)
        except Exception as exc:
            logger.error("script_writer_failed", topic=title[:60], error=str(exc))
            return None

        # 7. Safety-screen the generated storyboard
        is_safe, violations = is_safe_storyboard(storyboard)
        if not is_safe:
            logger.warning("storyboard_safety_rejected", topic=title, violations=violations)
            return None

        # Dedup: reject if same script hash already in DB
        if storyboard_hash_exists(storyboard.script_hash):
            logger.warning("storyboard_duplicate_hash", topic=title)
            return None

        # 8. Persist
        try:
            insert_storyboard(
                topic=title,
                content_type=content_type.value,
                script_hash=storyboard.script_hash,
                storyboard_json=storyboard.to_json(),
                total_score=scored_topic.total_score,
                generated_by=storyboard.generated_by,
            )
            record_topic_used(title, content_type.value)
        except Exception as exc:
            logger.error("storyboard_save_failed", topic=title[:60], error=str(exc))
            return None

        logger.info(
            "storyboard_saved",
            topic=title[:60],
            duration=storyboard.total_duration,
            generated_by=storyboard.generated_by,
        )
        return storyboard

    def run(
        self, content_types: list[ContentType] | None = None
    ) -> list[Storyboard]:
        require_clear("StoryboardPipeline.run")
        configure_logging()
        init_db()

        active_types = content_types or [
            ContentType(ct)
            for ct in get_section("research").get(
                "default_content_types",
                ["football_moments", "player_stories", "football_motivation"],
            )
        ]

        existing_topics = self._load_existing_topics()
        results: list[Storyboard] = []

        for content_type in active_types:
            storyboard = self._run_for_type(content_type, existing_topics)
            if storyboard:
                results.append(storyboard)
                # Update existing_topics so later types benefit from originality check
                existing_topics.append(storyboard.title)

        logger.info("pipeline_complete", produced=len(results))
        return results
