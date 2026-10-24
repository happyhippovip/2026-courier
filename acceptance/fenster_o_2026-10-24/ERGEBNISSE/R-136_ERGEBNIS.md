# R-136 · Ops `ops/ai/4week/WEEK_1_40H_QUEUE.md` · FENSTER O
Basis `81bbf224`, nur gelesen. sha256 `ec35cdd859e41fd4f7c4731fd894480211744fb47cef597b77efee81a783ab32`, 154 Zeilen.

| Punkt | Zeile | Inhalt | Urteil |
|---|---|---|---|
| Struktur | – | 5 Tage × 4 Blöcke à 2 h, jeder Block mit `MODE=CLAIM_ONE_BOUNDED_SUBTASK` und `NO_IDLE_EXIT=YES` (20×) | Ein Claim pro Block passt zu SINGLE_WRITER. `NO_IDLE_EXIT=YES` ohne Kosten-Gate steht in **Spannung** zu UNKNOWN_COST=BLOCK und zu „idle/exit safely, wenn nichts zulässig“ (Memory R-155 Z. 22). Mit V7 vereinbar nur, wenn „keine 0-€-Arbeit, dann BLOCKER-Datei“ gilt |
| Explizit Geld / PAYG / Cloud-Automation | – | **nicht gefunden** | grep nach cost/PAYG/cloud/€/billing/on-demand: keine Treffer zu Geld |
| Day 1 „failure **mail** behavior“ | 8 | Motor-Fehler per Mail | **Risiko: externe Nachricht**. V7 HACKATHON-Filter: „extern posten/senden“ VERBOTEN. Nur lesen/testen ohne Versand |
| Day 2 Ledger closure: identity/persistence/**replay**/reconcile | 38 | | **gültig und aktuell**. Entspricht B3/B5. Konkrete offene Punkte: O7-05/06/10/12, R-154 |
| Day 4 claim/lease, crash/restart continuity | 98 | | **gültig**. Offen: O7-03/04 (B2), O7-10 (Neustart-Replay) |
sha256: 55804055aedcf041c1d1e3b25365206823f54c23467946aaa55f203a7a4ad50a
