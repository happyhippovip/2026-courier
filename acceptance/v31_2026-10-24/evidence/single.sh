#!/bin/bash
# usage: single.sh "<dep diffs...>" <package> "<tests>"
S=/tmp/claude-0/-home-user-2026-courier/4510bb24-32c0-5203-8ebf-43dd2db70f44/scratchpad; R=$S/v31/p
deps="$1"; pkg="$2"; tests="$3"
rm -rf $S/v31/sw; git -C /home/user/2026-courier worktree prune
git -C /home/user/2026-courier worktree add -q --detach $S/v31/sw origin/integration/v1 2>/dev/null
cd $S/v31/sw
for d in $deps; do git apply --3way $R/$d.diff >/dev/null 2>&1 && git add -A || { echo "$pkg | DEP_APPLY_FAIL $d"; exit; }; done
if git apply --3way $R/$pkg.diff >/dev/null 2>&1 && ! git diff --name-only --diff-filter=U | grep -q .; then
  r=$(timeout 900 ../../venv/bin/python -m pytest -q -p no:cacheprovider $tests 2>&1 | tail -1)
else r="APPLY_FAIL"; fi
echo "$pkg | deps=[${deps}] | $r"
cd $S; git -C /home/user/2026-courier worktree remove --force $S/v31/sw
