from flask import Flask, render_template, jsonify, request, stream_with_context, Response
from python_scripts.download_model import download_model, get_class_names
from python_scripts.convert_to_onnx import convert_model
import requests
import logging
import subprocess
from contextlib import contextmanager
import os
from .SETUP import MODULES, DEVICES, DEPLOYMENTS
from .settings import WASMIOT_ORCHESTRATOR_URL
from .utils import pull_orchestrator_modules, pull_orchestrator_devices, pull_orchestrator_deployments
import csv

#app.logger.info()

app = Flask(__name__, template_folder="../templates", static_folder="../static")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

pull_orchestrator_devices()
pull_orchestrator_modules()
pull_orchestrator_deployments()

LAST_DEPLOYMENT = None

progress_log = {}

def update_progress_log(step):
    global progress_log
    progress_log[step] = True
    return f"data: {step}\n\n"


@app.route("/execute_deployment", methods=["GET"])
def execute_deployment():
    return render_template('index3.html')


@app.route("/run_pipeline_progress", methods=["GET"])
def run_pipeline_progress():
    def generate():
        global progress_log
        progress_log = {
            "download_model": False,
            "get_class_names": False,
            "convert_model": False,
            "run_rust_spectral_analysis": False,
            "run_rust_model": False,
            "run_save_data": False,
            "upload_wasm_model": False,
            "upload_wasm_spec": False,
            "upload_save_data": False,
            "add_model_desc": False,
            "add_spectral_analysis_desc": False,
            "add_save_data_desc": False,
            "do_deployment": False,
            "deploy": False,
        }

        try:
            pull_orchestrator_devices()

            download_model()
            yield update_progress_log("download_model")

            get_class_names()
            yield update_progress_log("get_class_names")

            convert_model()
            yield update_progress_log("convert_model")

            if not os.path.exists("modules/target/wasm32-wasip1/release/spectral_analysis.wasm"):
                run_rust_code("modules/rust_spectral_analysis")
            yield update_progress_log("run_rust_spectral_analysis")

            if not os.path.exists("modules/target/wasm32-wasip1/release/wasi_edge_impulse_onnx.wasm"):
                run_rust_code("modules/wasi_edge_impulse_onnx")
            yield update_progress_log("run_rust_model")

            if not os.path.exists("modules/target/wasm32-wasip1/release/save_accelerometer_data.wasm"):
                run_rust_code("modules/save_accelerometer_data")
            yield update_progress_log("run_save_data")

            upload_wasm("model", "modules/target/wasm32-wasip1/release/wasi_edge_impulse_onnx.wasm")
            yield update_progress_log("upload_wasm_model")

            upload_wasm("spec", "modules/target/wasm32-wasip1/release/spectral_analysis.wasm")
            yield update_progress_log("upload_wasm_spec")

            upload_wasm("save", "modules/target/wasm32-wasip1/release/save_accelerometer_data.wasm")
            yield update_progress_log("upload_save_data")

            pull_orchestrator_modules()

            add_desc(
                "model",
                {
                    "model.onnx": (
                        "model.onnx",
                        open("modules/wasi_edge_impulse_onnx/model.onnx", "rb"),
                        "application/octet-stream"
                    ),
                    "accelerometer_data.csv": (None, "undefined"),
                    "probabilities.csv": (None, "undefined")
                },
                {
                    "infer_predefined_paths[mountName]": "probabilities.csv",
                    "infer_predefined_paths[method]": "POST",
                    "infer_predefined_paths[stage]": "output",
                    "infer_predefined_paths[output]": "image/jpg",
                    "infer_predefined_paths[mounts][0][name]": "model.onnx",
                    "infer_predefined_paths[mounts][0][stage]": "deployment",
                    "infer_predefined_paths[mounts][1][name]": "features.csv",
                    "infer_predefined_paths[mounts][1][stage]": "execution",
                    "infer_predefined_paths[mounts][2][name]": "probabilities.csv",
                    "infer_predefined_paths[mounts][2][stage]": "output",
                }
            )
            yield update_progress_log("add_model_desc")

            add_desc(
                "spec",
                {
                    "raw_data.csv": (None, "undefined"),
                    "accelerometer_data.csv": (None, "undefined"),
                },
                {
                    "testailu[mountName]": "features.csv",
                    "testailu[method]": "POST",
                    "testailu[stage]": "output",
                    "testailu[output]": "image/jpg",
                    "testailu[mounts][0][name]": "accelerometer_data.csv",
                    "testailu[mounts][0][stage]": "execution",
                    "testailu[mounts][1][name]": "features.csv",
                    "testailu[mounts][1][stage]": "output",
                }
            )
            yield update_progress_log("add_spectral_analysis_desc")
