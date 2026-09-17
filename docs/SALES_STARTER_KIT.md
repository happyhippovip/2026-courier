# Courier Sales Starter Kit

## 1-Sentence Pitch
Courier is the durable orchestration runtime for agentic work that outlives the interactive AI session.

## 30-Second Explanation
Today’s AI agents live and die with the chat window. If a script crashes or a provider hits a rate limit, the entire context is lost. Courier solves this by separating the interactive agent (the Planner) from the execution environment (the Motor). Once a goal is submitted, Courier drives execution until completion—surviving crashes, securely preserving state, and seamlessly handing off work to replacement nodes without needing human "continue" prompts.

## 3 Demonstrated Capabilities
1. **Zero-Touch Worker Replacement:** Safely handles worker node crashes mid-workflow by preserving state and assigning replacement workers.
2. **Session Persistence:** Executes tasks completely decoupled from the UI, ensuring progress continues even if the user goes offline.
3. **Independent Verification:** Integrates a detached verifier process to cryptographically or deterministically validate output before marking work as complete.

## 3 Appropriate Initial Use Cases
1. **Long-Running Data Pipelines:** Scraping, enriching, and formatting massive datasets where script crashes or rate limits are common.
2. **Multi-Agent Code Generation:** Workflows where a researcher agent gathers context, a coder agent writes, and a verifier agent tests—requiring durable handoffs.
3. **Nightly Audits & Reporting:** Unattended overnight tasks that must guarantee completion by morning despite temporary network or API failures.

## 5 Pilot Qualification Questions
1. Are you currently building multi-step agentic workflows that take longer than 5-10 minutes to run?
2. What happens to your current workflows if the executing Python script crashes or the LLM provider times out?
3. Do you currently have to manually babysit agents with "continue" prompts?
4. Are you executing tasks across different operating systems or environments (e.g., local Mac and cloud GPU)?
5. Do you have a concrete workflow you can share with us to test in the Courier Motor?

## Short Pilot Outreach Template
**Subject:** Stop babysitting your AI agents (Courier Early Access)

Hi [Name],

I saw your team is building complex agentic workflows. Right now, most teams struggle because if a script crashes or an LLM times out, the agent loses context and the work has to restart.

We're piloting **Courier**, a durable orchestration runtime that separates the AI planner from execution. If a worker crashes, Courier preserves the exact state and automatically spins up a replacement to finish the job.

If you have a workflow that currently requires babysitting or suffers from dropped sessions, I'd love to integrate it into our Motor and show you a live recovery demo. 

Are you open to a brief technical introduction this week?

Best,
[Your Name]

## Common Technical Objections & Factual Answers

**Objection:** "We already use [LangChain/AutoGen/CrewAI], why do we need this?"
**Answer:** Those are excellent frameworks for *building* agent logic (the Planner). Courier is the *execution runtime* (the Motor) underneath them. Courier doesn't replace your agents; it ensures that when they crash, their state is preserved and execution is safely resumed.

**Objection:** "We just use Celery or Temporal for background jobs."
**Answer:** Standard task queues are great, but they are built for deterministic software, not non-deterministic agentic workflows. Courier is purpose-built for agentic state, handling zero-chat LLM handoffs and verifiable cryptographic acceptance criteria that traditional job queues don't natively support.

**Objection:** "Is this a managed cloud service?"
**Answer:** No. Courier is open-source (Community Edition) and deployed directly on your infrastructure. Your API keys and data never leave your secure local network or VPC.
