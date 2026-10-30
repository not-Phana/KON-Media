//! High-performance Compressed Inverted Posting Lists & Track Indexer in native Rust.
//!
//! Implements compressed inverted posting lists using d-gap delta encoding
//! and Variable Byte (Varint) packing for sub-millisecond candidate lookup.

use std::collections::{BTreeMap, HashMap};
use serde::{Deserialize, Serialize};
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PostingItem {
    pub doc_id: u32,
    pub term_frequency: u16,
}

#[derive(Debug, Clone, Default)]
pub struct CompressedPostingList {
    pub compressed_bytes: Vec<u8>,
    pub document_count: usize,
    pub last_doc_id: u32,
}

impl CompressedPostingList {
    pub fn new() -> Self {
        Self::default()
    }

    /// Append a document ID and frequency using d-gap varint compression.
    pub fn append(&mut self, doc_id: u32, freq: u16) {
        let delta = if self.document_count == 0 {
            doc_id
        } else {
            doc_id.saturating_sub(self.last_doc_id)
        };

        encode_varint(delta, &mut self.compressed_bytes);
        encode_varint(freq as u32, &mut self.compressed_bytes);

        self.last_doc_id = doc_id;
        self.document_count += 1;
    }

    /// Decompress all postings into `(doc_id, term_frequency)` tuples.
    pub fn decompress(&self) -> Vec<PostingItem> {
        let mut results = Vec::with_capacity(self.document_count);
        let mut offset = 0usize;
        let mut current_doc = 0u32;

        while offset < self.compressed_bytes.len() {
            let (delta, bytes_read1) = decode_varint(&self.compressed_bytes[offset..]);
            offset += bytes_read1;

            let (freq, bytes_read2) = decode_varint(&self.compressed_bytes[offset..]);
            offset += bytes_read2;

            current_doc += delta;
            results.push(PostingItem {
                doc_id: current_doc,
                term_frequency: freq as u16,
            });
        }

        results
    }
}

/// Variable-Byte (Varint) unsigned 32-bit integer encoder.
pub fn encode_varint(mut val: u32, out: &mut Vec<u8>) {
    while val >= 0x80 {
        out.push((val & 0x7F | 0x80) as u8);
        val >>= 7;
    }
    out.push(val as u8);
}

/// Variable-Byte (Varint) unsigned 32-bit integer decoder.
pub fn decode_varint(bytes: &[u8]) -> (u32, usize) {
    let mut val = 0u32;
    let mut shift = 0;
    let mut read = 0usize;

    for &b in bytes {
        read += 1;
        val |= ((b & 0x7F) as u32) << shift;
        if (b & 0x80) == 0 {
            break;
        }
        shift += 7;
    }

    (val, read)
}

/// Inverted Index mapping tokens to compressed posting lists.
pub struct CompressedInvertedIndex {
    term_dict: HashMap<String, CompressedPostingList>,
    doc_registry: BTreeMap<u32, String>, // doc_id -> title
    next_doc_id: u32,
}

impl CompressedInvertedIndex {
    pub fn new() -> Self {
        Self {
            term_dict: HashMap::new(),
            doc_registry: BTreeMap::new(),
            next_doc_id: 1,
        }
    }

    pub fn index_document(&mut self, text: &str) -> u32 {
        let doc_id = self.next_doc_id;
        self.next_doc_id += 1;

        let norm = normalize_text(text);
        let tokens: Vec<&str> = norm.split_whitespace().collect();

        let mut term_counts: HashMap<&str, u16> = HashMap::new();
        for t in tokens {
            *term_counts.entry(t).or_insert(0) += 1;
        }

        for (term, count) in term_counts {
            self.term_dict
                .entry(term.to_string())
                .or_insert_with(CompressedPostingList::new)
                .append(doc_id, count);
        }

        self.doc_registry.insert(doc_id, text.to_string());
        doc_id
    }

    /// Retrieve document IDs that match ALL query tokens (AND query).
    pub fn search_boolean_and(&self, query: &str) -> Vec<u32> {
        let norm = normalize_text(query);
        let q_tokens: Vec<&str> = norm.split_whitespace().collect();
        if q_tokens.is_empty() {
            return Vec::new();
        }

        // Gather posting lists
        let mut lists: Vec<Vec<PostingItem>> = Vec::new();
        for &tok in &q_tokens {
            if let Some(cpl) = self.term_dict.get(tok) {
                lists.push(cpl.decompress());
            } else {
                return Vec::new(); // Token missing -> empty intersection
            }
        }

        // Sort by list length ascending for fast intersection
        lists.sort_by_key(|l| l.len());

        let mut candidate_ids: Vec<u32> = lists[0].iter().map(|p| p.doc_id).collect();

        for other_list in &lists[1..] {
            let other_set: std::collections::HashSet<u32> = other_list.iter().map(|p| p.doc_id).collect();
            candidate_ids.retain(|id| other_set.contains(id));
            if candidate_ids.is_empty() {
                break;
            }
        }

        candidate_ids
    }

    pub fn get_document_title(&self, doc_id: u32) -> Option<&str> {
        self.doc_registry.get(&doc_id).map(|s| s.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_varint_compression_roundtrip() {
        let numbers = vec![1, 127, 128, 300, 16384, 1000000];
        let mut buf = Vec::new();

        for &n in &numbers {
            encode_varint(n, &mut buf);
        }

        let mut offset = 0;
        let mut decoded = Vec::new();
        while offset < buf.len() {
            let (val, read) = decode_varint(&buf[offset..]);
            decoded.push(val);
            offset += read;
        }

        assert_eq!(numbers, decoded);
    }

    #[test]
    fn test_compressed_posting_list() {
        let mut cpl = CompressedPostingList::new();
        cpl.append(10, 2);
        cpl.append(15, 1);
        cpl.append(22, 5);

        let items = cpl.decompress();
        assert_eq!(items.len(), 3);
        assert_eq!(items[0].doc_id, 10);
        assert_eq!(items[1].doc_id, 15);
        assert_eq!(items[2].doc_id, 22);
    }

    #[test]
    fn test_inverted_index_and_search() {
        let mut idx = CompressedInvertedIndex::new();
        let id1 = idx.index_document("Bleach Number One Bankai Theme");
        let _id2 = idx.index_document("One Piece We Are Hiroshi Kitadani");
        let id3 = idx.index_document("Bleach Battle Theme On The Precipice of Defeat");

        let hits = idx.search_boolean_and("Bleach Theme");
        assert_eq!(hits.len(), 2);
        assert!(hits.contains(&id1));
        assert!(hits.contains(&id3));
    }
}
