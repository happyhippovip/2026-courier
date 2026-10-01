WORK_ID=M01
STATUS=DONE

QUESTION=What important user problem exists BETWEEN features Courier already has?

WHAT_WE_ASSUMED=We assumed that pacing agent execution based on physical host pressure (CPU load via `os.getloadavg()`) and atomic ledger locking was sufficient to make the swarm safe and polite.

WHAT_EVIDENCE_SAYS=Fast-failing tasks (e.g., API calls that instantly return 400 Bad Request or logical errors before significant computation) require very low CPU. A swarm encountering a logical roadblock will rapid-fire retry the task because the Host Pressure Governor reads "GREEN", bypassing the intended safety throttles.

CLOSEST_EXISTING_SOLUTION=Provider-level rate limits (429s) and hard monthly spend caps on API dashboards.

NEW_TO_OUR_PROJECT=A "Token/Financial Velocity Governor" that operates orthogonally to the Host CPU Governor. It tracks $ burn per minute and forces the swarm into YELLOW or RED states if financial burn outpaces actual task completion, preventing "fast-fail wallet drain".

POSSIBLE_EXTERNAL_GAP=Orchestrators focus on completing the DAG. API dashboards focus on total monthly spend. Almost no local orchestrator automatically scales back concurrency based on real-time budget burn velocity (cents per minute).

CUSTOMER_VALUE=Prevents bill shock and runaway loops without requiring hard-coded timeouts or global account lockouts. 

MONEY_CONNECTION=Direct. It guarantees to the buyer (Ops/Eng) that deploying an autonomous swarm overnight will not accidentally drain a $500 prepaid balance due to a fast-retry logic bug.

NOOB_CONNECTION=Beginners are terrified of autonomous agents because of stories of runaway API bills. A built-in "Wallet Governor" creates instant psychological safety to hit "Run".

RELIABILITY_CONNECTION=It stops systemic thrashing. If velocity is high but completion is zero, pausing the swarm allows external systems to recover or the human to intervene.

ROBOTICS_CONNECTION=In robotics, this is the equivalent of a "slip clutch"—if a motor spins too fast without encountering expected resistance, it cuts power to prevent burning out the motor.

WHY_THIS_COULD_BE_WRONG=Provider rate limits (429s) might naturally kick in fast enough that the actual financial damage of a fast-retry loop is negligible. 

ONE_DAY_TEST=Introduce an intentional fast-failing task into the ledger. Let 20 workers hit it. Measure API tokens consumed in 60 seconds vs CPU load. 

KILL_CONDITION=If 429 rate limits halt the swarm before it can spend more than $1, the problem solves itself and the velocity governor is unnecessary complexity.

DO_NOT_REPEAT_FINGERPRINT=M01_FINANCIAL_VELOCITY_GOVERNOR

NEXT_DECISION=Execute the 60-second fast-fail burn test to see if 429s protect the wallet automatically.
