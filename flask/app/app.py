from flask import Flask, render_template, jsonify, request, render_template_string
from python_scripts.download_model import download_model
from python_scripts.convert_to_onnx import convert_model
import requests
import logging
import subprocess
from contextlib import contextmanager
import os
from .SETUP import MODULES, DEVICES, DEPLOYMENTS
from .settings import WASMIOT_ORCHESTRATOR_URL
from .utils import pull_orchestrator_modules

#app.logger.info()

LAST_DEPLOYMENT = None

app = Flask(__name__, template_folder="../templates")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

@app.route("/debugging", methods=["GET"])
def devices():    
    a = []
    id = None
    for item in DEVICES:
        if item.get("name") == "raspi1":
            a.append(item.get("_id"))
        if item.get("name") == "raspi2":
            a.append(item.get("_id"))
    return jsonify(a)

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/run_pipeline", methods=["GET"])
def run_pipeline():
    try:
        download_model()
        convert_model()
        run_rust_code("rust_spectral_analysis")
        #run_rust_code("wasi_edge_impulse_onnx")
        upload_wasm("model", "wasi_edge_impulse_onnx/target/wasm32-wasi/release/wasi_mobilenet_onnx.wasm")
        upload_wasm("spec", "rust_spectral_analysis/target/wasm32-wasi/release/spectral_analysis.wasm")
        pull_orchestrator_modules()
        add_model_desc()
        add_spectral_analysis_desc()
        do_deployment()
        deploy()
        do_run()

        return "Pipeline executed successfully!", 200
    except Exception as e:
        print(f"Pipeline failed: {e}")
        return "Pipeline execution failed. Check server logs for details.", 500

def run_rust_code(rust_project_path):

    with change_directory(rust_project_path):
        build_result = subprocess.run(["cargo", "build", "--target", "wasm32-wasi", "--release"], capture_output=True, text=True)
        if build_result.returncode != 0:
            print("Rust build failed:")
            print(build_result.stderr)
            return False

        print("Rust build succeeded.")
        print(build_result.stdout)
        return True

def upload_wasm(name, wasm_file_path):
    try:
        #wasm_file_path = "wasi_edge_impulse_onnx/target/wasm32-wasi/release/wasi_mobilenet_onnx.wasm"

        with open(wasm_file_path, "rb") as wasm_file:
            files = {'file': ("wasi_mobilenet_onnx.wasm", wasm_file, "application/wasm")}
            data_payload = {"name": name}

            response = requests.post(WASMIOT_ORCHESTRATOR_URL + '/file/module', files=files, data=data_payload)

            if response.status_code in (200, 201):
                return jsonify({"status": "success", "message": response.text})
            else:
                return jsonify({"status": "fail", "message": f"Failed to reach orchestrator. Status code: {response.status_code}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error communicating with orchestrator: {e}"})

#@app.route("/add_module_desc", methods=["GET", "POST"])
def add_model_desc():
    model_id = None
    for item in MODULES:
        if item.get("name") == "model":
            model_id = item.get("_id")
            break

    if not model_id:
        return "Model ID not found", 404

    url = f"http://172.17.0.1:3000/file/module/{model_id}/upload"

    data = {
        "infer_predefined_paths[output]": (None, "integer"),
        "infer_predefined_paths[mountName]": (None, "accelerometer_data.csv"),
        "infer_predefined_paths[method]": (None, "POST"),
        "infer_predefined_paths[stage]": (None, "execution"),
        "infer_predefined_paths[mounts][0][name]": (None, "model.onnx"),
        "infer_predefined_paths[mounts][0][stage]": (None, "deployment"),
        "infer_predefined_paths[mounts][1][name]": (None, "accelerometer_data.csv"),
        "infer_predefined_paths[mounts][1][stage]": (None, "execution")
    }

    try:
        files = {
            "model.onnx": ("edge-impulse-model.onnx", open("wasi_edge_impulse_onnx/edge-impulse-model.onnx", "rb"), "application/octet-stream")
        }

        response = requests.post(url, files={**data, **files})

        if response.status_code == 200:
            return f"Request succeeded: {response.text}", 200
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code

    except FileNotFoundError:
        return "Model file not found: edge-impulse-model.onnx", 500

    except Exception as e:
        return f"An error occurred: {str(e)}", 500
    
#@app.route("/add_module_desc2", methods=["GET", "POST"])
def add_spectral_analysis_desc():
    spec_id = None
    for item in MODULES:
        if item.get("name") == "spec":
            spec_id = item.get("_id")
            break
    if not spec_id:
        return "Spec ID not found", 404

    url = f"http://172.17.0.1:3000/file/module/{spec_id}/upload"

    data = {
        "testailu[mountName]": (None, "accelerometer_data.csv"),
        "testailu[method]": (None, "GET"),
        "testailu[stage]": (None, "output"),
        "testailu[output]": (None, "image/jpg"),
        "testailu[mounts][0][name]": (None, "accelerometer_data.csv"),
        "testailu[mounts][0][stage]": (None, "output"),
        "accelerometer_data.csv": (None, "undefined")
    }

    try:
        response = requests.post(url, files=data)

        if response.status_code == 200:
            return f"Request succeeded: {response.text}", 200
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code

    except Exception as e:
        return f"An error occurred: {str(e)}", 500

#@app.route("/do_deployment", methods=["GET", "POST"])
def do_deployment():
    global LAST_DEPLOYMENT

    from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

    url = WASMIOT_ORCHESTRATOR_URL + "/file/manifest"

    raspi1 = None
    raspi2 = None

    for item in DEVICES:
        if item.get("name") == "raspi1":
            raspi1 = item.get("_id")
        if item.get("name") == "raspi2":
            raspi2 = item.get("_id")

    model_id = None
    spec_id = None

    for item in MODULES:
        if item.get("name") == "spec":
            spec_id = item.get("_id")
        if item.get("name") == "model":
            model_id = item.get("_id")

    payload = {
        "name": "asd1233",
        "proc0": f'{{"device":"{raspi1}","module":"{spec_id}","func":"testailu"}}',
        "proc1": f'{{"device":"{raspi2}","module":"{model_id}","func":"infer_predefined_paths"}}',
        "sequence": [
            {"device": raspi1, "module": spec_id, "func": "testailu"},
            {"device": raspi2, "module": model_id, "func": "infer_predefined_paths"}
        ]
    }

    try:
        response = requests.post(url, json=payload)

        if response.status_code in [200, 201]:
            LAST_DEPLOYMENT = response.text.strip('"')
            return f"Request succeeded: {response.text}", response.status_code
        else:
            return f"Request failed with status code {response.status_code}: {response.text}", response.status_code


    except Exception as e:
        return f"An error occurred: {str(e)}", 500

#@app.route("/deploy", methods=["GET", "POST"])
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
            app.logger.info(response.text)
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

    #miten edge impulse mallit soveltuvat käytettäväksi liquidAI:n arkkitehtuurilla?

    # prosessointiblokin muuttaminen rustiksi
    # ja sellaseen muotoon että se toimii
    # orkestraattorilla 
    # tutkimuskysymyksiin: mitä oletin
    # pitää alkaa tehdä implementointiosiota
    # pohdintaosio: pitää peilata taakse päin

    # jos jotain ei voi toteuttaa, niin voi perustella ettei mene gradun tavoiteaikaan


    5555