import requests
import os

def download_model():
    # Read API key from a file
    with open("api_key.txt", "r") as key_file:
        api_key = key_file.read().strip() 

    projectId = "530573"

    base_url = "https://studio.edgeimpulse.com"

    # Make a request for impulse blocks data
    response = requests.get(
        f"{base_url}/v1/api/{projectId}/downloads",
        headers={
            "x-api-key": api_key
        },
    )

    if response.status_code == 200:
        data = response.json()

         # Find the link for the TensorFlow Lite (float32) model
        tflite_float32 = next(
            (item for item in data['downloads'] if item['type'] == 'TensorFlow Lite (float32)'),
            None
        )

        if tflite_float32:
            download_url = base_url + tflite_float32['link']

            # Download the file
            model_response = requests.get(
                download_url,
                headers={
                    "x-api-key": api_key
                },
                stream=True
            )

            if model_response.status_code == 200:
                # Ensure the "models" directory exists
                models_dir = "models"
                os.makedirs(models_dir, exist_ok=True)

                # Save the file to the "models" directory
                model_path = os.path.join(models_dir, "model.tflite")
                with open(model_path, "wb") as f:
                    for chunk in model_response.iter_content(chunk_size=1024):
                        f.write(chunk)

                print("TensorFlow Lite (float32) model downloaded and saved as 'model.tflite'")
            else:
                raise Exception(f"Error downloading model: {model_response.status_code}, {model_response.text}")
        else:
            raise Exception("TensorFlow Lite (float32) model not found.")
    else:
        raise Exception(f"Error fetching download links: {response.status_code}, {response.text}")

def get_class_names():
    # Read the API key from a file
    with open("api_key.txt", "r") as key_file:
        api_key = key_file.read().strip()

    # Project ID and base URL
    projectId = "530573"
    base_url = "https://studio.edgeimpulse.com"

    # Metrics file URL
    metrics_url = f"{base_url}/v1/api/{projectId}/learn-data/11/model/metrics"

    # Fetch the metrics file
    metrics_response = requests.get(
        metrics_url,
        headers={
            "x-api-key": api_key
        }
    )

    # Check the response and save class names to a file
    if metrics_response.status_code == 200:
        metrics_data = metrics_response.json()

        # Extract class names from the metrics file
        class_names = metrics_data.get('validation', {}).get('float32', {}).get('class_names', [])

        if class_names:
            print("Class names:", class_names)

            # Ensure the "models" directory exists
            models_dir = "models"
            os.makedirs(models_dir, exist_ok=True)

            # Save class names to the "models" directory
            class_file_path = os.path.join(models_dir, "classes.txt")
            with open(class_file_path, "w") as class_file:
                for class_name in class_names:
                    class_file.write(f"{class_name}\n")

            print(f"Class names saved to '{class_file_path}'.")
        else:
            print("No class names found in the metrics file.")
    else:
        raise Exception(f"Error fetching the metrics file: {metrics_response.status_code}, {metrics_response.text}")

if __name__ == "__main__":
    download_model()