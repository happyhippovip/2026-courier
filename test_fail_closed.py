import os
import sys
from scripts.courier_founder_mode import MultiChatGoalIntake

intake = MultiChatGoalIntake(os.getcwd())
try:
    intake._mutate(lambda data: data.append({"test": 1}))
except Exception as e:
    import traceback
    traceback.print_exc()

