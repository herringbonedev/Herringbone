# Herringbone

A cloud-native engine for log management, detection rules, and security intelligence.

[![DetectionEngine Ruleset](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine-ruleset.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine-ruleset.yml)
[![Enrichment](https://github.com/herringbonedev/Herringbone/actions/workflows/enrichment.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/enrichment.yml)
[![Herringbone Apps](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-apps.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-apps.yml)
[![Herringbone Logs](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-logs.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/herringbone-logs.yml)
[![Receiver](https://github.com/herringbonedev/Herringbone/actions/workflows/receiver.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/receiver.yml)
[![Mind Recon](https://github.com/herringbonedev/Herringbone/actions/workflows/mind-recon.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/mind-recon.yml)
[![Mind Overwatch](https://github.com/herringbonedev/Herringbone/actions/workflows/mind-overwatch.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/mind-overwatch.yml)
[![DetectionEngine Detetor](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine-detector.yml/badge.svg?branch=main)](https://github.com/herringbonedev/Herringbone/actions/workflows/detectionengine.detector.yml)

# Herringbone  

**Herringbone** is a modular framework for building your own SIEM or log management solution. Inspired by the defensive herringbone formation, it is designed around independence, flexibility, and interoperability.  

## Overview  

Herringbone is composed of independent **elements**. Each element performs a specific task and can be deployed on its own or combined with others. Elements come together to form **Units**, which define the broader mission they are intended to accomplish.  

For example, the **Detection Engine Unit** includes the **Ruleset** and **Detector** elements. On their own, these elements cannot act as a complete detection system. Together, the Ruleset manages detection rules while the Detector applies them to logs, identifies matches, and alerts the user.  

You are never required to deploy an entire Unit. You can choose to run only the elements you need, providing full control over the shape and size of your deployment.  

Special Units, such as **Mind**, contain AI powered elements. These are designed to support interchangeable models, giving you the flexibility to Bring Your Own Model. With Mind, the accuracy and power of your Herringbone deployment scales directly with the quality of the models you choose to integrate.  

## Core Principles  

All elements follow two guiding principles:  
1. **Independence** – no element depends on another to function.  
2. **Interoperability** – all elements expose universal inputs and outputs, enabling easy integration with any system, including other elements.  

These principles allow you to host Herringbone components wherever you choose. While Herringbone is designed and tested on vanilla Kubernetes, nothing prevents you from running receivers or other elements as containers distributed across multiple cloud providers and networks. As long as they share a common database, the system works seamlessly.  

## Features  

- Modular elements that can run independently  
- Units that combine elements into powerful missions  
- AI powered Mind Unit with Bring Your Own Model capability  
- Designed and tested on Kubernetes, deployable in any container environment  
- Universal inputs and outputs for flexible integration  

## Getting Started  

1. Familiarize yourself with the **Concepts** documentation to understand the principles of Herringbone.  
2. Review the **Installation Guide** to deploy Herringbone on Kubernetes or in containers.  
3. Explore the available **Units** and decide which elements fit your use case.  
4. Enable or disable elements as needed to tailor the solution to your environment.  

## Example  

A simple deployment of the Detection Engine Unit might look like this:  

- **Ruleset** manages detection rules.  
- **Detector** applies those rules to incoming logs.  
- Together they form a complete detection system, but you could also run only the Detector or Ruleset independently.  

## Contributing  

Contributions are welcome. Please review the **Contributing Guide** before submitting issues or pull requests. Code reviews are required before merging into the main branch to maintain quality and consistency.  

## License  

Herringbone is released under the [Apache 2.0 License](LICENSE).  
