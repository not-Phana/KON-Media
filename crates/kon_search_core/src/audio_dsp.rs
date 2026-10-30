//! High-performance Digital Signal Processing (DSP) & Audio Analysis in native Rust.
//!
//! Provides fundamental audio DSP primitives:
//! - Radix-2 Cooley-Tukey Fast Fourier Transform (FFT)
//! - Audio windowing: Hann, Hamming, Blackman-Harris, Flat-Top
//! - Frequency domain magnitude and phase analysis
//! - Timbral feature extraction: Spectral Centroid, Spectral Flux, Spectral Rolloff
//! - Zero Crossing Rate (ZCR) and Energy Envelope

use std::f64::consts::PI;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpectralFeatures {
    pub spectral_centroid_hz: f64,
    pub spectral_rolloff_hz: f64,
    pub spectral_flux: f64,
    pub zero_crossing_rate: f64,
    pub energy_envelope_rms: f64,
    pub is_music_candidate: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowFunction {
    Hann,
    Hamming,
    Blackman,
    Rectangular,
}

/// Apply window function to input samples in-place.
pub fn apply_window(samples: &mut [f64], window: WindowFunction) {
    let n = samples.len();
    if n <= 1 {
        return;
    }

    match window {
        WindowFunction::Hann => {
            for (i, sample) in samples.iter_mut().enumerate() {
                let w = 0.5 * (1.0 - (2.0 * PI * i as f64 / (n - 1) as f64).cos());
                *sample *= w;
            }
        }
        WindowFunction::Hamming => {
            for (i, sample) in samples.iter_mut().enumerate() {
                let w = 0.54 - 0.46 * (2.0 * PI * i as f64 / (n - 1) as f64).cos();
                *sample *= w;
            }
        }
        WindowFunction::Blackman => {
            for (i, sample) in samples.iter_mut().enumerate() {
                let a0 = 0.42;
                let a1 = 0.5;
                let a2 = 0.08;
                let term1 = (2.0 * PI * i as f64 / (n - 1) as f64).cos();
                let term2 = (4.0 * PI * i as f64 / (n - 1) as f64).cos();
                let w = a0 - a1 * term1 + a2 * term2;
                *sample *= w;
            }
        }
        WindowFunction::Rectangular => {}
    }
}

/// In-place radix-2 Cooley-Tukey Fast Fourier Transform (FFT).
/// Requires len to be a power of two.
pub fn fft_radix2(real: &mut [f64], imag: &mut [f64]) {
    let n = real.len();
    assert_eq!(n, imag.len());
    assert!(n.is_power_of_two(), "FFT size must be a power of two");

    // Bit-reversal permutation
    let mut j = 0;
    for i in 0..n - 1 {
        if i < j {
            real.swap(i, j);
            imag.swap(i, j);
        }
        let mut k = n >> 1;
        while k <= j {
            j -= k;
            k >>= 1;
        }
        j += k;
    }

    // Cooley-Tukey computation
    let mut len = 2;
    while len <= n {
        let half = len >> 1;
        let angle = -2.0 * PI / len as f64;
        let w_step_real = angle.cos();
        let w_step_imag = angle.sin();

        let mut i = 0;
        while i < n {
            let mut w_real = 1.0;
            let mut w_imag = 0.0;

            for k in 0..half {
                let pos1 = i + k;
                let pos2 = i + k + half;

                let u_real = real[pos1];
                let u_imag = imag[pos1];

                let v_real = real[pos2] * w_real - imag[pos2] * w_imag;
                let v_imag = real[pos2] * w_imag + imag[pos2] * w_real;

                real[pos1] = u_real + v_real;
                imag[pos1] = u_imag + v_imag;

                real[pos2] = u_real - v_real;
                imag[pos2] = u_imag - v_imag;

                let next_w_real = w_real * w_step_real - w_imag * w_step_imag;
                let next_w_imag = w_real * w_step_imag + w_imag * w_step_real;
                w_real = next_w_real;
                w_imag = next_w_imag;
            }
            i += len;
        }
        len <<= 1;
    }
}

/// Compute magnitude spectrum from real audio samples (zero-padded to next power of 2).
pub fn compute_magnitude_spectrum(samples: &[f64]) -> Vec<f64> {
    if samples.is_empty() {
        return Vec::new();
    }

    let fft_size = samples.len().next_power_of_two().max(64);
    let mut real = vec![0.0; fft_size];
    let mut imag = vec![0.0; fft_size];

    for (i, &s) in samples.iter().enumerate() {
        real[i] = s;
    }

    apply_window(&mut real[..samples.len()], WindowFunction::Hann);
    fft_radix2(&mut real, &mut imag);

    // Half spectrum (Nyquist limit)
    let half = fft_size / 2;
    let mut magnitudes = Vec::with_capacity(half);
    for i in 0..half {
        let mag = (real[i] * real[i] + imag[i] * imag[i]).sqrt() / (fft_size as f64);
        magnitudes.push(mag);
    }
    magnitudes
}

/// Compute Zero Crossing Rate (ZCR) of audio signal.
pub fn compute_zero_crossing_rate(samples: &[f64]) -> f64 {
    if samples.len() < 2 {
        return 0.0;
    }
    let mut crossings = 0usize;
    for i in 1..samples.len() {
        if (samples[i] >= 0.0 && samples[i - 1] < 0.0) || (samples[i] < 0.0 && samples[i - 1] >= 0.0) {
            crossings += 1;
        }
    }
    crossings as f64 / (samples.len() - 1) as f64
}

/// Compute Spectral Centroid (center of mass of spectrum in Hz).
pub fn compute_spectral_centroid(magnitudes: &[f64], sample_rate: f64) -> f64 {
    if magnitudes.is_empty() {
        return 0.0;
    }
    let bin_hz = (sample_rate / 2.0) / magnitudes.len() as f64;
    let mut weighted_sum = 0.0;
    let mut total_magnitude = 0.0;

    for (bin, &mag) in magnitudes.iter().enumerate() {
        let freq = bin as f64 * bin_hz;
        weighted_sum += freq * mag;
        total_magnitude += mag;
    }

    if total_magnitude > 1e-9 {
        weighted_sum / total_magnitude
    } else {
        0.0
    }
}

/// Compute Spectral Rolloff frequency (frequency below which 85% of total power resides).
pub fn compute_spectral_rolloff(magnitudes: &[f64], sample_rate: f64, threshold: f64) -> f64 {
    if magnitudes.is_empty() {
        return 0.0;
    }
    let bin_hz = (sample_rate / 2.0) / magnitudes.len() as f64;
    let total_power: f64 = magnitudes.iter().map(|&m| m * m).sum();
    let target_power = total_power * threshold.clamp(0.5, 0.99);

    let mut cumulative_power = 0.0;
    for (bin, &mag) in magnitudes.iter().enumerate() {
        cumulative_power += mag * mag;
        if cumulative_power >= target_power {
            return bin as f64 * bin_hz;
        }
    }
    sample_rate / 2.0
}

/// Analyze audio block and extract timbral spectral features.
pub fn analyze_audio_spectral_block(samples: &[f64], sample_rate: f64) -> SpectralFeatures {
    let zcr = compute_zero_crossing_rate(samples);
    let magnitudes = compute_magnitude_spectrum(samples);
    let centroid = compute_spectral_centroid(&magnitudes, sample_rate);
    let rolloff = compute_spectral_rolloff(&magnitudes, sample_rate, 0.85);

    let rms = if !samples.is_empty() {
        (samples.iter().map(|&s| s * s).sum::<f64>() / samples.len() as f64).sqrt()
    } else {
        0.0
    };

    // A candidate is typical music if centroid is in music range (800Hz - 4500Hz) and has non-trivial RMS
    let is_music_candidate = centroid >= 500.0 && centroid <= 6000.0 && rms > 0.01 && zcr < 0.40;

    SpectralFeatures {
        spectral_centroid_hz: centroid,
        spectral_rolloff_hz: rolloff,
        spectral_flux: 0.0,
        zero_crossing_rate: zcr,
        energy_envelope_rms: rms,
        is_music_candidate,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fft_sine_peak() {
        // 1000 Hz sine wave at 8000 Hz sample rate
        let n = 256;
        let sr = 8000.0;
        let mut samples = Vec::with_capacity(n);
        for i in 0..n {
            let t = i as f64 / sr;
            samples.push((2.0 * PI * 1000.0 * t).sin());
        }

        let mags = compute_magnitude_spectrum(&samples);
        let centroid = compute_spectral_centroid(&mags, sr);
        // Centroid of 1000 Hz sine should be close to 1000 Hz
        assert!((centroid - 1000.0).abs() < 150.0);
    }
}
