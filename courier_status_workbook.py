"""Courier Symphony status workbook generator (INITIAL TEMPLATE).

Builds a REAL editable .xlsx (stdlib only) from verified session evidence via
the repo's own courier_runtime.workbook machinery (reuse, no openpyxl needed).

Run once in a working shell from the repo root:
    python courier_status_workbook.py
Output: courier_status_YYYYMMDD-HHMMSS.xlsx next to this script.
The script self-verifies (read-back: cell count + formula markers).

Status: WRITTEN shell-less, NOT YET EXECUTED. First shell run is the proof.
Data stand: 2026-10-08 (META re-verified, UPDATES section added).
Update path: re-run this generator (workbook.apply() refuses formula cells).
Unknowns are labeled UNKNOWN in the sheet itself. Single Sheet1 only
(make_fixture has no multi-sheet/autoFilter support; filters stay manual).
"""
import datetime
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from courier_runtime import workbook as WB

COLS = "ABCDEF"


def cell(col, row):
    return f"{COLS[col]}{row}"


def build_cells(stand_utc):
    c = {}
    c["A1"] = "COURIER SYMPHONY — STATUS (INITIAL TEMPLATE)"
    c["B1"] = "Stand (UTC):"
    c["C1"] = stand_utc

    # META (rows 3-8)
    c["A3"] = "META"
    for i, h in enumerate(["key", "value", "source"]):
        c[cell(i, 4)] = h
    for r, row in enumerate([
        ["trunk SHA", "f425d3285", "GitHub API 2026-10-07 ~22:44Z (kann neuer sein)"],
        ["trunk re-check", "f425d3285 still tip", "GitHub API 2026-10-08 (Session)"],
        ["checkout", "UNKNOWN (Konflikt)", "5dea6473 (packed-refs) vs 330f5f01e140 (session.jsonl), beide UNVERIFIED"],
        ["generator", "courier_status_workbook.py + courier_runtime.workbook", "Repo"],
        ["coverage", "25+ PRs gesichtet, 82 offen (Stand 23:57Z)", "GitHub API"],
    ], start=5):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # WORKKEYS (rows 10-18)
    c["A10"] = "WORKKEYS"
    for i, h in enumerate(["key", "owner", "status", "branch/sha", "evidence", "next"]):
        c[cell(i, 11)] = h
    for r, row in enumerate([
        ["FREE-1", "FREE", "open, recipe ready", "trunk scripts/windows_worker/dist/*",
         "handoff forensics + raw 200/947B", "Shell: git rm + PR"],
        ["E-L3-1+", "L3", "specified", "courier_worker/host.py dispatch job",
         "static verified (WIN-WORKER)", "Shell: live repro + fix"],
        ["E-L3-2", "L3", "specified", "host.py:920/725", "static verified", "Shell: wrap + test"],
        ["E-L3-3", "L3", "specified", "service.py:481/486", "static verified",
         "Shell: ResourcePaused path + test"],
        ["BREAKER-01..09", "Muse (breaker)", "patches ready, UNAPPLIED", "PR#153 @672e9bc1",
         "9 defects + 18 tests (Report)", "Shell: apply+pytest+push"],
        ["CAP-1", "L3", "gap, no PR", "host.py:182-214", "audit WIN4", "L3/Shell: Win CPU/RAM probe"],
        ["REVIEW-200", "Cursor bc-c8de3c1f", "handed off", "PR#200 @a7559a7",
         "R-200-1/2 (Report)", "Owner: bounded re-sample"],
    ], start=12):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # MILESTONES (rows 20-27)
    c["A20"] = "MILESTONES (locked route)"
    for i, h in enumerate(["stage", "status", "evidence/stand"]):
        c[cell(i, 21)] = h
    for r, row in enumerate([
        ["Golden path", "CI green (11/11 @#157-Base)", "PR#157 body, Stand ~21:2xZ"],
        ["Desktop Hub", "implemented + tested", "L5 doc + tests/hub (Repo)"],
        ["Windows EXE", "PR#133 open (owned)", "PR-Liste"],
        ["Clean-machine", "harness exists, live proof open", "#157 Unproven-Liste"],
        ["Real adapters", "PR#134 open (owned)", "PR-Liste"],
        ["Robot overlay", "NOT STARTED (no evidence)", "UNKNOWN ob begonnen"],
    ], start=22):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # PROVIDERS / COST (rows 29-35) — no cost source exists anywhere
    c["A29"] = "PROVIDERS / COST"
    for i, h in enumerate(["provider", "observed", "credits", "cost", "quota", "source"]):
        c[cell(i, 30)] = h
    for r, row in enumerate([
        ["Muse", "YES", "UNKNOWN", "UNKNOWN", "UNKNOWN", "diese Session"],
        ["Cursor", "YES", "UNKNOWN", "UNKNOWN", "UNKNOWN", "GitHub API (PRs)"],
        ["Codex", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "keine Quelle"],
        ["Antigravity", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "keine Quelle"],
        ["Grok", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "keine Quelle"],
    ], start=31):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # BUGS + REGRESSION (rows 37-52)
    c["A37"] = "BUGS + REGRESSION"
    for i, h in enumerate(["id", "severity", "where", "status", "test"]):
        c[cell(i, 38)] = h
    for r, row in enumerate([
        ["E-L3-1+", "HIGH", "host.py spawn/nested", "specified", "spec'd, needs shell"],
        ["E-L3-2", "HIGH", "host.py:920", "specified", "spec'd"],
        ["E-L3-3", "MED", "service.py:481", "specified", "spec'd"],
        ["BREAKER-01", "HIGH", "coord ledger from_dict", "patch ready", "T1 roundtrip"],
        ["BREAKER-02", "HIGH", "DONE-terminal", "patch ready", "T5-T7"],
        ["BREAKER-03", "MED", "cancel flag", "patch ready", "T8-T10"],
        ["BREAKER-04", "HIGH", "timestamps", "patch ready", "T11-T13"],
        ["BREAKER-05", "MED", "id-burn", "patch ready", "T13-T15"],
        ["BREAKER-06", "MED-HIGH", "validation", "patch ready", "T2-T4"],
        ["BREAKER-07..09", "MED/MED/LOW", "gh adapter", "patch ready", "T16-T18"],
        ["R-200-1", "MED", "guardian stabilize", "handed to owner", "owner adds"],
        ["R-200-2", "LOW", "guardian test gap", "handed to owner", "owner adds"],
        ["sandbox-defect", "BLOCKER", "Muse runtime", "needs restart", "probe after restart"],
        ["api-quota-0", "ENV", "GitHub shared IP", "transient", "1 cheap call"],
    ], start=39):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # WEBSITE (rows 54-57) — no source in session
    c["A54"] = "WEBSITE LAUNCH"
    for i, h in enumerate(["item", "status", "source"]):
        c[cell(i, 55)] = h
    for r, row in enumerate([
        ["launch status", "UNKNOWN (keine Quelle in Session)", "—"],
        ["staging/prod URL", "UNKNOWN", "—"],
    ], start=56):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # NEXT ACTIONS (rows 59-68)
    c["A59"] = "NEXT ACTIONS"
    for i, h in enumerate(["prio", "action", "owner", "gate"]):
        c[cell(i, 60)] = h
    for r, row in enumerate([
        ["P0", "Muse restart + shell probe", "Dennis", "user-seitig"],
        ["P0", "TUI /settings enge Allows prüfen", "Dennis", "user-seitig"],
        ["P1", "Varianten-Kollision #140/#145/#153 + base=main", "L1/Dennis", "Entscheidung"],
        ["P1", "FREE-1 ausführen (git rm + PR)", "Shell-Fenster", "Shell"],
        ["P1", "E-L3 live repro + fixes + CAP-1", "L3/Shell", "Shell"],
        ["P1", "BREAKER-Patches auf #153 anwenden+testen", "Shell/L2", "Shell"],
        ["P2", "#200 R-200-1 bounded re-sample", "Cursor-Owner", "Owner-PR"],
        ["P2", "Issue-Scan + Trunk-CI im Quota-Fenster", "Analyse-Fenster", "Quota"],
        ["P1", "#251 R-251-1 Quoting-Fix (/out: mit Leerzeichen)", "Cursor-Owner", "Owner-PR"],
    ], start=61):
        for i, v in enumerate(row):
            c[cell(i, r)] = v

    # SUMMARY with real formulas (rows 70-75)
    c["A70"] = "SUMMARY (formulas)"
    c["A71"] = "metric"
    c["B71"] = "value"
    c["A72"] = "workkeys listed"
    c["B72"] = "=COUNTA(A12:A18)"
    c["A73"] = "open bugs listed"
    c["B73"] = "=COUNTA(A39:A52)"
    c["A74"] = "providers observed"
    c["B74"] = '=COUNTIF(B31:B35,"YES*")'
    c["A75"] = "cost/quota cells (all UNKNOWN)"
    c["B75"] = "=COUNTA(C31:E35)"

    # UPDATES 2026-10-08 (rows 76-85) — appended, existing ranges untouched
    c["A76"] = "UPDATES 2026-10-08"
    for i, h in enumerate(["item", "kind", "status", "evidence", "next"]):
        c[cell(i, 77)] = h
    for r, row in enumerate([
        ["REVIEW-251", "review", "done, handed to owner", "PR#251 @1a4e4b48 (raw read)",
         "Cursor owner decides"],
        ["R-251-1", "bug MEDIUM", "open, owned (#251)", "/out: quotes lost vs trunk",
         "owner: quote path"],
        ["R-251-2/3", "bug LOW", "open, owned (#251)", "review note 2026-10-08",
         "owner: try/catch + stale-exe"],
        ["48H-A", "preflight", "complete (static)", "dispatcher+adapter code @f425d3285",
         "B..F need shell"],
        ["48H-B-LOGS", "evidence", "proven", "live session.jsonl 2026-10-08",
         "exec/flags need shell"],
        ["P0-rootcause", "finding", "exact mechanism filed", "proxy_only, targets:[]",
         "persist target needs shell"],
        ["STOP-CHECKPOINT", "ownership", "12/12 owned", "PR #239-251 bodies ~03:37Z",
         "re-sweep after restart"],
    ], start=78):
        for i, v in enumerate(row):
            c[cell(i, r)] = v
    c["A85"] = "update items listed"
    c["B85"] = "=COUNTA(A78:A84)"
    return c


def main():
    stand = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    cells = build_cells(stand)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "courier_status_%s.xlsx" % stand.replace(" ", "_").replace(":", ""))
    WB.make_fixture(out, cells)
    back = WB.read_cells(out)
    assert len(back) == len(cells), f"cell count {len(back)} != {len(cells)}"
    for ref in ("B72", "B73", "B74", "B75", "B85"):
        assert isinstance(back.get(ref), str) and back[ref].startswith("="), ref
    with open(out, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    print(f"OK {out}")
    print(f"cells={len(back)} sha256={digest}")


if __name__ == "__main__":
    main()
