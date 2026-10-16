# COURIER SYMPHONY — BUSINESS VALUE & OFFERINGS PACKAGE
**Date:** 2026-10-09  
**Status:** Internal Drafts (0 External Spend, 0 Direct Marketing)  
**Positioning:** "Courier makes AI work verifiable, continuous and safe against duplicate effects."

---

## 1. Candidate Offerings

### Offer A: Doppel-Check für n8n- & Make-Workflows
- **Problem:** Automatisierte Workflows in n8n/Make führen bei Retries, Timeouts oder Webhook-Wiederholungen Aktionen doppelt aus (z.B. doppelte Rechnungsstellung, doppelte CRM-Einträge, zweifache E-Mail-Zustellung).
- **Lösung:** Courier Side-Effect Guard mit Idempotenz-Schlüsseln, Fencing-Token und atomarer Quittierung.
- **Zielgruppe:** Agenturen und Operations-Teams mit komplexen n8n/Make-Pipelines.
- **Pilot-Modell:** Kostenloser Proof of Concept für 3–5 ausgewählte Teams (1 Workflow).
- **Testhypothese:** 99 € Einmalgebühr / Setup pro geschütztem Workflow.

### Offer B: Repo Reality Check
- **Problem:** Agenten-gestützte Entwicklungs-Repositories ersticken in duplizierten Branches, unvollständigen PR-Stapeln und unklaren CI-Fehlern (wie unser eigener Backlog von 226 PRs).
- **Lösung:** Unabhängige, read-only Bestandsaufnahme und Entflechtung: Identifikation von Duplikaten, Merge-Basen und echten Fehlern vs. vererbtem Trunk-Rot.
- **Pilot-Modell:** Schneller manuell-gestützter Audit-Report für 1 Repository.
- **Testhypothese:** 49 € Testpreis für einen ersten strukturierten Entflechtungsbericht.

### Offer C: Workshop "Agent-Workflows ohne Doppelungen"
- **Inhalt:** 90-minütiger interaktiver Remote-Workshop:
  1. Warum native AI-Resumes externe Nebenwirkungen nicht verhindern.
  2. Exactly-Once vs. At-Least-Once in der Agenten-Praxis.
  3. Einrichtung von Side-Effect Guards mit atomaren Fencing-Tokens.
- **Testhypothese:** 49–99 € pro Teilnehmer.

---

## 2. Pilot-Checkliste (Pre-Flight vor Kundeninteraktion)
- [ ] Rechtliche Klärung (Gewerbe / Kleinunternehmer / steuerliche Erfassung).
- [ ] Scope-Definition: Keine direkten Schreibzugriffe auf Produktionsdatenbanken.
- [ ] Test-Webhook / Sandbox-Umgebung vorhanden.
- [ ] Schriftliche Bestätigung des Kunden für Pilot-Bedingungen.

---

## 3. Häufige Fragen (FAQ)
**F: Ersetzt Courier mein vorhandenes n8n oder Make?**  
*A: Nein. Courier setzt als Verifizierungs- und Schutzschicht vor kritische Aktionen an, um Doppelungen zu verhindern.*

**F: Was unterscheidet Courier von Session-Resumes in Claude oder Cursor?**  
*A: Lokale Tools merken sich den Chatverlauf. Courier garantiert über einen manipulationssicheren Ledger, dass externe Aktionen (Zahlungen, E-Mails, API-Calls) nach einem Neustart nicht doppelt ausgelöst werden.*
