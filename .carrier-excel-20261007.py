"""Build Courier_Symphony_Status_2026-10-07.xlsx from verified session evidence.

One-shot generator (deleted after use). Genuine values only; unknowns are
visibly labeled UNBEKANNT with peach fill. Status cells get light fills,
every table gets filters + frozen header + count formulas.
"""

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

OUT = Path(r"C:\Users\lol\Desktop\Courier_Symphony_Status_2026-10-07.xlsx")

HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF")
UNK_FILL = PatternFill("solid", fgColor="FCE4D6")  # peach = unknown/unmeasured
STATUS_FILL = {
    "PROVEN": PatternFill("solid", fgColor="C6EFCE"),
    "CONTAINED": PatternFill("solid", fgColor="DDEBF7"),
    "CHECKPOINTED": PatternFill("solid", fgColor="DDEBF7"),
    "OPEN": PatternFill("solid", fgColor="FFEB9C"),
    "QUEUED": PatternFill("solid", fgColor="FFEB9C"),
    "BLOCKED": PatternFill("solid", fgColor="FFC7CE"),
    "WATCHING": PatternFill("solid", fgColor="FFEB9C"),
    "MONITORING": PatternFill("solid", fgColor="FFEB9C"),
    "AUSSTEHEND": PatternFill("solid", fgColor="FFEB9C"),
    "UNPROVEN": PatternFill("solid", fgColor="FCE4D6"),
    "UNBEKANNT": PatternFill("solid", fgColor="FCE4D6"),
}


def base_status(value):
    s = str(value).upper()
    for key in STATUS_FILL:
        if s.startswith(key):
            return key
    return None


def make_sheet(wb, name, headers, rows, widths, status_col=None, stats=None):
    ws = wb.create_sheet(name)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = HDR_FONT
        cell.fill = HDR_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for r, row in enumerate(rows, 2):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if isinstance(v, str) and v.startswith("UNBEKANNT"):
                cell.fill = UNK_FILL
    if status_col:
        for r in range(2, 2 + len(rows)):
            key = base_status(ws.cell(row=r, column=status_col).value)
            if key:
                ws.cell(row=r, column=status_col).fill = STATUS_FILL[key]
    last_col = openpyxl.utils.get_column_letter(len(headers))
    ws.auto_filter.ref = f"A1:{last_col}{1 + len(rows)}"
    ws.freeze_panes = "A2"
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    if stats:
        sr = 3 + len(rows)
        for label, formula in stats:
            ws.cell(row=sr, column=1, value=label).font = Font(bold=True)
            ws.cell(row=sr, column=2, value=formula)
            sr += 1
    return ws


wb = openpyxl.Workbook()
wb.remove(wb.active)

make_sheet(wb, "Legende",
    ["Bereich", "Bedeutung"],
    [
        ["PROVEN / BELEGT + Datum", "Live in dieser Session auf Windows bewiesen"],
        ["CONTAINED / CHECKPOINTED", "Arbeit sicher zwischengelagert, fortsetzbar"],
        ["OPEN / QUEUED / BLOCKED", "Offen / wartend / fremdblockiert"],
        ["UNBEKANNT (pfirsich)", "Nicht gemessen oder nicht verifiziert — kein Raten"],
        ["Quelle LIVE 2026-10-07", "Eigener Shell-/Test-Lauf vom 2026-10-07"],
        ["Quelle Handoff/GitHub", "Datei im Repo bzw. GitHub-API vom 2026-10-07"],
        ["Stand", "2026-10-07 abends, Trunk b9fc486a sofern genannt"],
    ], [30, 60])

