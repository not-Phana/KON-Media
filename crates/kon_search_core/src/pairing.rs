//! High-speed Smart Stream Pairing Evaluator in native Rust.
//!
//! Evaluates candidate video streams against candidate audio streams for
//! optimal muxing, duration synchronization, format tiering, and title alignment.

use serde::{Deserialize, Serialize};
use crate::normalization::{ngram_similarity, normalize_text, strip_media_noise};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamCandidate {
    pub id: String,
    pub title: String,
    pub duration: f64,
    pub format_id: Option<String>,
    pub ext: Option<String>,
    pub abr: Option<f64>,        // Audio bitrate in kbps
    pub height: Option<u32>,     // Video height (e.g. 1080, 2160)
    pub fps: Option<f64>,
    pub codec: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PairingEvaluation {
    pub pair_score: f64,
    pub is_compatible: bool,
    pub duration_delta: f64,
    pub title_similarity: f64,
    pub format_tier_score: f64,
    pub rejection_reason: Option<String>,
}

/// Computes pairing score between video candidate and audio candidate.
pub fn evaluate_stream_pair(video: &StreamCandidate, audio: &StreamCandidate) -> PairingEvaluation {
    let dur_delta = (video.duration - audio.duration).abs();

    // Duration alignment score
    let duration_score = if dur_delta <= 1.0 {
        1.00
    } else if dur_delta <= 3.0 {
        0.95
    } else if dur_delta <= 8.0 {
        0.80
    } else if dur_delta <= 15.0 {
        0.50
    } else if dur_delta <= 30.0 {
        0.20
    } else {
        0.05
    };

    // Title similarity
    let v_clean = strip_media_noise(&video.title);
    let a_clean = strip_media_noise(&audio.title);
    let v_norm = normalize_text(&v_clean);
    let a_norm = normalize_text(&a_clean);
    let title_sim = if v_norm == a_norm {
        1.0
    } else {
        ngram_similarity(&v_norm, &a_norm, 2)
    };

    // Format & bitrate tiering score
    let abr = audio.abr.unwrap_or(128.0);
    let abr_score = (abr / 320.0).clamp(0.2, 1.0);

    let codec_bonus = match audio.codec.as_deref().unwrap_or("").to_lowercase().as_str() {
        c if c.contains("opus") => 0.10,
        c if c.contains("mp4a") || c.contains("aac") => 0.08,
        c if c.contains("mp3") => 0.04,
        _ => 0.0,
    };

    let format_tier_score = (abr_score * 0.90 + codec_bonus).min(1.0);

    // Weighted composite pairing score
    let pair_score = (title_sim * 0.40) + (duration_score * 0.45) + (format_tier_score * 0.15);

    let mut is_compatible = true;
    let mut rejection_reason: Option<String> = None;

    if dur_delta > 45.0 {
        is_compatible = false;
        rejection_reason = Some(format!(
            "Duration mismatch too large: delta is {:.1}s (video={:.1}s, audio={:.1}s)",
            dur_delta, video.duration, audio.duration
        ));
    } else if title_sim < 0.25 {
        is_compatible = false;
        rejection_reason = Some(format!(
            "Title similarity too low: {:.2} between video and audio",
            title_sim
        ));
    }

    PairingEvaluation {
        pair_score,
        is_compatible,
        duration_delta: dur_delta,
        title_similarity: title_sim,
        format_tier_score,
        rejection_reason,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stream_pair_perfect() {
        let v = StreamCandidate {
            id: "vid1".into(),
            title: "Number One (Bankai) - Bleach TYBW".into(),
            duration: 304.0,
            format_id: Some("137".into()),
            ext: Some("mp4".into()),
            abr: None,
            height: Some(1080),
            fps: Some(60.0),
            codec: Some("avc1".into()),
        };
        let a = StreamCandidate {
            id: "aud1".into(),
            title: "Number One (Bankai) - Bleach TYBW (Official Audio)".into(),
            duration: 304.5,
            format_id: Some("251".into()),
            ext: Some("webm".into()),
            abr: Some(160.0),
            height: None,
            fps: None,
            codec: Some("opus".into()),
        };
        let eval = evaluate_stream_pair(&v, &a);
        assert!(eval.is_compatible);
        assert!(eval.pair_score > 0.85);
        assert!(eval.duration_delta <= 1.0);
    }
}
