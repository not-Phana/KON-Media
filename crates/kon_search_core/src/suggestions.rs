//! Intelligent Search Suggestions & Music Discovery Core in native Rust.
//!
//! Provides ultra-fast, deterministic query understanding, entity discovery,
//! canonical music knowledge retrieval, typo tolerance, and multi-signal scoring.

use std::collections::HashSet;
use serde::{Deserialize, Serialize};

use crate::normalization::{ngram_similarity, normalize_text};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SuggestionIntent {
    pub raw_query: String,
    pub normalized_query: String,
    pub tokens: Vec<String>,
    pub matched_artists: Vec<MatchedArtistInfo>,
    pub detected_version: Option<String>,
    pub detected_context: Option<String>,
    pub title_fragments: Vec<String>,
    pub is_artist_focused: bool,
    pub is_version_focused: bool,
    pub is_context_focused: bool,
    pub is_single_keyword: bool,
    pub suggested_interpretations: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MatchedArtistInfo {
    pub key: String,
    pub canonical_name: String,
    pub genre: String,
    pub match_type: String,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SuggestionItem {
    pub title: String,
    pub artist: String,
    pub suggestion_type: String, // "title", "artist", "keyword", "version", "context"
    pub reason: String,
    pub confidence: String, // "strong", "possible", "weak"
    pub score: f64,
    pub url: String,
    pub thumbnail: String,
    pub duration: f64,
    pub context: Option<String>,
}

#[derive(Debug, Clone)]
pub struct CanonicalSong {
    pub title: &'static str,
    pub artist: &'static str,
    pub duration: f64,
    pub url: &'static str,
    pub thumbnail: &'static str,
    pub context: Option<&'static str>,
}

#[derive(Debug, Clone)]
pub struct CanonicalArtist {
    pub canonical_name: &'static str,
    pub aliases: &'static [&'static str],
    pub genre: &'static str,
    pub top_songs: &'static [CanonicalSong],
}

// -----------------------------------------------------------------------------
// Version Keywords & Context Dictionaries
// -----------------------------------------------------------------------------

pub const VERSION_KEYWORDS: &[&str] = &[
    "remix",
    "live",
    "cover",
    "acoustic",
    "instrumental",
    "extended",
    "nightcore",
    "slowed",
    "reverb",
    "jersey club",
    "lofi",
    "karaoke",
    "bass boosted",
    "piano",
    "orchestral",
    "original",
    "sped up",
    "spedup",
    "slowed down",
];

pub struct ContextMapping {
    pub trigger_terms: &'static [&'static str],
    pub franchise_name: &'static str,
    pub songs: &'static [CanonicalSong],
}

// -----------------------------------------------------------------------------
// Static Catalogs
// -----------------------------------------------------------------------------

static ARTIST_PORTER_ROBINSON_SONGS: [CanonicalSong; 5] = [
    CanonicalSong {
        title: "Shelter",
        artist: "Porter Robinson & Madeon",
        duration: 219.0,
        url: "https://www.youtube.com/watch?v=fzQ6gRAE308",
        thumbnail: "https://i.ytimg.com/vi/fzQ6gRAE308/hqdefault.jpg",
        context: Some("A-1 Pictures Anime Short Film"),
    },
    CanonicalSong {
        title: "Sad Machine",
        artist: "Porter Robinson",
        duration: 350.0,
        url: "https://www.youtube.com/watch?v=HAIDqt2xUek",
        thumbnail: "https://i.ytimg.com/vi/HAIDqt2xUek/hqdefault.jpg",
        context: Some("Worlds Album"),
    },
    CanonicalSong {
        title: "Language",
        artist: "Porter Robinson",
        duration: 368.0,
        url: "https://www.youtube.com/watch?v=5LILChvqUo4",
        thumbnail: "https://i.ytimg.com/vi/5LILChvqUo4/hqdefault.jpg",
        context: Some("Forza Horizon Soundtrack"),
    },
    CanonicalSong {
        title: "Look at the Sky",
        artist: "Porter Robinson",
        duration: 310.0,
        url: "https://www.youtube.com/watch?v=TJbh8_iOaL4",
        thumbnail: "https://i.ytimg.com/vi/TJbh8_iOaL4/hqdefault.jpg",
        context: Some("Nurture Album"),
    },
    CanonicalSong {
        title: "Goodbye to a World",
        artist: "Porter Robinson",
        duration: 328.0,
        url: "https://www.youtube.com/watch?v=W2TE0DjdN6I",
        thumbnail: "https://i.ytimg.com/vi/W2TE0DjdN6I/hqdefault.jpg",
        context: Some("Worlds Album"),
    },
];

