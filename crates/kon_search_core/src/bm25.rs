//! High-performance Okapi BM25 Lexical Index and Scorer in native Rust.
//!
//! Provides deterministic term-weighting retrieval with document-length
//! normalization, inverted indexing, and sub-millisecond query evaluation.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use crate::normalization::normalize_text;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexedDocument {
    pub id: String,
    pub title: String,
    pub artist: String,
    pub context: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BM25SearchResult {
    pub doc_id: String,
    pub score: f64,
}

pub struct BM25Index {
    k1: f64,
    b: f64,
    documents: HashMap<String, IndexedDocument>,
    doc_lengths: HashMap<String, usize>,
    inverted_index: HashMap<String, Vec<(String, usize)>>, // token -> [(doc_id, tf)]
    total_doc_length: usize,
}

impl BM25Index {
    pub fn new(k1: f64, b: f64) -> Self {
        Self {
            k1,
            b,
            documents: HashMap::new(),
            doc_lengths: HashMap::new(),
            inverted_index: HashMap::new(),
            total_doc_length: 0,
        }
    }

    pub fn default_params() -> Self {
        Self::new(1.2, 0.75)
    }

    pub fn add_document(&mut self, doc: IndexedDocument) {
        let text = format!("{} {} {}", doc.title, doc.artist, doc.context.as_deref().unwrap_or(""));
        let norm = normalize_text(&text);
        let tokens: Vec<String> = norm.split_whitespace().map(|s| s.to_string()).collect();
        let doc_len = tokens.len();

        let mut term_counts: HashMap<String, usize> = HashMap::new();
        for t in tokens {
            *term_counts.entry(t).or_insert(0) += 1;
        }

        for (term, count) in term_counts {
            self.inverted_index
                .entry(term)
                .or_insert_with(Vec::new)
                .push((doc.id.clone(), count));
        }

        self.total_doc_length += doc_len;
        self.doc_lengths.insert(doc.id.clone(), doc_len);
        self.documents.insert(doc.id.clone(), doc);
    }

    pub fn search(&self, query: &str, limit: usize) -> Vec<BM25SearchResult> {
        let norm_query = normalize_text(query);
        let query_tokens: Vec<&str> = norm_query.split_whitespace().collect();
        if query_tokens.is_empty() || self.documents.is_empty() {
            return Vec::new();
        }

        let n_docs = self.documents.len() as f64;
        let avg_dl = self.total_doc_length as f64 / n_docs.max(1.0);

        let mut doc_scores: HashMap<String, f64> = HashMap::new();

        for q_tok in query_tokens {
            if let Some(postings) = self.inverted_index.get(q_tok) {
                let df = postings.len() as f64;
                // Standard Okapi BM25 IDF
                let idf = ((n_docs - df + 0.5) / (df + 0.5) + 1.0).ln();

                for (doc_id, tf) in postings {
                    let tf_val = *tf as f64;
                    let dl = *self.doc_lengths.get(doc_id).unwrap_or(&1) as f64;

                    let numerator = tf_val * (self.k1 + 1.0);
                    let denominator = tf_val + self.k1 * (1.0 - self.b + self.b * (dl / avg_dl));

                    let term_score = idf * (numerator / denominator);
                    *doc_scores.entry(doc_id.clone()).or_insert(0.0) += term_score;
                }
            }
        }

        let mut results: Vec<BM25SearchResult> = doc_scores
            .into_iter()
            .map(|(doc_id, score)| BM25SearchResult { doc_id, score })
            .collect();

        results.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        results.truncate(limit);
        results
    }

    pub fn len(&self) -> usize {
        self.documents.len()
    }

    pub fn is_empty(&self) -> bool {
        self.documents.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bm25_index_and_retrieval() {
        let mut index = BM25Index::default_params();
        index.add_document(IndexedDocument {
            id: "1".into(),
            title: "Number One Bankai".into(),
            artist: "Shiro Sagisu".into(),
            context: Some("Bleach Thousand Year Blood War".into()),
        });
        index.add_document(IndexedDocument {
            id: "2".into(),
            title: "We Are".into(),
            artist: "Hiroshi Kitadani".into(),
            context: Some("One Piece OP 1".into()),
        });

        let res = index.search("Bankai Bleach", 5);
        assert!(!res.is_empty());
        assert_eq!(res[0].doc_id, "1");
    }
}
