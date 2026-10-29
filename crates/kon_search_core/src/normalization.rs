use std::collections::HashSet;

/// Normalize a text string: lowercased, non-alphanumeric chars converted to spaces, collapsed whitespace.
pub fn normalize_text(text: &str) -> String {
    if text.is_empty() {
        return String::new();
    }

    let mut result = String::with_capacity(text.len());
    let mut prev_is_space = false;

    for ch in text.chars() {
        if ch.is_alphanumeric() {
            for lower_ch in ch.to_lowercase() {
                result.push(lower_ch);
            }
            prev_is_space = false;
        } else {
            if !prev_is_space && !result.is_empty() {
                result.push(' ');
                prev_is_space = true;
            }
        }
    }

    // Trim trailing space if any
    if result.ends_with(' ') {
        result.pop();
    }
    result
}

/// Strip common media noise patterns like [Official Video], (HD Remastered), etc.
pub fn strip_media_noise(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];
        if ch == '[' || ch == '(' {
            let close_ch = if ch == '[' { ']' } else { ')' };
            let mut j = i + 1;
            let mut found_close = false;
            while j < chars.len() {
                if chars[j] == close_ch {
                    found_close = true;
                    break;
                }
                j += 1;
            }

            if found_close {
                let inside: String = chars[i + 1..j].iter().collect();
                let inside_lower = inside.to_lowercase();
                if inside_lower.contains("official")
                    || inside_lower.contains("video")
                    || inside_lower.contains("audio")
                    || inside_lower.contains("remaster")
                    || inside_lower.contains("hd")
                    || inside_lower.contains("4k")
                    || inside_lower.contains("lyrics")
                    || inside_lower.contains("clip officiel")
                {
                    i = j + 1;
                    continue;
                }
            }
        }
        out.push(ch);
        i += 1;
    }

    // Collapse spaces
    out.split_whitespace().collect::<Vec<&str>>().join(" ")
}

/// Tokenize normalized string into distinct clean words.
pub fn tokenize(text: &str) -> Vec<String> {
    let norm = normalize_text(text);
    norm.split_whitespace()
        .filter(|w| !w.is_empty())
        .map(|w| w.to_string())
        .collect()
}

/// Extract character n-grams from a string.
pub fn char_ngrams(s: &str, n: usize) -> HashSet<String> {
    let chars: Vec<char> = s.chars().collect();
    let mut ngrams = HashSet::new();
    if chars.is_empty() {
        return ngrams;
    }
    if chars.len() < n {
        ngrams.insert(s.to_string());
        return ngrams;
    }
    for i in 0..=(chars.len() - n) {
        let gram: String = chars[i..i + n].iter().collect();
        ngrams.insert(gram);
    }
    ngrams
}

/// Calculate Jaccard similarity over character n-grams for typo tolerance.
pub fn ngram_similarity(s1: &str, s2: &str, n: usize) -> f64 {
    let norm1 = normalize_text(s1);
    let norm2 = normalize_text(s2);
    if norm1.is_empty() || norm2.is_empty() {
        return 0.0;
    }
    if norm1 == norm2 {
        return 1.0;
    }

    let set1 = char_ngrams(&norm1, n);
    let set2 = char_ngrams(&norm2, n);

    let intersection_count = set1.intersection(&set2).count();
    let union_count = set1.union(&set2).count();

    if union_count == 0 {
        return 0.0;
    }

    (intersection_count as f64) / (union_count as f64)
}

/// Compute Levenshtein distance between two strings.
pub fn levenshtein_distance(s1: &str, s2: &str) -> usize {
    let v1: Vec<char> = s1.chars().collect();
    let v2: Vec<char> = s2.chars().collect();
    let l1 = v1.len();
    let l2 = v2.len();

    if l1 == 0 {
        return l2;
    }
    if l2 == 0 {
        return l1;
    }

    let mut prev_row: Vec<usize> = (0..=l2).collect();
    let mut curr_row: Vec<usize> = vec![0; l2 + 1];

    for i in 0..l1 {
        curr_row[0] = i + 1;
        for j in 0..l2 {
            let cost = if v1[i] == v2[j] { 0 } else { 1 };
            curr_row[j + 1] = std::cmp::min(
                std::cmp::min(prev_row[j + 1] + 1, curr_row[j] + 1),
                prev_row[j] + cost,
            );
        }
        prev_row.copy_from_slice(&curr_row);
    }

    prev_row[l2]
}

/// Calculate character-level edit similarity (0.0 to 1.0).
pub fn levenshtein_similarity(s1: &str, s2: &str) -> f64 {
    let norm1 = normalize_text(s1);
    let norm2 = normalize_text(s2);
    if norm1 == norm2 {
        return 1.0;
    }
    let max_len = std::cmp::max(norm1.chars().count(), norm2.chars().count());
    if max_len == 0 {
        return 1.0;
    }
    let dist = levenshtein_distance(&norm1, &norm2);
    let sim = 1.0 - ((dist as f64) / (max_len as f64));
    sim.max(0.0).min(1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_text() {
        assert_eq!(normalize_text("Number One - Bankai!"), "number one bankai");
        assert_eq!(normalize_text("  The Weeknd   "), "the weeknd");
    }

    #[test]
    fn test_strip_media_noise() {
        assert_eq!(
            strip_media_noise("Queen - Bohemian Rhapsody [Official Video HD]"),
            "Queen - Bohemian Rhapsody"
        );
    }

    #[test]
    fn test_ngram_similarity() {
        let sim = ngram_similarity("bohemain rhapsdy", "bohemian rhapsody", 3);
        assert!(sim > 0.35);
    }

    #[test]
    fn test_levenshtein_similarity() {
        let sim = levenshtein_similarity("bankai", "bankai");
        assert_eq!(sim, 1.0);
        let sim_close = levenshtein_similarity("bankai", "bankay");
        assert!(sim_close > 0.80);
    }
}
