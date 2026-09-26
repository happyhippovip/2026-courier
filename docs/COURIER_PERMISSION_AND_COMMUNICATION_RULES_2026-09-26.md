# Courier Permission + Communication Rules — 2026-09-26

Status: Product laws prepared during current convergence.

## Rule: NO_PERMISSION_SPAM

Once a user authorizes a project/workspace scope, Courier should work autonomously inside that scope without repeatedly asking for equivalent confirmations.

The customer experience should be:

"Darf Courier in diesem Projekt selbstständig arbeiten?"

After approval, repeated prompts such as Allow / Proceed / Accept All should not be the normal product interaction.

Courier asks again only at a genuine gate, including:

- money/spending;
- login/2FA or credential access requiring the human;
- publishing or external sending when not already authorized;
- destructive or irreversible actions;
- writing outside the authorized project/scope;
- permission expansion;
- safety/legal/human-decision boundaries;
- Goal Contract expansion.

Development machines may intentionally use broader trusted-workspace permissions than customer defaults.

Customer default is **scoped autonomy**, not unrestricted global machine access.

## Rule: SHORTEST_TRUE_ANSWER_FIRST

For human/family explanations, answer with the shortest familiar true phrase first.

Example first answer:

"Ich programmiere etwas Neues."

Only if the person asks for more:

"Wir erfinden ein Programm, das Arbeit am Computer selbst weiterführen soll."

Rules:

- known words first;
- core answer before explanation;
- technical detail only on demand;
- do not force internal Courier terminology on the listener;
- preserve truth while minimizing cognitive load.

## Relationship to Grandma Test

The Grandma Test remains the evidence/demo translation layer.

SHORTEST_TRUE_ANSWER_FIRST governs the **first sentence**.

The detailed Grandma update may follow only when useful.

## Product principle

The user should not have to understand:

- Ledger
- attempts
- execution IDs
- workers
- scheduler internals
- provider mechanics

to know what Courier is doing and whether it worked.
