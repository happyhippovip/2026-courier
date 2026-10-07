# Courier Desktop Swarm Overlay - W14 Acceptance Matrix

This document defines the strict physical acceptance criteria for the Desktop Robot Overlay (Issue #55) to pass the locked product route gate.

## 1. W10 Architecture & Containment
- [ ] NO LLM-token dependency for overlay rendering/animation.
- [ ] Overlay shell separates cleanly from Windows L3 Worker Host processes.
- [ ] Replay journal explicitly maps to W12 specifications.

## 2. W11 Layout Engine
- [ ] Geometry tests pass 12, 14, and 16 profile grids automatically.
- [ ] Layout scales gracefully without unbounded constraints (no RenderFlex overflows).
- [ ] macOS WindowAdapter handles permission denials and cleanly restores previous state.

## 3. W12 Visual Replay
- [ ] Event consumer correctly maps bus events to visual states (`IDLE`, `CUSTOMS`, `BLOCKED`, `WORKING`).
- [ ] Bus retry rules successfully fold identical task/event entries idempotently.
- [ ] Dropped events/foreign IDs never surface visually to the replay client.

## 4. W13 Desktop Swarm Overlay
- [ ] Agent worker windows visibly render their task summaries up to 240 chars.
- [ ] Visual state updates occur within <100ms of local event bus write.
- [ ] Render limits hold steady memory profile after 1000 simulated task events.
- [ ] UI accurately represents concurrent parallel worker claims without dropping visually.

## 5. Clean-Machine Integration
- [ ] W14 End-to-end integration verifies no credentials/secrets can be leaked in overlay bus payloads.
- [ ] Starts reliably via W10 Desktop Hub local startup routine.
- [ ] Shuts down cleanly without leaving orphan layout processes.
