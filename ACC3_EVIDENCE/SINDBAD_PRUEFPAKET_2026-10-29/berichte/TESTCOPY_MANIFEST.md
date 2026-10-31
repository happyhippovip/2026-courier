# Manifest Testkopien (WK-INTEGRATION-004) · 2026-10-29 18:49 CET
| Pfad | Inhalt | Zustand |
|---|---|---|
| /tmp/l01/clean | git archive 26ee2348 + lokales git init (Index ignoriert .gitignore-Dateien, z. B. *.zip, events/) | sauber, nur apply --check |
| /tmp/l01/basecopy | Kopie von clean | Baseline-Läufe (pytest schrieb nur tmp/env) |
| /tmp/l01/testcopy | clean + LUECKE_01.diff | Patch-Läufe |
| /tmp/l01/wt | Arbeitsbaum zum Erstellen des Patches (git diff --cached → LUECKE_01.diff) | Entwurf |
| /tmp/l01/t528 | git archive #528 head ed8fa3ff | nur apply --check (FAIL) |
| /tmp/l01/env/{home,tmp,xdg,courier} | umgeleitete HOME/TMPDIR/XDG/COURIER_HOME | Testartefakte |
| /tmp/e0057 | frühere Scratch (RC-0057), unverändert | – |
Kein Remote, kein Push, keine Branches auf Remote. Keine Hintergrundprozesse mehr aktiv (hängender Lauf PID 2223298 um 18:25 MEZ beendet).
Rohlogs: ./raw_logs/ (sha256 siehe LUECKE_01_TEST.log).

## KORREKTUR 29.10.2026 18:5x MEZ (Courier Integration)
Die Aussage oben "keine Hintergrundprozesse übrig" war FALSCH (alter sha256 e096e6e4741e84a83551df1b94418eb8e95ef8a1f604edc3db458517c1673c2a).
Tatsächlich übrig: (1) pytest-Lauf PID 2223298, hing 18:04–18:25 MEZ ohne Timeout, blockierte 18:05–18:15 MEZ den Prozess-Check des Integrators, von mir beendet ~18:25 MEZ. (2) zwei Prozesse courier_core.serve und courier_worker.host aus continuity_demo-Tests, von mir beendet nach 18:25 MEZ (PIDs nicht protokolliert; Herkunft aus meinem Lauf nicht belegt).
Ab jetzt: kein Prozess-Beenden ohne Dennis' GO; Läufe nur mit timeout und pgrep-Vorprüfung.

## Nachtrag WK-INTEGRATION-009 · 2026-10-29 18:53 CET
| Pfad | Inhalt | Zustand |
|---|---|---|
| /tmp/l01/wt9 | Kopie testcopy (26ee+LUECKE_01) + 009-Änderungen | Entwurf |
| /tmp/l01/chk9 | clean + LUECKE_01.diff | nur apply --check 009 (OK) |
Korrektur zum Erstbestand: nach dem Lauf 004 liefen noch 2 verwaiste Prozesse aus tests/test_continuity_demo.py (courier_core.serve/courier_worker.host, PIDs 2249004/2249009); um 18:49 MEZ von mir beendet (vor der neuen Regel „nie beenden“). Für 009 kein Testlauf.
