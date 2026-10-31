//! Intelligent Media Type & Music Candidate Classifier in native Rust.
//!
//! Classifies incoming media candidates into granular music categories,
//! filters out non-music content (gameplays, reaction videos, walk-throughs),
//! and calculates download suitability scores.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MediaCategory {
    OfficialAudio,
    OfficialMusicVideo,
    LyricVideo,
    LivePerformance,
    AcousticOrPiano,
    RemixOrNightcore,
    SoundtrackOrOST,
    CoverSong,
    GameplayOrWalkthrough,
    ReactionOrReview,
    PodcastOrTalk,
    GeneralVideo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MediaClassification {
    pub category: MediaCategory,
    pub is_music: bool,
    pub audio_suitability_score: f64, // 0.0 to 1.0
    pub detected_version_tags: Vec<String>,
    pub explanation: String,
}

const NON_MUSIC_CUES: &[&str] = &[
    "gameplay",
    "walkthrough",
    "playthrough",
    "let's play",
    "lets play",
    "speedrun",
    "full boss fight",
    "boss fight",
    "full cutscene",
    "cutscene",
    "reaction to",
    "reacts to",
    "first time hearing",
    "first reaction",
    "breakdown & analysis",
    "review & recap",
    "review",
    "podcast episode",
    "full episode",
    "unboxing",
    "tutorial",
    "how to fix",
    "trailer",
    "official trailer",
    "teaser",
    "gameplay trailer",
    "launch trailer",
    "cinematic trailer",
    "fragmovie",
    "highlights",
    "montage",
    "clutch",
    "ace",
    "funny moments",
    "fails",
    "patch notes",
    "dev diary",
    "tier list",
    "movie clip",
    "anime clip",
];

const OFFICIAL_MUSIC_CUES: &[&str] = &[
    "official audio",
    "official music video",
    "official video",
    "official mv",
    "official visualizer",
    "provided to youtube",
    "topic",
    "soundtrack",
    "ost",
    "theme song",
    "main menu theme",
    "original soundtrack",
    "opening theme",
    "ending theme",
    "records",
    "vevo",
];

const LYRIC_CUES: &[&str] = &["lyrics", "lyric video", "lyrics video", "color coded lyrics"];

const LIVE_CUES: &[&str] = &["live at", "live from", "live performance", "live in concert", "acoustic session", "tiny desk"];

const VERSION_CUES: &[(&str, &str)] = &[
    ("remix", "Remix"),
    ("nightcore", "Nightcore"),
    ("slowed", "Slowed & Reverb"),
    ("speed up", "Sped Up"),
    ("sped up", "Sped Up"),
    ("jersey club", "Jersey Club"),
    ("lofi", "Lo-Fi"),
    ("lo-fi", "Lo-Fi"),
    ("acoustic", "Acoustic"),
    ("instrumental", "Instrumental"),
    ("karaoke", "Karaoke"),
    ("orchestral", "Orchestral"),
    ("piano cover", "Piano"),
    ("8d audio", "8D Audio"),
    ("bass boosted", "Bass Boosted"),
];