static ARTIST_ARCTIC_MONKEYS_SONGS: [CanonicalSong; 4] = [
    CanonicalSong {
        title: "I Wanna Be Yours",
        artist: "Arctic Monkeys",
        duration: 184.0,
        url: "https://www.youtube.com/watch?v=nyuo9-OjNNg",
        thumbnail: "https://i.ytimg.com/vi/nyuo9-OjNNg/hqdefault.jpg",
        context: Some("AM Album"),
    },
    CanonicalSong {
        title: "Do I Wanna Know?",
        artist: "Arctic Monkeys",
        duration: 272.0,
        url: "https://www.youtube.com/watch?v=bpOSxM0rNPM",
        thumbnail: "https://i.ytimg.com/vi/bpOSxM0rNPM/hqdefault.jpg",
        context: Some("AM Album"),
    },
    CanonicalSong {
        title: "505",
        artist: "Arctic Monkeys",
        duration: 253.0,
        url: "https://www.youtube.com/watch?v=qU9mHegkTc4",
        thumbnail: "https://i.ytimg.com/vi/qU9mHegkTc4/hqdefault.jpg",
        context: Some("Favourite Worst Nightmare"),
    },
    CanonicalSong {
        title: "Why'd You Only Call Me When You're High?",
        artist: "Arctic Monkeys",
        duration: 161.0,
        url: "https://www.youtube.com/watch?v=6366dxFf-Os",
        thumbnail: "https://i.ytimg.com/vi/6366dxFf-Os/hqdefault.jpg",
        context: Some("AM Album"),
    },
];

static ARTIST_SHIRO_SAGISU_SONGS: [CanonicalSong; 5] = [
    CanonicalSong {
        title: "Number One (Bankai)",
        artist: "Hazel Fernandes & Shiro Sagisu",
        duration: 304.0,
        url: "https://www.youtube.com/watch?v=1lsn2tT5yTc",
        thumbnail: "https://i.ytimg.com/vi/1lsn2tT5yTc/hqdefault.jpg",
        context: Some("Bleach: Thousand-Year Blood War Theme"),
    },
    CanonicalSong {
        title: "Number One (Original)",
        artist: "Hazel Fernandes & Shiro Sagisu",
        duration: 298.0,
        url: "https://www.youtube.com/watch?v=6UpyiJ3q2pQ",
        thumbnail: "https://i.ytimg.com/vi/6UpyiJ3q2pQ/hqdefault.jpg",
        context: Some("Bleach OST Original 2004"),
    },
    CanonicalSong {
        title: "On The Precipice Of Defeat",
        artist: "Shiro Sagisu",
        duration: 172.0,
        url: "https://www.youtube.com/watch?v=ze5W8cDHcsQ",
        thumbnail: "https://i.ytimg.com/vi/ze5W8cDHcsQ/hqdefault.jpg",
        context: Some("Bleach Battle Theme"),
    },
    CanonicalSong {
        title: "Invasion",
        artist: "Shiro Sagisu",
        duration: 168.0,
        url: "https://www.youtube.com/watch?v=z8aO4hG-a5M",
        thumbnail: "https://i.ytimg.com/vi/z8aO4hG-a5M/hqdefault.jpg",
        context: Some("Bleach Espada Theme"),
    },
    CanonicalSong {
        title: "Treachery",
        artist: "Shiro Sagisu",
        duration: 183.0,
        url: "https://www.youtube.com/watch?v=1rXjH4gUqX8",
        thumbnail: "https://i.ytimg.com/vi/1rXjH4gUqX8/hqdefault.jpg",
        context: Some("Bleach Aizen Theme"),
    },
];

