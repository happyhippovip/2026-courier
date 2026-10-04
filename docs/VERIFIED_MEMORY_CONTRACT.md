# VERIFIED MEMORY CONTRACT

## 1. Principle
Verified Memory is an **accepted reusable project capability**, not merely stored text. It represents proven ground truth that the project relies upon for automated execution, recovery, and agent continuation.

## 2. Prohibition of Speculation
**Do not label speculative notes, plans, or unexecuted ideas as VERIFIED.** 
Only capabilities and facts that have been executed, observed, or structurally proven may receive the `VERIFIED` status.

## 3. Provenance Requirements
Each verified memory item MUST contain sufficient provenance to answer the following six questions definitively:

1. **WHAT is known?** (The precise capability, configuration, or fact that was proven)
2. **WHY is it believed?** (The deterministic evidence, test script, or logs that prove it)
3. **WHICH SHA/state does it apply to?** (The exact commit, artifact hash, or system state where this was true)
4. **WHO/WHAT produced the evidence?** (The agent, worker, or human who ran the verification)
5. **WHEN was it verified?** (An ISO-8601 timestamp of verification)
6. **WHAT could invalidate it?** (Specific conditions, such as "upgrading the OS," "changing the dependencies," or "modifying the network layer" that would render this memory obsolete)

## 4. Schema Enforcement
All structured Verified Memory MUST validate against `schemas/verified_memory_item.schema.json`. Any memory claiming to be "VERIFIED" without this strict provenance is invalid and must be downgraded to "IDEA", "PLANNED", or "UNVERIFIED".
