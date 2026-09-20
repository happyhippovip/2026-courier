# COURIER SYMPHONY — KANONISCHER PRODUKTPLAN

Status: Kanonische Arbeitsgrundlage bis zur nächsten ausdrücklich freigegebenen Revision  
Stand: 2026-09-20  
Prinzip: Finish vor Ausbau  
Steuerungsregel: Critical Path · Later · Non-Goal  
Beweisregel: No Evidence → No PASS  
Änderungsregel: No Authorization → No Scope Expansion

## Externes Kernversprechen

„Courier bringt dich am nächsten Tag genau dort weiter, wo du aufgehört hast.“

Dieses Versprechen ist die externe Produktbotschaft.

Interne Begriffe wie Ledger, Attempts, Evidence, Autonomy Grade oder Earned Autonomy werden Kunden nur gezeigt, wenn sie für Vertrauen oder Bedienung tatsächlich hilfreich sind.

---

## 0. Steuerung des Plans

Der Plan trennt drei Dinge strikt:

1. Gate-Status — Wie weit ist der Beweis?
2. Arbeitsfreigabe — Darf daran aktuell gearbeitet werden?
3. Priorität — Ist es der aktuelle Critical Path?

Damit bedeutet IN_PROGRESS nicht automatisch, dass mehrere Gates gleichzeitig Hauptpriorität haben.

### Aktueller Steuerungszustand

| Gate | Ziel | Status | Arbeitsfreigabe |
|---|---|---|---|
| 1 | Trusted Ledger | IN_PROGRESS | ACTIVE |
| 2 | Reliable Motor | IN_PROGRESS | ACTIVE_BOUNDED |
| 3 | Zero-Human A→B | NOT_PROVEN | PREP_ONLY |
| 4 | Restart & Recovery | NOT_PROVEN | PREP_ONLY |
| 5 | Bezahlter Minimalpilot | NOT_STARTED | NON_CODE_PREP |
| 6 | Product Shell | LOCKED | NO |
| 7 | Packaging / Updates | LOCKED | NO |

ACTIVE: aktueller Critical Path.

ACTIVE_BOUNDED: nur Arbeit, die Gate 1 nicht destabilisiert.

PREP_ONLY: Tests, Fixtures und Pläne vorbereiten; Gate noch nicht beanspruchen.

NON_CODE_PREP: Pilotkandidaten, Zahlungsweg, Datenschutz und Baseline dürfen vorbereitet werden.

LOCKED: nicht bauen.

Status wird ausschließlich durch Evidenz geändert.

---

## 1. Produktziel

Courier Symphony führt begonnene Arbeit zuverlässig, nachvollziehbar und wiederaufnehmbar weiter.

Der Nutzer definiert ein Ziel.

Courier speichert dauerhaft mindestens:

- Goal
- Goal Contract
- Tasks
- Dependencies
- Zuständigkeiten
- Attempts
- Executions
- Results
- Evidence
- Entscheidungen
- Fortsetzungszustand

Courier setzt autorisierte Arbeit selbstständig fort, ohne dass der Nutzer fortlaufend:

- Prompts kopiert
- Ergebnisse zwischen Agenten verschiebt
- Worker auswählt
- Anbieter manuell wechselt
- Status korrigiert
- „weiter“ schreibt

Courier stoppt nur an einer echten Grenze:

- menschliche Entscheidung
- Geldfreigabe
- Berechtigung
- Sicherheitsgrenze
- rechtliche Freigabe
- nicht auflösbarer Zielkonflikt
- ausdrücklich verlangte menschliche Kontrolle

Kernnutzen:

Nachweisbare, wiederaufnehmbare Autonomie über Tools, Worker, Provider und Sessions hinweg.

---

## 2. Internes Wettbewerbsverständnis

Nur intern:

„Nicht Codex oder Claude Code im Hintergrund, sondern tool-übergreifende, beweisbare Autonomie mit Ledger und prüfbaren Autonomy Grades.“

Der Wettbewerbsvorteil ist nicht die Anzahl der Modelle.

Der Wettbewerbsvorteil ist:

