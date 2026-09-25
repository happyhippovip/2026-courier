#!/usr/bin/env python3
"""
Offline-Testharness fuer die Terminal-Wall-Control.command Klassifikations-/
Adoptions-/Slot-Logik. Simuliert NUR die reine Datenlogik in Python (kein
Terminal.app, keine echten Prozesse, keine Aenderung am Controller selbst).

Ziel: beweisen, dass die Logik (TTY-Gruppierung, --yolo-Erkennung,
Slot-Vergabe, Over-Target, Idempotenz) fuer die im Auftrag genannten
Szenarien korrekt arbeitet, bevor der naechste echte Live-Klick passiert.
"""

import re

MUSE_TARGET = 64
AG_TARGET = 6
MUSE_PREFIX = "TW-MUSE-"
AG_PREFIX = "TW-AG-"


# ---------------------------------------------------------------------------
# 1) Nachbildung der museYoloTTYs-Logik (TTY-Gruppierung, wie im aktuellen
#    Terminal-Wall-Control.command, Zeile 414) inkl. "-ww" (keine Kuerzung).
# ---------------------------------------------------------------------------
def build_muse_yolo_ttys(ps_lines):
    """ps_lines: Liste von (tty, full_command_line) Tupeln, wie sie
    `ps -ww -eo tty=,args=` liefern wuerde (ungekuerzt)."""
    yolo_ttys = set()
    mb_ttys = set()
    for tty, cmd in ps_lines:
        low = cmd.lower()
        if "muse" in low and "--yolo" in cmd:
            yolo_ttys.add(tty)
        if "muse-bin" in cmd:
            mb_ttys.add(tty)
    return {t for t in mb_ttys if t in yolo_ttys}


def build_muse_any_ttys(ps_lines):
    return {tty for tty, cmd in ps_lines if "muse-bin" in cmd}


def build_ag_ttys(ps_lines):
    out = set()
    for tty, cmd in ps_lines:
        low = cmd.lower()
        if "agy" in low or "antigravity" in low or "gemini" in low:
            out.add(tty)
    return out


# ---------------------------------------------------------------------------
# 2) Nachbildung von slotFromTitle / PASS1 Klassifikation / PASS2 Adoption
# ---------------------------------------------------------------------------
def slot_from_title(title, prefix):
    if not title.startswith(prefix):
        return 0
    suffix = title[len(prefix):]
    try:
        return int(suffix)
    except ValueError:
        return 0


def next_free_slot(used_slots, max_slots):
    for n in range(1, max_slots + 1):
        if n not in used_slots:
            return n
    return 0


def classify_and_adopt(windows, muse_any_ttys, muse_yolo_ttys, ag_ttys,
                        muse_target=MUSE_TARGET, ag_target=AG_TARGET):
    """windows: Liste von dicts {id, tty, title}
    Simuliert PASS1 (Klassifikation, bestehende Tags respektieren) und
    PASS2 (Adoption bis zum Ziel), analog zur AppleScript-Logik."""
    muse_records = {}   # slot -> window id
    ag_records = {}
    used_muse_slots = set()
    used_ag_slots = set()
    muse_candidates = []
    ag_candidates = []
    conflicts = 0
    non_yolo_skipped = 0
    unrelated = 0
    unknown = 0

    for w in windows:
        wid, tty, title = w["id"], w["tty"], w["title"]
        if tty is None:
            unknown += 1
            continue
        is_muse = tty in muse_any_ttys
        is_ag = tty in ag_ttys
        ms = slot_from_title(title, MUSE_PREFIX)
        aslot = slot_from_title(title, AG_PREFIX)

        if ms > 0 and ms <= muse_target:
            if is_ag and not is_muse:
                conflicts += 1
            elif is_muse and tty not in muse_yolo_ttys:
                non_yolo_skipped += 1
            elif ms in used_muse_slots:
                muse_candidates.append(wid)
            else:
                used_muse_slots.add(ms)
                muse_records[ms] = wid
        elif aslot > 0 and aslot <= ag_target:
            if is_muse and not is_ag:
                conflicts += 1
            elif aslot in used_ag_slots:
                if is_ag:
                    ag_candidates.append(wid)
            else:
                used_ag_slots.add(aslot)
                ag_records[aslot] = wid
        elif is_muse:
            if tty in muse_yolo_ttys:
                muse_candidates.append(wid)
            else:
                non_yolo_skipped += 1
        elif is_ag:
            ag_candidates.append(wid)
        else:
            unrelated += 1

    adopted_muse = 0
    for wid in muse_candidates:
        if len(muse_records) >= muse_target:
            break
        slot = next_free_slot(used_muse_slots, muse_target)
        if slot == 0:
            break
        used_muse_slots.add(slot)
        muse_records[slot] = wid
        adopted_muse += 1

    adopted_ag = 0
    for wid in ag_candidates:
        if len(ag_records) >= ag_target:
            break
        slot = next_free_slot(used_ag_slots, ag_target)
        if slot == 0:
            break
        used_ag_slots.add(slot)
        ag_records[slot] = wid
        adopted_ag += 1

    return {
        "muse_records": muse_records,
        "ag_records": ag_records,
        "adopted_muse": adopted_muse,
        "adopted_ag": adopted_ag,
        "conflicts": conflicts,
        "non_yolo_skipped": non_yolo_skipped,
        "unrelated": unrelated,
        "unknown": unknown,
    }


