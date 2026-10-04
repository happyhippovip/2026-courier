# Courier Product Telemetry Design

**Philosophy:** Minimal product-learning events. No raw content.

**Approved Events:**
- `goal_created`: timestamp, goal_id (UUID)
- `goal_started`: timestamp, goal_id
- `first_value_delivered`: timestamp, time_to_first_value (ms)
- `human_required`: timestamp, reason_code (enum)
- `restart_resumed`: timestamp, duration_paused (ms)
- `goal_completed`: timestamp, final_status
- `support_needed`: timestamp, touch_id

**Privacy Boundary:**
Never collect passwords, tokens, private files, raw customer prompts, raw results, or unnecessary identifiers. Execution evidence is strictly separated from product analytics.
