use crate::dedup::deduplicate_candidates;
use crate::features::{CandidateInput, QueryInput};
use crate::scoring::{score_candidate, ScoredCandidate, ScorerWeights};

/// Rank a list of candidate results against the query.
pub fn rank_candidates(
    query: &QueryInput,
    candidates: Vec<CandidateInput>,
    weights: Option<ScorerWeights>,
) -> Vec<ScoredCandidate> {
    let active_weights = weights.unwrap_or_default();
    let deduped = deduplicate_candidates(candidates);

    let mut scored: Vec<ScoredCandidate> = deduped
        .into_iter()
        .map(|c| score_candidate(query, &c, &active_weights))
        .collect();

    // Deterministic tie-breaking sort:
    // 1. Score desc
    // 2. Exact title feature desc
    // 3. Views desc
    // 4. ID asc (stable deterministic tie-breaker)
    scored.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| {
                b.features
                    .exact_title
                    .partial_cmp(&a.features.exact_title)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| {
                b.features
                    .popularity_score
                    .partial_cmp(&a.features.popularity_score)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| {
                let v_a = a.views.unwrap_or(0);
                let v_b = b.views.unwrap_or(0);
                v_b.cmp(&v_a)
            })
            .then_with(|| a.id.cmp(&b.id))
    });

    scored
}


