WORK_ID=M06
STATUS=DONE

QUESTION=How can Courier communicate uncertainty without inventing meaningless percentages?

WHAT_WE_ASSUMED=We assumed that users want a single "Confidence Score" (e.g., 95%) to decide whether to trust an agent's output.

WHAT_EVIDENCE_SAYS=LLMs are notoriously bad at calibrating their own confidence. If you ask an LLM for a confidence percentage, it will often confidently hallucinate "99%" for a completely fabricated fact. A percentage is a mathematical lie in a non-deterministic generative system.

CLOSEST_EXISTING_SOLUTION=Self-reflection prompts ("Are you sure? Critique your answer") or standard RAG citations (e.g., `[1]`, `[2]`).

NEW_TO_OUR_PROJECT=The "Cryptographic Provenance Graph." Instead of a fake percentage, Courier visually displays the *chain of custody* of the data. Confidence is communicated strictly as a binary categorization of text: `GROUNDED` (cryptographically tied to a prior ledger read-action via SHA hash) or `GENERATIVE` (synthesized by the LLM with no direct ledger source). 

POSSIBLE_EXTERNAL_GAP=All competitors try to make the AI "seem" more confident or accurate. Courier can take the opposite approach: radically exposing the AI's "invented" text by highlighting it in a different color (e.g., yellow for generative, green for grounded). This builds immense trust because it doesn't hide the uncertainty.

CUSTOMER_VALUE=The human operator can instantly skim a 10-page report and only verify the "yellow" (generative) paragraphs, knowing the "green" paragraphs are byte-for-byte grounded in the source material via the ledger.

MONEY_CONNECTION=Legal, medical, and financial firms cannot deploy agents if they have to manually read every word to check for hallucinations. A system that automatically isolates and flags "generative leaps" drastically reduces QA time, justifying enterprise pricing.

NOOB_CONNECTION=Beginners understand "The AI read this from a file" vs "The AI made this up to fill in the blanks." They don't understand "Softmax probability distribution."

RELIABILITY_CONNECTION=It changes the definition of reliability from "The AI never hallucinates" to "The AI always explicitly tells you exactly which parts it hallucinated/generated."

ROBOTICS_CONNECTION=A self-driving car doesn't say "I am 90% sure the road is clear." It displays the raw LiDAR bounding boxes on a screen so the human can see exactly *why* it thinks the road is clear.

WHY_THIS_COULD_BE_WRONG=The LLM might hallucinate fake `EVIDENCE_REFS` (fake SHA256 hashes) to make generative text look grounded, bypassing the UI's safety highlighting.

ONE_DAY_TEST=Modify the agent prompt to require `[REF: sha256_hash]` for every factual claim. Write a 10-line Python verifier that strips the REFs, checks if they actually exist in `central_state.json`, and rejects the task if a REF is invalid.

KILL_CONDITION=If the strict validation causes the agent to fail >50% of its tasks because it struggles to correctly format or track the SHA256 hashes in its context window, the overhead destroys the utility of the system.

DO_NOT_REPEAT_FINGERPRINT=M06_CRYPTOGRAPHIC_PROVENANCE_NO_FAKE_CONFIDENCE

NEXT_DECISION=Implement the strict REF verifier on a simple reading comprehension task to see if the LLM can faithfully pass real SHAs from context to output.
