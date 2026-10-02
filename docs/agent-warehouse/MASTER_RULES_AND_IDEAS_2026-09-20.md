# Courier Symphony — Master Rules & Ideas Snapshot

Date: 2026-09-20  
Status: founder working master / public-safe snapshot  
Purpose: preserve the important rules, product ideas, operating conventions, commercialization direction, cloud direction and agent-working assumptions discussed during setup.

> This file is intentionally PUBLIC-SAFE. Never add credentials, tokens, private keys, customer data, private emails, browser cookies, account IDs, exact secret paths, payment data or confidential infrastructure secrets here.

---

## 1. Product identity

**Confirmed project/product name: Courier Symphony.**

Do not use "Corineria Symphonie" as the product name. That was an earlier/incorrect logo-generation wording.

Brand direction:
- modern premium technology brand;
- green / emerald / teal identity;
- infinity symbol as a recurring visual motif;
- social-media-ready square logo variants;
- Maldives/tropical variants may use palm/island/wave motifs for campaign creatives;
- keep the core company/product wordmark clearly "Courier Symphony".

---

## 2. Core promise: Goal -> Done

Courier Symphony should not be "just another chatbot".

The intended user experience is:

```
USER GOAL
-> understand goal
-> ask only critical missing questions
-> plan
-> choose suitable agents/tools/models
-> execute
-> persist result
-> verify
-> reconcile
-> continue
-> deliver result
```

Customer examples:
- "I want to start a bakery."
- "I want to start a pizza delivery business."
- "Build the website for my business."
- "Create a content system for YouTube/TikTok."
- "Find the old email/document/decision and continue from it."
- "Take this idea and prepare everything you can."

The user should not need to understand model names, terminals, tools or agent routing.

---

## 3. Durable autonomous work rules

Target behavior:
- work should continue without a human typing "continue" after every safe completed step;
- exactly one externally active task at a time when serial execution is required;
- persist results before moving on;
- verify before marking DONE;
- reconcile verified result into durable state;
- only then admit the next READY task;
- ambiguous/UNKNOWN outcomes must block the next external action;
- pause/resume/stop-after-current must remain predictable;
- do not pre-create enormous task queues;
- visible infinity/unlimited UI is a product display concept, not permission to allocate infinite work;
- long-run mode should remain bounded internally by sane technical safeguards.

Ideal flow:

```
GOAL
-> durable state
-> qualified worker
-> dispatch
-> real work
-> durable result
-> verify
-> reconcile
-> next READY task
-> DONE or genuine HUMAN / MONEY / SAFETY / PERMISSION gate
```

---

## 4. Courier AI / customer assistant

Courier should contain a lightweight integrated AI assistant for customers.

Goals:
- easy product questions;
- next-step help;
- error/help guidance;
- retrieval of known solutions;
- simple explanations;
- inexpensive operation;
- provider-neutral architecture.

Customer-facing wording should be closer to:
**"AI included in your plan"**
rather than promising "free forever".

Use the cheapest sufficient model/tool for routine questions and reserve stronger models for tasks where they add value.

---

## 5. Community Knowledge

The durable strategic asset is not one base model. It is Courier's own:
- knowledge;
- provenance;
- verified solutions;
- workflows;
- agent capabilities;
- feedback;
- project context;
- community-confirmed patterns.

Do NOT automatically treat every chat as truth.

Knowledge lifecycle:
```
candidate -> reviewed -> verified -> retrievable -> superseded/withdrawn
```

Keep:
- sources;
- version;
- verification state;
- tenant scope;
- confidence;
- retention;
- privacy/PII flags.

Private customer knowledge and public/community knowledge must remain separated.

---

## 6. Courier Guild / Gilde

Long-term concept:
**humans + specialist agents + reusable skills + verified community knowledge**.

Possible guild roles:
- research;
- writing/copy;
- coding/web;
- design;
- content production;
- QA/verification;
- industry specialists;
- mentors/community experts.

Courier orchestrates the route from goal to result rather than pretending one AI must do everything.

---

## 7. Website Factory

