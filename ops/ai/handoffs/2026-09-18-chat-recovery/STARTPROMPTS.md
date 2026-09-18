# Startprompts für den Chatwechsel — noch nicht ausgeführte Aufträge

Diese Prompts dienen der nächsten ausdrücklich gestarteten Sitzung. Es läuft dadurch kein neuer Agent. Der Recovery-Zweig enthält Dokumentation und übernimmt keine Produktionshoheit.

## A. Direkt in den neuen ChatGPT-Chat kopieren

```text
Übernimm Courier Symphony Muse nach einer längeren Chat-Unterbrechung.
Antworte auf Deutsch. Der Nutzer braucht verlässliche Kontinuität, sparsamen
Codex-Einsatz auf dem MacBook, geringe Rechnerbelastung und gespeicherte
Arbeitsergebnisse, die einen Chat- oder Rechnerneustart überstehen.

Repository: happyhippovip/2026-courier
Integration: release-candidate-integration
Recovery-Zweig: ops/chat-handover-20260918-recovery
Lies zuerst:
ops/ai/handoffs/2026-09-18-chat-recovery/CHAT_UEBERGABE.md
und diese STARTPROMPTS.md aus dem Recovery-Zweig.
Alternativ verwende die vom Nutzer hochgeladene lokale CHAT_UEBERGABE.md.

Die Übergabe hat den Remote-Snapshot
56fa90573dc2ad7a45ac407025ec1113a139b88b geprüft.
Das ist ein historischer Beobachtungspunkt, kein jetzt automatisch gültiger HEAD.
Lies danach die aktuellen ops/ai/START_HERE.md, OWNERSHIP_MAP.yaml,
NEXT_WORK.yaml und nur das relevante Paket/Checkpoint-Delta der Integration.
Nicht den gesamten alten Chat oder das ganze Repository wieder durchforsten.

Trenne immer: committed Code, lokale uncommittete Arbeit, Agentenberichte,
Spezifikation, tatsächlich laufende Prozesse und physische Abnahme.
Kein PASS aus Dateinamen, Testanzahlen, YAML-Labels oder alten Abschlussmeldungen.
KNOWN_GOOD_CHECKPOINT.md behauptet Neustartsicherheit, nennt aber lokale Fixes;
Muse-Checkpoint iteration 7 meldet fremde aktive uncommittete Restarbeit.
Diese Arbeitskopien sind durch den Remote-Snapshot nicht automatisch gesichert.

Wichtigste Themen: DLQ-01 echte unabhängige Attester-Autorität;
DLQ-02 serverseitige Uhr/Epoch/Frische statt freier Zeitstempel;
DLQ-03 typisierte Duplicate-/Revisionsfehler versus bestehende String-Prüfungen;
DLQ-04/08 tatsächlicher bounded drain, Acht-Sekunden-Abandon und os._exit;
DLQ-05 aktueller Quota-Vertrag nach beabsichtigter Gate-Entfernung 29191a53;
DLQ-06 echte Fehlerbehandlung/isolierte erhaltene Tests;
DLQ-07 INIT-Schutz ohne Überblockierung.
Die ausführliche Übergabe enthält die Widersprüche und Belegpfade.

GOOGLE ist laut gelesener Ownership Produktionswriter für Ledger/Guard/Motor.
MUSE macht Invarianten, Pakete, unabhängige Angriffe und seinen UI-Scope.
CODEX ist laut bestehendem Loop zunächst READ ONLY. Der Nutzer möchte Codex
als sparsame Ledger-Zentrale; nicht daraus unangekündigt einen konkurrierenden
Produktionswriter machen. Scope-Handoff vor Schreibarbeit ausdrücklich klären.

Erste Aufgabe: Bestätige die noch ungesicherten lokalen Änderungen und den
vorhandenen Runner/Wiederanlaufweg, soweit die verfügbaren Tools das erlauben.
Dann leite den nächsten kleinen vollständigen Ledger-Auftrag für Codex ab.
Ein YAML-Arbeitsplan beweist keinen laufenden Bot und keine Rebootsicherheit.
Keinen zweiten Runner erfinden/starten, solange der vorhandene ungeklärt ist.
Wenn lokale Maschine nicht erreichbar ist: als unbekannt festhalten und mit
sicherer Repository-/Paketarbeit fortfahren; keine Maschinenaktionen vortäuschen.

Keine Produktionsdienste oder fremden Prozesse starten/stoppen, keine Merges,
Deployments, Credential-Rotation, Zahlungen oder Publikationen ohne passende
explizite Autorität. Kein reset --hard, Blind-Cleanup oder Sandbox-Bypass.
Sichere Ergebnisse dauerhaft über einen erlaubten Recorder; keine endlosen
LLM-Polling-, Volltest- oder Statusschleifen. Ein echter Stop-Befehl gilt sofort.
Das Ziel ist erledigte und überprüfte Ledger-Arbeit, nicht Dauerverbrauch.
```

## B. Nächste autorisierte Codex-Sitzung auf dem MacBook

