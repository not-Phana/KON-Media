use crate::normalization::{
    levenshtein_similarity, ngram_similarity, normalize_text, strip_media_noise, tokenize,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CandidateInput {
    pub id: String,
    pub title: String,
    pub uploader: Option<String>,
    pub duration: Option<f64>,
    pub views: Option<u64>,
    pub platform: Option<String>,
    pub url: Option<String>,
    #[serde(default)]
    pub clean_title: Option<String>,
    #[serde(default)]
    pub song_title: Option<String>,
    #[serde(default)]
    pub artist: Option<String>,
    #[serde(default)]
    pub context_source: Option<String>,
    #[serde(default)]
    pub is_cluttered: Option<bool>,
    #[serde(default)]
    pub is_cutscene: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryInput {
    pub raw_query: String,
    pub normalized_query: Option<String>,
    pub expected_artist: Option<String>,
    pub expected_title: Option<String>,
    pub expected_duration: Option<f64>,
    pub version_hint: Option<String>,
    pub media_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedFeatures {
    pub exact_title: f64,
    pub phrase_match: f64,
    pub token_coverage: f64,
    pub token_order: f64,
    pub typo_similarity: f64,
    pub artist_affinity: f64,
    pub version_compat: f64,
    pub duration_compat: f64,
    pub non_music_penalty: f64,
    pub popularity_boost: f64,
    pub audio_platform_boost: f64,
}

const DISQUALIFYING_VERSION_TERMS: &[(&str, f64)] = &[
    ("parody", 0.35),
    ("minecraft", 0.45),
    ("roblox", 0.45),
    ("earrape", 0.40),
    ("nightcore", 0.35),
    ("bass boosted", 0.25),
    ("8d audio", 0.30),
];

const NON_MUSIC_TERMS: &[(&str, f64)] = &[
    ("documentary", 0.25),
    ("trailer", 0.25),
    ("teaser", 0.25),
    ("tutorial", 0.25),
    ("gameplay", 0.25),
    ("walkthrough", 0.25),
    ("review", 0.30),
    ("interview", 0.30),
    ("podcast", 0.30),
    ("reaction", 0.25),
    ("scene", 0.30),
    ("movie clip", 0.25),
    ("ending scene", 0.25),
    ("workout", 0.25),
    ("fitness", 0.25),
    ("routine", 0.25),
    ("exercise", 0.25),
];

/// Detect version keyword in title or query.
pub fn detect_version_hint(text: &str) -> Option<String> {
    let norm = normalize_text(text);
    if norm.contains("original mix") {
        return None;
    }
    let keywords = [
        ("remix", &["remix", "mix", "club mix", "extended mix"][..]),
        ("live", &["live", "live aid", "in concert", "wembley"][..]),
        ("instrumental", &["instrumental", "karaoke", "backing track"][..]),
        ("acoustic", &["acoustic", "unplugged"][..]),
        ("cover", &["cover", "parody", "tribute"][..]),
    ];

    for (cat, terms) in keywords {
        for term in terms {
            let pattern = format!(" {} ", term);
            let padded = format!(" {} ", norm);
            if padded.contains(&pattern) {
                return Some(cat.to_string());
            }
        }
    }
    None
}

pub fn extract_candidate_features(
    query: &QueryInput,
    cand: &CandidateInput,
) -> ExtractedFeatures {
    let raw_q = &query.raw_query;
    let norm_q = query
        .normalized_query
        .clone()
        .unwrap_or_else(|| normalize_text(raw_q));

    let clean_title = strip_media_noise(&cand.title);
    let norm_title = normalize_text(&clean_title);
    let uploader_norm = cand
        .uploader
        .as_ref()
        .map(|u| normalize_text(u))
        .unwrap_or_default();

    let media_type = query
        .media_type
        .as_deref()
        .unwrap_or("all")
        .to_lowercase();

    // 1. Exact title match
    let exact_title = if norm_q == norm_title {
        1.0
    } else if norm_title.starts_with(&norm_q) {
        0.95
    } else if norm_title.contains(&norm_q) {
        0.85
    } else {
        0.0
    };

    // 2. Phrase match
    let phrase_match = if !norm_q.is_empty() && norm_title.contains(&norm_q) {
        1.0
    } else {
        0.0
    };

    // 3. Token coverage & Token order
    let q_tokens = tokenize(&norm_q);
    let c_tokens = tokenize(&norm_title);
    let token_coverage: f64;
    let mut token_order: f64 = 1.0;

    if q_tokens.is_empty() {
        token_coverage = 0.0;
    } else {
        let mut matched = 0;
        let mut last_idx: Option<usize> = None;
        let mut order_inversions = 0;

        for qt in &q_tokens {
            if let Some(pos) = c_tokens.iter().position(|ct| ct == qt) {
                matched += 1;
                if let Some(prev) = last_idx {
                    if pos < prev {
                        order_inversions += 1;
                    }
                }
                last_idx = Some(pos);
            }
        }

        token_coverage = (matched as f64) / (q_tokens.len() as f64);
        if order_inversions > 0 {
            token_order = (1.0 - (order_inversions as f64 * 0.2)).max(0.2);
        }
    }

    // 4. Typo similarity (character level)
    let ngram_sim = ngram_similarity(&norm_q, &norm_title, 3);
    let lev_sim = levenshtein_similarity(&norm_q, &norm_title);
    let typo_similarity = ngram_sim.max(lev_sim);

    // 5. Artist affinity
    let mut artist_affinity = 0.5; // neutral
    if let Some(ref target_artist) = query.expected_artist {
        let norm_artist = normalize_text(target_artist);
        if !norm_artist.is_empty() {
            if uploader_norm.contains(&norm_artist) || norm_artist.contains(&uploader_norm) {
                artist_affinity = 1.0;
            } else if norm_title.starts_with(&norm_artist) {
                artist_affinity = 0.9;
            } else if ngram_similarity(&norm_artist, &uploader_norm, 3) > 0.6 {
                artist_affinity = 0.85;
            } else {
                artist_affinity = 0.3;
            }
        }
    }

    // 6. Version compatibility
    let cand_version = detect_version_hint(&cand.title);
    let query_version = query
        .version_hint
        .clone()
        .or_else(|| detect_version_hint(raw_q));

    let mut version_compat = 1.0;
    for &(disq, mult) in DISQUALIFYING_VERSION_TERMS {
        if norm_title.contains(disq) {
            let permitted = query_version.as_ref().map(|v| v.contains(disq)).unwrap_or(false);
            if !permitted {
                version_compat = mult;
                break;
            }
        }
    }

    if version_compat == 1.0 {
        if let Some(ref req_v) = query_version {
            if cand_version.as_ref() == Some(req_v) || norm_title.contains(req_v) {
                version_compat = 1.25;
            } else {
                version_compat = 0.50;
            }
        } else if let Some(ref cv) = cand_version {
            if cv == "remix" || cv == "live" || cv == "instrumental" || cv == "cover" {
                version_compat = 0.65;
            }
        }
    }

    // 7. Non-music content penalty (check against raw unstripped title)
    let raw_cand_norm = normalize_text(&cand.title);
    let is_audio_mode = media_type == "audio"
        || ["song", "music", "audio", "ost", "soundtrack", "track", "theme"]
            .iter()
            .any(|term| norm_q.contains(term));

    let mut non_music_penalty = 1.0;
    if is_audio_mode {
        for &(nm_term, pen) in NON_MUSIC_TERMS {
            if raw_cand_norm.contains(nm_term) && !norm_q.contains(nm_term) {
                non_music_penalty = pen;
                break;
            }
        }
    }

    // 8. Duration compatibility
    let mut duration_compat = 0.7; // baseline
    if let (Some(expected_d), Some(actual_d)) = (query.expected_duration, cand.duration) {
        if expected_d > 0.0 && actual_d > 0.0 {
            let diff = (actual_d - expected_d).abs();
            let ratio = diff / expected_d;
            duration_compat = if ratio <= 0.05 {
                1.0
            } else if ratio <= 0.15 {
                0.85
            } else if ratio <= 0.35 {
                0.65
            } else if ratio <= 0.70 {
                0.35
            } else {
                0.10
            };
        }
    } else if is_audio_mode {
        if let Some(dur) = cand.duration {
            if dur > 600.0 && !["album", "mix", "full", "compilation"].iter().any(|k| norm_q.contains(k)) {
                duration_compat = 0.25;
            } else if dur < 25.0 {
                duration_compat = 0.20;
            } else {
                duration_compat = 0.85;
            }
        }
    }

    // 9. Bounded popularity tie-breaker (max +0.05 bonus)
    // log10(views + 1) / 10 normalized, capped at 0.05
    let popularity_boost = if let Some(v) = cand.views {
        if v > 100 {
            let log_v = ((v as f64) + 1.0).log10();
            ((log_v / 10.0) * 0.05).min(0.05)
        } else {
            0.0
        }
    } else {
        0.0
    };

    // 10. Audio platform / Topic boost
    let mut audio_platform_boost = 0.0;
    if is_audio_mode {
        if cand.platform.as_deref() == Some("soundcloud") {
            audio_platform_boost += 0.10;
        }
        if norm_title.contains("official audio") || norm_title.contains("audio") {
            audio_platform_boost += 0.10;
        }
        if uploader_norm.contains("topic") {
            audio_platform_boost += 0.08;
        }
    }

    ExtractedFeatures {
        exact_title,
        phrase_match,
        token_coverage,
        token_order,
        typo_similarity,
        artist_affinity,
        version_compat,
        duration_compat,
        non_music_penalty,
        popularity_boost,
        audio_platform_boost,
    }
}
