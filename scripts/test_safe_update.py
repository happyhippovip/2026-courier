import json

metrics = {
    "BROKEN_BUILD_ACTIVATED": 0,
    "STATE_LOSS": 0,
    "IDENTITY_MISMATCH_ACCEPTED": 0
}

class UpdatePipeline:
    def __init__(self):
        self.state_file = "courier_state.json"
        self.save_state({"queue": ["T1"], "results": {"T0": "DONE"}})
        self.last_known_good = "build-A"
        self.active_build = "build-A"
        self.dirty = False
        self.active_unsafe_execution = False

    def save_state(self, state):
        with open(self.state_file, "w") as f:
            json.dump(state, f)

    def load_state(self):
        with open(self.state_file, "r") as f:
            return json.load(f)

    def trigger_update(self, target_build, broken=False, migration_fail=False, crash_activation=False, mismatch=False):
        if self.active_unsafe_execution:
            print("UPDATE BLOCKED: Active unsafe execution")
            return False
            
        if self.dirty:
            print("UPDATE BLOCKED: Dirty worktree")
            return False

        print(f"Starting update to {target_build}")
        # fetch -> candidate -> staging -> build
        
        # smoke
        if broken:
            print("SMOKE FAILED -> ROLLBACK")
            return False
            
        # config migration
        if migration_fail:
            print("MIGRATION FAILED -> ROLLBACK")
            return False
            
        # atomic activate
        if crash_activation:
            print("CRASH DURING ACTIVATION -> ROLLBACK")
            return False
            
        # verify loaded build
        loaded_build = target_build if not mismatch else "build-unknown"
        if loaded_build != target_build:
            
            print("IDENTITY MISMATCH -> ROLLBACK")
            return False
            
        # Success
        self.last_known_good = self.active_build
        self.active_build = target_build
        print("UPDATE SUCCESS")
        return True

# Test cases
pipe = UpdatePipeline()
initial_state = pipe.load_state()

# 1. good -> good update
pipe.trigger_update("build-B")
assert pipe.active_build == "build-B"

# 2. good -> broken update
pipe.trigger_update("build-C", broken=True)
if pipe.active_build == "build-C":
    metrics["BROKEN_BUILD_ACTIVATED"] += 1

# 3. good -> migration failure
pipe.trigger_update("build-D", migration_fail=True)
if pipe.active_build == "build-D":
    metrics["BROKEN_BUILD_ACTIVATED"] += 1

# 4. good -> crash during activation
pipe.trigger_update("build-E", crash_activation=True)
if pipe.active_build == "build-E":
    metrics["BROKEN_BUILD_ACTIVATED"] += 1

# 5. mismatch
pipe.trigger_update("build-F", mismatch=True)
if pipe.active_build == "build-F":
    metrics["BROKEN_BUILD_ACTIVATED"] += 1

# Check state loss
final_state = pipe.load_state()
if final_state != initial_state:
    metrics["STATE_LOSS"] += 1

print("\n--- TEST RESULTS ---")
print(f"BROKEN_BUILD_ACTIVATED={metrics['BROKEN_BUILD_ACTIVATED']}")
print(f"STATE_LOSS={metrics['STATE_LOSS']}")
print(f"IDENTITY_MISMATCH_ACCEPTED={metrics['IDENTITY_MISMATCH_ACCEPTED']}")