Courier weiß nachweisbar, was passiert ist, was als Nächstes passieren darf und ob es nach einem Abbruch korrekt weitergeht.

---

## 3. Verbindliche Reihenfolge

1. Trusted Ledger
2. Reliable Courier Motor
3. Zero-Human A→B
4. Restart & Recovery
5. Bezahlter Minimalpilot
6. Pilotentscheidung
7. Product Shell
8. Wiederholbaren Vertrieb beweisen
9. Packaging und Updates
10. Connector-/Plattformausbau

Ein späteres Gate darf ein früheres Gate niemals durch:

- UI
- Dokumentation
- Simulation
- Selbstbericht
- zusätzliche Features

ersetzen.

---

## 4. Gate 1 — Trusted Ledger

### Ziel

Courier besitzt eine dauerhaft rekonstruierbare Wahrheit darüber:

- was beauftragt wurde
- welcher Vertrag vor Arbeitsbeginn galt
- was gestartet wurde
- welcher Worker tätig war
- welcher Attempt betroffen war
- welche Execution stattfand
- welches Result zurückkam
- welche Evidenz entstand
- was geprüft wurde
- was akzeptiert wurde
- was abgelehnt wurde
- was UNKNOWN blieb

### Pflicht

Mindestens:

- stabile Goal-ID
- stabile Task-ID
- stabile Attempt-ID
- stabile Execution-ID
- stabile Result-ID
- eindeutige Result-Bindung
- idempotente Result-Verarbeitung
- identische Duplicates erzeugen keine Doppelwirkung
- widersprüchliche Duplicates werden abgelehnt
- stale Results überschreiben keine aktuelle Wahrheit
- Persistenz überlebt Restart
- Reconciliation ist idempotent
- unbelegte Historie bleibt UNKNOWN
- Provenienz wird nicht nachträglich erfunden

### Candidate-Bindung

Ein PASS ist ausschließlich für einen konkreten Candidate gültig.

Mindestens gebunden werden:

- Source SHA
- Tree/Fingerprint
- relevante Konfiguration
- geladene Runtime-Identität, falls erforderlich
- Acceptance-Evidence

Source auf Platte und tatsächlich geladene Runtime dürfen nicht verwechselt werden.

### PASS

Gate 1 ist PASS nur wenn:

- Ledger-Fingerprint definiert
- exakter Candidate gebunden
- erforderliche Tests erfolgreich
- erforderliche Runtime-Bindung vorhanden
- keine gateverletzenden UNKNOWNs
- unabhängige Abnahme vorhanden

Danach:

LEDGER_FROZEN = YES

---

## 5. Goal Contract — der harte Prüfanker

Vor autonomer Ausführung bestätigt der Mensch einmal den Goal Contract.

Dieser enthält mindestens:

- gewünschtes Endergebnis
- erlaubten Scope
- nicht erlaubten Scope
- relevante Constraints
- Akzeptanzkriterien
- erforderliche Evidenzklasse
- relevante Side-Effect-Grenzen
- Human-/Money-/Safety-Gates

Danach darf Courier daraus selbst Task-Verträge ableiten.

Diese müssen eindeutig auf den Goal Contract rückführbar sein.

Courier darf einen Task zerlegen.

Courier darf die Erfolgsvoraussetzungen nicht eigenmächtig verändern.

Erfordert neue Erkenntnis eine Erweiterung des Goal Contracts:

HUMAN_CONFIRMATION_REQUIRED

Fehlt ein ausreichender Prüfanker:

NOT_VERIFIABLE

Niemals automatisch:

PASS

---

## 6. Unabhängige Verifikation

Verifikation ist evidenzbasiert, nicht modellbasiert.

Bevorzugte Reihenfolge:

1. deterministische Prüfung
2. reproduzierbarer automatisierter Test
3. unabhängiger Reviewer
4. physischer End-to-End-Beweis

Ein zusätzlicher AI-Reviewer ist nicht nötig, wenn ein deterministischer Test das Akzeptanzkriterium vollständig beweist.

Wenn ein unabhängiger Reviewer erforderlich ist, gilt:

