import json
import pytest
from scripts.cannon_motor import CannonMotor
from app.cannon.adapters import LiveMuseAdapter

def test_real_selects_adapter_and_failure_stops_next(tmp_path, monkeypatch):
    m=CannonMotor(tmp_path)
    m._wq('init','canary')
    for i in range(2):
        m._wq('add',json.dumps(dict(task_id='real-'+str(i),package_id='canary',description='canary',dependencies=[],read_scopes=[],write_scopes=['canary'],status='READY',executor_kind='REAL_MUSE')))
    calls=[]
    def denied(task, folder, persist):
        calls.append(task['task_id'])
        raise ValueError('MISSING_TERMINAL_RESULT')
    monkeypatch.setattr(LiveMuseAdapter,'execute_canary',denied)
    m.start(mode='FINITE',limit=2,cooldown=0)
    assert m.run_step()['step']=='error'
    assert m.run_step()['step']=='noop'
    assert calls==['real-0']
    assert m.m['done_count']==0
    assert m.queue_snapshot()['tasks']['real-1']['status']=='READY'

@pytest.mark.parametrize('provider',['echo','fake','mock'])
def test_fake_provider_rejected(provider,tmp_path):
    with pytest.raises(ValueError,match='UNSUPPORTED_REAL_PROVIDER'):
        LiveMuseAdapter.execute_canary({'provider':provider},tmp_path,lambda x:None)

def test_legacy_exit_success_disabled():
    with pytest.raises(ValueError,match='LEGACY_EXIT_ONLY'):
        LiveMuseAdapter.execute(None,{},None,None)

def test_terminal_answer_not_prompt_echo():
    answer={'path':'/tmp/a','nonce':'abc','sha256':'123'}
    good={'payload_type':'run.terminal.completed','payload':{'terminal':'completed','text':json.dumps(answer)}}
    assert LiveMuseAdapter.validate_canary_terminal([good],'/tmp/a','abc','123')==answer
    for events in [[],[good,good],[{'payload_type':'prompt','payload':answer}],
                   [dict(good,payload={'terminal':'completed','text':'{}'})]]:
        with pytest.raises(ValueError):
            LiveMuseAdapter.validate_canary_terminal(events,'/tmp/a','abc','123')

def test_terminal_non_dict_events_fail_closed():
    # Garbage JSONL lines (non-dict events, non-dict payload, non-str text)
    # must fail closed with ValueError so the motor contains the fault as
    # BLOCKED+review instead of wedging on an uncaught AttributeError/TypeError.
    good={'payload_type':'run.terminal.completed',
          'payload':{'terminal':'completed','text':json.dumps({'path':'/tmp/a','nonce':'abc','sha256':'123'})}}
    for events in [['oops'],[42],[None],[[1,2]],
                   [dict(good,payload='garbage')],
                   [dict(good,payload={'terminal':'completed','text':42})]]:
        with pytest.raises(ValueError):
            LiveMuseAdapter.validate_canary_terminal(events,'/tmp/a','abc','123')
    # Noise alongside one valid terminal still validates.
    assert LiveMuseAdapter.validate_canary_terminal(
        ['oops',42,None,good],'/tmp/a','abc','123')=={'path':'/tmp/a','nonce':'abc','sha256':'123'}
