# AI + Community Knowledge Architecture

Date: 2026-09-20  
Status: architecture concept, not final implementation contract

## Ziel

Ein günstiger integrierter Assistent soll leichte Kundenfragen beantworten und gleichzeitig auf eine wachsende Courier-Wissensbasis zugreifen.

Wichtig: "Lernen" wird als **kontrolliertes Wissenswachstum** verstanden, nicht als ungeprüftes Training eines Basismodells auf allen Kundendaten.

## Empfohlene Schichten

```
User
  -> Courier Chat
  -> Policy / privacy / tenant gate
  -> Query classifier
  -> Knowledge retrieval
  -> if answerable from trusted knowledge:
         compose low-cost answer
     else:
         route to suitable model/tool
  -> citations / provenance
  -> feedback
  -> candidate knowledge
  -> moderation / verification
  -> versioned knowledge base
```

## Wissenseintrag

Jeder Knowledge-Record sollte mindestens enthalten:

- `knowledge_id`
- `tenant_scope` / public-community / private-customer
- Titel
- Problem
- Lösung
- Quelle(n)
- Ersteller
- Erstellzeit
- letzte Verifikation
- Version
- Status
- confidence / confirmation count
- tags / product area
- PII flag
- retention policy
- allowed-use flags

## Knowledge Lifecycle

1. **Candidate** — aus Nutzerfeedback/Agentenergebnis vorgeschlagen.
2. **Reviewed** — automatisiert oder menschlich geprüft.
3. **Verified** — Belege ausreichend.
4. **Published to retrieval** — im passenden Scope suchbar.
5. **Superseded** — durch neuere Version ersetzt.
6. **Withdrawn** — falsch, riskant oder veraltet.

## Datenschutz / Mandantentrennung

Community-Wissen und privates Kundenwissen dürfen nicht vermischt werden.

Mindestanforderungen:
- tenant isolation;
- consent / lawful basis;
- PII minimization;
- delete/export path;
- audit log;
- secrets never embedded as knowledge;
- per-source retention.

## Kostenkontrolle

- retrieval first;
- kurze Context-Pakete;
- kleine Modelle für einfache Fragen;
- Cache für häufige Fragen;
- batch embeddings;
- deduplication;
- budget per tenant/user/day;
- graceful fallback wenn externes Modell nicht verfügbar ist.

## Qualität

Antworten sollten im Produkt unterscheiden:
- "aus Courier-Wissen";
- "aus Kundendokumenten";
- "KI-generierte Einschätzung";
- "nicht sicher / braucht Prüfung".

## Community Flywheel

```
Frage
 -> gute Lösung
 -> explizites Feedback
 -> Kandidat
 -> Prüfung
 -> bestätigtes Wissen
 -> bessere nächste Antwort
 -> neue Bestätigung / Korrektur
```

So wird die Plattform mit der Zeit wertvoller, ohne ungeprüfte Aussagen automatisch als Wahrheit zu behandeln.

## Anbieterneutralität

OpenAI kann ein Modellanbieter sein. Die Courier-Wissensbasis, Datenmodelle, Routingregeln und Verifikationslogik sollten aber nicht an einen einzelnen Anbieter gekoppelt sein.

Die wertvolle langfristige Schicht ist:
- eigenes Knowledge;
- Provenance;
- Workflows;
- Agentenfähigkeiten;
- Feedback-/Verifikationsdaten;
- Nutzer-/Projektkontext unter sauberer Zugriffskontrolle.
