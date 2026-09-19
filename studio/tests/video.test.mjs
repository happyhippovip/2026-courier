import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import * as model from '../video-model.mjs';
import {filmFrame,museTelemetry,formatTime,cannonView} from '../video-model.mjs';
test('90s and 180s loop without leaving the HQ',()=>{
  for(const duration of [90,180])for(let t=0;t<duration*3;t+=.5){
    const f=filmFrame(t,duration);assert(f.x>=14&&f.x<=80);assert(f.y>=49&&f.y<=83);assert(f.scene>=0&&f.scene<=3);
  }
  assert.deepEqual(filmFrame(0,90),filmFrame(90,90));
  assert.notDeepEqual(filmFrame(0,90),filmFrame(10,90));
});
test('four deterministic scenes and readable timer',()=>{
  assert.deepEqual([0,23,46,69].map(t=>filmFrame(t,90).scene),[0,1,2,3]);
  assert.equal(formatTime(90),'01:30');assert.equal(formatTime(180),'03:00');
});
const now=Date.parse('2026-09-19T10:00:00Z');
const local=(age,status='COMPUTING')=>({observed_at:new Date(now-age).toISOString(),tools:{muse:{status}}});
test('absent, stale, future or unknown telemetry never becomes active',()=>{
  for(const s of [null,{},local(15000),local(-5001),local(0,'MADE_UP')])assert.equal(museTelemetry(s,now).fresh,false);
});
test('CPU activity never invents a task',()=>{
  const t=museTelemetry(local(1000),now);assert(t.fresh);assert.match(t.task,/nicht gemeldet/);
});
test('only explicitly known, fresh task content is displayed',()=>{
  const s=local(0);s.tools.muse.task_known=true;s.tools.muse.current_task='Prüfe lokale Tests';
  assert.equal(museTelemetry(s,now).task,'Prüfe lokale Tests');
  s.tools.muse.task_known=false;assert.notEqual(museTelemetry(s,now).task,'Prüfe lokale Tests');
});
test('video has no provider, Cannon write API or old dashboard bootstrap',()=>{
  const js=readFileSync(new URL('../video.mjs',import.meta.url),'utf8');
  const html=readFileSync(new URL('../video.html',import.meta.url),'utf8');
  assert.doesNotMatch(js,/8768|POST|api\/cannon|api\/human|studio\.js|localStorage/);
  assert.equal((js.match(/fetch\(/g)||[]).length,1);
  assert.match(js,/fetch\('\/video-status'/);
  assert.doesNotMatch(html,/src="studio\.js/);
  assert.match(html,/ABLAUFVISUALISIERUNG/);
});
test('Cannon statuses control motion without inventing work',()=>{
  for(const [status,label] of Object.entries({RUNNING:'ARBEITET',PAUSED:'PAUSIERT',IDLE:'WARTET',WAITING:'WARTET',COMPLETED:'FERTIG',ERROR:'BRAUCHT DICH',UNKNOWN:'BRAUCHT DICH',RECONCILE_REQUIRED:'BRAUCHT DICH',BOGUS:'BRAUCHT DICH'})){
    const view=cannonView({available:true,observed_at:new Date(now).toISOString(),cannon:{state:{status},session:{mode:'BEGRENZT',count:999991}}},now);
    assert.equal(view.label,label);assert.equal(view.moving,status==='RUNNING');assert.equal(view.remaining,'999991');
  }
});
test('unavailable/stale status falls back; fresh status automatically recovers',()=>{
  assert.equal(cannonView(null,now).live,false);
  const packet={available:true,observed_at:new Date(now).toISOString(),cannon:{live_muse:'UNPROVEN',state:{status:'RUNNING',metrics:{DONE:73}},session:{mode:'UNENDLICH',count:1000000}}};
  assert.equal(cannonView(packet,now+15000).live,false);
  const view=cannonView(packet,now);assert(view.live);assert.equal(view.remaining,'∞');assert.equal(view.done,'73');assert.match(view.provenance,/UNPROVEN/);
});
test('actual controller: idle, run, pause, resume, refresh without Cannon writes',async()=>{
  const nodes=new Map(),classes=new Set();let callback,packet;
  const node=id=>{if(!nodes.has(id))nodes.set(id,{style:{},classList:{toggle(){},add(){},remove(){}},after(){},append(){},replaceChildren(){},addEventListener(){},setAttribute(){},value:'90'});return nodes.get(id);};
  const context={...model,console,Date,AbortSignal,matchMedia:()=>({matches:false}),
    document:{hidden:false,body:{classList:{add:x=>classes.add(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)}},getElementById:node,createElement:()=>node('generated'+nodes.size),createTextNode:x=>x,querySelector:node,querySelectorAll:()=>[],addEventListener(){}},
    fetch:async()=>({ok:true,json:async()=>packet}),requestAnimationFrame:fn=>{callback=fn;return 1;},cancelAnimationFrame:()=>{callback=null;},setTimeout:()=>1,clearTimeout(){},setInterval(){}};
  const sandbox=vm.createContext(context);
  const source=readFileSync(new URL('../video.mjs',import.meta.url),'utf8').replace(/^import .*;\n/,'').replace('draw();renderDetail();readTelemetry();','draw();renderDetail();');
  vm.runInContext(source,sandbox);
  for(const state of ['IDLE','RUNNING','PAUSED','RUNNING','COMPLETED','UNKNOWN']){
    packet={available:true,observed_at:new Date().toISOString(),cannon:{state:{status:state}}};
    await vm.runInContext('readTelemetry()',sandbox);
    assert(classes.has('ambient-on'));
    assert.equal(classes.has('is-playing'),state==='RUNNING');
    assert.equal(typeof callback==='function',state==='RUNNING');
    if(state==='RUNNING'){callback(100);callback(200);assert.match(node('muse-bot').style.left,/%/);}
  }
  const css=readFileSync(new URL('../video.css',import.meta.url),'utf8');
  assert.match(css,/\.ambient-on \.water i\{animation:ripple/);
  assert.doesNotMatch(css,/animation:none!important/);
});
