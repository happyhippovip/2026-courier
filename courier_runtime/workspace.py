"""Smallest executable "Courier's own computer" loop.

INTENT -> WORKKEY -> HOST SELECTION -> WORK LEASE -> GRANT -> OWNED EXECUTION
-> HEARTBEAT -> EVIDENCE -> ACCEPTED STATE -> CHECKPOINT -> DONE, and after a
device loss: RECOVERY RECEIPT -> NEW ELIGIBLE HOST -> AUTHORITY REVALIDATION
-> CONTINUE FROM THE LAST ACCEPTED STEP.

Each step is a command run as a process Courier owns; a step is accepted
only when its process exits 0 and its declared output exists, and the
accepted fact cites that evidence. Hosts here are local device identities;
the same loop runs unchanged when a host is a real remote machine.
"""
import hashlib
import os
import subprocess
from dataclasses import dataclass

from courier_runtime.continuation import AcceptedFact, AcceptedLog, Checkpoint, decide
from courier_runtime.grants import GRANTED
from courier_runtime.hosts import Evidence, select
from courier_runtime.lease import StaleLease
from courier_runtime.ownership import OwnedProcess


@dataclass(frozen=True)
class Step:
    name: str
    argv: list
    output: str                    # file the step must produce
    effect_class: str = "idempotent"


class Workspace:
    def __init__(self, *, hosts, lease_store, broker, accepted_log, registry, workdir, clock, lease_ttl_s=30):
        self.hosts, self.leases, self.broker = hosts, lease_store, broker
        self.log, self.registry, self.workdir, self.clock = accepted_log, registry, workdir, clock
        self.ttl = lease_ttl_s
        self.evidence = []

    def run(self, workkey, requirement, scope, request, steps, host=None, stop_after=None):
        """Run steps from the last accepted one. Returns the decision dict of the final state.

        stop_after: simulate a device loss after starting that step (process left running).
        """
        host = host or select(requirement, self.hosts)
        checkpoint = Checkpoint.from_log(workkey, [s.name for s in steps], self.log, lease_scope=scope)
        grant, state, reason = self.broker.authorize(request)
        if state != GRANTED:
            return {"state": "NEEDS_USER", "reasons": [f"authority required: {reason}"], "host": host.device_id}
        checkpoint.grant_ids = [grant.grant_id]
        owned_alive = [r.pid for r in self.registry.owned(workkey) if _alive(r)]
        lease_free = self.leases.current(scope) is None or self.leases.current(scope).holder == host.device_id
        decision = decide(checkpoint, grants_valid={grant.grant_id: True}, owned_alive=owned_alive,
                          lease_available=lease_free)
        # resume_step None means do not run. `None or 0` would restart at step 0.
        if not decision["safe"] or decision.get("resume_step") is None:
            return {**decision, "host": host.device_id}
        lease = self.leases.acquire(scope, host.device_id, workkey, ttl_s=self.ttl)
        for index in range(decision["resume_step"], len(steps)):
            step = steps[index]
            proc = subprocess.Popen(step.argv, cwd=self.workdir, stdin=subprocess.DEVNULL)
            self.registry.add(OwnedProcess.capture(proc.pid, workkey, host.device_id))
            if stop_after == index:
                return {"state": "DEVICE_LOST", "host": host.device_id, "step": index, "pid": proc.pid}
            code = proc.wait(timeout=60)
            lease = self.leases.renew(lease, ttl_s=self.ttl)          # heartbeat after progress
            self.registry.stop(workkey)                                  # nothing of ours left behind
            out = os.path.join(self.workdir, step.output)
            passed = code == 0 and os.path.exists(out)
            ev = Evidence(workkey, "python", host.device_id, _sha256(out) if passed else "", passed)
            self.evidence.append(ev)
            if not passed:
                return {"state": "FAILED", "host": host.device_id, "step": index, "reasons": [f"exit {code}"]}
            self.leases.check_write(scope, lease.token)                 # fenced: only the lease holder accepts
            self.log.append(AcceptedFact(workkey, index, f"{step.name} produced {step.output}",
                                         (f"evidence:{ev.artifact_sha256}",), "controller", self.clock()))
        self.leases.release(lease)
        return {"state": "DONE", "host": host.device_id, "steps": len(steps)}


def _alive(record):
    from courier_runtime.ownership import is_same_process
    return is_same_process(record)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()
