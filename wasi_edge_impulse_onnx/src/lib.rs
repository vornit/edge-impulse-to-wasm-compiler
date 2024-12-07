use tract_onnx::{self as tonnx, prelude::{self as tp, Framework, InferenceModelExt, Tensor, tvec}};
use std::fs::File;
use std::io::{self, BufRead};

#[derive(Debug)]
pub enum E {
    ModelLoad,
    Optimization,
    Runnable,
    DataLoad,
    Run,
    Conversion,
}

/// Load accelerometer data from a CSV file.
fn load_accelerometer_data(file_path: String) -> Result<Vec<f32>, E> {
    let file = File::open(file_path).map_err(|_| E::DataLoad)?;
    let reader = io::BufReader::new(file);

    let mut data = Vec::new();
    for line in reader.lines() {
        let line = line.map_err(|_| E::DataLoad)?;
        for value in line.split(',') {
            let parsed_value: f32 = value.trim().parse().map_err(|_| E::DataLoad)?;
            data.push(parsed_value);
        }
    }

    Ok(data)
}

/// Infer the label index based on accelerometer data using the given model.
pub fn infer(model_path: String, data_path: String) -> Result<Vec<f32>, E> {
    // Load model from file.
    let model = tonnx::onnx()
        .model_for_path(model_path)
        .map_err(|e| {
            eprintln!("{:?}", e);
            E::ModelLoad
        })?
        .into_optimized()
        .map_err(|_| E::Optimization)?
        .into_runnable()
        .map_err(|_| E::Runnable)?;

    let data = load_accelerometer_data(data_path)?;

    // Create the tensor with shape as required by the model
    let tensor: Tensor = tp::tract_ndarray::Array2::from_shape_vec((1, 39), data)
        .map_err(|_| E::Conversion)?
        .into();

    let result = model.run(tvec!(tensor.into())).map_err(|_| E::Run)?;

    // Get the probabilities for all classes.
    let probabilities = result[0]
        .to_array_view::<f32>()
        .map_err(|_| E::Conversion)?
        .iter()
        .cloned()
        .collect::<Vec<f32>>();

    Ok(probabilities)
}

#[no_mangle]
pub fn infer_predefined_paths() -> i32 {
    for file in std::fs::read_dir(".").unwrap() {
        eprintln!("{:?}", file);
    }

    match infer("model.onnx".to_owned(), "accelerometer_data.csv".to_owned()) {
        Ok(probabilities) => {
            // Tulosta todennäköisyydet
            println!("Probabilities: {:?}", probabilities);

            // Etsi suurimman todennäköisyyden indeksi (oletettu luokka)
            if let Some((index, _)) = probabilities.iter().enumerate().max_by(|a, b| a.1.partial_cmp(b.1).unwrap()) {
                return index as i32; // Palauta luokan indeksi
            }

            eprintln!("No probabilities found.");
            -7 // Virhekoodi, jos todennäköisyyksiä ei löydy
        }
        Err(e) => {
            eprintln!("Error: {:?}", e);
            match e {
                E::ModelLoad => -1,
                E::Optimization => -2,
                E::Runnable => -3,
                E::DataLoad => -4,
                E::Run => -5,
                E::Conversion => -6,
            }
        },
    }
}