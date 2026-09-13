# Deterministic Demo: Value Proof That Requires Zero Trust

This demo lets any engineer inspect the exact structural waste in two sample agent configuration files without relying on sales claims or opaque AI evaluations.

---

## 1. What Is in This Demo?
In the `DEMO/workspace/` folder, there are two standard rules files:
1. **`.cursorrules`**:
   - Contains **2 duplicate directives** (repeated architecture instructions).
   - Contains **1 oversized embedded TypeScript schema** (45 lines) that should be externalized.
   - Contains **1 generic boilerplate preamble** (*"You are an expert senior software engineer..."*).
2. **`.gemini/rules/coding_style.md`**:
   - Contains **1 duplicate formatting rule**.

---

## 2. Run the Demo
Run the single-line command from the product directory:

```bash
node bin/agent-context-trimmer.js DEMO/workspace
```

---

## 3. Verifiable Structural Evidence
Running this command produces the exact output recorded in `DEMO_EXPECTED_OUTPUT.txt`:
- **Files Discovered**: 2
- **Total Repeated Tokens Per Turn**: ~440 tokens
- **Reducible Token Waste Per Turn**: ~350 tokens (over 75% reducible)
- **Specific Structural Issues Flagged**:
  * Line 9 of `.cursorrules`: Duplicate instruction (*"All external API calls must pass through..."*)
  * Line 10 of `.cursorrules`: Duplicate instruction (*"Ensure strict TypeScript typing..."*)
  * Line 13 of `.cursorrules`: Embedded code block is 45 lines long (flagged for externalization)
  * Line 60 of `.cursorrules`: Generic role preamble boilerplate
  * Line 3 of `coding_style.md`: Duplicate formatting directive

---

## 4. Why This Requires Zero Trust
- You can inspect the source code of `lib/analyzer.js` directly.
- The duplicates are plain text matching.
- The 45-line code block is counted deterministically.
- Token counts are calculated with simple standard formulas.
- No network requests, no LLM calls, no subscription paywalls.
