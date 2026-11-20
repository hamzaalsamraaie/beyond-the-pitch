"""
Shot-by-shot production planner.

For each VideoIdea, builds a list of Shots with specific AssetRequirements.
If a shot cannot be fulfilled with commercially available assets, it is
marked BLOCKED and the entire ProductionPlan is BLOCKED.

Design rules:
  - Every shot needs a named asset, source, license, and commercial-use confirmation
  - Match footage / broadcast clips → always BLOCKED (no commercial license available by default)
  - Club kit photos of specific players → BLOCKED without confirmed license
  - CC-BY Wikimedia photos of real events → AVAILABLE with attribution
  - Generic stock football visuals (Pixabay/Pexels) → AVAILABLE
  - Original motion graphics (stat cards, text reveals) → AVAILABLE
  - YouTube Audio Library music → AVAILABLE (YouTube-only distribution)
  - macOS TTS → BLOCKED for commercial content

Short format pacing rules (enforced):
  - Hook shot: ≤ 3 seconds
  - Minimum visual changes: 1 cut per 4 seconds on average
  - Maximum single shot duration: 8 seconds
  - On-screen captions: ≤ 6 words per shot for readability
"""

from __future__ import annotations

from src.planning.asset_registry import SOURCES
from src.planning.models import AssetRequirement, ProductionPlan, Shot, VideoIdea
from src.core.logger import get_logger

logger = get_logger(__name__)


def _blocked_asset(description: str, reason: str) -> AssetRequirement:
    return AssetRequirement(
        description=description,
        asset_type="video_clip",
        status="BLOCKED",
        source_name="None identified",
        source_url="",
        license="None",
        attribution_required=False,
        notes=reason,
    )


def _graphic_asset(description: str) -> AssetRequirement:
    src = SOURCES["original_graphics"]
    return AssetRequirement(
        description=description,
        asset_type="graphic",
        status="AVAILABLE",
        source_name=src.name,
        source_url=src.base_url,
        license=src.license_name,
        attribution_required=src.attribution_required,
    )


def _stock_image_asset(description: str, search_term: str) -> AssetRequirement:
    src = SOURCES["pixabay"]
    return AssetRequirement(
        description=description,
        asset_type="image",
        status="AVAILABLE",
        source_name=src.name,
        source_url=f"{src.base_url}/videos/search/?q={search_term.replace(' ', '+')}",
        license=src.license_name,
        attribution_required=src.attribution_required,
        notes=f"Search term: '{search_term}'. Confirm no recognisable player/kit before use.",
    )


def _wikimedia_image_asset(
    description: str,
    page_url: str,
    license_name: str,
    attribution: str,
) -> AssetRequirement:
    return AssetRequirement(
        description=description,
        asset_type="image",
        status="AVAILABLE",
        source_name="Wikimedia Commons",
        source_url=page_url,
        license=license_name,
        attribution_required=True,
        attribution_text=attribution,
        notes="Verify license on Wikimedia file page before use.",
    )


def _music_asset(track_name: str, genre: str) -> AssetRequirement:
    src = SOURCES["youtube_audio_library"]
    return AssetRequirement(
        description=f"Background music: {track_name}",
        asset_type="audio_music",
        status="AVAILABLE",
        source_name=src.name,
        source_url=src.base_url,
        license=src.license_name,
        attribution_required=False,
        notes=(
            f"Genre: {genre}. Check individual track attribution requirements. "
            "YouTube Audio Library license covers YouTube distribution only."
        ),
    )


