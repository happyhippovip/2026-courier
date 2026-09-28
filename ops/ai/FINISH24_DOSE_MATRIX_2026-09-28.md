# Finish24 Dose Matrix

Same slots are reused across invocations because each invocation advances exactly one pass P1..P6.

WINDOW_COUNT=1:
- Slot 01 only.
- Queue 6x.
- /clear after 2x and after 4x if CLEAR_SAFE.
- This is a single-window marathon.

WINDOW_COUNT=6:
- Slots 01-06.
- Queue 3x each.
- /clear.
- Queue 3x each again.
- Total = all six passes per slot.

WINDOW_COUNT=12:
- Slots 01-12.
- Queue 2x each.
- /clear.
- Queue 2x each.
- /clear.
- Queue final 2x each.
- Total = six passes.

WINDOW_COUNT=15:
- Slots 01-15.
- Queue 2x each.
- /clear.
- Queue 2x each.
- /clear.
- Queue 2x each.

WINDOW_COUNT=18:
- Slots 01-18.
- Same 2x + clear + 2x + clear + 2x.

WINDOW_COUNT=21:
- Slots 01-21.
- First 2x each.
- /clear.
- Second 2x.
- /clear.
- Final 2x only for slots not FAMILY_COMPLETE.

WINDOW_COUNT=24:
- Slots 01-24.
- First 2x each.
- /clear.
- Second 2x each.
- /clear.
- Final 2x only for unfinished slots.

Never queue a seventh invocation after FAMILY_COMPLETE.
Never /clear mid-claim, mid-patch, or mid-physical run.
