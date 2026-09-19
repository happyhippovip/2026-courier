import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkScript, CONTRACT, INTERVAL_MS, REQUEST_TIMEOUT_MS} from './controller.mjs';

function clock() {
  let now = 1_000_000, serial = 0;
  const timers = new Map();
  return {now:()=>now, timers,
    setTimer(fn, delay){const id=++serial;timers.set(id,{fn,at:now+delay});return id;},
    clearTimer(id){timers.delete(id);},
    async advance(ms){now+=ms;for(const [id,t] of [...timers])if(t.at<=now){timers.delete(id);t.fn();}
      for(let i=0;i<30;i++)await Promise.resolve();}
  };
}
function fixture(options={}) {
  const c=clock(), data=new Map();let calls=0, reads=0, held=false;
  const grant={operation_id:'op1',goal_id:'goal-existing',task_id:'task-existing',attempt_id:'attempt1',
    fingerprint:'fp1',session_id:'session-existing',runtime_id:'process-existing',lease_token:'opaque',
    expires_at:10_000_000,session_idle:true,scope_owned:true,allowed:true,cost_authorized:true,human_gate:false};
  const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)};
  const lock=async fn=>{if(held)return fn(false);held=true;try{return await fn(true);}finally{held=false;}};
  const adapter={contract:CONTRACT,async inspect(){reads++;return {contract:CONTRACT,status:'READY',grant};},
    async submit(){calls++;return {status:'ACCEPTED',operation_id:grant.operation_id,task_id:grant.task_id,session_id:grant.session_id};}};
  const create=extra=>new WorkScript({adapter,storage,lock,now:c.now,setTimer:c.setTimer,clearTimer:c.clearTimer,
    prompt:'approved bounded work',...extra});
  return {c,data,grant,storage,adapter,create,get calls(){return calls;},get reads(){return reads;},w:create(options)};
}

