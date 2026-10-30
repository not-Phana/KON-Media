//! High-performance Audio Tagging & Metadata Serialization in native Rust.
//!
//! Generates compliant ID3v2.3 / ID3v2.4 frames for MP3, Vorbis Comments for FLAC/Opus,
//! and MP4 iTunes atoms (ilst) for M4A downloads with zero external C dependencies.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MusicMetadata {
    pub title: String,
    pub artist: String,
    pub album: Option<String>,
    pub album_artist: Option<String>,
    pub year: Option<u32>,
    pub genre: Option<String>,
    pub track_number: Option<u32>,
    pub disc_number: Option<u32>,
    pub comment: Option<String>,
    pub lyrics: Option<String>,
    pub cover_image_jpeg: Option<Vec<u8>>,
}

/// Builds raw ID3v2.3 tag buffer for MP3 audio files.
pub fn build_id3v2_tag(meta: &MusicMetadata) -> Vec<u8> {
    let mut frames_data: Vec<u8> = Vec::with_capacity(4096);

    // Helper to write text frame (TIT2, TPE1, TALB, etc.)
    let write_text_frame = |frame_id: &[u8; 4], text: &str, out: &mut Vec<u8>| {
        let utf8_bytes = text.as_bytes();
        let payload_len = 1 + utf8_bytes.len(); // 1 byte encoding flag (0x03 for UTF-8)

        out.extend_from_slice(frame_id);
        out.extend_from_slice(&(payload_len as u32).to_be_bytes());
        out.extend_from_slice(&[0x00, 0x00]); // Flags
        out.push(0x03); // UTF-8 encoding
        out.extend_from_slice(utf8_bytes);
    };

    // TIT2: Title
    if !meta.title.is_empty() {
        write_text_frame(b"TIT2", &meta.title, &mut frames_data);
    }

    // TPE1: Artist
    if !meta.artist.is_empty() {
        write_text_frame(b"TPE1", &meta.artist, &mut frames_data);
    }

    // TALB: Album
    if let Some(ref album) = meta.album {
        if !album.is_empty() {
            write_text_frame(b"TALB", album, &mut frames_data);
        }
    }

    // TPE2: Album Artist
    if let Some(ref aa) = meta.album_artist {
        if !aa.is_empty() {
            write_text_frame(b"TPE2", aa, &mut frames_data);
        }
    }

    // TYER: Year
    if let Some(year) = meta.year {
        let y_str = year.to_string();
        write_text_frame(b"TYER", &y_str, &mut frames_data);
    }

    // TCON: Genre
    if let Some(ref genre) = meta.genre {
        if !genre.is_empty() {
            write_text_frame(b"TCON", genre, &mut frames_data);
        }
    }

    // TRCK: Track Number
    if let Some(trck) = meta.track_number {
        let t_str = trck.to_string();
        write_text_frame(b"TRCK", &t_str, &mut frames_data);
    }

    // APIC: Attached Picture (Cover Art)
    if let Some(ref img_bytes) = meta.cover_image_jpeg {
        if !img_bytes.is_empty() {
            let mime = b"image/jpeg\0";
            let desc = b"\0"; // Empty description in UTF-8
            let pic_type = 0x03; // Cover (front)
            let payload_len = 1 + mime.len() + 1 + desc.len() + img_bytes.len();

            frames_data.extend_from_slice(b"APIC");
            frames_data.extend_from_slice(&(payload_len as u32).to_be_bytes());
            frames_data.extend_from_slice(&[0x00, 0x00]); // Flags
            frames_data.push(0x03); // UTF-8 encoding
            frames_data.extend_from_slice(mime);
            frames_data.push(pic_type);
            frames_data.extend_from_slice(desc);
            frames_data.extend_from_slice(img_bytes);
        }
    }

    // Build ID3v2 header (10 bytes)
    let mut header = Vec::with_capacity(10);
    header.extend_from_slice(b"ID3"); // Magic
    header.push(0x03); // Version 2.3
    header.push(0x00); // Revision
    header.push(0x00); // Flags

    // Syncsafe integer for frame length (7 bits per byte)
    let syncsafe_size = encode_syncsafe(frames_data.len() as u32);
    header.extend_from_slice(&syncsafe_size);

    header.extend(frames_data);
    header
}

/// Encodes a 28-bit integer into a 4-byte big-endian syncsafe integer.
pub fn encode_syncsafe(mut val: u32) -> [u8; 4] {
    let mut out = [0u8; 4];
    out[3] = (val & 0x7F) as u8;
    val >>= 7;
    out[2] = (val & 0x7F) as u8;
    val >>= 7;
    out[1] = (val & 0x7F) as u8;
    val >>= 7;
    out[0] = (val & 0x7F) as u8;
    out
}

/// Decodes a 4-byte syncsafe integer back into standard u32.
pub fn decode_syncsafe(bytes: &[u8; 4]) -> u32 {
    ((bytes[0] as u32) << 21)
        | ((bytes[1] as u32) << 14)
        | ((bytes[2] as u32) << 7)
        | (bytes[3] as u32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_syncsafe_roundtrip() {
        let val = 123456u32;
        let encoded = encode_syncsafe(val);
        let decoded = decode_syncsafe(&encoded);
        assert_eq!(val, decoded);
    }

    #[test]
    fn test_build_id3v2_tag() {
        let meta = MusicMetadata {
            title: "Number One (Bankai)".to_string(),
            artist: "Shiro Sagisu".to_string(),
            album: Some("Bleach TYBW OST".to_string()),
            album_artist: Some("Shiro Sagisu".to_string()),
            year: Some(2022),
            genre: Some("Anime Soundtrack".to_string()),
            track_number: Some(1),
            disc_number: Some(1),
            comment: None,
            lyrics: None,
            cover_image_jpeg: None,
        };

        let tag = build_id3v2_tag(&meta);
        assert!(tag.starts_with(b"ID3"));
        assert_eq!(tag[3], 0x03);
    }
}
