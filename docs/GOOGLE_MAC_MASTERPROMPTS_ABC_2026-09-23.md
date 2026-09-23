# GOOGLE MAC MASTERPROMPTS A / B / C
Stand: 23.09.2026
Ziel: 7 Google/Antigravity-CLIs am Mac maximal parallel nutzen, ohne Doppelarbeit, Prüfungsorgien oder unkontrollierte Merges.

> Kurzregel: Alle 7 CLIs bekommen nacheinander denselben Block A, dann B, dann C.
> Jeder Agent claimt automatisch genau eine Lane. Kein Agent prüft dieselbe Sache ein zweites Mal, nur um "sicher zu sein".

## Gemeinsame Regeln für A / B / C

- Mac-only. Windows nicht anfassen.
- Lies zuerst: `AGENTS.md`, `CLAUDE.md`, `docs/MASTERPLAN_COURIER.md`, `docs/STATUS.md`, `docs/MUSE_HANDOFF.md`.
- Kein Beleg = kein PASS, aber **minimal ausreichender Beleg**. Keine Prüfungsorgien.
- Bereits belegte Fakten nicht erneut prüfen.
- Keine neue Architektur, wenn ein kleiner kausaler Fix reicht.
- Keine echten kostenpflichtigen Provider-Aufrufe nur zum Testen.
- Keine Secrets, Tokens, .env, ~/.ssh, ~/.aws lesen oder ausgeben.
- Kein Push, Merge, Tag, Release, Rebase, force, reset --hard.
- Keine echten Veröffentlichungen / Uploads / Accountänderungen.
- Code nur in eigenem Worktree ändern.
- Tests dürfen nur selbst gestartete Prozesse beenden.
- Nie komplette `pytest tests/`-Suite während Debugging; nur gezielte Tests.
- Wenn ein Lane-Problem nicht belegt ist: "NICHT BELEGT" melden und stoppen, nichts erfinden.
- Dennis entscheidet Merge/Push/Release/Geld/Accounts.

## Arbeitsmechanik

Gemeinsamer Arbeitsbereich:
`~/Downloads/courier_work/google/`

Jeder Agent:
1. erzeugt einmal eine Kennung `Gxxxx`;
2. claimt atomar genau eine noch freie Lane über `mkdir ~/Downloads/courier_work/google/claims/<LANE>`;
3. wenn claim existiert: nächste Lane probieren;
4. arbeitet nur diese Lane;
5. nutzt einen eigenen Worktree unter `~/Downloads/courier_work/google/lanes/<LANE>-<KENNUNG>`;
6. schreibt einen kurzen Report nach `~/Downloads/courier_work/google/reports/<LANE>-<KENNUNG>.md`;
7. beendet mit `BLOCK <A|B|C> / LANE <LANE> FERTIG`.

Reportformat:
- LANE
- BRANCH
- FULL_SHA
- STATUS: BELEGT | BEHAUPTET | VERMUTET | UNKNOWN
- FINDING
- CHANGED_FILES
- TARGETED_TEST
- EVIDENCE
- REMAINING_BLOCKER
- SMALLEST_NEXT_ACTION
- MERGE_DECISION: DENNIS

---

# MASTERPROMPT A — CANNON V1 CORE: FINDEN + KLEINSTER FIX

Du bist einer von 7 parallelen Google-Workern auf dem Mac.

Ziel dieses Blocks:
Die offenen Cannon-V1-Kernprobleme parallel schließen, ohne Doppelarbeit.

Claim genau EINE Lane:

- A1-BASELINE
  Kläre die offizielle `pre-yolo-patch`-Basis aus Git-Historie/Tags/Tests/Doku.
  Bekannte Referenzen: `49150d3f` und `e98ce2cc`.
  Nur ändern, wenn ein eindeutig falscher Referenzwert in Test/Doku die Ursache eines belegten Fehlers ist.

