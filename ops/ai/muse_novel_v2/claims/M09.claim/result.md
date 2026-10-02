WORK_ID=M09
STATUS=DONE

QUESTION=What happens if a provider disappears, rate-limits, changes model, changes account, or becomes temporarily unavailable?

WHAT_WE_ASSUMED=Most developers assume that an agent is tightly coupled to a specific LLM provider (e.g., "This is an OpenAI agent"). If the provider goes down, the agent halts until the provider returns.

WHAT_EVIDENCE_SAYS=Provider APIs experience rate limits, degradation, and outages regularly. In a multi-hour autonomous task, tying the success of the job to 100% uptime of a single API endpoint is mathematically doomed. If the agent crashes halfway, the standard approach is to restart the entire task, wasting money and time.

CLOSEST_EXISTING_SOLUTION=Router proxies like LiteLLM or Fallback models in LangChain. However, these only fall back for single, stateless chat completions. They do not handle transferring the "active state" of a complex, multi-step agent mid-flight.

NEW_TO_OUR_PROJECT="Hot-Swappable Cognitive Engines." Because Courier's Memory (the Ledger) is strictly separated from its Mind (the LLM Provider), the system is naturally resilient to provider failure. If Worker A (Gemini) hits a 429 Rate Limit at step 15 of a 30-step task, the Courier Dispatcher instantly releases the claim and Worker B (Claude) picks it up. A universal "Context Projection" layer translates the immutable ledger history into Claude's format, allowing Claude to execute step 16 as if nothing happened. 

POSSIBLE_EXTERNAL_GAP=The industry treats "The Agent" and "The LLM" as synonymous. Courier treats the LLM as a replaceable "Compute Node" processing a shared durable state. True vendor lock-in prevention isn't just about using a proxy; it's about making multi-step agent memory portable across providers in real-time.

CUSTOMER_VALUE=Mission-critical uptime. The user's overnight batch jobs will finish by morning regardless of whether Anthropic, Google, or OpenAI had an outage at 3 AM.

MONEY_CONNECTION=Enterprises demand SLAs. You cannot sell an enterprise automation tool with a 99.9% SLA if it relies exclusively on a 99.0% SLA upstream provider. Hot-swapping allows Courier to offer a composite SLA that is mathematically higher than any single provider.

NOOB_CONNECTION=A beginner doesn't care if it's Gemini, Claude, or GPT-4 under the hood. They just want the task to finish without an error message saying "RateLimitExceeded: Please try again later."

RELIABILITY_CONNECTION=It turns provider outages from a "System Failure" into a "Silent Failover." The swarm routes around the brain-damage.

ROBOTICS_CONNECTION=If a drone's primary optical sensor fails, it doesn't crash; it instantly falls back to LiDAR to maintain state and finish the flight.

WHY_THIS_COULD_BE_WRONG=Different LLMs have radically different reasoning styles. If Gemini takes Step A and Step B based on a specific logical leap, Claude might look at the ledger, fail to understand the logic, and hallucinate or roll back the work, making mid-flight swapping practically dangerous.

ONE_DAY_TEST=Start a 10-step complex refactoring task using only Gemini. At step 5, kill the Gemini worker and start a Claude worker. Observe if Claude can seamlessly interpret Gemini's ledger history and successfully complete steps 6-10.

KILL_CONDITION=If the "cognitive impedance mismatch" between models is so high that a swapped model consistently ruins the preceding model's work, hot-swapping multi-step tasks is a failed concept.

DO_NOT_REPEAT_FINGERPRINT=M09_HOT_SWAPPABLE_COGNITIVE_ENGINES

NEXT_DECISION=Run the mid-flight model swap test (Gemini -> Claude) on a live ledger.