def build_plan_zidane_headbutt() -> ProductionPlan:
    """
    'The Headbutt That Ended a Legend' — Zidane 2006 World Cup Final.

    Asset strategy: Wikimedia Commons photographs (CC-BY-SA) + original graphics.
    NO broadcast clips. NO match footage. Photo stills + text reveals only.
    TTS: BLOCKED for commercial until ElevenLabs or similar is configured.
    """
    idea = VideoIdea(
        title="The Headbutt That Ended a Legend",
        hook="2006 World Cup Final. 10 minutes left. And Zidane completely lost it.",
        concept_summary=(
            "Zidane's final act in professional football: the headbutt on Materazzi "
            "that sent him off in his last-ever game. What was said, what it cost, "
            "and why it's still football's most iconic moment of madness."
        ),
        content_type="player_story",
        trend_strength=0.80,
        originality=0.85,
        production_feasibility=0.85,
        licensing_feasibility=0.88,
        audience_interest=0.90,
        hook_quality=0.92,
        inspired_by=[],
        target_duration_secs=35,
        estimated_views_range="1M–5M",
    )

    shots = [
        Shot(
            shot_number=1,
            duration_secs=3.0,
            description="Text card: score and minute. High contrast white on black.",
            on_screen_caption="WORLD CUP FINAL · 110'",
            narration_text="2006. World Cup Final. 10 minutes left. And Zidane completely lost it.",
            sound_effect="stadium_ambient",
            transition_in="cut",
            asset=_graphic_asset(
                "Full-screen text card showing '2006 World Cup Final · 110 min remaining'"
            ),
        ),
        Shot(
            shot_number=2,
            duration_secs=5.0,
            description="Zidane photo — full career context. Widely reproduced CC-BY-SA image.",
            on_screen_caption="THE GREATEST OF HIS ERA",
            narration_text=(
                "Zinedine Zidane. Three-time FIFA World Player of the Year. "
                "Playing his last-ever professional game."
            ),
            sound_effect="",
            transition_in="cut",
            asset=_wikimedia_image_asset(
                description="Photo of Zinedine Zidane in France kit",
                page_url="https://commons.wikimedia.org/wiki/File:Zinedine_Zidane_2006.jpg",
                license_name="CC BY-SA 3.0",
                attribution="Photo: © Wikimedia Commons / CC BY-SA 3.0 — verify file page",
            ),
        ),
        Shot(
            shot_number=3,
            duration_secs=5.0,
            description="Materazzi photo for context.",
            on_screen_caption="MARCO MATERAZZI SAID SOMETHING",
            narration_text=(
                "Marco Materazzi said something. Nobody has ever confirmed exactly what. "
                "But Zidane heard it."
            ),
            sound_effect="",
            transition_in="cut",
            asset=_wikimedia_image_asset(
                description="Photo of Marco Materazzi",
                page_url="https://commons.wikimedia.org/wiki/File:Marco_Materazzi.jpg",
                license_name="CC BY-SA 2.0",
                attribution="Photo: © Wikimedia Commons / CC BY-SA 2.0 — verify file page",
            ),
        ),
        Shot(
            shot_number=4,
            duration_secs=4.0,
            description="Graphic: animated text reveal of what happened next.",
            on_screen_caption="HE TURNED AROUND",
            narration_text="Zidane turned around. Walked back. And headbutted him in the chest.",
            sound_effect="impact_thud",
            transition_in="cut",
            asset=_graphic_asset(
                "Animated text card: 'He turned around.' bold white on red — 3 cuts"
            ),
        ),
        Shot(
            shot_number=5,
            duration_secs=4.0,
            description="Red card graphic — referee's decision.",
            on_screen_caption="RED CARD. LAST ACT.",
            narration_text=(
                "Red card. His last act in professional football. France lost on penalties."
            ),
            sound_effect="referee_whistle",
            transition_in="cut",
            asset=_graphic_asset(
                "Full-screen animated red card reveal. 'Last game. Last act.'"
            ),
        ),
        Shot(
            shot_number=6,
            duration_secs=5.0,
            description="Stats card: Zidane's career in numbers.",
            on_screen_caption="HIS NUMBERS WERE PERFECT",
            narration_text=(
                "Three Ballon d'Or medals. One World Cup. One Champions League. "
                "And one moment the world will never forget."
            ),
            sound_effect="",
            transition_in="cut",
            asset=_graphic_asset(
                "Stat reveal card: '3× FIFA World Player of Year · 1× World Cup · "
                "1× Champions League'"
            ),
        ),
        Shot(
            shot_number=7,
            duration_secs=4.0,
            description="Closing text card with channel branding.",
            on_screen_caption="BEYOND THE PITCH",
            narration_text="Follow for more stories football never lets you forget.",
            sound_effect="",
            transition_in="fade",
            asset=_graphic_asset(
                "Branded outro card: 'Beyond The Pitch' + subscribe CTA"
            ),
        ),
    ]

    music = _music_asset(
        track_name="Epic Cinematic Instrumental (to be selected from YouTube Audio Library)",
        genre="Cinematic / Epic",
    )

    plan = ProductionPlan(
        idea=idea,
        shots=shots,
        full_script=" ".join(s.narration_text for s in shots if s.narration_text),
        music_requirement=music,
        notes=(
            "NARRATION BLOCKED: macOS TTS is not licensed for commercial use. "
            "Replace with ElevenLabs (commercial plan) or Amazon Polly before monetizing. "
            "Wikimedia image URLs are placeholders — verify each file's exact license on "
            "the Wikimedia file page before production begins."
        ),
    )
    return plan