static ARTIST_NEWJEANS_SONGS: [CanonicalSong; 4] = [
    CanonicalSong {
        title: "Ditto",
        artist: "NewJeans",
        duration: 186.0,
        url: "https://www.youtube.com/watch?v=pSUydWEqKwE",
        thumbnail: "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
        context: Some("OMG Single Album"),
    },
    CanonicalSong {
        title: "OMG",
        artist: "NewJeans",
        duration: 212.0,
        url: "https://www.youtube.com/watch?v=sVTy_wmn5SU",
        thumbnail: "https://i.ytimg.com/vi/sVTy_wmn5SU/hqdefault.jpg",
        context: Some("OMG Single Album"),
    },
    CanonicalSong {
        title: "Hype Boy",
        artist: "NewJeans",
        duration: 179.0,
        url: "https://www.youtube.com/watch?v=11cta61Wi0g",
        thumbnail: "https://i.ytimg.com/vi/11cta61Wi0g/hqdefault.jpg",
        context: Some("1st EP 'New Jeans'"),
    },
    CanonicalSong {
        title: "Super Shy",
        artist: "NewJeans",
        duration: 154.0,
        url: "https://www.youtube.com/watch?v=ArmDp-zijuc",
        thumbnail: "https://i.ytimg.com/vi/ArmDp-zijuc/hqdefault.jpg",
        context: Some("Get Up 2nd EP"),
    },
];

static ARTIST_YOASOBI_SONGS: [CanonicalSong; 4] = [
    CanonicalSong {
        title: "Idol (アイドル)",
        artist: "YOASOBI",
        duration: 213.0,
        url: "https://www.youtube.com/watch?v=ZRtdQ81jPUQ",
        thumbnail: "https://i.ytimg.com/vi/ZRtdQ81jPUQ/hqdefault.jpg",
        context: Some("Oshi no Ko Opening Theme"),
    },
    CanonicalSong {
        title: "Yoru ni Kakeru (夜に駆ける)",
        artist: "YOASOBI",
        duration: 261.0,
        url: "https://www.youtube.com/watch?v=by4SYYWlhEs",
        thumbnail: "https://i.ytimg.com/vi/by4SYYWlhEs/hqdefault.jpg",
        context: Some("Debut Single (Racing into the Night)"),
    },
    CanonicalSong {
        title: "Kaibutsu (怪物)",
        artist: "YOASOBI",
        duration: 206.0,
        url: "https://www.youtube.com/watch?v=dy90tA3TT1c",
        thumbnail: "https://i.ytimg.com/vi/dy90tA3TT1c/hqdefault.jpg",
        context: Some("BEASTARS Season 2 OP"),
    },
    CanonicalSong {
        title: "Gunjou (群青)",
        artist: "YOASOBI",
        duration: 248.0,
        url: "https://www.youtube.com/watch?v=Y4nEEZwckuU",
        thumbnail: "https://i.ytimg.com/vi/Y4nEEZwckuU/hqdefault.jpg",
        context: Some("Blue Period Inspired"),
    },
];

static ARTIST_KENSHI_YONEZU_SONGS: [CanonicalSong; 3] = [
    CanonicalSong {
        title: "KICK BACK",
        artist: "Kenshi Yonezu",
        duration: 193.0,
        url: "https://www.youtube.com/watch?v=M2cckDmNLMI",
        thumbnail: "https://i.ytimg.com/vi/M2cckDmNLMI/hqdefault.jpg",
        context: Some("Chainsaw Man OP"),
    },
    CanonicalSong {
        title: "Lemon",
        artist: "Kenshi Yonezu",
        duration: 255.0,
        url: "https://www.youtube.com/watch?v=SX_ViT4Ra7k",
        thumbnail: "https://i.ytimg.com/vi/SX_ViT4Ra7k/hqdefault.jpg",
        context: Some("Unnatural Drama Theme"),
    },
    CanonicalSong {
        title: "Peace Sign",
        artist: "Kenshi Yonezu",
        duration: 242.0,
        url: "https://www.youtube.com/watch?v=9aJVr5tTTWk",
        thumbnail: "https://i.ytimg.com/vi/9aJVr5tTTWk/hqdefault.jpg",
        context: Some("My Hero Academia Season 2 OP"),
    },
];

