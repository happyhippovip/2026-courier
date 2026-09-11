# POST-PURCHASE ACTIVATION & REFERRAL ENGINE
**DOCUMENT:** `opportunity_warehouse/research/POST_PURCHASE_ACTIVATION_GUIDE.md`  
**TARGET CAPABILITY:** `agent-context-trimmer v1.0.0`  
**OBJECTIVE:** Ensure 100% of buyers succeed in under 60 seconds and turn customer #1 into an organic distribution channel.

---

## 1. The Critical "First 60 Seconds" Rule
If a developer buys a €5 tool and struggles with node versions, permissions, or missing documentation, they will:
1. Abandon the tool.
2. Request a Gumroad refund.
3. Post negative feedback.

If the tool runs in **under 30 seconds** and prints an immediate token saving number:
1. They feel instant dopamine (ROI validated).
2. They share the terminal screenshot with colleagues or on X/Discord.
3. They become a recurring customer for future Symphony micro-tools.

---

## 2. Zero-Friction Onboarding Flow (To include in Gumroad Receipt)

```markdown
### Thank you for purchasing Agent Context Trimmer!

Here is how to audit your project in 30 seconds:

1. **Unzip the package:**
   ```bash
   unzip PRODUCT_PACKAGE.zip -d agent-context-trimmer
   cd agent-context-trimmer
   ```

2. **Run the Instant Audit on your workspace:**
   ```bash
   node bin/agent-context-trimmer.js /path/to/your/project
   ```

3. **View the visual report:**
   Open the generated `context_audit_report.html` in your browser to inspect exact wasted tokens and estimated monthly savings!

### Optional: Pre-Commit Hook Integration
Add this one-liner to your `.git/hooks/pre-commit` to prevent bloated rules from ever being committed:
```bash
node /path/to/agent-context-trimmer/bin/agent-context-trimmer.js . --ci
```
```

---

## 3. The Organic Referral Loop (The Post-Audit Share Hook)

When `agent-context-trimmer` finishes scanning, the terminal output includes a non-intrusive 1-line share prompt:
```text
----------------------------------------------------------------------
✨ Saved 5,150 tokens per prompt turn! ($37.08/mo projected savings)
Share your score on X:
"Audited my .cursorrules with Agent Context Trimmer: cut 35.8% token bloat!"
----------------------------------------------------------------------
```

This turns every satisfied customer into an autonomous marketing node at zero acquisition cost.
