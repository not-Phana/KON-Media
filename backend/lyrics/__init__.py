"""Lyrics service package for KON Media."""

from backend.lyrics.lyrics_service import (
    LyricsService,
    LyricsCache,
    clean_music_title,
    parse_lrc,
    get_lyrics_service,
)

__all__ = [
    "LyricsService",
    "LyricsCache",
    "clean_music_title",
    "parse_lrc",
    "get_lyrics_service",
]
