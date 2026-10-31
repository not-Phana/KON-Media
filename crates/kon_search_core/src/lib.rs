pub mod audio_dsp;
pub mod audio_tagger;
pub mod audio_verifier;
pub mod bm25;
pub mod cache;
pub mod catalog;
pub mod dedup;
pub mod download_queue;
pub mod entity_parser;
pub mod fast_resampler;
pub mod features;
pub mod fuzzy;
pub mod lyrics_matcher;
pub mod media_classifier;
pub mod normalization;
pub mod pairing;
pub mod query_rewriter;
pub mod ranking;
pub mod scoring;
pub mod soundtrack_db;
pub mod suggestions;
pub mod track_indexer;
pub mod vector_index;

use pyo3::prelude::*;

const CORE_VERSION: &str = "1.2.0";

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


/// Fast lightweight ranking for Flash mode.
#[pyfunction]
#[pyo3(signature = (query_json, candidates_json, limit=None))]
fn rank_candidates_flash_json(query_json: &str, candidates_json: &str, limit: Option<usize>) -> PyResult<String> {
    let query: features::QueryInput = serde_json::from_str(query_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid query JSON: {}", e)))?;

    let candidates: Vec<features::CandidateInput> = serde_json::from_str(candidates_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid candidates JSON: {}", e)))?;

    let ranked = ranking::rank_candidates_flash(&query, candidates, limit);

    serde_json::to_string(&ranked)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Fast lightweight suggestions for Flash mode.
#[pyfunction]
fn get_search_suggestions_flash_json(query: &str, media_type: &str, limit: usize) -> PyResult<String> {
    let items = suggestions::get_search_suggestions_flash(query, media_type, limit);
    serde_json::to_string(&items)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
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

/// Parse cluttered candidate title into clean artist, song, and franchise context.
#[pyfunction]
fn parse_media_entity_json(title: &str, uploader: &str) -> PyResult<String> {
    let parsed = entity_parser::parse_media_entity(title, uploader);
    serde_json::to_string(&parsed)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Get search suggestions and intelligent music discoveries in native Rust.
#[pyfunction]
fn get_search_suggestions_json(query: &str, media_type: &str, limit: usize) -> PyResult<String> {
    let items = suggestions::get_search_suggestions(query, media_type, limit);
    serde_json::to_string(&items)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Parse query intent clues (artists, version, context, fragments) in native Rust.
#[pyfunction]
fn parse_query_intent_json(query: &str) -> PyResult<String> {
    let intent = suggestions::parse_suggestion_intent(query);
    serde_json::to_string(&intent)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Evaluate candidate video stream against candidate audio stream for smart pairing.
#[pyfunction]
fn evaluate_stream_pair_json(video_json: &str, audio_json: &str) -> PyResult<String> {
    let video: pairing::StreamCandidate = serde_json::from_str(video_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid video JSON: {}", e)))?;
    let audio: pairing::StreamCandidate = serde_json::from_str(audio_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid audio JSON: {}", e)))?;

    let evaluation = pairing::evaluate_stream_pair(&video, &audio);
    serde_json::to_string(&evaluation)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Verify audio samples for loudness, silence ratio, and distortion.
#[pyfunction]
fn verify_audio_samples_json(samples: Vec<f32>, sample_rate: u32) -> PyResult<String> {
    let res = audio_verifier::verify_audio_samples(&samples, sample_rate);
    serde_json::to_string(&res)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Fast in-memory BM25 search over a batch of indexed documents.
#[pyfunction]
fn bm25_search_json(docs_json: &str, query: &str, limit: usize) -> PyResult<String> {
    let docs: Vec<bm25::IndexedDocument> = serde_json::from_str(docs_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid docs JSON: {}", e)))?;

    let mut index = bm25::BM25Index::default_params();
    for doc in docs {
        index.add_document(doc);
    }

    let results = index.search(query, limit);
    serde_json::to_string(&results)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Classify a candidate's media title, uploader, and duration.
#[pyfunction]
fn classify_media_candidate_json(title: &str, uploader: &str, duration_secs: f64) -> PyResult<String> {
    let classification = media_classifier::classify_candidate(title, uploader, duration_secs);
    serde_json::to_string(&classification)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Search verified soundtrack database in native Rust.
#[pyfunction]
fn search_soundtrack_db_json(query: &str, limit: usize) -> PyResult<String> {
    let entries = soundtrack_db::search_soundtrack_db(query, limit);
    serde_json::to_string(&entries)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Search canonical discography tracks in native Rust.
#[pyfunction]
fn search_catalog_tracks_json(query: &str, limit: usize) -> PyResult<String> {
    let tracks = catalog::search_catalog_tracks(query, limit);
    serde_json::to_string(&tracks)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Rewrite query with phonetic expansion, transliteration, and canonical hints.
#[pyfunction]
fn rewrite_query_json(query: &str) -> PyResult<String> {
    let rewritten = query_rewriter::rewrite_query(query);
    serde_json::to_string(&rewritten)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Parse synchronized LRC lyrics into structured timestamps.
#[pyfunction]
fn parse_lrc_json(lrc_content: &str) -> PyResult<String> {
    let parsed = lyrics_matcher::parse_lrc(lrc_content);
    serde_json::to_string(&parsed)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Search lyrics snippet across synchronized LRC content.
#[pyfunction]
fn search_lyrics_json(lrc_content: &str, query: &str) -> PyResult<String> {
    let parsed = lyrics_matcher::parse_lrc(lrc_content);
    let hits = lyrics_matcher::search_lyrics_snippet(&parsed, query);
    serde_json::to_string(&hits)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))
}

/// Build ID3v2 tag buffer from JSON metadata.
#[pyfunction]
fn build_id3v2_tag_json(meta_json: &str) -> PyResult<Vec<u8>> {
    let meta: audio_tagger::MusicMetadata = serde_json::from_str(meta_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid metadata JSON: {}", e)))?;
    Ok(audio_tagger::build_id3v2_tag(&meta))
}

/// Resample audio samples from in_rate to out_rate using cubic Hermite interpolation.
#[pyfunction]
fn resample_audio(samples: Vec<f32>, in_rate: u32, out_rate: u32) -> Vec<f32> {
    let (resampled, _) = fast_resampler::resample_mono_cubic(&samples, in_rate, out_rate);
    resampled
}

/// Damerau-Levenshtein similarity score between two strings.
#[pyfunction]
fn damerau_similarity(s1: &str, s2: &str) -> f64 {
    fuzzy::damerau_levenshtein_similarity(s1, s2)
}

/// Jaro-Winkler similarity score between two strings.
#[pyfunction]
#[pyo3(signature = (s1, s2, prefix_scale=0.1))]
fn jaro_winkler_similarity(s1: &str, s2: &str, prefix_scale: f64) -> f64 {
    fuzzy::jaro_winkler_similarity(s1, s2, prefix_scale)
}

/// Cache get from global in-memory Rust cache.
#[pyfunction]
fn cache_get(key: &str) -> Option<String> {
    cache::get_global_cache().get(&key.to_string())
}

/// Cache insert into global in-memory Rust cache.
#[pyfunction]
#[pyo3(signature = (key, value, ttl_secs=None))]
fn cache_insert(key: &str, value: &str, ttl_secs: Option<u64>) {
    let ttl = ttl_secs.map(std::time::Duration::from_secs);
    cache::get_global_cache().insert(key.to_string(), value.to_string(), ttl);
}

/// Cache metrics (hits, misses, evictions).
#[pyfunction]
fn cache_stats() -> (u64, u64, u64) {
    cache::get_global_cache().stats()
}

/// PyO3 Module definition for kon_search_core
#[pymodule]
fn kon_search_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_query, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_media_url, m)?)?;
    m.add_function(wrap_pyfunction!(rank_candidates_json, m)?)?;
    m.add_function(wrap_pyfunction!(rank_candidates_flash_json, m)?)?;
    m.add_function(wrap_pyfunction!(get_search_suggestions_flash_json, m)?)?;

    m.add_function(wrap_pyfunction!(parse_media_entity_json, m)?)?;
    m.add_function(wrap_pyfunction!(get_search_suggestions_json, m)?)?;
    m.add_function(wrap_pyfunction!(parse_query_intent_json, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_stream_pair_json, m)?)?;
    m.add_function(wrap_pyfunction!(verify_audio_samples_json, m)?)?;
    m.add_function(wrap_pyfunction!(bm25_search_json, m)?)?;
    m.add_function(wrap_pyfunction!(classify_media_candidate_json, m)?)?;
    m.add_function(wrap_pyfunction!(search_soundtrack_db_json, m)?)?;
    m.add_function(wrap_pyfunction!(search_catalog_tracks_json, m)?)?;
    m.add_function(wrap_pyfunction!(rewrite_query_json, m)?)?;
    m.add_function(wrap_pyfunction!(parse_lrc_json, m)?)?;
    m.add_function(wrap_pyfunction!(search_lyrics_json, m)?)?;
    m.add_function(wrap_pyfunction!(build_id3v2_tag_json, m)?)?;
    m.add_function(wrap_pyfunction!(resample_audio, m)?)?;
    m.add_function(wrap_pyfunction!(damerau_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(jaro_winkler_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(cache_get, m)?)?;
    m.add_function(wrap_pyfunction!(cache_insert, m)?)?;
    m.add_function(wrap_pyfunction!(cache_stats, m)?)?;
    m.add("__version__", CORE_VERSION)?;
    Ok(())
}
