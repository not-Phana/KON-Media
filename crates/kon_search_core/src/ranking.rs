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
                let v_a = a.views.unwrap_or(0);
                let v_b = b.views.unwrap_or(0);
                v_b.cmp(&v_a)
            })
            .then_with(|| a.id.cmp(&b.id))
    });

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
            },
            CandidateInput {
                id: "c_bleach".to_string(),
                title: "Bleach: Thousand-Year Blood War - Number One - Bankai (Hazel Fernandes)".to_string(),
                uploader: Some("Shiro Sagisu - Topic".to_string()),
                duration: Some(290.0),
                views: Some(5_000_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=bleach1".to_string()),
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
            },
            CandidateInput {
                id: "c_jumping".to_string(),
                title: "Jumping Machine - Original Mix (Audio)".to_string(),
                uploader: Some("Electro Records".to_string()),
                duration: Some(210.0),
                views: Some(10_000),
                platform: Some("youtube".to_string()),
                url: Some("https://youtube.com/watch?v=jump1".to_string()),
            },
        ];

        let ranked = rank_candidates(&query, candidates, None);
        assert_eq!(ranked[0].id, "c_jumping", "Literal Jumping Machine must rank #1 over Linkin Park");
    }
}
