from flask import Flask, request, jsonify
import kube_functions

app = Flask(__name__)

@app.route('/herringbone/apps/status', methods=['GET'])
def apps_status():
    k8s_admin = kube_functions.KubernetesAppAdmin()
    pods = k8s_admin.get_pods()
    services = k8s_admin.get_services()
    return jsonify({"pods": pods, "services": services})

    
