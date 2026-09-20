# Courier Symphony — Product Vision & Feature Map

Date: 2026-09-20  
Status: product vision / structured handoff

## Kernversprechen

Courier Symphony soll nicht nur chatten. Der Kern ist:

**Ziel eingeben -> Ziel verstehen -> Arbeit zerlegen -> passende Agenten/Tools einsetzen -> Ergebnisse speichern -> prüfen -> zusammenführen -> Ergebnis liefern.**

Der Nutzer soll nicht zuerst wissen müssen, welches Modell, welches Tool oder welcher Spezialagent nötig ist.

Beispiele:

- "Ich möchte Bäcker werden / einen Bäckereibetrieb aufbauen."
- "Ich möchte einen Pizza-Lieferdienst starten."
- "Ich brauche eine komplette Website für mein Geschäft."
- "Ich möchte Content für YouTube oder TikTok produzieren."
- "Ich möchte meine vorhandenen Mails, Dokumente und Entscheidungen durchsuchen und daraus weiterarbeiten."

## Goal-to-Done Flow

1. **Goal Intake** — freies Ziel in natürlicher Sprache.
2. **Clarification Gate** — nur fehlende kritische Angaben nachfragen.
3. **Plan** — Arbeit in überprüfbare Schritte zerlegen.
4. **Capability Routing** — günstige/leichte Agenten für leichte Arbeit; stärkere Modelle nur wenn nötig.
5. **Execution** — möglichst genau eine klar begrenzte externe Aktion zur Zeit, wenn der Workflow dies erfordert.
6. **Durable Result** — Ergebnis persistieren.
7. **Verify / Reconcile** — Ergebnis gegen Ziel und Belege prüfen.
8. **Continue** — nächste zulässige Aufgabe automatisch starten.
9. **Human Gate** — nur bei echter Freigabe-, Sicherheits-, Zahlungs-, Rechts- oder Ambiguitätsgrenze stoppen.
10. **Deliverable** — Nutzer bekommt Artefakt/Ergebnis statt nur eine Liste von Tipps.

## Produktmodule

### 1. Courier AI Chat

- leichter, günstiger Assistent für normale Fragen;
- Hilfe direkt im Produkt;
- erklärt Funktionen, nächste Schritte und bekannte Lösungen;
- soll nach Möglichkeit zuerst eigenes Courier-Wissen nutzen und nur dann ein Modell aufrufen;
- Modellanbieter soll austauschbar bleiben.

### 2. Community Knowledge

- gute freigegebene Lösungen können strukturiert gespeichert werden;
- Quellen, Version, Bestätigung und Vertrauensstatus gehören zum Wissenseintrag;
- nicht jede Chatnachricht wird automatisch "Wahrheit";
- mögliche Zustände: vorgeschlagen -> geprüft -> bestätigt -> veraltet/zurückgezogen;
- Ziel: dieselben Probleme nicht immer wieder von null lösen.

### 3. Courier Guild / Gilde

Vision: Menschen + spezialisierte Agenten + wiederverwendbare Skills.

Mögliche Rollen:
- Recherche;
- Text/Copy;
- Web/Code;
- Design;
- Content-Produktion;
- QA/Verifikation;
- branchenspezifische Fachleute;
- Community-Mentoren.

Die Gilde ist kein Versprechen, dass jeder Vorgang vollautomatisch oder ohne fachliche Verantwortung erledigt wird. Sie ist die Orchestrierungsschicht für Zusammenarbeit.

### 4. Website Factory

Aus einem Ziel wie "Ich brauche eine Website für meine Pizzeria" kann Courier einen Arbeitsplan ableiten:

- Unternehmensprofil und Zielgruppe;
- Seitenstruktur;
- Naming/Positionierung;
- Texte;
- FAQ;
- lokale Informationen;
- Bild-/Asset-Briefings;
- Frontend-/Template-Erstellung;
- technische Checks;
- Übergabe zur Veröffentlichung.

Wichtig: Domainkauf, Zahlungen, rechtliche Pflichttexte und produktive Veröffentlichung bleiben explizite Freigabepunkte.

### 5. Mail & Archive

Zielbild:
- Mails und Dokumente auffindbar machen;
- Entscheidungen aus alten Projekten wiederfinden;
- Zusammenhänge zwischen Mail, Aufgabe, Ergebnis und Projekt erhalten;
- keine privaten Mailinhalte in öffentliche Repositories spiegeln;
- Cloud-Ziel braucht eigene Zugriffskontrollen und Verschlüsselung.

### 6. Content Automation

Vorhandene Codebasis enthält Produktionspfade für YouTube und TikTok. Details siehe `CONTENT_PIPELINES_2026-09-20.md`.

Grundregel:
**Produktion darf automatisierbar sein; öffentliche Veröffentlichung bleibt ein gesondertes Gate.**

### 7. Dauerlauf / autonome Arbeit

Das Produktziel ist, nach einem bestätigten Abschluss selbstständig die nächste zulässige Aufgabe zu übernehmen, statt für jeden Schritt ein menschliches "Weiter" zu verlangen.

Sicherheitsprinzipien:
- kein Folgetask bei unklarem Ausgang;
- keine blinden Wiederholungen nach möglicher externer Submission;
- klare Pause/Stop-after-current-Semantik;
- persistente Ergebnisse statt flüchtiger Chatzustände.

## Kostenprinzip

"Billig" entsteht durch Architektur, nicht durch ein einzelnes Modell:

- Routing nach Aufgabenschwere;
- Retrieval vor Generierung;
- Cache / Wiederverwendung bestätigter Lösungen;
- kleine Modelle für einfache Fragen;
- lokale Verarbeitung dort, wo sinnvoll;
- stärkere Modelle nur bei höherem Nutzen;
- keine unnötige Parallelität;
- Budget-/Spend-Gates.

## Was Courier nicht behaupten sollte

- nicht "die KI trainiert sich automatisch an jeder Kundennachricht";
- nicht "kostenlos für immer", solange externe Infrastruktur reale Kosten verursacht;
- nicht "jede Idee gehört uns";
- nicht "vollautomatisch ohne Grenzen" bei Geld, Recht, Sicherheit, Publishing oder unbekanntem externen Zustand.

Bessere Formulierung:
**Courier baut eine eigene Wissens- und Orchestrierungsschicht, die mit freigegebenen, geprüften Lösungen und Produktwissen laufend besser werden kann.**


## Customer Packaging / Included AI

Founder-approved working direction (2026-09-20):

Courier should sell a **simple outcome package**, not expose raw model-token complexity to normal customers.

Initial hypothesis:
- roughly **EUR 99–100/month**;
- meaningful routine Courier AI/agent usage included;
- customer wording: **"included in your plan"**, not "free";
- fair-use / internal budget envelope protects unit economics;
- expensive or unusually large tasks trigger an explicit extra quote before work starts;
- no silent overages.

Customer experience:

`GOAL -> PLAN -> INCLUDED OR EXTRA QUOTE -> EXECUTE -> VERIFY -> RESULT`

Internal architecture may use credits, cost budgets, task classes and model routing, but the UI should remain simple.

Canonical working detail:
`docs/agent-warehouse/CUSTOMER_PACKAGING_AND_COST_GUARDRAILS_2026-09-20.md`
