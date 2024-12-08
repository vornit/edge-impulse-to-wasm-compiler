use rustfft::{FftPlanner, num_complex::Complex};
use std::io::Write;

pub fn generate_features(
    implementation_version: i32,
    draw_graphs: bool,
    raw_data: Vec<f64>,
    axes: Vec<String>,
    sampling_freq: i32,
    scale_axes: i32,
    input_decimation_ratio: i32,
    filter_type: String,
    filter_cutoff: f64,
    filter_order: i32,
    analysis_type: String,
    fft_length: i32,
    spectral_peaks_count: i32,
    spectral_peaks_threshold: i32,
    spectral_power_edges: String,
    do_log: bool,
    do_fft_overlap: bool,
    wavelet_level: i32,
    wavelet: String,
    extra_low_freq: bool,
) -> Vec<f64> {
    let mut fx: Vec<Vec<f64>> = vec![vec![], vec![], vec![]];

    // Split the data into three separate vectors
    for (i, value) in raw_data.iter().enumerate() {
        match i % 3 {
            0 => fx[0].push(*value),
            1 => fx[1].push(*value),
            2 => fx[2].push(*value),
            _ => unreachable!(),
        }
    }

    // Center each data axis
    for axis_data in &mut fx {
        let mean: f64 = axis_data.iter().sum::<f64>() / axis_data.len() as f64;
        for value in axis_data.iter_mut() {
            *value -= mean;
        }
    }

    // Round values ​​to 8 decimal places
    let fx_formatted: Vec<Vec<String>> = fx.iter()
        .map(|axis_data| axis_data.iter()
            .map(|&val| format!("{:.8}", val))
            .collect()
        ).collect();

        let mut all_features: Vec<f64> = Vec::new();

        for (i, axis_data) in fx.iter().enumerate() {
            let (features, _, _, _) = extract_spec_features(
                axis_data,
                sampling_freq,
                fft_length as i32,
                &filter_type,
                filter_cutoff,
                do_log,
                do_fft_overlap,
                true,
                &axes[i],
            );
            all_features.extend(features);
        }
    
        all_features
    }

fn extract_spec_features(
    fx: &Vec<f64>,
    sampling_freq: i32,
    fft_length: i32,
    filter_type: &str,
    filter_cutoff: f64,
    do_log: bool,
    do_fft_overlap: bool,
    spec_stats: bool,
    suffix: &str,
) -> (Vec<f64>, Vec<String>, Vec<f64>, Vec<f64>) {
    let mut features: Vec<f64> = Vec::new();

    let mean_square: f64 = fx.iter().map(|&x| x * x).sum::<f64>() / fx.len() as f64;
    let rms = mean_square.sqrt();

    features.push(rms);

    let skewness = skew(fx);
    features.push(skewness);

    let kurtosis = calculate_kurtosis(fx);
    features.push(kurtosis);

    let (freqs, mut spec_powers) = welch_max_hold(
        fx,
        sampling_freq as f64,
        fft_length as usize,
        if do_fft_overlap { (fft_length / 2) as usize } else { 0 },
    );

    if spec_stats {
        let spec_skewness = skew(&spec_powers);
        features.push(spec_skewness);

        let spec_kurtosis = calculate_kurtosis(&spec_powers);
        features.push(spec_kurtosis);
    }

    // Frequency spacing (Rust equivalent of `freq_spacing = freqs[1]`)
    let freq_spacing = if freqs.len() > 1 { freqs[1] - freqs[0] } else { 0.0 };

    if do_log {
        zero_handling(&mut spec_powers); // Replace zeros with epsilon
        for val in spec_powers.iter_mut() {
            *val = val.log10();
        }
    }

    // Append spectral powers (excluding the first element)
    for i in 1..spec_powers.len() {
        features.push(spec_powers[i]);
    }

    // TODO: Implement labels if needed
    let labels = vec![format!("Dummy Label{}", suffix)];

    (features, labels, spec_powers, freqs)
}

fn skew(data: &Vec<f64>) -> f64 {
    if data.len() < 2 {
        return 0.0;
    }

    let n = data.len() as f64;
    let mean = data.iter().sum::<f64>() / n;

    // Calculate the standard deviation
    let variance = data.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / n;
    let std_dev = variance.sqrt();

    if std_dev == 0.0 {
        return 0.0;
    }

    let skewness = data
        .iter()
        .map(|&x| (x - mean).powi(3))
        .sum::<f64>()
        / (n * std_dev.powi(3));

    skewness
}

