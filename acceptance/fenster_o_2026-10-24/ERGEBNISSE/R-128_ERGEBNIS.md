# R-128 · Doku `docs/FAST_VERIFICATION_POLICY.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `f9206362ea974474001399ab20013b9eb246b8398e821d340f1553f0b8e9476e`, 102 Zeilen, letzter Commit 2026-09-16.

| Aussage | Zeile | Urteil |
|---|---|---|
| Kleinste ausreichende Verifikation zuerst | 9 | **gültig**. So habe ich O7 betrieben: einzelne Dateien, ein Gesamtlauf mit 44 Tests in ~4 s |
| Kein breites `kill` | 37 | **gültig**; deckt sich mit „keine Prozesse beenden“ |
| Kein zweiter Heavy-Regressionslauf wegen Kontextwechsel | 39, 83 | **gültig**; HEAVY_JOB_LIMIT=1 |
| `SAME_RELEVANT_FINGERPRINT + VERIFIED_PASS = REUSE` | 71 | **gültig, mit Einschränkung**: Der Fingerprint muss Code **und** Testdatei umfassen. Wo ein Test nichts prüft (R-130: `tests/test_mission_chip.py:159` immer wahr), führt Wiederverwenden zu falschem PASS |
| Kosten / PAYG | – | **nicht gefunden** (nur „Verifikationskosten“ im Sinne von Aufwand) |
sha256: 3abe073a7526e4f052f7b025523b1086510fe22242dc988996ed4868a3a9ad52
