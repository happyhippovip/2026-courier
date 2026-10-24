# Google Antigravity Windows — Deep-Work Auto-Continue V1

**Public engineering prompt · 23 October 2026 · Courier Symphony · Pre-release**

This page documents a **bounded, aggressively productive, owner-safe verification mission**, not a commitment to nonstop compute. It does not itself start an agent, scheduler or cloud service.

## Verified starting snapshot

At the time of writing, PRs [#835](https://github.com/happyhippovip/2026-courier/pull/835), [#836](https://github.com/happyhippovip/2026-courier/pull/836), [#837](https://github.com/happyhippovip/2026-courier/pull/837) and [#838](https://github.com/happyhippovip/2026-courier/pull/838) were **open**, and both Courier v1 CI and GitHub Customer-Reality checks were **successful on their specific current heads**. Green PR checks do not authorize merges or certify real-provider production execution.

The Windows Antigravity agent reported `RECONCILED (NO-OP / QUIESCENT)`, a previously queued Glass message and **zero active scheduler tasks**. It is currently waiting at the HG-02 merge permission boundary. PR #838 includes the explicit **one queued continuation per fingerprint** policy; never refill a queue with duplicate prompts.

## Copy-paste prompt for EXISTING Google Antigravity Windows conversation

```text
👑🥊👊😎🪟🧪⚗️🚀
COURIER SYMPHONY — GOOGLE WINDOWS DEEP-WORK CONTINUE V1
MODE: HIGH-INTENSITY NEW-EVIDENCE MISSION / LOW INTERRUPTION / 0 € EXTRA

DU BIST GOOGLE ANTIGRAVITY WINDOWS, NICHT L1 UND KEIN FREMDER PRODUKTWRITER.
DIES IST EIN NEUER AUTORISIERTER READ-ONLY/ISOLIERTER TESTAUFTRAG,
KEINE FREIGABE ZU MERGES, PAUSCHALEN CODEÄNDERUNGEN ODER SPEND.

LAUFZEIT: 23.10.2026 BIS SPÄTESTENS 24.10.2026 20:00 Europe/Berlin.
Bestehende Sitzung nutzen. Keine Zeitverlängerung durch Neustart.

LETZTER BERICHT:
- RECONCILED (NO-OP / QUIESCENT)
- alle bekannten PR-Checks #835/#836/#837/#838 waren grün
- Scheduler 0 aktive Tasks
- HG-02-Merge-Freigabe steht aus
- PR #838 fordert EINMALIGE Queue-Nachricht pro Fingerprint
Dieser Bericht ist ein Snapshot, keine aktuelle Freigabe.

AUFTRAG:
Nutze die vorhandene IDE-Sitzung intensiv für bisher noch nicht
unabhängig belegte Windows-, Cross-Home-, CostGate- und Replay-Grenzfälle.
Erzeuge keine leere Aktivität. Nimm nicht dieselbe CI mehrfach auseinander.

PHASE A — KANONISCHER IST-STAND
GW-401: Letzten Checkpoint, Workkeys, aktiven Prozessstatus lesen.
GW-402: integration/v1 und #835–#838 auf aktuelle SHAs prüfen.
GW-403: Vorhandene Tests/Belege nach (SHA, Invariante, Testfall) deduplizieren.
GW-404: Eigene Scope- und Lease-Autorisierung prüfen; ohne Lease READ-ONLY.
GW-405: Windows- vs. Linux-spezifische Tests unterscheiden.
GW-406: Eine Prioritätenmatrix der bisher UNBELEGTEN Fälle erstellen.

PHASE B — WINDOWS / LIFECYCLE NEGATIVTESTS
GW-407: H10-Claim: falschen Owner, veraltete Nonce, Stale-Writer simulieren.
GW-408: Timeout nach CLAIMED vor STARTED ohne erneute Ausführung.
GW-409: Crash nach STARTED ohne Blind-Replay.
GW-410: RESULT_READY nur erneut zustellen, nicht Provider neu ausführen.
GW-411: RELEASE_PENDING bei Restart ohne Double-FINAL.
GW-412: Windows Lock fehlt / LeaseStore beschädigt / File-IO denied: fail closed.
GW-413: Cross-Home Lease expired, aber alter Prozess lebt weiter:
        keine Doppelarbeit und kein automatischer unbewiesener Reclaim.
GW-414: Crash/Recovery und Dead-Letter mit identischem Workkey testen.

PHASE C — BOUNDARY PROOFS
GW-415: #836 Provider-DONE ohne akzeptierten Journal-Proof negativ prüfen.
GW-416: #837 A→B→C bis echtes synthetisches RESULT_ACCEPTED prüfen.
GW-417: Stale Dispatch, falsche Task-ID, Attempt und Receipt-Bytes ablehnen.
GW-418: local_shell mit unbekannten/gefälschten 0-EUR-Kosten ablehnen;
        niemals einen echten kostenpflichtigen CLI starten.
GW-419: Bridge-Paket gegen Controller-Admission-CostGate vergleichen.
GW-420: PR #838: nur eine Fortsetzung je Fingerprint; keine Doppel-Queue.
GW-421: Event-Trigger bei unveränderten SHAs/CI erzeugt KEINEN neuen Job.
GW-422: Relevantes neues CI-FAIL löst GENAU EINE gezielte Prüfung aus.

PHASE D — BELASTBARE ÜBERGABE
GW-423: Neue Defekte auf Root Cause, Scope und zuständigen Owner abbilden.
GW-424: Für neue Befunde minimal reproduzierbare Testfixtures erstellen.
GW-425: Vorher-rot/nachher-grün NUR behaupten, wenn wirklich gelaufen.
GW-426: Alle nachgewiesenen Tests mit SHA, Exitcode und Testnamen archivieren.
GW-427: L1-Handoff: HG-02-Eingangsgates, Risiken und offene Beweise.
GW-428: Abschlusscheckpoint, next-ready-only Liste, kein falsches GO.

FORTSETZUNGSLOGIK:
- Jede wirklich neue sichere Aufgabe → ausführen, dokumentieren, NEXT.
- Schon unabhängig nachgewiesen → SKIP mit Verweis, keine Wiederholung.
- Kein Writer-Recht → isolierte Tests / Patchvorschlag / Handoff.
- Wait-for-merge HG-02 → keine Freigabe erfinden.
- Wenn eine PR ohne L1-Ereignis unverändert ist, suche zuerst neue
  Testfälle innerhalb deines eigenen bestätigten Scopes.
- Sobald alle unterscheidbaren Tests erledigt sind, korrekt QUIESCENT_SAFE;
  Ausdauer durch vorhandene neue Arbeit, nicht künstliche Pseudo-Workkeys.

RESSOURCEN:
Maximal zwei leichte READ-ONLY-Subagenten mit verschiedenem Prüfziel,
soweit lokal verfügbar und ohne neue Cloud-/PAYG-Kosten.
Nur EIN schwerer Testjob je Windows-Host.
Keine anderen Agenten/Prozesse beenden.
Bremse bei Memory-/I/O-Druck.

WAKE-UP:
Zuerst vorhandene Goal-/Loop-/Schedule-/Glass-Sender prüfen.
PR #838 verlangt genau EINE Fortsetzungsnachricht je Fingerprint.
Wenn aktuell 0 Scheduler aktiv sind: KEINEN zufälligen Cron erfinden.
Nutze vorhandene unterstützte native Planungs-/Goal-Funktionen
nur mit dokumentiertem Kostenstatus, klarer Endzeit, Dedupe und
expliziter Berechtigung für die konkrete Automation.
Bei nicht belegter Funktion/Kosten: keinen neuen Sender starten;
stattdessen direkt die obigen Arbeitsphasen in der aktuellen Sitzung.

KEINE ZWISCHENNACHRICHTEN. Checkpoint nach 5 neuen sinnvollen Workkeys.
Nur bei dringender Sicherheitsentscheidung, unbekannten Kosten oder
zwingender Berechtigung fragen. Keine repetitive GO-Frage.

HART:
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO

KEIN UNAUTORISIERTER MERGE. KEINE PRODUKTIONSFREIGABE.
KEINE ZUSÄTZLICHE CLOUD-ABRECHNUNG.
KEINE ÖFFENTLICHEN PRIVATEN DATEN/SECRETS.

JETZT BEGINNEN:
Ermittle die ersten 3 tatsächlich UNBELEGTEN Windows-P0/P1-Proofs,
bearbeite sie nacheinander und setze mit der deduplizierten Queue fort.
Nur ein Abschlussbericht, wenn alles sicher abgearbeitet ist.

👑🥊👊😎🪟🧪⚗️🚀
```

## Interpretation

An **idle** agent with zero scheduled jobs will not resume simply because a long goal is written. The prompt is a new interactive assignment in the existing session. Persistent future wake-ups require an actually supported, authorized scheduling mechanism, a deduplication gate and an absolute stop condition. More identical queued messages risk duplication and do not provide more compute.

## Limits

- Checks run on specific commits; do not confuse CI pass with production release.
- HG-02 must remain a deliberate authorized decision.
- Any Windows installer/service/scheduler change is a separate privileged operation.
- Do not place account details, device paths, project-memory material, credentials or personal files in this public document.
