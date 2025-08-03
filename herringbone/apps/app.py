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
    """Get the status of Herringbone apps"""
    k8s_admin = kube_functions.KubernetesAppAdmin()
    deployments = k8s_admin.get_deployments()

    status = {}
    for deployment in deployments:
        if deployment["images"][0] in list(image_comp.keys()):
            status[image_comp[deployment["images"][0]]] = "Deployed"

    return jsonify(status)

@app.route('/herringbone/apps/ready')
def apps_ready():

    return jsonify({"ready":True, "description":"herringbone/apps API is ready."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7002)