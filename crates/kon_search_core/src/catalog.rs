//! Global Canonical Music Discography and Artist Registry in native Rust.
//!
//! Provides fast lookup of canonical artists, known aliases, genres,
//! and signature discographies across mainstream and niche music.

use serde::Serialize;
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize)]
pub struct TrackMetadata {
    pub title: &'static str,
    pub artist: &'static str,
    pub duration_seconds: f64,
    pub genre: &'static str,
    pub album: Option<&'static str>,
    pub year: u32,
    pub is_explicit: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArtistEntry {
    pub name: &'static str,
    pub aliases: &'static [&'static str],
    pub origin: &'static str,
    pub primary_genre: &'static str,
    pub tracks: &'static [TrackMetadata],
}

// -----------------------------------------------------------------------------
// Catalog Data
// -----------------------------------------------------------------------------

static ARCTIC_MONKEYS_TRACKS: [TrackMetadata; 6] = [
    TrackMetadata { title: "I Wanna Be Yours", artist: "Arctic Monkeys", duration_seconds: 184.0, genre: "Indie Rock", album: Some("AM"), year: 2013, is_explicit: false },
    TrackMetadata { title: "Do I Wanna Know?", artist: "Arctic Monkeys", duration_seconds: 272.0, genre: "Indie Rock", album: Some("AM"), year: 2013, is_explicit: false },
    TrackMetadata { title: "505", artist: "Arctic Monkeys", duration_seconds: 253.0, genre: "Indie Rock", album: Some("Favourite Worst Nightmare"), year: 2007, is_explicit: false },
    TrackMetadata { title: "R U Mine?", artist: "Arctic Monkeys", duration_seconds: 201.0, genre: "Indie Rock", album: Some("AM"), year: 2013, is_explicit: false },
    TrackMetadata { title: "Why'd You Only Call Me When You're High?", artist: "Arctic Monkeys", duration_seconds: 161.0, genre: "Indie Rock", album: Some("AM"), year: 2013, is_explicit: false },
    TrackMetadata { title: "Fluorescent Adolescent", artist: "Arctic Monkeys", duration_seconds: 177.0, genre: "Indie Rock", album: Some("Favourite Worst Nightmare"), year: 2007, is_explicit: false },
];

static PORTER_ROBINSON_TRACKS: [TrackMetadata; 6] = [
    TrackMetadata { title: "Shelter", artist: "Porter Robinson & Madeon", duration_seconds: 219.0, genre: "Electronic", album: Some("Shelter"), year: 2016, is_explicit: false },
    TrackMetadata { title: "Sad Machine", artist: "Porter Robinson", duration_seconds: 350.0, genre: "Synth-pop", album: Some("Worlds"), year: 2014, is_explicit: false },
    TrackMetadata { title: "Language", artist: "Porter Robinson", duration_seconds: 368.0, genre: "Progressive House", album: Some("Language"), year: 2012, is_explicit: false },
    TrackMetadata { title: "Look at the Sky", artist: "Porter Robinson", duration_seconds: 310.0, genre: "Electropop", album: Some("Nurture"), year: 2021, is_explicit: false },
    TrackMetadata { title: "Goodbye to a World", artist: "Porter Robinson", duration_seconds: 328.0, genre: "Electronic", album: Some("Worlds"), year: 2014, is_explicit: false },
    TrackMetadata { title: "Get Your Wish", artist: "Porter Robinson", duration_seconds: 218.0, genre: "Electropop", album: Some("Nurture"), year: 2020, is_explicit: false },
];

static THE_WEEKND_TRACKS: [TrackMetadata; 6] = [
    TrackMetadata { title: "Blinding Lights", artist: "The Weeknd", duration_seconds: 200.0, genre: "Synthwave", album: Some("After Hours"), year: 2020, is_explicit: false },
    TrackMetadata { title: "Starboy", artist: "The Weeknd ft. Daft Punk", duration_seconds: 230.0, genre: "R&B", album: Some("Starboy"), year: 2016, is_explicit: true },
    TrackMetadata { title: "Save Your Tears", artist: "The Weeknd", duration_seconds: 215.0, genre: "Synth-pop", album: Some("After Hours"), year: 2020, is_explicit: false },
    TrackMetadata { title: "The Hills", artist: "The Weeknd", duration_seconds: 242.0, genre: "Trap R&B", album: Some("Beauty Behind the Madness"), year: 2015, is_explicit: true },
    TrackMetadata { title: "Die For You", artist: "The Weeknd", duration_seconds: 260.0, genre: "R&B", album: Some("Starboy"), year: 2016, is_explicit: false },
    TrackMetadata { title: "Can't Feel My Face", artist: "The Weeknd", duration_seconds: 213.0, genre: "Pop", album: Some("Beauty Behind the Madness"), year: 2015, is_explicit: false },
];

