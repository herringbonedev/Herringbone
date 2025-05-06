# The Receiver

Collecting logs from applications and endpoints is easy with the receiver service.

#### Setup a receiver

Select a receiver type to fit your log collection needs

Receiver types:
- TCP
- UDP

The receiver type is set by the RECEIVER_TYPE environment variable of the application host. In the
example we use Docker to start up one UDP receiver container on port 7002.

```bash
docker run -p 7002:7002/udp -e RECEIVER_TYPE=UDP receiver:beta-1.0.0
```
The receiver container port is 7002 for all types.

Add in Kubernetes Horizontal Pod Autoscaling to your deployment and make it scalable! See the example below of
a more advanced real world UDP receiver deployment.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: receiver-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: receiver
  template:
    metadata:
      labels:
        app: receiver
    spec:
      containers:
      - name: receiver
        image: receiver:beta-1.0.0
        ports:
        - containerPort: 7002
          protocol: UDP
        env:
        - name: RECEIVER_TYPE
          value: "UDP"
        resources:
          requests:
            memory: "128Mi"
          limits:
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: receiver-service
spec:
  selector:
    app: receiver
  type: NodePort
  ports:
  - protocol: UDP
    port: 7002
    targetPort: 7002
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: receiver-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: receiver-deployment
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 60
```
