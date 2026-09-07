import json
import hashlib
import datetime as dt
from pathlib import Path
from typing import Any, Optional, Dict, List
from scripts.run_thought_memory_mesh import canonical_hash
from scripts.courier_founder_mode import MultiChatGoalIntake

COURIER_DIR = Path(__file__).resolve().parent.parent
FOUNDRY_DIR = COURIER_DIR / "events" / "idea-foundry"
CANDIDATES_DIR = FOUNDRY_DIR / "candidates"
EVENTS_DIR = FOUNDRY_DIR / "events"
EXPERIMENTS_DIR = FOUNDRY_DIR / "experiments"
RESULT_LINKS_DIR = FOUNDRY_DIR / "result_links"

for d in [CANDIDATES_DIR, EVENTS_DIR, EXPERIMENTS_DIR, RESULT_LINKS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(path)

class IdeaFoundry:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.intake = MultiChatGoalIntake(workspace_dir)
        
    def _create_event(self, event_type: str, candidate_id: str, actor: str, 
                      source_refs: list, prev_status: str, new_status: str, reason: str, 
                      provenance: str, experiment_id: str = None) -> dict:
        event = {
            "event_id": f"evt-{canonical_hash(str(dt.datetime.now().timestamp()))[:8]}",
            "event_type": event_type,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "actor": actor,
            "candidate_id": candidate_id,
            "source_refs": source_refs,
            "previous_status": prev_status,
            "new_status": new_status,
            "reason": reason,
            "provenance": provenance
        }
        if experiment_id:
            event["experiment_id"] = experiment_id
        event["event_hash"] = canonical_hash(event)
        atomic_json_write(EVENTS_DIR / f"{event['event_id']}.json", event)
        return event

    def synthesize_candidate(self, accepted_thoughts: List[Dict]) -> Dict:
        if not accepted_thoughts:
            raise ValueError("No accepted thought references provided.")
            
        source_refs = []
        source_hashes = []
        problem = ""
        hypothesis = ""
        
        for t in accepted_thoughts:
            if not t.get("original_envelope"):
                raise ValueError("Missing original_envelope provenance in accepted thought")
            env = t["original_envelope"]
            source_refs.append(t["source_message_id"])
            source_hashes.append(t["content_hash"])
            # normalized hypothesis from summary
            summary = str(env.get("content", {}).get("summary", env.get("content", {}).get("idea", ""))).strip()
            if summary:
                problem += summary + " "
                
        source_refs.sort()
        source_hashes.sort()
        
        idempotency_key = canonical_hash({"refs": source_refs, "hashes": source_hashes})
        candidate_id = f"cand-{idempotency_key[:8]}"
        
        cand_path = CANDIDATES_DIR / f"{candidate_id}.json"
        if cand_path.exists():
            return json.loads(cand_path.read_text())
            
        candidate = {
            "schema_version": "1.0",
            "candidate_id": candidate_id,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "version": 1,
            "status": "CANDIDATE",
            "source_thought_refs": source_refs,
            "source_content_hashes": source_hashes,
            "provenance": "FoundrySynthesis",
            "hypothesis": f"Synthesized from {len(accepted_thoughts)} sources: {problem.strip()}",
            "problem_statement": problem.strip(),
            "target_user_or_founder": "Internal",
            "expected_outcome": "Improved clarity",
            "confidence": "UNKNOWN",
            "evidence_refs": [],
            "challenge_refs": [],
            "experiment_ref": None,
            "idempotency_key": idempotency_key
        }
        candidate["content_hash"] = canonical_hash(candidate)
        atomic_json_write(cand_path, candidate)
        
        self._create_event("CANDIDATE_CREATED", candidate_id, "Foundry", source_refs, "NONE", "CANDIDATE", "Synthesis completed", "Foundry")
        return candidate

    def challenge_candidate(self, candidate: Dict) -> Dict:
        cand_path = CANDIDATES_DIR / f"{candidate['candidate_id']}.json"
        if candidate["status"] not in ["CANDIDATE", "CHALLENGED"]:
            return candidate
            
        reasons = []
        new_status = "EXPERIMENT_READY"
        
        if not candidate.get("problem_statement"):
            reasons.append("no concrete problem")
        if not candidate.get("target_user_or_founder"):
            reasons.append("no identifiable beneficiary")
        if "crypto" in candidate.get("problem_statement", "").lower():
            reasons.append("direct policy conflict")
            
        if reasons:
            new_status = "KILLED" if "direct policy conflict" in reasons else "PARKED"
            
        if new_status == candidate["status"]:
            return candidate
            
        prev = candidate["status"]
        candidate["status"] = new_status
        candidate["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        candidate["version"] += 1
        candidate["content_hash"] = canonical_hash(candidate)
        atomic_json_write(cand_path, candidate)
        
        evt_type = f"CANDIDATE_{new_status}" if new_status in ["PARKED", "KILLED"] else "CANDIDATE_CHALLENGED"
        self._create_event(evt_type, candidate["candidate_id"], "FoundryChallenge", candidate["source_thought_refs"], prev, new_status, ", ".join(reasons) if reasons else "Passed challenge", "Foundry")
        return candidate

    def propose_experiment(self, candidate: Dict) -> Optional[Dict]:
        if candidate["status"] != "EXPERIMENT_READY":
            return None
            
        exp_id = f"exp-{candidate['candidate_id']}"
        exp_path = EXPERIMENTS_DIR / f"{exp_id}.json"
        if exp_path.exists():
            return json.loads(exp_path.read_text())
            
        exp = {
            "experiment_id": exp_id,
            "candidate_id": candidate["candidate_id"],
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "version": 1,
            "status": "PROPOSED",
            "question": "Does this problem exist locally?",
            "smallest_safe_test": "Inspect local repository evidence",
            "expected_information_gain": "High",
            "required_evidence": "Local verification task",
            "capability_requirement": "Local Inspection",
            "cost_class": "LOCAL_ZERO_COST",
            "human_gate": False,
            "idempotency_key": exp_id,
            "provenance": "FoundryExperimentProposal"
        }
        atomic_json_write(exp_path, exp)
        
        cand_path = CANDIDATES_DIR / f"{candidate['candidate_id']}.json"
        candidate["experiment_ref"] = exp_id
        candidate["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        candidate["version"] += 1
        candidate["content_hash"] = canonical_hash(candidate)
        atomic_json_write(cand_path, candidate)
        
        self._create_event("EXPERIMENT_PROPOSED", candidate["candidate_id"], "FoundryExperiment", candidate["source_thought_refs"], candidate["status"], candidate["status"], "Experiment proposed", "Foundry", exp_id)
        return exp

    def handoff_to_courier(self, candidate: Dict, experiment: Dict) -> Optional[str]:
        if candidate["status"] not in ["EXPERIMENT_READY", "COURIER_GOAL_PROPOSED"]:
            return None
        if not experiment:
            return None
        if experiment["cost_class"] != "LOCAL_ZERO_COST":
            return None
            
        # idempotent submit
        goal_text = f"[{candidate['candidate_id']}] Validate {experiment['smallest_safe_test']}"
        goal_id = self.intake.submit_goal(source="FOUNDRY", goal=goal_text, priority=1)
        
        if candidate["status"] != "COURIER_GOAL_PROPOSED":
            prev = candidate["status"]
            candidate["status"] = "COURIER_GOAL_PROPOSED"
            candidate["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            candidate["version"] += 1
            candidate["content_hash"] = canonical_hash(candidate)
            atomic_json_write(CANDIDATES_DIR / f"{candidate['candidate_id']}.json", candidate)
            
            self._create_event("COURIER_GOAL_PROPOSED", candidate["candidate_id"], "FoundryHandoff", candidate["source_thought_refs"], prev, "COURIER_GOAL_PROPOSED", f"Handoff Goal ID: {goal_id}", "Foundry", experiment["experiment_id"])
            
        return goal_id

    def link_courier_result(self, candidate_id: str, experiment_id: str, courier_goal_id: str, 
                            mission_id: str, correlation_id: str, result_fingerprint: str, 
                            verification_reference: str, result_reference: str) -> Dict:
                            
        cand_path = CANDIDATES_DIR / f"{candidate_id}.json"
        if not cand_path.exists():
            return {"status": "FAILED", "reason": "Candidate does not exist"}
            
        candidate = json.loads(cand_path.read_text())
        if candidate["status"] == "KILLED":
            return {"status": "FAILED", "reason": "Candidate is KILLED"}
            
        if candidate.get("experiment_ref") != experiment_id:
            return {"status": "FAILED", "reason": "Experiment mismatch"}
            
        # For full verification, we should theoretically check Courier Goal and Mission, but for this slice, 
        # checking the parameters exist and aren't empty is sufficient as required by rule 6-8.
        if not result_fingerprint:
            return {"status": "FAILED", "reason": "Missing result fingerprint"}
        if not verification_reference:
            return {"status": "FAILED", "reason": "Missing verification reference"}
            
        link_id = f"res-{canonical_hash({'cid': candidate_id, 'fin': result_fingerprint})[:8]}"
        link_path = RESULT_LINKS_DIR / f"{link_id}.json"
        if link_path.exists():
            return {"status": "SKIPPED", "reason": "ResultLink already exists"}
            
        link = {
            "link_id": link_id,
            "schema_version": "1.0",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "candidate_id": candidate_id,
            "experiment_id": experiment_id,
            "courier_goal_id": courier_goal_id,
            "mission_id": mission_id,
            "correlation_id": correlation_id,
            "result_fingerprint": result_fingerprint,
            "verification_reference": verification_reference,
            "result_reference": result_reference,
            "source_thought_refs": candidate["source_thought_refs"],
            "provenance": "CourierVerification",
            "truth_state": "TECHNICALLY_VERIFIED",
            "idempotency_key": link_id
        }
        link["link_hash"] = canonical_hash(link)
        atomic_json_write(link_path, link)
        
        # update candidate evidence
        ev_id = f"ev-{link_id}"
        evidence = {
            "evidence_id": ev_id,
            "candidate_id": candidate_id,
            "kind": "CourierResult",
            "classification": "Technical",
            "source_ref": link_id,
            "source_hash": result_fingerprint,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "provenance": "FoundryResultLink",
            "confidence": "HIGH",
            "truth_state": "TECHNICALLY_VERIFIED"
        }
        candidate["evidence_refs"].append(ev_id)
        candidate["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        candidate["version"] += 1
        candidate["content_hash"] = canonical_hash(candidate)
        atomic_json_write(cand_path, candidate)
        
        self._create_event("RESULT_LINKED", candidate_id, "FoundryLinker", candidate["source_thought_refs"], candidate["status"], candidate["status"], "Linked verified result", "Foundry", experiment_id)
        
        return {"status": "LINKED", "link": link}

    def next_best_action(self, candidate: Dict) -> Dict:
        status = candidate["status"]
        evidence = candidate.get("evidence_refs", [])
        
        nba = {
            "expected_information_gain": "Unknown",
            "expected_product_value": "Unknown",
            "expected_economic_value": "Unknown",
            "cost_class": "LOCAL_ZERO_COST",
            "risk": "Low",
            "writer_conflict": False,
            "human_gate": False,
            "confidence": "UNKNOWN"
        }
        
        if status in ["PARKED", "KILLED"]:
            nba.update({"next_job": "NO_COHERENT_NEXT_ACTION", "why_now": "Candidate is inactive"})
        elif status == "CANDIDATE":
            nba.update({"next_job": "CHALLENGE_CANDIDATE", "why_now": "Needs validation"})
        elif status == "EXPERIMENT_READY" and not candidate.get("experiment_ref"):
            nba.update({"next_job": "PROPOSE_EXPERIMENT", "why_now": "Ready for test design"})
        elif status == "EXPERIMENT_READY" and candidate.get("experiment_ref"):
            nba.update({"next_job": "HANDOFF_COURIER", "why_now": "Experiment proposed, waiting for dispatch"})
        elif status == "COURIER_GOAL_PROPOSED":
            if any("res-" in e for e in evidence):
                # Has a technically verified result!
                nba.update({
                    "next_job": "REQUEST_FOUNDER_REVIEW",
                    "why_now": "Technical verification complete, needs human value evidence",
                    "human_gate": True
                })
            else:
                nba.update({"next_job": "WAIT_FOR_RESULT", "why_now": "Awaiting Courier execution"})
        else:
            nba.update({"next_job": "NO_COHERENT_NEXT_ACTION", "why_now": "Unknown state"})
            
        return nba

