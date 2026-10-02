# Courier Symphony — Customer Packaging, Included AI & Cost Guardrails

Date: 2026-09-20  
Status: founder-approved product hypothesis / implementation target, not yet a public price promise

## Product principle

The customer should experience:

**Goal -> Courier decides the work -> included vs. extra is clear -> work runs -> verified result**

The customer should not need to understand which model, agent, cloud worker or tool is used.

## Initial packaging hypothesis

A strong initial commercial hypothesis is a package around **EUR 99–100 per month** that includes a meaningful amount of routine Courier work.

Customer-facing wording should be:

**"Included in your Courier plan"**

rather than:

**"free"**

because Courier still has real model, cloud, storage, bandwidth and support costs.

The exact public price, limits and commercial terms remain a Founder/Human Gate until operating-cost evidence is available.

## What can be included

The base package may include a defined allowance for:

- Courier AI questions;
- retrieval from Courier Knowledge;
- lightweight research;
- drafting and rewriting;
- website copy and basic website-building tasks;
- document and archive assistance;
- routine agent workflows;
- small automations;
- selected content-preparation tasks;
- reuse of verified community solutions;
- a bounded amount of cloud/model execution.

## Fair-use and unit economics

Never promise economically unbounded compute for a fixed monthly price.

Internally track at least:

- model cost;
- cloud compute cost;
- storage cost;
- bandwidth/egress cost;
- tool/API cost;
- human-support cost where applicable;
- task duration;
- retries;
- expensive-specialist usage.

Suggested internal fields:

- `PLAN_ID`
- `INCLUDED_BUDGET_EUR`
- `INCLUDED_AGENT_CREDITS`
- `MODEL_COST_EUR`
- `CLOUD_COST_EUR`
- `TOOL_COST_EUR`
- `TOTAL_VARIABLE_COST_EUR`
- `GROSS_MARGIN_ESTIMATE_EUR`
- `OVERAGE_REQUIRES_APPROVAL`
- `CUSTOMER_QUOTE_STATUS=INCLUDED|EXTRA_QUOTE_REQUIRED`

The implementation may use credits, budget envelopes, task classes or another mechanism. The customer experience should stay simple even if the internal accounting is detailed.

## Routing policy

Use the cheapest sufficient capability.

Preferred routing:

`OWN KNOWLEDGE/CACHE -> DETERMINISTIC TOOL -> SMALL/CHEAP MODEL -> STRONGER MODEL -> HUMAN SPECIALIST`

Only move upward when the lower-cost route is insufficient.

## Customer quote gate

Before an expensive or unusually large task begins, Courier should classify it:

### INCLUDED

The task fits the customer's plan and internal cost/risk envelope.

Customer sees something like:

**"Included in your plan — Courier can start."**

### EXTRA_QUOTE_REQUIRED

The task is likely to exceed included resources or requires paid external/human work.

Customer sees:

**"This task needs additional resources. Estimated extra price: X. Approve before Courier starts."**

No silent overage.

## Examples

### Included-type request

"I own a bakery. Build the structure and draft copy for a simple website."

Possible included work:
- research based on supplied/public information;
- sitemap;
- page copy;
- FAQ;
- draft assets/prompts;
- first website implementation within package limits.

Possible external gates:
- domain purchase;
- premium stock assets;
- paid plugins;
- production hosting;
- legal review;
- unusual compute.

### Larger request

"Create and operate a full content engine producing many videos every day."

Courier may plan it automatically, but must calculate expected variable cost and classify whether it is included or requires an extra quote.

## Pricing experiments

The EUR 99–100 figure is a **commercial hypothesis to validate**, not a guarantee.

Measure:
- activation;
- tasks completed per customer;
- cost per completed outcome;
- retention;
- willingness to pay;
- support burden;
- gross margin;
- share of tasks answered from Courier Knowledge;
- share of tasks needing expensive models;
- upgrade/extra-quote acceptance.

## Commercial safety

This document does not authorize:
- activating billing;
- charging customers;
- changing AWS/model subscriptions;
- purchasing resources;
- public price publication;
- contacting customers;
- accepting contracts.

Those remain Human Gates until explicitly approved.

## Strategic goal

Courier should make sophisticated AI feel simple:

**The customer buys a useful outcome package, not a confusing pile of model tokens.**

The long-term moat is:
- orchestration;
- verified knowledge;
- reusable workflows;
- agent capabilities;
- cost routing;
- trusted archive/context;
- community/guild network;
- reliable Goal-to-Done delivery.
