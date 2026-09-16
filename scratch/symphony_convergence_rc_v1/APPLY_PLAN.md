# APPLY PLAN: MINIMUM KERNEL SYMPHONY RC V1

## Objective
Apply the minimum verified Windows autonomy kernel and governance choke points to a compatible Courier checkout at commit `aa5c01d21c7e055c7e3b5117ded5eddc6793dde4`.

## Prerequisites
1. Clean git working tree at base commit: `git status` must report no active changes.
2. Zero active writer or process leases.
3. Node.js environment with version >= 18.x.

## Step-by-Step Application Instructions

```powershell
# Step 1: Verify baseline commit
git rev-parse HEAD
# Must return: aa5c01d21c7e055c7e3b5117ded5eddc6793dde4

# Step 2: Dry-run the patch
git apply --check scratch/symphony_convergence_rc_v1/MINIMUM_KERNEL.patch

# Step 3: Apply the patch
git apply scratch/symphony_convergence_rc_v1/MINIMUM_KERNEL.patch

# Step 4: Verify working tree status
git status --short
# Exactly 53 files should be modified or created.

# Step 5: Execute verification suite
& "C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe" tests/test_supervisor_plane_p0.js
& "C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe" tests/test_mandatory_scenarios_suite.js
```
