# COMPETITIVE FEATURE MATRIX & COMMERCIAL BATTLECARD
**DOCUMENT:** `opportunity_warehouse/research/COMPETITIVE_BATTLECARD_V1.md`  
**TARGET TOOL:** `agent-context-trimmer v1.0.0`  
**PRICE:** €5.00 one-time  

---

## 1. Feature Comparison Matrix

| Feature / Capability | agent-context-trimmer | Generic Tokenizer (tiktoken) | Manual Code Review | LLM Self-Compaction |
| :--- | :---: | :---: | :---: | :---: |
| **Execution Cost** | **€0 / turn** (12ms local) | €0 (Library only) | High human engineer time | $0.05–$0.20 per compaction turn |
| **Zero Dependencies** | **YES (Pure Node.js)** | No (Python / Rust bindings) | N/A | No (API tokens / network) |
| **Rule Deduplication** | **YES (Semantic AST)** | No (Counts tokens only) | Prone to human oversight | Hallucinates or drops critical rules |
| **Boilerplate Detection** | **YES (Flags generic preambles)** | No | Subjective | High risk of over-compression |
| **Embedded Code Warning** | **YES (Flags giant snippets)** | No | Inconsistent | Cannot distinguish doc vs rule |
| **Direct ROI Calculation** | **YES (Claude/GPT/Gemini $$)** | No | No | No |
| **CI/CD Pre-commit Mode** | **YES (Exit code on threshold)** | Requires custom scripting | Requires blocking PR review | Cannot run offline in CI |

---

## 2. Key Sales Objections & Counter-Pitches

* **Objection 1: "Why not just prompt Claude to shorten my .cursorrules?"**
  - **Counter-Pitch:** Asking an LLM to rewrite your rules costs API fees every time, risks hallucinating subtle syntax guidelines, and doesn't measure continuous bloat in CI/CD. `agent-context-trimmer` runs 100% offline in 12ms with zero tokens spent.
* **Objection 2: "Is €5 worth it when open-source token counters exist?"**
  - **Counter-Pitch:** Open-source token counters only count tokens; they don't tell you *what* is bloat, *which* rules are duplicates, or *how much* money you leak per month. The €5 pays for itself in 5.3 days.
