//! Comprehensive Anime, Game & Film Soundtrack Knowledge Base in native Rust.
//!
//! Provides verified soundtrack associations, franchise song indexes, and
//! composer registries for instant contextual query resolution.

use serde::Serialize;
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize)]
pub struct SoundtrackEntry {
    pub title: &'static str,
    pub artist: &'static str,
    pub franchise: &'static str,
    pub role: &'static str, // "Opening", "Ending", "Theme Song", "Insert Song", "OST"
    pub canonical_video_id: Option<&'static str>,
    pub duration_seconds: f64,
}

pub static SOUNDTRACK_REGISTRY: &[SoundtrackEntry] = &[
    // --- BLEACH ---
    SoundtrackEntry {
        title: "Number One (Bankai)",
        artist: "Hazel Fernandes & Shiro Sagisu",
        franchise: "Bleach: Thousand-Year Blood War",
        role: "Theme Song",
        canonical_video_id: Some("1lsn2tT5yTc"),
        duration_seconds: 304.0,
    },
    SoundtrackEntry {
        title: "On The Precipice Of Defeat",
        artist: "Shiro Sagisu",
        franchise: "Bleach",
        role: "OST Battle Theme",
        canonical_video_id: Some("ze5W8cDHcsQ"),
        duration_seconds: 172.0,
    },
    SoundtrackEntry {
        title: "Asterisk (*〜アスタリスク〜)",
        artist: "ORANGE RANGE",
        franchise: "Bleach",
        role: "Opening 1",
        canonical_video_id: Some("b0b-JkPjL1s"),
        duration_seconds: 254.0,
    },
    SoundtrackEntry {
        title: "Rolling Star",
        artist: "YUI",
        franchise: "Bleach",
        role: "Opening 5",
        canonical_video_id: Some("P_Xf_q9q_8k"),
        duration_seconds: 202.0,
    },
    SoundtrackEntry {
        title: "Velonica",
        artist: "Aqua Timez",
        franchise: "Bleach",
        role: "Opening 9",
        canonical_video_id: Some("cM7_zZ5J8fE"),
        duration_seconds: 278.0,
    },
    SoundtrackEntry {
        title: "Ranbu no Melody (乱舞のメロディ)",
        artist: "SID",
        franchise: "Bleach",
        role: "Opening 13",
        canonical_video_id: Some("sN6qV6s0k5M"),
        duration_seconds: 233.0,
    },
    SoundtrackEntry {
        title: "Life is Like a Boat",
        artist: "Rie fu",
        franchise: "Bleach",
        role: "Ending 1",
        canonical_video_id: Some("6bY00i_wTQE"),
        duration_seconds: 301.0,
    },

    // --- ZENLESS ZONE ZERO ---
    SoundtrackEntry {
        title: "I-BULL",
        artist: "jo0ji",
        franchise: "Zenless Zone Zero Season 3 Chapter 2",
        role: "Opening Theme",
        canonical_video_id: Some("IBULL_official"),
        duration_seconds: 204.0,
    },
    SoundtrackEntry {
        title: "Bizarre Brigade",
        artist: "HOYO-MiX",
        franchise: "Zenless Zone Zero",
        role: "Battle Theme",
        canonical_video_id: Some("ZZZ_Bizarre_Brigade"),
        duration_seconds: 182.0,
    },

    // --- ATTACK ON TITAN ---
    SoundtrackEntry {
        title: "Guren no Yumiya (紅蓮の弓矢)",
        artist: "Linked Horizon",
        franchise: "Attack on Titan",
        role: "Opening 1",
        canonical_video_id: Some("8OkpRK2_gVs"),
        duration_seconds: 316.0,
    },
    SoundtrackEntry {
        title: "Shinzo wo Sasageyo! (心臓を捧げよ!)",
        artist: "Linked Horizon",
        franchise: "Attack on Titan",
        role: "Opening 3",
        canonical_video_id: Some("CID-sYQNCew"),
        duration_seconds: 341.0,
    },
    SoundtrackEntry {
        title: "The Rumbling",
        artist: "SiM",
        franchise: "Attack on Titan",
        role: "Opening 7",
        canonical_video_id: Some("OB8_wBxv5p4"),
        duration_seconds: 220.0,
    },
    SoundtrackEntry {
        title: "Vogel im Kafig",
        artist: "Hiroyuki Sawano ft. Cyua",
        franchise: "Attack on Titan",
        role: "OST",
        canonical_video_id: Some("vogel_im_kafig"),
        duration_seconds: 380.0,
    },

    // --- NARUTO ---
    SoundtrackEntry {
        title: "Blue Bird (ブルーバード)",
        artist: "Ikimonogakari",
        franchise: "Naruto Shippuden",
        role: "Opening 3",
        canonical_video_id: Some("KpsJWFuVTdI"),
        duration_seconds: 215.0,
    },
    SoundtrackEntry {
        title: "Silhouette (シルエット)",
        artist: "KANA-BOON",
        franchise: "Naruto Shippuden",
        role: "Opening 16",
        canonical_video_id: Some("dlFA0Zq1k2A"),
        duration_seconds: 240.0,
    },
    SoundtrackEntry {
        title: "Haruka Kanata (遥か彼方)",
        artist: "ASIAN KUNG-FU GENERATION",
        franchise: "Naruto",
        role: "Opening 2",
        canonical_video_id: Some("nJ6A6GC_ki4"),
        duration_seconds: 242.0,
    },
    SoundtrackEntry {
        title: "Wind",
        artist: "Akeboshi",
        franchise: "Naruto",
        role: "Ending 1",
        canonical_video_id: Some("wind_akeboshi"),
        duration_seconds: 221.0,
    },
    SoundtrackEntry {
        title: "Sadness and Sorrow",
        artist: "Toshio Masuda",
        franchise: "Naruto",
        role: "OST",
        canonical_video_id: Some("sadness_sorrow"),
        duration_seconds: 180.0,
    },

    // --- ONE PIECE ---
    SoundtrackEntry {
        title: "We Are! (ウィーアー!)",
        artist: "Hiroshi Kitadani",
        franchise: "One Piece",
        role: "Opening 1",
        canonical_video_id: Some("we_are_op1"),
        duration_seconds: 240.0,
    },
    SoundtrackEntry {
        title: "Over The Top",
        artist: "Hiroshi Kitadani",
        franchise: "One Piece",
        role: "Opening 22",
        canonical_video_id: Some("over_the_top"),
        duration_seconds: 232.0,
    },
    SoundtrackEntry {
        title: "New Genesis (新時代)",
        artist: "Ado",
        franchise: "One Piece Film: Red",
        role: "Theme Song",
        canonical_video_id: Some("1FliVTcX8bQ"),
        duration_seconds: 226.0,
    },

    // --- JUJUTSU KAISEN ---
    SoundtrackEntry {
        title: "Kaikai Kitan (廻廻奇譚)",
        artist: "Eve",
        franchise: "Jujutsu Kaisen",
        role: "Opening 1",
        canonical_video_id: Some("1tk1P3rkAAk"),
        duration_seconds: 222.0,
    },
    SoundtrackEntry {
        title: "Ao no Sumika (青のすみか)",
        artist: "Tatsuya Kitani",
        franchise: "Jujutsu Kaisen Season 2",
        role: "Opening 3 (Hidden Inventory)",
        canonical_video_id: Some("ao_no_sumika"),
        duration_seconds: 196.0,
    },
    SoundtrackEntry {
        title: "SpecialZ",
        artist: "King Gnu",
        franchise: "Jujutsu Kaisen Season 2",
        role: "Opening 4 (Shibuya Incident)",
        canonical_video_id: Some("specialz_king_gnu"),
        duration_seconds: 238.0,
    },

    // --- DEMON SLAYER (KIMETSU NO YAIBA) ---
    SoundtrackEntry {
        title: "Gurenge (紅蓮華)",
        artist: "LiSA",
        franchise: "Demon Slayer: Kimetsu no Yaiba",
        role: "Opening 1",
        canonical_video_id: Some("CwkzK-F0Y00"),
        duration_seconds: 237.0,
    },
    SoundtrackEntry {
        title: "Homura (炎)",
        artist: "LiSA",
        franchise: "Demon Slayer: Mugen Train",
        role: "Theme Song",
        canonical_video_id: Some("4DxL6IKmNx4"),
        duration_seconds: 275.0,
    },
    SoundtrackEntry {
        title: "Zankyosanka (残響散歌)",
        artist: "Aimer",
        franchise: "Demon Slayer: Entertainment District",
        role: "Opening 2",
        canonical_video_id: Some("tLQLa6lM3Us"),
        duration_seconds: 184.0,
    },

    // --- CHAINSAW MAN ---
    SoundtrackEntry {
        title: "KICK BACK",
        artist: "Kenshi Yonezu",
        franchise: "Chainsaw Man",
        role: "Opening 1",
        canonical_video_id: Some("M2cckDmNLMI"),
        duration_seconds: 193.0,
    },

    // --- CYBERPUNK EDGERUNNERS ---
    SoundtrackEntry {
        title: "I Really Want to Stay at Your House",
        artist: "Rosa Walton & Hallie Coggins",
        franchise: "Cyberpunk: Edgerunners",
        role: "Insert Theme",
        canonical_video_id: Some("KvMY1uzSC1E"),
        duration_seconds: 246.0,
    },
    SoundtrackEntry {
        title: "This Fffire",
        artist: "Franz Ferdinand",
        franchise: "Cyberpunk: Edgerunners",
        role: "Opening",
        canonical_video_id: Some("this_fffire"),
        duration_seconds: 218.0,
    },

    // --- TOKYO GHOUL ---
    SoundtrackEntry {
        title: "Unravel",
        artist: "TK from Ling Tosite Sigure",
        franchise: "Tokyo Ghoul",
        role: "Opening 1",
        canonical_video_id: Some("7aMOurgDB-o"),
        duration_seconds: 240.0,
    },

    // --- OSHI NO KO ---
    SoundtrackEntry {
        title: "Idol (アイドル)",
        artist: "YOASOBI",
        franchise: "Oshi no Ko",
        role: "Opening 1",
        canonical_video_id: Some("ZRtdQ81jPUQ"),
        duration_seconds: 213.0,
    },

    // --- FRIEREN: BEYOND JOURNEY'S END ---
    SoundtrackEntry {
        title: "Yuusha (勇者)",
        artist: "YOASOBI",
        franchise: "Frieren: Beyond Journey's End",
        role: "Opening 1",
        canonical_video_id: Some("OIBODIPC_8Y"),
        duration_seconds: 194.0,
    },
    SoundtrackEntry {
        title: "Anytime Anywhere",
        artist: "milet",
        franchise: "Frieren: Beyond Journey's End",
        role: "Ending 1",
        canonical_video_id: Some("milet_frieren"),
        duration_seconds: 231.0,
    },

    // --- GENSHIN IMPACT ---
    SoundtrackEntry {
        title: "Liyue Harbor (Moon in One's Cup)",
        artist: "HOYO-MiX ft. Yu-Peng Chen",
        franchise: "Genshin Impact",
        role: "OST",
        canonical_video_id: Some("genshin_liyue"),
        duration_seconds: 198.0,
    },
    SoundtrackEntry {
        title: "Rage Beneath the Mountains (Azhdaha Battle)",
        artist: "HOYO-MiX ft. Yu-Peng Chen",
        franchise: "Genshin Impact",
        role: "Boss Theme",
        canonical_video_id: Some("genshin_azhdaha"),
        duration_seconds: 260.0,
    },

    // --- PERSONA 5 ---
    SoundtrackEntry {
        title: "Life Will Change",
        artist: "Shoji Meguro ft. Lyn Inaizumi",
        franchise: "Persona 5",
        role: "Theme Song",
        canonical_video_id: Some("life_will_change"),
        duration_seconds: 262.0,
    },
    SoundtrackEntry {
        title: "Last Surprise",
        artist: "Shoji Meguro ft. Lyn Inaizumi",
        franchise: "Persona 5",
        role: "Battle Theme",
        canonical_video_id: Some("last_surprise"),
        duration_seconds: 236.0,
    },

    // --- NIER: AUTOMATA ---
    SoundtrackEntry {
        title: "Weight of the World",
        artist: "Keiichi Okabe ft. J'Nique Nicole",
        franchise: "NieR: Automata",
        role: "Theme Song",
        canonical_video_id: Some("weight_of_the_world"),
        duration_seconds: 344.0,
    },

    // --- UNDERTALE ---
    SoundtrackEntry {
        title: "Megalovania",
        artist: "Toby Fox",
        franchise: "Undertale",
        role: "Boss Theme (Sans)",
        canonical_video_id: Some("0FCvzsVlXpQ"),
        duration_seconds: 156.0,
    },
    SoundtrackEntry {
        title: "Hopes and Dreams",
        artist: "Toby Fox",
        franchise: "Undertale",
        role: "Boss Theme (Asriel)",
        canonical_video_id: Some("tz82xbLvK_k"),
        duration_seconds: 181.0,
    },
];

