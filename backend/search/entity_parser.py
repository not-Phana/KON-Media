"""Intelligent song entity parser and media title cleaner.

Extracts real song titles, artists, and franchise/soundtrack contexts from
cluttered, SEO-stuffed YouTube titles, e.g.:
'Zenless Zone Zero Season 3 Chapter 2 Opening / (I-BULL - iburu) jo0ji'
-> Artist: 'jo0ji', Song: 'I-BULL', Clean: 'jo0ji - I-BULL', Context: 'Zenless Zone Zero Season 3 Chapter 2 Opening'
"""

import re
from typing import Any, Dict, Optional, Tuple

NOISE_SUFFIXES = [
    re.compile(r"\[[^\]]*(?:official|video|audio|remaster|hd|4k|lyrics?|full\s*ver|mv)[^\]]*\]", re.IGNORECASE),
    re.compile(r"\([^)]*(?:official|video|audio|remaster|hd|4k|lyrics?|full\s*ver|mv)[^)]*\)", re.IGNORECASE),
    re.compile(r"\|\s*official\s*(?:video|audio|trailer|mv).*", re.IGNORECASE),
]

FRANCHISE_ROLES = [
    "opening",
    "ending",
    "op",
    "ed",
    "theme song",
    "theme",
    "soundtrack",
    "ost",
    "insert song",
    "boss theme",
    "battle theme",
    "cutscene",
]


def clean_parenthetical_readings(text: str) -> Tuple[str, Optional[str]]:
    """Handle bilingual titles in parens like '(I-BULL - iburu)' -> ('I-BULL', 'iburu')."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    elif text.startswith("【") and text.endswith("】"):
        text = text[1:-1].strip()
    elif text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()

    if " - " in text:
        parts = text.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    if " / " in text:
        parts = text.split(" / ", 1)
        return parts[0].strip(), parts[1].strip()
    return text, None


def parse_media_entity(raw_title: str, uploader: str = "") -> Dict[str, Any]:
    """Parse cluttered candidate title into clean artist, song, and franchise context."""
    title = raw_title.strip()

    # Default fallback
    result: Dict[str, Any] = {
        "raw_title": title,
        "clean_title": title,
        "song_title": None,
        "artist": None,
        "context_source": None,
        "is_cluttered": False,
        "is_cutscene": False,
    }

    if not title:
        return result

    # Check for cutscene / gameplay without song
    lower_title = title.lower()
    if any(k in lower_title for k in ("cutscene", "gameplay", "walkthrough", "full scene", "boss fight", "reaction to")):
        if not any(k in lower_title for k in ("official audio", "official mv", "music video", "by ")):
            result["is_cutscene"] = True

    # Strip pure wrapper noise like [Official Video] or (HD)
    clean_base = title
    for pat in NOISE_SUFFIXES:
        clean_base = pat.sub("", clean_base).strip()

    # -------------------------------------------------------------
    # Pattern 1: Slash / Pipe separation
    # e.g. "Zenless Zone Zero Season 3 Chapter 2 Opening / (I-BULL - iburu) jo0ji"
    # e.g. "Chainsaw Man OP Full / Kenshi Yonezu - KICK BACK"
    # -------------------------------------------------------------
    for sep in (" / ", " // ", " | "):
        if sep in clean_base:
            parts = clean_base.split(sep, 1)
            left, right = parts[0].strip(), parts[1].strip()

            # Identify which side is franchise/context and which is the song
            left_has_role = any(r in left.lower() for r in FRANCHISE_ROLES)
            right_has_role = any(r in right.lower() for r in FRANCHISE_ROLES)

            context_part = None
            song_part = None

            if left_has_role and not right_has_role:
                context_part, song_part = left, right
            elif right_has_role and not left_has_role:
                context_part, song_part = right, left

            if context_part and song_part:
                # Parse song_part: e.g. "(I-BULL - iburu) jo0ji" or "Kenshi Yonezu - KICK BACK"
                artist = None
                song = None

                # Subpattern A: "(Song - Reading) Artist"
                paren_match = re.match(r"^[\(\[【](.+?)[\)\]】]\s*(.+)$", song_part)
                if paren_match:
                    in_paren = paren_match.group(1).strip()
                    outside = paren_match.group(2).strip()
                    primary_song, _ = clean_parenthetical_readings(in_paren)
                    song = primary_song
                    artist = outside

                # Subpattern B: "Artist - (Song)" or "Artist - Song"
                elif " - " in song_part:
                    s_parts = song_part.split(" - ", 1)
                    artist = s_parts[0].strip()
                    s_title, _ = clean_parenthetical_readings(s_parts[1].strip())
                    song = s_title

                # Subpattern C: "Song by Artist"
                elif " by " in song_part.lower():
                    by_parts = re.split(r"\s+by\s+", song_part, flags=re.IGNORECASE, maxsplit=1)
                    song = by_parts[0].strip()
                    artist = by_parts[1].strip()

                if song and artist:
                    clean_display = f"{artist} - {song}"
                    result.update({
                        "clean_title": clean_display,
                        "song_title": song,
                        "artist": artist,
                        "context_source": context_part,
                        "is_cluttered": True,
                    })
                    return result

    # -------------------------------------------------------------
    # Pattern 2: Hyphen franchise prefix
    # e.g. "Zenless Zone Zero - I-BULL by jo0ji"
    # e.g. "Bleach TYBW - Number One (Hazel Fernandes)"
    # -------------------------------------------------------------
    if " - " in clean_base:
        parts = clean_base.split(" - ")
        if len(parts) >= 2:
            first = parts[0].strip()
            first_has_role = any(r in first.lower() for r in FRANCHISE_ROLES) or any(
                f in first.lower() for f in ("ost", "soundtrack", "season", "chapter", "episode")
            )
            if first_has_role and len(parts) >= 3:
                # "Anime OST - Artist - Song"
                context_part = first
                artist = parts[1].strip()
                song, _ = clean_parenthetical_readings(parts[2].strip())
                result.update({
                    "clean_title": f"{artist} - {song}",
                    "song_title": song,
                    "artist": artist,
                    "context_source": context_part,
                    "is_cluttered": True,
                })
                return result

    # -------------------------------------------------------------
    # Pattern 3: Standard "Artist - Title" with trailing anime/game parenthetical
    # e.g. "LiSA - Gurenge (Demon Slayer OP 1)"
    # -------------------------------------------------------------
    trailing_paren_match = re.match(r"^(.+?\s*-\s*.+?)\s*[\(\[【](.+?)[\)\]】]$", clean_base)
    if trailing_paren_match:
        main_part = trailing_paren_match.group(1).strip()
        paren_content = trailing_paren_match.group(2).strip()
        if any(r in paren_content.lower() for r in FRANCHISE_ROLES):
            if " - " in main_part:
                m_parts = main_part.split(" - ", 1)
                artist, song = m_parts[0].strip(), m_parts[1].strip()
                result.update({
                    "clean_title": f"{artist} - {song}",
                    "song_title": song,
                    "artist": artist,
                    "context_source": paren_content,
                    "is_cluttered": True,
                })
                return result

    # If uploader is available and looks like an artist or topic
    if uploader and " - Topic" in uploader:
        topic_artist = uploader.replace(" - Topic", "").strip()
        if " - " not in clean_base:
            result.update({
                "clean_title": f"{topic_artist} - {clean_base}",
                "song_title": clean_base,
                "artist": topic_artist,
            })
            return result

    return result
