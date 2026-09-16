# DEPENDENCY GRAPH: COURIER ARCHITECTURE

```mermaid
graph TD
    Goal[Goal Management Plane] --> Planner[Task Planner & Decomposer]
    Planner --> BorderGuard[Border Guard Pre-Dispatch Gate]
    BorderGuard --> Dispatcher[Authoritative Dispatcher Core]
    
    subgraph Execution & Concurrency
        Dispatcher --> Fence[Dispatcher Uncertainty Fence]
        Dispatcher --> Mutex[Hierarchical No-Stacking Mutex]
        Dispatcher --> Governor[Resource Governor & Concurrency Throttle]
        Dispatcher --> Supervisor[Process Supervisor & Identity Verifier]
    end
    
    subgraph Verification & Satisfaction
        Supervisor --> Customs[Result Customs & AST Weakening Detector]
        Customs --> Verifier[Independent Goal Verifier]
        Verifier --> Journal[Durable Append-Only Journal]
    end
    
    subgraph Safety & Fault Handling
        Reconciler[Crash & Restart Reconciler] --> Fence
        Reconciler --> Mutex
        DeadlockResolver[Deadlock Cycle Detector] --> Rollback[Atomic Rollback Engine]
        Rollback --> Mutex
        SpendGov[Zero-Spend & Human-Gate Governor] --> BorderGuard
        SpendGov --> Dispatcher
    end
```

### Critical Dependency Rules
1. **Dispatcher Dominance**: No task execution may bypass `BorderGuard`, `Fence`, and `Mutex`.
2. **Reconciliation Priority**: On restart, `Reconciler` must run before any new task dispatch.
3. **Rollback Preemption**: Deadlock resolver triggers `Rollback` which cleanly releases `Mutex` leases before re-enqueuing tasks.
4. **Independent Satisfaction**: `Goal` state updates only after `Verifier` validates deliverable hashes against `Journal` events.
