# MASTER — Dennis zuerst

Stand: 21.09.2026, gelesen ca. 05:10 MESZ. Alles mit BELEGT hat Claude nur gelesen, nichts wurde geändert.

## Ablauf pro Chat (deine Methode)

1. MASTER_01_Briefing_an_alle.txt an den Chat schicken. Nichts anderes.
2. Rollenbestätigung prüfen (höchstens 6 Zeilen). Sie stimmt nur, wenn alle fünf Punkte richtig sind: Rolle, erlaubter Bereich,
   Verbote genannt (kein reset --hard, kein Force-Push, keine fremden Prozesse, keine fremden Änderungen), Antwortformat mit
   START_SHA und END_SHA, und er wartet auf den Auftrag statt selbst loszulaufen.
   Beispiele für falsch: Muse sagt, er darf auch den Ledger reparieren. Google sagt, er fängt schon mit AWS an.
   Codex sagt, er baut den Fix selbst.
3. Erst danach der Auftrag: MASTER_10_Google.txt, MASTER_20_Muse.txt, MASTER_30_Codex.txt (Codex erst, wenn Google fertig ist).
   MASTER_02_Statuspaket_nur_lesen.txt ist optional für die Windows-Instanz von Muse und für Google, wenn du wissen willst, was dort liegt.
   ChatGPT bekommt statt eines Agenten-Auftrags MASTER_03_ChatGPT_Lotse.txt: Er führt dich Schritt für Schritt, kennt deine Rechner aber nicht.
   Jeder Schritt braucht deinen Beweis (Screenshot oder Text). Seine Rollenbestätigung stimmt, wenn er sagt: sieht nur, was du zeigst,
   hat keine Autorität über den Repo-Zustand, wartet auf den Auftrag.
4. Antworten hierher, mit den drei Zeilen VON / AUFTRAG / ZEIT darüber. Ich vergleiche mit deinen acht Punkten und gebe je Antwort
   ANNEHMEN, NACHBESSERN oder VERWERFEN, mit Grund, dazu: wer bekommt welche Aufgabe, welcher Beleg fehlt, was entscheidest nur du.

## Was ich am Briefing geändert habe

1. Antwortformat: Es fehlten Branch, START_SHA und END_SHA. Dein Vergleichspunkt 1 braucht sie. Ergänzt.
2. SHA-Hard-Stop fehlte. Er steht jetzt als Regel 0, vor "Ein Schreiber pro Ordner".
3. Muse: Dein Briefing nennt Muse New 2026 auf Windows. Die uncommitteten Cannon-Änderungen liegen aber im Mac-Ordner.
   Es darf nur EINEN Cannon-Schreiber geben. Der Auftrag setzt den Mac als Standard.
4. Claude: "hat keinen Repo-Zugriff" stimmte in dieser Sitzung nicht. Ich konnte den Mac-Ordner lesen (auf deine Freigabe).
   Jetzt steht: liest nur, was Dennis freigibt, schreibt nie.
5. Google: Seine Dauerregel (.agents/rules/00-courier-autonomy.md, "KEEP WORKING") kann "Warte auf den Auftrag" überstimmen.
   Deshalb steht bei JETZT ein Satz, dass Warten ein gültiger Stop-Grund ist.
6. Außerdem: STAND mit den gelesenen Fakten aktualisiert, "Lob ist kein Beleg" in Regel 2, AWS- und Sicherheitseinstellungen sowie Merges bei Dennis.
   Deine acht Vergleichspunkte habe ich nicht geändert.

## Was gerade Sache ist

1. BELEGT: Auf GitHub steht der Integrationsbranch weiter auf 71b3dc06 (= PR39, Draft). main steht auf 3e2fe24d.
2. BELEGT: Dein Mac-Ordner ~/Downloads/2026-courier steht auf 6ca172ac ("known-good 1-10") und liegt 16 Commits vor dem Integrationsbranch.
   Diese 16 sind auf GitHub als Branch known-good/1-10-working-2026-09-19 und als Tag courier-1-10-working-2026-09-19 gesichert.
   Dein Rettungspunkt ist sicher.
3. BELEGT: Einer dieser Commits (80656278, "Trust Root Env Bypass") liegt in Googles Bereich (Ledger/Guard/Motor). Wer ihn geschrieben hat, ist UNKNOWN.
   Google entscheidet, ob er übernommen wird; Codex prüft.
4. BELEGT: Uncommittet liegen dort Muses Cannon-Zähler (5 Dateien geändert, 4 neu) und Laufzeitdaten. Im Ledger stehen 26 neue Einträge
   "Global-Stop", alle UNKNOWN, zuletzt 03:25 Uhr. Ein Courier-Prozess schreibt dort gerade (05:09 Uhr).
5. BELEGT: scripts/cannon_motor.py enthält _admit_local_fake und REAL_MUSE, und bei leerer Queue wartet der Motor absichtlich ("no filler work").
   Googles Bug-Behauptung dazu ist BEHAUPTET, bis ein roter Test sie zeigt.