- nicht der Writer
- nicht dasselbe Modell
- nicht derselbe Arbeitskontext
- keine Übernahme des Writer-Selbsturteils als Evidenz

Teure unabhängige Modelle werden nur dort verwendet, wo deterministische Evidenz nicht ausreicht.

---

## 7. Gate 2 — Reliable Courier Motor

### Ziel

Ein gültiges Result führt deterministisch zur nächsten zulässigen Aktion.

### Verbindlicher Pfad

Result  
→ persistieren  
→ validieren  
→ gegen Goal-/Task-Contract prüfen  
→ reconcile  
→ Dependencies aktualisieren  
→ READY neu berechnen  
→ Eligibility prüfen  
→ Worker auswählen  
→ dispatchen

### Regeln

- kein menschlicher Continue-Befehl im Normalpfad
- Queue leer = IDLE
- IDLE erzeugt keine Arbeit
- kein AI-Polling
- kein Tight Polling
- Retries sind begrenzt
- Provider-Ausfall blockiert nur betroffene Arbeit
- unabhängige READY-Arbeit darf weiterlaufen
- ein logischer Attempt hat höchstens eine aktive externe Execution
- ein mutable Scope hat höchstens einen aktiven Writer
- UNKNOWN Execution wird reconciled, nicht blind neu gestartet

### PASS

Gate 2 ist PASS, wenn der komplette Pfad automatisiert und reproduzierbar funktioniert.

---

## 8. Gate 3 — Zero-Human A→B

Physisch beweisen:

ONE GOAL  
→ Task A  
→ realer Worker  
→ reales Result A  
→ automatische Verifikation  
→ automatische Reconciliation  
→ Task B READY  
→ automatische Worker-Auswahl  
→ automatischer Dispatch  
→ reales Result B  
→ DONE

### Pflichtmetrik

HUMAN_RELAY_COUNT = 0

Nicht zulässig:

- Prompt kopieren
- „Weiter“
- Worker manuell auswählen
- Result manuell übertragen
- Status manuell setzen
- B manuell starten
- Result manuell injizieren

Fixtures dürfen vorbereiten.

Fixtures dürfen Gate 3 nicht beweisen.

---

## 9. Gate 4 — Restart & Recovery

Mindestens folgende Matrix wird getestet:

- Courier-Prozessrestart
- Worker verschwindet
- Result persistiert, Reconcile fehlt
- READY vor Dispatch
- Dispatch erfolgt, Result fehlt
- Provider temporär nicht verfügbar
- stale Result
- identisches Duplicate Result
- widersprüchliches Duplicate Result

Für jedes Szenario gilt:

- kein Task verloren
- kein akzeptiertes Result verloren
- keine stille Doppelwirkung
- stale Daten überschreiben keine aktuelle Wahrheit
- Zustand bleibt ehrlich
- nächste zulässige Aktion ist deterministisch

### RSR

RSR = erfolgreich bestandene Restart-Szenarien / definierte Restart-Szenarien

Gate-Ziel:

RSR = 100 %

Neue Restart-Szenarien erweitern die Matrix und können Revalidation auslösen.

---

## 10. Proof Card

Jede wesentliche abgeschlossene Arbeit besitzt eine kompakte Proof Card.

Pflichtfelder:

- Goal-ID
- Goal-Contract-Fingerprint
- Task-ID
- tatsächliches Result
- Akzeptanzkriterien
- Evidence-IDs
- Prüfstufe
- Source-/Build-/Runtime-Fingerprint
- Covered Surface
- UNKNOWNs
- Human Interventions
- Revalidation-Status

Keine lange Agentenprosa.

---

## 11. Proof Levels

P0 — SELF_REPORTED  
Worker behauptet Erfolg.

P1 — DETERMINISTIC_TESTED  
Automatisierte deterministische Evidenz vorhanden.

P2 — INDEPENDENTLY_VERIFIED  
Unabhängige Prüfung vorhanden.

P3 — PHYSICAL_E2E  
Realer End-to-End-Pfad physisch bewiesen.

Ein höherer Proof Level ersetzt keine fehlenden Akzeptanzkriterien.

