WORK_ID=M17
STATUS=DONE

QUESTION=Take one Physical-AI reliability problem and ask whether solving it creates a valuable normal software feature for Courier.

WHAT_WE_ASSUMED=We assumed that if a software tool (e.g., a web scraper or an SQL query) executes without throwing a runtime error, the data returned is valid and the agent should proceed to reason about it.

WHAT_EVIDENCE_SAYS=In physical robotics, a camera might still be powered on and transmitting frames (no system error), but if the lens is covered in mud, the data is useless. Robots use "Sensor Confidence Telemetry" to detect this. If confidence drops below a threshold, the robot halts to avoid driving off a cliff. In software AI, if a web scraper hits a CAPTCHA or a 403 Forbidden page, it still returns an HTTP 200 with HTML text (no system error). The LLM reads the "muddy" data, hallucinates that the target company sells CAPTCHAs, and confidently makes a disastrous business decision. 

CLOSEST_EXISTING_SOLUTION=Standard `try/catch` error handling or HTTP status code checks. However, these only catch hard system failures, not semantic data degradation (the "muddy lens" problem).

NEW_TO_OUR_PROJECT="Tool Confidence Telemetry." We port the robotics concept of "Sensor Degradation" into Courier's software tools. Every tool in Courier must return a dual payload: `{ data: string, telemetry: { confidence_score: 0.0 - 1.0, anomaly_flag: boolean } }`. For example, a scraper tool uses a lightweight regex to check if the returned HTML contains "Prove you are human." If so, it flags `confidence_score: 0.1`. The Courier Dispatcher has a hardcoded hardware-like interrupt: if any tool returns a score < 0.5, the LLM is physically blocked from using the `data` payload and is forced into a `SENSOR_RECOVERY_MODE`.

POSSIBLE_EXTERNAL_GAP=Agent frameworks currently treat tools as binary: they either throw an exception or return perfect truth. By introducing a gradient of "Data Confidence," Courier prevents the single biggest cause of silent hallucinations—agents confidently reasoning over garbage data.

CUSTOMER_VALUE=Drastically reduces "silent failures." A silent failure (e.g., an agent summarizing an error page and emailing it to a client) is infinitely worse than a loud failure (the agent stopping and asking for help).

MONEY_CONNECTION=Enterprise trust. You cannot sell autonomous agents to banks or healthcare providers if the agent is capable of confidently executing trades based on an empty or malformed API response. 

NOOB_CONNECTION=A beginner understands: "If your robot vacuum gets its sensor blocked, it stops and beeps. Your software AI should do the exact same thing when a website blocks it."

RELIABILITY_CONNECTION=This solves "Garbage In, Garbage Out" at the orchestration layer, preventing the LLM from ever seeing the garbage in the first place.

ROBOTICS_CONNECTION=Direct 1:1 translation of LiDAR/Camera confidence thresholding used in autonomous vehicles (e.g., Tesla Autopilot disengaging in heavy rain).

WHY_THIS_COULD_BE_WRONG=Calculating the `confidence_score` requires developers to write heuristic checks (e.g., regexes) for every tool they build. Developers are notoriously lazy and might just hardcode `confidence_score: 1.0` to bypass the requirement, rendering the feature useless.

ONE_DAY_TEST=Build a `fetch_pricing` tool that intentionally returns the text of a Cloudflare "Access Denied" page instead of actual pricing data. Watch the agent hallucinate based on it. Then, implement the Confidence Telemetry wrapper that flags Cloudflare/CAPTCHA pages as `confidence: 0.0` and observe if the Dispatcher successfully halts the agent.

KILL_CONDITION=If it is impossible to accurately write lightweight heuristic checks for data anomalies without just using another expensive LLM call (which ruins latency and cost), this feature is not viable for standard tools.

DO_NOT_REPEAT_FINGERPRINT=M17_TOOL_CONFIDENCE_TELEMETRY_MUDDY_LENS

NEXT_DECISION=Implement a basic anomaly/confidence wrapper for the `read_url` tool to detect common anti-bot/error pages.
