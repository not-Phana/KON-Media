//! Intelligent song entity parser and media title cleaner.
//!
//! Extracts real song titles, artists, and franchise/soundtrack contexts from
//! cluttered, SEO-stuffed YouTube titles, e.g.:
//! "Zenless Zone Zero Season 3 Chapter 2 Opening / (I-BULL - iburu) jo0ji"
//! -> Artist: "jo0ji", Song: "I-BULL", Clean: "jo0ji - I-BULL", Context: "Zenless Zone Zero Season 3 Chapter 2 Opening"

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParsedEntity {
    pub raw_title: String,
    pub clean_title: String,
    pub song_title: Option<String>,
    pub artist: Option<String>,
    pub context_source: Option<String>,
    pub is_cluttered: bool,
    pub is_cutscene: bool,
}

const NOISE_TERMS: &[&str] = &[
    "official video",
    "official music video",
    "official audio",
    "official visualizer",
    "music video",
    "official mv",
    "lyric video",
    "lyrics video",
    "lyrics",
    "remastered",
    "remaster",
    "hd",
    "4k",
    "full ver",
    "full version",
    "visualizer",
    "audio",
    "mv",
];

const FRANCHISE_ROLES: &[&str] = &[
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
];

const CUTSCENE_KEYWORDS: &[&str] = &[
    "cutscene",
    "gameplay",
    "walkthrough",
    "full scene",
    "boss fight",
    "reaction to",
];

/// Handle bilingual or parenthetical titles like "(I-BULL - iburu)" -> ("I-BULL", Some("iburu")).
pub fn clean_parenthetical_readings(text: &str) -> (String, Option<String>) {
    let mut trimmed = text.trim();
    if (trimmed.starts_with('(') && trimmed.ends_with(')'))
        || (trimmed.starts_with('[') && trimmed.ends_with(']'))
        || (trimmed.starts_with('【') && trimmed.ends_with('】'))
        || (trimmed.starts_with('{') && trimmed.ends_with('}'))
    {
        if trimmed.len() >= 2 {
            trimmed = trimmed[1..trimmed.len() - 1].trim();
        }
    }

    if let Some(pos) = trimmed.find(" - ") {
        let left = trimmed[..pos].trim().to_string();
        let right = trimmed[pos + 3..].trim().to_string();
        return (left, Some(right));
    }
    if let Some(pos) = trimmed.find(" / ") {
        let left = trimmed[..pos].trim().to_string();
        let right = trimmed[pos + 3..].trim().to_string();
        return (left, Some(right));
    }

    (trimmed.to_string(), None)
}

/// Strip bracketed or parenthesized noise like [Official Video] or (HD).
pub fn strip_enclosed_noise(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];
        if ch == '[' || ch == '(' || ch == '【' {
            let close = match ch {
                '[' => ']',
                '(' => ')',
                '【' => '】',
                _ => ')',
            };
            if let Some(close_idx) = chars[i + 1..].iter().position(|&c| c == close) {
                let inner: String = chars[i + 1..i + 1 + close_idx].iter().collect();
                let inner_lower = inner.to_lowercase();
                let is_noise = NOISE_TERMS.iter().any(|&noise| inner_lower.contains(noise));
                if is_noise {
                    i = i + 1 + close_idx + 1;
                    continue;
                }
            }
        }
        result.push(ch);
        i += 1;
    }

    result.trim().to_string()
}

/// Strip trailing pipe suffixes such as "| Official Video" or "| 4K MV".
pub fn strip_pipe_noise(text: &str) -> String {
    if let Some(pos) = text.rfind('|') {
        let suffix = text[pos + 1..].trim().to_lowercase();
        if NOISE_TERMS.iter().any(|&term| suffix.contains(term)) {
            return text[..pos].trim().to_string();
        }
    }
    text.to_string()
}

