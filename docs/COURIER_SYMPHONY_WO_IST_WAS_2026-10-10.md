# 🐦 Courier Symphony — Wo ist was? Gemeinsamer Wegweiser

**Stand:** 10.10.2026 · **Art:** öffentliche, verständliche Orientierung und Übergabe · **Status:** dokumentierte Momentaufnahme, **kein** Vollbackup und **keine** Freigabe für Agentenaktionen.

> **In 30 Sekunden:** Es gibt **ein Produkt Courier Symphony**, aber mehrere getrennte Arbeitsorte. **GitHub speichert versionierte Dateien. Cursor zeigt Projekte und Agenten-Chats. Codex zeigt weitere Arbeitsbereiche/Unterhaltungen. ChatGPT speichert seine eigenen Chats/Projekte.** Gleiche Namen bedeuten **nicht**, dass Inhalte automatisch synchronisiert sind. **Nichts löschen, umbenennen oder zusammenführen, bevor die Herkunft und Sicherung geklärt ist.**

Dieses Dokument soll die immer wieder gestellte Frage **„Was ist was, und wo soll ich weitermachen?“** beantworten. Es ist auf Deutsch, für Nichtprogrammierer geschrieben und trennt bestätigte Fakten von früheren Berichten und offenen Prüfungen.

## 1. Statuskennzeichen

- ✅ **VERIFIZIERT:** durch sichtbare GitHub-Information oder dokumentierten Nachweis belegt; Datum beachten.
- 🟡 **BERICHTET / AUF SCREENSHOT GESEHEN:** aus den bisherigen Gesprächen und Bildschirmfotos; nicht von hier aus live in jeder App überprüfbar.
- ⚠️ **OFFEN:** keine vollständige Inhalts-, Synchronisations- oder Sicherungsprüfung.
- ⛔ **NICHT TUN:** keine implizite Freigabe zum Löschen, Verschieben, Zusammenführen, Neustarten oder Ausgeben von Geld.

**Aktuelle Leitentscheidung:** Bestehende Arbeit behalten und eine **gemeinsame Orientierung** schaffen. Nicht drei GitHub-Repositories physisch in eines kopieren. Nicht behaupten, dass Agenten-Chats automatisch gegenseitig lesbar sind.

## 2. Die drei GitHub-Repositories — was ist was?

