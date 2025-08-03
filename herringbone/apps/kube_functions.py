from kubernetes import client, config

class KubernetesAppAdmin():
    def __init__(self, namespace='herringbone'):

        config.load_incluster_config()
        self.v1 = client.CoreV1Api()
        self.namespace = namespace
    
    def get_deployments(self):
        try:
            apps_v1 = client.AppsV1Api()
            deployments = apps_v1.list_namespaced_deployment(self.namespace)

            result = []
            for deployment in deployments.items:
                dep_name = deployment.metadata.name
                containers = deployment.spec.template.spec.containers
                images = [container.image for container in containers]
                result.append({
                    "images": images
                })
                    
            return result

        except client.rest.ApiException as e:
            raise RuntimeError(f"Failed to list deployments: {e}")
