import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkScript, CONTRACT, INTERVAL_MS, REQUEST_TIMEOUT_MS} from './controller.mjs';

// Local replacement transport: 503 sequences without any provider call.
// Each case owns an isolated clock and an isolated journal (own tmp state).
// Real test events (submit attempts, journal entries) are counted;
// nothing is set to success outside the controller under test.
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
function transportFixture({submit}) {
  const c=clock(), data=new Map(); let sends=0; const attempts=[];
  const grant={operation_id:'op-t1',goal_id:'goal-t',task_id:'task-t',attempt_id:'attempt1',
    fingerprint:'fp-t',session_id:'session-t',runtime_id:'process-t',lease_token:'opaque',
    expires_at:10_000_000,session_idle:true,scope_owned:true,allowed:true,cost_authorized:true,human_gate:false};
  const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)};
  const lock=async fn=>fn(true);
  const adapter={contract:CONTRACT,
    async inspect(){return {contract:CONTRACT,status:'READY',grant};},
    async submit(args){sends++;attempts.push(args.grant.operation_id);return submit(args);}};
  const create=extra=>new WorkScript({adapter,storage,lock,now:c.now,setTimer:c.setTimer,clearTimer:c.clearTimer,
    prompt:'approved bounded work',...extra});
  const journal=()=>JSON.parse(data.get('courier.work-script.v1')??'{}');
  return {c,data,grant,storage,adapter,create,journal,get sends(){return sends;},get attempts(){return attempts;},w:create()};
}
const okReceipt=g=>({status:'ACCEPTED',operation_id:g.operation_id,task_id:g.task_id,session_id:g.session_id});

test('transient 503: ambiguous op is not blindly retried; recovery needs reconciliation',async()=>{
  let fail=true;
  const f=transportFixture({submit:async args=>{if(fail)throw Error('503 Service Unavailable');return okReceipt(args.grant);}});
  f.w.start();await f.w.tick();
  assert.equal(f.w.state.status,'BLOCKED_CHECK_OR_DELIVERY');
  assert.equal(f.sends,1);
  const key1=JSON.stringify(['goal-t','task-t','attempt1','fp-t']);
  assert.equal(f.journal()[key1],'PENDING');
  const next=f.create();next.start();await next.tick(); // recovered transport, same journal
  assert.equal(next.state.status,'BLOCKED_UNCONFIRMED');
  assert.equal(f.sends,1); // no blind retry of the ambiguous op
  // Current behavior: one unreconciled PENDING wedges even new work.
  fail=false;
  f.grant.operation_id='op-t2';f.grant.task_id='task-t2';f.grant.fingerprint='fp-t2';
  const wedged=f.create();wedged.start();await wedged.tick();
  assert.equal(wedged.state.status,'BLOCKED_UNCONFIRMED');
  assert.equal(f.sends,1);
  // Documented recovery path (README): owner reconciles op1 externally first.
  const raw=JSON.parse(f.data.get('courier.work-script.v1'));raw[key1]='REJECTED';
  f.data.set('courier.work-script.v1',JSON.stringify(raw));
  const third=f.create();third.start();await third.tick();
  assert.equal(third.state.status,'SENT');
  assert.equal(f.sends,2);
  assert.equal(f.journal()[JSON.stringify(['goal-t','task-t2','attempt1','fp-t2'])],'ACCEPTED');
});

test('permanent 503 fails closed with a bounded single attempt',async()=>{
  const f=transportFixture({submit:async()=>{throw Error('503 Service Unavailable');}});
  f.w.start();await f.w.tick();
  assert.equal(f.w.state.status,'BLOCKED_CHECK_OR_DELIVERY');
  assert.equal(f.w.enabled,false);
  assert.equal(f.sends,1);
  await f.c.advance(INTERVAL_MS*5); // stopped controller schedules nothing further
  assert.equal(f.sends,1);
  assert.equal(f.c.timers.size,0);
});

test('abort after partial output keeps PENDING and records no success',async()=>{
  const f=transportFixture({submit:async args=>({status:'ACCEPTED',operation_id:args.grant.operation_id})}); // truncated: no session/task binding
  f.w.start();await f.w.tick();
  assert.equal(f.w.state.status,'BLOCKED_UNCONFIRMED');
  assert.equal(f.w.state.lastReceipt,null);
  assert.deepEqual(Object.values(f.journal()),['PENDING']);
  const next=f.create();next.start();await next.tick();
  assert.equal(f.sends,1); // retained PENDING is not replayed after restart
  assert.equal(next.state.status,'BLOCKED_UNCONFIRMED');
});
