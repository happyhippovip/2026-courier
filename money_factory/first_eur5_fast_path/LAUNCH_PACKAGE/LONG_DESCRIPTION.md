# Agent Context Trimmer — Full Product Overview

## Background: Repeated Context in Coding Agents
Modern AI-assisted developer environments (Cursor, Windsurf, Cline, GitHub Copilot, Gemini CLI) inject repository guidelines into the model's context. In active agentic development:
1. **Instruction Sprawl**: Guidelines often duplicate rules across different sections or across multiple files (`.cursorrules`, `.gemini/rules/*.md`, `.windsurfrules`).
2. **Embedded Code Payloads**: Data schemas, API interfaces, and JSON payloads are frequently pasted directly into instructions instead of being kept as referenced workspace files.
3. **Context Burden**: Repeated prompt tokens consume context window capacity and contribute to token consumption on conversational turns.

*Note on Prompt Caching*: Many leading model providers (Anthropic, OpenAI) offer prompt caching that discounts cached tokens after the first turn. However, context length still impacts latency, attention focus, and cache initialization costs. Keeping rules lean remains a foundational best practice.

---

## What Agent Context Trimmer Does
`agent-context-trimmer` is a standalone command-line audit tool designed for local, offline inspection of agent configurations.

### Core Capabilities:
- **Rule Discovery**: Automatically locates configuration files matching common agent conventions (`.cursorrules`, `.cursor/rules/*.mdc`, `.gemini/**/*.md`, `.windsurfrules`, `.clinerules`, `CLINEmode.md`, `.copilot-instructions.md`, `AGENTS.md`).
- **Duplicate Directive Detection**: Identifies identical or near-identical instructions across bulleted lists and numbered rules with full Unicode international character support.
- **Large Block Detection**: Flags code blocks exceeding 25 lines that can be moved to referenced documentation files.
- **Configurable Cost Modeling**: Estimates token counts using a calibrated Byte-Pair heuristic (~4 chars/token) and models potential monthly input costs across customizable turn counts (default: 40 turns/day x 20 working days) against published provider rate cards.
- **Zero External Dependencies**: Standard Node.js >= 18 built-in modules only (`fs`, `path`, `crypto`). No `node_modules` installation required.
- **100% Offline & Private**: Zero HTTP calls, zero telemetry, zero analytics. Your code and rules never leave your machine.
- **Interactive HTML Report**: Generates a self-contained local HTML dashboard with `--html`.
- **Machine-Readable JSON**: Outputs structured metrics with `--json` for CI/CD or Git pre-commit checks.

---

## Verified Platform & Environment
- **Physically Verified**: Windows 11 x64, Node.js v24.
- **Expected Compatibility**: macOS and Linux (uses standard cross-platform Node.js APIs; direct execution on macOS/Linux not locally verified on this build workstation).

---

## Quick Start
```bash
# Run audit on current workspace
node bin/agent-context-trimmer.js .

# Generate an interactive HTML report
node bin/agent-context-trimmer.js . --html audit.html

# Output JSON for scripts or pre-commit hooks
node bin/agent-context-trimmer.js . --json
```