wk = [
    ["L3-windows-terminate-verify", "Muse 01a11819", "lane/L3-windows-terminate-verify", "b9fc486a", "CHECKPOINTED", "2/2 Tests grün (RED→GREEN), Modul 48/50, Golden 11/11 auf Basis", "Stash-Vergleich, dann Commit/Push/PR", "LIVE 2026-10-07"],
    ["L3-RUNONCE-CLAIM-HARDEN", "Fremde Session 01a1180e", "lane/L3-runonce-claim-hardening", "UNBEKANNT", "CONTAINED (Stash)", "Diff in stash@{0} (2 Dateien), Spec in Checkpoint-Datei", "Owner poppt Stash, verifiziert, PR", "Triage 2026-10-07"],
    ["GAP1 stop-bat", "UNBEKANNT (frei)", "–", "b9fc486a", "OPEN", "Handoff win_acceptance_gap_stop_close", "L6-Fix + Live-Beweis", "Handoff 2026-10-07"],
    ["GAP2 restart-reconnect", "L1 (sequenziert)", "–", "b9fc486a", "BLOCKED (#157)", "Handoff win_acceptance_gap_restart", "Warten auf PR #157", "Handoff 2026-10-07"],
    ["GAP3 install-uninstall", "UNBEKANNT (frei)", "–", "b9fc486a", "OPEN (VM nötig)", "Handoff win_acceptance_gap_real_install", "Scratch-VM-Beweis nötig", "Handoff 2026-10-07"],
    ["FREE-1 dist-cleanup", "UNBEKANNT (frei)", "–", "b9fc486a", "OPEN", "Forensik-JSON mit Rezept", "Rezept aus Forensik umsetzen", "Handoff 2026-10-07"],
    ["P0 approval-friction", "Muse-Runtime + Dennis", "–", "–", "OPEN (Freigabe)", "check=ready, admit=deny (bewiesen)", "muse sandbox windows setup freigeben", "LIVE 2026-10-07"],
    ["Dashboard-Akzeptanz", "UNBEKANNT (frei)", "–", "b9fc486a", "QUEUED", "Auftrag da, hub/server+model gelesen", "Scope claimen, Invarianten testen", "Auftrag 2026-10-07"],
    ["PR #181 L3-Supervisor", "UNBEKANNT", "UNBEKANNT", "a9e8902 (PR-SHA)", "OPEN (PR)", "PR-Body gelesen, Mac-Fokus", "Review/Gap-Audit", "GitHub 2026-10-07"],
]
n = len(wk) + 1
make_sheet(wb, "Workkeys",
    ["Workkey", "Owner", "Branch", "Basis", "Status", "Evidenz", "Nächste Aktion", "Quelle"], wk,
    [26, 20, 30, 12, 18, 44, 40, 18], status_col=5,
    stats=[("Anzahl", f"=COUNTA(A2:A{n})"), ("Offen/Queued", f'=COUNTIF(E2:E{n},"OPEN*")+COUNTIF(E2:E{n},"QUEUED")')])

ms = [
    ["Trunk integration/v1", "b9fc486a LIVE", "fetch + golden", "2026-10-07", "LIVE"],
    ["Golden 11/11 Windows", "PROVEN", "121.86s, Tree clean", "2026-10-07", "LIVE"],
    ["L3 Fix + Tests", "CHECKPOINTED", "2/2 grün nach RED", "2026-10-07", "LIVE"],
    ["Modul-Gate L3", "48/50 (Timing-Flake)", "wakes=5 statt ≤3", "2026-10-07", "LIVE"],
    ["Sandbox-Reparatur", "AUSSTEHEND", "Freigabe-Anfrage gestellt", "UNBEKANNT", "Auftrag"],
    ["Dashboard-Abnahme", "QUEUED", "–", "UNBEKANNT", "Auftrag"],
]
m = len(ms) + 1
make_sheet(wb, "Meilensteine",
    ["Meilenstein", "Status", "Evidenz", "Datum", "Quelle"], ms,
    [26, 24, 34, 14, 12], status_col=2,
    stats=[("Anzahl", f"=COUNTA(A2:A{m})"), ("Proven", f'=COUNTIF(B2:B{m},"PROVEN")+COUNTIF(B2:B{m},"*LIVE")')])

