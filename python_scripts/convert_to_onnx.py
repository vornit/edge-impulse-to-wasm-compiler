import tf2onnx
import os

def convert_model(tflite_model_path=None, onnx_output_path=None):

    tflite_model_path = "models/model.tflite"
    onnx_output_path = "models/model.onnx"

    os.makedirs("models", exist_ok=True)

    print(f"Converting model: {tflite_model_path} -> {onnx_output_path}")

    try:
        tf2onnx.convert.from_tflite(tflite_model_path, output_path=onnx_output_path)
        print("Model successfully converted!")
    except FileNotFoundError:
        error_message = f"TFLite model file not found: {tflite_model_path}"
        print(error_message)
        raise Exception(error_message)
    except Exception as e:
        error_message = f"Model conversion failed: {str(e)}"
        print(error_message)
        raise Exception(error_message)