| Repository | Aufgabe | Sichtbarkeit (GitHub-Prüfung am 10.10.2026) | Bedeutung |
| --- | --- | --- | --- |
| [`happyhippovip/2026-courier`](https://github.com/happyhippovip/2026-courier) | **Hauptprogramm / Courier-V1-Code** | Öffentlich | Technische Produktentwicklung: Controller, Ledger, Worker, Verifier, Hub, Windows-Auslieferung; V1-Arbeitsziel `integration/v1`. |
| `happyhippovip/2026-project-memory` | **Privates Projektgedächtnis** | Privat | Übergaben, Arbeitsnachweise, Entscheidungen, historische Inventare und wichtige Kontinuität. **Nicht** als öffentliches Datenarchiv behandeln. |
| [`happyhippovip/courier-pilot-website`](https://github.com/happyhippovip/courier-pilot-website) | **Website / öffentliche Darstellung** | Öffentlich | Website-Arbeit getrennt vom Courier-Produktcode. |

**Merksatz:** Programm = `2026-courier`; Gedächtnis = `2026-project-memory`; Website = `courier-pilot-website`.

Das private Gedächtnis ist kein automatisch vollständiges Backup aller lokalen Dateien, ChatGPT-Chats oder Codex-Sitzungen. Die Website ist kein zweiter Courier-Laufzeitkern. Diese Trennung ist **beabsichtigt**.

### Wo steht die technische Wahrheit?

- [`AGENTS.md`](../AGENTS.md): Pflichtregeln für Agenten und sichere Zusammenarbeit.
- [`docs/V1_RULE_0.md`](V1_RULE_0.md): Produktziel, **FINISH THE PRODUCT**.
- [`docs/V1_ORCHESTRATION_PLAYBOOK.md`](V1_ORCHESTRATION_PLAYBOOK.md): bestehende Rollen und Entwicklungskoordination.
- [`docs/V1_WINDOW_CUSTODY_PROTOCOL.md`](V1_WINDOW_CUSTODY_PROTOCOL.md): alte Sitzungen nicht blind schließen oder überschreiben.
- [`docs/NEXT_CHAT_HANDOFF.md`](NEXT_CHAT_HANDOFF.md): Einstieg für einen neuen Entwicklungs-Chat.
- [`docs/v1/INTEGRATION_LOG.md`](v1/INTEGRATION_LOG.md): nachgewiesene Integrationsschritte, nicht bloß Versprechen.

**Nur L1 integriert nach `integration/v1`.** Es gibt genau sechs V1-Writer-Lanes L1–L6, keinen neuen parallelen Scheduler, keine selbstständigen Zahlungen (`AUTONOMOUS_SPEND_LIMIT_EUR=0`). Für den Mac galt zuletzt Ressourcenpause; **aktueller Host-Zustand muss vor jeder Ausführung neu überprüft werden**.

## 3. Drei Codex-Bereiche in der Oberfläche — NICHT drei neue GitHub-Produkte

Die Namen wurden in Codex-Bildschirmfotos und einer am 10.10.2026 bereits vorhandenen privaten Bestandsaufnahme erfasst.

| Codex-Eintrag / lokaler Bezug | Was er bedeutet | Jetzt tun |
| --- | --- | --- |
| **`2026-Projektzentrale`** | Älteres **Projektregister/Archiv mit historischer Agentenarchitektur und verschiedenen Projekten**; nach damaliger lokaler Inventur **kein eigenes Git-Root**. Enthält auch eigenständige Arbeiten außerhalb Courier. | **Behalten.** Nicht als „erledigt“ markieren und nicht vollständig nach Courier kopieren. |
| **`2026-courier`** | Der Bereich des Courier-Hauptprogramms; der damalige Mac-Einstieg führte in einen Checkout des Haupt-Repositories. | **Technische Hauptreferenz**, aber Branch, lokale Änderungen und Owner vor Schreibarbeit prüfen. |
| **`Downloads`** | Auf dem Mac ein **übergeordneter Sammelordner** mit unterschiedlichen lokalen Arbeitsständen, Archiven und Projekten; **kein einheitliches Git-Repository**. | **Nur inventarisieren.** Nicht den gesamten Ordner als Duplikat löschen oder zu Courier migrieren. |

**Achtung:** Ein gleichnamiger Eintrag in Codex, Finder, Cursor oder ChatGPT ist nicht automatisch dasselbe Objekt. Ein Codex-Chat unter „Downloads“ kann trotzdem Courier-relevante Arbeit enthalten. Der Titel allein beweist weder einen aktiven Prozess noch einen gesicherten Commit.

Ein vorhandenes internes Inventar vom 10.10.2026 dokumentiert weitere lokale Worktrees, Stashes, uncommittete Änderungen und historische Archive. Es wurde **nicht** vollständig abgeglichen und bleibt im privaten Gedächtnis. Diese öffentliche Übersicht ist **kein** Freibrief, alte Ordner aufzuräumen.

## 4. Cursor — App, Fenster, Repositories, Agenten-Chats

### Die zwei Fenster sind dieselbe App

- **Agents Window:** die vertraute Oberfläche mit **New Chat**, **Search**, **Automations**, **Customize**, **Projects** und den bisherigen Agentenunterhaltungen.
- **Editor Window:** Dateiliste links, Code in der Mitte, Terminal unten, gegebenenfalls `New Agent` rechts.

Am **10.10.2026** wurde auf dem Mac die zuvor vermisste Agents-Oberfläche tatsächlich wieder geöffnet. **Bestätigter Bedienweg auf dem damaligen Mac: `⌘ Command + ⌥ Option + N` im Cursor-Editor.** Das war **eine Fenster-/Oberflächenlösung, keine Repository-Reparatur**. Kein Code musste dafür gelöscht oder neu installiert werden.

In der Cursor-Agents-Projektliste erschienen die **drei GitHub-Repositories** `2026-courier`, `2026-project-memory` und `courier-pilot-website`. Darunter stehen viele ältere Unterhaltungen/Tasks. **Die Zuordnung in der Seitenleiste bedeutet nicht, dass alle Chats gegenseitig synchronisiert oder sämtliche Ergebnisse committed sind.**

**Cursor-Zielbild:** ein erkennbares „Courier Symphony“-Arbeitsgefühl und eine zentrale Navigation, **ohne** das technische Programm, das private Gedächtnis und die Website physisch zu vermischen. Ob die aktuell installierte Agents-Oberfläche ältere Chats projektübergreifend vereinen kann, ist **nicht verifiziert**.

## 5. ChatGPT — Gesprächsprojekte sind keine Git-Ordner

In den bisherigen Bildschirmfotos/Gesprächen wurden ChatGPT-Projektbezeichnungen genannt, darunter:

- **`2026 – Export Courier Symphony`** — früher genannter Sammel-/Exportbereich für Courier-Gespräche;
- **`Downloads`** — so benannter ChatGPT-Bereich in einer früheren Übersicht; **nicht** mit dem macOS-Downloads-Ordner gleichsetzen;
- **`Windows – Courier Symphony My Projekt`** — früher genannter Gesprächsbereich für Windows-bezogene Courier-Arbeit.

🟡 **Status dieser Namen:** aus früheren Unterhaltungen/Bildschirmfotos berichtet; **heutige vollständige ChatGPT-Projektliste und Zuordnung wurden nicht direkt aus dem Konto inventarisiert**. Deshalb weder als vollständige Liste noch als sichere Speicherorte jedes Chats ausgeben.

**ChatGPT-Projekte enthalten Chats, Anweisungen und gegebenenfalls Projektdateien; sie sind kein Git-Repository und kein vollständiger Sicherungsnachweis des Programmcodes.** ChatGPT, Codex und Cursor teilen ihre Gesprächsverläufe **nicht automatisch vollständig**. Ein zentraler Chat kann bekannte Ergebnisse erklären, aber fehlende Chats nicht herbeizaubern.

**Künftig:** In einem bestehenden Courier-Chat beginnen, auf diesen Wegweiser und die aktuellen offiziellen Dateien verweisen, dann **nur fehlende Informationen** prüfen. Keine neuen „Projektzentralen“ auf Verdacht anlegen und keine alten Chats unkontrolliert verschieben.

## 6. Grok — die eigenständige APP (nicht Word)

**Korrektur ausdrücklich festgehalten:** Gemeint ist **Grok als eigene App**, **kein Grok-Word-Dokument** und nicht automatisch der Grok-Modellwähler in Cursor.

In einem Grok-iPhone-Screenshot vom 10.10.2026 wurden links die Punkte **Automatisierung**, **Projekte** und **Grok Bot** sowie **angeheftete Chats** sichtbar. Ihre Themen waren **Windows-Recovery**, **MacBook-Recovery**, **gemeinsame Windows+Mac-Recovery** und ein **Courier-Symphony-Masterplan**.

**Das heißt:** Grok hat eigene, sichtbare Chats und eine eigene Projekt-Navigation. Ein angehefteter Grok-Chat ist **kein GitHub-Commit**, kein Cursor-Task und kein Beweis, dass ChatGPT oder Codex ihn automatisch kennen. Auch eine ältere Integration oder ein Draft-PR belegt noch **keinen laufenden gegenseitigen Gedächtnis-Sync**. Ob Grok private GitHub-Dateien lesen/schreiben darf, muss pro tatsächlicher Verbindung geprüft werden.

**Schutz:** Für Grok und andere Tools denselben **öffentlichen Wegweiser** als erste Lesequelle nutzen. Ausführliche Chat-Titel, private lokale Bestandsaufnahmen und Kontodaten gehören nur ins **private** Memory, sofern der konkrete Dienst berechtigt darauf zugreifen kann. Neue Assistenten sollen den gelesenen Pfad explizit bestätigen, bevor sie behaupten, mit dem Gesamtstand vertraut zu sein.

### Private detaillierte Ergänzung

Im privaten Repo liegt der datierte Bericht `memory/COURIER_CROSS_APP_STATUS_AND_HANDOFF_2026-10-10.md`. Er trennt für **Cursor, Grok-App, ChatGPT, Codex, GitHub sowie Mac/Windows**: gesehenen UI-Stand, historische Git-/Datei-Nachweise, noch ungesicherte Chat-/Worktree-Inhalte, Sicherheitsregeln und nächste Lesepfade. **Nur für berechtigte Zugriffe**; nicht in dieses öffentliche Dokument kopieren.

## 7. Mac und Windows — gleiche Firma, verschiedene Aufgaben

| Ort | Rolle | Besonderheit |
| --- | --- | --- |
| **MacBook / Cursor / Muse / Antigravity** | Planung, Orientierung, lesende Prüfung und ausgewählte Arbeiten nach Ressourcenfreigabe | Historisch hoher RAM-/Swap-Druck und Ressourcenpause. Nicht mehrere schwere Prozesse starten oder unbekannte Sitzungen überschreiben. |
| **Windows-Laptop / Cursor und Worker-Umgebung** | Windows-spezifische Tests, Worker, Installer/EXE-Prüfung und weitere zugewiesene Arbeit | Ein Windows-Erfolg ist kein Beweis, dass derselbe Schritt auch auf dem Mac funktioniert. |
| **GitHub** | Versionierte Projektdateien, geprüfte Commits, PRs und dokumentierte Nachweise | Ein Remote-Commit ist **kein** Backup uncommitteter lokaler Dateien, anderer Worktrees oder Chatverläufe. |
| **ChatGPT/Codex** | Planung, Besprechungen, Codex-Tasks und Übergaben | Verlauf und Aufgaben pro Oberfläche unterscheiden; die App-Limits sind kein Beweis für den Projekt-/Backupstatus. |

## 8. Was ist wirklich gelöst, was noch offen?

| Thema | Nachweisstatus am 10.10.2026 |
| --- | --- |
| Cursor-**Agents Window auf dem Mac** wieder sichtbar | ✅ **GELÖST** (durch Tastenkombination bestätigt) |
| Die **drei GitHub-Repositories existieren** | ✅ **GITHUB VERIFIZIERT**; Hauptrepo + Website öffentlich, Gedächtnis privat |
| Funktion der Repositories eindeutig beschrieben | ✅ **IN DIESEM DOKUMENT ERKLÄRT** |
| Codex-`2026-Projektzentrale`, `2026-courier` und `Downloads` grundsätzlich zugeordnet | 🟡 **HISTORISCHER QUELLENABGLEICH**; keine Vollinventur aller Chats |
| Sämtliche **Codex-Agenten-Chats** geprüft/zusammengeführt | ⚠️ **OFFEN** |
| Alle **ChatGPT-Projektchats** geprüft/vereinigt | ⚠️ **OFFEN** |
| **Grok-App:** angeheftete Recovery-/Masterplan-Chats sichtbar | 🟡 **SCREENSHOT**; nicht automatisch synchronisiert oder exportiert |
| **Grok↔Cursor↔ChatGPT** dauerhafter Live-Sync | ⚠️ **NICHT NACHGEWIESEN** |
| Alle lokalen Änderungen, Worktrees, Stashes und Archive gesichert | ⚠️ **OFFEN** |
| **V37**-Einzelsicherung (Patch/Bundle) | 🟡 **FRÜHERER NACHWEIS** einer Teil-Sicherung; **kein Gesamtbackup** |
| Doppelte Arbeit vollständig erkannt und beseitigt | ⚠️ **OFFEN**, nicht einfach aus ähnlichen Namen ableiten |
| Kontingent-/Abrechnungsfragen bei externen KI-Tools | ⚠️ **GETRENNTER PRIVATER SUPPORTVORGANG**; keine persönlichen Abrechnungsdaten in dieses öffentliche Repo |

**Wichtig:** Weder „100 % gesichert“ noch „alles doppelt“ noch „alle Agenten liefen“ ist aktuell belegt. Statusmeldungen sind keine Git- und Backup-Beweise.

## 9. Unsere vereinbarte Art zusammenzuarbeiten

- **Deutsch, verständlich, präzise.** Keine unnötigen Fachwörter; Fachwörter kurz erklären.
- **Genau EIN nächster Schritt** pro Bildschirmfoto/Fehler; danach Rückmeldung abwarten.
- Erst **Was ist passiert? → Was ist verifiziert? → Was ist unbekannt? → Was ist der nächste sichere Schritt?**
- Kennzeichnungen: 🍎 Mac/Ressourcen · 🔨 Reparatur · 😎 Fortschritt · 🕶️ Koordination · 🧪 Test · ⚗️ Optimierung · 🤖 Agent · 🐦 Courier · ✅ überprüft · ⚠️ Risiko · 🔴 Blocker · 💶 Kosten.
- Nutzer kopiert Agenten-Anweisungen oft **sofort** in bezahlte Tools. Deshalb **keine direkt ausführbaren oder teuren Prompts ohne eindeutige Freigabe**, keine versteckten Nebentasks und keine Prompt-Flut.
- **Keine Ausgaben ohne ausdrückliche Zustimmung.** Keine neuen Abos, API-Kosten, Agenten-Schwärme oder automatischen Käufe.
- Nicht gleichzeitig in demselben Bereich schreiben; keine Git-Resets, Stash-Anwendungen, Workspace-Bereinigung, PR-Merges, Löschungen oder Kontenänderungen ohne explizite Freigabe und Sicherungsnachweis.
- **Nur dokumentieren, was wirklich geschehen ist.** `VERIFIED`, `REPORTED`, `PLANNED`, `UNKNOWN` unterscheiden.
- Nur echte Fortschritte an Courier priorisieren. **Nicht erneut von null anfangen.**

## 10. Sicherer Ablauf für die spätere Konsolidierung

1. **Bestehende Bereiche erhalten.** Namen in Cursor/Codex/ChatGPT und die lokalen Ordner nicht vorschnell ändern.
2. **Vorhandene Inventare lesen** und ihren Datumsstand berücksichtigen. Der private Mac-Workspace-Bericht vom 10.10.2026 ist eine wichtige historische Quelle, nicht automatisch Live-Wahrheit.
3. **Jede wichtige Unterhaltung / Datei / Änderung einmal erfassen:** Ursprung, Plattform, Repository oder Chat-Projekt, Status, Beleglink, noch nicht gesicherter Inhalt, zuständiger Owner.
4. **Sicherung zuerst:** Git-Historie, lokale uncommittete Dateien, Stashes/Worktrees und Chatverläufe sind unterschiedliche Sicherungsgegenstände.
5. **Duplikate nur anhand von Inhalten/IDs nachweisen**, nicht anhand gleicher Namen; widersprüchliche Versionen erhalten bis zur Klärung.
6. **Gemeinsame Navigation statt Datenvermischung:** dieses Dokument ist der öffentliche Einstieg; ausführliche private Verläufe gehören ins private Projektgedächtnis.
7. **Nachweis vor „ERLEDIGT“:** Nur bewiesene Lösungen so markieren; aktuelle Prozess-/Provider-Zustände jeweils neu prüfen.

Dieser Ablauf ist ein **Plan**, keine Autorisierung zum Ausführen oder Verschieben.

## 11. Datenschutz und Veröffentlichungsgrenze

**Hier öffentlich erlaubt:** Namen und Zweck öffentlich erkennbarer Repositories, grobe Tool-Rollen, Statusunterschiede, freigegebene Arbeitsweise und bekannte UI-Lösung.

**Hier NICHT öffentlich abgelegt:** private Repo-Inhalte, vollständige lokale Dateilisten/ungesicherte Diffs, Chat-Transkripte, Support-Ticketnummern, Rechnungen, Bank-/Kontodaten, E-Mail-Adressen, Credentials, Tokens, Gesundheits-/Familiendetails, private Geschäftsunterlagen und ungeprüfte Spekulationen über technische Schuld.

Die Veröffentlichung dieses Wegweisers **verschiebt, synchronisiert oder exportiert nichts** aus Cursor, Codex oder ChatGPT.

---

### Kurzreferenz zum Kopieren in *neue* Gespräche (keine Ausführungsanweisung)

**„Mein Projekt heißt Courier Symphony. Grok ist die GROK-APP (nicht Grok Word). Bitte lies zuerst `docs/COURIER_SYMPHONY_WO_IST_WAS_2026-10-10.md` im öffentlichen Repo `happyhippovip/2026-courier`, beachte `AGENTS.md` und überprüfe den aktuellen Zustand. Meine drei GitHub-Repositories sind Hauptprogramm, privates Gedächtnis und Website. Codex-`2026-Projektzentrale` ist historische Arbeitsablage, Codex-`Downloads` ist keine eigene App-Architektur. Cursor-Agenten-Chats und ChatGPT-Chats sind nicht automatisch synchronisiert. Bitte antworte verständlich auf Deutsch, mit einem sicheren Schritt und ohne selbstständig Kosten oder Dateiänderungen auszulösen.“**

**Fortschreiben:** Dieses Dokument darf durch einen neuen, datierten und belegten Bericht ergänzt werden, nicht durch das Überschreiben ungeprüfter Altdaten. Produkt-/Integrationsregeln bleiben in den oben verlinkten kanonischen Dateien maßgeblich.
