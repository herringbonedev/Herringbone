# Thank you for contributing!

## Issues

We use GitHub Issues as our project’s to-do list. They’re not just for bugs; they can also be feature requests, ideas, or general tasks we want to track. By adding labels, milestones, and linking them to pull requests, Issues help us plan work and keep the backlog organized.

We use GitHub labels to keep Issues and Pull Requests organized. Each Issue should have:

- One area label (what part of the system it touches)
- One type label (what kind of work it is)
- Optionally, a status label (extra context, e.g., “help wanted”)

| Label              | Description                                                                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `apps api`         | Issues and features for the **Apps/API layer** (endpoints, auth, pagination, query params, response schemas, UI integration).             |
| `argo dev`         | **Argo CD (dev environment)**: app-of-apps, Kustomize overlays, sync/health problems, rollout behavior, drift, and Argo configuration.    |
| `bug`              | A confirmed defect. Include repro steps, expected vs. actual behavior, logs/stack traces, and environment details.                        |
| `cd`               | **Continuous Delivery/Deployment** topics: ArgoCD release flows, Helm/Kustomize packaging, versioning, and deployment automation.         |
| `ci`               | **Continuous Integration** workflows (GitHub Actions): builds, tests, linting, caching, artifacts, matrix jobs.                           |
| `dev`              | Local/dev environment setup: Dockerfiles, Make targets, kind/minikube/GKE dev cluster configs, sample data, `.env` and bootstrap scripts. |
| `documentation`    | Docs and examples: README, API references, architecture diagrams, runbooks, onboarding guides, comments.                                  |
| `duplicate`        | This item duplicates another. Link to the canonical issue/PR and close this one.                                                          |
| `enhancement`      | A feature request or improvement to existing behavior, performance, or UX—**not** a bug.                                                  |
| `enrichment`       | The **Enrichment** component: model prompts, recon\_data schema, IOC extraction, KV fields, confidence scoring, and pipelines.            |
| `good first issue` | Small, well-scoped tasks with clear acceptance criteria—ideal for newcomers. Provide context and a pointer to the code path.              |
| `help wanted`      | Extra hands needed (design/implementation/testing). Provide context, expected outcome, and contact/mentors if possible.                   |
| `invalid`          | Not actionable (can’t reproduce, outside scope, or missing info). Explain why and suggest next steps if appropriate.                      |
| `logs api`         | **Logs service/API**: storage schema, queries/filters, pagination/cursors, retention, indexing, and search semantics.                     |
| `mind recon`       | The **Mind** (AI) service: model/container, Modelfile settings, JSON-only enforcement, rate limits, batch enrich, and health endpoints.   |
| `question`         | Clarifications or design decisions needed. Use for Q\&A threads that aren’t clearly bugs or enhancements.                                 |
| `receiver http`    | HTTP receiver ingest: payload validation, auth/headers, rate limits, backpressure, batching, and error handling.                          |
| `receiver tcp`     | TCP receiver ingest: framing/protocol parsing, connection lifecycle, throughput, retries, and resilience.                                 |
| `receiver udp`     | UDP receiver ingest: datagram handling, batching, drops, ordering, and performance tuning.                                                |
| `wontfix`          | Acknowledged but won’t be pursued (out of scope, not aligned with roadmap, or superseded). State reasoning and alternatives.              |
| `workflow`         | GitHub Actions **workflow plumbing** (jobs/steps, runners, concurrency, permissions). Pair with `ci` or `cd` to indicate intent.          |


## Documentation

## Code Review

## License