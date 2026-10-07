# MUSE9 M1 — FAILED_TEST_CAUSALITY (Sidecar)

ROLE=M1. READ_ONLY_C2. LEDGER=FROZEN. Kein RUN, keine Revalidierung.
Operator-Stand (lokale Evidence, fremd beobachtet): 28 passed / 1 skipped / 1 failed.

## Subcases

### M1-S1: Count + Suite-Identitaet (Count CONFIRMED, Suite INFERRED)
- Count 30 = `tests/test_artifact_upload_flow.py`: 23 `def test` + genau 2
  Parametrize-Stellen (7er `:65`, 2er `:173`, per Search verifiziert, keine
  weiteren) = 23+6+1 = 30. Passt exakt zum Stand 28/1/1.
- Suite-Name ist INFERENZ (unique-match, kein Beleg): einzige bekannte Suite
  mit 30 Faellen + genau 1 win32-Skip. Gegenprobe: `test_muse_convergence.py`
  skippt via `importorskip("fcntl")` das GESAMTE Modul (viele Skips, kein
  Match); `test_ci_acceptance_credentials.py` skippt nur ohne yaml (0 Skips
  bei installiertem yaml). Runner-Bestaetigung des Dateinamens steht aus.
- GATE_STATE-Anker: 29/1/0 (gleiche Suite, falls Inferenz stimmt).
  -> Regression: genau ein Pass→Fail-Uebergang, Total unveraendert.

### M1-S2: Skip-Identitaet (CONFIRMED, an M2 uebergeben)
- Der 1 Skip ist `test_mac_worker_uploads_and_verifier_reconciles`
  (`:462-466`): `sys.platform == "win32"` -> `pytest.skip("Mac daemon
  requires fcntl")`. Deterministisch, kein Flakiness.
- DISPROVEN: "Der Failed ist der Mac-Test, der jetzt faellt statt skippt" —
  skipped ist weiterhin 1, Skip-Pfad ist plattform-deterministisch.

### M1-S3: Failure-Kandidaten-Ranking (statisch, Methode CONFIRMED)
- Tier-1 (verhaltenssensitiv, je 1 Def): die 4 Windows-Daemon-E2E-Tests
  `:400` uploads+reconciles (Harness max_calls=6, Status + artifact_id-Asserts),
  `:421` transient-failure (faults network+503, max_calls=12),
  `:430` changed-after-hash (expects HUMAN_REQUIRED + current_task None),
  `:449` upload-disabled-by-default (max_calls=5, kein /artifacts-Call).
  Diese brechen zuerst bei Call-/Status-Drift (Call-Anzahl, Status-String,
  Release-Pfad); reine Log-/Kommentar-Aenderungen brechen sie nicht.
- Tier-2 (env-sensitiv): `:309` proxy-bypass — einzige Test ohne Fixtures,
  mutiert `os.environ` direkt (finally-gesichert, aber ohne monkeypatch).
- Tier-3 (deterministisch): alle reinen Flask-Client/Verifier-Unit-Tests
  (Statuscode-Asserts gegen `load_patched_server`, tmp-isoliert).
- Failing-Test-Name: MISSING_EVIDENCE (braucht Runner-Output).

### M1-S4: Root-Cause-Klassen + Diskriminatoren
- BEHAVIOR_DRIFT: Code seit 29/30-GREEN geaendert (eigener Checkout
  `fix-cb1-new @ e575178` ≠ Kandidat `3c2aa516` belegt Drift-Moeglichkeit).
  Diskriminator: `git stash`-freier Diff der 5 Gate-Dateien + Rerun.
- ENV: Operator-Umgebung (Proxy-Vars, Keys, Python/Abhaengigkeiten).
  Diskriminator: Rerun in sauberer Env.
- ORDER: Test-Reihenfolge/Isolation (globale Patches: `time.sleep`,
  `urlopen`, `Popen` — alle monkeypatch-revertiert, aber Leak bei
  hartem Abbruch moeglich). Diskriminator: Single-Test-Run vs. Full-File.
- FLAKY_COUNT: Harness-max_calls-Grenze (StopLoop-Timing).
  Diskriminator: max_calls-Variation im Rerun (nur Diagnose, kein Fix).
- REAL_BUG: Produkt-Code-Fehler. Diskriminator: Minimal-Repro ohne Harness.

### M1-S5: Isolations-Protokoll (fuer Shell-Owner, NICHT hier)
1. `python -m pytest tests/test_artifact_upload_flow.py -q` (Stand sichern).
2. Bei Fail: derselbe Befehl mit `-x -vv --tb=long` (Name + Traceback).
3. Single-Test-Rerun des Failers allein (ORDER-Diskriminator).
4. `git status --short` + `git log --oneline -3` (Drift-Beleg).
5. Ergebnis als Text zurueck (Name, Traceback, Single-vs-Full).

### M1-S6: Handoff-Impact (Folge, keine Revalidierung)
- 29/30-Zitate in Gate-Docs sind STALE, bis der Rerun den Stand bestaetigt
  oder korrigiert. `VALIDATED_LOCAL_GREEN` gilt nur fuer den belegten Lauf.
- Kein neues Gate-Urteil von M1: M1 liefert Ursachen-Tabelle, kein PASS/FAIL.

## Klassifikation
- CONFIRMED: M1-S1 (Count 30; Suite als unique-match INFERRED, Gegenproben
  bestanden), M1-S2 (Skip-Identitaet), Regression (ein Pass→Fail, falls Suite
  stimmt), Ranking-Methode + Tier-Liste.
- DISPROVEN: Mac-Test-failt-statt-skippt; Total veraendert (weiter 30).
- MISSING_EVIDENCE: Failing-Test-Name + Traceback + Operator-Env + SHA des Runs.
- BLOCKED_OTHER_OWNER: Isolations-Run + Rerun (Shell-Owner); Skip-Validitaet (M2).

## OWNER_PACKET (fuer Shell-Owner)
- Datei: diese. Input erbeten: Failing-Test-Name, Traceback, Single-vs-Full,
  `git status/log`, Env-Notiz (Proxy/Key-Verdacht ohne Secrets).
- Danach: M1-S4-Klasse zuordnen, Tier-1/2/3-Hypothese bestaetigen/verwerfen.

## CRITICAL_PATH
Failing-Test-Name -> Single-Rerun (ORDER?) -> Drift-Check (BEHAVIOR?) ->
Klasse -> Fix-Owner oder Test-Owner.

## NEXT_OWNER
Shell-Owner (Isolations-Protokoll M1-S5). Danach M2 (Skip im selben Lauf
mitbewerten) und M3 (Drift-Risiko des Diffs).

## DO_NOT_REPEAT
- Suite nicht erneut zaehlen (30 belegt).
- Mac-Skip nicht erneut identifizieren (belegt, M2 owning validity).
- Keine Test-Runs aus diesem Fenster (keine Shell; Verbot gilt).
- Keine Gate-Urteile ("trotzdem GREEN") aus M1 ableiten.

## STATUS
M1_STATIC_DONE. Warte auf Runner-Evidenz (Name + Traceback).
