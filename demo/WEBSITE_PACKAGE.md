# Courier Website Content Package

## One-Sentence Value Proposition
Courier is the OS-owned durable runtime for agentic work that outlives the interactive AI session.

## Problem
Today's AI agents live and die with the chat window. If the user's browser closes, a provider rate limit is hit, or a Python script crashes, the entire context is lost and the work must be restarted from scratch.

## How Courier Solves It
Courier separates the *Planner* (the interactive agent) from the *Motor* (the execution runtime). The Motor orchestrates tasks across replaceable worker processes. Once a goal is submitted, Courier drives execution until completion—surviving worker crashes and interruptions without needing human "continue" prompts.

## Three Strongest Demonstrated Capabilities
1. **Zero-Touch Worker Replacement**: If a worker process crashes midway through a task, Courier's Motor safely preserves state and gracefully reassigns the remaining execution plan to a replacement worker.
2. **Session Persistence via Motor State**: State is persisted instantly by the Motor, completely independent of the UI or demo observer script.
3. **Independent Verification**: Completion isn't just assumed; Courier uses a separate, independent verifier process to check output evidence before advancing the workflow.

## Short Demo Narrative
*In this 90-second standalone demo, we show how Courier handles real-world worker interruptions:*
- A multi-step "Market Research Pipeline" is submitted to the Courier Motor. 
- Local Worker Process A begins extracting data. 
- **CRASH!** We explicitly terminate Worker A mid-workflow.
- The Courier Motor detects the failure, preserves the exact state, and safely waits. 
- Local Worker Process B starts, automatically picks up exactly where Worker A left off, and completes the final reporting steps. 
- The result is verified and the goal is marked DONE—zero human intervention required.

## Early Access / Pilot CTA
**Stop babysitting your AI agents.** 
Join the early access pilot to bring durable execution to your autonomous workflows.
[ Request Pilot Access ]

## Technically Accurate Limitations
- Courier is an orchestration runtime, not an AI model. It requires an external LLM provider or interactive agent to generate the initial workflow plan.
- At present, the verification step relies on deterministic artifact hashes. Subjective or generative verification models are still in alpha.
- This demo orchestrates local worker processes; distributed orchestration across physical machines over public internet requires a secure VPN or proxy setup not shown here.
