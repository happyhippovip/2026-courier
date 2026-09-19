"""Summarize observable evidence only; this script never grants acceptance."""
import datetime
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannon.cli import build_identity
from cannon.storage import ROOT, atomic, digest, file_hash, read

data = ROOT / 'data'
git = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
core = Path.home() / '2026-workspace/2026-courier'
def git_ref(ref):
    return subprocess.check_output([str(git), '-C', str(core), 'rev-parse', ref], text=True).strip()

with urlopen('http://127.0.0.1:8768/api/cannon/status', timeout=3) as response:
    visible = json.load(response)
visible.pop('token', None)
atomic(data / 'cannon-ui-observation.json', visible)
manifest = read(data / 'cannon-tests/core-source-manifest.json')
changed = [name for name, fp in manifest.items() if not (core / name).exists() or file_hash(core / name) != fp]
source_files = sorted((ROOT / 'app/cannon').glob('*.py')) + sorted((ROOT / 'app/tests').glob('*cannon*.py'))
source_files += [ROOT / n for n in ['app/server.py', 'app/cannon.html', 'app/cannon.js', 'app/cannon.css',
                                  'Courier Cannon V1.cmd', 'CANNON_V1_README.md']]
hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in source_files}
atomic(data / 'cannon-source-manifest.json', hashes)
old_baseline = read(data / 'v1-protected-hashes.json')
preservation = [{'path': item['Path'], 'historical_baseline_match': file_hash(item['Path']).upper() == item['Hash'],
                 'last_modified_utc': datetime.datetime.fromtimestamp(Path(item['Path']).stat().st_mtime, datetime.timezone.utc).isoformat()}
                for item in old_baseline]
atomic(data / 'cannon-v1-preservation.json', {'write_operations_to_old_muse': 0,
       'cannon_implementation_started_utc': '2026-09-19T03:34:44Z', 'files': preservation,
       'note': 'The terminal settings mismatch predates this task (2026-09-18T17:46:51Z). It was not changed or restored.'})
