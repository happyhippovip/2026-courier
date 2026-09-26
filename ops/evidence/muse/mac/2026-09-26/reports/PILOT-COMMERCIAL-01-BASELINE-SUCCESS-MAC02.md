# PILOT-COMMERCIAL-01 — baseline questions + success criteria (fills PILOT-03 pointer)

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=NON_CODE_PREP · 2026-09-26
Complements (not repeats): PILOT-01 (MAC-21, profile/offer/price/duration —
its SUCCESS_CRITERIA points here), RV06 (workflow types), RV18 (acceptance
test), RV08 (proof card), RV13 (incident card).

## The key promise, stated as hypothesis (NOT as capability)
"Bertha kommt morgen an ihre Arbeit zurück, ohne alles manuell zu
rekonstruieren." This is WHAT THE PILOT TESTS. It is unproven for customer
work (RV19/GAP2: verifier is fixture-scoped; E30: revenue path dead). Every
pilot must be able to FALSIFY it — otherwise the pilot proves nothing.

## BASELINE_QUESTIONS (ask day 0, before scope handshake; record answers verbatim)
B1. "Beschreiben Sie die Aufgabe, bei der Sie morgens am längsten brauchen,
bis Sie wieder drin sind." ( free text; must map to one RV06 workflow type —
if it maps to none, this is the wrong pilot.)
B2. "Wie viele Minuten kostet das an einem typischen Tag?" (number; the
pilot's only quantitative anchor. No number → no measurable promise.)
B3. "Was genau müssen Sie rekonstruieren?" (checklist the customer ticks:
offene Dateien / Stand der Teilergebnisse / was als Nächstes dran war /
Entscheidungen von gestern / Sonstiges.)
B4. "Woran erkennen SIE, dass ein Arbeitsergebnis stimmt?" (free text — this
becomes the customer's verification method; if the answer is "Bauchgefühl",
the task is not pilotable yet: today's verifier needs an exact check.)
B5. "Was darf auf keinen Fall automatisch passieren?" (free text — seeds the
FORBIDDEN_ACTIONS + REAL_GATES of the RV17 scope handshake.)
B6. "Wer darf den Piloten stoppen, und wie?" (names the revocation path;
if nobody can answer, do not start.)

## SUCCESS_CRITERIA (evaluate days 11–14 of the PILOT-01 2-week window)
Each criterion is PASS/FAIL with its evidence. Pilot passes iff ALL pass.
S1. WITNESSED_ACCEPTANCE=PASS — RV18 test printed PASS in front of the
customer on day 0. (Evidence: RV08 card of the witnessed run.)
S2. SCOPED_TASKS_VERIFIED — every in-scope task has a proof card with
VERIFIED_BY + method filled. Unverified tasks count as NOT DONE
(grandma rule: FERTIG zählt nur Geprüftes).
S3. NEXT_DAY_CONTINUITY — at least one overnight/next-day event occurred in
days 1–10 AND the day-0 B2 reconstruction minutes dropped to a recorded
lower number on the morning after, by the customer's own report (not ours).
If no overnight event occurred, S3 = INCONCLUSIVE (not PASS) and the pilot
extends by one week or closes inconclusive — never upgraded silently.
S4. HUMAN_INTERVENTIONS_COUNTED — total printed on cards; every intervention
names its gate. Target 0 after start; any count is data, not failure —
hiding one is failure.
S5. NO_OUT_OF_SCOPE_EFFECT — customer confirms nothing happened outside the
authorized workspace; operator confirms from logs. Any breach = pilot FAIL,
incident card filed, scope model (RV17) revised before any next pilot.
S6. CUSTOMER_WOULD_REPEAT — B6-style plain question day 14: "Würden Sie das
für diese Aufgabe wieder einschalten?" YES/NO + one sentence. NO with reasons
is a successful pilot outcome (learning), not a failed one.

## What this deliberately does NOT contain
No ROI multiples, no time-saved extrapolation beyond B2→S3 mornings actually
observed, no SLA, no "autonomy guaranteed". First-5-pilots rule: n=5 anecdotes
with cards, never statistics.
