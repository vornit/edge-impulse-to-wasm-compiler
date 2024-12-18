from .settings import WASMIOT_ORCHESTRATOR_URL
import requests
from .SETUP import update_modules, update_devices, update_deployments

def pull_orchestrator_modules():
    url = f"{WASMIOT_ORCHESTRATOR_URL}/file/module"
    res = requests.get(url)
    res.raise_for_status()

    if data := res.json():
        update_modules(data)
    else:
        raise ValueError(f"Error getting modules from {url}")

def pull_orchestrator_devices():

    url = f"{WASMIOT_ORCHESTRATOR_URL}/file/device"
    res = requests.get(url)
    res.raise_for_status()

    if data := res.json():
        update_devices(data)
    else:
        raise ValueError(f"Error getting devices from {url}")
    
def pull_orchestrator_deployments():

    url = f"{WASMIOT_ORCHESTRATOR_URL}/file/manifest"
    res = requests.get(url)
    res.raise_for_status()

    if data := res.json():
        update_deployments(data)
    else:
        raise ValueError(f"Error getting devices from {url}")