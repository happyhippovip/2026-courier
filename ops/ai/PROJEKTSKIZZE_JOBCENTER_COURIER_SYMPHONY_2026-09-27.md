# Projektskizze — Courier Symphony
## Stand: 27.09.2026

### 1. Vorhaben in einem Satz
**Courier Symphony soll aus einem Ziel ein nachvollziehbar bearbeitetes digitales Projekt machen, ohne dass der Nutzer ständig Ergebnisse zwischen verschiedenen KI-Systemen kopieren und die Arbeit selbst koordinieren muss.**

Leitidee: **KI/Muse erschafft. Courier liefert. Der Ledger beweist.**

### 2. Ausgangsproblem
Heutige KI-Werkzeuge können einzelne Aufgaben sehr gut bearbeiten. Bei längeren Projekten bleibt jedoch viel Koordinationsarbeit beim Menschen: Aufgaben verteilen, Ergebnisse übertragen, Fortschritt merken, Doppelarbeit erkennen, prüfen, ob etwas wirklich fertig ist, und entscheiden, was als Nächstes passieren soll.

Courier Symphony soll diese Lücke schließen. Das System soll ein Ziel in Arbeitspakete überführen, geeignete KI-Motoren koordinieren, Ergebnisse zurücknehmen, verifizieren, den Zustand im Ledger festhalten und — wenn sicher möglich — selbstständig mit dem nächsten sinnvollen Schritt fortfahren.

### 3. Kundennutzen
Der Kunde soll nicht 20 Terminals, Agenten oder Tokenanzeigen verstehen müssen. Er sieht einen einfachen **Courier** als menschliche Oberfläche des Ledgers.

Beispiel:
> 📦 AUFTRAG: Kerzen-Shop  
> 🟡 Wird gebaut  
> ✅ Logo fertig  
> ✅ Startseite verifiziert  
> 🔍 Bezahlung wird geprüft  
> 💤 Unnötige Arbeit nicht gestartet  
> 👤 Von dir brauche ich gerade nichts

Das Maskottchen ist damit keine reine Dekoration. Seine Zustände entsprechen echten Systemzuständen: Auftrag angenommen, unterwegs, Prüfung, verifiziert zugestellt, bewusst wartend, geschützt oder menschliche Entscheidung erforderlich.

### 4. Das zentrale Erlebnis
Der geplante Kernbeweis ist bewusst einfach:

1. Nutzer beschreibt ein reales Projekt.
2. Courier wird einmal gestartet.
3. Nutzer kann das Gerät verlassen.
4. Courier führt mehrere sinnvolle Schritte automatisch weiter.
5. Ergebnisse werden tatsächlich geprüft.
6. Beim Zurückkommen sieht der Nutzer verständlich, was erledigt und verifiziert wurde, was wartet und ob eine Entscheidung erforderlich ist.

Beispiel:
> „Während du weg warst, habe ich 7 Schritte weitergebracht. 5 sind verifiziert. Einer wartet. Einen unnötigen Lauf habe ich nicht gestartet. Ich brauche dich gerade nicht.“

Alle Zahlen müssen aus dem echten Ledger stammen; keine erfundenen Fortschrittswerte.

### 5. Technischer Kern: Living Ledger
Der Ledger ist die Vertrauens- und Steuerungsschicht:

GOAL → CONTRACT → TASK → CLAIM → EXECUTION → RESULT → VERIFY → RECONCILE → NEXT

Ein gemeldetes Ergebnis ist noch kein bewiesenes Ergebnis. Erst nach erfolgreicher Verifikation darf Courier es entsprechend darstellen.

Der Ledger soll außerdem unnötigen Ressourcenverbrauch vermeiden: bereits erledigte Arbeit wiederverwenden, Doppelarbeit unterdrücken, blockierte Aufgaben nicht starten und die Zahl gleichzeitig laufender schwerer Prozesse an das Gerät anpassen.

### 6. Courier Pocket — einfache Handyansicht
Geplant ist eine datenarme, zunächst lesende Handy-/Webansicht des echten Ledgers. Sie zeigt nur das, was der Nutzer wissen muss:
- Was wollte ich?
- Was passiert gerade?
- Was ist wirklich geprüft?
- Braucht Courier mich?
- Was passiert als Nächstes?
- Welche Kosten/Ressourcen wurden tatsächlich beobachtet, soweit messbar?

Keine zweite Datenquelle und keine künstliche Fortschrittsanzeige.

### 7. Geschäftsmodell / Zielgruppe
Geplantes niedrigschwelliges Einstiegsangebot: **ca. 14 €**. Zielgruppen sind insbesondere Solo-Entwickler, kleine Selbstständige, Gründer und Menschen, die digitale Projekte mit KI umsetzen möchten, ohne selbst mehrere KI-Werkzeuge koordinieren zu müssen.

