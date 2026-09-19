'use strict';
let state, current = 'Chat', draft = '', toastTimer, runStatus = '';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nav = [['Pull Requests','⑂'],['Geplant','◷'],['Projekte','▱'],['Plan','☷'],['Plugins / Integrationen','▦'],['Entdecken','◇'],['ARBEITSBEREICH'],['Bibliothek','▤'],['Prompts','▧'],['Vorlagen','▥'],['Agenten','♧'],['Ergebnisse','▣'],['Evidenz','◇'],['Einstellungen','⚙']];
const actions = [
 ['Idee umsetzen','♧','Von der Idee<br>zum Ziel','Ziel: \nGewünschtes Ergebnis: \nAkzeptanzkriterien: \nGrenzen: '],
 ['Fehler analysieren','⌕','Logs, Fehler,<br>Ursachen','Fehlerbild: \nReproduktion: \nErwartetes Verhalten: \nBetroffene Dateien: '],
 ['Projekt planen','☷','Aufgaben, Struktur,<br>nächste Schritte','Projektziel: \nAusgangslage: \nKleine Arbeitspakete: \nDefinition of Done: '],
 ['Code Review','⌘','Änderungen,<br>Tests, Risiken','Review-Ziel: \nCommit / Diff: \nPrüfschwerpunkte: \nNur lesen: ja'],
 ['Recherche','◎','Quellen, Fragen,<br>belastbare Antworten','Forschungsfrage: \nBekannte Quellen: \nGewünschtes Ergebnis: \nBudget: keine Käufe']
];
function badge(value, tone='') { return `<span class="badge ${tone}">${esc(value)}</span>`; }
function timeLabel(value){ return value ? new Date(value*1000).toLocaleString('de-DE') : 'UNKNOWN'; }
function title(h,p){return `<div class="view-title"><h1>${esc(h)}</h1><p>${esc(p)}</p></div>`;}
function empty(text){return `<div class="empty">${esc(text)}</div>`;}
function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').style.display='none',4500);}
async function post(path,body){
 const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Symphony-Token':state.token},body:JSON.stringify(body)});
 const result=await r.json();if(!r.ok)throw Error(result.error||'Aktion fehlgeschlagen');return result;
}
function taskRows(tasks=state.tasks){return tasks.length ? tasks.slice().reverse().map(t=>`<div class="activity-row" tabindex="0" role="button" data-task="${esc(t.id)}" aria-label="Aufgabe ${esc(t.id)} öffnen"><span class="symbol">◇</span><div class="body"><b>${esc(t.instruction)}</b><small>${esc(t.id)} · ${esc(t.worker)}</small></div>${badge(t.status)}</div>`).join('') : empty('Keine Aufgaben in der lesbaren Courier-Quelle.');}
function composer(){const ready=state.intake.status==='READY';const label=ready?'Canonical Intake bereit':'Courier Runtime nicht verfügbar';const startup=state.runtime_start||{};const detail=ready?'Goal wird über den vorhandenen Courier-Intake übergeben. V2 wählt keinen Worker.':`Courier-Start: ${startup.action||'UNAVAILABLE'}. Keine lokale Ersatz-Queue.`;return `<section class="composer"><textarea id="goal" aria-label="Zielentwurf" maxlength="8000" placeholder="Schreibe dein Ziel oder stelle eine Frage …">${esc(draft)}</textarea><div class="composer-bottom"><span class="meta">◇ ${ready?'Canonical Courier Intake':'Run prüft zuerst den Canonical Runtime-Service'}</span><button id="save-draft">Entwurf speichern</button><button class="primary" id="run-goal" ${draft.trim()?'':'disabled'} title="${esc(label)}">RUN COURIER GOAL →</button></div></section><div class="notice">${badge(state.intake.status,ready?'good':'warn')}<span>${detail}</span></div>${runStatus?`<div class="notice">${badge('SUBMITTED','good')}<span>${esc(runStatus)}</span></div>`:''}`;}
function renderChat(){
 return `<section class="hero"><img src="/icon.svg" alt=""><div><div class="eyebrow">DEIN LOKALER WORKSPACE</div><h1>Guten Tag, ${esc(state.preferences.display_name)}</h1><p>Was möchtest du mit Courier erreichen?</p></div><div class="hero-note">Eine Idee.<br>Mehrere Agenten.<br>Belegbare Ergebnisse.</div></section><div class="tiles">${actions.map((a,i)=>`<button class="tile" data-template="${i}"><span class="tile-icon">${a[1]}</span><b>${a[0]}</b><small>${a[2]}</small></button>`).join('')}</div>${composer()}<div class="chips"><button data-nav="Terminal">⌘ Muse-Umgebung öffnen</button><button data-nav="Projekte">⑂ Repository ansehen</button><button data-nav="Evidenz">◇ Quellen prüfen</button><button data-nav="System-Status">◷ Courier-Stand</button></div><div class="section-head"><h2>Gespeicherte Aktivitäten</h2><button class="text-button" data-nav="Aktivität">Alle anzeigen →</button></div>${taskRows(state.tasks.slice(-4))}<p class="hint">Momentaufnahme aus Courier · keine neue Ausführung oder Abnahme durch V2.</p>`;
}
function projectView(){const p=state.project;return title('Projekte','Vorhandene lokale Ordner. Kein Repository wurde angelegt oder verändert.')+state.projects.map((x,i)=>`<section class="card"><span class="subtle-label">${i?'Workspace':'Aktives Projekt'}</span><h3>${esc(x.name)}</h3><code>${esc(x.path)}</code>${i?'':`<div class="divider"></div><div class="status-row"><span>Branch</span><span>${esc(p.branch)}</span></div><div class="status-row"><span>Arbeitsstand</span><span>${esc(p.worktree)}</span></div><div class="status-row"><span>Sync</span><span>${esc(p.sync)}</span></div><code>HEAD ${esc(p.head)}</code>`}<p><button data-open="${i?'repair':'project'}">Im Explorer öffnen ↗</button></p></section>`).join('');}
function planView(){return title('Plan','Der gespeicherte Courier-Plan. V2 verändert keine Aufgaben oder Zuständigkeiten.')+(state.goals.length?state.goals.map(g=>`<section class="card"><div class="section-head"><h3>${esc(g.id)}</h3>${badge(g.status)}</div><p>${esc(g.text)}</p>${g.steps.length?g.steps.map((s,i)=>`<div class="status-row"><span>${i+1}. ${esc(s.instruction)}</span><span>${badge(s.status)}</span></div>`).join(''):empty('Keine gespeicherten Planschritte.')}</section>`).join(''):empty('Kein gespeicherter Plan verfügbar.'));}
function filesView(){return title('Dateien','Dateiübersicht des aktuellen Projekts. Inhalte und vertrauliche Konfigurationen werden nicht geladen.')+`<section class="card"><div class="buttons"><button data-open="project">Projektordner öffnen ↗</button><button data-open="v2">V2-Ordner öffnen ↗</button></div><div class="divider"></div>${state.files.map(f=>`<div class="file-row"><span>${f.kind==='Ordner'?'▱':'▤'}</span>${esc(f.name)}<small>${f.kind}${f.size!==null?' · '+Math.ceil(f.size/1024)+' KB':''}</small></div>`).join('')}</section>`;}
function terminalView(){return title('Terminal','Die funktionierende Muse-Umgebung bleibt eigenständig und unverändert.')+`<section class="card"><img src="/icon.svg" alt="" width="48"><h3>Dein bewährtes Muse V1</h3><p>Öffnet genau die vorhandene Verknüpfung. Anmeldung, Modell, Berechtigungen und Strg+A/C/V werden von V2 nicht verändert.</p><pre>${esc(state.muse_launcher)}</pre><button class="primary" data-open="muse" ${state.muse_exists?'':'disabled'}>Muse öffnen ↗</button></section><section class="card"><h3>Courier-Arbeitsordner</h3><p>Öffne bei Bedarf ein Terminal über den vorhandenen Explorer. V2 installiert keinen Terminal-Emulator.</p><button data-open="project">Projektordner öffnen ↗</button></section>`;}
function agentCards(){return state.providers.map((p,i)=>`<section class="card"><div class="section-head"><h3>${esc(p.name)}</h3>${badge(p.status)}</div><p>${esc(p.detail)}</p>${i===0?'<button data-open="muse">Muse V1 öffnen ↗</button>':''}</section>`).join('');}
function agentsView(){return title('Agenten','Austauschbare Ausführende. Verfügbarkeit wird nur aus aktuellen Nachweisen abgeleitet.')+`<div class="card-grid">${agentCards()}</div><div class="section-head"><h2>Gespeicherte Worker-Registry</h2></div>${state.workers.length?state.workers.map(w=>`<section class="card"><div class="section-head"><h3>${esc(w.name)}</h3>${badge(w.status,w.status==='AVAILABLE'?'good':'')}</div><p>${esc(w.platform)} · ${esc(w.evidence)}</p><small>Letzter Heartbeat: ${timeLabel(w.seen)} · Aufgabe: ${esc(w.task)}</small></section>`).join(''):empty('Keine lesbare Worker-Registry.')}<p class="hint">Ein Heartbeat älter als 120 Sekunden ist kein Verfügbarkeitsnachweis.</p>`;}
function evidenceView(){return title('Evidenz','Exakte Dateiquellen und SHA-256. Vorhandene Prüfberichte sind keine neue Abnahme durch V2.')+state.sources.map(s=>`<section class="card"><div class="section-head"><h3>Courier-Quelle</h3>${badge(s.status)}</div><code>${esc(s.path)}</code><p>Geändert: ${timeLabel(s.modified)}</p><pre>SHA-256: ${esc(s.sha256||'UNKNOWN')}</pre></section>`).join('')+state.tasks.map(t=>`<section class="card"><h3>${esc(t.id)}</h3><small>Task-SHA-256</small><code>${esc(t.hash)}</code><p>Verifikation (gespeichert)</p><pre>${esc(t.verification)}</pre><p>Artefakt-Referenzen</p><pre>${esc(t.artifacts)}</pre></section>`).join('');}
function resultsView(){return title('Ergebnisse','Gespeicherte Resultat-IDs, Prüfstatus und Artefakt-Referenzen.')+(state.tasks.filter(t=>t.result_id!=='UNKNOWN').map(t=>`<section class="card"><div class="section-head"><h3>${esc(t.result_id)}</h3>${badge(t.status)}</div><p>${esc(t.id)} · ${esc(t.worker)}</p><small>Zeitstempel: ${esc(t.timestamp)}</small><pre>${esc(t.verification)}</pre><button data-task="${esc(t.id)}">Details und Referenzen →</button></section>`).join('')||empty('Keine DurableResult-ID in der gelesenen Momentaufnahme.'));}
function systemView(){return title('System-Status','Nur eine Ansicht auf Courier. Kein zweiter Scheduler, keine eigene Ledger-Wahrheit.')+`<section class="card">${state.system.map(([k,v])=>`<div class="status-row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join('')}</section><div class="notice">${badge('MOMENTAUFNAHME')}<span>Abgelesen: ${timeLabel(state.observed_at)}. Informationen können veraltet sein. Es läuft kein automatisches Polling.</span></div><p><button data-nav="Evidenz">Quelldateien und Hashes ansehen →</button></p>`;}
function settingsView(){return title('Einstellungen','Lokale Anzeigeoptionen. Sensible Einstellungen bleiben außerhalb von V2.')+`<section class="card"><h3>Dein Workspace</h3><label class="field">Anzeigename<input id="display-name" maxlength="60" value="${esc(state.preferences.display_name)}"></label><button id="save-name">Anzeigename speichern</button></section><section class="card"><h3>Verbindungen · schreibgeschützt</h3><div class="status-row"><span>Version</span><span>Courier Symphony 2.0 · lokal</span></div><div class="status-row"><span>Design</span><span>Midnight / Blau</span></div><p>Projekt</p><code>${esc(state.project.path)}</code><p>Muse-Starter</p><code>${esc(state.muse_launcher)}</code><div class="notice">Muse-Login, Sandbox, Modell, Tastenkürzel, Windows-Sicherheit und Provider-Konten besitzen hier keine Änderungsfunktion.</div></section><section class="card"><h3>V2 schließen</h3><p>Das Fenster kann jederzeit geschlossen werden. „V2 beenden“ stoppt zusätzlich nur diesen lokalen UI-Server. Courier und Muse laufen unabhängig weiter.</p><button id="shutdown">V2 beenden</button></section>`;}
function templatesView(name){return title(name,'Lokale Vorlagen für klare Ziele. Ein Klick füllt nur den Entwurf aus.')+`<div class="card-grid">${actions.map((a,i)=>`<section class="card"><h3>${a[0]}</h3><pre>${esc(a[3])}</pre><button data-template="${i}">Als Entwurf verwenden →</button></section>`).join('')}</div>`;}
function comingView(name){const descriptions={'Pull Requests':'GitHub ist nicht mit V2 verbunden. Es werden keine PRs angelegt oder verändert.','Geplant':'Die Zeitplanung bleibt beim bestehenden Courier. V2 startet keine Hintergrundaufgaben.','Plugins / Integrationen':'Neue Integrationen können später bewusst angebunden werden. Es werden keine Dienste installiert.','Entdecken':'Keine externen Kataloge oder kostenpflichtigen Dienste verbunden.'};return title(name,descriptions[name])+`<section class="card"><span class="subtle-label">Bewusst noch nicht verbunden</span><h3>${esc(name)}</h3>${badge('COMING LATER')}<p>${esc(descriptions[name])}</p><button data-nav="Chat">Zum Workspace →</button></section>`;}
function render(){
 if(!state)return;
 document.querySelectorAll('[data-nav]').forEach(b=>{b.classList.toggle('active',b.dataset.nav===current);if(b.getAttribute('role')==='tab')b.setAttribute('aria-selected',b.dataset.nav===current?'true':'false');});
 const views={'Chat':renderChat,'Projekte':projectView,'Plan':planView,'Dateien':filesView,'Terminal':terminalView,'Agenten':agentsView,'Evidenz':evidenceView,'Ergebnisse':resultsView,'System-Status':systemView,'Einstellungen':settingsView,'Aktivität':()=>title('Aktivität','Gespeicherte Aufgaben · keine live laufende Ausführung durch V2.')+taskRows(),'Bibliothek':()=>title('Bibliothek','Deine lokalen Arbeitsmittel und überprüfbaren Quellen.')+`<div class="card-grid"><section class="card"><h3>Vorlagen</h3><p>Fünf Zielvorlagen zum Weiterarbeiten.</p><button data-nav="Vorlagen">Vorlagen ansehen →</button></section><section class="card"><h3>Ergebnisse und Evidenz</h3><p>Vorhandene Courier-Artefakte nachvollziehen.</p><button data-nav="Evidenz">Evidenz ansehen →</button></section></div>`};
 $('content').innerHTML=views[current]?views[current]():['Prompts','Vorlagen'].includes(current)?templatesView(current):comingView(current);
}
function go(view){current=view;$('search').value='';render();window.scrollTo({top:0,behavior:'instant'});}
function renderContext(){
 const p=state.project;$('project-name').textContent=p.name;$('project-path').textContent=p.path;
 $('git-line').innerHTML=`<span>◉ ${esc(p.worktree)}</span><span>⑂ ${esc(p.branch)}</span>`;
 $('profile-name').textContent=state.preferences.display_name;$('avatar').textContent=state.preferences.display_name.slice(0,1).toUpperCase();
 $('project-nav').innerHTML=state.projects.map(p=>`<button class="project-link" data-nav="Projekte">▱ ${esc(p.name)}</button>`).join('');
 $('agents-mini').innerHTML=state.providers.slice(0,5).map((p,i)=>`<div class="agent"><span class="agent-icon">${i===0?'<img src="/icon.svg" alt="">':['','⌘','✧','▣','◇'][i]}</span><div class="body"><b>${esc(p.name)}</b><small>${i===0?'Vorhandener V1-Starter':'Verfügbarkeit nicht belegt'}</small></div>${badge(p.status)}</div>`).join('');
 $('status-mini').innerHTML=state.system.filter(([k])=>['Ledger / Trust','A → B','Unattended','Cost routing'].includes(k)).map(([k])=>`<div class="status-row"><span>${esc(k)}</span>${badge('UNKNOWN')}</div>`).join('');
 $('observed').textContent='Abgelesen '+timeLabel(state.observed_at)+' · kein Live-Status';
}
async function refresh(initial=false){
 $('refresh').disabled=true;
 try{const r=await fetch('/api/state');const data=await r.json();if(!r.ok)throw Error(data.error);state=data;if(initial)draft=state.draft.text;renderContext();render();if(!initial)toast('Momentaufnahme aktualisiert.');}
 catch(e){toast(e.message);if(!state)$('content').innerHTML=title('Quelle nicht erreichbar','Die Oberfläche konnte keine lokalen Daten laden. Bitte über Aktualisieren erneut versuchen.');}
 finally{$('refresh').disabled=false;}
}
document.addEventListener('input',e=>{if(e.target.id==='goal'){draft=e.target.value;const run=$('run-goal');if(run)run.disabled=!draft.trim();}});
document.addEventListener('click',async e=>{
 const el=e.target.closest('button,[data-task]');if(!el)return;
 try{
  if(el.dataset.nav)go(el.dataset.nav);
  if(el.dataset.template!==undefined){draft=actions[Number(el.dataset.template)][3];go('Chat');$('goal').focus();}
  if(el.dataset.open){el.disabled=true;await post('open',{action:el.dataset.open});toast(el.dataset.open==='muse'?'Vorhandener Muse-Starter geöffnet.':'Ordner geöffnet.');el.disabled=false;}
  if(el.dataset.task){$('detail-text').textContent=JSON.stringify(state.tasks.find(t=>t.id===el.dataset.task),null,2);$('detail').showModal();}
  if(el.id==='close-detail')$('detail').close();
  if(el.id==='save-draft'){await post('draft',{text:draft});toast('Entwurf lokal gespeichert. Kein Auftrag wurde gestartet.');}
  if(el.id==='run-goal'){el.disabled=true;const result=await post('run-goal',{goal_text:draft});runStatus='Goal '+result.goal.goal_id+' wurde an Courier übergeben.';await refresh();toast('SUBMITTED · '+runStatus);}
  if(el.id==='save-name'){await post('preferences',{display_name:$('display-name').value});await refresh();toast('Anzeigename gespeichert.');}
  if(el.id==='refresh')await refresh();
  if(el.id==='shutdown'){await post('shutdown',{});document.body.innerHTML='<div class="card"><h1>Courier Symphony ist beendet.</h1><p>Du kannst dieses Fenster schließen. Muse V1 und Courier wurden nicht gestoppt.</p></div>';}
 }catch(err){el.disabled=false;toast(err.message);}
});
document.addEventListener('keydown',e=>{
 if(e.ctrlKey&&e.key.toLowerCase()==='k'){e.preventDefault();$('search').focus();}
 if(e.ctrlKey&&e.key.toLowerCase()==='n'){e.preventDefault();go('Chat');$('goal').focus();}
 if(e.key==='Enter'&&e.target.matches('[data-task]'))e.target.click();
});
$('search').addEventListener('input',e=>{
 const term=e.target.value.toLowerCase().trim();if(!term){render();return;}
 const pages=['Chat','Dateien','Terminal','Aktivität','System-Status',...nav.filter(a=>a.length===2).map(a=>a[0])];
 $('content').innerHTML=title('Suchen','Ansichten und lokale Aktionen.')+pages.filter(p=>p.toLowerCase().includes(term)).map(p=>`<button class="search-result" data-nav="${esc(p)}">${esc(p)} →</button>`).join('');
});
$('navigation').innerHTML=nav.map(a=>a.length===1?`<div class="side-label">${a[0]}</div>`:`<button data-nav="${a[0]}"><span class="nav-icon">${a[1]}</span>${a[0]}</button>`).join('');
refresh(true);