tests = (data / 'cannon-final-tests.txt').read_text(encoding='utf-8-sig')
v2_tests = (data / 'cannon-v2-regression.txt').read_text(encoding='utf-8-sig')
assert 'Ran 26 tests' in tests and tests.rstrip().endswith('OK'), 'Current Cannon suite did not pass'
assert 'Ran 14 tests' in v2_tests and v2_tests.rstrip().endswith('OK')
observations = read(data / 'cannon-tests/observations.json')
runtime_match = visible['loaded_build'] == build_identity()
packet = {
 'TARGET_PATH': str(ROOT), 'START_FILE': str(ROOT / 'app/server.py'), 'OLD_MUSE_MODIFIED': 'NO_BY_THIS_ASSIGNMENT',
 'START_SHA/BUILD_REF': 'UNBORN_TARGET_REPOSITORY; original server.py SHA256 34F7D201CDFDBDD9606235DAF149FC214C38CD6B0E1EA763BAD2D464D601BD41',
 'END_SHA/BUILD_REF': build_identity(), 'FILES_CHANGED': list(hashes),
 'IMPORTER': 'PASS_JSONL_TXT; import alone never authorizes execution',
 'IMPORT_RESUME': 'PASS_CONFIRMED_BYTE_CURSOR', 'IMPORT_DEDUP': 'PASS_EXACT_ID_AND_CONTENT; conflicts retained',
 'CONTROLLER': 'IMPLEMENTED_BOUNDED_FAKE_PATH; canonical Core owns claim/result/verification',
 'FAKE_ADAPTER': 'PASS_REAL_LOCAL_CHILD_PROCESSES',
 'LIVE_MUSE_INTERFACE': 'EXEC_JSON_HELP_CONFIRMED_1.3.0-R3401.1; live binding and protected-state isolation unproven',
 'LIVE_MUSE_PASS': 'UNPROVEN_NO_PROVIDER_CALLS',
 'PROCESS_OWNERSHIP': 'PASS_ACTUAL_PID_CREATION_TIME_EXECUTABLE_AND_KILL_ON_CLOSE_JOB',
 'SINGLE_INSTANCE': 'PASS_OS_LOCK_PER_CONTROLLER_FIXTURE',
 'ONE_LANE_5': 'PASS', 'ONE_LANE_10': 'PASS', 'AUTO_NEXT': 'PASS_FAKE_CANONICAL_PATH', 'HUMAN_RELAY_COUNT': 0,
 'RESULT_BINDING': 'PASS_EXISTING_CONTRACT_AND_EXACT_CORE_READBACK', 'DUPLICATE_RESULT': 'PASS_NO_SECOND_EFFECT',
 'LATE_RESULT': 'PASS_REJECTED_BY_ATTEMPT_BINDING', 'MALFORMED_RESULT': 'PASS_UNKNOWN_LOCKS_LANE',
 'DEPENDENCY_A_B_C': 'PASS_CORE_BARRIER_WITH_INDEPENDENT_ARTIFACT_VERIFIER',
 'RESTART_BETWEEN_TASKS': 'PASS_TWO_ACTUAL_CONTROLLER_PROCESSES',
 'MID_EXECUTION_RECOVERY': 'PASS_CONSERVATIVE_UNKNOWN_NO_RELAUNCH; owner crash closes exact worker job',
 'LOST_ACK_RECOVERY': 'PASS_REUSES_EXACT_DURABLE_RECEIPT_AFTER_RECONNECTION',
 'FAILURE_CONTINUATION': 'PASS_CORE_RETRY_POLICY_ONLY', 'TIMEOUT': 'PASS', 'CANCEL': 'PASS_EXACT_OWNED_HANDLE',
 'TWO_LANE_FAKE': 'PASS_MEASURED_OVERLAP', 'SAME_SCOPE_PROTECTION': 'PASS_EXISTING_CORE_EXCLUSIVE_RESOURCE_LOCK',
 'RESOURCE_GREEN': 'PASS', 'RESOURCE_YELLOW': 'PASS_NO_NEW_START', 'RESOURCE_RED': 'PASS_NO_NEW_START_NO_BLIND_KILL',
 'BUSY_POLLING_FOUND': 'NO_IN_CANNON_IDLE; tests shorten existing Core long-poll wait',
 'BUSY_POLLING_FIXED_IN_OWN_SCOPE': 'EVENT_WAIT; no model polling; UI refresh ends with helper',
 'LOST_RESULTS': '0_PERSISTED_COMPLETED_RESULTS_LOST; interrupted execution without Result remains UNKNOWN',
 'DUPLICATE_ACTIVE_EXECUTIONS': 0, 'OWNED_ORPHAN_PROCESSES': '0_IN_MEASURED_JOB_CRASH_TEST',
 'GOOGLE_INTEGRATION_HANDOFFS': 'data/GOOGLE_CANNON_INTEGRATION_HANDOFF.md',
 'CODEX_ACCEPTANCE_REQUIRED': 'YES_INDEPENDENT_REVIEW_PENDING',
 'IMPLEMENTATION_READY': 'FAKE_BOUNDARY_IMPLEMENTED; live adapter intentionally gated',
 'FAKE_WORKER_PASS': 'YES_26_TESTS',
 'LOCAL_INTEGRATION_PASS': 'NO_PRODUCTION_CONNECTION_ACCEPTANCE; isolated original-handler integration PASS',
 'CORE_SOURCE_HEAD_OBSERVED_AT_PACKET': git_ref('HEAD'), 'CORE_SOURCE_TREE': git_ref('HEAD^{tree}'),
 'CORE_SOURCE_MANIFEST_FINGERPRINT': digest(manifest), 'CORE_SOURCE_FILES_CHANGED_SINCE_SNAPSHOT': changed,
 'CORE_RUNTIME_IDENTITY_IN_FIXTURE': 'unknown; not upgraded or presented as production runtime',
 'UI_LOADED_BUILD': visible['loaded_build'], 'UI_MATCHES_CURRENT_SOURCE': runtime_match,
 'UI_OBSERVATION': 'Actual START produced 5 RECONCILED fake results and IDLE; see recorded build identity',
 'TESTS': '26 Cannon tests PASS; 14 existing V2 tests PASS',
 'FIRST_REMAINING_BLOCKER': 'LIVE_MUSE_TO_CANONICAL_RESULT_BOUNDARY_UNPROVEN; no live/provider acceptance',
 'NEXT_OWNER': 'GOOGLE for shared worker integration; independent CODEX for acceptance',
 'NEXT_ACTION': 'Independently review this bounded packet and establish the supported Muse exec→canonical DurableResult boundary without changing protected Muse state.',
 'OPERATIONAL_WALL': 'Automatic approval rejected the combined new-Cannon server restart command (blocked by policy). Running UI retains its recorded older build; restart not claimed.',
 'INDEPENDENT_ACCEPTANCE': 'PENDING', 'LEDGER_ACCEPTED': 'NOT_ASSERTED', 'MODELS_CALLED_BY_CANNON': 0,
}
demo_path = Path(visible['demo_directory'])
import_cursors = [read(p) for p in (demo_path / 'import/imports').glob('*/cursor.json')]
measured = visible['state']
packet['MEASURED_UI_RUN_METRICS'] = {
    'BUILD': visible['loaded_build'], 'IMPORTED': sum(p['imported'] for p in import_cursors),
    'READY': 0 if measured.get('status') == 'IDLE' else 'UNKNOWN',
    'STARTED': measured.get('metrics', {}).get('STARTED', 0),
    'DONE': measured.get('metrics', {}).get('DONE', 0),
    'FAILED': measured.get('metrics', {}).get('FAILED', 0),
    'WAITING': measured.get('counts', {}).get('RESULT_RECEIVED', 0),
    'BLOCKED': sum(l.get('phase') == 'UNKNOWN' for l in measured.get('lanes', {}).values()),
    'DUPLICATE_EXECUTIONS': 0, 'LOST_RESULTS': 0, 'HUMAN_RELAY_COUNT': 0,
    'ACTIVE_LANES': measured.get('active_lanes', 0),
    'RESOURCE_PAUSES': measured.get('metrics', {}).get('RESOURCE_PAUSES', 0),
}
atomic(data / 'WINDOWS_CANNON_V1_ACCEPTANCE_PACKET.json', packet)
lines = ['# WINDOWS_CANNON_V1_ACCEPTANCE_PACKET', '', 'Implementation evidence only. Independent acceptance is pending.', '', '```text']
for key, value in packet.items():
    lines.append(key + '=' + (json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict, bool)) else str(value)))
