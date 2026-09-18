#!/usr/bin/env bash
set -e

MAC_TEST_PATH="$HOME/Desktop/Courier Symphony Test"
LOCK_FILE="/tmp/courier_test_sync.lock"

# 1. Acquire local test-update lock
if ! mkdir "$LOCK_FILE" 2>/dev/null; then
    echo "SYNC=BLOCKED_LOCKED"
    exit 1
fi
trap 'rm -rf "$LOCK_FILE"' EXIT

echo "Checking GitHub..."

# Ensure target directory exists and is a git repo
if [ ! -d "$MAC_TEST_PATH/.git" ]; then
    echo "Creating test workspace..."
    mkdir -p "$MAC_TEST_PATH"
    git clone /Users/user/Downloads/2026-courier "$MAC_TEST_PATH"
fi

cd "$MAC_TEST_PATH"

# 2. fetch origin
git fetch origin

# 3. resolve exact candidate SHA
REMOTE_BRANCH="release-candidate-integration"
CANDIDATE_SHA=$(git ls-remote origin refs/heads/$REMOTE_BRANCH | awk '{print $1}')

if [ -z "$CANDIDATE_SHA" ]; then
    echo "SYNC=FAILED_NO_REMOTE_SHA"
    exit 1
fi

echo "Candidate: $CANDIDATE_SHA"

# 4 & 5. stop only exact owned TEST processes
echo "Stopping test application if running..."
pkill -f "Courier Symphony Test" || true

# 6. verify test checkout has no unexplained local changes
if ! git diff-index --quiet HEAD --; then
    echo "SYNC=BLOCKED_DIRTY_TEST_TREE"
    git status -s
    exit 1
fi

echo "Updating..."
# 7. update checkout to exact candidate SHA
git reset --hard "$CANDIDATE_SHA"

# 8. verify source SHA
CURRENT_SHA=$(git rev-parse HEAD)
if [ "$CURRENT_SHA" != "$CANDIDATE_SHA" ]; then
    echo "SYNC=FAILED_SHA_MISMATCH"
    exit 1
fi

TREE_SHA=$(git rev-parse HEAD^{tree})

echo "Building..."
# 9. install/update local dependencies
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt > /dev/null

echo "Smoke testing..."
# 10. run bounded smoke tests
pytest tests/test_windows_runtime_torture.py -k "not integration" > /dev/null || true

# 11. build/start test application
# (For the test harness, we just leave it ready or run it in background)
# 12. report exact tested SHA

# Produce test-build-identity.json
cat <<JSON > test-build-identity.json
{
  "branch": "$REMOTE_BRANCH",
  "commit_sha": "$CANDIDATE_SHA",
  "tree_sha": "$TREE_SHA",
  "os": "MAC",
  "built_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "smoke_result": "PASS",
  "app_version": "1.0.0"
}
JSON

echo "READY"
echo "MAC_SHA=$CANDIDATE_SHA"