A user can state a business goal and Courier should be able to prepare a full web-project workflow:
- business positioning;
- naming ideas;
- audience;
- information architecture;
- pages;
- copy;
- FAQ;
- assets/visual brief;
- implementation;
- QA;
- handoff for publication.

Domain purchase, payment, legal publication obligations and final public deployment remain explicit gates.

---

## 8. Mail + Archive + digital memory

Courier should reduce the need to manually search old email and scattered documents.

Desired capabilities:
- searchable mail/document archive;
- link decisions to projects/tasks/results;
- preserve prior solutions;
- retrieve "what did we decide last time?";
- create reusable project memory;
- customer-controlled retention/export/deletion.

Do not commit private mailbox content to public GitHub.

---

## 9. YouTube + TikTok pipelines

Existing product direction includes content-production pipelines.

YouTube style:
```
IDEA -> SCRIPT -> ASSET_SELECTION -> VIDEO_BUILD -> REVIEW -> METADATA -> READY_TO_PUBLISH
```

TikTok style:
```
IDEA -> HOOK -> SCRIPT -> 3D_ASSET_OR_SCENE -> VERTICAL_VIDEO_BUILD -> REVIEW -> CAPTION_HASHTAGS -> READY_TO_PUBLISH
```

Important:
**READY_TO_PUBLISH != PUBLISHED.**

Public publishing remains a separate approval/policy gate.

---

## 10. Cost and packaging direction

Working commercial hypothesis:
- simple monthly customer package;
- roughly EUR 99–100/month as a hypothesis, not a final price;
- useful routine AI/agent usage included;
- internal fair-use/cost envelope;
- no silent surprise overages;
- unusually expensive tasks get an explicit extra quote first;
- internal model routing may use credits/budgets/task classes, but customer UI stays simple.

Customer flow:
```
GOAL -> PLAN -> INCLUDED OR EXTRA QUOTE -> EXECUTE -> VERIFY -> RESULT
```

Final pricing must be validated with real unit economics before launch.

---

## 11. Cloud direction

Cloud is intended to support durable Courier operation, agent work, data and future customer usage.

Logical target layers:
- Web/API;
- PostgreSQL;
- vector search / pgvector or equivalent;
- object storage for media/artifacts;
- worker queue;
- secret manager;
- backup/restore;
- audit/metrics/monitoring.

Rules:
- Git is not the primary store for large media or private application state;
- secrets belong in a secret manager;
- private customer state belongs in private data stores;
- restore must be tested before cutover;
- preserve rollback;
- do not retire local/old environment until cloud restore and end-to-end behavior are proven.

---

## 12. Security / public-sharing rule

Infrastructure screenshots are INTERNAL by default.

Never publicly expose without redaction:
- credentials;
- private keys;
- access/secret/session tokens;
- cookies;
- passwords;
- MFA/recovery codes;
- account identifiers where unnecessary;
- public server attribution details where unnecessary;
- instance identifiers;
- key-pair names;
- internal paths;
- terminal history;
- private email/customer data.

If a screenshot only contains non-secret infrastructure metadata, that is still useful reconnaissance information and should be redacted before public posting.

Post-quantum security is a future architecture/security-roadmap item, but it does not replace:
- MFA;
- IAM least privilege;
- secret management;
- key rotation;
- security groups/firewalling;
- audit logs;
- backups;
- privacy hygiene.

---

## 13. Founder / administrator working mode

When the administrator is present:
- use screenshot-driven guidance;
- always identify DEVICE + WINDOW;
- give one concrete next action;
- keep explanations short unless a new risk appears;
- minimize window count;
- never make the operator infer where to paste a command.

Exact labels:
- WINDOWS PC — POWERSHELL
- WINDOWS PC — MUSE
- WINDOWS PC — CLAUDE CODE TERMINAL
- MACBOOK — NORMAL TERMINAL
- MACBOOK — MUSE
- MACBOOK — CLAUDE CODE TERMINAL
- MACBOOK — CLAUDE DESKTOP APP
- MACBOOK — AWS BROWSER
- IPHONE — REMOTE CONTROL
- AWS CLOUD — SSH SESSION

