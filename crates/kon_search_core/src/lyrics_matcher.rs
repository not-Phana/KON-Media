//! Synchronized Lyrics (LRC) & Subtitle (SRT) Parser and Search Engine in native Rust.
//!
//! Provides ultra-fast parsing and search over timed lyrics:
//! - Standard LRC format parsing `[mm:ss.xx] lyric text`
//! - Millisecond-accurate timestamp lookup (binary search)
//! - Lyrics snippet search (find songs by partial remembered lyric words)
//! - Line synchronization and active lyric tracking

use serde::{Deserialize, Serialize};
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LyricLine {
    pub timestamp_ms: u64,
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedLrc {
    pub title: Option<String>,
    pub artist: Option<String>,
    pub album: Option<String>,
    pub lines: Vec<LyricLine>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LyricSearchResult {
    pub line_index: usize,
    pub timestamp_ms: u64,
    pub text: String,
    pub match_score: f64,
}

/// Parse standard LRC string into structured lyrics with millisecond timestamps.
pub fn parse_lrc(lrc_content: &str) -> ParsedLrc {
    let mut title: Option<String> = None;
    let mut artist: Option<String> = None;
    let mut album: Option<String> = None;
    let mut lines = Vec::new();

    for raw_line in lrc_content.lines() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        // Metadata tag: [ti:Song Title] or [ar:Artist Name] or [al:Album Name]
        if line.starts_with("[ti:") && line.ends_with(']') {
            title = Some(line[4..line.len() - 1].trim().to_string());
            continue;
        }
        if line.starts_with("[ar:") && line.ends_with(']') {
            artist = Some(line[4..line.len() - 1].trim().to_string());
            continue;
        }
        if line.starts_with("[al:") && line.ends_with(']') {
            album = Some(line[4..line.len() - 1].trim().to_string());
            continue;
        }

        // Timestamp tag: [mm:ss.xx] text
        if line.starts_with('[') {
            if let Some(close_idx) = line.find(']') {
                let tag = &line[1..close_idx];
                let text = line[close_idx + 1..].trim().to_string();

                if let Some(ms) = parse_lrc_timestamp(tag) {
                    lines.push(LyricLine {
                        timestamp_ms: ms,
                        text,
                    });
                }
            }
        }
    }

    // Sort lines by timestamp
    lines.sort_by_key(|l| l.timestamp_ms);

    ParsedLrc {
        title,
        artist,
        album,
        lines,
    }
}

/// Parse `mm:ss.xx` or `mm:ss:xx` or `mm:ss` timestamp into milliseconds.
pub fn parse_lrc_timestamp(tag: &str) -> Option<u64> {
    let parts: Vec<&str> = tag.split(':').collect();
    if parts.len() < 2 {
        return None;
    }

    let minutes: u64 = parts[0].parse().ok()?;
    let sec_parts: Vec<&str> = parts[1].split('.').collect();
    let seconds: u64 = sec_parts[0].parse().ok()?;

    let ms: u64 = if sec_parts.len() > 1 {
        let frac_str = sec_parts[1];
        let frac_val: u64 = frac_str.parse().ok()?;
        if frac_str.len() == 2 {
            frac_val * 10 // hundredths to ms
        } else if frac_str.len() == 3 {
            frac_val
        } else {
            frac_val * 100
        }
    } else {
        0
    };

    Some(minutes * 60_000 + seconds * 1_000 + ms)
}

/// Find active lyric line index for given playback position in milliseconds.
pub fn find_active_lyric_index(lines: &[LyricLine], current_ms: u64) -> Option<usize> {
    if lines.is_empty() {
        return None;
    }

    let idx = match lines.binary_search_by_key(&current_ms, |l| l.timestamp_ms) {
        Ok(exact) => exact,
        Err(pos) => {
            if pos == 0 {
                0
            } else {
                pos - 1
            }
        }
    };

    Some(idx)
}

/// Search for lyric snippet across a song's synchronized lines.
pub fn search_lyrics_snippet(lrc: &ParsedLrc, query: &str) -> Vec<LyricSearchResult> {
    let norm_q = normalize_text(query);
    if norm_q.is_empty() {
        return Vec::new();
    }

    let mut results = Vec::new();

    for (i, line) in lrc.lines.iter().enumerate() {
        let norm_l = normalize_text(&line.text);
        if norm_l.contains(&norm_q) {
            let score = if norm_l == norm_q {
                1.0
            } else {
                norm_q.len() as f64 / norm_l.len() as f64
            };

            results.push(LyricSearchResult {
                line_index: i,
                timestamp_ms: line.timestamp_ms,
                text: line.text.clone(),
                match_score: score,
            });
        }
    }

    results.sort_by(|a, b| b.match_score.partial_cmp(&a.match_score).unwrap_or(std::cmp::Ordering::Equal));
    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_lrc_content() {
        let raw = r#"
[ti:Number One]
[ar:Shiro Sagisu]
[00:15.50]If you wanna see some action
[00:20.10]Gotta be the center of attraction
[00:25.00]Make sure that they got their eyes on you
"#;
        let lrc = parse_lrc(raw);
        assert_eq!(lrc.title.as_deref(), Some("Number One"));
        assert_eq!(lrc.artist.as_deref(), Some("Shiro Sagisu"));
        assert_eq!(lrc.lines.len(), 3);
        assert_eq!(lrc.lines[0].timestamp_ms, 15500);

        let active = find_active_lyric_index(&lrc.lines, 18000);
        assert_eq!(active, Some(0));

        let hits = search_lyrics_snippet(&lrc, "center of attraction");
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].line_index, 1);
    }
}
