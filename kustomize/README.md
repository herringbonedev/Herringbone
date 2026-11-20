# Kubernetes overlay prerequisites

Every `kustomize/*/kustomization.yaml` must render with `kustomize build`. The PR Validation workflow checks all overlays.

All overlays target the `herringbone` namespace. Create the namespace before applying and provide a MongoDB service at `mongodb-headless.mongodb.svc.cluster.local:27017`.

Provision these Kubernetes Secrets in the `herringbone` namespace before deploying:

- `mongo-secret`: `username`, `password` (also referenced by existing core overlays).
- `herringbone-auth-secrets`: `jwt_secret`, `service_jwt_private_key`, `service_jwt_public_key`, `bootstrap_token`. Search also mounts its `jwt_secret`.
- `incidents-correlator-secrets` and `incidents-orchestrator-secrets`: each must have `service_token`, `service_jwt_public_key`, `jwt_secret`. Internal tokens require the appropriate service scopes.

Supply secrets using an external secret controller or `kubectl create secret generic --from-file=...` and local files. Never commit real secret values.

New services are internal ClusterIP services. The incident services depend on the existing `herringbone-logs-service` and `incidents-incidentset-service`. Expose user-facing APIs through a separately configured gateway/ingress, not these service definitions.
