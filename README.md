# Herringbone
Bite sized security tool components for you to stack however you want!

### MongoDB

For this beta version of the Herringbone SOC a MongoDB instance must be provided. To keep
things simple all you need to do is provide a Secret with the MongoDB credentials. If you need
to modify the connection info then you will need to modify the `/kustomize/<app_name>/deployment.yaml`

Secret template (must be in the `herringbone` namespace with the name `mongo-secret`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mongo-secret
  namespace: herringbone
type: Opaque
data:
  username: YWRtaW4=        # base64 for 'admin'
  password: Y2hhbmdlbWU=    # base64 for 'changeme'
```
### ArgoCD

Beta is leveraging ArgoCD as the application deployment and scalability engine. You will need to have
an ArgoCD instance available on the target cluster to deploy Herringbone beta.

For setup instructions, see: https://argo-cd.readthedocs.io

## Application deployments

You can deploy any combination of applications from the kustomize directory. Herringbone is designed with modularity in mind; allowing you to spin up only the components of the SOC you need. Each application is interoperable but independently deployable, enabling flexible scaling and streamlined operations.

For example, if your goal is simply to collect logs via an HTTP endpoint and view them through a user interface, you can deploy just the HTTP receiver application and the herringbone UI. No unnecessary services—just what you need, when you need it.

You can always deploy additional applications later. All components are built to be plug-and-play. Just add the application in ArgoCD, deploy from its respective kustomize directory, and it will integrate automatically with the rest of the system.

### Mind

### Receivers

### Enrichment

### Herringbone UI