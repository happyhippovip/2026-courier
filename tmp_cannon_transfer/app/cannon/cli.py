"""Local controls and explicitly isolated demo. No production/provider start."""
import argparse
import json
import os
import sys
from pathlib import Path
from .adapters import FakeAdapter
from .controller import Controller, resource_state
from .importer import Importer
from .storage import ROOT, InstanceLock, atomic, digest, file_hash, owned, read

def build_identity():
    files = sorted((ROOT / 'app/cannon').glob('*.py')) + [ROOT / name for name in
             ['app/server.py', 'app/cannon.html', 'app/cannon.js', 'app/cannon.css',
              'app/tests/cannon_support.py', 'data/cannon-tests/core-source-manifest.json',
              'Courier Cannon V1.cmd']]
    return digest({str(p.relative_to(ROOT)): file_hash(p) for p in files})


# Each candidate gets its own explicit fake fixture. Prior evidence is retained.
# Within that candidate, Start/Resume reuse one canonical goal and checkpoint.
DEMO = owned(os.environ.get('CANNON_DEMO_DIR', str(ROOT / 'data/cannon-demo' / build_identity())))


def demo(count, mode, max_starts=None, initialize_control=True):
    sys.path.insert(0, str(ROOT / 'app/tests'))
    from cannon_support import CORE_FIXTURE_ID, CORE_MANIFEST, SNAPSHOT, IsolatedCore, load_core, snapshot, step
    with InstanceLock(DEMO / 'owner'):
        manifest = read(DEMO / 'session.json')
        candidate = build_identity()
        if manifest and manifest['cannon_build'] != candidate:
            raise ValueError('Demo build changed; archive its owned evidence before a new demo')
        snapshot()  # Validate the frozen fixture on every launch, including resume.
        if not manifest:
            manifest = {'cannon_build': candidate, 'core_manifest': file_hash(CORE_MANIFEST),
                        'core_fixture_id': CORE_FIXTURE_ID, 'core_fixture_policy': 'PINNED_LOCAL_ONLY_NOT_LIVE_CORE_ACCEPTANCE',
                        'mode': mode, 'count': count, 'kind': 'ISOLATED_FAKE_ONLY'}
            atomic(DEMO / 'session.json', manifest)
        elif mode != manifest['mode'] or count != manifest['count']:
            raise ValueError('Resume must retain the original demo count and mode')
        elif manifest.get('core_fixture_id') != CORE_FIXTURE_ID or manifest['core_manifest'] != file_hash(CORE_MANIFEST):
            raise ValueError('Demo Core fixture changed; previous evidence preserved')
        workspace = owned(DEMO / 'workspace'); workspace.mkdir(parents=True, exist_ok=True)
        os.chdir(workspace)
        api, verifier = load_core()
        core = IsolatedCore(api, verifier, DEMO / 'core')
        adapter = FakeAdapter(SNAPSHOT / 'scripts/integration_contract.py', workspace)
        try:
            if not manifest.get('goal_id'):
                source = DEMO / 'tasks.jsonl'
                records = [{'id': 'demo-' + str(i), 'kind': 'TASK', 'task': step('demo-' + str(i), fake_delay=.4)} for i in range(count)]
                source.write_text('\n'.join(json.dumps(r) for r in records) + '\n', encoding='utf-8')
                importer = Importer(DEMO / 'import')
                importer.ingest(source, 'demo')
                receipt = importer.submit_authorized([(r['id'], digest(r)) for r in records], core, 'explicit-demo-start')
                manifest['goal_id'] = receipt['goal_id']; atomic(DEMO / 'session.json', manifest)
            core.goal_ids = [manifest['goal_id']]
            controller = Controller(DEMO / 'controller', core, adapter, mode=mode, resources=resource_state)
            # Web controls are persisted before GO; preserve an early Pause/Stop.
            if initialize_control:
                controller.control('RESUME')
            state = controller.run(max_starts=max_starts)
            atomic(DEMO / 'outcome.json', {'kind': 'FAKE_CORE_FIXTURE', 'controller': state,
                                          'live_muse': 'UNPROVEN', 'independent_acceptance': 'PENDING'})
            print(json.dumps(state, indent=2))
            return 0 if state['status'] in {'IDLE', 'PAUSED'} else 2
        finally:
            adapter.close(); core.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Cannon V1: isolated local fake test only')
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('demo'); run.add_argument('--count', type=int, choices=[5, 10], default=5)
    run.add_argument('--mode', choices=['NORMAL'], default='NORMAL')
    run.add_argument('--gated', action='store_true')
    run.add_argument('--max-starts', type=int)
    sub.add_parser('status')
    for control in ['pause', 'stop-after-current']: sub.add_parser(control)
    ingest = sub.add_parser('import'); ingest.add_argument('path'); ingest.add_argument('--import-id')
    args = parser.parse_args(argv)
    if args.action == 'demo':
        if args.gated and os.read(0, 3) != b'GO\n': return 3
        try:
            return demo(args.count, args.mode, args.max_starts, initialize_control=not args.gated)
        except Exception as exc:
            atomic(DEMO / 'error.json', {'error': type(exc).__name__ + ': ' + str(exc)[:500]})
            raise
    if args.action == 'status':
        print(json.dumps(read(DEMO / 'controller/controller.json', {'status': 'NOT_STARTED'}), indent=2)); return 0
    if args.action == 'import':
        print(json.dumps(Importer(ROOT / 'data/cannon-import').ingest(args.path, args.import_id), indent=2)); return 0
    atomic(DEMO / 'controller/control.json', {'action': 'PAUSE' if args.action == 'pause' else 'STOP_AFTER_CURRENT'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
