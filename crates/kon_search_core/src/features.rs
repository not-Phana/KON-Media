use crate::normalization::{
    levenshtein_similarity, ngram_similarity, normalize_text, strip_media_noise, tokenize,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CandidateInput {
    pub id: String,
    pub title: String,
    pub uploader: Option<String>,
    pub duration: Option<f64>,
    pub views: Option<u64>,
    #[serde(default)]
    pub likes: Option<u64>,
    #[serde(default)]
    pub listeners: Option<u64>,
    #[serde(default)]
    pub chart_rank: Option<u32>,
    #[serde(default)]
    pub release_year: Option<u32>,
    #[serde(default)]
    pub is_trending: Option<bool>,
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

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
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
    #[serde(default)]
    pub popularity_score: f64,
    #[serde(default)]
    pub has_popularity_data: bool,
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
    ("reacts", 0.25),
    ("react to", 0.25),
    ("react", 0.25),
    ("scene", 0.30),
    ("movie clip", 0.25),
    ("ending scene", 0.25),
    ("workout", 0.25),
    ("fitness", 0.25),
    ("routine", 0.25),
    ("exercise", 0.25),
];

/// Normalize all available verifiable popularity signals into a unified [0.0, 1.0] score.
/// Returns (normalized_popularity, has_popularity_data).
/// If no popularity data is available, returns (0.50, false) as a neutral prior without unfair penalty.
pub fn normalize_popularity(candidate: &CandidateInput) -> (f64, bool) {
    let mut signals: Vec<(f64, f64)> = Vec::with_capacity(4);

    // 1. Total streams / view count (log-scale normalized from 1k to 3B)
    if let Some(v) = candidate.views {
        if v > 0 {
            let log_v = (v as f64).log10();
            let v_score = ((log_v - 3.0) / (9.5 - 3.0)).clamp(0.0, 1.0);
            signals.push((v_score, 1.0));
        }
    }

    // 2. Monthly listeners count (log-scale normalized from 1k to 100M)
    if let Some(l) = candidate.listeners {
        if l > 0 {
            let log_l = (l as f64).log10();
            let l_score = ((log_l - 3.0) / (8.0 - 3.0)).clamp(0.0, 1.0);
            signals.push((l_score, 1.0));
        }
    }

    // 3. Chart position (1..100, where 1 is top of chart)
    if let Some(rank) = candidate.chart_rank {
        if (1..=100).contains(&rank) {
            let c_score = 1.0 - ((rank - 1) as f64 / 100.0);
            signals.push((c_score, 1.2));
        }
    }

    // 4. Likes / favorites count (log-scale normalized)
    if let Some(k) = candidate.likes {
        if k > 0 {
            let log_k = (k as f64).log10();
            let k_score = ((log_k - 2.0) / (7.5 - 2.0)).clamp(0.0, 1.0);
            signals.push((k_score, 0.7));
        }
    }

    if signals.is_empty() {
        // Neutral prior when no data is provided: never assume unknown is unpopular
        return (0.50, false);
    }

    let total_weight: f64 = signals.iter().map(|(_, w)| w).sum();
    let weighted_sum: f64 = signals.iter().map(|(s, w)| s * w).sum();
    let mut base_pop = weighted_sum / total_weight;

    // Fresh popularity & trend velocity:
    // Avoid allowing an old hit to automatically outrank every new trending song.
    if candidate.is_trending.unwrap_or(false) {
        base_pop = (base_pop + 0.18).min(1.0);
    }

    if let Some(year) = candidate.release_year {
        if year >= 2025 {
            base_pop = (base_pop * 1.12).min(1.0);
        } else if year >= 2023 {
            base_pop = (base_pop * 1.05).min(1.0);
        }
    }

    (base_pop.clamp(0.0, 1.0), true)
}

/// Check if query represents a broad discovery search (e.g. "popular songs", "trending music").
pub fn is_broad_discovery_query(text: &str) -> bool {
    let norm = normalize_text(text);
    let terms = [
        "popular songs",
        "popular music",
        "popular tracks",
        "trending songs",
        "trending music",
        "top songs",
        "top music",
        "top hits",
        "best songs",
        "best music",
        "hit songs",
        "viral songs",
        "billboard hits",
        "chart hits",
        "most played",
        "most popular",
    ];
    for t in terms {
        if norm.contains(t) {
            return true;
        }
    }
    if norm == "popular" || norm == "trending" || norm == "hits" || norm == "top hits" {
        return true;
    }
    false
}

/// Detect version keyword in title or query.
pub fn detect_version_hint(text: &str) -> Option<String> {
    let norm = normalize_text(text);
    if norm.contains("original mix") {
        return None;
    }
    let keywords = [
        ("remix", &["remix", "mix", "club mix", "extended mix", "dub", "flip", "jersey club", "jersey remix", "jersey", "edit"][..]),
        ("live", &["live", "live aid", "in concert", "wembley", "coachella", "acoustic live", "live performance"][..]),
        ("instrumental", &["instrumental", "karaoke", "backing track", "piano cover", "instrumental version"][..]),
        ("acoustic", &["acoustic", "unplugged", "acoustic version"][..]),
        ("cover", &["cover", "parody", "tribute"][..]),
        ("slowed", &["slowed", "slowed down", "slowed reverb", "reverb"][..]),
        ("sped_up", &["sped up", "speed up", "nightcore", "fast version"][..]),
        ("version", &["version", "ver", "edition"][..]),
    ];

    for (cat, terms) in keywords {
        for term in terms {
            if norm.contains(term) {
                return Some(cat.to_string());
            }
        }
    }
    None
}

/// Extract relevance feature vector comparing query against candidate.
pub fn extract_candidate_features(query: &QueryInput, candidate: &CandidateInput) -> ExtractedFeatures {
    let norm_q = query
        .normalized_query
        .clone()
        .unwrap_or_else(|| normalize_text(&query.raw_query));
    let q_tokens = tokenize(&norm_q);

    let clean_title = candidate
        .clean_title
        .as_deref()
        .unwrap_or(&candidate.title);
    let norm_title = normalize_text(clean_title);
    let title_tokens = tokenize(&norm_title);

    let stripped_title = strip_media_noise(&candidate.title);
    let norm_stripped_title = normalize_text(&stripped_title);

    let parsed_entity = if candidate.song_title.is_none() || candidate.clean_title.is_none() {
        Some(crate::entity_parser::parse_media_entity(
            &candidate.title,
            candidate.uploader.as_deref().unwrap_or(""),
        ))
    } else {
        None
    };

    let song_title_ref = candidate
        .song_title
        .as_deref()
        .or_else(|| parsed_entity.as_ref().and_then(|p| p.song_title.as_deref()));
    let song_title_norm = song_title_ref.map(normalize_text);

    // 1. Exact title match (1.0 for perfect, 0.98 for parsed song title, 0.95 for stripped match)
    let exact_title = if norm_title == norm_q {
        1.0
    } else if let Some(ref st_norm) = song_title_norm {
        if st_norm == &norm_q {
            0.98
        } else if norm_stripped_title == norm_q {
            0.95
        } else {
            0.0
        }
    } else if norm_stripped_title == norm_q {
        0.95
    } else {
        0.0
    };

    // 2. Phrase match
    let phrase_match = if norm_title.contains(&norm_q) && !norm_q.is_empty() {
        1.0
    } else if norm_stripped_title.contains(&norm_q) && !norm_q.is_empty() {
        0.9
    } else {
        0.0
    };

    // 3. Token coverage: fraction of query tokens present in title or uploader/artist
    let uploader_norm = candidate
        .uploader
        .as_deref()
        .map(normalize_text)
        .unwrap_or_default();
    let artist_norm = candidate
        .artist
        .as_deref()
        .map(normalize_text)
        .unwrap_or_default();

    let mut covered_f: f64 = 0.0;
    for t in &q_tokens {
        if title_tokens.contains(t)
            || uploader_norm.contains(t.as_str())
            || artist_norm.contains(t.as_str())
        {
            covered_f += 1.0;
        } else if title_tokens.iter().any(|tt| crate::normalization::levenshtein_similarity(t, tt) >= 0.70) {
            covered_f += 0.85;
        }
    }
    let token_coverage = if q_tokens.is_empty() {
        0.0
    } else {
        (covered_f / q_tokens.len() as f64).min(1.0)
    };

    // 4. Token order agreement
    let mut token_order = 0.0;
    if q_tokens.len() >= 2 && token_coverage >= 0.8 {
        let mut last_idx: Option<usize> = None;
        let mut in_order = true;
        for t in &q_tokens {
            if let Some(pos) = title_tokens.iter().position(|x| x == t) {
                if let Some(prev) = last_idx {
                    if pos < prev {
                        in_order = false;
                        break;
                    }
                }
                last_idx = Some(pos);
            }
        }
        if in_order {
            token_order = 1.0;
        }
    }

    // 5. Typo / subword similarity
    let typo_similarity = {
        let lev = levenshtein_similarity(&norm_q, &norm_title);
        let ng = ngram_similarity(&norm_q, &norm_title, 3);
        (lev * 0.4 + ng * 0.6).min(1.0)
    };

    // 6. Artist / uploader agreement
    let artist_affinity = if let Some(exp_artist) = &query.expected_artist {
        let norm_exp_a = normalize_text(exp_artist);
        if !norm_exp_a.is_empty() {
            if artist_norm.contains(&norm_exp_a) || uploader_norm.contains(&norm_exp_a) {
                1.0
            } else if norm_title.contains(&norm_exp_a) {
                0.7
            } else {
                0.0
            }
        } else {
            0.0
        }
    } else {
        // If query tokens match candidate artist/uploader strongly
        let mut a_matches = 0;
        for t in &q_tokens {
            if artist_norm.contains(t.as_str()) || uploader_norm.contains(t.as_str()) {
                a_matches += 1;
            }
        }
        if !q_tokens.is_empty() && a_matches > 0 {
            (a_matches as f64 / q_tokens.len() as f64) * 0.8
        } else {
            0.0
        }
    };

    // 7. Version compatibility
    let query_v_hint = query
        .version_hint
        .clone()
        .or_else(|| detect_version_hint(&norm_q));
    let cand_v_hint = detect_version_hint(&candidate.title);

    let version_compat = match (&query_v_hint, &cand_v_hint) {
        (Some(qv), Some(cv)) if qv == cv => 1.0,
        (Some(_), None) => 0.2, // User wanted a specific version, candidate doesn't state it
        (None, Some(_)) => {
            // Disqualify unwanted live/parody/etc. if user didn't ask for it
            let mut penalty: f64 = 0.5;
            for (term, mult) in DISQUALIFYING_VERSION_TERMS {
                if norm_title.contains(term) {
                    penalty = penalty.min(*mult);
                }
            }
            penalty
        }
        _ => 1.0,
    };

    // 8. Duration compatibility
    let duration_compat = if let Some(cand_d) = candidate.duration {
        if let Some(exp_d) = query.expected_duration {
            let diff = (cand_d - exp_d).abs();
            if diff <= 15.0 {
                1.0
            } else if diff <= 45.0 {
                0.8
            } else if diff <= 90.0 {
                0.5
            } else {
                0.2
            }
        } else {
            // Natural song duration bonus (2 to 7 minutes)
            if (120.0..=420.0).contains(&cand_d) {
                0.9
            } else if cand_d > 900.0 {
                // Long video/mix penalty
                0.2
            } else {
                0.6
            }
        }
    } else {
        0.5
    };

    // 9. Non-music penalty
    let mut non_music_penalty: f64 = 1.0;
    if candidate.is_cutscene.unwrap_or(false) {
        non_music_penalty = 0.2;
    }
    for (term, mult) in NON_MUSIC_TERMS {
        if norm_title.contains(term) && !norm_q.contains(term) {
            non_music_penalty = non_music_penalty.min(*mult);
        }
    }

    // 10. Popularity / view count normalization & bounded tie-breaker
    let (popularity_score, has_popularity_data) = normalize_popularity(candidate);
    let popularity_boost = if has_popularity_data {
        (popularity_score * 0.05).min(0.05)
    } else {
        0.025
    };

    // 11. Audio platform boost
    let audio_platform_boost = if candidate.platform.as_deref() == Some("soundcloud") {
        0.10
    } else {
        0.0
    };

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
        popularity_score,
        has_popularity_data,
    }
}

pub use extract_candidate_features as extract_features;