test('OFF performs no checks; start waits 120s; repeated start has one timer',async()=>{
  const f=fixture();await f.c.advance(INTERVAL_MS*2);assert.equal(f.reads,0);
  f.w.start();f.w.start();assert.equal(f.c.timers.size,1);
  await f.c.advance(INTERVAL_MS-1);assert.equal(f.calls,0);
  await f.c.advance(1);assert.equal(f.calls,1);assert.equal(f.w.state.status,'SENT');
});
test('2-second visual interval does not send prompts',async()=>{
  const f=fixture();f.w.start();await f.c.advance(2000);assert.equal(f.calls,0);assert.equal(f.reads,0);
});
test('explicit check and OFF/ON cannot leave an early stale timer',async()=>{
  const f=fixture();f.w.start();const stale=[...f.c.timers.values()][0].fn;
  await f.w.tick();assert.equal(f.c.timers.size,1);
  await f.c.advance(60_000);f.w.stop();f.w.start();
  const reads=f.reads;stale();await f.c.advance(60_000);
  assert.equal(f.reads,reads);assert.equal(f.c.timers.size,1);
  await f.c.advance(60_000);assert.equal(f.reads,reads+1);
});
test('stop cancels future checks and preserves accepted work',async()=>{
  const f=fixture();f.w.start();await f.w.tick();f.w.stop();await f.c.advance(INTERVAL_MS*3);
  assert.equal(f.calls,1);assert.equal(f.w.state.status,'OFF');
});
test('no attached adapter blocks start',()=>{
  const f=fixture({adapter:null});f.w.start();assert.equal(f.w.state.status,'NOT_CONNECTED');assert.equal(f.c.timers.size,0);
});
test('no lock or storage fails closed',()=>{
  for(const x of [{lock:null},{storage:null}]){const f=fixture(x);f.w.start();assert.equal(f.w.enabled,false);}
});
test('busy session never receives input',async()=>{
  const f=fixture();f.adapter.inspect=async()=>({contract:CONTRACT,status:'BUSY'});
  f.w.start();await f.w.tick();assert.equal(f.calls,0);assert.equal(f.w.state.status,'BUSY');
});
test('IDLE stops checks and does not claim DONE',async()=>{
  const f=fixture();f.adapter.inspect=async()=>({contract:CONTRACT,status:'IDLE'});
  f.w.start();await f.w.tick();assert.equal(f.w.state.status,'IDLE');assert.equal(f.w.enabled,false);assert.equal(f.calls,0);
});
test('permission, scope, budget, human gate, busy flag and expiry all deny input',async()=>{
  for(const change of [{allowed:false},{scope_owned:false},{cost_authorized:false},{human_gate:true},
    {session_idle:false},{expires_at:1},{session_id:''},{lease_token:''},{runtime_id:''},{attempt_id:''}]){
    const f=fixture();Object.assign(f.grant,change);f.w.start();await f.w.tick();
    assert.equal(f.calls,0);assert.equal(f.w.state.status,'BLOCKED_AUTHORITY');
  }
});
test('unchanged work and repeated operation are not submitted again',async()=>{
  const f=fixture();f.w.start();await f.w.tick();await f.w.tick();
  f.grant.operation_id='unnecessary-new-operation';await f.w.tick();assert.equal(f.calls,1);assert.equal(f.w.state.status,'UNCHANGED');
});
test('new authorized task proceeds without human relay',async()=>{
  const f=fixture();f.w.start();await f.c.advance(INTERVAL_MS);
  f.grant.task_id='task-B';f.grant.operation_id='op-B';f.grant.fingerprint='fp-B';
  await f.c.advance(INTERVAL_MS);assert.equal(f.calls,2);
});
test('cross-tab lock and journal give one submission',async()=>{
  const f=fixture(), other=f.create();f.w.start();other.start();
  await Promise.all([f.w.tick(),other.tick()]);await other.tick();assert.equal(f.calls,1);
});
test('restart begins OFF; manual enable still suppresses accepted repeat',async()=>{
  const f=fixture();f.w.start();await f.w.tick();f.w.stop();const next=f.create();
  assert.equal(next.enabled,false);next.start();await next.tick();assert.equal(f.calls,1);
});
test('ambiguous send persists PENDING and is not replayed after restart',async()=>{
  const f=fixture();let sends=0;f.adapter.submit=async()=>{sends++;throw Error('connection lost after send');};
  f.w.start();await f.w.tick();const next=f.create();next.start();await next.tick();
  assert.equal(sends,1);assert.equal(next.state.status,'BLOCKED_UNCONFIRMED');
});
test('mismatching receipt cannot claim delivery or be retried',async()=>{
  const f=fixture();f.adapter.submit=async()=>({status:'ACCEPTED',operation_id:'other'});
  f.w.start();await f.w.tick();assert.equal(f.w.state.status,'BLOCKED_UNCONFIRMED');assert.equal(f.w.state.lastReceipt,null);
});
test('REJECTED remains blocked',async()=>{
  const f=fixture();f.adapter.submit=async()=>({status:'REJECTED',operation_id:f.grant.operation_id,
    task_id:f.grant.task_id,session_id:f.grant.session_id});
  f.w.start();await f.w.tick();assert.equal(f.w.state.status,'BLOCKED_REJECTED');
});
test('storage failure before sending results in zero dispatch',async()=>{
  const f=fixture();f.storage.setItem=()=>{throw Error('quota');};f.w.start();await f.w.tick();assert.equal(f.calls,0);
});
test('malformed journal fails closed',async()=>{
  const f=fixture();f.data.set('courier.work-script.v1','{"x":"fabricated"}');
  f.w.start();await f.w.tick();assert.equal(f.calls,0);assert.equal(f.w.enabled,false);
});
test('stop during inspect prevents late submission',async()=>{
  const f=fixture();let finish;f.adapter.inspect=()=>new Promise(resolve=>{finish=resolve;});
  f.w.start();const pending=f.w.tick();await Promise.resolve();await Promise.resolve();f.w.stop();
  finish({contract:CONTRACT,status:'READY',grant:f.grant});await pending;assert.equal(f.calls,0);
});
test('hung inspect is bounded with no model retry',async()=>{
  const f=fixture();f.adapter.inspect=()=>new Promise(()=>{});f.w.start();const pending=f.w.tick();
  await Promise.resolve();await f.c.advance(REQUEST_TIMEOUT_MS);await pending;
  assert.equal(f.w.enabled,false);assert.equal(f.calls,0);
});
test('journal stores no lease tokens or prompt text',async()=>{
  const f=fixture();f.w.start();await f.w.tick();const raw=[...f.data.values()].join('');
  assert.equal(raw.includes('opaque'),false);assert.equal(raw.includes('approved bounded work'),false);
});
