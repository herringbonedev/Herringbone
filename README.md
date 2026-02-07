# Herringbone  

**Herringbone** is a modular framework for building SIEM and log management systems. It is designed to be flexible, composable, and deployable in many different ways, depending on your needs.

![Homepage screenshot](.docs/images/homepage.png)

## Learn how to use Herringbone  

See the [Wiki](https://github.com/herringbonedev/Herringbone/wiki) for guides, concepts, and usage documentation.

## Overview  

Herringbone is built from small, independent services called **elements**.  
Each element performs a single, well-defined function and can run on its own.

Related elements can be grouped into **Units**, which represent a larger capability or purpose. Units are organizational—not mandatory deployment boundaries.

For example, the **Detection Engine Unit** includes the **Ruleset** and **Detector** elements:
- **Ruleset** manages detection rules
- **Detector** evaluates logs against those rules and produces detections

You can run these elements together, separately, or alongside other systems. You are never required to deploy a full Unit.

## Core Principles  

All elements follow two core principles:

1. **Independence**  
   Each element can run and scale on its own without tight coupling to other elements.

2. **Interoperability**  
   Elements communicate through consistent, well-defined inputs and outputs, making them easy to integrate with each other or with external systems.

Because of this, Herringbone components can be deployed almost anywhere. While development and testing focus on Kubernetes, elements can run as standalone containers across different environments as long as they share access to the same data store.

## Features  

- Independent, composable elements  
- Optional Units for organizing related functionality  
- AI-assisted elements with Bring Your Own Model support  
- Designed for Kubernetes but runnable in any container environment  
- Consistent interfaces for integration and extension  

## Getting Started  

1. Read the **Concepts** documentation to understand how Herringbone is structured  
2. Review the available **Units** and **elements**  
3. Deploy only what you need and expand over time  

## Contributing  

Contributions are welcome. Please read the [Contributing guide](./CONTRIBUTING.md) before submitting issues or pull requests. All changes require review before merging.

## License  

Herringbone is released under the [Apache 2.0 License](LICENSE).