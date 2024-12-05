from flask import Flask, render_template, jsonify, request, render_template_string
from python_scripts.download_model import download_model
from python_scripts.convert_to_onnx import convert_model
import requests
import logging
import subprocess
from contextlib import contextmanager
import os

app = Flask(__name__, template_folder="../templates")

logging.basicConfig(level=logging.INFO)

app.logger.setLevel(logging.INFO)

@contextmanager
def change_directory(directory):
    original_directory = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(original_directory)

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/run_pipeline", methods=["GET"])
def run_pipeline():
    try:
        download_model()
        convert_model()
        #run_rust_code()
        upload_wasm()
        return "Pipeline executed successfully!", 200
    except Exception as e:
        print(f"Pipeline failed: {e}")
        return "Pipeline execution failed. Check server logs for details.", 500

def run_rust_code():
    rust_project_path = "wasi_edge_impulse_onnx"

    with change_directory(rust_project_path):
        build_result = subprocess.run(["cargo", "build", "--target", "wasm32-wasi", "--release"], capture_output=True, text=True)
        if build_result.returncode != 0:
            print("Rust build failed:")
            print(build_result.stderr)
            return False

        print("Rust build succeeded.")
        print(build_result.stdout)
        return True

def upload_wasm():
    try:
        orchestrator_url = 'http://172.17.0.1:3000/file/module'

        wasm_file_path = "wasi_edge_impulse_onnx/target/wasm32-wasi/release/wasi_mobilenet_onnx.wasm"

        with open(wasm_file_path, "rb") as wasm_file:
            files = {'file': ("wasi_mobilenet_onnx.wasm", wasm_file, "application/wasm")}
            data_payload = {"name": "testi2"}

            response = requests.post(orchestrator_url, files=files, data=data_payload)

            if response.status_code in (200, 201):
                return jsonify({"status": "success", "message": response.text})
            else:
                return jsonify({"status": "fail", "message": f"Failed to reach orchestrator. Status code: {response.status_code}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error communicating with orchestrator: {e}"})

def get_file_structure(directory):
    file_structure = {}
    for root, dirs, files in os.walk(directory):
        rel_path = os.path.relpath(root, directory)
        file_structure[rel_path] = {
            "dirs": dirs,
            "files": files
        }
    return file_structure

@app.route("/file-structure")
def file_structure():
    structure = get_file_structure("/app")
    
    return render_template("file_structure.html", structure=structure)