# ---------------------------------------------------------------------------
# Testfaelle laut Auftrag
# ---------------------------------------------------------------------------
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# --- Szenario 1: Muse TTY mit --yolo auf derselben Zeile ---
ps1 = [("ttys001", "muse-bin-1.3.0-R3401.1 --yolo --provider meta")]
yolo1 = build_muse_yolo_ttys(ps1)
check("1) --yolo auf derselben Zeile wird erkannt", yolo1 == {"ttys001"}, yolo1)

# --- Szenario 2: --yolo nur auf Parent-Prozess derselben TTY (Kind ohne Flag) ---
ps2 = [
    ("ttys002", "muse --yolo --provider meta"),          # Parent-Wrapper
    ("ttys002", "muse-bin-1.3.0-R3401.1 --provider meta"),  # Kind ohne --yolo im eigenen argv
]
yolo2 = build_muse_yolo_ttys(ps2)
check("2) --yolo nur beim Parent, TTY-Gruppierung findet es trotzdem", yolo2 == {"ttys002"}, yolo2)

# --- Szenario 3: lange ps-Zeile (simuliert die -ww-Notwendigkeit) ---
long_path = "/Users/user/.nvm/versions/node/v20/lib/node_modules/@muse/cli/bin/" + ("x" * 200)
ps3 = [("ttys003", f"{long_path}/muse-bin-1.3.0-R3401.1 --yolo")]
yolo3 = build_muse_yolo_ttys(ps3)
check("3) --yolo wird auch bei sehr langer Pfad-Praefix-Zeile erkannt (kein Kuerzungs-Analogon in Python-Test)",
      yolo3 == {"ttys003"}, yolo3)
# Hinweis: Python-strings kuerzen nicht wie ps ohne -ww; dieser Test kann die
# reale macOS-ps-Kuerzung nicht nachstellen, bestaetigt aber, dass die
# AWK-Logik selbst (ohne Kuerzung) korrekt ist. Die -ww-Notwendigkeit ist
# separat durch echte Logs belegt (siehe vorherige Handoffs), nicht hier.

# --- Szenario 4: 87 Muse > Ziel 64 (Over-Target, keine Reduktion) ---
windows4 = [{"id": i, "tty": f"ttys{i:03d}", "title": f"Downloads — task {i} — muse-bin-1.3.0"} for i in range(1, 88)]
muse_any4 = {f"ttys{i:03d}" for i in range(1, 88)}
muse_yolo4 = {f"ttys{i:03d}" for i in range(1, 88)}  # alle bestaetigt yolo
res4 = classify_and_adopt(windows4, muse_any4, muse_yolo4, set())
check("4) 87 Muse > Ziel 64: genau 64 werden adoptiert, Rest bleibt unangetastet (keine Reduktion, kein Fehler)",
      len(res4["muse_records"]) == 64 and res4["adopted_muse"] == 64,
      f"adoptiert={res4['adopted_muse']}, records={len(res4['muse_records'])}, restliche 23 einfach nicht in muse_records")

# --- Szenario 5: 7 AG > Ziel 6 (Over-Target AG) ---
windows5 = [{"id": i, "tty": f"agtty{i}", "title": "Downloads — agy --dangerously-skip-permissions"} for i in range(1, 8)]
ag_ttys5 = {f"agtty{i}" for i in range(1, 8)}
res5 = classify_and_adopt(windows5, set(), set(), ag_ttys5)
check("5) 7 AG > Ziel 6: genau 6 adoptiert, 7. bleibt Kandidat/unadoptiert, kein Fehler",
      len(res5["ag_records"]) == 6 and res5["adopted_ag"] == 6,
      f"adoptiert={res5['adopted_ag']}, records={len(res5['ag_records'])}")

