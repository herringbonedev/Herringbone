# API Development guidelines

Here you will find the **required** rules for developing Herringbone microservices that have API endpoints.

*All of the following sections must be included for a valid microservice*

### Liveness probes

A liveness probe is a Kubernetes health check that tells the kubelet whether a container is still running properly, so it can restart it if it’s stuck or dead.

Example of a liveness probe.

```python
@app.route('example/livez', methods=['GET'])
def liveness_probe():
    """Checks if the API is up and running.
    """

    return 'OK', 200
```

### Readiness probes

A readiness probe is a health check that tells Kubernetes whether a container is ready to serve requests

Example of a readiness probe.

```python
@app.route('example/readyz', methods=['GET'])
def readiness_check():
    """Readiness check to see if the service is able to serve data.
    """
    
    some_obj = SomeObject()

    if some_obj.is_ready_to_serve():
        return jsonify({"ready": True}), 200
    else:
        return jsonify({"ready": False}), 503
```

### Where to put the probe endpoints

1. Routes for liveness and readiness should always be `livez` and `readyz` respectively.

2. Must be the last routes in the API microservice.

3. Must be partitioned as follows:

```python
#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for healthz and readyz
#

@app.route('example/livez', methods=['GET'])
def liveness_probe():
    """Checks if the API is up and running.
    """

    return 'OK', 200

@app.route('example/readyz', methods=['GET'])
def readiness_check():
    """Readiness check to see if the service is able to serve data.
    """
    
    some_obj = SomeObject()

    if some_obj.is_ready_to_serve():
        return jsonify({"ready": True}), 200
    else:
        return jsonify({"ready": False}), 503
```

### Kustomization deployment manifest

To add to your deployment.yaml kustomization manifest use the following example:

```yaml
livenessProbe:
httpGet:
    path: example/livez
    port: 7002
initialDelaySeconds: 5
periodSeconds: 10
readinessProbe:
httpGet:
    path: example/readyz
    port: 7002
initialDelaySeconds: 10
periodSeconds: 10
```