6. BELEGT: Ein schneller Suchlauf nach Schlüsselmustern im getaggten Stand hatte keine Treffer. Das ist kein vollständiger Scan.
7. UNKNOWN: Windows-PC, Googles eigener Ordner, und ob die Tests heute grün sind (Muse sagt 22 von 24, das ist BEHAUPTET).

## Deine Schritte nebenher

1. **Browser zurückholen.** In Chrome Cmd+Shift+T drücken. Das öffnet das zuletzt geschlossene Fenster mit allen Tabs. War es nur ein Tab, noch einmal drücken.
   Alternativ: Menü Verlauf, dann Kürzlich geschlossen. Laut Muses Protokoll waren im geschlossenen AWS-Fenster: Förderaufruf, Claude, Yahoo-Suche,
   CloudShell und die AWS-Anmeldung. Ich habe hier keine Computersteuerung und kann das nicht für dich tun.

2. **AWS-Regel (nur du, etwa 2 Minuten).** Ich ändere keine Sicherheitseinstellungen und melde mich nirgends an. Ich prüfe danach dein Ergebnis.
   Du kannst die Schritte selbst gehen oder dich von ChatGPT führen lassen (MASTER_03). Den Nachher-Screenshot zeigst du in jedem Fall auch mir.
   1. In der AWS-Konsole anmelden, oben rechts die Region Frankfurt (eu-central-1) wählen.
   2. EC2, dann Security Groups, dann courier-sg (ID sg-069e6db48544f9543) öffnen. Reiter "Inbound rules". Jetzt Screenshot machen (VORHER), erst danach "Edit inbound rules".
   3. Die vorhandene Regel NICHT anfassen: SSH, TCP, Port 22, Quelle 79.218.46.116/32.
   4. "Add rule": Type SSH. Bei Source ins Feld klicken, "ec2-instance-connect" tippen und die Prefix List
      com.amazonaws.eu-central-1.ec2-instance-connect wählen (laut Muses Protokoll pl-03384955215625250).
      Description: EC2 Instance Connect Frankfurt.
   5. Vor dem Speichern prüfen: genau 2 Zeilen; Zeile 1 unverändert; kein 0.0.0.0/0, kein ::/0, keine leere Zeile, kein Port 0.
   6. "Save rules". Seite neu laden: wieder genau 2 Regeln?
   7. Screenshot NACHHER an mich (mir darfst du die IP zeigen, ich kenne sie; ChatGPT zeigst du sie abgedeckt).
      Danach nichts weiter (kein EC2-Connect-Test, kein IAM, kein SSM).
   Unsicher oder sieht etwas anders aus? Nichts speichern, Screenshot an mich.

## Standardentscheidungen (schon eingetragen, sag nur, wenn du es anders willst)

- Google arbeitet ab 71b3dc06 auf dem Integrationsbranch, in einem eigenen Ordner, nicht im Muse-Ordner.
- Muse ist der einzige Cannon-Schreiber, auf dem Mac. Die Windows-Instanz liest nur. Dein Briefing nennt für Windows die offenen Punkte
  Live-Ansicht, Logo, Start/Stop und Modulfehler "cannon". Mein Muse-Auftrag deckt nur den Mac-Zähler ab. Soll die Windows-Instanz zuerst dran sein,
  schreibe ich ihren Auftrag, nachdem das Statuspaket zurück ist.
- Muse pusht nichts. Push später nur nach deinem GO in einen neuen Branch muse/cannon-counter-2026-09-21.
- Google entscheidet über die 16 Mac-Commits (Scope-Owner), Codex prüft. Nichts wird blind gemergt.
- scripts/cannon_motor.py gehört vorerst Muse (Cannon). Google ändert dort erst etwas, wenn er den Befund mit einem roten Test belegt
  und du die Besitzfrage entschieden hast.
- Begrenzte Sitzung: Jeder Agent liefert nach seinen Punkten das Antwortformat und stoppt. Willst du Dauerlauf, streiche in der Auftragsdatei den
  Regelpunkt 5 "BEGRENZTE SITZUNG". Dann gilt Googles Regel "KEEP WORKING".

## Was dieser Lauf schafft und was nicht

Schafft, wenn es belegt wird: Gate 1 (Ledger-Vertrauen: vier Befunde, neun Punkte), Cannon-Zähler mit Tests und lokalem Commit,
Klärung der 16 Mac-Commits, AWS-Regel gespeichert und von mir geprüft.

Schafft nicht: die physische Windows-Abnahme (Human + Google, später), Live-Muse, Startpaket, Updater, Medaillen, Community, Login, Zahlungen.
Ein Prompt kann nicht garantieren, dass alles fertig wird. Er sorgt nur dafür, dass jeder Punkt entweder belegt oder als UNKNOWN gemeldet wird.
Die neun Gate-1-Punkte stammen aus Codex' Aufzählung, nicht aus dem Repo.