fn calculate_kurtosis(fx: &Vec<f64>) -> f64 {
    let n = fx.len() as f64;
    let mean = fx.iter().sum::<f64>() / n;
    let variance = fx.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / n;

    let fourth_moment = fx.iter().map(|&x| (x - mean).powi(4)).sum::<f64>() / n;

    fourth_moment / variance.powi(2) - 3.0
}

fn welch_max_hold(
    fx: &Vec<f64>,
    sampling_freq: f64,
    nfft: usize,
    n_overlap: usize,
) -> (Vec<f64>, Vec<f64>) {
    let mut spec_powers = vec![0.0_f64; nfft / 2 + 1];
    let mut freqs = vec![0.0_f64; nfft / 2 + 1];

    // Precompute the frequencies
    for i in 0..freqs.len() {
        freqs[i] = i as f64 * sampling_freq / nfft as f64;
    }

    // Prepare FFT planner
    let mut fft_planner = FftPlanner::new();
    let fft = fft_planner.plan_fft_forward(nfft);

    let mut ix = 0;
    while ix < fx.len() {
        // Slice the data and zero-pad if necessary
        let end_idx = usize::min(ix + nfft, fx.len());
        let mut input = vec![Complex::new(0.0, 0.0); nfft];
        for j in 0..(end_idx - ix) {
            input[j].re = fx[ix + j];
        }

        // Perform FFT
        let mut spectrum = input.clone();
        fft.process(&mut spectrum);

        // Compute power spectrum
        let power_spectrum: Vec<f64> = spectrum.iter()
            .take(nfft / 2 + 1)
            .map(|x| x.norm_sqr() as f64 / nfft as f64)
            .collect();

        // Update the maximum spectral powers
        for (i, &power) in power_spectrum.iter().enumerate() {
            spec_powers[i] = spec_powers[i].max(power);
        }

        ix += nfft - n_overlap;
    }

    (freqs, spec_powers)
}

fn zero_handling(x: &mut Vec<f64>) {
    let epsilon = 1e-10;
    for val in x.iter_mut() {
        if *val == 0.0 {
            *val = epsilon;
        }
    }
}