/// Classify a candidate's media title, uploader, and duration.
pub fn classify_candidate(title: &str, uploader: &str, duration_secs: f64) -> MediaClassification {
    let lower_title = title.to_lowercase();
    let lower_uploader = uploader.to_lowercase();

    // 1. Check for non-music indicators
    let has_non_music_cue = NON_MUSIC_CUES.iter().any(|&cue| lower_title.contains(cue));
    let has_music_override = OFFICIAL_MUSIC_CUES.iter().any(|&cue| lower_title.contains(cue))
        || lower_uploader.contains("topic")
        || lower_uploader.contains("records")
        || lower_uploader.contains("vevo");

    if has_non_music_cue && !has_music_override {
        let is_reaction = lower_title.contains("reaction") || lower_title.contains("reacts");
        return MediaClassification {
            category: if is_reaction {
                MediaCategory::ReactionOrReview
            } else {
                MediaCategory::GameplayOrWalkthrough
            },
            is_music: false,
            audio_suitability_score: 0.15,
            detected_version_tags: Vec::new(),
            explanation: "Candidate detected as non-music video (gameplay/reaction/cutscene)".to_string(),
        };
    }

    // Unusually long files (>20 minutes) without album keywords are usually podcasts / long streams
    if duration_secs > 1200.0 && !lower_title.contains("full album") && !lower_title.contains("discography") {
        return MediaClassification {
            category: MediaCategory::PodcastOrTalk,
            is_music: false,
            audio_suitability_score: 0.20,
            detected_version_tags: Vec::new(),
            explanation: "Candidate duration exceeds 20 minutes without album indicators".to_string(),
        };
    }

    // 2. Detect version tags
    let mut version_tags = Vec::new();
    for &(cue, tag) in VERSION_CUES {
        if lower_title.contains(cue) {
            version_tags.push(tag.to_string());
        }
    }

    // 3. Classify music category
    if lower_title.contains("official audio") || (lower_uploader.contains("topic") && !lower_title.contains("video")) {
        return MediaClassification {
            category: MediaCategory::OfficialAudio,
            is_music: true,
            audio_suitability_score: 1.00,
            detected_version_tags: version_tags,
            explanation: "Verified studio audio release".to_string(),
        };
    }

    if lower_title.contains("official music video") || lower_title.contains("official mv") || lower_title.contains("music video") {
        return MediaClassification {
            category: MediaCategory::OfficialMusicVideo,
            is_music: true,
            audio_suitability_score: 0.95,
            detected_version_tags: version_tags,
            explanation: "Official music video".to_string(),
        };
    }

    if LYRIC_CUES.iter().any(|&cue| lower_title.contains(cue)) {
        return MediaClassification {
            category: MediaCategory::LyricVideo,
            is_music: true,
            audio_suitability_score: 0.92,
            detected_version_tags: version_tags,
            explanation: "Lyric video release".to_string(),
        };
    }

    if LIVE_CUES.iter().any(|&cue| lower_title.contains(cue)) {
        return MediaClassification {
            category: MediaCategory::LivePerformance,
            is_music: true,
            audio_suitability_score: 0.85,
            detected_version_tags: version_tags,
            explanation: "Live performance or concert recording".to_string(),
        };
    }

    if lower_title.contains("ost") || lower_title.contains("soundtrack") || lower_title.contains("theme song") {
        return MediaClassification {
            category: MediaCategory::SoundtrackOrOST,
            is_music: true,
            audio_suitability_score: 0.92,
            detected_version_tags: version_tags,
            explanation: "Original soundtrack release".to_string(),
        };
    }

    if !version_tags.is_empty() {
        return MediaClassification {
            category: MediaCategory::RemixOrNightcore,
            is_music: true,
            audio_suitability_score: 0.88,
            detected_version_tags: version_tags,
            explanation: "Specialized remix/alternate version".to_string(),
        };
    }

    if lower_title.contains("cover") {
        return MediaClassification {
            category: MediaCategory::CoverSong,
            is_music: true,
            audio_suitability_score: 0.80,
            detected_version_tags: version_tags,
            explanation: "Cover performance".to_string(),
        };
    }

    MediaClassification {
        category: MediaCategory::GeneralVideo,
        is_music: true,
        audio_suitability_score: 0.75,
        detected_version_tags: version_tags,
        explanation: "General media release".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gameplay_rejection() {
        let c = classify_candidate("Elden Ring Malenia Full Boss Fight Gameplay No Damage", "GamersHub", 450.0);
        assert!(!c.is_music);
        assert_eq!(c.category, MediaCategory::GameplayOrWalkthrough);
    }

    #[test]
    fn test_official_audio() {
        let c = classify_candidate("Hazel Fernandes - Number One (Official Audio)", "Shiro Sagisu - Topic", 304.0);
        assert!(c.is_music);
        assert_eq!(c.category, MediaCategory::OfficialAudio);
        assert_eq!(c.audio_suitability_score, 1.0);
    }

    #[test]
    fn test_trailer_rejection() {
        let c = classify_candidate("Counter-Strike 2 - Official Release Trailer", "Valve", 180.0);
        assert!(!c.is_music);
        assert_eq!(c.category, MediaCategory::GameplayOrWalkthrough);
    }

    #[test]
    fn test_game_soundtrack_acceptance() {
        let c = classify_candidate("Counter-Strike 2 - Main Menu Theme Song (Official Audio)", "Valve", 195.0);
        assert!(c.is_music);
        assert_eq!(c.category, MediaCategory::OfficialAudio);
    }
}
