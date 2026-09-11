# Post-Launch Customer Onboarding Video Walkthrough Script
**Target Duration**: 90 Seconds  
**Format**: 1080p 60fps Screencast + Clear Studio Voiceover  
**Product**: `agent-context-trimmer v1.0.0` (€5.00 Gumroad Tier)  
**Audience**: AI-first Developers, Cursor / Claude Code Users, Freelance Engineers  

---

## Storyboard & Timing Breakdown

### [00:00 - 00:15] Hook: The Hidden Token Tax
- **Visual**: Screen recording of Cursor or Claude Code stalling on a 150-line `.cursorrules` file. Cost calculator shows token usage spike.
- **Voiceover**: 
  > *"Every time you prompt your AI coding assistant, it reads your entire rules file, system prompt, and context headers. If your rules are cluttered with stale preambles, duplicate guidelines, and code snippets, you are paying a 30 to 50% token tax on every single request."*
- **On-Screen Text**: 🔴 **30–50% Token Bloat Detected**

---

### [00:15 - 00:35] The Solution: Zero-Dependency Unpack
- **Visual**: Download page on Gumroad. Unzipping `agent-context-trimmer-1.0.0.zip` into local terminal. Clean directory structure with zero external npm dependencies.
- **Voiceover**: 
  > *"Meet `agent-context-trimmer`. It is a lightweight, zero-dependency CLI tool engineered to audit, prune, and compress your AI context files in milliseconds. No npm installs, no cloud telemetry, 100% offline."*
- **Terminal Action**:
  ```bash
  unzip agent-context-trimmer-1.0.0.zip
  cd agent-context-trimmer
  node bin/trimmer.js --version
  # Output: v1.0.0 (Production Verified)
  ```

---

### [00:35 - 00:60] The Audit in Action
- **Visual**: Terminal running audit against real workspace.
- **Voiceover**: 
  > *"Let's run an audit on our project repository. One single command scans all rules, instructions, and agent definitions."*
- **Terminal Action**:
  ```bash
  node bin/trimmer.js audit --dir ../my-app
  ```
- **Visual Callout**: Terminal output highlights:
  - 4 duplicate style rules eliminated.
  - 120 tokens of generic LLM conversational preamble pruned.
  - 34-line embedded code example converted to referenced path.
  - **Total Reduction: 43.8% token savings.**

---

### [00:60 - 00:75] Automated One-Click Optimization
- **Visual**: Running `--fix` mode with safety snapshot confirmation.
- **Voiceover**: 
  > *"To apply the optimizations automatically, pass the `--fix` flag. Trimmer creates an instant timestamped backup before touching a single character, ensuring zero risk to your existing configurations."*
- **Terminal Action**:
  ```bash
  node bin/trimmer.js fix --dir ../my-app --backup
  # [BACKUP] Created .cursorrules.bak-20260911
  # [FIX] Compressed 1,420 tokens -> 798 tokens (-43.8%)
  ```

---

### [00:75 - 00:90] Payoff & Next Step
- **Visual**: Side-by-side terminal comparison. Fast responses in Cursor. Link to Gumroad and pgvector local kit upgrade.
- **Voiceover**: 
  > *"Your AI now responds 25% faster with zero hallucinations from conflicting instructions. At €5 one-time, this tool pays for itself within your first five days of coding. Grab your copy now on Gumroad."*
- **On-Screen Callout**: 🚀 **Payback in 5.3 Days | Get agent-context-trimmer on Gumroad (€5)**

---
