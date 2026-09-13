# agent-context-trimmer

> **Stop burning $50–$200/month on silent AI coding assistant token bloat.**

A lightweight, zero-dependency developer utility that audits your AI agent rulebooks (`.cursorrules`, `.cursor/rules/`, `.gemini/rules/`, `CLINEmode`, `.windsurfrules`, and system prompt templates).

It instantly calculates exact token counts per conversational turn, detects duplicate instructions and giant embedded code blocks, and projects your exact monthly dollar savings across Claude 3.5 Sonnet, GPT-4o, and Gemini 1.5 Pro.

---

## The Silent Cost of Bloated Agent Rules

AI coding assistants (Cursor, Antigravity, Cline, Windsurf, Copilot Workspace) **re-transmit your entire system prompt and rule files on every single turn**.

If your `.cursorrules` or prompt files have grown to 15,000 tokens:
- In a typical 40-turn coding session, you burn **600,000 input tokens**.
- At $3.00/1M tokens (Claude 3.5 Sonnet), that is **$1.80 wasted per session**.
- Over 20 working days, you silently pay **$36.00/month for repetitive rules**.

`agent-context-trimmer` finds the waste in under 1 second.

---

## Quick Start

### 1. Run Directly with Node (Zero Install)
```bash
node bin/agent-context-trimmer.js .
```

### 2. Generate an Interactive HTML Audit Dashboard
```bash
node bin/agent-context-trimmer.js --html audit-report.html .
```

### 3. Customize Your Workload Profile
```bash
# Analyze for heavy developers: 60 turns/day across 25 working days
node bin/agent-context-trimmer.js --turns 60 --sessions 25 .
```

---

## What It Audits
- **Multi-File Context Aggregation**: Automatically discovers `.cursorrules`, `.cursor/rules/*.mdc`, `.gemini/config/rules/*.md`, `.windsurfrules`, `CLINEmode`, and `AGENTS.md`.
- **Duplicate Rules**: Identifies identical or near-identical instructions repeated across files.
- **Giant Embedded Code Blocks**: Flags massive static schemas or code snippets that bloat every prompt instead of being loaded on demand.
- **Verbose Boilerplate**: Detects generic role preambles ("You are an expert AI engineer...") that consume tokens without steering performance.
- **Compounding ROI**: Computes exact per-turn and monthly dollar projections for leading models.

---

## Requirements
- Node.js >= 18.0.0
- Zero external npm dependencies. 100% offline. No API keys or internet connection required.

---

## License
MIT License. See [LICENSE_NOTES.md](LICENSE_NOTES.md) for commercial use terms.
