# DEVELOPER CHEAT SHEET: AGENT CONTEXT OPTIMIZATION
**DOCUMENT:** `opportunity_warehouse/research/DEVELOPER_QUICK_REFERENCE_CARD.md`  
**TARGET:** Developers building with Cursor, Claude Code, Windsurf, Cline  

---

## 1. The Top 5 Prompt Bloat Anti-Patterns

| Anti-Pattern | Bad Example (Bloat) | Fixed Pattern (Optimized) | Token Savings |
| :--- | :--- | :--- | :---: |
| **1. Identity Boilerplate** | *"You are an expert full-stack TypeScript senior engineer..."* | **Delete entirely.** Leading LLMs already operate at senior level. | ~35 tokens/turn |
| **2. Embedded Documentation** | Pasting 200 lines of library API reference directly into `.cursorrules`. | Reference local file: *"See `docs/api_summary.md` when editing endpoints."* | ~400–800 tokens/turn |
| **3. Duplicate Directives** | Having both "Strict typing" and "Ensure zero any types" across 3 sections. | Consolidate into single bullet: `- Strict typing (no any).` | ~25 tokens/turn |
| **4. Pre-Commit Linter Rules** | Listing 30 syntax rules that ESLint/Prettier already enforce on save. | Let the linter catch it. Use rules only for architectural decisions. | ~300 tokens/turn |
| **5. Obsolete Model Workarounds**| Hacks meant for GPT-3.5 (e.g. *"Think step by step"*, *"Do not apologize"*). | **Delete.** Claude 3.5 Sonnet and GPT-4o don't need prompt crutches. | ~40 tokens/turn |

---

## 2. CLI Quick Reference for `agent-context-trimmer`

```bash
# Audit current repository rules and token burn
npx agent-context-trimmer .

# Generate standalone self-contained HTML report
npx agent-context-trimmer --html report.html .

# CI/CD Pre-commit Mode (exits 1 if bloat > 15%)
npx agent-context-trimmer --audit --threshold 15
```
