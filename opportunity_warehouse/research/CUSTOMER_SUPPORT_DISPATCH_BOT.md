# AUTOMATED CUSTOMER SUPPORT & DEVELOPER FAQ MATRIX
**DOCUMENT:** `opportunity_warehouse/research/CUSTOMER_SUPPORT_DISPATCH_BOT.md`  
**GOAL:** 100% automated resolution of buyer queries within 60 seconds without human intervention.  

---

## Canned Resolution Matrix

### Q1: "Does agent-context-trimmer work on Windows, macOS, and Linux?"
> **Answer:** Yes. The tool is written in pure, zero-dependency Node.js (v18+). It uses platform-independent path normalization and runs natively on Windows (PowerShell/CMD), macOS (zsh), and Linux (bash).

### Q2: "Can I add this to my pre-commit hook or GitHub Actions CI?"
> **Answer:** Yes! Run `npx agent-context-trimmer --audit --threshold 15`. If redundant token bloat exceeds 15%, it exits with code 1, automatically preventing bloated prompt commits.

### Q3: "Does it modify or delete my .cursorrules file automatically?"
> **Answer:** No. By default, `agent-context-trimmer` runs in read-only audit mode (`--audit`). It only suggests optimized diffs. It never mutates your source files without explicit confirmation.

### Q4: "I need a team license for 10+ engineers. How do I upgrade?"
> **Answer:** You can upgrade to the **Symphony Autonomous Stack Team License** (€29 or €39 bundle on Gumroad), which includes `@symphony/agent-locks` and multi-seat commercial redistribution rights.

### Q5: "What is your refund policy?"
> **Answer:** 14-day no-questions-asked refund policy. If the tool does not uncover measurable context bloat in your project, reply to your Gumroad receipt email for an instant refund.