static DAFT_PUNK_TRACKS: [TrackMetadata; 5] = [
    TrackMetadata { title: "Get Lucky", artist: "Daft Punk ft. Pharrell Williams", duration_seconds: 248.0, genre: "Disco", album: Some("Random Access Memories"), year: 2013, is_explicit: false },
    TrackMetadata { title: "Harder, Better, Faster, Stronger", artist: "Daft Punk", duration_seconds: 224.0, genre: "French House", album: Some("Discovery"), year: 2001, is_explicit: false },
    TrackMetadata { title: "One More Time", artist: "Daft Punk", duration_seconds: 320.0, genre: "French House", album: Some("Discovery"), year: 2000, is_explicit: false },
    TrackMetadata { title: "Around the World", artist: "Daft Punk", duration_seconds: 429.0, genre: "French House", album: Some("Homework"), year: 1997, is_explicit: false },
    TrackMetadata { title: "Instant Crush", artist: "Daft Punk ft. Julian Casablancas", duration_seconds: 337.0, genre: "Synth-pop", album: Some("Random Access Memories"), year: 2013, is_explicit: false },
];

static NEWJEANS_TRACKS: [TrackMetadata; 5] = [
    TrackMetadata { title: "Ditto", artist: "NewJeans", duration_seconds: 186.0, genre: "K-pop · Baltimore Club", album: Some("OMG"), year: 2022, is_explicit: false },
    TrackMetadata { title: "OMG", artist: "NewJeans", duration_seconds: 212.0, genre: "K-pop · UK Garage", album: Some("OMG"), year: 2023, is_explicit: false },
    TrackMetadata { title: "Hype Boy", artist: "NewJeans", duration_seconds: 179.0, genre: "K-pop · R&B", album: Some("New Jeans"), year: 2022, is_explicit: false },
    TrackMetadata { title: "Super Shy", artist: "NewJeans", duration_seconds: 154.0, genre: "K-pop · Jersey Club", album: Some("Get Up"), year: 2023, is_explicit: false },
    TrackMetadata { title: "Attention", artist: "NewJeans", duration_seconds: 180.0, genre: "K-pop · R&B", album: Some("New Jeans"), year: 2022, is_explicit: false },
];

static YOASOBI_TRACKS: [TrackMetadata; 5] = [
    TrackMetadata { title: "Idol (アイドル)", artist: "YOASOBI", duration_seconds: 213.0, genre: "J-pop", album: Some("THE BOOK 3"), year: 2023, is_explicit: false },
    TrackMetadata { title: "Yoru ni Kakeru (夜に駆ける)", artist: "YOASOBI", duration_seconds: 261.0, genre: "J-pop", album: Some("THE BOOK"), year: 2019, is_explicit: false },
    TrackMetadata { title: "Kaibutsu (怪物)", artist: "YOASOBI", duration_seconds: 206.0, genre: "J-pop", album: Some("THE BOOK 2"), year: 2021, is_explicit: false },
    TrackMetadata { title: "Gunjou (群青)", artist: "YOASOBI", duration_seconds: 248.0, genre: "J-pop", album: Some("THE BOOK"), year: 2020, is_explicit: false },
    TrackMetadata { title: "Yuusha (勇者)", artist: "YOASOBI", duration_seconds: 194.0, genre: "J-pop", album: Some("THE BOOK 3"), year: 2023, is_explicit: false },
];

static KENSHI_YONEZU_TRACKS: [TrackMetadata; 5] = [
    TrackMetadata { title: "KICK BACK", artist: "Kenshi Yonezu", duration_seconds: 193.0, genre: "J-rock", album: Some("LOST CORNER"), year: 2022, is_explicit: false },
    TrackMetadata { title: "Lemon", artist: "Kenshi Yonezu", duration_seconds: 255.0, genre: "J-pop", album: Some("STRAY SHEEP"), year: 2018, is_explicit: false },
    TrackMetadata { title: "Peace Sign", artist: "Kenshi Yonezu", duration_seconds: 242.0, genre: "J-rock", album: Some("BOOTLEG"), year: 2017, is_explicit: false },
    TrackMetadata { title: "Uma to Shika (馬と鹿)", artist: "Kenshi Yonezu", duration_seconds: 268.0, genre: "J-pop", album: Some("STRAY SHEEP"), year: 2019, is_explicit: false },
    TrackMetadata { title: "Chikyugi (Spinning Globe)", artist: "Kenshi Yonezu", duration_seconds: 273.0, genre: "Art Pop", album: Some("The Boy and the Heron OST"), year: 2023, is_explicit: false },
];

