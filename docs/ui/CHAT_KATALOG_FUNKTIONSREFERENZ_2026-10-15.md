# Courier Symphony – funktionierende Chat-Katalogansicht (eingefrorene Referenz)

**Datum:** 2026-10-15. **Status:** Nutzer bestätigt: Bedienung funktioniert für TRAUM-0004 bis TRAUM-0020 in der Chat-Nachricht. **Scope:** 17 Einträge, nicht 3000 geladene Volltexte. **Repository:** öffentliches 2026-courier, isolierter Dokumentationsbranch; kein Merge.

## Nicht verändern: bestätigtes Bedienverhalten
- Pfeile **Zurück** und **Weiter** navigieren per `DIL.useState` innerhalb **derselben Chat-Nachricht**. Kein `issueNewTurn` bei Bereichsende.
- Aktive Navigation 4–20; Pfeile werden nur an den echten Grenzen deaktiviert.
- Nummernsprung 4–20, **Öffnen**.
- **Kopieren** direkt über dem Prompt, kopiert `full` mittels `GenUI.copy(full)` und zeigt danach **Kopiert**.
- Prompt-Volltext in scrollbarem Bereich, mobil gut lesbar.
- Sicherheitsstatus PLAN_ONLY. **Kein** Agentenstart, kein Queue-Refill, keine zusätzlichen Kosten.

## Vollständiger Referenzquelltext der funktionierenden Chat-Ansicht
Die folgende DIL-Vorlage ist zur **Wiederherstellung durch ChatGPT im Chat** gedacht, nicht als HTML-Datei oder ausführbarer GitHub-Quellcode. Der Quelltext wurde aus der unmittelbar vom Nutzer bestätigten Chat-Nachricht übernommen.

~~~text
{@body const phases=["Zustandsmodell","Sicherheitsprüfung","Prüfplan","UI- und Bedienkonzept","Integrationsentwurf","Kosten- und Betriebsplan","Abnahme- und Übergabepaket","Quelleninventur","Risikoanalyse","Vertragsspezifikation"]}
{@body const instructions=["Beschreibe zulässige Zustände, Übergänge, Idempotenz, Lease-Grenzen und unzulässige Übergänge.","Leite ein Threat Model für diesen Teilbereich ab, ohne produktive Systeme zu verändern.","Definiere unabhängige Abnahme, Testfixtures und Evidenzanforderungen, ohne Tests auszuführen.","Entwirf eine operatorfreundliche Darstellung, die UNKNOWN, Quellenvertrauen und Sperren ehrlich zeigt.","Bestimme Ein- und Ausgänge, bestehende Schnittstellen, Migrationsrisiken und Konflikte mit geschützten PRs.","Vergleiche Premium- und Economy-Eignung, Quotenrisiko, Hostlast und zulässige Laufzeit.","Erstelle ein konsistentes, nachprüfbares Übergabepaket für unabhängige Prüfer und späteren Owner.","Ermittle ausschließlich vorhandene Quellen, Versionsanker und widersprüchliche Aussagen. Gib je Fund Datei, Zeile oder UNKNOWN an.","Untersuche konkrete Fehlermodi, Dubletten, Berechtigungsgrenzen und Auswirkungen auf Kolibri sowie Windows-EXE.","Formuliere einen minimalen überprüfbaren Datenvertrag einschließlich Eingaben, Ausgaben, Pflichtfeldern und fail-closed Verhalten."]}
{@body const deliveries=["Zustandsübergangstabelle und mindestens drei negative Gegenfälle.","Threat-Matrix mit Trust Boundaries und mindestens fünf überprüfbaren Negativfällen.","Mindestens fünf messbare Acceptance Criteria mit Soll- und Fehlersignal.","Ansichtsspezifikation mit Leer-, Fehler- und Konfliktzustand.","Integrationskarte mit Abhängigkeiten und expliziten Nicht-Zielen.","Budget- und Kapazitätsplan mit UNKNOWN statt erfundener Zahlen.","Checkpoint mit Quellen, offenen Entscheidungen, Owner/Lease UNKNOWN und Freigabegate.","Quellenmatrix mit VERIFIED/REPORTED/UNKNOWN und mindestens einer offenen Beweisfrage.","Risikoregister mit Auslöser, Schaden, Nachweis, Schwere und Schutzmaßnahme.","Versionierter Vertragsentwurf mit Beispielen für gültige und ungültige Daten."]}
{@body const allPhases=["Quelleninventur","Risikoanalyse","Vertragsspezifikation",...phases.slice(0,7)]}
{@body const allTasks=[instructions[7],instructions[8],instructions[9],...instructions.slice(0,7)]}
{@body const allDeliveries=[deliveries[7],deliveries[8],deliveries[9],...deliveries.slice(0,7)]}
{@body const [index,setIndex]=DIL.useState(4)}
{@body const [jump,setJump]=DIL.useState("4")}
{@body const [copied,setCopied]=DIL.useState(false)}
{@body const id="TRAUM-"+String(index).padStart(4,"0")}
{@body const topic=index<=10?"Task-Routing":"Worker-Admission"}
{@body const phase=allPhases[(index-1)%10]}
{@body const task=allTasks[(index-1)%10]}
{@body const delivery=allDeliveries[(index-1)%10]}
{@body const full=`COURIER SYMPHONY – KATALOGENTWURF ${id}\nProduktlinie: Agenten-Orchestrierung. Fachthema: ${topic}. Phase: ${phase}.\nAuftrag: Entwickle für den Teilbereich „${topic}“ innerhalb der Produktlinie „Agenten-Orchestrierung“ eine eigenständige ${phase.toLowerCase()} im Kontext von Courier Symphony. ${task}\nBeziehe die vorhandenen Produktziele (Kolibri, überprüfbare Übergaben, unabhängiger Verifier, Windows-EXE) nur ein, wo sachlich relevant. Trenne Ist-Code, Agentenmeldung, Annahme und offenen Befund. Prüfe Überschneidungen mit bestehenden Originalen und PRs; ohne Quellenzugriff nichts als verifiziert ausgeben.\nErwartete Lieferung: ${delivery}\nPflichtfelder: Quellenpfad/Zeile/Commit oder UNKNOWN; Risiken; Abhängigkeiten; Akzeptanzkriterien; Kosten-/Ressourcenstatus; Owner/Lease nur mit Beleg; nächster sicherer Schritt.\nGrenzen: PLAN_ONLY; keine Prozesse, Tests, Commits, PRs, Downloads, API-Kosten, Datenbankänderungen oder Queue-Refill. Mac-Freeze und geschützte Bereiche respektieren. Kein produktiver Workkey.\nAbschluss: Kompakter prüfbarer Checkpoint; ohne gesondertes GO keine Folgeaufgabe.`}
<box border radius="2xl" padding={3} gap={3}>
  <row align="center" justify="between">
    <box gap={1}>
      <text color="secondary" weight="medium" size="xs">COURIER SYMPHONY · KATALOGANSICHT</text>
      <title size="lg">Traumkatalog 3000</title>
    </box>
    <badge>PLAN_ONLY</badge>
  </row>
  <row align="center" justify="between" gap={2}>
    <button color="secondary" disabled={index===4} onClick={()=>{setIndex(v=>Math.max(4,v-1));setCopied(false)}}><icon name="chevron-left"/> Zurück</button>
    <box align="center" gap="1px">
      <title size="lg" tabularNums>{index} / 3000</title>
      <caption>Bereich 4–20 geladen</caption>
    </box>
    <button color="primary" disabled={index===20} onClick={()=>{setIndex(v=>Math.min(20,v+1));setCopied(false)}}>Weiter <icon name="chevron-right"/></button>
  </row>
  <row align="center" gap={2}>
    <box flex="1" gap="1px">
      <label>Direkt zu einer Nummer (4–20)</label>
      <input size="lg" value={jump} onChange={setJump} placeholder="z. B. 17"/>
    </box>
    <button color="secondary" disabled={!Number.isInteger(Number(jump))||Number(jump)<4||Number(jump)>20} onClick={()=>{setIndex(Number(jump));setCopied(false)}}>Öffnen</button>
  </row>
  <divider color="subtle"/>
  <row align="center" justify="between" gap={2}>
    <box flex="1" gap="1px">
      <title size="lg">{id}</title>
      <caption>{topic} · {phase}</caption>
    </box>
    <button color="secondary" onClick={()=>{GenUI.copy(full);setCopied(true)}}><icon name={copied?"check":"copy"}/> {copied?"Kopiert":"Kopieren"}</button>
  </row>
  <box background="surface-secondary" radius="lg" padding={3} height="390px" scrollable>
    <text preserveWhitespace size="sm">{full}</text>
  </box>
  <row align="center" justify="between">
    <caption>Volltext · nicht zur Ausführung freigegeben</caption>
    <text color="secondary" size="xs" tabularNums>{index-3} von 17</text>
  </row>
