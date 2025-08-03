from flask import Flask, request, jsonify
import kube_functions

app = Flask(__name__)

image_comp = {
    "quay.io/herringbone/enrichment:latest": "enrichment",
    "quay.io/herringbone/herringbone-apps:latest": "herringbone-apps",
    "quay.io/herringbone/mind_recon:latest": "mind_recon",
    "quay.io/herringbone/receiver:latest": "receiver",
}

@app.route('/herringbone/apps/status', methods=['GET'])
def apps_status():
    """Get the status of Herringbone apps
    """

    k8s_admin = kube_functions.KubernetesAppAdmin()
    deployments = k8s_admin.get_deployments()

    status = {}
    for deployment in deployments:
        if deployment["images"][0] in list(image_comp.keys()):
            status[image_comp[deployment["images"][0]]] = "Deployed"

    return jsonify(status)

#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for healthz and readyz
#

@app.route('/herringbone/apps/livez', methods=['GET'])
def liveness_probe():
    """Checks if the API is up and running.
    """

    return 'OK', 200

@app.route('/herringbone/apps/readyz', methods=['GET'])
def readiness_check():
    """Readiness check to see if the service is able to serve data
    from the Kubernetes API.
    """
    
    k8s_admin = kube_functions.KubernetesAppAdmin()
    if k8s_admin.readyz():
        return jsonify({"ready": True}), 200
    else:
        return jsonify({"ready": False}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7002)