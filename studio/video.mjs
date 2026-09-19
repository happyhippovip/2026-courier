import {scenes, filmFrame, formatTime, cannonView} from './video-model.mjs';
const $ = id => document.getElementById(id);
let running=false, elapsed=0, duration=90, lastTime=0, frameId=0, sceneIndex=-1, selected='muse', snapshot=null, reading=false;
let telemetry={fresh:false,status:'Live-Quelle nicht verbunden',task:'Keine aktuelle Muse-Aufgabe gemeldet.'};
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
let live=cannonView(null), pollTimer;
let previousState='UNKNOWN';
document.body.classList.add('ambient-on');

function renderLive() {
  $('film-state').textContent=live.live?`LIVE STATUS · ${live.label}`:live.label;
  if(live.live){
    $('scene-title').textContent=live.label;
    $('ticker-text').textContent=`LIVE STATUS / ${live.label} · ${live.task} · ${live.provenance}`;
    $('detail-scene').textContent=selected==='muse'?`Cannon: ${live.label}`:'Nicht angebunden';
  }
}

function renderDetail() {
  const muse=selected==='muse';
  $('detail-tag').textContent=muse?'MUSE':selected.toUpperCase();
  $('detail-name').textContent=muse?'Muse im Mittelpunkt.':`${selected==='codex'?'Codex':'Google'} · nicht eingebunden`;
  $('detail-description').textContent=muse?'Der Bot zeigt den Ablauf im Video. Tatsächliche Arbeit erscheint nur mit aktueller lokaler Telemetrie.':'Dieser Worker ist in dieser Präsentationsansicht nicht angeschlossen. Ein Klick startet weder ein Modell noch einen Prozess.';
  $('detail-scene').textContent=muse?(running?scenes[Math.max(0,sceneIndex)].detail:'Animation pausiert · keine Task-Ausführung'):'Kein Video-Worker aktiv';
  $('real-task').textContent=muse?telemetry.task:'Keine Telemetrie angebunden.';
  $('source-status').className=muse&&telemetry.fresh?'fresh':'';
  $('source-status').replaceChildren();
  const dot=document.createElement('i');
  $('source-status').append(dot,document.createTextNode(muse?telemetry.status:'Nicht eingebunden'));
  renderLive();
}
function selectWorker(worker) {
  selected=worker;
  document.querySelectorAll('[data-worker]').forEach(button=>{
    const active=button.dataset.worker===worker;
    button.classList.toggle('selected',active);button.setAttribute('aria-pressed',String(active));
  });
  renderDetail();
  $('detail-panel').classList.remove('highlight');
  void $('detail-panel').offsetWidth;
  $('detail-panel').classList.add('highlight');
  const detailBounds=$('detail-panel').getBoundingClientRect();
  if (detailBounds.bottom>innerHeight || detailBounds.top<0) $('detail-panel').scrollIntoView({behavior:reducedMotion.matches?'instant':'smooth',block:'nearest'});
}
function draw() {
  const frame=filmFrame(elapsed,duration);
  $('muse-bot').style.left=`${frame.x}%`;
  $('muse-bot').style.top=`${frame.y}%`;
  $('progress').style.width=`${frame.progress*100}%`;
  $('elapsed').textContent=formatTime(elapsed%duration);
  if (frame.scene!==sceneIndex) {
    sceneIndex=frame.scene;
    $('chapter-no').textContent=`0${sceneIndex+1} / 04`;
    $('scene-title').textContent=scenes[sceneIndex].title;
    $('timeline-caption').textContent=`Szene ${sceneIndex+1} · ${scenes[sceneIndex].label}`;
    $('ticker-text').textContent=`PRÄSENTATION / ${scenes[sceneIndex].text}  ·  MUSE im Fokus. Keine Modellaufrufe. Keine Steuerung von Cannon.  ·  ${scenes[sceneIndex].text}`;
    document.querySelectorAll('[data-scene]').forEach(node=>node.classList.toggle('selected',Number(node.dataset.scene)===sceneIndex));
    document.querySelectorAll('[data-chapter]').forEach(node=>node.classList.toggle('selected',Number(node.dataset.chapter)===sceneIndex));
    renderDetail();
  }
}
function tick(time) {
  if (!running) return;
  if (!lastTime) lastTime=time;
  const delta=time-lastTime;
  if (delta>=33) {elapsed+=Math.min(delta,100)/1000;lastTime=time;draw();}
  frameId=requestAnimationFrame(tick);
}
function setRunning(value) {
  running=value;
  document.body.classList.toggle('is-playing',value);
  $('play-label').textContent=value?'Video pausieren':'Video starten';
  $('play-icon').textContent=value?'Ⅱ':'▶';
  $('film-state').textContent=value?'FILM LÄUFT · ENDLOSSCHLEIFE':'VIDEO PAUSIERT';
  $('play').setAttribute('aria-pressed',String(value));
  cancelAnimationFrame(frameId);lastTime=0;
  if (value&&!document.hidden) frameId=requestAnimationFrame(tick);
  renderDetail();
}
async function readTelemetry() {
  if (reading) return;
  reading=true;$('refresh-data').disabled=true;
  try {
    // Read-only, same-origin existing source. No Cannon/Muse/provider API.
    const response=await fetch('/video-status',{cache:'no-store',signal:AbortSignal.timeout(3500)});
    if (!response.ok) throw Error('unavailable');
    snapshot=await response.json();
  } catch {
    snapshot=null;
  } finally {
    live=cannonView(snapshot);
    const raw=snapshot?.cannon?.state?.status;
    const normalized=live.live&&['RUNNING','PAUSED','IDLE','WAITING','COMPLETED','ERROR','UNKNOWN'].includes(raw)?raw:'UNKNOWN';
    document.body.classList.toggle('just-completed',normalized==='COMPLETED'&&previousState!=='COMPLETED');
    if(normalized!==previousState)console.info('VIDEO STATE:',normalized);
    previousState=normalized;
    telemetry={fresh:live.live,status:live.live?'LIVE STATUS · '+live.label:live.label,task:live.task};
    for(const id of ['play','restart','duration'])$(id).disabled=live.live;
    setRunning(live.moving);
    reading=false;$('refresh-data').disabled=false;renderDetail();
    clearTimeout(pollTimer);
    if(!document.hidden)pollTimer=setTimeout(readTelemetry,5000);
  }
}
$('play').addEventListener('click',()=>setRunning(!running));
$('restart').addEventListener('click',()=>{elapsed=0;sceneIndex=-1;draw();setRunning(true)});
$('duration').addEventListener('change',()=>{duration=Number($('duration').value);elapsed=0;sceneIndex=-1;$('duration-label').textContent=formatTime(duration);draw();});
$('muse-bot').addEventListener('click',()=>selectWorker('muse'));
document.querySelectorAll('[data-worker]').forEach(button=>button.addEventListener('click',()=>selectWorker(button.dataset.worker)));
document.querySelectorAll('[data-scene]').forEach(button=>button.addEventListener('click',()=>{elapsed=Number(button.dataset.scene)*duration/4;draw();}));
$('refresh-data').addEventListener('click',readTelemetry);
$('fullscreen').addEventListener('click',async()=>{
  try {if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}
  catch {$('fullscreen').title='Bitte das Browserfenster manuell maximieren';}
});
document.addEventListener('visibilitychange',()=>{cancelAnimationFrame(frameId);clearTimeout(pollTimer);lastTime=0;if(!document.hidden)readTelemetry();});
draw();renderDetail();readTelemetry();
