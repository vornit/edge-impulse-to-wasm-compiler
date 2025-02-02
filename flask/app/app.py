from flask import Flask, render_template, jsonify, request, stream_with_context, Response
from python_scripts.download_model import download_model
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

app = Flask(__name__, template_folder="../templates")

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


@app.route("/run_pipeline_progress", methods=["GET"])
def run_pipeline_progress():
    def generate():
        global progress_log
        progress_log = {
            "download_model": False,
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

            convert_model()
            yield update_progress_log("convert_model")

            if not os.path.exists("modules/target/wasm32-wasi/release/spectral_analysis.wasm"):
                run_rust_code("modules/rust_spectral_analysis")
            yield update_progress_log("run_rust_spectral_analysis")

            if not os.path.exists("modules/target/wasm32-wasi/release/wasi_edge_impulse_onnx.wasm"):
                run_rust_code("modules/wasi_edge_impulse_onnx")
            yield update_progress_log("run_rust_model")

            if not os.path.exists("modules/target/wasm32-wasi/release/save_accelerometer_data.wasm"):
                run_rust_code("modules/save_accelerometer_data")
            yield update_progress_log("run_save_data")

            upload_wasm("model", "modules/target/wasm32-wasi/release/wasi_edge_impulse_onnx.wasm")
            yield update_progress_log("upload_wasm_model")

            upload_wasm("spec", "modules/target/wasm32-wasi/release/spectral_analysis.wasm")
            yield update_progress_log("upload_wasm_spec")

            upload_wasm("save", "modules/target/wasm32-wasi/release/save_accelerometer_data.wasm")
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
        build_result = subprocess.run(["cargo", "build", "--target", "wasm32-wasi", "--release"], capture_output=True, text=True)
        
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

    url = f"http://172.17.0.1:3000/file/module/{module_id}/upload"

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

    from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

    url = WASMIOT_ORCHESTRATOR_URL + "/file/manifest"

    device1 = None
    device2 = None
    device3 = None

    for item in DEVICES:
        if item.get("name") == "device1":
            device1 = item.get("_id")
        if item.get("name") == "device2":
            device2 = item.get("_id")
        if item.get("name") == "device3":
            device3 = item.get("_id")

    model_id = None
    spec_id = None
    save_id = None

    for item in MODULES:
        if item.get("name") == "spec":
            spec_id = item.get("_id")
        if item.get("name") == "model":
            model_id = item.get("_id")
        if item.get("name") == "save":
            save_id = item.get("_id")

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

        logger.info("Response:")
        logger.info(response)

        if response.status_code in [200, 201]:
            LAST_DEPLOYMENT = response.text.strip('"')
            return f"Request succeeded: {response.text}", response.status_code
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code


    except Exception as e:
        return f"An error occurred: {str(e)}", 500


def deploy():
    spec_id = None
    for item in MODULES:
        if item.get("name") == "spec":
            spec_id = item.get("_id")
            break

    url = "http://172.17.0.1:3000/file/manifest/" + LAST_DEPLOYMENT

    data = {
        "id": LAST_DEPLOYMENT,
    }
    
    try:
        response = requests.post(url, data=data)

        if response.status_code in [200, 201]:
            return f"Request succeeded: {response.text}", response.status_code
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code

    except Exception as e:
        return f"An error occurred: {str(e)}", 500


def do_run():
    url = "http://172.17.0.1:3000/execute/" + LAST_DEPLOYMENT

    data = {
        "id": LAST_DEPLOYMENT,
    }
    
    try:
        response = requests.post(url, data=data)

        if response.status_code in [200, 201]:
            return f"Request succeeded: {response.text}", response.status_code
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code


    except Exception as e:
        return f"An error occurred: {str(e)}", 500


@app.route("/manifest-request")
def manifest_request():
    try:
        orchestrator_url = 'http://172.17.0.1:3000/file/manifest'
        response = requests.get(orchestrator_url)
        
        if response.status_code == 200:
            try:
                response_json = response.json()
                return jsonify(response_json), 200
            except ValueError:
                return jsonify({"message": response.text}), 200
        else:
            return jsonify({
                "status": "fail",
                "message": f"Failed to reach orchestrator. Status code: {response.status_code}"
            }), response.status_code
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error communicating with orchestrator: {e}"
        }), 500


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


@app.route('/upload', methods=['GET'])
def upload_page():
    global LAST_DEPLOYMENT

    for item in DEPLOYMENTS:
        if item.get("name") == "asd1233":
            LAST_DEPLOYMENT = item.get("_id")
            break
    
    return render_template('index2.html', last_deployment=LAST_DEPLOYMENT)


@app.route('/csv')
def display_csv_as_text():
    csv_url = 'http://172.15.0.4:5000/module_results/model/probabilities.csv'
    
    try:
        response = requests.get(csv_url)
        response.raise_for_status()
        
        csv_content = response.text.splitlines()
        csv_reader = csv.reader(csv_content)
        
        data = [float(cell) for row in csv_reader for cell in row]
        
        return f"[{', '.join(map(str, data))}]"
    
    except requests.exceptions.RequestException as e:
        return f"Error loading CSV file: {e}", 500


@app.route('/get_text', methods=['GET'])
def get_text():
    csv_url = 'http://172.15.0.4:5000/module_results/model/probabilities.csv'
    
    try:
        response = requests.get(csv_url)
        response.raise_for_status()
        
        csv_content = response.text.splitlines()
        csv_reader = csv.reader(csv_content)
        
        data = [float(cell) for row in csv_reader for cell in row]

        return f"[{', '.join(map(str, data))}]"
    
    except requests.exceptions.RequestException as e:
        return f"Error loading CSV file: {e}", 500