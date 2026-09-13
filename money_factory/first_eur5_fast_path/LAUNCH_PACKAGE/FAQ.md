# Frequently Asked Questions (FAQ)

### Q: Which AI coding assistants and file formats are supported?
**A:** `agent-context-trimmer` scans for known markdown and text configuration files used by Cursor (`.cursorrules`, `.cursor/rules/*.mdc`), Google Antigravity / Gemini (`.gemini/**/*.md`), Windsurf (`.windsurfrules`), Cline (`.clinerules`, `CLINEmode.md`), GitHub Copilot Workspace (`.copilot-instructions.md`), and general agent files (`AGENTS.md`). You can also specify any individual text file directly as a target.

### Q: Does this tool send any code or data to external servers?
**A:** **No.** The tool operates 100% locally. It contains zero network calls, zero telemetry, and zero tracking code. Your files remain entirely on your local filesystem.

### Q: Are there any npm dependencies to install?
**A:** **No.** The tool requires only Node.js (version 18 or newer) and uses standard library modules (`fs`, `path`, `crypto`). There is no `npm install` step.

### Q: How are token counts and cost projections calculated?
**A:** Token counts are calculated using an empirical Byte-Pair heuristic (~1.3 tokens per word + char-length scaling), which approximates BPE tokenizers within standard margins on typical English prose and code. Financial figures are illustrative projections based on published base input rates (Claude 3.5 Sonnet at $3.00/1M, GPT-4o at $2.50/1M, Gemini 1.5 Pro at $1.25/1M). They do not account for dynamic prompt caching discounts or custom enterprise tiers.

### Q: What platforms are supported?
**A:** 
- **Verified**: Windows 11 x64 (Node.js >= 18).
- **Expected**: macOS and Linux (the implementation relies solely on POSIX-compliant standard Node.js APIs, though local testing was performed on a Windows workstation).

### Q: Can this be used in Git pre-commit hooks?
**A:** **Yes.** With the `--json` flag, the tool outputs structured JSON. A simple shell script can inspect `summary.wasted_tokens_per_turn` and exit with code 1 if duplicate rules exceed a defined threshold.