- A2-LIVE-TEXT
  Reproduziere den offenen Live-Text-Fehler mit dem kleinsten vorhandenen Test/Befehl.
  Belege exakte Fehlermeldung und Root Cause.
  Wenn kausal und klein: minimaler Fix + gezielter Test.

- A3-NOTAUS
  Belege Reaktionszeit der STOP-/Pause-Logik nur mit Fake-/lokalen Aufgaben.
  Ziel < 15 s.
  Wenn verletzt: kleinster kausaler Fix + Zeitmessungs-Test.

- A4-RESULT-BINDING
  Prüfe nur die Invarianten:
  `result_id == voller Commit-Hash`,
  jede Aufgabe genau einmal DONE,
  kein ARTIFACT_MISSING/MISMATCH als falsches PASS.
  Belegter Fehler -> kleinster Fix + gezielter Test.

- A5-RECOVERY
  Prüfe Recovery/Heartbeat/Wiederaufnahme nach simuliertem Abbruch einer selbst gestarteten Fake-Aufgabe.
  Ziel: keine doppelte und keine verlorene Aufgabe.
  Kein fremder Prozess darf beendet werden.

- A6-DOUBLE-START
  Prüfe Supervisor-/State-Sperre gegen zwei Cannons auf demselben Zustand.
  Nur Fake/local.
  Belegter Fehler -> kleinster Fix.

- A7-LIMITS-SAFETY
  Prüfe nur kritische Start-/Limit-Schutzlogik:
  Zeit/Kontingent/Serienfehler/ungültige Env-Werte,
  Sandbox-Assertion,
  keine echten Providerkosten standardmäßig.
  Kein breites Security-Redesign.

Regel:
Erst gezielt reproduzieren, dann nur bei BELEGTEM Problem ändern.
Keine zweite Meinung, kein Fremdreport-Review.

Am Ende Report schreiben und:
`BLOCK A / LANE <LANE> FERTIG`

---

# MASTERPROMPT B — CANNON V1 ABNAHME + FREEZE-VORBEREITUNG

Dieser Block kommt erst nach A.

Lies die vorhandenen A-Reports. Wiederhole keine bereits ausreichenden Belege.
Claim genau EINE Lane:

- B1-FIVE-RUN
  Finde und nutze den bestehenden 5er-Lauf.
  Keine neue Testinfrastruktur.
  Führe ihn aus, wenn die A-Blocker behoben/verfügbar sind.
  Liefere roh: PASS/FAIL, Lauf-IDs, Commit-Bindung, Duplikate, verlorene Ergebnisse.

- B2-ENDLOS-RUN
  Werte den vorhandenen Endlos-Lauf aus.
  Nicht neu starten, wenn Artefakte reichen.
  Gesucht: Aufgabenanzahl, Hänger, menschliche Eingriffe, DUPLICATE_EXECUTIONS, LOST_RESULTS, result_id/Commit-Bindung.

- B3-MAC-ACCEPTANCE
  Prüfe nur die Cannon-V1-Abnahmekriterien auf dem Mac:
  result_id/Commit, 0 Duplikate, 0 verlorene Ergebnisse, Notaus <15 s.
  Nur die minimal nötigen Befehle.

- B4-CONFLICT-MAP
  Lies A-Branches/Reports und ermittle nur Dateiüberschneidungen und offensichtliche Merge-Konflikte.
  Nichts mergen.
  Empfohlene kleinste Merge-Reihenfolge liefern.

- B5-FREEZE-PACKAGE
  Finde vorhandenen Bundle-/Backup-Mechanismus und bereite die exakten Freeze-Schritte für `courier-cannon-v1` vor.
  NICHT taggen, NICHT pushen.

- B6-RUNTIME-GROWTH
  Ein begrenzter Fake-Langlauf zur Messung von Logs/State/Dateien nur wenn nicht bereits belegt.
  Ziel: kein offensichtliches unbegrenztes Wachstum, das Cannon V1 praktisch blockiert.
  Kein Performance-Tuning ohne belegten Blocker.

