import tf2onnx

def convert_model(tflite_model_path, onnx_output_path):
    print(f"Converting model: {tflite_model_path} -> {onnx_output_path}")
    tf2onnx.convert.from_tflite(tflite_model_path, output_path=onnx_output_path)

if __name__ == "__main__":
    tflite_model_path = "model.tflite"
    onnx_output_path = "model.onnx"
    convert_model(tflite_model_path, onnx_output_path)
    print("Model successfully converted!")