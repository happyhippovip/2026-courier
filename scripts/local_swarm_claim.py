#!/usr/bin/env python3
import argparse,json,os,shutil,socket,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/"ops"/"ai"/"AUTO_SWARM_TASKBANK_2026-09-28.json"
STATE=ROOT/".courier_swarm"; CLAIMS=STATE/"claims"; DONE=STATE/"done"; BLOCKED=STATE/"blocked"; LOCKS=STATE/"locks"; STOP=STATE/"STOP"
def ensure():
    for p in (STATE,CLAIMS,DONE,BLOCKED,LOCKS): p.mkdir(parents=True,exist_ok=True)
def bank(): return json.loads(BANK.read_text(encoding="utf-8"))["tasks"]
def emit(x): print(json.dumps(x,ensure_ascii=False,indent=2))
def claim(pool):
    ensure()
    if STOP.exists(): emit({"status":"STOPPED","reason":STOP.read_text(encoding="utf-8",errors="ignore")}); return 3
    for t in bank():
        if t["pool"]!=pool: continue
        tid=t["id"]
        if (DONE/f"{tid}.json").exists() or (BLOCKED/f"{tid}.json").exists(): continue
        c=CLAIMS/tid
        try: c.mkdir()
        except FileExistsError: continue
        group=t.get("exclusive_group"); gd=None
        if group:
            gd=LOCKS/group
            try: gd.mkdir()
            except FileExistsError: shutil.rmtree(c,ignore_errors=True); continue
        token=uuid.uuid4().hex
        meta={"task_id":tid,"token":token,"pool":pool,"host":socket.gethostname(),"pid":os.getpid(),"claimed_at":time.time(),"exclusive_group":group}
        (c/"claim.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
        if gd: (gd/"owner.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
        emit({"status":"CLAIMED","claim_token":token,"task":t}); return 0
    emit({"status":"NO_TASK","pool":pool}); return 2
def readclaim(tid):
    p=CLAIMS/tid/"claim.json"
    if not p.exists(): raise SystemExit("no live claim")
    return json.loads(p.read_text(encoding="utf-8"))
def unlock(m):
    shutil.rmtree(CLAIMS/m["task_id"],ignore_errors=True)
    g=m.get("exclusive_group")
    if g:
        p=LOCKS/g/"owner.json"
        try:
            cur=json.loads(p.read_text(encoding="utf-8"))
            if cur.get("token")==m.get("token"): shutil.rmtree(LOCKS/g,ignore_errors=True)
        except Exception: pass
def finish(kind,tid,token,summary):
    ensure(); m=readclaim(tid)
    if m.get("token")!=token: raise SystemExit("claim token mismatch")
    rec={"task_id":tid,"claim_token":token,"finished_at":time.time(),"host":socket.gethostname(),"summary":summary}
    target=(DONE if kind=="complete" else BLOCKED)/f"{tid}.json"; tmp=target.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8"); os.replace(tmp,target); unlock(m)
    emit({"status":"DONE" if kind=="complete" else "BLOCKED","task_id":tid}); return 0
def status():
    ensure(); d={}
    for t in bank(): d.setdefault(t["pool"],{"total":0,"done":0,"blocked":0,"claimed":0}); d[t["pool"]]["total"]+=1
    for name,folder in (("done",DONE),("blocked",BLOCKED)):
        for p in folder.glob("*.json"):
            t=next((x for x in bank() if x["id"]==p.stem),None)
            if t:d[t["pool"]][name]+=1
    for p in CLAIMS.iterdir():
        if p.is_dir():
            t=next((x for x in bank() if x["id"]==p.name),None)
            if t:d[t["pool"]]["claimed"]+=1
    emit({"stopped":STOP.exists(),"pools":d}); return 0
def main():
    a=argparse.ArgumentParser(); s=a.add_subparsers(dest="cmd",required=True)
    c=s.add_parser("claim"); c.add_argument("--pool",required=True,choices=["windows-google","mac-google","muse"])
    for n in ("complete","block","release"):
        p=s.add_parser(n); p.add_argument("--task-id",required=True); p.add_argument("--token",required=True)
        if n!="release": p.add_argument("--summary",default="")
    st=s.add_parser("stop"); st.add_argument("--reason",default="operator emergency stop")
    s.add_parser("resume"); s.add_parser("status"); x=a.parse_args(); ensure()
    if x.cmd=="claim": return claim(x.pool)
    if x.cmd=="complete": return finish("complete",x.task_id,x.token,x.summary)
    if x.cmd=="block": return finish("block",x.task_id,x.token,x.summary)
    if x.cmd=="release":
        m=readclaim(x.task_id)
        if m.get("token")!=x.token: raise SystemExit("claim token mismatch")
        unlock(m); emit({"status":"RELEASED","task_id":x.task_id}); return 0
    if x.cmd=="status": return status()
    if x.cmd=="stop": STOP.write_text(x.reason,encoding="utf-8"); emit({"status":"STOPPED","reason":x.reason}); return 0
    if x.cmd=="resume": STOP.unlink(missing_ok=True); emit({"status":"RESUMED"}); return 0
if __name__=="__main__": raise SystemExit(main())
