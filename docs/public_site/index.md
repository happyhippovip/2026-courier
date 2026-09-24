# Welcome to Courier

Welcome to the **Courier** project documentation.

Courier is an autonomous, multi-worker workflow orchestration platform designed to coordinate complex, long-running agentic goals across heterogeneous operating environments (Mac and Windows).

## What is Courier?

Courier transforms high-level user instructions into verifiable, structured execution workflows. By decoupling task planning from distributed worker execution, Courier provides:

- **Multi-Worker Orchestration**: Seamless delegation between specialized worker daemons across diverse runtime platforms.
- **Durable Task Lifecycle**: End-to-end tracking from initial goal decomposition to physical proof of execution and independent verification.
- **Fail-Closed Resilience**: Robust recovery protocols ensuring consistent state preservation and safe re-entrancy across agent handoffs or system reboots.
- **Progress Visibility**: Real-time status reporting and transparent task ledgers for every workflow phase.

## Getting Started

Explore our documentation to get started with Courier:

- [Setup Guide](setup.md) - How to configure and start Courier daemons and workers.
- [Architecture](architecture.md) - Deep dive into central orchestration and worker nodes.
- [Central API Reference](api.md) - Endpoints and schemas for goal submission and task state transitions.
- [Security Model](security.md) - Sandboxing policies, process isolation, and security guarantees.
- [FAQ](faq.md) - Frequently asked questions regarding operations and capabilities.
- [Contributing](contributing.md) - How to develop and contribute improvements to Courier.

---
*Courier: Start with an idea. Let autonomous coordination carry it across the finish line.*
