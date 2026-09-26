# WALL-P2-DOWNLOAD-IA — download page IA + install prerequisites (PREP ONLY)

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=READ_ONLY · 2026-09-26
Observed 2026-09-26 on MAC (commands run, outputs exact):
- Repo root has NO pyproject.toml, NO uv.lock, NO setup.py, NO requirements.txt,
  NO setup.cfg, NO .python-version (all `ls: No such file or directory`).
- `python3 --version` → Python 3.9.13. `import flask` → 3.1.3 (system env).
- HEAD 332a42f9. INSTALLER STATUS: NOT YET EXISTING (mandatory label, see below).

## Page IA (static draft)
1. GET COURIER (download block) — always paired with the NOT-YET-EXISTING
   label until RV11's gate opens. No download button ships before then; the
   block shows prerequisites + "notify me" instead. (No fake download.)
2. PREREQUISITES (checklist with copy-paste checks):
   - Python ≥3.9 (`python3 --version`) — OBSERVED floor 3.9.13, not a promise
     of support below what CI proves. No pinned manifest exists yet → page
     must say "dependency list stabilizing" rather than print versions we
     cannot guarantee (only Flask 3.1.3 observed; nothing else inventoried).
   - git (candidate distribution is SHA-based today: `git cat-file -t <sha>`
     is literally the GO-gate — MMAC2).
   - Disk: workspace + state + artifacts + append-only evidence ledger live
     on-machine (RV11: separate data dir, survives updates).
   - macOS note: the dev-config path touches keychain (E15 §2) — the future
     installer MUST ship a keychain-free config path (RV17). Page lists this
     as a known requirement, not a solved fact.
3. INSTALL (placeholder section, visibly gated): "Installer does not exist
   yet — packaging is gated on the revenue-path close (RV19/GAP1). This page
   is the checklist the installer will satisfy." (RV11 gating note, adopted.)
4. VERIFY YOUR INSTALL (future): re-run of the canary proof-card recipe
   (RV08 fields) so a user can confirm their own machine reproduces
   A→VERIFY→B. Script does not exist yet — mark PLACEHOLDER, do not invent.
5. UNINSTALL (one screen, per RV11): remove runtime + logs + (on consent)
   state; verify no second scheduler/wall/ledger remains.

## Forbidden (honored)
No "Download now" button, no version number, no supported-platforms matrix,
no "5-minute setup" claim — none of these exist. UNKNOWN stays UNKNOWN.

STATUS=DRAFT_COMPLETE · complements RV11 (checklist) with page structure
