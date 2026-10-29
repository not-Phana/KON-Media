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
    pub uploader: Option<String>,
    pub duration: Option<f64>,
    pub views: Option<u64>,
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

    // Modifiers (version compatibility, non-music suppression, and severe duration mismatch)
    let duration_multiplier = if feat.duration_compat < 0.50 {
        feat.duration_compat
    } else {
        1.0
    };
    let final_score = (base_score * feat.version_compat * feat.non_music_penalty * duration_multiplier).max(0.0);

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
        uploader: cand.uploader.clone(),
        duration: cand.duration,
        views: cand.views,
        platform: cand.platform.clone(),
        url: cand.url.clone(),
        score: (final_score * 10000.0).round() / 10000.0,
        confidence,
        features: feat,
        explanations,
    }
}
