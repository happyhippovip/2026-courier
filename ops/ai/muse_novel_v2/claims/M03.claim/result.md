WORK_ID=M03
STATUS=DONE

QUESTION=What could make an Oma/nontechnical user obtain a real useful result within ten minutes?

WHAT_WE_ASSUMED=We assumed users interact with Courier via a CLI, IDE integration (Muse), or a dashboard. 

WHAT_EVIDENCE_SAYS=Oma (and busy executives) do not install CLIs, Docker, or VS Code. Their primary interface for delegating work to human assistants is Email or WhatsApp. Any setup process requiring terminal access instantly filters out 99% of the non-technical market.

CLOSEST_EXISTING_SOLUTION=Email-to-CRM tools (like forwarding receipts to Expensify), or basic chatbots on WhatsApp.

NEW_TO_OUR_PROJECT="Courier Inbox." The UI is completely invisible. The user simply forwards a confusing email (e.g., a 10-page bureaucratic PDF from an insurance company) to `oma@courier.bot`. The IMAP listener translates the email into a `GOAL` in the ledger. The swarm executes the work (reading, analyzing, drafting a response) and the system emails the final `DELIVERABLE` back to the user.

POSSIBLE_EXTERNAL_GAP=Most Agent platforms assume the user wants to watch the agent work via a dashboard (the "AgentOps" UI). Non-technical users don't want to watch the agent; they just want the result delivered to their existing inbox. Asynchronous agent orchestration via email is an empty space.

CUSTOMER_VALUE=Zero-friction onboarding. Time-to-value is under 60 seconds (the time it takes to forward an email). No accounts to create (auth is tied to sender email), no apps to install.

MONEY_CONNECTION=High-income, low-time executives will pay a premium ($50+/mo) for a "magic email address" that actually solves problems autonomously rather than just summarizing them.

NOOB_CONNECTION=The ultimate noob interface is an interface they have already used for 20 years: Email.

RELIABILITY_CONNECTION=Email is naturally asynchronous. It perfectly matches the Courier architecture where work takes time and shouldn't block a UI thread.

ROBOTICS_CONNECTION=Similar to "drop and forget" logistics (like placing a package in a mailbox). You don't watch the sorting facility; you just wait for the delivery confirmation.

WHY_THIS_COULD_BE_WRONG=Oma might just forward an attachment with zero context. Without an interactive chat UI to ask clarifying questions, the swarm might hallucinate the wrong goal (e.g., summarizing the insurance letter instead of drafting a cancellation reply).

ONE_DAY_TEST=Write a 50-line Python script that polls a dedicated Gmail inbox, translates unread emails into Courier ledger tasks, waits for the status to turn DONE, and replies to the sender with the result.

KILL_CONDITION=If agents cannot reliably infer the implicit goal of a forwarded email >80% of the time, the lack of a synchronous chat interface will cause unacceptable failure rates.

DO_NOT_REPEAT_FINGERPRINT=M03_EMAIL_TO_LEDGER_INVISIBLE_UI

NEXT_DECISION=Build the IMAP-to-Ledger listener script and forward 5 real-world complex emails to it.