/// Parse cluttered candidate title into clean artist, song, and franchise context.
pub fn parse_media_entity(raw_title: &str, uploader: &str) -> ParsedEntity {
    let title = raw_title.trim();
    if title.is_empty() {
        return ParsedEntity {
            raw_title: String::new(),
            clean_title: String::new(),
            song_title: None,
            artist: None,
            context_source: None,
            is_cluttered: false,
            is_cutscene: false,
        };
    }

    let lower_title = title.to_lowercase();
    let mut is_cutscene = false;
    if CUTSCENE_KEYWORDS.iter().any(|&k| lower_title.contains(k)) {
        let music_indicator = [
            "official audio",
            "official mv",
            "music video",
            "by ",
            "original soundtrack",
        ]
        .iter()
        .any(|&k| lower_title.contains(k));
        if !music_indicator {
            is_cutscene = true;
        }
    }

    let mut clean_base = strip_pipe_noise(title);
    clean_base = strip_enclosed_noise(&clean_base);

    let mut is_cluttered = clean_base.len() < title.len() || clean_base.contains('/') || clean_base.contains('|');

    let mut context_part: Option<String> = None;
    let mut song_part: Option<String> = None;

    // Pattern 1: Slash / Pipe separation
    for sep in &[" // ", " / ", " | "] {
        if let Some(pos) = clean_base.find(sep) {
            let left = clean_base[..pos].trim();
            let right = clean_base[pos + sep.len()..].trim();

            let left_lower = left.to_lowercase();
            let right_lower = right.to_lowercase();
            let left_has_role = FRANCHISE_ROLES.iter().any(|&r| left_lower.contains(r));
            let right_has_role = FRANCHISE_ROLES.iter().any(|&r| right_lower.contains(r));

            if left_has_role && !right_has_role {
                context_part = Some(left.to_string());
                song_part = Some(right.to_string());
                is_cluttered = true;
                break;
            } else if right_has_role && !left_has_role {
                context_part = Some(right.to_string());
                song_part = Some(left.to_string());
                is_cluttered = true;
                break;
            } else {
                song_part = Some(clean_base.clone());
            }
        }
    }

    let base_song = song_part.unwrap_or_else(|| clean_base.clone());
    let mut detected_artist: Option<String> = None;
    let mut detected_song: Option<String> = None;

    // Subpattern A: "(Song - Reading) Artist" or "[Song] Artist"
    if base_song.starts_with('(') || base_song.starts_with('[') || base_song.starts_with('【') {
        let first_char = base_song.chars().next().unwrap();
        let close_char = match first_char {
            '(' => ')',
            '[' => ']',
            '【' => '】',
            _ => ')',
        };
        if let Some(close_idx) = base_song.find(close_char) {
            let in_paren = &base_song[first_char.len_utf8()..close_idx];
            let outside = base_song[close_idx + close_char.len_utf8()..].trim();
            if !outside.is_empty() {
                let (primary_song, _) = clean_parenthetical_readings(in_paren);
                detected_song = Some(primary_song);
                detected_artist = Some(outside.to_string());
                is_cluttered = true;
            }
        }
    }

    // Subpattern B: "Artist - Title" or "Title - Artist"
    if detected_song.is_none() {
        if let Some(dash_pos) = base_song.find(" - ") {
            let p1 = base_song[..dash_pos].trim();
            let p2 = base_song[dash_pos + 3..].trim();

            let (c1, _) = clean_parenthetical_readings(p1);
            let (c2, _) = clean_parenthetical_readings(p2);

            let up_lower = uploader.trim().to_lowercase();
            if !up_lower.is_empty() && up_lower.contains(&c1.to_lowercase()) {
                detected_artist = Some(c1);
                detected_song = Some(c2);
            } else if !up_lower.is_empty() && up_lower.contains(&c2.to_lowercase()) {
                detected_artist = Some(c2);
                detected_song = Some(c1);
            } else {
                detected_artist = Some(c1);
                detected_song = Some(c2);
            }
        } else if let Some(by_pos) = base_song.to_lowercase().find(" by ") {
            let left = base_song[..by_pos].trim();
            let right = base_song[by_pos + 4..].trim();
            detected_song = Some(left.to_string());
            detected_artist = Some(right.to_string());
        } else {
            detected_song = Some(base_song.clone());
            if !uploader.trim().is_empty() {
                detected_artist = Some(uploader.trim().to_string());
            }
        }
    }

    let clean_title = match (&detected_artist, &detected_song) {
        (Some(a), Some(s)) if !a.is_empty() && !s.is_empty() => format!("{} - {}", a, s),
        (None, Some(s)) if !s.is_empty() => s.clone(),
        _ => clean_base,
    };

    ParsedEntity {
        raw_title: title.to_string(),
        clean_title,
        song_title: detected_song,
        artist: detected_artist,
        context_source: context_part,
        is_cluttered,
        is_cutscene,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clean_parenthetical() {
        let (title, reading) = clean_parenthetical_readings("(I-BULL - iburu)");
        assert_eq!(title, "I-BULL");
        assert_eq!(reading.as_deref(), Some("iburu"));
    }

    #[test]
    fn test_parse_media_entity_slash() {
        let raw = "Zenless Zone Zero Season 3 Chapter 2 Opening / (I-BULL - iburu) jo0ji [Official MV]";
        let entity = parse_media_entity(raw, "jo0ji Official");
        assert!(entity.is_cluttered);
        assert_eq!(
            entity.context_source.as_deref(),
            Some("Zenless Zone Zero Season 3 Chapter 2 Opening")
        );
        assert_eq!(entity.clean_title, "jo0ji - I-BULL");
    }
}
