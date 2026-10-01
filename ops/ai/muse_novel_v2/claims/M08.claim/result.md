WORK_ID=M08
STATUS=DONE

QUESTION=What should happen when Courier does not know whether an external action actually happened?

WHAT_WE_ASSUMED=We assumed that standard HTTP retry logic (exponential backoff) is sufficient for agent reliability, treating API timeouts as simple transient failures.

WHAT_EVIDENCE_SAYS=In distributed systems, a timeout (e.g., 504 Gateway Timeout) does not mean the action failed; it means the *response* failed. If an agent is sending an email or executing a trade, and a timeout occurs, blindly retrying (like most agent frameworks do) will cause disastrous double-execution (spamming the user or double-billing). Because agents operate autonomously, the blast radius of a blind retry loop on a non-idempotent endpoint is massive.

CLOSEST_EXISTING_SOLUTION=Idempotency keys (e.g., Stripe API). However, 90% of the internet (SMTP, legacy web forms, internal databases) does not support idempotency keys.

NEW_TO_OUR_PROJECT=The "Investigator Pattern" for Ambiguous Side-Effects. When a Courier agent experiences a network timeout on a non-idempotent tool call, it does NOT retry. Instead, the ledger halts the task and automatically spawns a mandatory `VERIFICATION_GOAL` task. The agent must use read-only tools (e.g., "Check Sent folder", "Query database for ID") to mathematically prove whether the physical side-effect occurred. Only after the Investigator task resolves to YES or NO does the ledger unblock the original task.

POSSIBLE_EXTERNAL_GAP=Agent frameworks currently treat tools as synchronous black boxes. If the box throws an error, the agent either crashes or retries. No framework natively injects an "epistemological verification" step to reconcile internal state with external reality after a network partition.

CUSTOMER_VALUE=Prevents catastrophic business errors (double-billing, double-emailing, database corruption) while maintaining autonomy. The human doesn't have to jump in to check if the email actually sent.

MONEY_CONNECTION=Enterprise risk teams will not allow autonomous agents to execute `POST` requests without a mathematically sound answer to the "Two Generals Problem" (network partitioning). The Investigator Pattern turns a theoretical computer science risk into a solved operational feature.

NOOB_CONNECTION=A beginner doesn't know what "idempotency" is. They just know they don't want their AI assistant to accidentally buy the same pair of shoes three times because Amazon's website was slow.

RELIABILITY_CONNECTION=This is the definition of reliability for side-effecting agents. It replaces "hope it didn't run twice" with "verify external state before proceeding."

ROBOTICS_CONNECTION=If a robotic arm attempts to place a screw but loses camera feed for 2 seconds, it does not blindly plunge the screwdriver down again. It queries its sensors to verify if the screw is already in the hole.

WHY_THIS_COULD_BE_WRONG=For many APIs, there is no easy read-only endpoint to verify if a state change occurred (e.g., submitting an anonymous web form). In those cases, the Investigator Pattern cannot function.

ONE_DAY_TEST=Create a mock "Send Email" tool that successfully sends the email but intentionally drops the HTTP connection before returning a 200 OK. Force the agent to use it. If the agent blindly retries, it fails. Implement the Investigator Pattern and see if the agent queries the "Read Sent Mail" tool to safely recover.

KILL_CONDITION=If the cognitive overhead of requiring developers to write a "Verify" counterpart for every "Write" tool they create is too high, developers will abandon the framework.

DO_NOT_REPEAT_FINGERPRINT=M08_INVESTIGATOR_PATTERN_AMBIGUOUS_SIDE_EFFECTS

NEXT_DECISION=Implement the "dropped connection" mock test to see how the current Courier loop handles a 504 on a successful write.