#[no_mangle]
pub fn testailu() -> i32 {
    let implementation_version = 4;
    let draw_graphs = false;

    let raw_data = vec![
        -0.6300, 6.7400, 6.9600, -0.6300, 6.7300, 6.9600, -0.6500, 6.7200, 6.9600, -0.6400, 6.7300, 6.9800, -0.6300, 6.7300, 6.9900, -0.6300, 6.7100, 6.9900, -0.6200, 6.7200, 6.9800, -0.6300, 6.7200, 6.9700, -0.6300, 6.7100, 6.9800, -0.6200, 6.7200, 6.9700, -0.6200, 6.7300, 6.9600, -0.6300, 6.7300, 6.9700, -0.6200, 6.7300, 6.9800, -0.6300, 6.7300, 6.9800, -0.6400, 6.7200, 6.9700, -0.6300, 6.7200, 6.9900, -0.6300, 6.7200, 6.9700, -0.6300, 6.7200, 6.9800, -0.6300, 6.7200, 6.9700, -0.6400, 6.7100, 6.9600, -0.6200, 6.7300, 6.9800, -0.6200, 6.7200, 6.9600, -0.6200, 6.7300, 6.9600, -0.6200, 6.7100, 6.9800, -0.6200, 6.7200, 6.9700, -0.6400, 6.7300, 6.9800, -0.6500, 6.7300, 6.9800, -0.6400, 6.7200, 6.9800, -0.6400, 6.7200, 6.9700, -0.6400, 6.7200, 6.9600, -0.6300, 6.7200, 6.9700, -0.6300, 6.7200, 6.9700, -0.6300, 6.7300, 6.9600, -0.6100, 6.7100, 6.9700, -0.6200, 6.7300, 6.9700, -0.6200, 6.7200, 6.9700, -0.6300, 6.7200, 6.9800, -0.6400, 6.7200, 6.9800, -0.6500, 6.7100, 6.9700, -0.6400, 6.7100, 6.9800, -0.6300, 6.7200, 6.9800, -0.6400, 6.7300, 6.9900, -0.6300, 6.7100, 6.9700, -0.6200, 6.7200, 6.9700, -0.6100, 6.7100, 6.9700, -0.6200, 6.7300, 6.9700, -0.6400, 6.7300, 6.9700, -0.6400, 6.7200, 6.9800, -0.6400, 6.7100, 6.9700, -0.6400, 6.7200, 6.9900, -0.6400, 6.7100, 6.9900, -0.6400, 6.7200, 6.9800, -0.6400, 6.7200, 6.9800, -0.6200, 6.7200, 6.9700, -0.6200, 6.7200, 6.9800, -0.6200, 6.7300, 6.9700, -0.6200, 6.7300, 6.9800, -0.6400, 6.7000, 6.9800, -0.6200, 6.7200, 6.9800, -0.6400, 6.7000, 6.9700, -0.6400, 6.7000, 6.9900, -0.6400, 6.7100, 6.9700, -0.6400, 6.7100, 6.9700, -0.6300, 6.7200, 6.9800, -0.6300, 6.7200, 6.9700, -0.6200, 6.7100, 6.9700, -0.6200, 6.7200, 6.9700, -0.6200, 6.7100, 6.9700, -0.6300, 6.7200, 6.9800, -0.6300, 6.7200, 6.9700, -0.6200, 6.7200, 6.9700, -0.6300, 6.7200, 6.9700, -0.6400, 6.7200, 6.9800, -0.6500, 6.7100, 6.9700, -0.6400, 6.7300, 6.9900, -0.6200, 6.7100, 6.9800, -0.6400, 6.7000, 6.9700, -0.6300, 6.7100, 6.9800, -0.6300, 6.7100, 6.9800, -0.6300, 6.7100, 6.9700, -0.6200, 6.7300, 6.9900, -0.6200, 6.7300, 6.9700, -0.6400, 6.7100, 6.9600, -0.6400, 6.7200, 6.9900, -0.6200, 6.7200, 6.9800, -0.6300, 6.7200, 6.9800, -0.6200, 6.7100, 6.9700, -0.6400, 6.7000, 6.9800, -0.6300, 6.7100, 6.9700, -0.6400, 6.7000, 6.9700, -0.6300, 6.7200, 6.9700, -0.6300, 6.7100, 6.9700, -0.6200, 6.7200, 6.9800, -0.6200, 6.7200, 6.9800, -0.6400, 6.7100, 6.9700, -0.6300, 6.7100, 6.9900, -0.6400, 6.7200, 6.9800, -0.6400, 6.7100, 6.9800, -0.6300, 6.7300, 6.9800, -0.6200, 6.7200, 6.9800, -0.6400, 6.7100, 6.9800, -0.6300, 6.7200, 6.9700, -0.6300, 6.7100, 6.9800, -0.6200, 6.7200, 6.9700
    ];

    let axes = vec!["x".to_string(), "y".to_string(), "z".to_string()];
    let sampling_freq = 52;
    let scale_axes = 1;
    let input_decimation_ratio = 1;
    let filter_type = "none".to_string();
    let filter_cutoff = 0.0;
    let filter_order = 0;
    let analysis_type = "fft".to_string();

    let fft_length = 16;
    let spectral_peaks_count = 0;
    let spectral_peaks_threshold = 0;
    let spectral_power_edges = "0".to_string();

    let do_log = true;
    let do_fft_overlap = true;
    let extra_low_freq = false;

    let wavelet_level = 3;
    let wavelet = "haar".to_string();

    // Generate features
    let features = generate_features(
        implementation_version,
        draw_graphs,
        raw_data,
        axes,
        sampling_freq,
        scale_axes,
        input_decimation_ratio,
        filter_type,
        filter_cutoff,
        filter_order,
        analysis_type,
        fft_length,
        spectral_peaks_count,
        spectral_peaks_threshold,
        spectral_power_edges,
        do_log,
        do_fft_overlap,
        wavelet_level,
        wavelet,
        extra_low_freq,
    );

    // Save features to a file in a single line with comma-separated values
    let file_path = "accelerometer_data.csv";
    let Ok(mut output) = std::fs::File::create(file_path)
        else { return SaveFeaturesError::FileCreationFailed as i32 };

    let data: String = features
        .iter()
        .map(|f| format!("{:.4}", f)) // Muotoilu neljään desimaaliin
        .collect::<Vec<String>>()
        .join(", "); // Pilkku ja välilyönti erottimena

    let Ok(_) = output.write_all(data.as_bytes())
        else { return SaveFeaturesError::FileWriteFailed as i32 };

    // Return 0 to indicate success
    0
}

enum SaveFeaturesError {
    FileCreationFailed = -1,
    FileWriteFailed = -2,
}