static ARTIST_THE_WEEKND_SONGS: [CanonicalSong; 3] = [
    CanonicalSong {
        title: "Blinding Lights",
        artist: "The Weeknd",
        duration: 200.0,
        url: "https://www.youtube.com/watch?v=4NRXx6U8ABQ",
        thumbnail: "https://i.ytimg.com/vi/4NRXx6U8ABQ/hqdefault.jpg",
        context: Some("After Hours Album"),
    },
    CanonicalSong {
        title: "Starboy",
        artist: "The Weeknd ft. Daft Punk",
        duration: 230.0,
        url: "https://www.youtube.com/watch?v=34Na4j8AVgA",
        thumbnail: "https://i.ytimg.com/vi/34Na4j8AVgA/hqdefault.jpg",
        context: Some("Starboy Album"),
    },
    CanonicalSong {
        title: "Save Your Tears",
        artist: "The Weeknd",
        duration: 215.0,
        url: "https://www.youtube.com/watch?v=XXYlFuWEuKI",
        thumbnail: "https://i.ytimg.com/vi/XXYlFuWEuKI/hqdefault.jpg",
        context: Some("After Hours Album"),
    },
];

static ARTIST_DAFT_PUNK_SONGS: [CanonicalSong; 3] = [
    CanonicalSong {
        title: "Get Lucky",
        artist: "Daft Punk ft. Pharrell Williams",
        duration: 248.0,
        url: "https://www.youtube.com/watch?v=5NV6Rdv1a3I",
        thumbnail: "https://i.ytimg.com/vi/5NV6Rdv1a3I/hqdefault.jpg",
        context: Some("Random Access Memories"),
    },
    CanonicalSong {
        title: "Harder, Better, Faster, Stronger",
        artist: "Daft Punk",
        duration: 224.0,
        url: "https://www.youtube.com/watch?v=gAjR4_CbPpQ",
        thumbnail: "https://i.ytimg.com/vi/gAjR4_CbPpQ/hqdefault.jpg",
        context: Some("Discovery / Interstella 5555"),
    },
    CanonicalSong {
        title: "One More Time",
        artist: "Daft Punk",
        duration: 320.0,
        url: "https://www.youtube.com/watch?v=FGBhQbmMxbw",
        thumbnail: "https://i.ytimg.com/vi/FGBhQbmMxbw/hqdefault.jpg",
        context: Some("Discovery / Interstella 5555"),
    },
];

static KNOWN_ARTISTS: &[CanonicalArtist] = &[
    CanonicalArtist {
        canonical_name: "Porter Robinson",
        aliases: &["porter", "porter robinson", "porterrobinson"],
        genre: "Electronic · Synth-pop",
        top_songs: &ARTIST_PORTER_ROBINSON_SONGS,
    },
    CanonicalArtist {
        canonical_name: "Arctic Monkeys",
        aliases: &["arctic monkeys", "arctic monkey", "alex turner"],
        genre: "Indie Rock · Post-Punk",
        top_songs: &ARTIST_ARCTIC_MONKEYS_SONGS,
    },
    CanonicalArtist {
        canonical_name: "Shiro Sagisu",
        aliases: &["shiro sagisu", "sagisu", "hazel fernandes", "bleach composer"],
        genre: "Soundtrack · Orchestral Rock",
        top_songs: &ARTIST_SHIRO_SAGISU_SONGS,
    },
    CanonicalArtist {
        canonical_name: "NewJeans",
        aliases: &["newjeans", "new jeans", "nwjns"],
        genre: "K-pop · R&B · Jersey Club",
        top_songs: &ARTIST_NEWJEANS_SONGS,
    },
    CanonicalArtist {
        canonical_name: "YOASOBI",
        aliases: &["yoasobi", "ayase", "ikura"],
        genre: "J-pop · Electro-pop",
        top_songs: &ARTIST_YOASOBI_SONGS,
    },
    CanonicalArtist {
        canonical_name: "Kenshi Yonezu",
        aliases: &["kenshi yonezu", "yonezu kenshi", "hachi"],
        genre: "J-rock · Art Pop",
        top_songs: &ARTIST_KENSHI_YONEZU_SONGS,
    },
    CanonicalArtist {
        canonical_name: "The Weeknd",
        aliases: &["the weeknd", "weeknd", "abel tesfaye"],
        genre: "R&B · Synthwave · Pop",
        top_songs: &ARTIST_THE_WEEKND_SONGS,
    },
    CanonicalArtist {
        canonical_name: "Daft Punk",
        aliases: &["daft punk", "daftpunk", "guy manuel", "thomas bangalter"],
        genre: "French House · Electronic",
        top_songs: &ARTIST_DAFT_PUNK_SONGS,
    },
];