</box>
~~~

## Wiederherstellungsprompt (kopieren)

> Öffne den Courier-Symphony-Traumkatalog **direkt im Chat** in der am 15.10.2026 vom Nutzer bestätigten, funktionierenden Ansicht. Quelle: `docs/ui/CHAT_KATALOG_FUNKTIONSREFERENZ_2026-10-15.md` im Repository `happyhippovip/2026-courier`, Branch `docs/chat-katalog-funktioniert-2026-10-15`. Verwende die dort dokumentierte DIL-Komponente als unveränderte Bedienreferenz: echte Zurück/Weiter-Pfeile im selben Chat, ID und Zähler, Nummernsprung, Volltext im scrollbaren Feld, Kopieren rechts oben. Kein externer Link statt der Chat-Ansicht. Die Referenz enthält 17 navigierbare Einträge (4–20), nicht 3000 geladene Volltexte. Für eine Erweiterung echte Katalogdaten laden und erst dann höhere Reichweite behaupten. PLAN_ONLY, keine produktiven Aktionen.

## Desktop-Übergabe an Grok (noch nicht ausgeführt)
Der Grok-Agent soll erst nach gesonderter lokaler Freigabe die Datei in **vorhandene, belegte** Grok-Ordner auf Windows und Mac kopieren, ohne Dateien zu überschreiben. Windows-/Mac-Pfade, Leases und Ressourcenstatus sind UNKNOWN; MAC_RESOURCE_PAUSED und Datenrettung haben Vorrang. GitHub-Datei ist die wiederauffindbare Referenz, keine automatische Desktop-Synchronisation.

## Abnahmekriterien für Erweiterung
1. Verhalten 4–20 bleibt unverändert.
2. Für 1–3000: **alle tatsächlichen Prompt-Volltexte** sind im UI verfügbar, ohne neue Chat-Nachrichten oder Datenverlust.
3. Zähler und geladenes Datenvolumen werden nicht verwechselt.
4. Kopieren kopiert stets den ausgewählten Volltext.
5. Kein stiller Wechsel in externen Browser, HTML-Datei oder Download.