/// Fast lightweight ranking pipeline for KON Search 1.2 Rei Flash.
/// Prioritizes raw sub-millisecond execution while maintaining strict media classification and token fidelity.
pub fn rank_candidates_flash(
    query: &QueryInput,
    candidates: Vec<CandidateInput>,
    limit: Option<usize>,
) -> Vec<ScoredCandidate> {
    let deduped = deduplicate_candidates(candidates);
    let norm_q = query
        .normalized_query
        .clone()
        .unwrap_or_else(|| crate::normalization::normalize_text(&query.raw_query));
    let q_tokens = crate::normalization::tokenize(&norm_q);
    let is_audio_mode = query.media_type.as_deref() == Some("audio");
    let is_broad = crate::features::is_broad_discovery_query(&norm_q);

    let mut scored: Vec<ScoredCandidate> = deduped
        .into_iter()
        .map(|c| {
            let clean_title = c.clean_title.as_deref().unwrap_or(&c.title);
            let norm_title = crate::normalization::normalize_text(clean_title);
            let title_tokens = crate::normalization::tokenize(&norm_title);

            // 1. Fast exact or leading phrase match
            let is_exact = norm_title == norm_q;
            let starts_with = norm_title.starts_with(&norm_q);
            let contains_phrase = norm_title.contains(&norm_q);
            let all_tokens_in_order = if q_tokens.len() >= 2 {
                let mut last_pos: Option<usize> = None;
                let mut in_order = true;
                for qt in &q_tokens {
                    if let Some(pos) = title_tokens.iter().position(|x| x == qt) {
                        if let Some(prev) = last_pos {
                            if pos < prev {
                                in_order = false;
                                break;
                            }
                        }
                        last_pos = Some(pos);
                    } else {
                        in_order = false;
                        break;
                    }
                }
                in_order
            } else {
                false
            };

            let phrase_score = if is_exact {
                1.0
            } else if starts_with {
                0.90
            } else if contains_phrase {
                0.80
            } else if all_tokens_in_order {
                0.70
            } else {
                0.0
            };

            // 2. Token overlap ratio with lightweight typo tolerance
            let mut matched_tokens: f64 = 0.0;
            for qt in &q_tokens {
                if title_tokens.contains(qt) {
                    matched_tokens += 1.0;
                } else if title_tokens.iter().any(|tt| crate::normalization::levenshtein_similarity(qt, tt) >= 0.70) {
                    matched_tokens += 0.75;
                }
            }
            let token_coverage = if !q_tokens.is_empty() {
                (matched_tokens / q_tokens.len() as f64).min(1.0)
            } else {
                0.0
            };

            // 3. Artist / channel affinity
            let uploader_norm = c
                .uploader
                .as_deref()
                .map(crate::normalization::normalize_text)
                .unwrap_or_default();
            let artist_bonus = if !uploader_norm.is_empty()
                && (norm_q.contains(&uploader_norm) || uploader_norm.contains(&norm_q))
            {
                0.15
            } else {
                0.0
            };

            // 4. Content classification (Crucial: Never allow gameplay videos in audio mode!)
            let classification = crate::media_classifier::classify_candidate(
                &c.title,
                c.uploader.as_deref().unwrap_or(""),
                c.duration.unwrap_or(0.0),
            );
            let is_music = classification.is_music;
            let content_type = match classification.category {
                crate::media_classifier::MediaCategory::SoundtrackOrOST => "soundtrack",
                _ if !is_music => "video",
                _ => "song",
            };

            let mut audio_mode_mult = 1.0;
            let mut explanations = Vec::new();
            if is_audio_mode && !is_music {
                audio_mode_mult = 0.15;
                explanations.push("Demoted non-music video in audio mode (Flash)".to_string());
            }

            let query_wants_live = norm_q.contains("live");
            let is_unrequested_live = !query_wants_live && (norm_title.contains("live") || norm_title.contains("piano live") || norm_title.contains("acoustic live"));
            let version_mult = if is_unrequested_live { 0.75 } else { 1.0 };

            // Weighted composite flash relevance
            let raw_relevance = (((phrase_score * 0.45) + (token_coverage * 0.40) + artist_bonus) * version_mult) * audio_mode_mult;

            // Popularity normalization (exact same principles as Rei)
            let (pop_score, has_pop_data) = crate::features::normalize_popularity(&c);

            let final_score = if is_broad {
                explanations.push("Broad discovery search (Flash)".to_string());
                (0.25 * raw_relevance + 0.75 * pop_score).max(0.0)
            } else if raw_relevance < 0.15 {
                raw_relevance * 0.50
            } else {
                let pop_mult = if has_pop_data {
                    1.0 + 0.50 * (pop_score - 0.50)
                } else {
                    1.0
                };
                raw_relevance * pop_mult
            };

            let rounded_score = ((final_score) * 10000.0).round() / 10000.0;
            let confidence = if rounded_score >= 0.70 {
                "high".to_string()
            } else if rounded_score >= 0.40 {
                "medium".to_string()
            } else {
                "low".to_string()
            };

            if is_exact {
                explanations.push("Exact title match (Flash)".to_string());
            } else if phrase_score >= 0.75 {
                explanations.push("Phrase match (Flash)".to_string());
            }

            let feat = crate::features::ExtractedFeatures {
                exact_title: if is_exact { 1.0 } else { 0.0 },
                phrase_match: phrase_score,
                token_coverage,
                token_order: if starts_with { 1.0 } else { 0.5 },
                typo_similarity: 0.0,
                artist_affinity: artist_bonus,
                version_compat: 1.0,
                duration_compat: 1.0,
                non_music_penalty: if is_music { 1.0 } else { 0.25 },
                popularity_boost: (pop_score * 0.05).min(0.05),
                audio_platform_boost: 0.0,
                popularity_score: pop_score,
                has_popularity_data: has_pop_data,
            };

            ScoredCandidate {
                id: c.id,
                title: c.title,
                clean_title: c.clean_title,
                song_title: c.song_title,
                artist: c.artist,
                context_source: c.context_source,
                is_cluttered: c.is_cluttered,
                is_cutscene: c.is_cutscene,
                is_music: Some(is_music),
                content_type: Some(content_type.to_string()),
                uploader: c.uploader,
                duration: c.duration,
                views: c.views,
                likes: c.likes,
                listeners: c.listeners,
                chart_rank: c.chart_rank,
                release_year: c.release_year,
                is_trending: c.is_trending,
                popularity: Some(pop_score),
                platform: c.platform,
                url: c.url,
                score: rounded_score,
                confidence,
                features: feat,
                explanations,
            }
        })
        .collect();

    scored.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| {
                b.features
                    .exact_title
                    .partial_cmp(&a.features.exact_title)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| {
                b.features
                    .popularity_score
                    .partial_cmp(&a.features.popularity_score)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| {
                let v_a = a.views.unwrap_or(0);
                let v_b = b.views.unwrap_or(0);
                v_b.cmp(&v_a)
            })
            .then_with(|| a.id.cmp(&b.id))
    });

    if let Some(l) = limit {
        scored.truncate(l);
    }

    scored
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_number_one_bankai_vs_we_are() {
        let query = QueryInput {
            raw_query: "Number One - Bankai".to_string(),
            normalized_query: Some("number one bankai".to_string()),
            expected_artist: None,
            expected_title: None,
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_onepiece".to_string(),
                title: "Hiroshi Kitadani - We Are! (One Piece Opening)".to_string(),
                uploader: Some("Avex Pictures".to_string()),
                duration: Some(240.0),
                views: Some(50_000_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=op1".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_bleach".to_string(),
                title: "Bleach: Thousand-Year Blood War - Number One - Bankai (Hazel Fernandes)".to_string(),
                uploader: Some("Shiro Sagisu - Topic".to_string()),
                duration: Some(290.0),
                views: Some(5_000_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=bleach1".to_string()),
                ..Default::default()
            },
        ];

        let ranked = rank_candidates(&query, candidates, None);
        assert_eq!(ranked[0].id, "c_bleach", "Bleach Number One Bankai must rank #1 over One Piece We Are");
    }

    #[test]
    fn test_jumping_machine_vs_emptiness_machine() {
        let query = QueryInput {
            raw_query: "jumping machine".to_string(),
            normalized_query: Some("jumping machine".to_string()),
            expected_artist: None,
            expected_title: None,
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_lp".to_string(),
                title: "Linkin Park - The Emptiness Machine (Official Music Video)".to_string(),
                uploader: Some("Linkin Park".to_string()),
                duration: Some(190.0),
                views: Some(80_000_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=lp1".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_jumping".to_string(),
                title: "Jumping Machine - Original Mix (Audio)".to_string(),
                uploader: Some("Electro Records".to_string()),
                duration: Some(210.0),
                views: Some(10_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=jump1".to_string()),
                ..Default::default()
            },
        ];

        let ranked = rank_candidates(&query, candidates, None);
        assert_eq!(ranked[0].id, "c_jumping", "Literal Jumping Machine must rank #1 over Linkin Park");
    }

    #[test]
    fn test_flash_ranking_precision_and_gameplay_rejection() {
        let query = QueryInput {
            raw_query: "Counter-Strike 2".to_string(),
            normalized_query: Some("counter-strike 2".to_string()),
            expected_artist: None,
            expected_title: None,
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_trailer".to_string(),
                title: "Counter-Strike 2 - Official Release Trailer".to_string(),
                uploader: Some("Valve".to_string()),
                duration: Some(180.0),
                views: Some(25_000_000),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_theme".to_string(),
                title: "Counter-Strike 2 - Main Menu Theme Song (Official Audio)".to_string(),
                uploader: Some("Valve".to_string()),
                duration: Some(195.0),
                views: Some(3_000_000),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
        ];

        let ranked = rank_candidates_flash(&query, candidates, None);
        assert_eq!(ranked[0].id, "c_theme", "CS2 theme song must rank above gameplay trailer in Flash audio mode");
        assert!(ranked[0].is_music.unwrap_or(false));
        assert!(!ranked[1].is_music.unwrap_or(true));
    }


    #[test]
    fn test_ambiguous_bad_guy_popular_vs_obscure() {
        let query = QueryInput {
            raw_query: "bad guy".to_string(),
            normalized_query: Some("bad guy".to_string()),
            expected_artist: None,
            expected_title: Some("bad guy".to_string()),
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_obscure".to_string(),
                title: "bad guy - Local Garage Band Demo".to_string(),
                uploader: Some("Unknown Band".to_string()),
                duration: Some(195.0),
                views: Some(120),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_billie".to_string(),
                title: "Billie Eilish - bad guy (Official Video)".to_string(),
                uploader: Some("Billie Eilish".to_string()),
                duration: Some(205.0),
                views: Some(1_400_000_000),
                chart_rank: Some(1),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_missing_data".to_string(),
                title: "bad guy - Unlabeled Stream Rip".to_string(),
                uploader: Some("IndieUploader".to_string()),
                duration: Some(200.0),
                views: None, // Missing popularity data
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
        ];

        // 1. Rei Precision Mode
        let ranked_rei = rank_candidates(&query, candidates.clone(), None);
        assert_eq!(ranked_rei[0].id, "c_billie", "Billie Eilish must rank #1 on ambiguous title in Rei");
        assert_eq!(ranked_rei[1].id, "c_missing_data", "Missing data must not be unfairly penalized below obscure 120-view track in Rei");
        assert_eq!(ranked_rei[2].id, "c_obscure", "120-view obscure demo must rank lowest among title matches in Rei");

        // 2. Rei Flash Speed Mode
        let ranked_flash = rank_candidates_flash(&query, candidates, None);
        assert_eq!(ranked_flash[0].id, "c_billie", "Billie Eilish must rank #1 on ambiguous title in Flash");
        assert_eq!(ranked_flash[1].id, "c_missing_data", "Missing data must not be unfairly penalized in Flash");
        assert_eq!(ranked_flash[2].id, "c_obscure", "Obscure track must rank lowest in Flash");
    }

    #[test]
    fn test_broad_search_popular_songs() {
        let query = QueryInput {
            raw_query: "popular songs".to_string(),
            normalized_query: Some("popular songs".to_string()),
            expected_artist: None,
            expected_title: None,
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_random_compilation".to_string(),
                title: "Popular Songs 2026 - Top 10 Playlist Mix".to_string(),
                uploader: Some("RandomUser123".to_string()),
                duration: Some(300.0),
                views: Some(500),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_blinding_lights".to_string(),
                title: "The Weeknd - Blinding Lights (Official Audio)".to_string(),
                uploader: Some("The Weeknd".to_string()),
                duration: Some(200.0),
                views: Some(4_200_000_000),
                chart_rank: Some(1),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_bohemian".to_string(),
                title: "Queen - Bohemian Rhapsody (Official Video)".to_string(),
                uploader: Some("Queen Official".to_string()),
                duration: Some(355.0),
                views: Some(1_600_000_000),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
        ];

        let ranked_rei = rank_candidates(&query, candidates.clone(), None);
        assert_eq!(ranked_rei[0].id, "c_blinding_lights", "Blinding Lights must rank #1 on broad discovery query 'popular songs' in Rei");
        assert_eq!(ranked_rei[1].id, "c_bohemian", "Bohemian Rhapsody must rank #2 in Rei");
        assert_eq!(ranked_rei[2].id, "c_random_compilation", "500-view compilation must rank last despite keyword 'popular songs'");

        let ranked_flash = rank_candidates_flash(&query, candidates, None);
        assert_eq!(ranked_flash[0].id, "c_blinding_lights", "Blinding Lights must rank #1 in Flash");
        assert_eq!(ranked_flash[1].id, "c_bohemian", "Bohemian Rhapsody must rank #2 in Flash");
    }

    #[test]
    fn test_specific_search_preserves_relevance_over_popularity() {
        let query = QueryInput {
            raw_query: "Number One by Bankai".to_string(),
            normalized_query: Some("number one by bankai".to_string()),
            expected_artist: None,
            expected_title: None,
            expected_duration: None,
            version_hint: None,
            media_type: Some("audio".to_string()),
        };

        let candidates = vec![
            CandidateInput {
                id: "c_ed_sheeran".to_string(),
                title: "Ed Sheeran - Shape of You (Official Music Video)".to_string(),
                uploader: Some("Ed Sheeran".to_string()),
                duration: Some(235.0),
                views: Some(6_000_000_000), // Huge views, completely unrelated
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
            CandidateInput {
                id: "c_number_one".to_string(),
                title: "Bleach TYBW - Number One (Bankai Version) - Shiro SAGISU".to_string(),
                uploader: Some("Shiro Sagisu - Topic".to_string()),
                duration: Some(305.0),
                views: Some(14_000_000),
                platform: Some("youtube".to_string()),
                ..Default::default()
            },
        ];

        let ranked_rei = rank_candidates(&query, candidates.clone(), None);
        assert_eq!(ranked_rei[0].id, "c_number_one", "Relevant song must decisively outrank 6B-view unrelated track in Rei");

        let ranked_flash = rank_candidates_flash(&query, candidates, None);
        assert_eq!(ranked_flash[0].id, "c_number_one", "Relevant song must decisively outrank 6B-view unrelated track in Flash");
    }

}
