WORK_ID=M02
STATUS=DONE

QUESTION=What should Courier deliberately REFUSE to automate because refusing it could increase trust, reliability or usability?

WHAT_WE_ASSUMED=Most agent frameworks assume that long-running agents should automatically summarize or compress their conversation history to avoid hitting token limits and save costs (e.g., LangChain's `ConversationSummaryMemory`).

WHAT_EVIDENCE_SAYS=Auto-summarization is lossy and introduces a compounding error rate. When an agent summarizes its own past, it drops nuanced failures or constraints, leading to late-stage hallucinations and infinite loops because the "ground truth" was quietly rewritten by an LLM.

CLOSEST_EXISTING_SOLUTION=AutoGPT/LangChain auto-summarizers, or simply letting the context window crash.

NEW_TO_OUR_PROJECT=An explicit ANTI-FEATURE: "Zero Lossy Compression." Courier strictly refuses to summarize or fuzzy-compress historical state. The ledger is append-only and immutable. If the context becomes too large, the system hard-fails with `CONTEXT_EXHAUSTED` and demands the creation of a durable, distinct output artifact (a file or a new ledger state) rather than silently degrading the memory.

POSSIBLE_EXTERNAL_GAP=Enterprise buyers do not trust agents because they are "black boxes" that drift over time. If a platform guarantees that input data and evidence are never silently altered or summarized behind the scenes, it moves from a "toy" to a "compliant system of record."

CUSTOMER_VALUE=Trust. When a task succeeds or fails, the user knows exactly what data was in the window. No ghost variables, no lost constraints. 

MONEY_CONNECTION=Compliance and Legal teams will veto agent adoption if the agent's decision-making trail is based on lossy LLM self-summaries. A strict "no-compression" guarantee unlocks regulated enterprise budgets.

NOOB_CONNECTION=Beginners hate when an AI "forgets" what they said 10 minutes ago because it decided that part of the conversation wasn't important enough for the summary.

RELIABILITY_CONNECTION=Forces agents to practice good "data hygiene"—writing intermediate results to disk (artifacts) instead of relying on infinite conversational memory.

ROBOTICS_CONNECTION=A robot mapping a room doesn't "summarize" a wall out of existence to save RAM; it updates a hard spatial map. Software agents must do the same with artifacts.

WHY_THIS_COULD_BE_WRONG=Gemini 1.5 Pro has a 2-million token context window. It's possible that for 99% of tasks, context exhaustion is a solved problem, making this anti-feature philosophically interesting but practically irrelevant.

ONE_DAY_TEST=Feed a complex software refactor task into an agent with a deliberately constrained context window (e.g., 32k limits). Test A: Auto-summarize history. Test B: Hard-fail and force artifact creation. Measure which results in a working codebase.

KILL_CONDITION=If massive context windows (2M+) prove cheaper and more reliable than forcing artifact creation, then relying on raw history is superior to this anti-feature.

DO_NOT_REPEAT_FINGERPRINT=M02_ANTI_FEATURE_NO_LOSSY_COMPRESSION

NEXT_DECISION=Review whether current 2M token models make context exhaustion obsolete, or if cost-per-token still requires strict artifact extraction.
