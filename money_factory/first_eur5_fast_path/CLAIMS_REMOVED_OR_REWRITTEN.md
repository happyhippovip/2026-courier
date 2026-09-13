# CLAIMS REMOVED OR REWRITTEN (COMMERCIAL TRUTH AUDIT)

**Product**: `agent-context-trimmer` (v1.0.0)  
**Standard**: Strict adherence to verifiable evidence. If we cannot prove it, we do not present it as fact.

---

## Summary of Changes

| Category | Original Sales Claim | Rewritten Truthful Statement | Rationale |
| :--- | :--- | :--- | :--- |
| **Financial Savings** | "Instantly eliminate $30+/month in silent input token burn" | "Estimate repeated context overhead across LLM sessions based on your own usage" | Dollar savings depend on individual developer volume, model choice, and prompt caching. Presenting $30/mo as guaranteed fact was unsupported. |
| **Payback Guarantee** | "Pays for itself in less than two weeks of solo coding—or on day two for a team" | "Lets you model potential break-even scenarios based on customizable turn volume and rate cards" | Guaranteed payback assumes fixed bloat and no prompt caching discounts. Reframed as an illustrative model. |
| **ROI Percentage** | "Year 1 Net ROI: +540% to +12,700%" | *Removed from marketing copy entirely* | Compounded percentage extrapolations are marketing hype, not empirical product capabilities. |
| **Execution Latency** | "Audits your workspace in 45 milliseconds" | "Under 50ms on tested benchmark fixtures" | 45ms was measured on a specific 2-file fixture. Large repositories with deep directory trees will take longer. |
| **Platform Verification** | "Supported on Windows, macOS, and Linux" | "Verified on Windows 11 x64; expected on macOS and Linux via standard Node.js APIs" | Honest boundary: macOS and Linux have not been directly tested on this machine. Mac host access is strictly denied. |
| **Token Measurement** | "Calibrated Byte-Pair Encoding engine" | "Calibrated Byte-Pair length-and-word heuristic (~4 chars/token)" | Clarified that the tool uses an empirical approximation heuristic rather than an exact byte-pair tokenizer library like tiktoken. |
| **Prompt Compounding** | "Every single rule token is re-sent on every turn, burning money" | "Rules consume repeated context window capacity; prompt caching may discount cached tokens, but keeping rules lean remains best practice" | Acknowledged modern prompt caching mechanisms (Anthropic/OpenAI) to avoid misleading buyers about raw API billing mechanics. |
| **Headline Value** | "Eliminate Silent LLM Token Waste" | "Audit and Model Context Token Overhead in AI Coding Rules" | Clear, professional, non-sensationalized product framing. |

---

## Integrity Sign-Off
All promotional hyperbole has been removed. All remaining technical claims are directly verified by local unit tests, adversarial test suites, and transparent benchmark data.