// Context Mappings
static BLEACH_SONGS: [CanonicalSong; 5] = [
    CanonicalSong {
        title: "Number One (Bankai)",
        artist: "Hazel Fernandes & Shiro Sagisu",
        duration: 304.0,
        url: "https://www.youtube.com/watch?v=1lsn2tT5yTc",
        thumbnail: "https://i.ytimg.com/vi/1lsn2tT5yTc/hqdefault.jpg",
        context: Some("Bleach: Thousand-Year Blood War Theme"),
    },
    CanonicalSong {
        title: "On The Precipice Of Defeat",
        artist: "Shiro Sagisu",
        duration: 172.0,
        url: "https://www.youtube.com/watch?v=ze5W8cDHcsQ",
        thumbnail: "https://i.ytimg.com/vi/ze5W8cDHcsQ/hqdefault.jpg",
        context: Some("Bleach Battle Theme"),
    },
    CanonicalSong {
        title: "Asterisk (*〜アスタリスク〜)",
        artist: "ORANGE RANGE",
        duration: 254.0,
        url: "https://www.youtube.com/watch?v=b0b-JkPjL1s",
        thumbnail: "https://i.ytimg.com/vi/b0b-JkPjL1s/hqdefault.jpg",
        context: Some("Bleach OP 1"),
    },
    CanonicalSong {
        title: "Rolling Star",
        artist: "YUI",
        duration: 202.0,
        url: "https://www.youtube.com/watch?v=P_Xf_q9q_8k",
        thumbnail: "https://i.ytimg.com/vi/P_Xf_q9q_8k/hqdefault.jpg",
        context: Some("Bleach OP 5"),
    },
    CanonicalSong {
        title: "Velonica",
        artist: "Aqua Timez",
        duration: 278.0,
        url: "https://www.youtube.com/watch?v=cM7_zZ5J8fE",
        thumbnail: "https://i.ytimg.com/vi/cM7_zZ5J8fE/hqdefault.jpg",
        context: Some("Bleach OP 9"),
    },
];

static AOT_SONGS: [CanonicalSong; 3] = [
    CanonicalSong {
        title: "Guren no Yumiya (紅蓮の弓矢)",
        artist: "Linked Horizon",
        duration: 316.0,
        url: "https://www.youtube.com/watch?v=8OkpRK2_gVs",
        thumbnail: "https://i.ytimg.com/vi/8OkpRK2_gVs/hqdefault.jpg",
        context: Some("Attack on Titan Season 1 OP 1"),
    },
    CanonicalSong {
        title: "Shinzo wo Sasageyo! (心臓を捧げよ!)",
        artist: "Linked Horizon",
        duration: 341.0,
        url: "https://www.youtube.com/watch?v=CID-sYQNCew",
        thumbnail: "https://i.ytimg.com/vi/CID-sYQNCew/hqdefault.jpg",
        context: Some("Attack on Titan Season 2 OP"),
    },
    CanonicalSong {
        title: "The Rumbling",
        artist: "SiM",
        duration: 220.0,
        url: "https://www.youtube.com/watch?v=OB8_wBxv5p4",
        thumbnail: "https://i.ytimg.com/vi/OB8_wBxv5p4/hqdefault.jpg",
        context: Some("Attack on Titan Final Season Part 2 OP"),
    },
];

