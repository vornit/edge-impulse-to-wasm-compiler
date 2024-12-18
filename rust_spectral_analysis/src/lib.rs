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
        1.7300, 1.0800, 10.5200, 1.7400, 0.7300, 10.1600, 1.5700, 0.4000, 9.5300, 1.5300, -0.6200, 9.0400, 1.3500, -1.1000, 8.9800, 1.1500, -0.7100, 8.2100, 1.1700, -0.0300, 8.3800, 1.2800, 0.3500, 10.4500, 1.3600, -0.6000, 9.7800, 1.2500, -0.6200, 8.4800, 1.0600, -1.3500, 7.4500, 0.7600, -1.0600, 7.5700, 0.6800, -0.6500, 7.7600, 0.7000, -0.4000, 9.0000, 0.8900, -0.0200, 11.6700, 0.8200, -1.2900, 11.0100, 0.7500, -1.0500, 8.3900, 0.3800, -1.4900, 7.0900, -0.1000, -0.8400, 6.7900, -0.2000, -0.4200, 6.6300, -0.5000, 0.0600, 7.8300, -0.5700, -0.0500, 8.3400, -0.4400, -1.1300, 7.7200, -0.3600, -1.5000, 6.6500, -0.3100, -1.3800, 7.8400, -0.6200, -0.2300, 7.6900, -1.0300, 0.4500, 6.6700, -1.0200, 0.0200, 6.1100, -0.9100, -1.0100, 5.4100, -0.9900, -1.9000, 5.2600, -0.9100, -2.1200, 5.4000, -0.9100, -1.4200, 6.1800, -0.9400, -0.8100, 7.4400, -0.8100, -0.9600, 7.4500, -0.4800, -1.1600, 6.9200, -0.1400, -1.5100, 7.3400, -0.2200, -1.2300, 8.0200, -0.4900, -0.4200, 7.4100, -0.5500, -0.5300, 6.0300, -0.1300, -0.4200, 6.5300, 0.0600, -0.6800, 7.6500, -0.0600, -0.3000, 7.9200, 0.0700, -0.0900, 7.0400, 0.5100, 0.2400, 7.3700, 0.8500, 0.2800, 8.3500, 0.8800, -0.0100, 9.0700, 0.7700, -0.3800, 9.6300, 1.1200, -0.0600, 9.4200, 2.1600, 0.1100, 9.3400, 2.2000, -0.0900, 12.1000, 1.3900, 0.4100, 11.3900, 1.7300, -0.0200, 8.4100, 2.3600, 0.0800, 9.2600, 2.5900, 0.2300, 11.2400, 2.4100, 1.2200, 11.6600, 2.3700, 1.8700, 9.5800, 2.3900, 2.0200, 9.9400, 2.4300, 1.4400, 11.5900, 2.4500, 0.8600, 11.5200, 2.6900, 1.3000, 9.7300, 2.6100, 1.6700, 10.2500, 2.3700, 2.5000, 10.6800, 2.4600, 2.2500, 10.2400, 2.5800, 1.9400, 10.2900, 2.7000, 1.7800, 10.0100, 2.7000, 1.9000, 10.0500, 2.7200, 2.4900, 9.7000, 2.9200, 2.8400, 9.3200, 2.9500, 2.5400, 10.0000, 3.0700, 2.9200, 10.2600, 3.4400, 2.2100, 9.8700, 3.7700, 1.5700, 10.7100, 3.9200, 1.3900, 12.2300, 4.0100, 1.0600, 12.0800, 4.0100, 1.7900, 12.0200, 3.8000, 2.4400, 11.6100, 3.8100, 3.0600, 10.9800, 3.9200, 2.4300, 9.9100, 4.0500, 1.8500, 10.5000, 4.0800, 1.9000, 11.8200, 4.2300, 2.0700, 11.9100, 4.4200, 1.6900, 12.0000, 4.5200, 1.6700, 12.2100, 4.5000, 1.4200, 12.3200, 4.4200, 1.5000, 12.0400, 4.3000, 1.4300, 11.5500, 4.2400, 1.8000, 11.5000, 4.1400, 1.6700, 11.2100, 4.0000, 2.1600, 10.9700, 3.9800, 2.0100, 10.9900, 4.0300, 1.6100, 10.9000, 4.0000, 1.3400, 11.4800, 4.0300, 0.9400, 12.0400, 4.1100, 1.3200, 12.4900, 3.9600, 1.3500, 12.5000, 3.8200, 1.6400, 11.9300, 3.7400, 1.3300, 11.2700, 3.5300, 1.6700, 11.1600, 3.2400, 1.5900, 11.1800, 3.1300, 1.8100, 11.4100, 3.0500, 1.6900, 10.7400, 2.7500, 1.4900, 10.3000, 2.3900, 1.8100, 9.8800, 2.2700, 2.0000, 10.0100
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