MODULES: list = []
DEVICES: list = []
DEPLOYMENTS: list = []

def get_modules() -> list:
    return MODULES

def get_devices() -> list:
    return DEVICES

def get_deployments() -> list:
    return DEPLOYMENTS

def update_modules(data: list):
    MODULES.clear()
    MODULES.extend(data)

def update_devices(data: list):
    DEVICES.clear()
    DEVICES.extend(data)

def update_deployments(data: list):
    DEPLOYMENTS.clear()
    DEPLOYMENTS.extend(data)

