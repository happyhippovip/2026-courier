# M2 — SKIPPED_TEST_VALIDITY (Muse 2)

Stand: 2026-09-28. Statisch. Kein Re-Run, keine Revalidierung.

## Befund
- Der genau EINE Skip ist lokalisiert: `tests/test_artifact_upload_flow.py:463-466`
  `if sys.platform == "win32": pytest.skip("Mac daemon requires fcntl")`.
  Deterministisch, plattformbedingt, kein Flaky-Skip, kein versehentliches Skip.
- Gate-Regel (`GOOGLE_PRE_CODEX_GATE_2026-09-27.md:23`): `SKIPPED_COUNT=0`
  fuer erforderliche Targeted-Tests.
- Widerspruch in den Akten: `GATE_STATE_CURRENT.md:10` meldet
  `57_PASSED__1_SKIPPED_MAC_ONLY__0_FAILED`, `PRE_CODEX_HANDOFF.md:32-33` meldet
  `SKIPPED_COUNT=0`. Beide koennen nicht gleichzeitig die gleiche Suite meinen.

## Gueltigkeits-Urteil (statisch, kein Gate-Urteil)
- Der Skip SELBST ist valide: `fcntl` existiert auf Windows nicht; der Mac-Daemon-
  Upload-Pfad (`scripts/mac_worker/daemon.py`, `fcntl.flock` in
  `acquire_worker_lock`, `:392-402`) ist auf Windows nicht import-/lauffaehig.
  Ein erzwungener Run auf Windows wuerde Import-Crash statt Pruefung liefern.
- Die REGEL ist auf Windows unerfuellbar formuliert: Solange diese Suite auf
  Windows laeuft, ist SKIPPED_COUNT=0 nur durch Streichen des Mac-Pfads erreichbar
  — was Coverage vernichtet statt sie zu beweisen.
- Der WIDERSPRUCH (1 vs 0) ist ein Reporting-Defekt (vgl. M1-F3), kein Test-Defekt.

## ACCEPTANCE / REQUIREMENT
- M2.1: Skips werden klassifiziert: `PLATFORM_GUARD (valide, zaehlt getrennt)` |
  `CONDITIONAL (valide, Grund nennen)` | `SUSPICIOUS (untersuchen)`.
  Dieser Skip = PLATFORM_GUARD.
- M2.2: Gate-Item 6 braucht eine plattformqualifizierte Lesart
  (z.B. `SKIPPED_SUSPICIOUS=0`, `SKIPPED_PLATFORM_GUARD<=n mit Liste`) ODER der
  Mac-Pfad bekommt ein Windows-faehiges Double. ENTSCHEID des Gate-Owners,
  keine lokale Umdeutung durch ein Fenster.
- M2.3: Bis zum Entscheid gilt: dokumentiert als `SKIPPED=1 (PLATFORM_GUARD,
  fcntl)`, nicht als 0 und nicht als Fail.

## MISSING_SYSTEM_SUPPORT
- Kein Skip-Register (welcher Skip, warum, wo gueltig).
- Kein Windows-Double fuer den Mac-Upload-Pfad.

## BLOCKED_UNTIL
- Gate-Owner-Entscheid zur M2.2-Lesart. Kein Fenster entscheidet das lokal.

## NEXT
M3 (False-Green-Muster aus M1+M2 verallgemeinern).