---

## 12. Autonomy Grade

Autonomy Grade beschreibt bewiesenes Systemverhalten, nicht Marketing.

Grade A0 — MANUAL

Menschlicher Relay-Schritt erforderlich.

Grade A1 — SINGLE_STEP

Ein Task kann ohne Relay abgeschlossen werden.

Grade A2 — AUTO_CONTINUE

Result führt automatisch zur nächsten zulässigen Arbeit.

Grade A3 — ZERO_RELAY_CHAIN

Mehrstufige reale Arbeit erreicht:

HUMAN_RELAY_COUNT = 0

Grade A4 — RECOVERY_RESILIENT

A3 plus vollständige definierte Restart-Matrix.

Ein Grade gilt nur für seine konkrete Covered Surface.

---

## 13. Covered Surface

Jeder Autonomy Grade bindet:

- Module
- relevante Konfiguration
- externe Verträge
- Connector-Verträge
- Contract-Fingerprint
- notwendige Acceptance Tests

Ändert sich ein entscheidungsrelevanter Bestandteil:

REVALIDATION_REQUIRED

Der alte Grade wird bis zur erfolgreichen Revalidation nicht als aktuell gültig angezeigt.

Änderungen außerhalb der Covered Surface entwerten den Grade nicht automatisch.

---

## 14. Gate 5 — Minimaler Pilot

Der Pilot kommt vor einer schönen Product Shell.

Sichtbar benötigt werden nur:

- Arbeitet
- Braucht dich
- Fertig
- Proof Card
- Proof Level
- Autonomy Grade
- nächste Aktion

Nicht erforderlich:

- großes Home
- umfangreiche Navigation
- Marketplace
- Update-UI
- Enterprise-Admin
- großes Dashboard

Der Pilot testet Nutzen, nicht Designqualität.

---

## 15. Pilot-Installation

Ein automatischer Installer ist keine Pilotvoraussetzung.

Erste Piloten dürfen:

- begleitet
- manuell eingerichtet
- persönlich onboarded

werden.

Dieser Aufwand wird gemessen:

SETUP_MINUTES_PER_PILOT

Manuelles Setup darf im Pilot existieren.

Es darf nicht als skalierbarer Endzustand ausgegeben werden.

---

## 16. Pilot mit echten Menschen

Jeder Pilot besitzt:

- klares Goal
- menschlich bestätigten Goal Contract
- dokumentierte Baseline
- Pilotdauer
- vereinbarten Preis
- Daten-/Permission-Scope

Zielgruppe sind Menschen mit realem Problem durch:

- verlorenen Kontext
- Copy/Paste
- manuelle Übergaben
- wiederholtes Erklären
- Session-Abbrüche

Der Pilot testet ausschließlich:

„Courier bringt dich am nächsten Tag genau dort weiter, wo du aufgehört hast.“

---

## 17. Pilotmetriken

### HIPG — Human Interventions per Goal

HIPG = notwendige menschliche Fortsetzungseingriffe / abgeschlossene oder beendete Goals

Ziel:

HIPG < 1,0

Normale initiale Goal-Bestätigung wird nicht als Relay gezählt.

Echte HUMAN_REQUIRED-Entscheidungen werden separat erfasst.

### RSR

RSR = bestandene Restart-Szenarien / ausgeführte definierte Restart-Szenarien

Ziel:

100 %

### NDR — Next-Day Return

Ein Pilot zählt als NDR, wenn der Nutzer am Folgetag aus eigenem Interesse Courier erneut nutzt oder seinen begonnenen Goal-Pfad fortsetzt.

Erste 5er-Kohorte:

3–5 / 5 → GO

positives Signal; nächstes Gate darf vorbereitet werden.

2 / 5 → ITERATE ONCE

genau ein begrenzter Iterationszyklus am Kernversprechen, Use Case oder Zielsegment.

Danach neue Kohorte messen.

0–1 / 5 → REVIEW CORE PROMISE

kein automatischer Feature-Ausbau.

Fünf Piloten sind:

ein Entscheidungssignal, kein Marktbeweis.

---

