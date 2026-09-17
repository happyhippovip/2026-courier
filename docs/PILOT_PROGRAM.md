# Courier Early Access Pilot Program

## Who the Pilot is For
The Courier Early Access Pilot is designed for engineering teams and AI operators who are currently building multi-step agentic workflows and are experiencing reliability issues, session loss, or orchestration bottlenecks when relying solely on interactive agent chat interfaces.

## The Core Engagement
**You supply:** One concrete, existing agentic workflow (e.g., a multi-step data extraction, code generation pipeline, or research task) that you currently run manually or via fragile scripts.
**We provide:** Integration of that workflow into the Courier Motor. 

## What the Integration Demonstrates
We will prove on your infrastructure that Courier can:
- Decouple the execution of your workflow from the interactive AI session.
- Orchestrate the execution across replaceable worker processes.
- Gracefully survive simulated or real worker crashes mid-execution.
- Re-assign tasks and securely preserve state without requiring a human to type "continue".

## Expected Onboarding Inputs
To begin the pilot, we need:
1. **Workflow Definition:** A clear description of the tasks, dependencies, and expected outcomes of your chosen workflow.
2. **Infrastructure Access:** (Optional/If applicable) Local network or cloud environment access where the Courier Motor and workers will be deployed.
3. **LLM Provider API Keys:** To authorize the interactive agents performing the work (keys remain fully on your secure infrastructure).

## What Is Included
- Initial consultation and architecture review of your workflow.
- Deployment configuration for a single Courier Motor instance and up to two local or network-adjacent worker processes.
- Conversion of your workflow into a Courier-compatible `workflow_plan`.
- A live demonstration of failure recovery and independent verification using your own tasks.

## What Is NOT Included
- Public internet hosting or external proxy routing for geographically distributed workers.
- Generative/AI-based verification models (we use deterministic cryptographic artifact verification).
- Automated provisioning of third-party cloud hardware.
- Enterprise SLAs or customized legal/compliance audits.

## Current Technical Limitations
- Courier is an orchestration runtime, not a foundational AI model. It requires your existing LLM setup.
- The included Verifier requires deterministic output matching or verifiable cryptographic artifacts.
- The open-source community edition does not include built-in zero-trust public network tunnels.

## Next Steps
To apply, please prepare a brief description of the single agentic workflow you'd like to harden, and reach out to our team to schedule an introductory call.

**[ Apply via contact email provided by your Courier representative ]**