#
            add_desc(
                "save",
                {
                    "accelerometer_data.csv": (None, "undefined"),
                },
                {
                    "save_sensor_data[mountName]": "accelerometer_data.csv",
                    "save_sensor_data[method]": "GET",
                    "save_sensor_data[stage]": "output",
                    "save_sensor_data[output]": "image/jpg",
                    "alloc[param0]": "integer",
                    "alloc[output]": "integer",
                    "alloc[mountName]": "",
                    "alloc[method]": "GET",
                    "save_sensor_data[mounts][0][name]": "accelerometer_data.csv",
                    "save_sensor_data[mounts][0][stage]": "output",
                }
            )
            yield update_progress_log("add_save_data_desc")

            do_deployment()
            yield update_progress_log("do_deployment")

            deploy()
            yield update_progress_log("deploy")

            pull_orchestrator_deployments()

            yield "event: end\ndata: Pipeline executed successfully!\n\n"

        except Exception as e:
            error_step = [step for step, completed in progress_log.items() if not completed][0]
            yield f"event: fail\ndata: {error_step}\n\n"
            yield f"event: error\ndata: Pipeline execution failed: {e}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")


@contextmanager
def change_directory(directory):
    original_directory = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(original_directory)


@app.route("/devices", methods=["GET"])
def devices2():    
    return jsonify(DEVICES)


@app.route("/modules", methods=["GET"])
def modules2():    
    return jsonify(MODULES)


@app.route("/deployments", methods=["GET"])
def deployments2():    
    return jsonify(DEPLOYMENTS)


@app.route('/', methods=["GET"])
def index():        
    return render_template('index.html')


def run_rust_code(rust_project_path):
    with change_directory(rust_project_path):
        build_result = subprocess.run(["cargo", "build", "--target", "wasm32-wasip1", "--release"], capture_output=True, text=True)

        
        if build_result.returncode != 0:
            error_message = f"Rust build failed in {rust_project_path}:\n{build_result.stderr}"
            print(error_message)
            raise Exception(error_message)

        print(f"Rust build succeeded in {rust_project_path}.")
        print(build_result.stdout)


def upload_wasm(name, wasm_file_path):
    try:
        with open(wasm_file_path, "rb") as wasm_file:
            files = {'file': (os.path.basename(wasm_file_path), wasm_file, "application/wasm")}
            data_payload = {"name": name}

            response = requests.post(WASMIOT_ORCHESTRATOR_URL + '/file/module', files=files, data=data_payload)

            if response.status_code in (200, 201):
                print(f"Successfully uploaded {name} to orchestrator.")
            else:
                error_message = f"Failed to upload {name}: Status code {response.status_code}, {response.text}"
                print(error_message)
                raise Exception(error_message)

    except FileNotFoundError:
        error_message = f"WASM file not found: {wasm_file_path}"
        print(error_message)
        raise Exception(error_message)

    except Exception as e:
        error_message = f"Error uploading {name}: {e}"
        print(error_message)
        raise Exception(error_message)


def add_desc(module_name, files, data):
    module_id = None
    for item in MODULES:
        if item.get("name") == module_name:
            module_id = item.get("_id")
            break

    if not module_id:
        error_message = f"Module ID for '{module_name}' not found"
        print(error_message)
        raise Exception(error_message)

    url = f"{WASMIOT_ORCHESTRATOR_URL}/file/module/{module_id}/upload"

    try:
        response = requests.post(url, files=files, data=data)

        if response.status_code == 200:
            print(f"Module description for '{module_name}' added successfully: {response.text}")
        else:
            error_message = f"Failed to add module description for '{module_name}': Status code {response.status_code}, {response.text}"
            print(error_message)
            raise Exception(error_message)

    except FileNotFoundError:
        error_message = f"File not found: {files}"
        print(error_message)
        raise Exception(error_message)

    except Exception as e:
        error_message = f"An error occurred while adding description for '{module_name}': {str(e)}"
        print(error_message)
        raise Exception(error_message)