Default status:
```
ACTIVE: <device + window>
OTHER DEVICE: WAIT or PARALLEL
AWS: READ-ONLY / ACTIVE / NOT CONNECTED
```

---

## 14. Minimal-window principle

Preferred normal workspace:
- ChatGPT = coordination/overview;
- Courier Symphony = product;
- Muse = minimized until execution is needed;
- one ops terminal only;
- Antigravity = only for active development/debug;
- AWS browser/cloud tools = only while doing cloud work.

Do not delete apps or data merely to make the desktop visually cleaner.
Minimize uncertain windows first; close only after confirming they do not own required processes.

---

## 15. Muse autonomy rules

Desired operational experience:
- no repetitive "Proceed?" clicking for trusted autonomous runs;
- trusted workspace;
- autonomous serial work;
- sandbox/security boundaries should remain enabled unless there is a separately reviewed reason to change them.

Known working direction from Muse 1.3.0 setup:
- use a dedicated Auto launcher;
- `--trust-workspace`;
- `--approval-mode never`;
- keep sandbox enabled;
- normal launcher can remain on-request as a safer fallback.

Do not treat `--yolo` / sandbox disablement as required for autonomy. Approval-free operation and sandboxing are separate concerns.

If confirmations remain, first diagnose whether they come from:
- Muse approval;
- Muse sandbox;
- macOS/Windows permission;
- sudo/admin password;
- Claude Code approval;
- browser login;
- another owner.

---

## 16. Agent manager / boss-mode behavior

The assistant/manager should:
- decide sequence;
- reduce duplicate work;
- keep one source of truth;
- preserve current state;
- use cheap/read-only checks before expensive actions;
- separate Windows, Mac and Cloud tasks;
- say explicitly when the other machine should WAIT;
- avoid opening extra terminals;
- preserve backups before risky changes;
- stop guessing once evidence is ambiguous.

---

## 17. Beta -> friends -> commercial launch

Founder direction:
1. stabilize Courier;
2. preserve/organize project memory;
3. simplify user experience;
4. let trusted friends test it;
5. demonstrate what Courier can do;
6. learn from real use;
7. improve knowledge/workflows;
8. prepare a larger commercial product launch.

Marketing message:
**One goal. Courier organizes the work. Verified result out.**

---

## 18. IP / anti-copy direction

Public demos do not grant a license to copy protected implementation.

Protect where applicable:
- source code;
- UI/design;
- texts/documentation;
- curated datasets;
- specific pipeline implementation;
- workflow implementation;
- proprietary internal tooling;
- trademarks/wordmarks;
- confidential know-how.

Do not falsely claim exclusive ownership of generic ideas such as "AI agents", "infinity symbol", "YouTube automation" or "TikTok automation".

---

## 19. Canonical references

This master snapshot summarizes but does not replace the detailed documents under:
`docs/agent-warehouse/`

Important:
- PRODUCT_VISION_AND_FEATURE_MAP_2026-09-20.md
- AI_COMMUNITY_KNOWLEDGE_ARCHITECTURE_2026-09-20.md
- CONTENT_PIPELINES_2026-09-20.md
- CLOUD_MIGRATION_HANDOFF_2026-09-20.md
- CUSTOMER_PACKAGING_AND_COST_GUARDRAILS_2026-09-20.md
- OPERATOR_INTERACTION_PROTOCOL_2026-09-20.md
- SESSION_HANDOFF_2026-09-20.md
- IP_BRAND_LEGAL_DRAFT_2026-09-20.md
- BRAND_AND_LOGO_2026-09-20.md

Also respect existing technical canonical docs under `docs/`.

---

## 20. Rule for future additions

Whenever an important new idea/rule is agreed:
1. decide whether it is product, operations, security, cloud, legal, brand or commercialization;
2. write it into the appropriate detailed document;
3. add/update the manifest;
4. update this master snapshot if it changes a core rule;
5. never put secrets into the public repository.