static NARUTO_SONGS: [CanonicalSong; 3] = [
    CanonicalSong {
        title: "Blue Bird (ブルーバード)",
        artist: "Ikimonogakari",
        duration: 215.0,
        url: "https://www.youtube.com/watch?v=KpsJWFuVTdI",
        thumbnail: "https://i.ytimg.com/vi/KpsJWFuVTdI/hqdefault.jpg",
        context: Some("Naruto Shippuden OP 3"),
    },
    CanonicalSong {
        title: "Silhouette (シルエット)",
        artist: "KANA-BOON",
        duration: 240.0,
        url: "https://www.youtube.com/watch?v=dlFA0Zq1k2A",
        thumbnail: "https://i.ytimg.com/vi/dlFA0Zq1k2A/hqdefault.jpg",
        context: Some("Naruto Shippuden OP 16"),
    },
    CanonicalSong {
        title: "Haruka Kanata (遥か彼方)",
        artist: "ASIAN KUNG-FU GENERATION",
        duration: 242.0,
        url: "https://www.youtube.com/watch?v=nJ6A6GC_ki4",
        thumbnail: "https://i.ytimg.com/vi/nJ6A6GC_ki4/hqdefault.jpg",
        context: Some("Naruto OP 2"),
    },
];

static CONTEXT_MAPPINGS: &[ContextMapping] = &[
    ContextMapping {
        trigger_terms: &["bleach", "bankai", "ichigo", "shinigami", "soul society"],
        franchise_name: "Bleach Soundtrack",
        songs: &BLEACH_SONGS,
    },
    ContextMapping {
        trigger_terms: &["attack on titan", "aot", "shingeki", "eren", "rumbling"],
        franchise_name: "Attack on Titan Soundtrack",
        songs: &AOT_SONGS,
    },
    ContextMapping {
        trigger_terms: &["naruto", "shippuden", "hokage", "sasuke"],
        franchise_name: "Naruto Soundtrack",
        songs: &NARUTO_SONGS,
    },
];

// -----------------------------------------------------------------------------
// Query Understanding Functions
// -----------------------------------------------------------------------------

pub fn parse_suggestion_intent(raw_query: &str) -> SuggestionIntent {
    let raw = raw_query.trim().to_string();
    let norm = normalize_text(&raw);
    let tokens: Vec<String> = norm.split_whitespace().map(|s| s.to_string()).collect();

    // Detect version
    let mut detected_version: Option<String> = None;
    for &vk in VERSION_KEYWORDS {
        if norm.contains(vk) {
            detected_version = Some(vk.to_string());
            break;
        }
    }

    // Detect context
    let mut detected_context: Option<String> = None;
    for cm in CONTEXT_MAPPINGS {
        for &term in cm.trigger_terms {
            if norm.contains(term) {
                detected_context = Some(cm.franchise_name.to_string());
                break;
            }
        }
        if detected_context.is_some() {
            break;
        }
    }

    // Detect artist
    let mut matched_artists = Vec::new();
    for artist in KNOWN_ARTISTS {
        for &alias in artist.aliases {
            let sim = if norm == alias {
                1.0
            } else if norm.starts_with(alias) || norm.contains(alias) {
                0.85
            } else {
                ngram_similarity(&norm, alias, 2)
            };

            if sim >= 0.70 {
                let match_type = if sim >= 0.99 {
                    "exact_alias"
                } else if sim >= 0.80 {
                    "prefix_alias"
                } else {
                    "fuzzy_alias"
                };
                matched_artists.push(MatchedArtistInfo {
                    key: alias.to_string(),
                    canonical_name: artist.canonical_name.to_string(),
                    genre: artist.genre.to_string(),
                    match_type: match_type.to_string(),
                    score: sim,
                });
                break;
            }
        }
    }

    let is_artist_focused = !matched_artists.is_empty()
        && (tokens.len() <= 3 || matched_artists.iter().any(|a| a.score >= 0.95));
    let is_version_focused = detected_version.is_some();
    let is_context_focused = detected_context.is_some();
    let is_single_keyword = tokens.len() == 1;

    let mut interpretations = Vec::new();
    if let Some(ref art) = matched_artists.first() {
        interpretations.push(format!("Artist: {}", art.canonical_name));
    }
    if let Some(ref ver) = detected_version {
        interpretations.push(format!("Version: {}", ver));
    }
    if let Some(ref ctx) = detected_context {
        interpretations.push(format!("Context: {}", ctx));
    }

    SuggestionIntent {
        raw_query: raw,
        normalized_query: norm,
        tokens,
        matched_artists,
        detected_version,
        detected_context,
        title_fragments: Vec::new(),
        is_artist_focused,
        is_version_focused,
        is_context_focused,
        is_single_keyword,
        suggested_interpretations: interpretations,
    }
}

