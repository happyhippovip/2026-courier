# ROLLBACK PLAN: MINIMUM KERNEL SYMPHONY RC V1

## Objective
Instantly and cleanly revert all changes introduced by `MINIMUM_KERNEL.patch` without data loss or residual state.

## Rollback Methods

### Method 1: Clean Git Restore (Fastest)
If no commits have been made:
```powershell
# 1. Reverse the patch
git apply --reverse scratch/symphony_convergence_rc_v1/MINIMUM_KERNEL.patch

# 2. Alternatively, restore modified and clean untracked files
git restore .
git clean -fd -e scratch/
```

### Method 2: Reverse Patch Application
```powershell
git apply --reverse scratch/symphony_convergence_rc_v1/MINIMUM_KERNEL.patch
git status
# Confirms working directory returned exactly to pre-patch state.
```

## Rollback Verification Checklist
- [ ] `git status` matches pre-patch baseline.
- [ ] Active process leases remain 0.
- [ ] No phantom files remain in `governance/` or `supervisor/`.
