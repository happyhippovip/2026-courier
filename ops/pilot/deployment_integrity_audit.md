# Courier Deployment Integrity Audit

**Status:** Post-Pilot Manual Service (Do not replace EUR149 Continuity Audit).

**Description:**
A comprehensive audit of how an AI system is deployed within a customer's environment, focusing on:
1. **Isolation:** Are the agent's credentials and network access strictly bounded?
2. **Immutability:** Can the agent rewrite its own source or historical ledgers?
3. **Verification:** Is the outcome independently verified outside the agent's control?
4. **Data Leakage:** Is telemetry stripping out private data and raw prompts?

**Execution:**
Manual review by a Courier engineer, producing a RAG-friendly Integrity Report.

**Future Automation:**
Only consider automating once we have 10+ manual audits completed and a standardized heuristic checklist.