```text
COURIER — FOCUSED LEDGER CONTINUATION

Lies die Chat-Übergabe und den aktuellen
ops/ai/CODEX_CONTINUOUS_REVIEW.yaml.
Bleibe zunächst READ ONLY für Produktionscode und kanonische Daten.
Prüfe aktuellen HEAD, Ownership und bereits vorhandene Review-Ergebnisse.
Eine alte iteration: 0 in YAML beweist nicht, dass nie gearbeitet wurde.

Arbeite ausschließlich an Ledger/Guard und unmittelbar nötigen
Persistenz-/Motor-/Trust-Fragen. Verwende einen festen Review-Snapshot.
Verbrauche die vorhandenen vollständigen Pakete, nicht erneut das ganze Repo.
Priorität: konkrete Entscheidung/Review zur Attester-Vertrauenswurzel und zum
maßgeblichen Freshness-/Epoch-Vertrag; danach der passende kleine Code-Diff.
Owner-Drafts nicht verändern; nicht als committed ausgeben.

Vor Tests: State-Isolation, Testdateien, Timeout und eigene Prozesszuordnung
prüfen. Nur kleinste relevante T1/T2/T3-Sets, seriell bei geteilten Ressourcen.
Keine Produktionsabnahme aus Mocks und keine angeblichen Testläufe erfinden.

Ergebnis je Einheit: Snapshot, Paket, geprüfte Invariante, exakter Test/Reproducer,
beobachtetes Resultat, verbleibende Unsicherheit, nächste sichere Aktion.
Bei unvollständigem Paket: fehlende Felder konkret nennen und anderes fertiges
Ledger-Paket nutzen. Keine unveränderten bereits geprüften Pakete wiederholen.
Bei ausschließlich wartender Implementierung/Autorität: kontrolliert yielden,
nicht künstlich Kontingent verbrennen. Kein unbegrenztes LLM-Polling.

Vor Sitzungsende einen wiederverwendbaren Ergebnis-/Resume-Block liefern.
Dauerhafte Speicherung erfolgt über den autorisierten Recorder. Nicht eigenmächtig
no_commits/no_pushes/read_only des bestehenden Vertrags überschreiben.
Keine zweite Produktions- oder Agenteninstanz blind starten.
```

## C. Muse — schmaler paralleler Auftrag

```text
COURIER — PACKET AND EVIDENCE CONTINUITY
Lies aktuellen Muse-Checkpoint und Ownership. Google-owned Drafts bleiben tabu.
Sichere/prüfe die bereits existierenden Reproducer und Testartefakte statt neue
breite Audits zu starten. Bereinige nur in deinem genehmigten Dokumentations-
oder Testscope die offenen Paketfelder: genaue SHAs, echte Befehle/Exitcodes,
Test-Isolation, vorhandene Dateien, Unterschiede Draft/Remote/Physical.
Besonders: DLQ-06-Testlöschung, DLQ-07-FOLLOWUP, widersprüchliche
DLQ-01/02-Spezifikationen, alte NEXT_WORK-Zustände.
Keine neuen Produktfeatures und kein Auffüllen der Queue mit Scheinaufgaben.
YAML vor Commit wirklich parsen und den geschriebenen Stand erneut lesen.
Dokumentiere fertige Arbeit einmal; danach nächste echte sichere Einheit oder
explizites WAITING mit Resume-Bedingung. Keine schweren Paralleltests.
```

## D. Google — bestehende Implementierung fortsetzen, kein Neustart

```text
COURIER — RESUME OWNED LEDGER IMPLEMENTATION
Lies aktuellen Google-Loop, Ownership, deinen tatsächlichen Arbeitskopie-Diff
und die Übergabe. Sichere zuerst deine bereits vorhandenen uncommitteten Fixes
und notwendigen untracked Dateien; keine fremden Änderungen überschreiben.
Fahre am nächsten belegten eigenen Implementierungsproblem fort.

Führe nicht nochmals die gesamte Discovery durch. Gleiche die schwächere
History-/48h-Draft-Lösung mit dem noch offenen stärkeren Attester-/Epoch-Vertrag
ab; Partial-Mitigation bleibt Partial-Mitigation. Behalte legitime positive
Kontrollfälle, Edge-Conservation und task-lokale Fehlerisolierung bei.

T0/T1/T2/T3 als echte begrenzte Läufe mit isoliertem State und Exitcodes.
Keine gelöschten Regressionstests oder Schema-Mocks als Gesamtnachweis.
Liefere ein vollständiges, SHA-gebundenes Codex-Review-Paket mit konkreten Fragen.
Ledger-Akzeptanz nicht von Hand erzwingen. Kein physisches Windows-PASS ohne
beobachtete kanonische Prozess-/Artefaktbindung.
```

## Modell- und CLI-Hinweis

Der Vorschlag Mittel als Standard, Hoch gezielt, xhigh nur bei belegtem Mehrwert passt zur am 18.09.2026 gelesenen offiziellen Reasoning-Dokumentation. Arbeitsheuristik, keine Zusage über Tageskontingent und keine hier vorgenommene Konfigurationsänderung. Pro-Modus und Reasoning-Effort sind nicht überall dieselbe Einstellung.

Offizielle Referenzen:
https://developers.openai.com/api/docs/guides/reasoning
https://developers.openai.com/codex/cli/reference
https://help.openai.com/de-de/articles/11369540-codex-mit-ihrem-chatgpt-tarif-nutzen

Die CLI dokumentiert codex exec sowie codex resume / codex exec resume.
Installierte lokale Version und Hilfe entscheiden über konkrete Flags.
Keine Muse-Flags ungeprüft auf Codex übertragen und keine verschachtelte
interaktive Sitzung als Dauerbetrieb ausgeben.