- B7-FINAL-MAC-STATUS
  Konsolidiere ausschließlich vorhandene A/B-Belege in einen kurzen Mac-Status:
  READY_TO_FREEZE: YES/NO
  BLOCKERS: ...
  REQUIRED_NEXT_ACTION: genau eine Sache.
  Keine neuen Tests außer wenn ein einzelner fehlender Beleg zwingend erforderlich ist.

Keine Prüfungsorgie. Ein vorhandener starker Beleg zählt.

Am Ende:
`BLOCK B / LANE <LANE> FERTIG`

---

# MASTERPROMPT C — PRODUKT-/KANAL-PIPELINE BESCHLEUNIGEN

Dieser Block kommt nach B.

Wenn B7 `READY_TO_FREEZE = NO` meldet:
- KEINE neuen Produktfeatures bauen.
- Nur read-only Pipeline-Bestand/Gaps dokumentieren.
- Den einen Cannon-Blocker nicht parallel durch neue Architektur umgehen.

Wenn Cannon V1 freeze-ready ist:
Zielbild:

`KANAL WÄHLEN -> STORY/ZIEL EINGEBEN -> TEMPLATE -> RUN -> REVIEW -> READY_TO_PUBLISH -> HUMAN APPROVAL -> PUBLISH`

Claim genau EINE Lane:

- C1-PIPELINE-RUNNER
  Inventarisiere und vervollständige minimal den vorhandenen `scripts/run_content_production_pipeline.py`-Pfad.
  Bestehendes wiederverwenden, nichts neu erfinden.

- C2-CHANNEL-TEMPLATES
  Prüfe `config/social_channels.json`, `config/content_workflows.json` und vorhandene Templates.
  Ziel: Kanal + Workflow + Template eindeutig auswählbar.
  Keine Accountänderung.

- C3-STUDIO-OPERATOR
  Prüfe vorhandene `studio/`-Oberfläche und den kleinsten Anschluss an:
  Kanal wählen + Ziel/Story eingeben + Workflow starten.
  Keine große UI-Neuentwicklung.

- C4-YOUTUBE-HEALTH
  Prüfe Repo-seitig, was für YouTube wirklich implementiert/belegt ist.
  Live-Auth nur mit nebenwirkungsfreiem Health-Check, falls bereits sicher verfügbar.
  Niemals Secrets anzeigen, nichts veröffentlichen.
  Wenn Auth nicht sicher belegbar: UNKNOWN, nicht neu authentifizieren.

- C5-TIKTOK-HEALTH
  Wie C4 für TikTok.
  Kein echter Upload/Publish.

- C6-RENDER-PACKAGE
  Prüfe vorhandene Render-/Asset-/Metadata-/READY_TO_PUBLISH-Kette.
  Ziel: lokaler End-to-End-Lauf bis READY_TO_PUBLISH mit vorhandenen Komponenten.
  Keine Veröffentlichung.

- C7-CUSTOMER-PATH
  Schreibe/verbessere nur die minimale Bedien-/Schnellstart-Doku:
  Kanal wählen, Story eingeben, Template wählen, Start, Ergebnis, Human-Gate.
  Nichts doppelt dokumentieren.

Zusatz:
Nicht künstlich Credits verbrennen.
Dokumentiere lieber:
- erledigte echte Aufgaben
- gesparte menschliche Relays
- Wartezeit durch Quota
- backlog, der bei mehr legitimer Kapazität abgearbeitet werden könnte

Am Ende:
`BLOCK C / LANE <LANE> FERTIG`

---

## Reihenfolge für Dennis

1. Alle 7 Mac-Google-CLIs: MASTERPROMPT A einfügen.
2. Wenn die 7 A-Lanes fertig/ausgeschöpft sind: MASTERPROMPT B in dieselben 7 Sitzungen.
3. Danach MASTERPROMPT C.
4. Ergebnisse nicht einzeln zerdenken: Reports gesammelt an Chief/ChatGPT geben.
5. Windows bleibt separat und später.