## 18. Zahlung im Pilot

Der erste Umsatz wartet nicht auf Billing-Plattform oder Installer.

Pilot-Orientierung:

49–99 € Setup-/Pilotgebühr

Der Preis ist ein Experiment.

Zu messen:

- PAYMENT_YES/NO
- tatsächlicher Betrag
- Setup-Aufwand
- Wiederkehr
- Support-Aufwand
- Providerkosten

Feedback ohne Zahlungsbereitschaft ist schwächere Evidenz als eine echte Zahlung.

---

## 19. Pilot-Voraussetzungen

Vor dem ersten bezahlten externen Pilot müssen ausreichend geklärt sein:

- einfacher Zahlungsweg
- verarbeitete Nutzerdaten
- Speicherort
- beteiligte Provider
- Berechtigungen
- Aufbewahrung
- Löschung
- notwendige Datenschutzhinweise
- organisatorische DSGVO-Pflichten
- steuerliche/gewerbliche Voraussetzungen

Falls erforderlich werden insbesondere geprüft:

- Gewerbeanmeldung
- steuerliche Erfassung
- Umsatzsteuer-/Kleinunternehmerfragen

Der Produktplan ersetzt keine individuelle Rechts- oder Steuerberatung.

Diese Punkte blockieren nicht Gate 1–4.

Sie können aber den Start eines bezahlten externen Piloten blockieren.

---

## 20. Parallelspur ab sofort

Während Gate 1–4 darf Nicht-Code-Arbeit parallel laufen.

Erlaubt:

- Pilotkandidaten ansprechen
- Kandidatenliste führen
- Baseline-Fragebogen vorbereiten
- Pilotgespräch vorbereiten
- Zahlungsweg vorbereiten
- Datenfluss inventarisieren
- Pilotunterlagen vorbereiten
- Pilotpreis testen

Nicht erlaubt:

- große Marketingkampagne
- Product Shell vorziehen
- Billing-Plattform bauen
- Features aus ungeprüften Interviewwünschen bauen

Die Parallelspur darf den Engineering-Critical-Path nicht unterbrechen.

---

## 21. Gate 6 — Product Shell

Nur nach positivem Pilotsignal.

Zielpfad:

Connect  
→ Goal  
→ Arbeitet  
→ Braucht dich  
→ Fertig

Optional:

Details öffnen

Interne Komplexität bleibt intern.

Der Kunde muss Ledger, Attempts, Workers oder Execution-IDs nicht verstehen.

---

## 21a. Courier Brain — providerunabhaengiger eigener Kontext (LATER)

**Klassifikation:** LATER bis positiver Pilotnachweis; keine Freigabe, Gate 1–5 zu ueberspringen.

Courier soll spaeter einen eigenen, providerunabhaengigen Kontext-/Wissensspeicher anbieten, den Nutzer zu Beginn auswaehlen oder neu anlegen koennen. Arbeitsname: **Courier Brain**.

Ziel:
- wiederverwendbarer Nutzer-/Projektkontext bleibt ausserhalb einzelner Provider-Chats,
- Nutzer koennen ein vorhandenes Brain waehlen, ein leeres Brain starten oder ein eigenes importieren,
- der Katalog darf offizielle Brain-Vorlagen/Manifeste anbieten,
- private Brain-Inhalte bleiben standardmaessig privat und werden nicht automatisch in einen oeffentlichen Katalog kopiert,
- Export, Loeschung und Providerwechsel muessen moeglich bleiben.

**Abgrenzung:**
- Brain = wiederverwendbarer Kontext, Wissen, Praeferenzen und freigegebene Quellen.
- Ledger = belegte Ausfuehrungswahrheit.
- Goal Contract = konkrete Erfolgskriterien und Grenzen eines Goals.
- Katalog = auffindbare Vorlagen/Manifeste; er ist nicht automatisch der Speicher privater Inhalte.

Ein Brain darf keine Ausfuehrungsrechte, Geldgrenzen oder Goal-Contract-Grenzen erweitern. Auswahl oder Wechsel eines Brains startet keinen Job.

Vorgesehener spaeterer Product-Shell-Pfad:

