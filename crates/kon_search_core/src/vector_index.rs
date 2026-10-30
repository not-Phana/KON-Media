//! High-performance Dense Vector Search & Nearest Neighbors in native Rust.
//!
//! Provides optimized vector math and index structures for semantic embeddings:
//! - Cosine Similarity and Cosine Distance
//! - Squared Euclidean (L2) distance
//! - Dot Product distance
//! - Flat Vector Index with SIMD-friendly loops
//! - Top-K Nearest Neighbor Retrieval

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MetricType {
    Cosine,
    L2,
    DotProduct,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorSearchResult {
    pub id: String,
    pub score: f64,
}

pub struct VectorIndex {
    dimension: usize,
    metric: MetricType,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
}

impl VectorIndex {
    pub fn new(dimension: usize, metric: MetricType) -> Self {
        Self {
            dimension,
            metric,
            ids: Vec::new(),
            vectors: Vec::new(),
        }
    }

    pub fn add(&mut self, id: String, mut vector: Vec<f32>) -> Result<(), String> {
        if vector.len() != self.dimension {
            return Err(format!(
                "Vector dimension mismatch: expected {}, got {}",
                self.dimension,
                vector.len()
            ));
        }

        if self.metric == MetricType::Cosine {
            normalize_vector_in_place(&mut vector);
        }

        self.ids.push(id);
        self.vectors.push(vector);
        Ok(())
    }

    pub fn search(&self, mut query: Vec<f32>, top_k: usize) -> Vec<VectorSearchResult> {
        if query.len() != self.dimension || self.vectors.is_empty() {
            return Vec::new();
        }

        if self.metric == MetricType::Cosine {
            normalize_vector_in_place(&mut query);
        }

        let mut scored: Vec<(usize, f64)> = match self.metric {
            MetricType::Cosine | MetricType::DotProduct => self
                .vectors
                .iter()
                .enumerate()
                .map(|(idx, v)| (idx, dot_product(&query, v) as f64))
                .collect(),
            MetricType::L2 => self
                .vectors
                .iter()
                .enumerate()
                .map(|(idx, v)| {
                    let d = l2_distance_squared(&query, v) as f64;
                    (idx, 1.0 / (1.0 + d)) // Invert so higher is closer
                })
                .collect(),
        };

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(top_k);

        scored
            .into_iter()
            .map(|(idx, score)| VectorSearchResult {
                id: self.ids[idx].clone(),
                score,
            })
            .collect()
    }

    pub fn size(&self) -> usize {
        self.vectors.len()
    }

    pub fn dimension(&self) -> usize {
        self.dimension
    }
}

/// Compute dot product between two float vectors.
pub fn dot_product(v1: &[f32], v2: &[f32]) -> f32 {
    let mut sum = 0.0f32;
    for (&a, &b) in v1.iter().zip(v2.iter()) {
        sum += a * b;
    }
    sum
}

/// Compute squared L2 distance between two float vectors.
pub fn l2_distance_squared(v1: &[f32], v2: &[f32]) -> f32 {
    let mut sum = 0.0f32;
    for (&a, &b) in v1.iter().zip(v2.iter()) {
        let diff = a - b;
        sum += diff * diff;
    }
    sum
}

/// Normalize vector to unit Euclidean norm in place.
pub fn normalize_vector_in_place(v: &mut [f32]) {
    let norm_sq = dot_product(v, v);
    if norm_sq > 1e-9 {
        let inv_norm = 1.0 / norm_sq.sqrt();
        for val in v.iter_mut() {
            *val *= inv_norm;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cosine_similarity() {
        let mut index = VectorIndex::new(3, MetricType::Cosine);
        index.add("song1".into(), vec![1.0, 0.0, 0.0]).unwrap();
        index.add("song2".into(), vec![0.0, 1.0, 0.0]).unwrap();
        index.add("song3".into(), vec![0.9, 0.1, 0.0]).unwrap();

        let res = index.search(vec![1.0, 0.0, 0.0], 2);
        assert_eq!(res.len(), 2);
        assert_eq!(res[0].id, "song1");
        assert!((res[0].score - 1.0).abs() < 1e-4);
        assert_eq!(res[1].id, "song3");
    }
}
