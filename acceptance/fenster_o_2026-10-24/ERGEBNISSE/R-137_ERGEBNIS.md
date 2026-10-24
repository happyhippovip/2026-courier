# R-137 · Ops `ops/ai/4week/WEEK_2_40H_QUEUE.md` · FENSTER O
Basis `81bbf224`, nur gelesen. sha256 `b2a929c99c0d50495946ff906c6dfebba1b9fc5934ef3afc0a487bf962edefb9`, 154 Zeilen.

| Punkt | Zeile | Inhalt | Urteil |
|---|---|---|---|
| Struktur | – | 5 Tage × 4 Blöcke à 2 h, jeder Block mit `MODE=CLAIM_ONE_BOUNDED_SUBTASK` und `NO_IDLE_EXIT=YES` (20×) | Ein Claim pro Block passt zu SINGLE_WRITER. `NO_IDLE_EXIT=YES` ohne Kosten-Gate steht in **Spannung** zu UNKNOWN_COST=BLOCK und zu „idle/exit safely, wenn nichts zulässig“ (Memory R-155 Z. 22). Mit V7 vereinbar nur, wenn „keine 0-€-Arbeit, dann BLOCKER-Datei“ gilt |
| Explizit Geld / PAYG / Cloud-Automation | – | **nicht gefunden** | grep nach cost/PAYG/cloud/€/billing/on-demand: keine Treffer zu Geld |
| Day 1 „invoke exactly one **Codex HIGH**“ | 8 | Modelllauf hoher Stufe | **Kostenrisiko UNKNOWN**: Ein Abo-Lauf ist laut V7 erlaubt, ein Lauf mit „HIGH“-Stufe ohne geprüften Kontingent- oder On-Demand-Status ist UNKNOWN_COST, also BLOCK, bis Dennis Kontingent bzw. On-Demand bestätigt |
| Day 3/4 RUN_1/RUN_2 „One physical runner only … A execution count remains 1“ | 68, 98 | | **gültig als Ziel**. Genau das prüfen O7-10 (Neustart darf nicht doppelt dispatchen, heute rot) und B5 |
| „relay=0“, „zero-human continuation“ | 68 | | **gültig**. Hängt am R1-Fix (O7-15) und an G2 (O7-14) |
sha256: bda3e157fa11b44d498f16f6197c3b03f07bd894e66767b57d1d1e6f7514812b
