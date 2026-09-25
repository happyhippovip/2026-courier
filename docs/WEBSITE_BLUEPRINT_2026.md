# Courier Symphony — Website Blueprint 2026

Status: strategic product and company website plan. Build after the core cloud/runtime foundation is stable enough to support truthful claims.

## Purpose

The website must do four jobs at once:

1. explain Courier Symphony in seconds
2. prove that the product is real
3. support funding / grant / partner conversations
4. prepare for future customers and integrations

The site must look ambitious, but every technical claim must be backed by real evidence.

## Positioning

Courier Symphony is presented as an AI operations platform for reliable, auditable, unattended work.

Core promise:
- one task at a time
- traceable execution
- fail-closed handling of unknown outcomes
- reproducible cloud setup
- cost control
- recovery
- versioned workflows
- multi-provider readiness

Avoid generic claims such as "revolutionary AI" without proof.

## Homepage structure

### 1. Hero

Headline direction:
"AI operations that keep working when nobody is watching."

Supporting message:
Courier Symphony coordinates tasks, agents, cloud workers, verification, recovery, and cost controls in one auditable execution system.

Primary CTA:
- See how it works
- Request a demo

Secondary CTA:
- Technical architecture

### 2. Product proof

Show the real execution chain:

TASK
-> ADMISSION
-> EXECUTE
-> RESULT
-> PERSIST
-> VERIFY
-> RECONCILE
-> DONE
-> NEXT

Include visual status examples:
- RUNNING
- WAITING
- BLOCKED
- UNKNOWN
- DONE

### 3. Why it is different

Focus on concrete product properties:

- unattended operation
- execution lineage
- no blind retries on unknown outcomes
- workflow versioning
- provider abstraction
- cost guardrails
- portable recovery
- reproducible infrastructure
- one trusted source of operational truth

### 4. Architecture

Show a clean architecture diagram:

Mac / Windows
-> Courier Control Plane
-> AWS Controller
-> Burst Worker(s)
-> Model / Tool Providers
-> Execution Ledger
-> Storage / Recovery
-> Observability

AWS is the preferred primary cloud, while the architecture remains portable.

Do not claim formal AWS partnership unless confirmed.

### 5. Live proof / metrics

When available, show real metrics only:

- completed tasks
- uptime
- duplicate rate
- lost-result rate
- intervention rate
- average cost per completed task
- recovery time
- current workflow version

Never use fabricated counters or placeholder "customer" numbers.

### 6. Security and trust

Explain:

- least privilege
- temporary cloud credentials
- no plaintext long-lived keys in workers
- encrypted storage
- audit trail
- reproducible restore
- UNKNOWN fail-closed behavior

### 7. Funding / partner credibility

Create a dedicated page with:

- company vision
- technical differentiation
- architecture
- roadmap
- milestones
- measured reliability
- cost model
- recovery model
- security model
- technical evidence
- future market path

This page supports grant, investor, AWS, and strategic-partner conversations.

### 8. Use cases

Initial examples:

- autonomous research pipelines
- media production operations
- long-running AI task queues
- cloud agent supervision
- workflow automation
- recovery-sensitive production jobs

Only publish use cases that can be demonstrated.

### 9. Product / developer page

Future sections:

- workflow API
- execution IDs
- webhook / callback patterns
- policy rules
- versioned workflows
- SDK / API docs

### 10. Company page

Keep it credible and concise:

- mission
- why Courier exists
- product philosophy
- company roadmap
- contact

Do not invent employees, offices, customers, investors, or partners.

## Visual direction

The site should feel:

- premium
- technical
- calm
- dark / high-contrast
- modern but not gimmicky
- evidence-driven

Visual language:
- subtle graph / node relationships
- execution timelines
- clean system diagrams
- live status blocks
- audit / lineage views
- restrained motion

Avoid:
- excessive glowing gradients
- fake dashboards
- generic stock AI imagery
- meaningless animated particles
- copied Atlas branding

Use inspiration from strong AI-infrastructure product sites, but keep Courier visually distinct.

## Core pages

- /
- /product
- /architecture
- /security
- /use-cases
- /developers
- /funding
- /company
- /contact

Later:
- /pricing
- /status
- /docs
- /changelog

## Evidence system

Every major technical claim should point to evidence that can be maintained:

- Git version
- test result
- architecture artifact
- benchmark
- operational metric
- recovery drill
- cost measurement

The website should never outrun the actual product.

## Grant-ready website mode

For funding applications, the site must make it easy for a reviewer to see:

- what the problem is
- what is technically novel
- what already works
- what is still being built
- measurable milestones
- why the architecture can scale
- how security and recovery are handled
- why funding accelerates a credible roadmap

## AWS alignment

The public site may state that Courier is built on or optimized for AWS only when that is technically true.

Do not use:
- "AWS Partner"
- "Amazon Partner"
- AWS logos implying endorsement

unless formal rights / status exist.

A future AWS-focused page can show:
- AWS architecture
- IAM / SSM security model
- EC2 controller / burst worker
- cost optimization
- recovery
- Bedrock / AgentCore experiments if adopted

## Meta / Facebook alignment

Likewise, do not publicly call Meta / Facebook a formal partner unless confirmed.

The site can truthfully describe integrations, model usage, or platform support when implemented.

## Build order

Do not build the full website before the product foundation is stable.

1. lock brand / message
2. build simple company landing page
3. add architecture and security pages
4. add real product proof / screenshots
5. add grant / partner evidence page
6. add developer / API pages
7. add pricing only when commercial packaging is clear

## Immediate rule

The website is now a tracked company workstream, but it must not interrupt the current AWS live-write lane.

Current execution priority remains:

secure AWS access
-> reproducible cloud state
-> Machine A
-> Machine B
-> headless runtime
-> Execution Ledger
-> first public website version