// -----------------------------------------------------------------------------
// Scoring & Ranking Suggestions
// -----------------------------------------------------------------------------

pub fn score_suggestion(query_norm: &str, intent: &SuggestionIntent, song: &CanonicalSong) -> f64 {
    let song_norm = normalize_text(song.title);
    let artist_norm = normalize_text(song.artist);

    // Exact match
    if song_norm == query_norm {
        return 1.00;
    }

    let mut score: f64 = 0.0;

    // Title prefix / containment
    if song_norm.starts_with(query_norm) {
        score = score.max(0.90);
    } else if song_norm.contains(query_norm) {
        score = score.max(0.82);
    } else {
        // Token overlap
        let song_tokens: HashSet<&str> = song_norm.split_whitespace().collect();
        let matched = intent.tokens.iter().filter(|t| song_tokens.contains(t.as_str())).count();
        if !intent.tokens.is_empty() {
            let coverage = matched as f64 / intent.tokens.len() as f64;
            score = score.max(coverage * 0.75);
        }

        // Fuzzy typo match
        let typo = ngram_similarity(query_norm, &song_norm, 2);
        if typo > 0.60 {
            score = score.max(typo * 0.70);
        }
    }

    // Artist match bonus
    for ma in &intent.matched_artists {
        let ma_norm = normalize_text(&ma.canonical_name);
        if artist_norm.contains(&ma_norm) || ma_norm.contains(&artist_norm) {
            score = (score + 0.25).min(0.98);
            break;
        }
    }

    // Version match bonus / penalty
    if let Some(ref req_ver) = intent.detected_version {
        if song_norm.contains(req_ver) {
            score = (score + 0.20).min(0.99);
        } else {
            score = (score - 0.15).max(0.10);
        }
    }

    // Context match bonus
    if let Some(ref req_ctx) = intent.detected_context {
        if let Some(song_ctx) = song.context {
            if song_ctx.to_lowercase().contains(&req_ctx.to_lowercase()) {
                score = (score + 0.25).min(0.99);
            }
        }
    }

    score
}

