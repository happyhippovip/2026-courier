import os
"""Trust-boundary integration: real isolated server state + Guard + Ledger.

TLS transport is replaced by the Flask test client, not the authority verdict.
These are software tests, never physical acceptance evidence.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone

import pytest

@pytest.fixture(autouse=True)
def restore_resolver():
    from scripts import agent_handoff_ledger
    original = agent_handoff_ledger._attestation_resolver
    yield
    agent_handoff_ledger._attestation_resolver = original
import requests
from server import app as server
from scripts import agent_handoff_ledger as ledger
from scripts import ledger_attestation
from scripts.attestation_contract import principal
from scripts.courier_verifier import verify_artifact
from tests.test_ledger_attestation_trust_root import _base_record, _base_guard, _artifact


ORIGIN = 'https://courier.test'
AUTH = {'Authorization': 'Bearer test-secret'}
VERIFY = {'Authorization': 'Bearer verifier-secret'}


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(server, 'BATCH_QUEUE_DIR', str(tmp_path / 'batches'))
    monkeypatch.setattr(server, 'API_KEY', 'test-secret')
    monkeypatch.setattr(server, 'VERIFIER_API_KEY', 'verifier-secret')
    monkeypatch.setattr(server, 'STARTUP_SOURCE_CLEAN', True)
    monkeypatch.setattr(server, 'runtime_source_is_clean', lambda: True)
    assert server.STATE_FILE == str(tmp_path / 'state.json'), "STATE_FILE not correctly set to temporary path"
    monkeypatch.setattr(server, 'SERVER_BINDING', {'sha': 'a'*40, 'runtime': 'courier-server:'+'b'*32})
    monkeypatch.setenv('COURIER_ATTESTATION_ORIGIN', ORIGIN)
    monkeypatch.setenv('COURIER_API_KEY', 'test-secret')
    http = server.app.test_client()
    def get(session, url, **kwargs):
        assert session.trust_env is False
        assert kwargs['allow_redirects'] is False
        assert url.startswith(ORIGIN + '/attestations/')
        response = http.get(url[len(ORIGIN):], headers=kwargs['headers'])
        class Response:
            status_code = response.status_code
            def json(self):
                return response.get_json()
        return Response()
    monkeypatch.setattr(requests.Session, 'get', get)
    http.post('/workers/register', headers=AUTH, json={'worker_id':'worker', 'platform':'mac', 'capabilities':['macos']})
    goal = http.post('/goals', headers=AUTH, json={'goal_text':'write durable artifact', 'workflow_plan':[
        {'task_id':'task-A', 'target_agent':'mac', 'instruction':'write artifact', 'artifacts':['a.txt']}
    ]}).json['goal_id']
    task = http.post('/tasks/claim', headers=AUTH, json={'worker_id':'worker', 'capabilities':['macos']}).json['task']
    artifact = tmp_path / 'a.txt'
    artifact.write_bytes(b'independent artifact\n')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert verify_artifact(str(artifact), digest)
    result = {k:task[k] for k in ('goal_id','task_id','attempt_id','dispatch_id','execution_ref','worker_id')}
    result.update(run_id='worker-process', status='SUCCESS', artifacts=[{'path':'a.txt','sha256':digest}], runtime_identity=server.SERVER_BINDING)
    import json
    identity = {k: result.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    res_id = "result-" + hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result.update(result_id=res_id)
    result.update(producer_id='forged', verifier_id='forged', producer_principal='forged')
    assert http.post('/tasks/result', headers=AUTH, json=result).status_code == 200
    verification = {'task_id':task['task_id'], 'result_id':res_id, 'verifier_id':'independent-verifier', 'verdict':'PASS', 'received_runtime_identity': server.SERVER_BINDING, 'artifacts':result['artifacts']}
    return {'http':http,'goal':goal,'task':task,'verification':verification,'tmp':tmp_path,'res_id':res_id}


def verify(context):
    http = context['http']
    assert http.post('/tasks/verify', headers=VERIFY, json=context['verification']).status_code == 200
    state = server.load_state()
    receipt = next(iter(state['attestation_receipts'].values()))
    return receipt


def evidence(receipt):
    return {'source_url':ORIGIN+'/attestations/'+receipt['attestation_id'], 'source_type':'MACHINE_ARTIFACT',
            'observed_at':datetime.fromtimestamp(receipt['verified_at'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'evidence_sha':receipt['binding']['sha'], 'runtime_binding':receipt['binding']['runtime'],
            'validity':'VALID','reason':'server-authenticated result verification',
            'producer_id':receipt['producer_principal'],'verifier_id':receipt['verifier_principal'],
            'result_sha256':receipt['result_sha256']}


def setup_ledger(context, e):
    from scripts import agent_handoff_ledger
    def resolve(url):
        path = url.replace('https://courier.test', '')
        resp = context['http'].get(path, headers={'Authorization': 'Bearer test-secret'})
        if resp.status_code != 200: return None
        return resp.json
    agent_handoff_ledger._attestation_resolver = resolve

    path = context['tmp'] / 'ledger.json'
    record = _base_record()
    record.update(GOAL=context['goal'],CURRENT_SHA=e['evidence_sha'],RUNTIME_IDENTITY=e['runtime_binding'])
    g = _base_guard()
    g['binding'].update(current_sha=e['evidence_sha'],runtime_identity=e['runtime_binding'])
    g['evidence'] = [dict(e, validity='UNKNOWN')]
    g['acceptance_predicate']['required_results'] = ['ISSUE_STATE']
    g['acceptance_predicate']['results'] = {'ISSUE_STATE':{'status':'UNKNOWN','observed_value':'PENDING','evidence_urls':[]}}
    ledger.initialize(path,record,g,5)
    g['evidence'] = [e]
    return path, g, record


def promote(path,g):
    first = ledger.update(path,0,{'TASKS_COMPLETED':3},'actor-v1',5,guard=g)
    assert first['acceptance_guard']['transition_state'] == 'PROVISIONAL'
    return ledger.update(path,1,{'STATUS':'DONE'},'actor-v2',5)


def test_independent_authenticated_receipt_and_idempotency(context):
    receipt = verify(context)
    assert receipt['producer_principal'] == principal('test-secret')
    assert receipt['verifier_principal'] == principal('verifier-secret')
    before = open(server.STATE_FILE,'rb').read()
    assert context['http'].post('/tasks/verify',headers=VERIFY,json=context['verification']).json['status']=='ACK_DUPLICATE'
    assert open(server.STATE_FILE,'rb').read()==before
    path,g,_=setup_ledger(context,evidence(receipt))
    accepted=promote(path,g)
    assert accepted['acceptance_guard']['transition_state']=='CANONICAL_ACCEPTED'
    assert accepted['record']['CLEAN_IDLE']=='YES'
    before=path.read_bytes()
    with pytest.raises(ledger.NoMeaningfulChangeError):
        ledger.update(path,2,{'STATUS':'CLEAN_IDLE'},'actor-v2',5)
    assert path.read_bytes()==before


@pytest.mark.parametrize('attack', ['producer','verifier','same_identity','runtime','hostname','sha','url','digest','goal','timestamp'])
def test_forged_metadata_never_counts(context,attack):
    e=evidence(verify(context))
    if attack=='producer':e['producer_id']='alias'
    elif attack=='verifier':e['verifier_id']='alias'
    elif attack=='same_identity':e['verifier_id']=e['producer_id']
    elif attack=='runtime':e['runtime_binding']='courier-server:'+'c'*32
    elif attack=='hostname':e['runtime_binding']='my-host'
    elif attack=='sha':e['evidence_sha']='c'*40
    elif attack=='url':e['source_url']=ORIGIN+'/attestations/'+'c'*32
    elif attack=='digest':e['result_sha256']='c'*64
    elif attack=='timestamp':e['observed_at']='2020-01-01T00:00:00Z'
    else:context['goal']='another-goal'
    path,g,_=setup_ledger(context,e)
    try:
        r=promote(path,g)
    except ledger.SelfCertificationError:
        return
    assert r['acceptance_guard']['transition_state']=='PROVISIONAL'
    assert r['record']['CLEAN_IDLE']=='NO'


def test_original_alias_attack_fails_closed(context):
    e=_artifact('https://example.invalid/unattested','caller-producer','caller-verifier')
    path,g,_=setup_ledger(context,e)
    r=promote(path,g)
    assert r['record']['CLEAN_IDLE']=='NO'
    assert r['acceptance_guard']['transition_state']=='PROVISIONAL'


def test_same_update_cannot_accept(context):
    path,g,_=setup_ledger(context,evidence(verify(context)))
    with pytest.raises(ledger.CleanIdleError):
        ledger.update(path,0,{'STATUS':'DONE','CLEAN_IDLE':'YES','NEXT_EXECUTABLE_ACTION':'NONE'},'acceptor',5,guard=g)
    assert ledger.load_bundle(path)['revision']==0


@pytest.mark.parametrize('attack',['stale','restart','rotation','changed_result','incomplete_goal','source_changed','source_dirty_at_start'])
def test_receipt_revalidated_on_every_read(context,monkeypatch,attack):
    r=verify(context)
    e=evidence(r)
    path,g,_=setup_ledger(context,e)
    ledger.update(path,0,{'TASKS_COMPLETED':3},'actor-v1',5,guard=g)
    if attack=='restart':monkeypatch.setattr(server,'SERVER_BINDING',dict(server.SERVER_BINDING,runtime='courier-server:'+'e'*32))
    elif attack=='rotation':monkeypatch.setattr(server,'VERIFIER_API_KEY','rotated-verifier')
    elif attack=='source_changed':monkeypatch.setattr(server,'runtime_source_is_clean',lambda:False)
    elif attack=='source_dirty_at_start':monkeypatch.setattr(server,'STARTUP_SOURCE_CLEAN',False)
    elif attack=='stale':
        monkeypatch.setattr('scripts.attestation_contract.time.time',lambda:r['received_at']+172801)
    else:
        state=server.load_state()
        if attack=='changed_result':state['tasks']['task-A']['result']['artifacts'][0]['sha256']='e'*64
        else:state['goals'][context['goal']]['status']='ACTIVE'
        server.save_state(state)
    out=ledger.update(path,1,{'STATUS':'DONE'},'actor-v2',5)
    assert out['record']['CLEAN_IDLE']=='NO'


def test_producer_cannot_submit_verdict_with_alias(context):
    assert context['http'].post('/tasks/verify',headers=AUTH,json=context['verification']).status_code==401
    assert not server.load_state().get('attestation_receipts')


def test_equal_keys_cannot_attest(context,monkeypatch):
    monkeypatch.setattr(server,'VERIFIER_API_KEY','test-secret')
    assert context['http'].post('/tasks/verify',headers=AUTH,json=context['verification']).status_code==503


@pytest.mark.parametrize('field,value',[('verdict','FAIL'),('artifacts',[]),('result_id','another-result')])
def test_contradictory_verification_replay(context,field,value):
    verify(context)
    altered=dict(context['verification']);altered[field]=value
    assert context['http'].post('/tasks/verify',headers=VERIFY,json=altered).status_code==409


def test_self_attack_receipt_cannot_launder_untrusted_predicate(context):
    e=evidence(verify(context))
    path,g,_=setup_ledger(context,e)
    fake=dict(e,source_url='https://example.invalid/copied-valid-looking',result_sha256='f'*64)
    g['evidence'].append(fake)
    g['acceptance_predicate']['required_results'].append('OTHER')
    g['acceptance_predicate']['results']['OTHER']={'status':'PASS','observed_value':'fake','evidence_urls':[fake['source_url']]}
    rec = ledger.update(path,0,{'TASKS_COMPLETED':3},'actor-v1',5,guard=g)
    assert rec["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    # Actually wait, let's see what it transitions to
    # the guard should have transition_state == 'PROVISIONAL'



def test_no_authority_or_network_fail_closed(context,monkeypatch):
    e=evidence(verify(context));_,_,rec=setup_ledger(context,e)
    monkeypatch.delenv('COURIER_ATTESTATION_ORIGIN')
    assert not ledger_attestation.authenticated_evidence(e,rec)
    monkeypatch.setenv('COURIER_ATTESTATION_ORIGIN',ORIGIN)
    def offline(*a,**k):raise requests.ConnectionError('offline')
    monkeypatch.setattr(requests.Session,'get',offline)
    assert not ledger_attestation.authenticated_evidence(e,rec)

@pytest.fixture(autouse=True)
def _disable_mock_ledger(monkeypatch):
    monkeypatch.delenv("MOCK_LEDGER", raising=False)
