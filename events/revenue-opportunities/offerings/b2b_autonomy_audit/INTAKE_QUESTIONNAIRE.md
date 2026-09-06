# Customer Intake Questionnaire — €99 AI Agent Reliability Check

> [!IMPORTANT]
> **SECRET-FREE INTAKE NOTICE:**
> DO NOT provide API keys, passwords, database strings, OAuth tokens, session cookies, private keys, or `.env` files. Provide only sanitized code, architectural summaries, or scrubbed configuration files.

Please answer the following 5 questions (takes ~3 minutes):

1. **Target Workflow Scope:** Describe the single autonomous workflow to be checked (e.g. multi-file code refactorer, background scraper, batch report generator).
2. **Current Known Symptoms:** What specific reliability failure or uncertainty is prompting this check (e.g. process hangs, lock file stalls, duplicate actions after restart, unmonitored subagents)?
3. **Runtime & OS Environment:** What environment does the agent execute in (macOS, Ubuntu/Linux, Docker container, local subprocess)?
4. **State & Progress Persistence:** How does the agent track execution state across crashes/reboots (SQLite, flat JSON files, Redis, PostgreSQL)?
5. **Worker Concurrency Model:** How many concurrent processes, threads, or subagents read/write the shared working directory?
