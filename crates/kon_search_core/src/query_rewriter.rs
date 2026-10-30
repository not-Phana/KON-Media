//! Intelligent Query Rewriting, Phonetic Encoding & Transliteration in native Rust.
//!
//! Provides sub-microsecond query expansion:
//! - American Soundex phonetic encoder
//! - Double Metaphone phonetic approximations
//! - Hepburn Romaji to Japanese title mapping
//! - Punctuation normalization & symbol expansion

use serde::{Deserialize, Serialize};
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryRewriteResult {
    pub original_query: String,
    pub normalized_query: String,
    pub soundex_code: String,
    pub metaphone_primary: String,
    pub metaphone_secondary: Option<String>,
    pub expanded_terms: Vec<String>,
    pub canonical_title_hint: Option<String>,
}

// -----------------------------------------------------------------------------
// Romaji / Phonetic Mappings for Famous Music & Anime
// -----------------------------------------------------------------------------

struct RomajiMapping {
    romaji: &'static str,
    kanji: &'static str,
    english: &'static str,
}

static ROMAJI_TABLE: &[RomajiMapping] = &[
    RomajiMapping { romaji: "gurenge", kanji: "紅蓮華", english: "Red Lotus" },
    RomajiMapping { romaji: "homura", kanji: "炎", english: "Flame" },
    RomajiMapping { romaji: "zankyosanka", kanji: "残響散歌", english: "Song of Reverberation" },
    RomajiMapping { romaji: "kizuna no kiseki", kanji: "絆ノ奇跡", english: "Miracle of Bonds" },
    RomajiMapping { romaji: "shinzo wo sasageyo", kanji: "心臓を捧げよ", english: "Dedicate Your Heart" },
    RomajiMapping { romaji: "guren no yumiya", kanji: "紅蓮の弓矢", english: "Crimson Bow and Arrow" },
    RomajiMapping { romaji: "jiyuu no tsubasa", kanji: "自由の翼", english: "Wings of Freedom" },
    RomajiMapping { romaji: "yoru ni kakeru", kanji: "夜に駆ける", english: "Racing into the Night" },
    RomajiMapping { romaji: "kaibutsu", kanji: "怪物", english: "Monster" },
    RomajiMapping { romaji: "gunjou", kanji: "群青", english: "Ultramarine" },
    RomajiMapping { romaji: "yuusha", kanji: "勇者", english: "The Brave" },
    RomajiMapping { romaji: "ao no sumika", kanji: "青のすみか", english: "Where Our Blue Is" },
    RomajiMapping { romaji: "kaikai kitan", kanji: "廻廻奇譚", english: "Round and Round Tale" },
    RomajiMapping { romaji: "ranbu no melody", kanji: "乱舞のメロディ", english: "Melody of the Wild Dance" },
    RomajiMapping { romaji: "haruka kanata", kanji: "遥か彼方", english: "Far Away" },
    RomajiMapping { romaji: "chikyugi", kanji: "地球儀", english: "Spinning Globe" },
    RomajiMapping { romaji: "uma to shika", kanji: "馬と鹿", english: "Horse and Deer" },
    RomajiMapping { romaji: "suzume", kanji: "すずめ", english: "Sparrow" },
    RomajiMapping { romaji: "sparkle", kanji: "スパークル", english: "Sparkle" },
    RomajiMapping { romaji: "nandemonaiya", kanji: "なんでもないや", english: "It's Nothing" },
    RomajiMapping { romaji: "zenzenzense", kanji: "前前前世", english: "Past Past Past Life" },
    RomajiMapping { romaji: "grand escape", kanji: "グランドエスケープ", english: "Grand Escape" },
    RomajiMapping { romaji: "unravel", kanji: "アンラベル", english: "Unravel" },
    RomajiMapping { romaji: "asphyxia", kanji: "アスフィクシア", english: "Asphyxia" },
];

/// Encodes a word into standard 4-character American Soundex code (e.g. "Robert" -> "R163").
pub fn soundex(word: &str) -> String {
    let clean: String = word
        .chars()
        .filter(|c| c.is_ascii_alphabetic())
        .collect::<String>()
        .to_uppercase();

    if clean.is_empty() {
        return "0000".to_string();
    }

    let chars: Vec<char> = clean.chars().collect();
    let mut code = String::with_capacity(4);
    code.push(chars[0]);

    let get_digit = |c: char| -> Option<char> {
        match c {
            'B' | 'F' | 'P' | 'V' => Some('1'),
            'C' | 'G' | 'J' | 'K' | 'Q' | 'S' | 'X' | 'Z' => Some('2'),
            'D' | 'T' => Some('3'),
            'L' => Some('4'),
            'M' | 'N' => Some('5'),
            'R' => Some('6'),
            _ => None, // A, E, I, O, U, H, W, Y
        }
    };

    let mut last_digit = get_digit(chars[0]);

    for &ch in &chars[1..] {
        if code.len() == 4 {
            break;
        }
        let current_digit = get_digit(ch);
        if let Some(digit) = current_digit {
            if Some(digit) != last_digit {
                code.push(digit);
                last_digit = Some(digit);
            }
        } else if ch != 'H' && ch != 'W' {
            last_digit = None;
        }
    }

    while code.len() < 4 {
        code.push('0');
    }

    code
}