Beispielanwendung: Aufbau einer Website bzw. eines digitalen Projekts zur kommerziellen Nutzung. Courier verspricht dabei **keinen wirtschaftlichen Erfolg oder bestimmte Einnahmen**; der Nutzen liegt in automatisierter Projektarbeit und Koordination.

Vor einer endgültigen Preiszusage werden reale Infrastruktur-/KI-Kosten gemessen.

### 8. Solo, LFG und LFM
Courier soll später nicht nur KI-Arbeit koordinieren:
- **SOLO:** alleine mit Courier bauen.
- **LFM:** ein Projekt sucht einen Menschen/eine Fähigkeit.
- **LFG:** eine Person sucht ein Projekt, bei dem sie mitarbeiten kann.

Der Ledger kann dafür zeigen, welche Fähigkeit ein reales Projekt tatsächlich noch benötigt, statt nur allgemeine Stellenanzeigen zu erzeugen.

### 9. Wiederverwendbare Pakete und Community
Aus wiederkehrenden Abläufen — Ausgangsidee war unter anderem eine einfach wiederverwendbare Pipeline — sollen installierbare Courier-Pakete entstehen.

Nützliche, geprüfte Community-Beiträge können die Paketbibliothek erweitern. Als zukünftiger Anreiz ist ein Modell vorgesehen, bei dem akzeptierte wertvolle Beiträge beispielsweise **drei Monate kostenlose Nutzung** ermöglichen können. Bedingungen, Rechte/Lizenzen, Moderation und Missbrauchsschutz werden vor einer verbindlichen öffentlichen Zusage definiert.

### 10. Updates und Sicherheit
Geplant sind häufige, perspektivisch tägliche herunterladbare Verbesserungen. Updates sollen versioniert, authentifiziert/signiert, nachvollziehbar und zurückrollbar sein.

Die Sicherheitsarchitektur soll **crypto-agil** bleiben, damit zukünftige Migration auf standardisierte Post-Quantum-Verfahren möglich ist. „Quantensicher“ wird nicht behauptet, bevor eine entsprechende Implementierung tatsächlich umgesetzt und geprüft wurde.

### 11. Wirtschaftlichkeit durch weniger unnötige KI-Arbeit
Courier soll nicht möglichst viele Agenten beschäftigen, sondern möglichst viel **verifizierte nützliche Arbeit pro Ressourceneinsatz** erreichen.

Später messbar:
- Kosten/Tokens pro verifiziertem Ergebnis,
- unterdrückte Doppelarbeit,
- wiederverwendete Evidenz/Pakete,
- vermiedene unnötige Modellläufe,
- menschliche Eingriffe,
- tatsächlich reconciled/verifizierte Ergebnisse.

Prozentuale Einsparversprechen werden erst nach vergleichbaren Messungen gemacht.

### 12. Aktueller Entwicklungsstand
Die Produktvision, Ledger-Regeln, adaptive Ressourcensteuerung, Kostenanforderungen und Courier-Pocket/Living-Ledger-Oberfläche sind als Anforderungen im Projekt dokumentiert.

Der aktuelle technische Schwerpunkt ist bewusst enger: die Kernkette für Ausführung → Ergebnis → Verifikation → Reconciliation → automatische Fortsetzung reproduzierbar beweisen. Erst danach wird die Pocket-Oberfläche auf den echten Ledger gesetzt.

### 13. Nächste Meilensteine
1. Kernbeweis der autonomen Ausführung und Verifikation abschließen.
2. Zweiten isolierten Wiederanlauf-/Fortsetzungsbeweis durchführen.
3. Kleine read-only Courier-Pocket-Ansicht aus echtem Ledger bauen.
4. „Weggehen und zurückkommen“-Demo aufnehmen.
5. Reale Ressourcen-/Kostenmessung integrieren.
6. Wiederverwendbare Pakete produktisieren.
7. Danach LFG/LFM und Community-Beitragsmodell ausbauen.

### 14. Abgrenzung
Courier Symphony ist derzeit ein Entwicklungsprojekt. Aussagen zu Preis, Einsparungen, Umsatzmöglichkeiten, täglichen Updates und zukünftiger Post-Quantum-Sicherheit sind Ziele bzw. geplante Produktmerkmale, soweit sie noch nicht technisch und wirtschaftlich nachgewiesen sind.

### 15. Förderlogik
Das Vorhaben zielt darauf, aus umfangreicher eigener Entwicklungsarbeit ein verständliches, niedrigschwelliges Softwareprodukt und perspektivisch eine selbstständige wirtschaftliche Tätigkeit aufzubauen. Eine Förderung würde insbesondere helfen, die verbleibende technische Validierung, Produktisierung, Demonstration, Kostenprüfung und Vorbereitung eines marktfähigen Angebots strukturiert abzuschließen.

Der zentrale Unterschied soll für Außenstehende unmittelbar sichtbar werden:

**Der Kunde sieht Ruhe. Courier koordiniert die Komplexität. Der Ledger zeigt, was wirklich angekommen und geprüft ist.**