**Brain waehlen/neu -> Connect -> Goal -> Arbeitet -> Braucht dich -> Fertig**

Ein **Leeres Brain** bleibt immer moeglich, damit die Funktion kein Zwang fuer einfache Piloten wird.

---

## 22. Gate 7 — Packaging / Updates

Erst nach Core- und Pilotnachweis.

Erforderlich werden später:

- reproduzierbarer Build
- Source-Identität
- Build-Identität
- Loaded-Runtime-Identität
- Single Instance
- sicheres Update
- Rollback
- Last Known Good
- State-Kompatibilität
- keine verlorene laufende Arbeit

---

## 23. Non-Goals / Scope Freeze

Bis zum positiven Pilotnachweis nicht bauen:

- Marketplace
- vollständige Billing-Plattform
- Enterprise-Admin
- Kubernetes
- Multi-Region
- großes Dashboard
- vollständige Social-Automation
- Spieleplattform
- Millionen-Task-Cannon als Produktionsziel
- zusätzliche Ledger
- zusätzliche Scheduler ohne belegte Lücke
- zusätzliche Watchdogs ohne belegte Lücke
- perfekte Desktop-Shell
- App-Store-Optimierung
- spekulative Enterprise-Funktionen

Default = nicht bauen.

Nicht im Plan:

→ keine Implementierung ohne ausdrückliche Freigabe.

---

## 24. Agenten-Grenzen

Agenten dürfen:

- Code implementieren
- Tests ausführen
- Evidenz erzeugen
- Reviews durchführen
- Fehler klassifizieren
- dependency-sichere autorisierte Arbeit fortsetzen
- Metriken auswerten

Agenten dürfen nicht:

- eigene Rechte erweitern
- Scope selbst erweitern
- Geldgrenzen verändern
- Sicherheitsgrenzen verändern
- Kundendaten unautorisiert freigeben
- ungefragt publizieren
- UNKNOWN zu PASS machen
- Proof Levels erfinden
- Erfolg erfinden
- neue Arbeit nur zur Beschäftigung erzeugen

---

## 25. Gate-Timeboxes

Timeboxes sind Review-Grenzen, keine künstlichen PASS-Deadlines.

Default:

Gate 1–4:  
5 Arbeitstage bis zwingender Scope-/Blocker-Review

Pilotvorbereitung:  
5 Arbeitstage für Minimalvoraussetzungen

erste Pilotkohorte:  
10–14 Kalendertage

erste Product Shell:  
maximal 10 Arbeitstage bis Review

Wenn ein Gate nach der Timebox nicht PASS ist:

1. Arbeit stoppen
2. ersten kausalen Blocker benennen
3. Scope prüfen
4. nicht kausale Arbeit entfernen
5. Evidenzlage prüfen
6. entscheiden:
   - weiter
   - enger schneiden
   - blockieren
   - Ansatz ändern

Eine Verlängerung braucht einen dokumentierten Grund.

Kein Gate verlängert sich still selbst.

---

## 26. Gate-Zustände

Erlaubte Zustände:

- NOT_STARTED
- PREP_ONLY
- IN_PROGRESS
- BLOCKED
- REVALIDATION_REQUIRED
- PASS
- FROZEN

PASS bedeutet:

Gate-Kriterien aktuell bewiesen.

FROZEN bedeutet:

Gate ist abgeschlossen und reguläre Änderung beendet.

Nur PASS erlaubt den regulären Übergang zum nächsten Gate.

Nur FROZEN beendet reguläre Arbeit an einem abgeschlossenen Gate.

„Fast fertig“ ist kein Zustand.

---

## 27. Evidence Invalidation

Ein bestehender PASS wird ungültig, wenn:

- Covered Surface relevant geändert wurde
- Candidate gewechselt hat
- Runtime nicht mehr zum akzeptierten Build passt
- Akzeptanzvertrag geändert wurde
- relevante Konfiguration geändert wurde
- vorherige Evidence nachweislich falsch oder unvollständig war

Dann:

REVALIDATION_REQUIRED

Nicht:

