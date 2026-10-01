# M9 — NEXT_PHASE_CONVERGENCE (Muse 9)

Stand: 2026-09-28. Synthese aus UA-A01..J01 + M1..M8. Kein neues Gate-Urteil.

## Konvergierte Lage (ein NEXT, Rangfolge)
NEXT_GLOBAL = `MAC_CANARY_DECISION` (Owner: Mensch/Mac-Operator).
Begruendung: Alle physischen Beweise (RUN_1/2, Restart, Metriken) haengen an
dieser Entscheidung; alles andere ist Prep und darf sie nicht ueberholen.

Rangfolge dahinter (strikte Ordnung, keine Parallel-Tore):
1. `MAC_CANARY_DECISION` — wer startet was auf welchem Mac-Host (vgl. UA-B01).
2. `RUN_CHAIN_REPAIR` — M7.1/M7.2 + M8.1–M8.3 als Text-Entwuerfe (Owner baut).
3. `PILOT_AUTHORIZATION` — erst nach echten RUNs sinnvoll (UA-B01, UA-I01).
4. `CODEX_REVIEW` — laeuft auf dem DANN gueltigen Bundle, nicht vorher.

Nicht in der Liste (absichtlich): neue Queues, neue Worker-Familien,
Product-Shell-Arbeit (J01-Verbot), PRE_CODEX-Revalidierung (Bar).

## Dedupe-Protokoll (gegen 9-Fenster-Kosten)
- D1. M1–M8-Pakete sind KANONISCH fuer ihre Themen; wer ein Thema beruehrt,
  zitiert das Paket statt neu zu analysieren (COST_SAFE-Geist).
- D2. Neue Funde gehen als `F`-Zeilen in das passende M-Paket (Append),
  nicht als neue Datei.
- D3. Offene Owner-Entscheide (genau 7): M2.2 (Skip-Regel), M3.4 (Siegel-Wort),
  M4.2 (Ein-Prozess-Regel), M5.2 (Heartbeat-Option), M6.1 (Reap-Garantie),
  M7.2 (Log-vs-State-Checker), Bundle-Ort (UA-G01). Liste geschlossen halten.

## Reuse-Karte (nicht neu bauen)
- Beacon-Vertrag + Beacon-Code (reparieren, nicht neu) — UA-E01.
- RUN-Evidenz-Layout (wiederverwenden) — UA-H01.
- `run_muse`-Muster: In-Task-Heartbeat + Gruppen-Cleanup (M5/M6-Referenz).
- `save_state`-Atomaritaet (M8-H4) — kein eigenes Journal noetig.
- Shell-Riegel intakt (nicht anfassen) — UA-G01/UA-J01.

## ACCEPTANCE / REQUIREMENT
- M9.1: Genau EIN `NEXT_GLOBAL` (oben); alle Dokumente mit abweichendem NEXT
  sind `LOCAL_NEXT` und verweisen hierher.
- M9.2: Kein Fenster startet Arbeit ausserhalb Rang 1–4 ohne menschliche Freigabe.
- M9.3: Nach jeder Owner-Entscheidung (D3): genau EINE Zeile hier aktualisieren
  (`ENTSCHEID | DATUM | WER`), kein Rewrite der Pakete.

## BLOCKED_UNTIL
- Menschliche Bestaetigung dieses NEXT_GLOBAL (ein Wort genuegt).

## NEXT
Warten auf Rang-1-Entscheidung. Bis dahin: nur D3-Entscheide dokumentieren,
keine neue Analyse.