make_sheet(wb, "Provider_Kosten",
    ["Provider", "Kennzahl", "Wert", "Quelle"],
    [
        ["Muse", "Verbrauchte Credits", "UNBEKANNT (nicht gemessen)", "–"],
        ["Muse", "Kosten", "UNBEKANNT (nicht gemessen)", "–"],
        ["Antigravity", "Verbrauch/Kosten", "UNBEKANNT (nicht gemessen)", "–"],
        ["GitHub API", "Quote (unauth, geteilte IP)", "LIMIT ERREICHT (403), Search-API OK", "LIVE 2026-10-07"],
        ["Host", "RAM frei", "1304/16219 MB (8%)", "LIVE 2026-10-07"],
        ["Host", "Prozesse", "Antigravity + mind. 3 Muse-Bins", "LIVE 2026-10-07"],
    ], [16, 30, 42, 18])

bg = [
    ["F-001 Sandbox-Admit", "Default-Shell immer deny", "MUSE_RUNTIME", "OPEN", "Sentinel-Probe", "check=ready vs admit=deny"],
    ["F-002 Prompt-pro-Call", "Jedes escalated promptet", "MUSE_RUNTIME", "OPEN", "–", "15+ Calls beobachtet"],
    ["F-007 Terminate-Unverified", "Job-Kill ungeprüft + unbounded", "L3 (eigene Session)", "FIX CHECKPOINTED", "2 neue Tests", "RED→GREEN 1.09s"],
    ["F-008 Golden 11/11", "Positivbeleg", "–", "PROVEN", "tests/golden", "121.86s, clean"],
    ["WAKES-FLAKE", "wakes=5 vs ≤3 im Full-File-Lauf", "UNBEKANNT (Umgebung?)", "UNPROVEN", "–", "2× fail full, 1× pass solo"],
]
b = len(bg) + 1
make_sheet(wb, "Bugs_Regressionen",
    ["ID", "Symptom", "Owner", "Status", "Regressionstest", "Beleg"], bg,
    [24, 36, 20, 18, 22, 30], status_col=4,
    stats=[("Anzahl", f"=COUNTA(A2:A{b})"), ("Offen/Unproven", f'=COUNTIF(D2:D{b},"OPEN")+COUNTIF(D2:D{b},"UNPROVEN")')])

make_sheet(wb, "Website_Launch",
    ["Punkt", "Status", "Evidenz"],
    [
        ["Launch-Termin", "UNBEKANNT", "Keine aktuelle Evidenz in dieser Session"],
        ["Inhalt/Umfang", "UNBEKANNT", "Alte Notiz (Sept): nur Dashboard-Surface, ungetestet"],
        ["Blocker", "UNBEKANNT", "Muss verifiziert werden"],
    ], [22, 16, 60], status_col=2)

ac = [
    [1, "Stash-Vergleich wakes-Flake (1 Shell-Call)", "L3-wtv", "Shell-Freigabe", "eigene Session"],
    [2, "muse sandbox windows setup freigeben", "P0", "Dennis (Human-Gate)", "Dennis"],
    [3, "Terminate-Scope klären (Fremd-Branch)", "L3-wtv", "L1/PR-Check", "L1 + eigene Session"],
    [4, "Commit+Push+PR L3-Fix", "L3-wtv", "1+3, Publikations-Gate", "eigene Session"],
    [5, "Dashboard-Scope claimen", "Dashboard", "–", "UNBEKANNT"],
    [6, "Runonce-Stash zurückholen", "L3-runonce", "Owner-Session", "fremde Session"],
    [7, "RAM entlasten (sichere Fenster)", "–", "Custody", "Dennis"],
]
make_sheet(wb, "Naechste_Aktionen",
    ["Prio", "Aktion", "Workkey", "Blockiert durch", "Owner"], ac,
    [8, 48, 14, 24, 18])

OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print(f"saved: {OUT} ({OUT.stat().st_size} bytes)")

# Verify by reading back.
rb = openpyxl.load_workbook(OUT, data_only=False)
print("sheets:", rb.sheetnames)
for name in rb.sheetnames:
    ws = rb[name]
    print(f"{name}: dim={ws.dimensions} filter={ws.auto_filter.ref} freeze={ws.freeze_panes}")
print("VERIFY-OK")