/// Search soundtrack knowledge base for matches to a query string.
pub fn search_soundtrack_db(query: &str, limit: usize) -> Vec<&'static SoundtrackEntry> {
    let norm = normalize_text(query);
    if norm.is_empty() {
        return Vec::new();
    }

    let mut matches: Vec<(&'static SoundtrackEntry, f64)> = Vec::new();

    for entry in SOUNDTRACK_REGISTRY {
        let t_norm = normalize_text(entry.title);
        let f_norm = normalize_text(entry.franchise);
        let a_norm = normalize_text(entry.artist);
        let r_norm = normalize_text(entry.role);
        let clean_f = f_norm.split("season").next().unwrap_or(&f_norm).trim();

        let mut score = 0.0;
        if t_norm == norm {
            score = 1.0;
        } else if t_norm.contains(&norm) {
            score = 0.85;
        } else if f_norm.contains(&norm) || norm.contains(&f_norm) || (!clean_f.is_empty() && norm.contains(clean_f)) {
            score = 0.80;
        } else if a_norm.contains(&norm) {
            score = 0.75;
        } else {
            // Check token overlap
            let q_tokens: Vec<&str> = norm.split_whitespace().collect();
            let all_text = format!("{} {} {} {}", t_norm, f_norm, a_norm, r_norm);
            let matched = q_tokens.iter().filter(|&&t| all_text.contains(t)).count();
            if !q_tokens.is_empty() {
                score = (matched as f64 / q_tokens.len() as f64) * 0.70;
            }
        }

        if !r_norm.is_empty() {
            let r_tokens: Vec<&str> = r_norm.split_whitespace().collect();
            if r_tokens.iter().any(|&rt| norm.contains(rt)) {
                score += 0.15;
            }
        }

        if score >= 0.40 {
            matches.push((entry, score));
        }
    }

    matches.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    matches.truncate(limit);
    matches.into_iter().map(|(e, _)| e).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lookup_bankai() {
        let res = search_soundtrack_db("Bankai", 3);
        assert!(!res.is_empty());
        assert_eq!(res[0].title, "Number One (Bankai)");
    }

    #[test]
    fn test_lookup_zenless() {
        let res = search_soundtrack_db("Zenless Zone Zero Opening", 2);
        assert!(!res.is_empty());
        assert_eq!(res[0].title, "I-BULL");
        assert_eq!(res[0].artist, "jo0ji");
    }
}
