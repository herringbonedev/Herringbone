# Herringbone

A cloud-native engine for log management, detection rules, and security intelligence.

[![DetectionEngine Ruleset](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine-ruleset.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine-ruleset.yml)
[![Enrichment](https://github.com/herringbonedev/Herringbone/actions/workflows/enrichment.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/enrichment.yml)
[![Herringbone Apps](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-apps.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-apps.yml)
[![Herringbone Logs](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-logs.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-logs.yml)
[![Receiver](https://github.com/herringbonedev/Herringbone/actions/workflows/receiver.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/receiver.yml)

## Summary

Herringbone is a flexible, cloud-native platform for log management and security detection. Inspired by the defensive herringbone formation, it provides layered coverage where each component strengthens the whole: log receivers capture data from any source, the detection engine scans and detects threats directly from MongoDB, enrichment adds AI-driven context, and APIs open everything for integration. Deployable on Kubernetes, serverless, or cloud environments, Herringbone adapts to different needs; from straightforward log management to advanced, intelligence-driven security.

## How it works

Herringbone includes all the core components you’d expect in modern cybersecurity and log management tooling. Each component is designed as an independent **building block** that can be enabled, disabled, or scaled to meet specific needs. This modular approach gives engineering teams a level of granular control and flexibility that many other solutions don’t offer.

No component in Herringbone building block is tightly coupled to another, allowing you to deploy each one independently and assemble a fully customized solution tailored to your needs.

During its beta phase, Herringbone relies on a small set of critical infrastructure components. These dependencies are planned to be reduced or fully removed in future releases:

- MongoDB
- Kubernetes (built on vanilla Kubernetes, with support for distributions such as OpenShift, GKE, and others)
- ArgoCD
- NGINX Ingress
- LoadBalancer Service (e.g., MetalLB for on-premises environments)

## Building blocks available

Here you will find subsections of building blocks that are currently available.

### Log Ingestion Receivers

Available over TCP, UDP, and HTTP, the receivers provide a simple and reliable way to stream data into the Herringbone platform.

### Log Ingestion Enrichment

Scans incoming logs and adds context that may be missing. It integrates with connected services, such as AI models, to generate human-readable descriptions, highlight potential indicators of compromise (IOCs), and produce structured key–value pairs for faster searching, filtering, and correlation.

### Detection Engine Ruleset

Create and manage detection rules stored in the database. These rules can be applied to both incoming and historical logs to find matches, uncover suspicious activity, and drive automated detection workflows.

### Mind Recon

A containerized AI model with a simple API that Herringbone’s Enrichment components use to generate descriptions, extract IOCs, and add structured fields to logs.

### Herringbone Apps

An API that collects information about Herringbone’s building blocks running in the Kubernetes cluster by leveraging the Kubernetes API and a dedicated service account.

### Herringbone Logs

An API that serves logs directly from the central database, providing a single access point for all collected data.