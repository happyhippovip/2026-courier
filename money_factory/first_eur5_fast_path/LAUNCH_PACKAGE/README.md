# Agent Context Trimmer

> Local, zero-dependency audit tool to identify duplicate rules, large embedded code blocks, and context token overhead in AI coding assistant configurations.

---

## Highlights
- **Zero Dependencies**: Pure Node.js (>= 18) standard library.
- **100% Offline**: Zero external network requests, zero telemetry, private and local.
- **Fast Execution**: Under 50ms on tested benchmark fixtures.
- **Multi-Assistant Support**: Scans Cursor (`.cursorrules`), Windsurf (`.windsurfrules`), Cline (`.clinerules`), Gemini (`.gemini/**/*.md`), Copilot, and custom files.
- **Actionable Reporting**: Terminal output, structured JSON, and self-contained interactive HTML dashboards.

---

## Installation & Requirements
- Requires Node.js >= 18.0.0.
- No installation or build steps needed.

```bash
# Verify installation
node bin/agent-context-trimmer.js --version
```

---

## Usage

### 1. Basic Workspace Scan
```bash
node bin/agent-context-trimmer.js <path-to-workspace>
```

### 2. Export HTML Dashboard
```bash
node bin/agent-context-trimmer.js . --html audit.html
```

### 3. Machine-Readable JSON (CI / Pre-commit)
```bash
node bin/agent-context-trimmer.js . --json
```

### 4. Custom Turn / Session Modeling
```bash
# Model 60 turns per day across 22 working days
node bin/agent-context-trimmer.js . --turns 60 --sessions 22
```

---

## Verified Platform Evidence
- **Verified Environment**: Windows 11 x64 (Node.js v24.20.0).
- **Expected Compatibility**: macOS and Linux (standard Node.js runtime).
