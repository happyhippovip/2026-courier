# Batch 15 Evidence

## Substep 1: Testabdeckung für Register Social Channel (Missing Test)
- **Fehler:** Das Skript `scripts/register_social_channel.py` (Zuständig für die Onboarding-Logik und Secret-Detection für neue YouTube/TikTok-Kanäle) hatte keine Tests, was die Sicherheit des Secret-Guards gefährdete.
- **Fix:** `tests/test_register_social_channel.py` verfasst. Es wird sichergestellt, dass gültige Channels sauber in `social_channels.json` registriert werden und Duplikate abgewiesen werden. Zudem wird explizit der `check_secrets`-Mechanismus gegen Patterns (wie `ghp_...` oder Password-Strings) positiv getestet.
- **Check/Test:** Die Testsuite läuft lokal erfolgreich durch (`4 passed`).

## Substep 2: Testabdeckung und Fix für Apply Memory Update Proposal (Missing Test / Bug Fix)
- **Fehler:** `scripts/apply_memory_update_proposal.py` (wendet Chief-Approved Memory Updates physisch auf Repo-Dateien an) war ungetestet. Während der Testerstellung wurde ein Logik-Bug identifiziert: Die Schema-Prüfung erlaubte in der Testversion das nicht-kanonische Label `DRAFT`.
- **Fix:** `tests/test_apply_memory_update_proposal.py` implementiert. Mocking von `CANONICAL_MEMORY_ALLOWLIST` und Validation-Logik eingesetzt. Den Test auf die kanonischen Labels (`PLANNED`) korrigiert. Die Logik zum Dry-Run sowie der Fall von Mismatches zwischen Proposal und Approval (z.B. falsche IDs) wird abgedeckt.
- **Check/Test:** Der Test wurde lokal erfolgreich ausgeführt (`2 passed`).

## Substep 3: Testabdeckung für Revenue Customer Intake (Missing Test)
- **Fehler:** Das Skript `scripts/revenue_customer_intake.py` (erstellt automatische Goals bei Kundeneingängen für Revenue Safety Audits) besaß keine Unit-Tests.
- **Fix:** `tests/test_revenue_customer_intake.py` angelegt. Die `requests.post` Methode an die `API_URL` wurde über Monkeypatching gemockt. Es wird validiert, dass der generierte Goal-Payload das korrekte `revenue_safety_audit` Profil besitzt, an `target_agent: linux` gebunden wird und alle CLI-Argumente (`owner`, `repo`, `sha`, `customer_ref`) exakt ins Schema injiziert werden.
- **Check/Test:** Der Test läuft erfolgreich durch (`2 passed`).
