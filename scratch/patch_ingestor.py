import os

WORKSPACE_ROOT = r'C:\Users\lol\2026-workspace'
filepath = os.path.join(WORKSPACE_ROOT, 'courier', 'chief', 'ingestor.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        self.control_plane.upsert_task(
            task_id=task_id,
            assignment_id=assignment_id,
            origin_lane=origin_lane,
            status=TaskStatus.COMPLETED if is_completed else TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(
                local_step_erledigt=local_step_done,
                gesamtaufgabe_erledigt=gesamtaufgabe_done,
                blocker=blocker,
                next_step=next_task
            ),
            active_agent=origin_lane.value,
            canonical_fingerprint=canonical_fingerprint
        )'''

replacement = '''        try:
            self.control_plane.upsert_task(
                task_id=task_id,
                assignment_id=assignment_id,
                origin_lane=origin_lane,
                status=TaskStatus.COMPLETED if is_completed else TaskStatus.RUNNING,
                two_level_done=TwoLevelDone(
                    local_step_erledigt=local_step_done,
                    gesamtaufgabe_erledigt=gesamtaufgabe_done,
                    blocker=blocker,
                    next_step=next_task
                ),
                active_agent=origin_lane.value,
                canonical_fingerprint=canonical_fingerprint
            )
        except RuntimeError as e:
            if "Terminal Mutation Rejected" in str(e) or "Terminal Legacy Mutation Rejected" in str(e) or "Conflict" in str(e):
                pass
            else:
                raise'''

if target in content:
    content = content.replace(target, replacement)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Patched ingestor.py successfully!')
else:
    print('Target not found in ingestor.py!')