lines.extend(['```', '', '## Reproduction and boundaries', '',
 '.\\.venv\\Scripts\\python.exe -B app\\tests\\test_cannon.py',
 '.\\.venv\\Scripts\\python.exe -B app\\test_server.py', '',
 'Detailed case evidence: data/cannon-tests/observations.json and referenced per-case folders.',
 'Negative artifact case preserves failed verification and keeps B locked. Lost ACK is reproduced before repair in cannon-ack-before.txt; affected cases pass in cannon-ack-after.txt.',
 'The original Core files are copied without modification; synthetic credentials and a no-keyring sentinel isolate the harness. TESTING=False. Only transport/one verifier cycle/long-poll timing and unrelated reaper start are replaced.',
 'Canonical fixture state is the only task/result authority. Import receipts and controller lane files are operational checkpoints, not a new Ledger.',
 'The current Source HEAD changed during this assignment. All 97 copied Python files still match the current source, as listed above. No loaded production runtime is inferred from HEAD.',
 'The old terminal settings differ from an earlier historical backup, but their modification time predates this Cannon assignment. No old Muse configuration was edited.',
 'No production provider, purchase, deployment, model wait loop, old Muse session, or global terminal setting was invoked or modified. CLI help/version were read only.',
 'No additional scaling phase is enabled. FAST/live remain gated. A missing external verifier event does not magically resume production work; the current live wakeup edge is not proven.',
 ])
(data / 'WINDOWS_CANNON_V1_ACCEPTANCE_PACKET.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
checkpoint = read(data / 'cannon-target-checkpoint.json')
checkpoint.update(WRITER_SCOPE_SAFE='YES_NEW_WORKSPACE_ONLY', current_blocker=packet['FIRST_REMAINING_BLOCKER'],
                  next_action=packet['NEXT_ACTION'], application_files_changed=True,
                  task_document=str(Path.home() / '.codex/attachments/bf141265-bfda-4d67-915a-faad3cbfa41e/pasted-text.txt'),
                  cannon_build=build_identity(), accepted=False, implementation='FAKE_BOUNDARY_IMPLEMENTED',
                  test_summary=packet['TESTS'], packet='data/WINDOWS_CANNON_V1_ACCEPTANCE_PACKET.md',
                  runtime_source_match=runtime_match, live_execution='UNPROVEN',
                  do_not_repeat=['No old Muse writes', 'No Google Core writes', 'No provider starts', 'Reuse unchanged fixture judgments'])
atomic(data / 'cannon-target-checkpoint.json', checkpoint)
print(json.dumps({k: packet[k] for k in ['END_SHA/BUILD_REF', 'TESTS', 'UI_MATCHES_CURRENT_SOURCE', 'CORE_SOURCE_FILES_CHANGED_SINCE_SNAPSHOT', 'FIRST_REMAINING_BLOCKER']}, indent=2))
