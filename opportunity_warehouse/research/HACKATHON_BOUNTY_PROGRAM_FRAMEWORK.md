# Symphony Developer Hackathon & Community Bounty Program Framework

**Objective**: Accelerate community-contributed AST pruning rules, language adapters, and editor extensions.  
**Sponsor**: Symphony Autonomous Commercial Ecosystem  
**Total Bounty Pool**: €5,000 (Allocated across 30+ prizes and micro-bounties)  

---

## 1. Bounty Categories & Prize Tiers

### Category A: Language-Specific AST Rule Packs (€100 - €250)
Developers contribute AST pruning rules for languages with verbose syntax:
- **Rust Pack**: Prune redundant `derive` macros, cargo build noise, and repetitive lifetime annotations.
- **Go Pack**: Collapse redundant `if err != nil` boilerplate in prompt contexts while preserving error types.
- **Godot / GDScript Pack**: Prune scene file metadata and redundant node signals.
- **Solidity Pack**: Strip NatSpec noise while preserving function signatures and security modifiers.

### Category B: IDE & Editor Integrations (€250 - €500)
- **VS Code Extension**: Status bar showing live tokens trimmed and instant button to trigger pre-commit trim.
- **JetBrains Plugin**: Right-click context menu: "Trim Selected Prompt".
- **Neovim / Lua Plugin**: Buffer save hook invoking `agent-context-trimmer`.

### Category C: Performance & Compression Algorithmic Breakthroughs (€500)
- Implement streaming regex engines or SIMD-accelerated string scanning achieving >5x speedup on 10MB prompt files.

---

## 2. Submission & Automated Evaluation Rubric

Every PR submitted to the open repository must pass automated CI gates:
1. **Rule Diff Compatibility**: Must score >= 90/100 on `test_rule_diff.js` with 0 breaking changes.
2. **Deterministic Test Coverage**: Must include dedicated unit test suite with 100% pass rate.
3. **Semantic Retention Rate**: Must maintain >= 98% symbol retention on `test_benchmark_harness.js`.
4. **Zero Dependencies**: Must use 100% native Node.js built-in modules.

---

## 3. Payout & Award Distribution Workflow
1. Contributor forks repository and implements rule pack in `experiments/<pack_name>`.
2. Contributor opens PR with `[BOUNTY_SUBMISSION]` tag.
3. GitHub Action executes `run_all_experiment_tests.js`.
4. Upon deterministic green verification and review approval, bounty is issued via direct SEPA transfer or GitHub Sponsors payout within 48 hours.

---

## 4. Timeline & Launch Milestones
- **Day 1**: Public announcement on Hacker News & Twitter/X.
- **Day 1–14**: Rolling micro-bounty awards (€100/submission).
- **Day 21**: Hackathon Grand Prize Winners selected by Symphony Core Architecture Board.