„war früher grün, also bleibt es grün.“

---

## 28. Definition von Core fertig

Core fertig bedeutet:

- Ledger PASS + FROZEN
- Motor PASS
- Result → Verify → Reconcile → Next READY bewiesen
- A→B ohne Relay physisch bewiesen
- Restart-Matrix PASS
- Autonomy Grade mindestens A4 für den definierten Core-Scope
- Ressourcenbetrieb bounded
- keine Tight-Polling-Schleifen
- Proof Cards korrekt
- Covered Surface gebunden

Dann gilt:

CORE_FREEZE

Danach Core-Änderungen nur bei:

- beobachtetem kausalen Defekt
- Sicherheitsproblem
- notwendiger Revalidation
- realer Kundenanforderung
- nachgewiesenem wirtschaftlichem Vorteil

---

## 29. Entscheidungsregel für jede neue Idee

Jede neue Idee erhält genau eine Kategorie.

### CRITICAL PATH

Ohne diese Arbeit kann das aktuelle Gate nicht PASS werden.

→ jetzt bearbeiten

### LATER

Wertvoll, aber für das aktuelle Gate nicht erforderlich.

→ notieren, nicht bauen

### NON-GOAL

Verletzt Scope Freeze oder lenkt vom Kernversprechen ab.

→ nicht bauen

Unklar:

→ nicht starten

Technische Interessantheit, Agentenbegeisterung oder freie Rechenzeit machen eine Idee nicht zum Critical Path.

---

## 30. Kanonischer kritischer Pfad

### JETZT

Ledger remote, exakt gebunden und unabhängig schließen.

Parallel ausschließlich:

- Pilotkandidaten
- Baseline
- Zahlungsweg
- Daten-/Compliance-Vorbereitung

### DANACH

Reliable Motor PASS.

### DANN

Zero-Human A→B.

### DANN

Restart-Matrix und A4.

### DANN

Minimaler bezahlter Pilot.

### DANN

HIPG, RSR, NDR, Zahlung und Supportaufwand auswerten.

### BEI POSITIVEM SIGNAL

Product Shell.

### ERST DANACH

Packaging.

Updates.

breitere Connectoren.

skalierter Vertrieb.

---

## 31. Kanonische Stop-Regel

Arbeit wird beendet, wenn:

- aktuelles Gate PASS und anschließend FROZEN ist
- kein dependency-sicheres autorisiertes Critical-Path-Item verbleibt
- echte menschliche Entscheidung erforderlich ist
- Permission-/Safety-/Money-Grenze erreicht wurde
- weitere Arbeit nur LATER oder NON-GOAL wäre

Kein Agent erfindet Arbeit, nur weil noch Zeit oder Compute verfügbar ist.

---

## 32. Produktprinzip

Courier gewinnt nicht dadurch, dass es mehr Dinge gleichzeitig tut.

Courier gewinnt dadurch, dass begonnene Arbeit morgen zuverlässig, beweisbar und ohne menschliches Relay weitergeht.

## Kanonische Klarstellungen dieser Revision

- Gate-Status und Arbeitsfreigabe sind getrennt – damit widerspricht „Gate 2 IN_PROGRESS“ nicht mehr automatisch der Reihenfolge.
- HIPG, RSR und NDR sind berechenbar, nicht nur Schlagworte.
- Autonomy Grade hat A0–A4 statt eines undefinierten Scores.
- PASS kann aktiv ungültig werden, wenn Covered Surface, Candidate oder Runtime sich ändern.
- Goal Contract und Task-Vertrag sind getrennt: der Mensch bestätigt einmal das Ziel; Courier darf danach autonom zerlegen.
- Es gibt eine kanonische Stop-Regel. Ein Agent kann nach einem bestandenen Gate nicht einfach neue „wichtige“ Arbeit erfinden.


---

## Datenschutz-/Speicherhinweis

Persönliche Zahlungs-, Konto-, Steuer- oder Identifikationsdaten gehören **nicht** in das öffentliche Courier-Repository. Private Zahlungsdaten werden nur in dafür vorgesehenen privaten Nutzerunterlagen verwaltet.
