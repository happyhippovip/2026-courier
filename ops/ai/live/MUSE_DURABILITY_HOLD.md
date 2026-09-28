# Durability Hold — REPORTED_FINAL_SHA stale (kein Push, kein Gate-Update)

ROLE=declared single PRE_CODEX durability owner | HOST=MAC (Prompt sagte
Windows — Host-Mismatch notiert, Arbeit ist repo-basiert) | LEDGER=SKIP
BASE=4c1e24cc (origin/candidate-b-1, remote-verifiziert per ls-remote)
REPORTED_FINAL_SHA=34b0a426 (lokal vorhanden: Q027-Packet + Test-Update)

## Warum NICHT publiziert (technisch möglich, semantisch falsch)
- Push-Dry-Run: 4c1e24cc..34b0a426 fast-forward, Permission OK.
  Kein technischer Blocker.
- Aber Writer-Linie ist weitergelaufen: candidate..HEAD = 6 Commits mit
  neuen Fixes (Popen-Leak/Timeout-Kill, Lock-fd-Leak, Duplicate-task_ids,
  Timestamp-Ordering-Tests 09166bd5, AI-Duplicate-IDs, Pressure-Hoarding).
  34b0a426 als FINAL zu persistieren würde einen überholten Candidate
  durabel machen und die neueren Fixes stranden → exakt der False-Green,
  den das Gate bewacht.
- Scope-Hygiene-Notiz: 876396b3 fasst Packet (3 Source-Files) + 5 Doc-Files
  in einem Commit; ML-11-"strictly 5" gilt nur für Candidate-Files.
  Kein Blocker, aber unsauber für künftige Scope-Audits.

## Re-Arm (exakt)
Neuer REPORTED_FINAL_SHA vom Windows Central Writer NACH Quiescence der
Fix-Serie (keine neuen Source-Fix-Commits seit Deklaration) → dann:
lokale Bytes prüfen → Scope-Diff (nur autorisierte Files) → Push →
ls-remote-Verifikation → Gate GENAU EINMAL → Codex-Handoff.

## Addendum — SUPERSEDED (Gate DURABLE, ls-remote bestätigt)
Peer-Durability-Owner pushte 34b0a426 (candidate-b-1 + Mirror
evidence/pre-codex-final-34b0a42, beide remote == 34b0a426, selbst per
ls-remote verifiziert). Gate: PRE_CODEX_STATE=DURABLE,
AUTHORITATIVE_READY=YES. Hold-Position (stale-Bedenken) wird NICHT als
Zweit-Validator weiterverfolgt (Cost-Guard, Single-Owner-Regel).
Protokoll: PRE_CODEX-Arbeiten STOP, CODEX_NOW=YES, warten auf genau
einen Codex-HIGH-Review. Stale-Bedenken lebt nur als Codex-Input
(neuere Writer-Fixes nach 34b0a426), nicht als Gate-Einspruch.

DO_NOT_REPEAT_FINGERPRINT=musedurability-hold-34b0a426-stale
