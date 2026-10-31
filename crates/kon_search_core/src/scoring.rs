use crate::features::{extract_candidate_features, CandidateInput, ExtractedFeatures, QueryInput};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoredCandidate {
    pub id: String,
    pub title: String,
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
    #[serde(default)]
    pub is_music: Option<bool>,
    #[serde(default)]
    pub content_type: Option<String>,
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
    #[serde(default)]
    pub popularity: Option<f64>,
    pub platform: Option<String>,
    pub url: Option<String>,
    pub score: f64,
    pub confidence: String,
    pub features: ExtractedFeatures,
    pub explanations: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScorerWeights {
    pub weight_exact_title: f64,
    pub weight_phrase_match: f64,
    pub weight_token_coverage: f64,
    pub weight_token_order: f64,
    pub weight_typo_similarity: f64,
    pub weight_artist_affinity: f64,
    pub weight_duration_compat: f64,
}

impl Default for ScorerWeights {
    fn default() -> Self {
        Self {
            weight_exact_title: 0.30,
            weight_phrase_match: 0.25,
            weight_token_coverage: 0.25,
            weight_token_order: 0.10,
            weight_typo_similarity: 0.15,
            weight_artist_affinity: 0.15,
            weight_duration_compat: 0.10,
        }
    }
}

pub fn score_candidate(
    query: &QueryInput,
    cand: &CandidateInput,
    weights: &ScorerWeights,
) -> ScoredCandidate {
    let feat = extract_candidate_features(query, cand);
    let mut explanations = Vec::new();

    if feat.exact_title >= 0.85 {
        explanations.push("Exact or leading title match".to_string());
    } else if feat.phrase_match >= 0.90 {
        explanations.push("Continuous query phrase match".to_string());
    }

    if feat.token_coverage >= 0.99 {
        explanations.push("Full query token coverage".to_string());
    }

    if feat.artist_affinity >= 0.85 {
        explanations.push("Verified artist / channel affinity".to_string());
    }

    if feat.version_compat < 0.60 {
        explanations.push("Version mismatch or unrequested remix/parody penalty".to_string());
    } else if feat.version_compat > 1.10 {
        explanations.push("Requested version match boost".to_string());
    }

    if feat.non_music_penalty < 0.80 {
        explanations.push("Non-music content mismatch penalty".to_string());
    }

    // Weighted linear base score
    let base_score = weights.weight_exact_title * feat.exact_title
        + weights.weight_phrase_match * feat.phrase_match
        + weights.weight_token_coverage * feat.token_coverage
        + weights.weight_token_order * feat.token_order
        + weights.weight_typo_similarity * feat.typo_similarity
        + weights.weight_artist_affinity * feat.artist_affinity
        + weights.weight_duration_compat * feat.duration_compat
        + feat.audio_platform_boost
        + feat.popularity_boost; // strictly bounded tie-breaker (max 0.05)

    // Classify candidate media identity
    let classification = crate::media_classifier::classify_candidate(
        &cand.title,
        cand.uploader.as_deref().unwrap_or(""),
        cand.duration.unwrap_or(0.0),
    );
    let is_music = classification.is_music;
    let content_type = match classification.category {
        crate::media_classifier::MediaCategory::SoundtrackOrOST => "soundtrack",
        _ if !is_music => "video",
        _ => "song",
    };

    // Modifiers (version compatibility, non-music suppression, audio mode demotion, and duration mismatch)
    let duration_multiplier = if feat.duration_compat < 0.50 {
        feat.duration_compat
    } else {
        1.0
    };
    let mut audio_mode_multiplier = 1.0;
    if query.media_type.as_deref() == Some("audio") && !is_music {
        audio_mode_multiplier = 0.15;
        explanations.push("Demoted non-music video in audio mode".to_string());
    }

    let is_text_match = feat.token_coverage > 0.0 || feat.phrase_match > 0.0 || feat.exact_title > 0.0 || feat.typo_similarity >= 0.50;
    let raw_relevance = if !is_text_match {
        0.0
    } else {
        (base_score * feat.version_compat * feat.non_music_penalty * duration_multiplier * audio_mode_multiplier).max(0.0)
    };

    // Popularity-Aware Combined Ranking
    let norm_q = query.normalized_query.as_deref().unwrap_or(&query.raw_query);
    let is_broad = crate::features::is_broad_discovery_query(norm_q);

    let final_score = if is_broad {
        explanations.push("Broad discovery search: prioritized by streaming popularity".to_string());
        (0.25 * raw_relevance + 0.75 * feat.popularity_score).max(0.0)
    } else if raw_relevance < 0.15 {
        // Prevent unrelated songs from ranking highly just because they share a word or have views
        raw_relevance * 0.50
    } else {
        let pop_mult = if feat.has_popularity_data {
            if feat.popularity_score >= 0.75 {
                explanations.push("High streaming popularity boost".to_string());
            } else if feat.popularity_score <= 0.25 {
                explanations.push("Low playcount demoted relative to major releases".to_string());
            }
            1.0 + 0.50 * (feat.popularity_score - 0.50)
        } else {
            explanations.push("Neutral baseline (unpenalized missing popularity data)".to_string());
            1.0
        };
        (raw_relevance * pop_mult).max(0.0)
    };

    let confidence = if final_score >= 0.65 {
        "high".to_string()
    } else if final_score >= 0.35 {
        "medium".to_string()
    } else {
        "low".to_string()
    };

    ScoredCandidate {
        id: cand.id.clone(),
        title: cand.title.clone(),
        clean_title: cand.clean_title.clone(),
        song_title: cand.song_title.clone(),
        artist: cand.artist.clone(),
        context_source: cand.context_source.clone(),
        is_cluttered: cand.is_cluttered,
        is_cutscene: cand.is_cutscene,
        is_music: Some(is_music),
        content_type: Some(content_type.to_string()),
        uploader: cand.uploader.clone(),
        duration: cand.duration,
        views: cand.views,
        likes: cand.likes,
        listeners: cand.listeners,
        chart_rank: cand.chart_rank,
        release_year: cand.release_year,
        is_trending: cand.is_trending,
        popularity: Some(feat.popularity_score),
        platform: cand.platform.clone(),
        url: cand.url.clone(),
        score: (final_score * 10000.0).round() / 10000.0,
        confidence,
        features: feat,
        explanations,
    }
}
