# Thank you for contributing!

## Issues

We use GitHub Issues as our project’s to-do list. They’re not just for bugs; they can also be feature requests, ideas, or general tasks we want to track. By adding labels, milestones, and linking them to pull requests, Issues help us plan work and keep the backlog organized.

We use GitHub labels to keep Issues and Pull Requests organized. Each Issue should have:

- One area label (what part of the system it touches)
- One type label (what kind of work it is)
- Optionally, a status label (extra context, e.g., “help wanted”)

#### Area Labels

| Label           | Description                                                                                                       |
| --------------- | ----------------------------------------------------------------------------------------------------------------- |
| `apps api`      | Issues and features for the **Apps/API layer** (endpoints, auth, pagination, queries, responses, UI integration). |
| `argo dev`      | **Argo CD (dev environment)**: app-of-apps, Kustomize overlays, sync/health, rollouts, drift detection.           |
| `cd`            | **Continuous Delivery/Deployment** topics: ArgoCD release flows, Helm/Kustomize packaging, deployments.           |
| `ci`            | **Continuous Integration** workflows: GitHub Actions builds, tests, linting, caching, and pipelines.              |
| `dev`           | Local/dev environment setup: Dockerfiles, Minikube/kind/GKE dev clusters, `.env` setup.                           |
| `enrichment`    | The **Enrichment** service: model prompts, recon\_data schema, IOC extraction, KV fields, pipelines.              |
| `logs api`      | **Logs service/API**: schema, queries/filters, pagination, retention, and search functionality.                   |
| `mind recon`    | The **Mind AI** service: model/container config, Modelfile, JSON-only enforcement, batch enrich, health checks.   |
| `receiver http` | HTTP receiver ingest: payload validation, headers, rate limiting, batching, errors.                               |
| `receiver tcp`  | TCP receiver ingest: framing/protocol parsing, connection handling, throughput.                                   |
| `receiver udp`  | UDP receiver ingest: datagram handling, packet drops, ordering, resilience.                                       |
| `workflow`      | GitHub Actions **workflow plumbing**: runners, permissions, job orchestration.                                    |

#### Type Labels

| Label           | Description                                                                                         |
| --------------- | --------------------------------------------------------------------------------------------------- |
| `bug`           | A confirmed defect. Provide repro steps, expected vs actual results, logs, and environment details. |
| `documentation` | Improvements or additions to project documentation, guides, or comments.                            |
| `enhancement`   | A new feature or improvement to existing behavior (not a bug).                                      |
| `question`      | Clarifications, design discussions, or general Q\&A.                                                |

#### Status Labels

| Label              | Description                                                                   |
| ------------------ | ----------------------------------------------------------------------------- |
| `good first issue` | Small, well-scoped, beginner-friendly tasks with clear acceptance criteria.   |
| `help wanted`      | Maintainers request extra help (design, implementation, or testing).          |
| `duplicate`        | Duplicate of another Issue/PR — should be closed and linked.                  |
| `invalid`          | Not valid or not actionable (cannot reproduce, missing info, out of scope).   |
| `wontfix`          | Acknowledged but won’t be addressed (out of scope, not aligned with roadmap). |

## Documentation

## Code Review

## License