def do_deployment():
    global LAST_DEPLOYMENT

    url = WASMIOT_ORCHESTRATOR_URL + "/file/manifest"

    device1, device2, device3 = None, None, None

    for item in DEVICES:
        if item.get("name") == "device1":
            device1 = item.get("_id")
        if item.get("name") == "device2":
            device2 = item.get("_id")
        if item.get("name") == "device3":
            device3 = item.get("_id")

    model_id, spec_id, save_id = None, None, None

    for item in MODULES:
        if item.get("name") == "spec":
            spec_id = item.get("_id")
        if item.get("name") == "model":
            model_id = item.get("_id")
        if item.get("name") == "save":
            save_id = item.get("_id")

    if not all([device1, device2, device3, model_id, spec_id, save_id]):
        error_message = "One or more required devices or modules not found."
        logger.error(error_message)
        raise Exception(error_message)

    payload = {
        "name": "asd1233",
        "proc0": f'{{"device":"{device3}","module":"{save_id}","func":"save_sensor_data"}}',
        "proc1": f'{{"device":"{device1}","module":"{spec_id}","func":"testailu"}}',
        "proc2": f'{{"device":"{device2}","module":"{model_id}","func":"infer_predefined_paths"}}',
        "sequence": [
            {"device": device3, "module": save_id, "func": "save_sensor_data"},
            {"device": device1, "module": spec_id, "func": "testailu"},
            {"device": device2, "module": model_id, "func": "infer_predefined_paths"},
        ]
    }

    try:
        response = requests.post(url, json=payload)

        if response.status_code in [200, 201]:
            LAST_DEPLOYMENT = response.text.strip('"')
            return f"Request succeeded: {response.text}", response.status_code
        else:
            error_message = f"Deployment failed: Status code {response.status_code}, {response.text}"
            print(error_message)
            raise Exception(error_message)

    except Exception as e:
        error_message = f"Error during deployment: {e}"
        print(error_message)
        raise Exception(error_message)


def deploy():
    if not LAST_DEPLOYMENT:
        error_message = "No deployment ID found for deployment."
        print(error_message)
        raise Exception(error_message)

    url = f"{WASMIOT_ORCHESTRATOR_URL}/file/manifest/{LAST_DEPLOYMENT}"
    data = {"id": LAST_DEPLOYMENT}    

    try:
        response = requests.post(url, data=data)

        if response.status_code in [200, 201]:
            print(f"Deployment was successful: {response.text}")
            return f"Request succeeded: {response.text}", response.status_code
        else:
            error_message = f"Deployment failed: Status code {response.status_code}, {response.text}"
            print(error_message)
            raise Exception(error_message)

    except Exception as e:
        error_message = f"Deployment failed: {e}"
        print(error_message)
        raise Exception(error_message)

@app.route('/do_run', methods=['POST'])
def do_run():
    if not LAST_DEPLOYMENT:
        return 'No deployment found.', 400

    url = f"{WASMIOT_ORCHESTRATOR_URL}/execute/{LAST_DEPLOYMENT}"
    data = {"id": LAST_DEPLOYMENT}
    
    try:
        response = requests.post(url, data=data)

        if response.status_code in [200, 201]:
            probabilities = get_text()
            
            if isinstance(probabilities, tuple):
                return probabilities

            return probabilities, 200, {'Content-Type': 'text/plain'}
        else:
            return f"Execution failed: Status code: {response.status_code}", response.status_code

    except Exception as e:
        logger.error(f"Error in do_run: {e}")
        return f"Server error: {e}", 500


@app.route("/manifest-request")
def manifest_request():
    orchestrator_url = f"{WASMIOT_ORCHESTRATOR_URL}/file/manifest"
    
    try:
        response = requests.get(orchestrator_url)
        response.raise_for_status()
        
        try:
            response_json = response.json()
            return jsonify(response_json), 200
        except ValueError:
            error_message = "Failed to parse JSON from orchestrator response."
            print(error_message)
            raise Exception(error_message)


    except Exception as e:
        error_message = f"Failed to communicate with orchestrator: {e}"
        print(error_message)
        raise Exception(error_message)

@app.route('/file-structure')
def file_structure():
    structure = {}
    for root, dirs, files in os.walk('.'):
        structure[root] = {'dirs': dirs, 'files': files}
    return jsonify(structure)

@app.route('/upload', methods=['GET'])
def upload_page():
    global LAST_DEPLOYMENT

    for item in DEPLOYMENTS:
        if item.get("name") == "asd1233":
            LAST_DEPLOYMENT = item.get("_id")
            break
    
    return render_template('index2.html', last_deployment=LAST_DEPLOYMENT)


def get_text():
    csv_url = 'http://172.15.0.22:5000/module_results/model/probabilities.csv'
    try:
        response = requests.get(csv_url)
        response.raise_for_status()
        
        csv_content = response.text.splitlines()
        csv_reader = csv.DictReader(csv_content)

        result = []
        for row in csv_reader:
            class_name = row['class']
            probability = row['probability']
            result.append(f"{class_name}: {probability}")

        return f"Probabilities:\n" + "\n".join(result)
    
    except Exception as e:
        logger.error(f"Error loading CSV file from {csv_url}: {e}")
        return f"Error loading CSV file: {e}", 500