/// Simplified Double Metaphone phonetic encoding.
pub fn metaphone(word: &str) -> (String, Option<String>) {
    let clean: String = word
        .chars()
        .filter(|c| c.is_ascii_alphabetic())
        .collect::<String>()
        .to_uppercase();

    if clean.is_empty() {
        return (String::new(), None);
    }

    let mut primary = String::with_capacity(clean.len());
    let chars: Vec<char> = clean.chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        let ch = chars[i];
        match ch {
            'A' | 'E' | 'I' | 'O' | 'U' => {
                if i == 0 {
                    primary.push(ch);
                }
            }
            'B' => {
                primary.push('P');
                if i + 1 < len && chars[i + 1] == 'B' {
                    i += 1;
                }
            }
            'C' => {
                if i + 1 < len && chars[i + 1] == 'H' {
                    primary.push('X');
                    i += 1;
                } else if i + 1 < len && (chars[i + 1] == 'I' || chars[i + 1] == 'E' || chars[i + 1] == 'Y') {
                    primary.push('S');
                } else {
                    primary.push('K');
                }
            }
            'D' => {
                if i + 1 < len && chars[i + 1] == 'G' {
                    primary.push('J');
                    i += 1;
                } else {
                    primary.push('T');
                }
            }
            'F' | 'J' | 'L' | 'M' | 'N' | 'R' => {
                primary.push(ch);
            }
            'G' => {
                if i + 1 < len && chars[i + 1] == 'H' {
                    i += 1;
                } else if i + 1 < len && (chars[i + 1] == 'I' || chars[i + 1] == 'E' || chars[i + 1] == 'Y') {
                    primary.push('J');
                } else {
                    primary.push('K');
                }
            }
            'K' => {
                primary.push('K');
            }
            'P' => {
                if i + 1 < len && chars[i + 1] == 'H' {
                    primary.push('F');
                    i += 1;
                } else {
                    primary.push('P');
                }
            }
            'Q' => {
                primary.push('K');
            }
            'S' => {
                if i + 1 < len && chars[i + 1] == 'H' {
                    primary.push('X');
                    i += 1;
                } else {
                    primary.push('S');
                }
            }
            'T' => {
                if i + 1 < len && chars[i + 1] == 'H' {
                    primary.push('0'); // Theta sound
                    i += 1;
                } else {
                    primary.push('T');
                }
            }
            'V' => {
                primary.push('F');
            }
            'W' | 'Y' => {
                if i + 1 < len && ['A', 'E', 'I', 'O', 'U'].contains(&chars[i + 1]) {
                    primary.push(ch);
                }
            }
            'X' => {
                primary.push_str("KS");
            }
            'Z' => {
                primary.push('S');
            }
            _ => {}
        }
        i += 1;
    }

    (primary, None)
}

/// Rewrite query with phonetic expansion, transliteration, and canonical hints.
pub fn rewrite_query(query: &str) -> QueryRewriteResult {
    let norm = normalize_text(query);
    let mut expanded_terms = Vec::new();
    let mut canonical_hint: Option<String> = None;

    // Check Romaji mappings
    for item in ROMAJI_TABLE {
        if norm.contains(item.romaji) {
            expanded_terms.push(item.kanji.to_string());
            expanded_terms.push(item.english.to_string());
            if canonical_hint.is_none() {
                canonical_hint = Some(format!("{} ({})", item.kanji, item.romaji));
            }
        }
    }

    let snd = soundex(&norm);
    let (meta_p, meta_s) = metaphone(&norm);

    QueryRewriteResult {
        original_query: query.to_string(),
        normalized_query: norm,
        soundex_code: snd,
        metaphone_primary: meta_p,
        metaphone_secondary: meta_s,
        expanded_terms,
        canonical_title_hint: canonical_hint,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_soundex_encoding() {
        assert_eq!(soundex("Robert"), "R163");
        assert_eq!(soundex("Rupert"), "R163");
        assert_eq!(soundex("Bankai"), "B520");
    }

    #[test]
    fn test_metaphone_encoding() {
        let (p, _) = metaphone("Bleach");
        assert_eq!(p, "PLX");
    }

    #[test]
    fn test_query_rewrite_gurenge() {
        let res = rewrite_query("gurenge");
        assert!(res.expanded_terms.contains(&"紅蓮華".to_string()));
    }
}