pub fn get_search_suggestions(
    query: &str,
    _media_type: &str,
    limit: usize,
) -> Vec<SuggestionItem> {
    let trimmed = query.trim();
    if trimmed.is_empty() {
        return Vec::new();
    }

    let intent = parse_suggestion_intent(trimmed);
    let mut candidates: Vec<SuggestionItem> = Vec::new();
    let mut seen_urls: HashSet<String> = HashSet::new();

    // 1. Context-based discoveries (e.g. "Bleach" -> Number One, Asterisk, etc.)
    if let Some(ref ctx_name) = intent.detected_context {
        for cm in CONTEXT_MAPPINGS {
            if cm.franchise_name == ctx_name {
                for song in cm.songs {
                    if seen_urls.insert(song.url.to_string()) {
                        let score = score_suggestion(&intent.normalized_query, &intent, song)
                            .max(0.78);
                        candidates.push(SuggestionItem {
                            title: song.title.to_string(),
                            artist: song.artist.to_string(),
                            suggestion_type: "context".to_string(),
                            reason: format!("From {}", cm.franchise_name),
                            confidence: if score >= 0.85 { "strong".to_string() } else { "possible".to_string() },
                            score,
                            url: song.url.to_string(),
                            thumbnail: song.thumbnail.to_string(),
                            duration: song.duration,
                            context: song.context.map(|s| s.to_string()),
                        });
                    }
                }
            }
        }
    }

    // 2. Artist-focused discoveries (e.g. "Porter" -> Porter Robinson artist & top tracks)
    for ma in &intent.matched_artists {
        for artist in KNOWN_ARTISTS {
            if artist.canonical_name == ma.canonical_name {
                // Add artist card suggestion
                let art_url = format!("artist:{}", normalize_text(artist.canonical_name));
                if seen_urls.insert(art_url.clone()) {
                    candidates.push(SuggestionItem {
                        title: artist.canonical_name.to_string(),
                        artist: artist.genre.to_string(),
                        suggestion_type: "artist".to_string(),
                        reason: format!("Artist · {}", artist.genre),
                        confidence: "strong".to_string(),
                        score: 0.95,
                        url: art_url,
                        thumbnail: String::new(),
                        duration: 0.0,
                        context: Some(format!("Genre: {}", artist.genre)),
                    });
                }

                // Add top songs
                for song in artist.top_songs {
                    if seen_urls.insert(song.url.to_string()) {
                        let score = score_suggestion(&intent.normalized_query, &intent, song)
                            .max(0.80);
                        candidates.push(SuggestionItem {
                            title: song.title.to_string(),
                            artist: song.artist.to_string(),
                            suggestion_type: "artist".to_string(),
                            reason: format!("Popular track by {}", artist.canonical_name),
                            confidence: if score >= 0.85 { "strong".to_string() } else { "possible".to_string() },
                            score,
                            url: song.url.to_string(),
                            thumbnail: song.thumbnail.to_string(),
                            duration: song.duration,
                            context: song.context.map(|s| s.to_string()),
                        });
                    }
                }
            }
        }
    }

    // 3. Scan all canonical catalogs for matching titles or keywords
    for artist in KNOWN_ARTISTS {
        for song in artist.top_songs {
            if seen_urls.contains(song.url) {
                continue;
            }
            let score = score_suggestion(&intent.normalized_query, &intent, song);
            if score >= 0.50 {
                seen_urls.insert(song.url.to_string());
                let sug_type = if intent.is_version_focused {
                    "version"
                } else if score >= 0.85 {
                    "title"
                } else {
                    "keyword"
                };
                let conf = if score >= 0.82 {
                    "strong"
                } else if score >= 0.60 {
                    "possible"
                } else {
                    "weak"
                };
                candidates.push(SuggestionItem {
                    title: song.title.to_string(),
                    artist: song.artist.to_string(),
                    suggestion_type: sug_type.to_string(),
                    reason: if song.title.to_lowercase().contains(&intent.normalized_query) {
                        "Matching song title".to_string()
                    } else {
                        "Relevant music match".to_string()
                    },
                    confidence: conf.to_string(),
                    score,
                    url: song.url.to_string(),
                    thumbnail: song.thumbnail.to_string(),
                    duration: song.duration,
                    context: song.context.map(|s| s.to_string()),
                });
            }
        }
    }

    // Sort deterministically: score desc, confidence, title asc
    candidates.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.title.cmp(&b.title))
    });

    // Truncate to limit
    let max_results = if limit == 0 { 6 } else { limit };
    candidates.truncate(max_results);
    candidates
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bankai_intent() {
        let intent = parse_suggestion_intent("Number One Bankai");
        assert!(intent.is_context_focused);
        assert_eq!(intent.detected_context.as_deref(), Some("Bleach Soundtrack"));
    }

    #[test]
    fn test_porter_suggestions() {
        let results = get_search_suggestions("Porter", "audio", 6);
        assert!(!results.is_empty());
        assert!(results.iter().any(|r| r.artist.contains("Porter Robinson") || r.title == "Porter Robinson"));
    }

    #[test]
    fn test_bleach_context_discovery() {
        let results = get_search_suggestions("Bleach", "audio", 6);
        assert!(!results.is_empty());
        assert!(results.iter().any(|r| r.title.contains("Number One")));
    }
}
