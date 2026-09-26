# WEBSITE_00: COURIER WEBSITE LAUNCH PACKAGE MASTER INDEX

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Package Complete  
**OUTPUT DIRECTORY**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/`  
**DATE**: 2026-09-26  
**BASELINE REPOSITORY**: `/Users/user/Downloads/2026-courier` (Clean, Unmodified)

---

## 1. Executive Summary & Launch Package Architecture

This launch package prepares the complete content, structure, copy, evidence, and commercial agreements for the Courier website (`courier.sh` / `courier-symphony.com`).

It is constructed under strict adherence to the **Evidence Gate Rule**:
> *"Never turn an unproven claim into marketing text. Leave the website content ready so proof -> publish is fast."*

```
+──────────────────────────────────────────────────────────────────────────────────────────────────────────+
| COURIER WEBSITE LAUNCH PACKAGE MANIFEST                                                                   |
+───────────────────────────────────+──────────────────────────────────────────────────────────────────────+
| ARTIFACT                          | PRIMARY CONTENT MODULES & SCOPE                                      |
+───────────────────────────────────+──────────────────────────────────────────────────────────────────────+
| WEBSITE_00_LAUNCH_PACKAGE_INDEX   | Master index, architectural compliance, gate readiness, quickstart.  |
| WEBSITE_01_LANDING_PAGE_AND_HERO  | Landing page structure, hero copy, 3-step loop (Auftrag/Geprüft/     |
|                                   | Als_Nächstes), honest limits block, differentiation pillars.          |
| WEBSITE_02_PILOT_AND_WAITLIST     | Pilot page, waitlist form fields, 3-minute manual onboarding flow,   |
|                                   | deposit pricing copy (€500 pilot / 100% money-back guarantee).       |
| WEBSITE_03_FAQ_AND_PRODUCT_RULES  | Evidence-gated FAQ, Grandma Test explanation, No-Permission-Spam     |
|                                   | (Single Scope Autonomy), Fast-Track 48H deadline execution mode.     |
| WEBSITE_04_TRUST_PRIVACY_DATAFLOW | Trust & Evidence section, live Proof Card specification, privacy     |
|                                   | summary (zero model training), unidirectional local data flow.       |
| WEBSITE_05_DOWNLOAD_AND_INSTALL   | Download page structure, macOS installation prerequisites, support   |
|                                   | and automated incident reporting, 60-second video demo storyboard.   |
| WEBSITE_06_PUBLIC_CLAIM_DISCIPLINE| Master Claims Registry (15 claims evaluated with proof citations),    |
|                                   | Red-line Anti-Hype vocabulary guide, Gate transition criteria.       |
+───────────────────────────────────+──────────────────────────────────────────────────────────────────────+
```

---

## 2. Hard Boundaries & Invariant Compliance

1. **Product Shell Invariant**: **NO PRODUCT SHELL WAS BUILT**. All work is strictly confined to independent website copy, structured schemas, evidence mappings, and markdown launch artifacts under `OUTPUT`.
2. **Final Candidate Invariant**: **NO REPOSITORY CODE OR COMMITS MODIFIED**. The running candidate on branch `agent/canonical-wall-supervisor-v2` (@ `332a42f9`) remains untouched.
3. **No Capabilities Invented**: Every product assertion is mapped to an existing test in `tests/`, an existing contract in `scripts/`, or an existing report in `reports/`. Unproven roadmap items (e.g. 1-click DMG installer, self-serve credit card checkout, Windows enterprise clustering) are explicitly quarantined with `SAFE_TO_PUBLISH_NOW=NO`.
4. **Single-Writer Safety**: All live writer processes (e.g. `PID 61758` on Mac singlewriter lane) and supervisors remain undisturbed.

---

## 3. Immediate Path: Proof $\rightarrow$ Publish Cadence

When the final physical proof passes in the runner lane:
1. **Step 1: Checksum Injection (< 5 minutes)**:
   - Extract real SHA-256 hashes, timestamps, and run IDs from the physical proof card.
   - Replace the placeholders in `WEBSITE_01` (Hero Proof Card) and `WEBSITE_05` (Demo Storyboard).
2. **Step 2: Static Site Generation (< 15 minutes)**:
   - Render the 6 markdown artifacts directly into static HTML via existing templates (`website/` directory).
3. **Step 3: Verification & Go-Live (< 10 minutes)**:
   - Verify that all claims on the live staging preview match `WEBSITE_06` approved claims.
   - Deploy static assets to host.
