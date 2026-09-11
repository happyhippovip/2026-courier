# Developer Quick-Start Vertical Short Video Script (45 Seconds)
**Platform**: YouTube Shorts / X (Twitter) Video / TikTok  
**Aspect Ratio**: 9:16 Vertical (1080x1920)  
**Pacing**: Fast, developer-focused, no fluff  
**Target Action**: Visit Gumroad link & purchase (€5.00)  

---

## Shot-by-Shot Timeline

### [00:00 - 00:08] The Hook
- **Visual**: Tight crop of Cursor AI chat interface. A prompt takes 4.8 seconds to start streaming. Token counter shows 3,840 context tokens.
- **Voiceover**: 
  > *"If your AI coding assistant feels sluggish, check your rules file. You're probably sending thousands of tokens of duplicate instructions on every single prompt."*
- **Text Overlay**: 🛑 **Stop Paying the Hidden Context Tax**

---

### [00:08 - 00:20] The Problem
- **Visual**: Quick scrolling through bloated `.cursorrules` and `AGENTS.md` files filled with markdown code blocks and conversational preambles.
- **Voiceover**: 
  > *"Every stale example and repeated guideline adds hundreds of milliseconds of latency and eats your token budget."*
- **Visual Callout**: 
  ```
  Before: 2,400 tokens / prompt | 1500 req/mo = $10.80/mo wasted
  ```

---

### [00:20 - 00:35] The 2-Second Fix
- **Visual**: Terminal opens. Clean command execution:
  ```bash
  node bin/trimmer.js audit --dir .
  ```
  Terminal spits out clean color-coded savings matrix.
- **Voiceover**: 
  > *"Agent Context Trimmer audits your workspace offline in milliseconds. Run it once with `--fix --backup`, and watch your rules compress by 40 to 50% without losing a single instruction."*
- **Visual Callout**: 
  ```
  [OPTIMIZED] 2,400 -> 1,340 tokens (-44.2%)
  [SPEED] Latency reduced by -235ms / request
  ```

---

### [00:35 - 00:45] Call to Action
- **Visual**: Gumroad checkout page showing €5.00 one-time price. Download package unzips instantly.
- **Voiceover**: 
  > *"Zero dependencies, 100% private, pays for itself in less than a week. Grab it now for €5 on Gumroad."*
- **Text Overlay**: 🚀 **Get agent-context-trimmer (€5) | Link in Bio / Comments**

---
