# R-125 · Doku `docs/COURIER_VERIFIED_CONTINUITY_POSITIONING_2026-09-30.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `92fed820c80c2335170bd20932908b70c74d76219570365018565140effcc6e3`, 77 Zeilen, letzter Commit 2026-09-30.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Fortsetzen nur aus belegtem Zustand, nicht aus Agenten-Behauptung | 15 | **gültig, im Code verletzt** | Provider-DONE ohne Proof (O7-12, `courier_runtime/continuity.py:225-230`; auf #836 noch per API, R-154) |
| Geschätzte oder unbekannte Werte kennzeichnen | 21 | **gültig, im Hub verletzt** | VERIFIED ohne Beweis (R-146, `courier_hub/static/kolibri_universe.mjs:46,137-138`) |
| Duplikatvermeidung als Kern | 46 | **gültig, Lücke** | Doppel-Dispatch nach Grace (O7-10) |
| „A feature is not called VERIFIED merely because it appears in source or documentation“ | 76 | **gültig**; widerlegt die „VERIFIED“-Zeilen in `docs/GOOGLE_ANTIGRAVITY_HANDOVER_2026-10-21_V1.md` (R-130) |
sha256: 425beed779315e37f72b29b10e0751b073cdd381b44217fa3b25f1def969d410
