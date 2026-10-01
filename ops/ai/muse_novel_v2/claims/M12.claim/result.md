WORK_ID=M12
STATUS=DONE

QUESTION=What can the founder sell manually first that teaches exactly what Courier should build?

WHAT_WE_ASSUMED=We assumed we should build a generic "AI Orchestration Platform" and then find developers willing to learn our infrastructure to build their own use cases.

WHAT_EVIDENCE_SAYS=Selling generic infrastructure is the hardest go-to-market motion. Developers are fatigued by new "agent frameworks." However, businesses happily pay for finished outcomes. If you want to know exactly what orchestration features are missing from Courier, you must use it in a high-stakes, real-world production environment where failure directly costs the founder time and money.

CLOSEST_EXISTING_SOLUTION=Traditional software consulting agencies, or specific code-mod tools like Grit.io. 

NEW_TO_OUR_PROJECT=The "Tech Debt Eradication as a Service" (Service-First Trojan Horse). The founder sells a fixed-price outcome to a CTO: "I will migrate your Vue 2 codebase to Vue 3 for $5,000." The client thinks they hired a boutique agency. Behind the scenes, the founder attempts to fulfill the contract using only Courier. Every time Courier fails, hallucinates, or loops, the founder discovers the exact missing framework feature (e.g., AST-aware diffing tools, LSP integration, manual rollback gates) and builds it.

POSSIBLE_EXTERNAL_GAP=Most agent frameworks are built by testing on toy benchmarks (SWE-bench). They optimize for passing isolated tests, not for surviving a messy, undocumented enterprise codebase over a 48-hour continuous run. By selling a real service, Courier's architecture is shaped by reality, not benchmarks.

CUSTOMER_VALUE=The customer gets their legacy code migrated cheaply and quickly without pulling their own senior engineers off product work. 

MONEY_CONNECTION=It generates immediate cash flow to fund development. It proves the ROI of Courier in dollars ($5,000 earned for 2 hours of human setup and 40 hours of AI compute). Once the Courier workflow is perfected on the service side, the "Vue 3 Migration Playbook" (M11) can be packaged and sold as a software product.

NOOB_CONNECTION=The ultimate non-technical product is a service. The client doesn't need to know how to use Courier; they just write a check and get an upgraded codebase.

RELIABILITY_CONNECTION=Nothing forces a system to become reliable faster than a founder who has to manually clean up after the system's mistakes at 2 AM to deliver a client project on time.

ROBOTICS_CONNECTION=Boston Dynamics didn't just sell robot dogs; they sold "site inspection services" where their own operators walked the dogs through hazardous facilities, learning exactly where the hardware failed in the real world before selling the robot.

WHY_THIS_COULD_BE_WRONG=The foundational LLM models (Gemini/Claude) might simply lack the architectural reasoning capabilities required for a massive framework migration, meaning the founder ends up doing 95% of the work manually and Courier learns nothing about orchestration because the failure was at the LLM reasoning layer.

ONE_DAY_TEST=Find a mid-sized open-source project stuck on an old framework version. Open an issue offering to migrate it for free. Use Courier to attempt the migration. Document every single time you have to intervene manually.

KILL_CONDITION=If the manual intervention is caused strictly by the LLM's inability to write correct code (rather than Courier's inability to orchestrate, retry, or provide context), then Courier cannot solve the problem and this service is not viable.

DO_NOT_REPEAT_FINGERPRINT=M12_SERVICE_FIRST_TECH_DEBT_TROJAN_HORSE

NEXT_DECISION=Execute a free open-source framework migration using the current Courier build to stress-test the ledger.