# --- Szenario 6: vorhandene TW-AG-01..06 (Idempotenz, Slot-Erhalt) ---
# WICHTIG: "custom title of tb" ist in der echten AppleScript-Logik NUR der
# reine Tag (z.B. "TW-AG-01"), NICHT die von Terminal.app zusammengesetzte
# Anzeige "Downloads — TW-AG-01 — agy ...". Die Anzeige-Komposition ist reine
# Terminal-UI-Darstellung; slotFromTitle liest die custom-title-Property.
windows6 = [{"id": i, "tty": f"agtty{i}", "title": f"TW-AG-0{i}"} for i in range(1, 7)]
ag_ttys6 = {f"agtty{i}" for i in range(1, 7)}
res6 = classify_and_adopt(windows6, set(), set(), ag_ttys6)
expected_slots6 = {i: i for i in range(1, 7)}
actual_slots6 = {slot: wid for slot, wid in res6["ag_records"].items()}
check("6) TW-AG-01..06 bereits getaggt: jedes behaelt exakt seine eigene Slot-Nummer, 0 Umbenennungen",
      actual_slots6 == expected_slots6 and res6["adopted_ag"] == 0,
      f"records={actual_slots6}, adopted={res6['adopted_ag']} (muss 0 sein, da alle schon Slots hatten)")

# --- Szenario 7: UNKNOWN (Fenster ohne lesbare TTY, z.B. Lesefehler) ---
windows7 = [{"id": 1, "tty": None, "title": "?"}]
res7 = classify_and_adopt(windows7, set(), set(), set())
check("7) UNKNOWN-Fenster (tty=None) wird gezaehlt, aber NIE adoptiert/angefasst",
      res7["unknown"] == 1 and len(res7["muse_records"]) == 0 and len(res7["ag_records"]) == 0,
      res7)

# --- Szenario 8: doppelte/stale TTY (zwei Fenster behaupten denselben Muse-Slot) ---
windows8 = [
    {"id": 1, "tty": "ttys010", "title": "TW-MUSE-05"},
    {"id": 2, "tty": "ttys011", "title": "TW-MUSE-05"},  # Duplikat-Tag (custom title Property, nicht Anzeige)
]
muse_any8 = {"ttys010", "ttys011"}
muse_yolo8 = {"ttys010", "ttys011"}
res8 = classify_and_adopt(windows8, muse_any8, muse_yolo8, set())
check("8) Zwei Fenster mit identischem TW-MUSE-05 Tag: erstes behaelt Slot 5, zweites wird sicher auf neuen freien Slot umgehaengt (kein Crash, keine Kollision)",
      res8["muse_records"].get(5) == 1 and 2 in res8["muse_records"].values() and len(res8["muse_records"]) == 2,
      res8)

# --- Szenario 9: idempotenter Zweitlauf (gleicher Zustand zweimal klassifizieren) ---
windows9 = [{"id": i, "tty": f"ttys{i:03d}", "title": f"TW-MUSE-{i:02d}"} for i in range(1, 6)]
muse_any9 = {f"ttys{i:03d}" for i in range(1, 6)}
muse_yolo9 = {f"ttys{i:03d}" for i in range(1, 6)}
res9a = classify_and_adopt(windows9, muse_any9, muse_yolo9, set())
res9b = classify_and_adopt(windows9, muse_any9, muse_yolo9, set())
check("9) Zweiter Lauf auf identischem Zustand liefert identisches Ergebnis (0 neue Adoptionen, gleiche Slots)",
      res9a["muse_records"] == res9b["muse_records"] and res9b["adopted_muse"] == 0,
      f"lauf1={res9a['muse_records']}, lauf2={res9b['muse_records']}")


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------
print("=" * 70)
print("OFFLINE WALL LOGIC TEST HARNESS - ERGEBNIS")
print("=" * 70)
all_pass = True
for name, ok, detail in results:
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"[{status}] {name}")
    if detail:
        print(f"        Detail: {detail}")
print("=" * 70)
print(f"GESAMT: {'ALLE TESTS BESTANDEN' if all_pass else 'MINDESTENS EIN TEST FEHLGESCHLAGEN'} ({sum(1 for _,ok,_ in results if ok)}/{len(results)})")
