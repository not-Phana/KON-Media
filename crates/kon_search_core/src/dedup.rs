use crate::features::CandidateInput;
use crate::normalization::normalize_text;
use std::collections::HashSet;

/// Normalize a media URL into a canonical deduplication key.
pub fn normalize_media_url(raw_url: &str) -> String {
    let trimmed = raw_url.trim();
    if trimmed.is_empty() {
        return String::new();
    }

    // YouTube canonicalization
    if trimmed.contains("youtube.com/watch") {
        if let Some(pos) = trimmed.find("v=") {
            let after_v = &trimmed[pos + 2..];
            let id = after_v.split('&').next().unwrap_or(after_v);
            return format!("https://www.youtube.com/watch?v={}", id);
        }
    } else if trimmed.contains("youtu.be/") {
        if let Some(pos) = trimmed.find("youtu.be/") {
            let after_slash = &trimmed[pos + 9..];
            let id = after_slash.split('?').next().unwrap_or(after_slash);
            return format!("https://www.youtube.com/watch?v={}", id);
        }
    } else if trimmed.contains("soundcloud.com/") {
        // Strip query params like ?in=...
        let base = trimmed.split('?').next().unwrap_or(trimmed);
        return base.trim_end_matches('/').to_string();
    }

    trimmed.to_string()
}

/// Deduplicate candidates while strictly preserving distinct versions and platforms.
pub fn deduplicate_candidates(candidates: Vec<CandidateInput>) -> Vec<CandidateInput> {
    let mut seen_urls: HashSet<String> = HashSet::new();
    let mut seen_platform_keys: HashSet<(String, String, String)> = HashSet::new();
    let mut deduped: Vec<CandidateInput> = Vec::with_capacity(candidates.len());

    for cand in candidates {
        // URL dedup
        if let Some(ref url) = cand.url {
            let norm_url = normalize_media_url(url);
            if !norm_url.is_empty() {
                if seen_urls.contains(&norm_url) {
                    continue;
                }
                seen_urls.insert(norm_url);
            }
        }

        // Platform-scoped title and uploader dedup
        let norm_title = normalize_text(&cand.title);
        let norm_uploader = normalize_text(cand.uploader.as_deref().unwrap_or(""));
        let dur_bucket = match cand.duration {
            Some(d) => ((d / 4.0) as i64).to_string(),
            None => "none".to_string(),
        };
        let platform_name = cand.platform.as_deref().unwrap_or("unknown").to_string();
        let uploader_key = if !norm_uploader.is_empty() {
            norm_uploader
        } else {
            dur_bucket
        };
        let platform_key = (platform_name, norm_title, uploader_key);

        if seen_platform_keys.contains(&platform_key) {
            continue;
        }
        seen_platform_keys.insert(platform_key);

        deduped.push(cand);
    }

    deduped
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_media_url() {
        assert_eq!(
            normalize_media_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&ab_channel=RickAstley"),
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        );
        assert_eq!(
            normalize_media_url("https://youtu.be/dQw4w9WgXcQ?si=abcdef"),
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        );
        assert_eq!(
            normalize_media_url("https://soundcloud.com/artist/song?in=playlist"),
            "https://soundcloud.com/artist/song"
        );
    }
}
