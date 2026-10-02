from dataclasses import dataclass, field
from typing import Set, Dict, List, Any

@dataclass(frozen=True)
class SystemState:
    version: str
    capabilities: Set[str]
    behaviors: Dict[str, str]

@dataclass(frozen=True)
class UpdateManifest:
    id: str
    target_version: str
    capabilities: Set[str]
    behaviors: Dict[str, str]
    evidence_refs: List[str]
    rollback_metadata: Dict[str, Any]

@dataclass(frozen=True)
class SemanticDelta:
    removed_capabilities: Set[str]
    added_capabilities: Set[str]
    changed_behaviors: Dict[str, tuple]  # key -> (old_val, new_val)

@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    reason: str
    rollback_metadata: Dict[str, Any]

class SemanticUpdateGate:
    """
    Deterministic skeleton for validating updates semantically.
    BEFORE_ACCEPTED_STATE -> APPLY_TEST_UPDATE -> AFTER_STATE -> SEMANTIC_DELTA -> ACCEPT / REJECT.
    """

    @staticmethod
    def apply_test_update(before: SystemState, update: UpdateManifest) -> SystemState:
        """Simulates the update to produce the AFTER_STATE."""
        return SystemState(
            version=update.target_version,
            capabilities=update.capabilities,
            behaviors=update.behaviors
        )

    @staticmethod
    def compute_delta(before: SystemState, after: SystemState) -> SemanticDelta:
        """Derives the SEMANTIC_DELTA comparing BEFORE and AFTER states."""
        removed = before.capabilities - after.capabilities
        added = after.capabilities - before.capabilities
        
        changed = {}
        for k, v in before.behaviors.items():
            if k not in after.behaviors:
                changed[k] = (v, None)
            elif after.behaviors[k] != v:
                changed[k] = (v, after.behaviors[k])
                
        for k, v in after.behaviors.items():
            if k not in before.behaviors:
                changed[k] = (None, v)
                
        return SemanticDelta(
            removed_capabilities=removed, 
            added_capabilities=added, 
            changed_behaviors=changed
        )

    @staticmethod
    def evaluate(before: SystemState, update: UpdateManifest) -> GateDecision:
        """Gate logic to ACCEPT or REJECT an update based on the semantic delta."""
        if not update.evidence_refs:
            return GateDecision(False, "REJECT: evidence missing", update.rollback_metadata)
            
        after = SemanticUpdateGate.apply_test_update(before, update)
        delta = SemanticUpdateGate.compute_delta(before, after)
        
        # Rule 1: No capabilities can be removed
        if delta.removed_capabilities:
            return GateDecision(
                False, 
                f"REJECT: capability removed: {sorted(delta.removed_capabilities)}", 
                update.rollback_metadata
            )
            
        # Rule 2: Existing behaviors cannot be altered or removed (adding new ones is fine)
        for k, (old_v, new_v) in delta.changed_behaviors.items():
            if old_v is not None and new_v is not None:
                return GateDecision(
                    False, 
                    f"REJECT: behavior changed for '{k}'", 
                    update.rollback_metadata
                )
            if old_v is not None and new_v is None:
                return GateDecision(
                    False, 
                    f"REJECT: behavior removed for '{k}'", 
                    update.rollback_metadata
                )
                
        return GateDecision(True, "ACCEPT", update.rollback_metadata)
