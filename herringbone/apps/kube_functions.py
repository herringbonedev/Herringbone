from kubernetes import client, config

class KubernetesAppAdmin():
    def __init__(self, namespace='herringbone'):
        config.load_incluster_config()
        self.v1 = client.CoreV1Api()
        self.namespace = namespace

    def get_pods(self):
        try:
            pods = self.v1.list_namespaced_pod(self.namespace)
            return [pod.metadata.name for pod in pods.items]
        except client.rest.ApiException as e:
            raise RuntimeError(f"Failed to list pods: {e}")

    def get_services(self):
        try:
            services = self.v1.list_namespaced_service(self.namespace)
            return [service.metadata.name for service in services.items]
        except client.rest.ApiException as e:
            raise RuntimeError(f"Failed to list services: {e}")
    
    def get_deployments(self):
        try:
            apps_v1 = client.AppsV1Api()
            deployments = apps_v1.list_namespaced_deployment(self.namespace)
            return [deployment.metadata.name for deployment in deployments.items]
        except client.rest.ApiException as e:
            raise RuntimeError(f"Failed to list deployments: {e}")