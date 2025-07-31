from flask import Flask, request, jsonify
import kube_functions

app = Flask(__name__)

@app.route('/herringbone/apps/status', methods=['GET'])
def apps_status():
    k8s_admin = kube_functions.KubernetesAppAdmin()
    pods = k8s_admin.get_pods()
    services = k8s_admin.get_services()
    deployments = k8s_admin.get_deployments()
    return jsonify({"pods": pods, "services": services, "deployments": deployments})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7002)