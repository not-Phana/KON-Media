pub mod dedup;
pub mod features;
pub mod normalization;
pub mod ranking;
pub mod scoring;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

const CORE_VERSION: &str = "1.1.0";

/// Returns the Rust engine version.
#[pyfunction]
fn version() -> &'static str {
    CORE_VERSION
}

/// Normalize text with lowercase and alphanumeric cleanup.
#[pyfunction]
fn normalize_query(query: &str) -> String {
    normalization::normalize_text(query)
}

/// Normalize media URL into canonical form.
#[pyfunction]
fn normalize_media_url(url: &str) -> String {
    dedup::normalize_media_url(url)
}

/// Rank candidates passing and returning JSON strings for clean interop.
#[pyfunction]
fn rank_candidates_json(query_json: &str, candidates_json: &str) -> PyResult<String> {
    let query: features::QueryInput = serde_json::from_str(query_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid query JSON: {}", e)))?;

    let candidates: Vec<features::CandidateInput> = serde_json::from_str(candidates_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid candidates JSON: {}", e)))?;

    let ranked = ranking::rank_candidates(&query, candidates, None);

    serde_json::to_string(&ranked)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// PyO3 Module definition for kon_search_core
#[pymodule]
fn kon_search_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_query, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_media_url, m)?)?;
    m.add_function(wrap_pyfunction!(rank_candidates_json, m)?)?;
    m.add("__version__", CORE_VERSION)?;
    Ok(())
}