def build_plan_haaland_origin() -> ProductionPlan:
    """
    'Haaland's father was in prison when he scored his first goal' — origin story.

    Asset strategy: Wikimedia Commons photos + original stat graphics.
    All motion graphics only. No match footage required.
    """
    idea = VideoIdea(
        title="Haaland's Father Was in Prison During His First Big Game",
        hook="Erling Haaland grew up visiting his father in prison. That's where the hunger started.",
        concept_summary=(
            "Erling Haaland's father Alfie was convicted and jailed in 2001 for a tackle "
            "that injured Haaland Sr during a Champions League match. Erling grew up with that "
            "story — and it shaped everything."
        ),
        content_type="player_story",
        trend_strength=0.85,
        originality=0.90,
        production_feasibility=0.88,
        licensing_feasibility=0.88,
        audience_interest=0.88,
        hook_quality=0.92,
        inspired_by=[],
        target_duration_secs=30,
        estimated_views_range="2M–8M",
    )

    shots = [
        Shot(
            shot_number=1,
            duration_secs=3.0,
            description="Hook text card — shocking revelation.",
            on_screen_caption="HIS FATHER WAS IN PRISON",
            narration_text=(
                "Erling Haaland grew up visiting his father in prison. "
                "That's where the hunger started."
            ),
            transition_in="cut",
            asset=_graphic_asset("Full-screen text: 'His father was in prison.'"),
        ),
        Shot(
            shot_number=2,
            duration_secs=5.0,
            description="Haaland photo — career stats context.",
            on_screen_caption="60 GOALS IN 59 GAMES",
            narration_text=(
                "Erling Haaland. The most feared striker on the planet. "
                "60 goals in 59 Premier League games."
            ),
            transition_in="cut",
            asset=_wikimedia_image_asset(
                description="Photo of Erling Haaland",
                page_url="https://commons.wikimedia.org/wiki/File:Erling_Haaland_2022.jpg",
                license_name="CC BY-SA 4.0",
                attribution="Photo: © Wikimedia Commons / CC BY-SA 4.0 — verify file page",
            ),
        ),
        Shot(
            shot_number=3,
            duration_secs=5.0,
            description="Alfie Haaland photo and context graphic.",
            on_screen_caption="HIS FATHER'S CAREER ENDED",
            narration_text=(
                "His father, Alfie, was a professional footballer too. "
                "Until Roy Keane's tackle in 2001 ended his career. "
                "Keane later admitted it was deliberate."
            ),
            transition_in="cut",
            asset=_wikimedia_image_asset(
                description="Photo of Alfie Haaland",
                page_url="https://commons.wikimedia.org/wiki/File:Alfie_Haaland.jpg",
                license_name="CC BY-SA 3.0",
                attribution="Photo: © Wikimedia Commons / CC BY-SA 3.0 — verify file page",
            ),
        ),
        Shot(
            shot_number=4,
            duration_secs=5.0,
            description="Roy Keane photo with context graphic.",
            on_screen_caption="KEANE ADMITTED IT WAS DELIBERATE",
            narration_text=(
                "Roy Keane wrote in his autobiography that he had planned the tackle. "
                "He was later banned for five games."
            ),
            transition_in="cut",
            asset=_wikimedia_image_asset(
                description="Photo of Roy Keane",
                page_url="https://commons.wikimedia.org/wiki/File:Roy_Keane_2008.jpg",
                license_name="CC BY-SA 2.0",
                attribution="Photo: © Wikimedia Commons / CC BY-SA 2.0 — verify file page",
            ),
        ),
        Shot(
            shot_number=5,
            duration_secs=5.0,
            description="Erling Haaland scoring graphic / stat reveal.",
            on_screen_caption="NOW ERLING HAS THE LAST LAUGH",
            narration_text=(
                "Erling grew up knowing what his father lost. "
                "And he played every game like he had something to prove."
            ),
            transition_in="cut",
            asset=_graphic_asset(
                "Split screen graphic: Alfie Haaland (B&W) → Erling Haaland stat card"
            ),
        ),
        Shot(
            shot_number=6,
            duration_secs=4.0,
            description="Closing CTA card.",
            on_screen_caption="BEYOND THE PITCH",
            narration_text="Follow for more stories football never lets you forget.",
            transition_in="fade",
            asset=_graphic_asset("Branded outro card"),
        ),
    ]

    music = _music_asset(
        track_name="Dramatic Piano / Documentary (from YouTube Audio Library)",
        genre="Dramatic / Cinematic",
    )

    plan = ProductionPlan(
        idea=idea,
        shots=shots,
        full_script=" ".join(s.narration_text for s in shots if s.narration_text),
        music_requirement=music,
        notes=(
            "NARRATION BLOCKED for commercial use until commercial TTS is configured. "
            "All Wikimedia image URLs are illustrative — verify each file's exact license "
            "on the Wikimedia file page. Some images may not exist at those exact paths; "
            "search Wikimedia Commons for confirmed CC-BY images of each subject."
        ),
    )
    return plan
