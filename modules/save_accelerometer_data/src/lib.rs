use wasm3_api::*;
use std::fs::File;
use std::io::Write;

enum TestiFunctionPredefinedPathError {
    FileCreationFailed = -1,
    FileWriteFailed = -2,
}

#[no_mangle]
pub fn save_sensor_data() -> i32 {
    let ptr = testiFunction(0);

    let list_size = 312;
    let numbers: &[f32] = unsafe { std::slice::from_raw_parts(ptr as *const f32, list_size) };

    // Format numbers to two decimal places and join them with commas
    let list_str = numbers
        .iter()
        .map(|n| format!("{:.2}", n))  // Format each number to 2 decimal places
        .collect::<Vec<_>>()
        .join(", ");

    // Create and write to a CSV file
    let Ok(mut output) = File::create("accelerometer_data.csv")
        else { return TestiFunctionPredefinedPathError::FileCreationFailed as i32 };

    let Ok(_) = output.write_all(list_str.as_bytes())
        else { return TestiFunctionPredefinedPathError::FileWriteFailed as i32 };

    0
}
