use rustfft::{FftPlanner, num_complex::Complex};

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
) -> i32 {
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

    for (i, axis_data) in fx.iter().enumerate() {
        let (features, labels, spec_powers, freqs) = extract_spec_features(
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
    }

    0
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

    println!("Features: {:?}", features);

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