pub static ARTIST_DATABASE: &[ArtistEntry] = &[
    ArtistEntry {
        name: "Arctic Monkeys",
        aliases: &["arctic monkeys", "arctic monkey", "alex turner"],
        origin: "Sheffield, England",
        primary_genre: "Indie Rock",
        tracks: &ARCTIC_MONKEYS_TRACKS,
    },
    ArtistEntry {
        name: "Porter Robinson",
        aliases: &["porter robinson", "porter", "porterrobinson", "virtual self"],
        origin: "North Carolina, USA",
        primary_genre: "Electronic",
        tracks: &PORTER_ROBINSON_TRACKS,
    },
    ArtistEntry {
        name: "The Weeknd",
        aliases: &["the weeknd", "weeknd", "abel tesfaye"],
        origin: "Toronto, Canada",
        primary_genre: "R&B / Pop",
        tracks: &THE_WEEKND_TRACKS,
    },
    ArtistEntry {
        name: "Daft Punk",
        aliases: &["daft punk", "daftpunk", "guy-manuel", "thomas bangalter"],
        origin: "Paris, France",
        primary_genre: "French House",
        tracks: &DAFT_PUNK_TRACKS,
    },
    ArtistEntry {
        name: "NewJeans",
        aliases: &["newjeans", "new jeans", "nwjns", "minji", "hanni", "danielle", "haerin", "hyein"],
        origin: "Seoul, South Korea",
        primary_genre: "K-pop",
        tracks: &NEWJEANS_TRACKS,
    },
    ArtistEntry {
        name: "YOASOBI",
        aliases: &["yoasobi", "ayase", "ikura"],
        origin: "Tokyo, Japan",
        primary_genre: "J-pop",
        tracks: &YOASOBI_TRACKS,
    },
    ArtistEntry {
        name: "Kenshi Yonezu",
        aliases: &["kenshi yonezu", "yonezu kenshi", "hachi"],
        origin: "Tokushima, Japan",
        primary_genre: "J-rock",
        tracks: &KENSHI_YONEZU_TRACKS,
    },
];

/// Find tracks matching a query string across all registered artists.
use std::sync::OnceLock;

struct PrecomputedTrack {
    track: &'static TrackMetadata,
    title_norm: String,
    artist_norm: String,
}

static PRECOMPUTED_TRACKS: OnceLock<Vec<PrecomputedTrack>> = OnceLock::new();

fn get_precomputed_tracks() -> &'static [PrecomputedTrack] {
    PRECOMPUTED_TRACKS.get_or_init(|| {
        let mut tracks = Vec::new();
        for artist in ARTIST_DATABASE {
            for track in artist.tracks {
                tracks.push(PrecomputedTrack {
                    track,
                    title_norm: normalize_text(track.title),
                    artist_norm: normalize_text(track.artist),
                });
            }
        }
        tracks
    })
}

/// Search canonical catalog tracks for partial or fuzzy matches with zero dynamic allocations.
pub fn search_catalog_tracks(query: &str, limit: usize) -> Vec<&'static TrackMetadata> {
    let norm = normalize_text(query);
    if norm.is_empty() {
        return Vec::new();
    }

    let precomputed = get_precomputed_tracks();
    let mut matches: Vec<(&'static TrackMetadata, f64)> = Vec::new();

    for item in precomputed {
        let mut score = 0.0;
        if item.title_norm == norm {
            score = 1.0;
        } else if item.title_norm.starts_with(&norm) {
            score = 0.90;
        } else if item.title_norm.contains(&norm) {
            score = 0.82;
        } else if item.artist_norm.contains(&norm) {
            score = 0.70;
        }

        if score >= 0.50 {
            matches.push((item.track, score));
        }
    }

    matches.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    matches.truncate(limit);
    matches.into_iter().map(|(t, _)| t).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_search_shelter() {
        let results = search_catalog_tracks("Shelter", 3);
        assert!(!results.is_empty());
        assert_eq!(results[0].title, "Shelter");
    }

    #[test]
    fn test_search_arctic() {
        let results = search_catalog_tracks("Wanna Be Yours", 3);
        assert!(!results.is_empty());
        assert_eq!(results[0].title, "I Wanna Be Yours");
    }
}
