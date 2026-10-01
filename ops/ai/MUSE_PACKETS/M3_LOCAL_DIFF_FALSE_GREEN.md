# M3 — LOCAL_DIFF_FALSE_GREEN (Muse 3)

Stand: 2026-09-28. Statisch. Keine Revalidierung — nur Muster + Wachen.

## Problem
`VALIDATED_LOCAL_GREEN` + `AUTHORITATIVE_READY=YES` (`GATE_STATE_CURRENT.md`)
stehen neben: SCOPE_OK=NO, diff-check FAILED, Skip-Widerspruch 1-vs-0,
12-Case-Evidenz auf Pfaden ausserhalb des Repos, SHA-Durability UNKNOWN
(`PROOF_CARD.md`). "Lokal gruen" kann vom Nutzer als "bewiesen" gelesen werden —
das ist False-Green-Gefahr, kein bewiesener False-Green-Fall.

## False-Green-Muster (aus M1/M2 abstrahiert)
P1. STARKES_WORT_SCHWACHE_QUELLE: "READY/PROVEN" ohne Level
   (SYNTHETIC vs REPO_REPRODUCIBLE vs PHYSICAL — vgl. UA-D01).
P2. EXTERNE_EVIDENZ: Belege ausserhalb des Repos als PROVEN zitiert
   (`c:\Users\lol\courier_work\...\*.result.md` im Handoff).
P3. ZAEHLEN_OHNE_MENGE: 57 vs 51 ohne benannte Suite-Menge (M1-F3).
P4. REGELWIDRIG_GRUEN: Gruen-Siegel trotz verletzter Gate-Items
   (Scope-Item 3, Skip-Item 6, Diff-Item 7).
P5. STILLE_IGNORANZ: Flags/Argumente ohne Wirkung (`--db` am Server,
   `--target` am Verifier, `--port` am Server — alle belegt ignoriert).

## ACCEPTANCE / REQUIREMENT (Wachen, kein Code)
- M3.1: Jedes Gruen-Siegel nennt: `SUITE_MENGE | SHA | HOST | LEVEL | REGELSTATUS
  (alle Gate-Items einzeln ok/offen)`. Fehlt ein Feld, heisst das Siegel
  `PARTIAL_GREEN`, nie `READY`.
- M3.2: P2-Faelle werden als `EXTERNAL_UNVERIFIED` markiert, bis ein Bundle mit
  Hash im Repo liegt (vgl. UA-G01).
- M3.3: P5-Faelle bekommen je einen Satz im betroffenen Skript-Kopf
  ("IGNORIERT: --db, nutze COURIER_STATE_FILE") — Doku, kein Umbau.
- M3.4: `VALIDATED_LOCAL_GREEN` wird praezisiert zu `LOCAL_SYNTHETIC_GREEN`
  (Vorschlag an Gate-Owner; kein Fenster benennt das Gate eigenmaechtig um,
  aber jeder Bericht nutzt die praezise Form daneben).

## MISSING_SYSTEM_SUPPORT
- Kein Siegel-Schema (Felder aus M3.1) in durablem State.
- Kein Evidence-Bundle-Ort mit Hash.

## BLOCKED_UNTIL
- Gate-Owner bestaetigt Siegel-Vokabular (M3.4) und Bundle-Ort.

## NEXT
M4 (Replay-Identitaet — wo Gruen wirklich traegt: Idempotenzkette).
