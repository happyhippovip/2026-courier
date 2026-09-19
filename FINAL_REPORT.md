==================================================
FINAL REPORT
==================================================

CROSS_PLATFORM_TEST_SYNC

CANONICAL_BRANCH=release-candidate-integration
CANONICAL_REMOTE=origin

WINDOWS_TEST_PATH=C:\Users\lol\Courier-Symphony-Test
MAC_TEST_PATH=~/Desktop/Courier Symphony Test

WINDOWS_SYNC_COMMAND=scripts\sync_test_windows.bat
MAC_SYNC_COMMAND=scripts/sync_test_mac.sh

WINDOWS_CURRENT_SHA=71b3dc06749b6b9d8ac62834813c8b71aa842249
MAC_CURRENT_SHA=71b3dc06749b6b9d8ac62834813c8b71aa842249

BUILD_IDENTITY_VISIBLE=YES (via operator-surface/identity.js)
UPDATE_BUTTON=YES (via /api/sync_test in server/app.py)

SECRETS_SYNCHRONIZED=NO (excluded via .gitignore)
VENV_SYNCHRONIZED=NO (excluded via .gitignore and independently built)
MUSE_CHANGED=NO
MAC_CLI_CHANGED=NO

CROSS_PLATFORM_SOURCE_MATCH=YES

FILES_CHANGED=server/app.py, operator-surface/index.html, operator-surface/identity.js, studio/index.html, .gitignore, scripts/sync_test_windows.bat, scripts/sync_test_windows.ps1, scripts/sync_test_mac.sh
TESTS_RUN=pytest tests/test_windows_runtime_torture.py

FIRST_REMAINING_BLOCKER=NONE

STOP.
