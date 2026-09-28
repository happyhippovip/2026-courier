#!/usr/bin/env python3
import argparse, json, os, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"ops"/"ai"/"usage"/"USAGE_ROLLUP_CURRENT.json"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--provider",required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--task",required=True)
    p.add_argument("--input",type=int,default=0)
    p.add_argument("--cached",type=int,default=0)
    p.add_argument("--output",type=int,default=0)
    p.add_argument("--turns",type=int,default=0)
    p.add_argument("--subagents",type=int,default=0)
    p.add_argument("--status",default="UNKNOWN")
    p.add_argument("--useful-findings",type=int,default=0)
    p.add_argument("--duplicates-skipped",type=int,default=0)
    a=p.parse_args()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    data={"schema_version":"1.0","records":[]}
    if OUT.exists():
        try: data=json.loads(OUT.read_text(encoding="utf-8"))
        except Exception: pass
    rec={
      "recorded_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "provider_class":a.provider,
      "model_class":a.model,
      "task_id":a.task,
      "input_tokens":max(0,a.input),
      "cached_tokens":max(0,a.cached),
      "output_tokens":max(0,a.output),
      "turns":max(0,a.turns),
      "subagents_used":max(0,a.subagents),
      "status":a.status,
      "useful_findings":max(0,a.useful_findings),
      "duplicates_skipped":max(0,a.duplicates_skipped),
    }
    # Deliberately no account/subscription/payment/reset fields.
    data.setdefault("records",[]).append(rec)
    data["records"]=data["records"][-200:]
    tmp=OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2)+"
",encoding="utf-8")
    os.replace(tmp,OUT)
    print(json.dumps(rec,indent=2))
if __name__=="__main__": main()
