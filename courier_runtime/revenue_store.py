"""Durable storage for the revenue engine: Leads and Jobs as append-only JSONL
under <home>/revenue/, plus the monthly self-funding dashboard.

Every save appends a full snapshot; loading keeps the last snapshot per id, so
history is never rewritten. A torn last line (crash mid-write) is skipped.

Usage:
  python -m courier_runtime.revenue_store dashboard --home H --month 2026-10 [--monthly-cost 183]
"""
import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

from courier_runtime.revenue import Job, Lead, self_funding

DEFAULT_MONTHLY_COST_EUR = 183


class RevenueStore:
    def __init__(self, home):
        self.dir = Path(home) / "revenue"
        self.leads_path = self.dir / "leads.jsonl"
        self.jobs_path = self.dir / "jobs.jsonl"

    def _append(self, path, record):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _latest(path, key):
        latest = {}
        if not path.exists():
            return latest
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            latest[record[key]] = record
        return latest

    def save_lead(self, lead):
        self._append(self.leads_path, dataclasses.asdict(lead))

    def save_job(self, job):
        self._append(self.jobs_path, dataclasses.asdict(job))

    def leads(self):
        return [Lead(**r) for r in self._latest(self.leads_path, "lead_id").values()]

    def jobs(self):
        return [Job(**r) for r in self._latest(self.jobs_path, "job_id").values()]

    def dashboard(self, month, monthly_cost_eur=DEFAULT_MONTHLY_COST_EUR):
        """Self-funding for one month (YYYY-MM): jobs paid or delivered in that month."""
        jobs = []
        for j in self.jobs():
            # revenue lands in the month it was paid; costs and delivery stats in the
            # month it was delivered (or paid, if no delivery date) - never twice
            revenue_here = bool(j.paid_on) and j.paid_on.startswith(month)
            cost_here = (j.delivered_on or j.paid_on).startswith(month) if (j.delivered_on or j.paid_on) else False
            if revenue_here and cost_here:
                jobs.append(j)
            elif revenue_here:
                jobs.append(dataclasses.replace(j, delivered=False, model_cost_eur=0.0, cloud_cost_eur=0.0,
                                                api_cost_eur=0.0, other_direct_cost_eur=0.0, human_minutes=0))
            elif cost_here:
                jobs.append(dataclasses.replace(j, paid=False))
        result = self_funding(jobs, monthly_cost_eur)
        result["month"] = month
        result["leads_by_state"] = {}
        for lead in self.leads():
            result["leads_by_state"][lead.state] = result["leads_by_state"].get(lead.state, 0) + 1
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="courier_runtime.revenue_store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dashboard")
    d.add_argument("--home", default=os.environ.get("COURIER_HOME", os.getcwd()))
    d.add_argument("--month", required=True)
    d.add_argument("--monthly-cost", type=float, default=DEFAULT_MONTHLY_COST_EUR)
    args = parser.parse_args(argv)
    print(json.dumps(RevenueStore(args.home).dashboard(args.month, args.monthly_cost), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
