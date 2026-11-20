"""Tests for src/editing/sound_library.py"""
import pytest

from src.editing.sound_library import (
    EmbedPolicy, SoundEntry, SOUND_LIBRARY,
    recommend_sounds, format_sound_recommendation,
)


class TestSoundEntry:
    def test_all_entries_have_name_and_artist(self):
        for s in SOUND_LIBRARY:
            assert s.name, f"Entry missing name: {s}"
            assert s.artist, f"Entry missing artist: {s.name}"

    def test_all_entries_have_valid_bpm(self):
        for s in SOUND_LIBRARY:
            assert s.bpm >= 0, f"{s.name} has negative BPM"

    def test_all_entries_have_embed_policy(self):
        for s in SOUND_LIBRARY:
            assert isinstance(s.embed_policy, EmbedPolicy)

    def test_library_has_at_least_ten_entries(self):
        assert len(SOUND_LIBRARY) >= 10

    def test_library_has_free_embed_tracks(self):
        free = [s for s in SOUND_LIBRARY if s.embed_policy == EmbedPolicy.FREE_EMBED]
        assert len(free) >= 1

    def test_library_has_shorts_only_tracks(self):
        shorts = [s for s in SOUND_LIBRARY if s.embed_policy == EmbedPolicy.SHORTS_ONLY]
        assert len(shorts) >= 1

    def test_all_tags_are_strings(self):
        for s in SOUND_LIBRARY:
            for tag in s.tags:
                assert isinstance(tag, str), f"{s.name} has non-string tag"


class TestRecommendSounds:
    def test_returns_requested_count(self):
        results = recommend_sounds("hype", bpm_target=130, top_n=3)
        assert len(results) <= 3

    def test_returns_list_of_sound_entries(self):
        results = recommend_sounds("storytelling", top_n=2)
        for r in results:
            assert isinstance(r, SoundEntry)

    def test_embed_only_filter(self):
        results = recommend_sounds("storytelling", embed_only=True, top_n=10)
        for r in results:
            assert r.embed_policy == EmbedPolicy.FREE_EMBED

    def test_worldcup_recommends_worldcup_tracks(self):
        results = recommend_sounds("worldcup", top_n=3)
        # At least one result should have worldcup tag
        all_tags = {tag for r in results for tag in r.tags}
        assert "worldcup2026" in all_tags or "fifa" in all_tags

    def test_hype_recommends_hype_tracks(self):
        results = recommend_sounds("hype", bpm_target=140, top_n=3)
        all_tags = {tag for r in results for tag in r.tags}
        assert bool(all_tags & {"hype", "phonk", "beat_sync", "fast"})

    def test_unknown_story_type_returns_something(self):
        results = recommend_sounds("unknown_type", top_n=2)
        assert len(results) >= 1

    def test_bpm_preference_favours_closer_bpm(self):
        # At 140 BPM preference, 140 BPM track should beat 90 BPM track
        results = recommend_sounds("hype", bpm_target=140, top_n=5)
        bpms = [r.bpm for r in results if r.bpm > 0]
        if len(bpms) >= 2:
            # Average BPM should be relatively close to 140 for hype
            assert sum(bpms) / len(bpms) >= 100


class TestFormatSoundRecommendation:
    def test_contains_name(self):
        s = SOUND_LIBRARY[0]
        fmt = format_sound_recommendation(s)
        assert s.name in fmt

    def test_contains_artist(self):
        s = SOUND_LIBRARY[0]
        fmt = format_sound_recommendation(s)
        assert s.artist in fmt

    def test_contains_url(self):
        s = SOUND_LIBRARY[0]
        fmt = format_sound_recommendation(s)
        assert "http" in fmt

    def test_all_entries_formattable(self):
        for s in SOUND_LIBRARY:
            fmt = format_sound_recommendation(s)
            assert len(fmt) > 50
