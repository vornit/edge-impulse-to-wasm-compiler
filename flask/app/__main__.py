from .app import app
from .utils import pull_orchestrator_modules, pull_orchestrator_devices, pull_orchestrator_deployments
if __name__ == "__main__":

    try:
        pull_orchestrator_devices()
        pull_orchestrator_modules()
        pull_orchestrator_deployments()
    except:
        pass
    
    app.run(host="0.0.0.0", port=8080)